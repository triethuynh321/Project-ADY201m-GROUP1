import os
import pandas as pd
from sqlalchemy import create_engine, URL, text

DATABASE_URL = URL.create(
    drivername="postgresql+psycopg2",
    username="dat666",
    password="dat@123456",
    host="localhost",
    port=5432,
    database="gmaps_reviews_db"
)

engine = create_engine(DATABASE_URL)


def load_reviews_to_db():
    print("Đang đọc và đồng bộ file dữ liệu Google Maps và Foody...")

    current_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(current_dir)
    
    gmaps_path = os.path.join(root_dir, 'data', 'processed', 'gmaps_cleaned_reviews_all_cities.csv')
    foody_path = os.path.join(root_dir, 'data', 'processed', 'foody_cleaned_reviews_all_cities_final.csv')
    
    dfs = []
    
    if os.path.isfile(gmaps_path):
        df_gmaps = pd.read_csv(gmaps_path)
        if 'platform' not in df_gmaps.columns:
            df_gmaps['platform'] = 'GoogleMaps'
        dfs.append(df_gmaps)
        
    if os.path.isfile(foody_path):
        df_foody = pd.read_csv(foody_path)
        if 'user_hash' in df_foody.columns and 'user_name' not in df_foody.columns:
            df_foody = df_foody.rename(columns={'user_hash': 'user_name'})
        if 'platform' not in df_foody.columns:
            df_foody['platform'] = 'Foody'
        dfs.append(df_foody)
        
    if not dfs:
        raise FileNotFoundError("Không tìm thấy bất kỳ file dữ liệu sạch nào!")
        
    df = pd.concat(dfs, ignore_index=True)

    required_columns = [
        "restaurant_id", "shop_name", "user_name",
        "review_text", "city", "rating"
    ]

    missing = set(required_columns) - set(df.columns)
    if missing:
        raise ValueError(f"Dữ liệu gộp thiếu các cột bắt buộc: {sorted(missing)}")

    df = df.rename(columns={
        "shop_name": "name",
        "user_name": "author_name",
        "review_text": "comment_cleaned"
    })

    df["rating"] = pd.to_numeric(df["rating"], errors="coerce")

    # Lọc rating hợp lệ
    df_valid = df[df["rating"].between(1, 5)].copy()
    num_dropped = len(df) - len(df_valid)
    if num_dropped > 0:
        print(f"Đã tự động loại bỏ {num_dropped} dòng dữ liệu có rating không hợp lệ.")
    
    df = df_valid

    df["restaurant_id"] = df["restaurant_id"].astype(str).str.strip()
    df["name"] = df["name"].astype(str).str.strip()
    df["city"] = df["city"].astype(str).str.strip().str.title()
    df["author_name"] = df["author_name"].astype(str).str.strip()
    df["comment_cleaned"] = df["comment_cleaned"].fillna("").astype(str)
    df["platform"] = df["platform"].astype(str).str.strip()
    df["comment_length"] = df["comment_cleaned"].str.len()

    print(f"Tổng số dòng dữ liệu gộp hợp lệ: {len(df)}")

    with engine.begin() as conn:
        # 1. Khởi tạo schema (tạo 4 bảng và các view)
        schema_path = os.path.join(current_dir, 'init_schema.sql')
        if os.path.isfile(schema_path):
            print("Đang khởi tạo cấu trúc cơ sở dữ liệu phân tán...")
            with open(schema_path, 'r', encoding='utf-8') as f:
                conn.execute(text(f.read()))

        # 2. Nạp bảng restaurants
        print("Đang nạp dữ liệu vào bảng: restaurants...")
        df_restaurants = df.groupby("restaurant_id").agg(
            name=("name", "first"),
            city=("city", "first"),
            total_reviews=("rating", "count"),
            avg_rating=("rating", "mean"),
            avg_comment_length=("comment_length", "mean")
        ).reset_index()

        df_restaurants["total_reviews"] = df_restaurants["total_reviews"].astype(int)
        df_restaurants["avg_rating"] = df_restaurants["avg_rating"].astype(float)
        df_restaurants["avg_comment_length"] = df_restaurants["avg_comment_length"].astype(float)
        df_restaurants.to_sql("restaurants", con=conn, if_exists="append", index=False, chunksize=10000, method="multi")

        # 3. Nạp bảng users (danh sách tác giả duy nhất)
        print("Đang nạp dữ liệu vào bảng: users...")
        df_users = pd.DataFrame({"author_name": df["author_name"].unique()})
        df_users.to_sql("users", con=conn, if_exists="append", index=False, chunksize=10000, method="multi")

        # 4. Nạp bảng platforms (danh sách nền tảng duy nhất)
        print("Đang nạp dữ liệu vào bảng: platforms...")
        df_platforms = pd.DataFrame({"platform_name": df["platform"].unique()})
        df_platforms.to_sql("platforms", con=conn, if_exists="append", index=False, chunksize=10000, method="multi")

        # 5. Lấy ID khóa ngoại từ DB để map vào bảng reviews
        print("Đang ánh xạ khóa ngoại và nạp dữ liệu vào bảng: reviews...")
        users_map = pd.read_sql("SELECT user_id, author_name FROM users", con=conn)
        platforms_map = pd.read_sql("SELECT platform_id, platform_name FROM platforms", con=conn)

        df = df.merge(users_map, on="author_name", how="left")
        df = df.merge(platforms_map, left_on="platform", right_on="platform_name", how="left")

        # Chọn các cột cần thiết cho bảng reviews
        df_reviews = df[[
            "restaurant_id", "user_id", "platform_id",
            "city", "rating", "comment_cleaned", "comment_length"
        ]].copy()

        df_reviews.to_sql("reviews", con=conn, if_exists="append", index=False, chunksize=10000, method="multi")

    print("Hoàn tất phân tách và nạp dữ liệu vào mô hình đa thực thể thành công!")


if __name__ == "__main__":
    load_reviews_to_db()