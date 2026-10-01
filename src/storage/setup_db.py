import sqlite3
import os

def init_database():
    # Đảm bảo thư mục db/ tồn tại (tận dụng thư mục db/ theo chuẩn đề bài)
    os.makedirs("db", exist_ok=True)
    db_path = "db/shopeefood_project.db"
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Bảng lưu dữ liệu thô (Raw Layer)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS raw_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            raw_text TEXT,
            rating REAL,
            author TEXT,
            created_at TEXT
        )
    """)
    
    # 2. Bảng lưu dữ liệu sạch (Processed Layer)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cleaned_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            clean_text TEXT,
            rating REAL,
            sentiment_score REAL,
            platform TEXT
        )
    """)
    
    conn.commit()
    conn.close()
    print("Đã khởi tạo thành công cấu trúc database tại: db/shopeefood_project.db")

if __name__ == "__main__":
    init_database()