import os
import boto3
from botocore.exceptions import NoCredentialsError

# Cấu hình kết nối MinIO (dùng chung thông tin với crawler)
MINIO_ENDPOINT = 'http://localhost:9000'
ACCESS_KEY = 'dat666'
SECRET_KEY = 'dat@123456'

# Khởi tạo S3 client tương thích với MinIO
s3_client = boto3.client(
    's3',
    endpoint_url=MINIO_ENDPOINT,
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY
)

# Định nghĩa ánh xạ từ Bucket trên MinIO sang thư mục lưu trữ dưới máy local
BUCKET_MAPPING = {
    'gmaps-raw-data': 'data/raw/ggmaps',
    'foody-raw-data': 'data/raw/foody'
}

def download_data_from_minio():
    for bucket_name, local_dir in BUCKET_MAPPING.items():
        print(f"\n--- Đang quét và tải từ bucket: {bucket_name} ---")
        
        # Tạo thư mục local tương ứng nếu chưa tồn tại
        os.makedirs(local_dir, exist_ok=True)
        
        try:
            # Kiểm tra xem bucket có tồn tại không
            s3_client.head_bucket(Bucket=bucket_name)
        except Exception as e:
            print(f"[-] Bucket '{bucket_name}' không tồn tại hoặc không thể truy cập: {e}")
            continue
        
        try:
            # Liệt kê toàn bộ các đối tượng (file) trong bucket
            response = s3_client.list_objects_v2(Bucket=bucket_name)
            
            if 'Contents' not in response:
                print(f"[-] Bucket '{bucket_name}' hiện đang trống.")
                continue
            
            download_count = 0
            for obj in response['Contents']:
                file_key = obj['Key']
                
                # Bỏ qua nếu đây là thư mục (key kết thúc bằng dấu /)
                if file_key.endswith('/'):
                    continue
                
                # Chỉ tải về các file có định dạng .json hoặc bạn có thể bỏ qua điều kiện này nếu muốn tải tất cả
                if not file_key.endswith('.json'):
                    continue
                
                # Giữ nguyên cấu trúc thư mục (bao gồm cả thư mục run_...) từ MinIO về máy local
                local_file_path = os.path.join(local_dir, file_key)
                
                # Tự động tạo các thư mục cha tương ứng trên local nếu chưa có
                os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
                
                print(f"  Đang tải: {file_key} -> {local_file_path}")
                s3_client.download_file(bucket_name, file_key, local_file_path)
                download_count += 1
                
            print(f"[+] Đã tải thành công {download_count} file từ bucket '{bucket_name}' vào thư mục '{local_dir}'")
            
        except Exception as e:
            print(f"[!] Lỗi khi xử lý bucket {bucket_name}: {e}")

if __name__ == "__main__":
    print("=== BẮT ĐẦU QUÁ TRÌNH ĐỒNG BỘ DỮ LIỆU TỪ MINIO ===")
    download_data_from_minio()
    print("=== HOÀN TẤT ĐỒNG BỘ ===")