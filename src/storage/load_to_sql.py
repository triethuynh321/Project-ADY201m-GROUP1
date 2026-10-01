import sqlite3
import pandas as pd
import os

def load_data_to_sql():
    db_path = "db/shopeefood_project.db"
    
    if not os.path.exists(db_path):
        print("Chưa tìm thấy database! Vui lòng chạy setup_db.py trước.")
        return
        
    conn = sqlite3.connect(db_path)
    
    # 1. Nạp dữ liệu thô vào bảng raw_reviews
    raw_file = "data/processed/cleaned_reviews.csv"
    if os.path.exists(raw_file):
        df_raw = pd.read_csv(raw_file)
        df_raw.to_sql("cleaned_reviews", conn, if_exists="replace", index=False)
        print(f"Đã nạp {len(df_raw)} dòng dữ liệu thô vào bảng raw_reviews.")
    else:
        print(f"Không tìm thấy file raw tại {raw_file}.")
        
    # 2. Nạp dữ liệu sạch vào bảng cleaned_reviews
    cleaned_file = "data/processed/cleaned_reviews.csv"
    if os.path.exists(cleaned_file):
        df_clean = pd.read_csv(cleaned_file)
        df_clean.to_sql("cleaned_reviews", conn, if_exists="append", index=False)
        print(f"Đã nạp {len(df_clean)} dòng dữ liệu sạch vào bảng cleaned_reviews.")
    else:
        print(f"Không tìm thấy file processed tại {cleaned_file}.")
        
    conn.close()

if __name__ == "__main__":
    load_data_to_sql()