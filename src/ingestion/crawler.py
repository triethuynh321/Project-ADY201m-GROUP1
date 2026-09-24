import os
import json
import re
import pandas as pd
import requests
import csv

import os
import pandas as pd

def save_data(new_reviews, output_dir="data/raw"):
    os.makedirs(output_dir, exist_ok=True)
    csv_path = os.path.join(output_dir, "raw_reviews.csv")
    json_path = os.path.join(output_dir, "raw_reviews.json")
    
    # Chuyển dữ liệu mới cào thành DataFrame
    df_new = pd.DataFrame(new_reviews)
    
    if os.path.exists(csv_path):
        # 1. Đọc dữ liệu lịch sử đã lưu trước đó lên
        df_old = pd.read_csv(csv_path)
        
        # 2. Gộp dữ liệu cũ và dữ liệu mới lại với nhau
        df_combined = pd.concat([df_old, df_new], ignore_index=True)
        
        # 3. Loại bỏ các dòng bị trùng lặp hoàn toàn dựa trên các trường đặc trưng
        # (Giúp không bị lưu trùng nếu cào lại cùng một quán)
        initial_count = len(df_combined)
        df_combined.drop_duplicates(
            subset=["restaurant_id", "user_name", "review_text"], 
            keep="last", 
            inplace=True
        )
        final_count = len(df_combined)
        
        print(f"TỔNG CỘNG DỒN: {final_count} bình luận (Đã lọc {initial_count - final_count} bản trùng lặp).")
    else:
        df_combined = df_new
        print(f"Tạo file dữ liệu mới với {len(df_combined)} bình luận.")
        
    # Lưu lại xuống file CSV và JSON
    df_combined.to_csv(csv_path, index=False, encoding="utf-8-sig")
    df_combined.to_json(json_path, orient="records", force_ascii=False, indent=4)
    print(f"Hoàn thành lưu dữ liệu vào thư mục '{output_dir}'!")                 
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import time

def crawl_foody_reviews(urls, limit_per_url=1000):
    all_reviews = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        for url in urls:
            try:
                base_url = url.rstrip('/')
                review_url = base_url if '/binh-luan' in base_url else f"{base_url}/binh-luan"
                
                print(f"[Foody] Đang truy cập: {review_url}")
                page.goto(review_url, timeout=60000, wait_until="domcontentloaded")
                time.sleep(4) # Đợi trang render

                # Cuộn trang 3 lần để load danh sách
                for _ in range(10):
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(2)

                soup = BeautifulSoup(page.content(), 'html.parser')

                # Tìm các khối chứa bình luận chuẩn của Foody
                cards = soup.select('.micro-home-review-item, .review-item, div[class*="review-item"]')
                print(f"[Foody] Tìm thấy {len(cards)} khối bình luận hợp lệ.")

                for card in cards[:limit_per_url]:
                    # 1. Bóc tách Tên chuẩn xác (bỏ qua thẻ chứa avatar rỗng)
                    user_elem = (
                        card.select_one('.ru-user-name') or 
                        card.select_one('.ru-row a') or 
                        card.select_one('a[ng-bind*="User"], a[ng-bind*="name"]') or
                        card.select_one('.user-name, .owner-name')
                    )
                    
                    user_name = ""
                    if user_elem:
                        user_name = user_elem.get_text(strip=True)
                    
                    # Nếu chưa lấy được tên (do trúng thẻ avatar rỗng), duyệt tìm thẻ <a> đầu tiên có chữ
                    if not user_name:
                        for link in card.find_all('a'):
                            text = link.get_text(strip=True)
                            if text and len(text) > 1 and not text.startswith(('http', 'www')):
                                user_name = text
                                break
                    
                    if not user_name:
                        user_name = "Anonymous"

                    # 2. Điểm số
                    rating_elem = card.select_one('.review-points, .highlight, span[class*="point"]')
                    rating = rating_elem.get_text(strip=True) if rating_elem else "N/A"

                    # 3. Nội dung bình luận
                    comment_elem = card.select_one('.rd-des, .review-text, span[class*="comment"]')
                    comment = comment_elem.get_text(strip=True) if comment_elem else ""

                    if comment:
                        all_reviews.append({
                            "platform": "Foody",
                            "restaurant_id": url,
                            "user_name": user_name,
                            "rating": rating,
                            "review_text": comment
                        })

                print(f"[Foody] Đã trích xuất thành công {len(all_reviews)} bình luận!")

            except Exception as e:
                print(f"[Foody] Lỗi khi cào link {url}: {e}")

        browser.close()

    return all_reviews
if __name__ == "__main__":
    foody_urls = [
        "https://www.foody.vn/ho-chi-minh/hanh-dung-am-thuc-chay-man/binh-luan",
        "https://www.foody.vn/ho-chi-minh/nghien-store-banh-trang-an-vat-ly-thuong-kiet"
        
    ]
    
    print("Bắt đầu cào dữ liệu đánh giá từ hệ thống Foody/ShopeeFood...")
    
    
    all_reviews = crawl_foody_reviews(foody_urls,limit_per_url=1000)
    
    if all_reviews:
        save_data(all_reviews, output_dir="data/raw")
        print("Hoàn thành tiến trình cào và lưu dữ liệu thành công!")
    else:
        print("Không lấy được bình luận nào.")