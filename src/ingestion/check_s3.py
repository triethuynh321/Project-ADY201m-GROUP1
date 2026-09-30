import boto3
from botocore.config import Config

# Cấu hình chuẩn để ép boto3 sử dụng path-style
s3_config = Config(
    s3={'addressing_style': 'path'},
    signature_version='s3v4'
)

# Kết nối tới kho Data Lake S3 local trên Docker
s3 = boto3.client(
    's3',
    endpoint_url='http://127.0.0.1:18000',
    aws_access_key_id='test',
    aws_secret_access_key='test',
    config=s3_config
)

bucket_name = 'shopeefood-raw-data'

try:
    # 1. Kiểm tra và tự động tạo bucket nếu chưa tồn tại
    existing_buckets = [b['Name'] for b in s3.list_buckets().get('Buckets', [])]
    if bucket_name not in existing_buckets:
        s3.create_bucket(Bucket=bucket_name)
        print(f"Da tao moi bucket: {bucket_name}")

    # 2. Truy vấn danh sách file trong bucket
    response = s3.list_objects_v2(Bucket=bucket_name)

    if 'Contents' in response:
        print("\nDATA LAKE ĐANG CHỨA CÁC FILE DƯỚI ĐÂY:")
        print("-" * 50)
        for obj in response['Contents']:
            print(f"Tên file: {obj['Key']} | Dung lượng: {obj['Size']} bytes")
        print("-" * 50)
    else:
        print(f"\nKho Data Lake '{bucket_name}' hiện chưa có file nào (bucket đã sẵn sàng)!")

except Exception as e:
    print(f"\nLỗi kết nối S3: {e}")