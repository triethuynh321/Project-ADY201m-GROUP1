Vấn đề 1: Thắc mắc về hiện tượng mất container và dữ liệu trên S3/MinIO (từ 15/9 đến 20/9)

Cách đặt câu hỏi: Người dùng thắc mắc tại sao các container Docker đột nhiên biến mất sau khi chạy lệnh docker compose down và kiểm tra thấy Data Lake báo chưa có file nào (tại sao các container trước đó của tôi đột nhiên biến mất?, vẫn hiện chưa có file nào ? , nó không lưu trữ vĩnh viển sao ?).

Giải pháp/Tiến độ: Xác định rõ bản chất của Docker Desktop (tab containers chỉ hiển thị các tiến trình đang chạy) và cơ chế lưu trữ của image giả lập S3 hiện tại. Thống nhất quy trình đồng bộ file thô từ thư mục cục bộ (data/raw/) lên S3 thông qua script upload_to_s3.py mỗi khi khởi động lại môi trường làm việc, đảm bảo an toàn tuyệt đối cho dữ liệu gốc.

Vấn đề 2: Kiểm tra cấu trúc thư mục dự án và các file phụ trợ (từ 21/9 đến 26/9)

Cách đặt câu hỏi: Người dùng đối chiếu cây thư mục thực tế trên VS Code với tài liệu mẫu của đồ án và lo ngại về sự thiếu vắng các file quản lý phụ trợ (tôi đã làm đúng với cấu trúc dự án chưa ?, nhưng không hề có các file như check hay upload ?, vậy thì không cần phải xóa hay sữa lại thành quả hiện có đúng chứ ?).

Giải pháp/Tiến độ: Khẳng định cấu trúc thư mục của nhóm (data/raw/, data/processed/, src/ingestion/,...) hoàn toàn tuân thủ đúng chuẩn quy định của trường. Các file phụ trợ như check_s3.py hay upload_to_s3.py được đặt chuẩn trong thư mục src/ingestion/, không cần xóa hay sửa lại thành quả hiện có.

Vấn đề 3: Thiết kế kiến trúc lưu trữ SQL (Medallion Architecture) (từ 27/9 đến 30/9)

Cách đặt câu hỏi: Đặt vấn đề về việc xây dựng các bảng SQL lưu trữ và cách tổ chức code kết nối dữ liệu (đối với SQL sẽ chưa đồng thời code định hình hệ thống và dữ liệu hay phải tách tiêng ?, vậy thì cần viết 1 file python để load tất cả các dữ liệu từ datalake về đúng không ?).

Giải pháp/Tiến độ: Thống nhất phương án tách biệt rõ ràng giữa Định hình hệ thống (DDL/Tạo bảng) và Nạp dữ liệu (DML/Insert dữ liệu). Xác định chiến lược xây dựng 2 tầng lưu trữ vĩnh viễn trên cơ sở dữ liệu SQL: một bảng cho dữ liệu thô (Raw Layer) và một bảng cho dữ liệu đã làm sạch (Processed Layer) từ thư mục data/processed/.