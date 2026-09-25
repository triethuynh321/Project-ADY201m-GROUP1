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
    
    
    df_new = pd.DataFrame(new_reviews)
    
    if os.path.exists(csv_path):
      
        df_old = pd.read_csv(csv_path)
        
        
        df_combined = pd.concat([df_old, df_new], ignore_index=True)
        
       
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
                time.sleep(4) 

                for _ in range(10):
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(2)

                soup = BeautifulSoup(page.content(), 'html.parser')

                cards = soup.select('.micro-home-review-item, .review-item, div[class*="review-item"]')
                print(f"[Foody] Tìm thấy {len(cards)} khối bình luận hợp lệ.")

                for card in cards[:limit_per_url]:
                    user_elem = (
                        card.select_one('.ru-user-name') or 
                        card.select_one('.ru-row a') or 
                        card.select_one('a[ng-bind*="User"], a[ng-bind*="name"]') or
                        card.select_one('.user-name, .owner-name')
                    )
                    
                    user_name = ""
                    if user_elem:
                        user_name = user_elem.get_text(strip=True)
                    
                    if not user_name:
                        for link in card.find_all('a'):
                            text = link.get_text(strip=True)
                            if text and len(text) > 1 and not text.startswith(('http', 'www')):
                                user_name = text
                                break
                    
                    if not user_name:
                        user_name = "Anonymous"

                    rating_elem = card.select_one('.review-points, .highlight, span[class*="point"]')
                    rating = rating_elem.get_text(strip=True) if rating_elem else "N/A"

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
def get_foody_links_from_category(category_url, max_links=5):
    """
    Hàm quét trang danh mục trên Foody bằng cách trích xuất trực tiếp thẻ quán.
    """
    print(f"[Category] Đang quét danh sách quán từ: {category_url}")
    restaurant_urls = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        try:
            page.goto(category_url, timeout=60000)
            time.sleep(5)
            
            # Cuộn trang vài lần để tải thêm danh sách quán
            for _ in range(15):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(3)
                
            # Lấy tất cả các thẻ có thuộc tính href và chứa cấu trúc đường dẫn danh mục ẩm thực
            links = page.eval_on_selector_all(
                "a[href]", 
                "elements => elements.map(e => e.href)"
            )
            
            for href in links:
                if not href or "&" in href or "(" in href or ")" in href:
                    continue
                    
                # Đã thêm điều kiện loại bỏ album ở đây
                if any(city in href for city in ["/ho-chi-minh/", "/ha-noi/", "/da-nang/"]) \
                   and "/bai-viet/" not in href \
                   and "/album" not in href \
                   and "/o-dau/" not in href \
                   and "/fresh" not in href \
                   and "/tim-kiem" not in href \
                   and "/khuyen-mai" not in href:
                    
                    if not href.endswith('/binh-luan'):
                        full_link = href.rstrip('/') + '/binh-luan'
                    else:
                        full_link = href
                        
                    if full_link not in restaurant_urls:
                        restaurant_urls.append(full_link)
                        
                if len(restaurant_urls) >= max_links:
                    break
                    
        except Exception as e:
            print(f"[Category] Lỗi khi quét danh mục: {e}")
            
        browser.close()
        
    print(f"[Category] Đã quét thành công {len(restaurant_urls)} đường dẫn quán từ danh mục!")
    return restaurant_urls

if __name__ == "__main__":
    target_category_url = "https://www.foody.vn/ho-chi-minh/an-vat"
    foody_urls = get_foody_links_from_category(target_category_url, max_links=1000)
    
    if foody_urls:
        print("Bắt đầu tiến trình cào dữ liệu đánh giá hàng loạt...")
        all_reviews = crawl_foody_reviews(foody_urls, limit_per_url=1000)
        
        if all_reviews:
            save_data(all_reviews, output_dir="data/raw")
            print("Hoàn thành toàn bộ tiến trình quét danh mục và lưu dữ liệu thành công!")
        else:
            print("Không lấy được bình luận nào từ danh sách các quán trên.")
    else:
            print("Không tìm thấy đường dẫn quán nào từ trang danh mục.")