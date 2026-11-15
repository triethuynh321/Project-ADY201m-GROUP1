# Clean raw JSON data from MinIO for both Google Maps and Foody, 
# drop incomplete, remove icons, normalize Vietnamese, filter English, and save locally.

import io
import json
import os
import re
import boto3
import pandas as pd
from langdetect import detect, DetectorFactory

# Đảm bảo kết quả nhận diện ngôn ngữ ổn định
DetectorFactory.seed = 0

# 1. Cấu hình kết nối tới MinIO
S3_ENDPOINT = "http://localhost:9000"
AWS_ACCESS_KEY_ID = "dat666"
AWS_SECRET_ACCESS_KEY = "dat@123456"

s3_client = boto3.client(
    's3',
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

def remove_emojis_and_icons(text):
    """Loại bỏ triệt để toàn bộ icon, emoji và ký tự đặc biệt tượng hình"""
    if not isinstance(text, str):
        return ""
    
    emoji_pattern = re.compile(
        r'[\U00010000-\U0010ffff]|[\u2600-\u27bf]|[\U0001f300-\U0001f5ff]|'
        r'[\U0001f600-\U0001f64f]|[\U0001f680-\U0001f6ff]|[\U0001f700-\U0001f77f]|'
        r'[\U0001f780-\U0001f7ff]|[\U0001f800-\U0001f8ff]|[\U0001f900-\U0001f9ff]|'
        r'[\U0001fa00-\U0001fa6f]|[\U0001fa70-\U0001faff]|[\u2700-\u27bf]', 
        flags=re.UNICODE
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


# ==========================================
# 2. XỬ LÝ DỮ LIỆU GOOGLE MAPS (CÓ GÁN NHÃN THÀNH PHỐ TỪ TÊN FILE)
# ==========================================
def load_and_classify_gmaps_from_s3():
    bucket_name = "gmaps-raw-data"
    print(f"\n--- Đang quét dữ liệu Google Maps từ bucket: {bucket_name} ---")
    try:
        response = s3_client.list_objects_v2(Bucket=bucket_name)
        if 'Contents' not in response:
            print(f"Bucket {bucket_name} trống.")
            return pd.DataFrame()

        all_records = []
        for obj in response['Contents']:
            key = obj['Key']
            if key.endswith('.json'):
                obj_resp = s3_client.get_object(Bucket=bucket_name, Key=key)
                content = obj_resp["Body"].read()
                data = json.loads(content.decode("utf-8"))
                
                # Xác định thành phố dựa theo tiền tố tên file part
                filename_upper = key.upper()
                if 'SG_PART' in filename_upper:
                    city_name = 'Ho Chi Minh'
                elif 'HP_PART' in filename_upper:
                    city_name = 'Hai Phong'
                elif 'HN_PART' in filename_upper:
                    city_name = 'Hanoi'
                elif 'BN_PART' in filename_upper:
                    city_name = 'Bac Ninh'
                elif 'QN_PART' in filename_upper:
                    city_name = 'Quang Ninh'
                elif 'DN_PART' in filename_upper:
                    city_name = 'Dong Nai'
                elif 'CT_PART' in filename_upper:
                    city_name = 'Can Tho'
                elif 'DN2_PART' in filename_upper:
                    city_name = 'Da Nang'
                elif 'HUE_PART' in filename_upper:
                    city_name = 'Hue'
                else:
                    city_name = 'Unknown'

                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            item['city'] = city_name
                            all_records.append(item)
                elif isinstance(data, dict):
                    data['city'] = city_name
                    all_records.append(data)

        if not all_records:
            return pd.DataFrame()
        
        df = pd.DataFrame(all_records)
        print(f"Đã tải thành công {len(df)} dòng dữ liệu thô Google Maps.")
        return df

    except Exception as e:
        print(f"Lỗi khi đọc bucket {bucket_name}: {e}")
        return pd.DataFrame()


# ==========================================
# 3. XỬ LÝ DỮ LIỆU FOODY (GIỮ NGUYÊN CƠ CHẾ CÓ SẴN TRƯỜNG THÀNH PHỐ)
# ==========================================
def load_and_classify_foody_from_s3():
    bucket_name = "foody-raw-data"
    print(f"\n--- Đang quét dữ liệu Foody từ bucket: {bucket_name} ---")
    try:
        response = s3_client.list_objects_v2(Bucket=bucket_name)
        if 'Contents' not in response:
            print(f"Bucket {bucket_name} trống hoặc chưa được tạo.")
            return pd.DataFrame()

        all_records = []
        for obj in response['Contents']:
            key = obj['Key']
            if key.endswith('.json'):
                obj_resp = s3_client.get_object(Bucket=bucket_name, Key=key)
                content = obj_resp["Body"].read()
                data = json.loads(content.decode("utf-8"))
                
                # Foody dữ liệu đã có sẵn yếu tố thành phố bên trong cấu trúc, giữ nguyên không gán đè
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            all_records.append(item)
                elif isinstance(data, dict):
                    all_records.append(data)

        if not all_records:
            return pd.DataFrame()
        
        df = pd.DataFrame(all_records)
        print(f"Đã tải thành công {len(df)} dòng dữ liệu thô Foody.")
        return df

    except Exception as e:
        print(f"Lỗi khi đọc bucket {bucket_name}: {e}")
        return pd.DataFrame()


# ==========================================
# 4. HÀM CHUNG LÀM SẠCH DỮ LIỆU
# ==========================================
def clean_reviews_data(df, platform_name="gmaps"):
    if df.empty:
        return df

    print(f"Đang tiến hành làm sạch dữ liệu cho nền tảng: {platform_name}...")
    initial_rows = len(df)

    required_columns = ["restaurant_id", "user_name", "rating", "review_text", "city"]
    for col in required_columns:
        if col not in df.columns:
            df[col] = None

    # 1. Xóa trùng lặp
    df = df.drop_duplicates(subset=["restaurant_id", "user_name", "review_text"])

    # 2. Loại bỏ dòng thiếu thông tin
    df = df.dropna(subset=required_columns)
    for col in required_columns:
        df[col] = df[col].astype(str).str.strip()

    invalid_values = ["", "N/A", "Unknown", "nan", "None"]
    df = df[~df["user_name"].isin(invalid_values)]
    df = df[~df["review_text"].isin(invalid_values)]
    df = df[~df["city"].isin(invalid_values)]

    # 3. Chuẩn hóa rating từ 1 đến 5 sao
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce").astype("Int64")
    df = df[(df["rating"] >= 1) & (df["rating"] <= 5)]

    # 4. Xử lý văn bản: Xóa icon -> Chuẩn hóa từ viết tắt
    df["review_text"] = df["review_text"].apply(remove_emojis_and_icons)
    df["review_text"] = df["review_text"].apply(normalize_vietnamese_text)

    # 5. Lọc bỏ bình luận tiếng nước ngoài (tiếng Anh)
    print("Đang lọc bỏ các bình luận tiếng nước ngoài...")
    df = df[df["review_text"].apply(is_vietnamese_text)]

    cleaned_rows = len(df)
    print(f"Hoàn tất làm sạch {platform_name}! Loại bỏ {initial_rows - cleaned_rows} dòng lỗi/thiếu/không phải tiếng Việt.")
    return df

def save_local_processed_data(df, output_filename):
    if df.empty:
        print(f"Không có dữ liệu hợp lệ để lưu cho file: {output_filename}")
        return

    os.makedirs("data/processed", exist_ok=True)
    local_path = os.path.join("data/processed", output_filename)

    df.to_csv(local_path, index=False, encoding="utf-8-sig")
    print(f"Đã lưu file dữ liệu sạch thành công tại: {local_path}")

if __name__ == "__main__":
    try:
        print("=== BẮT ĐẦU QUÁ TRÌNH LÀM SẠCH DỮ LIỆU TỪ MINIO ===")
        
        # --- Xử lý Google Maps ---
        raw_gmaps_df = load_and_classify_gmaps_from_s3()
        if not raw_gmaps_df.empty:
            cleaned_gmaps_df = clean_reviews_data(raw_gmaps_df, platform_name="gmaps")
            save_local_processed_data(cleaned_gmaps_df, "gmaps_cleaned_reviews_all_cities.csv")
            
        # --- Xử lý Foody ---
        raw_foody_df = load_and_classify_foody_from_s3()
        if not raw_foody_df.empty:
            cleaned_foody_df = clean_reviews_data(raw_foody_df, platform_name="foody")
            save_local_processed_data(cleaned_foody_df, "foody_cleaned_reviews_all_cities.csv")
            
        print("=== HOÀN TẤT TOÀN BỘ QUÁ TRÌNH LÀM SẠCH ===")
        
    except Exception as e:
        print(f"Lỗi thực thi script cleaner: {e}")