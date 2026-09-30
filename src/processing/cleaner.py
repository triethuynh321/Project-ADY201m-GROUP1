# Clean raw data from MinIO and load into PostgreSQL (Report 2-3)
import io
import boto3
import pandas as pd

from botocore.client import Config

# 1. Cấu hình kết nối tới S3Mock (Đã đồng bộ port 18000)
S3_ENDPOINT = "http://127.0.0.1:18000"
AWS_ACCESS_KEY_ID = "test"
AWS_SECRET_ACCESS_KEY = "test"
BUCKET_NAME = "shopeefood-raw-data"

# Cấu hình chuẩn boto3 cho S3Mock
s3_config = Config(
    s3={'addressing_style': 'path'},
    signature_version='s3v4'
)

# Khởi tạo client kết nối S3
s3_client = boto3.client(
    's3',
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name="us-east-1",
    config=s3_config
)


def load_data_from_s3(file_key):
  """Đọc file CSV thô trực tiếp từ Data Lake (S3)"""
  print(f"Đang tải file {file_key} từ Data Lake...")
  response = s3_client.get_object(Bucket=BUCKET_NAME, Key=file_key)
  content = response["Body"].read()
  # Đọc nội dung vào DataFrame của pandas
  df = pd.read_csv(io.BytesIO(content))
  return df


def clean_reviews_data(df):
  """Thực hiện các bước làm sạch dữ liệu review"""
  print("Đang tiến hành làm sạch dữ liệu...")

  initial_rows = len(df)

  # Bước 1: Xóa các dòng bị trùng lặp hoàn toàn
  df = df.drop_duplicates()

  # Bước 2: Xóa các dòng bị thiếu nội dung review hoặc điểm số (nếu có cột tương ứng)
  # Lưu ý: Điều chỉnh tên cột ('review', 'rating') cho khớp với file CSV thực tế của bạn
  if "review" in df.columns:
    df = df.dropna(subset=["review"])
    # Xóa khoảng trắng thừa trong nội dung review
    df["review"] = df["review"].astype(str).str.strip()

  # Bước 3: Chuẩn hóa định dạng (ví dụ: viết thường, loại bỏ ký tự đặc biệt nếu cần)
  # df['review'] = df['review'].str.lower()

  cleaned_rows = len(df)
  print(
      f"Đã làm sạch xong! Loại bỏ {initial_rows - cleaned_rows} dòng trùng"
      " lặp/lỗi."
  )
  return df


def save_cleaned_data(df, output_filename="cleaned_reviews.csv"):
  """Lưu dữ liệu sạch cục bộ hoặc đẩy ngược lên S3 (Processed Zone)"""
  output_path = f"data/processed/{output_filename}"

  # Lưu file cục bộ vào thư mục processed
  df.to_csv(output_path, index=False, encoding="utf-8-sig")
  print(f"Đã lưu file dữ liệu sạch tại: {output_path}")

  # (Tuỳ chọn) Bạn có thể upload ngược file sạch này lên một bucket/folder sạch trên S3 nếu muốn


if __name__ == "__main__":
  # Tên file thô bạn đã upload lên S3 trước đó
  # Ví dụ: 'shopeefood/raw/gmaps_reviews.csv' hoặc đường dẫn tương ứng trong bucket
  target_file_key = "shopeefood/raw/gmaps_reviews.csv"

  try:
    # 1. Đọc dữ liệu từ Data Lake
    raw_df = load_data_from_s3(target_file_key)
    print(f"Đã tải thành công {len(raw_df)} dòng dữ liệu thô.")

    # 2. Làm sạch
    cleaned_df = clean_reviews_data(raw_df)

    # 3. Lưu kết quả
    save_cleaned_data(cleaned_df)

  except Exception as e:
    print(
        f"Lỗi khi xử lý dữ liệu từ Data Lake: {e}\nHãy đảm bảo Docker và S3"
        " đang chạy!"
    )