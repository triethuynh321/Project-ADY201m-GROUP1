import os
import boto3
from botocore.client import Config

# Cấu hình bắt buộc để boto3 không bị lỗi kết nối với S3Mock
s3_config = Config(
    s3={'addressing_style': 'path'},
    signature_version='s3v4'
)

s3 = boto3.client(
    's3',
    endpoint_url='http://127.0.0.1:18000', # Đổi từ localhost sang 127.0.0.1
    aws_access_key_id='test',
    aws_secret_access_key='test',
    region_name='us-east-1',
    config=s3_config
)

bucket_name = 'shopeefood-raw-data'

# Đảm bảo bucket tồn tại trước khi upload
def upload_legacy_files():
    # Sử dụng đường dẫn tương đối chuẩn từ thư mục gốc dự án
    files_to_upload = [
        "data/raw/raw_reviews.csv",
        "data/raw/raw_reviews.json",
        "data/raw/gmaps_reviews.csv",
        "data/raw/gmaps_reviews.json"
    ]

    print("Bắt đầu đẩy dữ liệu cũ lên Data Lake S3...")
    for file_path in files_to_upload:
        if os.path.exists(file_path):
            s3_key = f"shopeefood/{file_path.replace('data/', '')}"
            try:
                s3.upload_file(file_path, bucket_name, s3_key)
                print(f"Đã upload thành công: {file_path} -> s3://{bucket_name}/{s3_key}")
            except Exception as e:
                print(f"Lỗi khi upload {file_path}: {e}")
        else:
            print(f"Không tìm thấy file trên máy: {file_path}")
    print("Hoàn tất đồng bộ dữ liệu cũ!")

if __name__ == "__main__":
    upload_legacy_files()