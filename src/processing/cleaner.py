# Clean raw JSON data from MinIO: drop incomplete, remove icons, normalize Vietnamese, filter English, and save locally
import io
import json
import os
import re
import boto3
import pandas as pd
from langdetect import detect, DetectorFactory

# Đảm bảo kết quả nhận diện ngôn ngữ ổn định
DetectorFactory.seed = 0

# 1. Cấu hình kết nối tới MinIO (chỉ để tải dữ liệu thô)
S3_ENDPOINT = "http://localhost:9000"
AWS_ACCESS_KEY_ID = "dat666"
AWS_SECRET_ACCESS_KEY = "dat@123456"
BUCKET_NAME = "gmaps-raw-data"

s3_client = boto3.client(
    's3',
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

def remove_emojis_and_icons(text):
    """Loại bỏ toàn bộ icon, emoji và ký tự đặc biệt tượng hình"""
    if not isinstance(text, str):
        return ""
    emoji_pattern = re.compile(
        r"["
        r"\U00010000-\U0010ffff"
        r"\u2000-\u3300"
        r"\uD83C[\uDC00-\uDFFF]"
        r"\uD83D[\uDC00-\uDFFF]"
        r"\uD83E[\uDD00-\uDDFF]"
        r"]+", flags=re.UNICODE
    )
    cleaned_text = emoji_pattern.sub(r'', text)
    return " ".join(cleaned_text.split())

def normalize_vietnamese_text(text):
    """Chuẩn hóa và sửa lại các từ viết tắt / tiếng lóng sang tiếng Việt phổ thông"""
    if not isinstance(text, str):
        return ""
    
    abbreviations = {
        r'\bko\b': 'không',
        r'\bk\b': 'không',
        r'\bkg\b': 'không',
        r'\bdc\b': 'được',
        r'\bđc\b': 'được',
        r'\bmk\b': 'mình',
        r'\bmn\b': 'mọi người',
        r'\bmng\b': 'mọi người',
        r'\brùi\b': 'rồi',
        r'\brq\b': 'rất',
        r'\brẩt\b': 'rất',
        r'\boke\b': 'ok',
        r'\bokey\b': 'ok',
        r'\btkiu\b': 'cảm ơn',
        r'\btks\b': 'cảm ơn',
    }
    
    for pattern, replacement in abbreviations.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        
    return text

def is_vietnamese_text(text):
    """Kiểm tra xem văn bản có phải là tiếng Việt hay không (lọc bỏ tiếng Anh và ngôn ngữ khác)"""
    if not isinstance(text, str) or len(text.strip()) < 3:
        return False
    try:
        lang = detect(text)
        return lang == 'vi'
    except Exception:
        return False

def load_all_json_from_s3():
    """Tự động quét và gom toàn bộ các file JSON thô từ MinIO bucket"""
    print("Đang quét các file JSON thô từ MinIO...")
    try:
        response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix='gmaps/raw/')
        if 'Contents' not in response:
            print("Không tìm thấy file nào trong thư mục gmaps/raw/ trên MinIO.")
            return pd.DataFrame()

        all_records = []
        for obj in response['Contents']:
            key = obj['Key']
            if key.endswith('.json'):
                print(f"Đang tải file: {key}")
                obj_resp = s3_client.get_object(Bucket=BUCKET_NAME, Key=key)
                content = obj_resp["Body"].read()
                data = json.loads(content.decode("utf-8"))
                if isinstance(data, list):
                    all_records.extend(data)
                elif isinstance(data, dict):
                    all_records.append(data)

        if not all_records:
            return pd.DataFrame()
        
        df = pd.DataFrame(all_records)
        print(f"Đã gộp tổng cộng {len(df)} dòng dữ liệu thô.")
        return df

    except Exception as e:
        print(f"Lỗi khi đọc dữ liệu từ MinIO: {e}")
        return pd.DataFrame()

def clean_reviews_data(df):
    """Lọc bỏ dữ liệu thiếu, xóa icon, lọc tiếng Anh và chuẩn hóa tiếng Việt"""
    if df.empty:
        return df

    print("Đang tiến hành làm sạch, lọc tiếng Anh và chuẩn hóa văn bản...")
    initial_rows = len(df)

    required_columns = ["restaurant_id", "user_name", "rating", "review_text"]
    for col in required_columns:
        if col not in df.columns:
            df[col] = None

    # 1. Xóa trùng lặp
    df = df.drop_duplicates(subset=["restaurant_id", "user_name", "review_text"])

    # 2. Loại bỏ triệt để các dòng thiếu thông tin
    df = df.dropna(subset=required_columns)
    for col in required_columns:
        df[col] = df[col].astype(str).str.strip()

    invalid_values = ["", "N/A", "Unknown", "nan", "None"]
    df = df[~df["user_name"].isin(invalid_values)]
    df = df[~df["review_text"].isin(invalid_values)]

    # 3. Chuẩn hóa rating từ 1 đến 5 sao
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce").astype("Int64")
    df = df[(df["rating"] >= 1) & (df["rating"] <= 5)]

    # 4. Xử lý văn bản: Xóa icon -> Chuẩn hóa từ viết tắt
    df["review_text"] = df["review_text"].apply(remove_emojis_and_icons)
    df["review_text"] = df["review_text"].apply(normalize_vietnamese_text)

    # 5. Lọc bỏ các bình luận không phải tiếng Việt (lọc bỏ tiếng Anh)
    print("Đang lọc bỏ các bình luận tiếng nước ngoài (tiếng Anh)...")
    df = df[df["review_text"].apply(is_vietnamese_text)]

    cleaned_rows = len(df)
    print(f"Đã hoàn tất! Loại bỏ {initial_rows - cleaned_rows} dòng lỗi, thiếu thông tin hoặc tiếng nước ngoài.")
    return df

def save_local_processed_data(df, output_filename="gmaps_cleaned_reviews.csv"):
    """Lưu file dữ liệu sạch trực tiếp vào ổ cứng trong thư mục data/processed"""
    if df.empty:
        print("Không có dữ liệu hợp lệ sau khi làm sạch.")
        return

    # Tạo thư mục data/processed nếu chưa tồn tại
    os.makedirs("data/processed", exist_ok=True)
    local_path = os.path.join("data/processed", output_filename)

    # Lưu file CSV với bảng mã utf-8-sig để đọc tiếng Việt chuẩn trên Excel
    df.to_csv(local_path, index=False, encoding="utf-8-sig")
    print(f"Đã lưu thành công file dữ liệu sạch tại ổ cứng: {local_path}")

if __name__ == "__main__":
    try:
        # 1. Tải dữ liệu thô từ MinIO
        raw_df = load_all_json_from_s3()
        if not raw_df.empty:
            # 2. Thực hiện làm sạch
            cleaned_df = clean_reviews_data(raw_df)
            
            # 3. Lưu kết quả vào thư mục data/processed trên ổ cứng
            save_local_processed_data(cleaned_df)
        else:
            print("Không tìm thấy dữ liệu thô.")
    except Exception as e:
        print(f"Lỗi thực thi: {e}")