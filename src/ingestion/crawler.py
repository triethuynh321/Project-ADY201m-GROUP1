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
import random
def crawl_foody_reviews(urls, limit_per_url=1000):
    all_reviews = []
    
    with sync_playwright() as p:
        # Thay thế đoạn khởi tạo browser cũ bằng đoạn có thêm các args chống phát hiện bot
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ]
        )
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
                time.sleep(random.uniform(5, 10)) 

                for _ in range(5):
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(2)

                soup = BeautifulSoup(page.content(), 'html.parser')

                cards = soup.select('.foody-box-review, .review-item')
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
                    comment = comment_elem.get_text(strip=True).replace("Xem thêm", "").strip() if comment_elem else ""

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
def get_foody_links_from_category(category_url, max_links=10000):
    """
    Hàm quét trang danh mục trên Foody bằng cách trích xuất trực tiếp thẻ quán.
    """
    print(f"[Category] Đang quét danh sách quán từ: {category_url}")
    restaurant_urls = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        try:
            page.goto(category_url, timeout=60000)
            time.sleep(random.uniform(8, 15))
            
            # Cuộn trang vài lần để tải thêm danh sách quán
            for _ in range(15):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                
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
                    and "/khuyen-mai" not in href \
                    and "/thuc-don" not in href \
                    and "/bai-dau-xe" not in href \
                    and "/dia-diem-phuc-vu" not in href:
                    
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
import time
import random
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

def get_gmaps_links_from_search(search_url, max_restaurants=20):
    """
    Hàm quét danh sách quán từ trang kết quả tìm kiếm/danh mục của Google Maps
    """
    restaurant_urls = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        print(f"[Google Maps Category] Đang tìm kiếm: {search_url}")
        page.goto(search_url, timeout=60000)
        time.sleep(random.uniform(3, 5))
        
        # Google Maps chứa danh sách kết quả trong một khung scroll bên trái
        # Selector khung chứa danh sách kết quả tìm kiếm
        sidebar_selector = 'div[role="feed"]'
        
        try:
            page.wait_for_selector(sidebar_selector, timeout=10000)
            
            # Tiến hành cuộn khung sidebar để tải thêm các quán trong danh mục
            last_height = 0
            for i in range(100): # Số lần cuộn để load thêm quán (có thể tăng giảm)
                page.evaluate(f"""
                    let feed = document.querySelector('{sidebar_selector}');
                    if (feed) {{
                        feed.scrollTop = feed.scrollHeight;
                    }}
                """)
                time.sleep(random.uniform(2, 4))
                
            # Lấy toàn bộ các thẻ chứa đường dẫn quán ăn
            links = page.locator('a.hfpxzc').all()
            for link in links:
                href = link.get_attribute('href')
                if href and href not in restaurant_urls:
                    restaurant_urls.append(href)
                    if len(restaurant_urls) >= max_restaurants:
                        break
                        
            print(f"[Google Maps Category] Đã quét thành công {len(restaurant_urls)} đường dẫn quán từ danh mục!")
            
        except Exception as e:
            print(f"[Google Maps Category] Lỗi khi quét danh mục: {e}")
            
        browser.close()
    return restaurant_urls

def crawl_gmaps_reviews(place_url, max_reviews=50):
    reviews_list = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
        context = browser.new_context(locale="vi-VN")
        page = context.new_page()
        try:
            print(f"[Google Maps Review] Đang truy cập quán: {place_url}")
            page.goto(place_url, timeout=60000)
            time.sleep(random.uniform(3, 5))
            
            # Tìm và click tab Đánh giá
            try:
                reviews_tab = page.locator('button[role="tab"]:has-text("Đánh giá"), button[role="tab"]:has-text("Reviews")').first
                if reviews_tab.count() > 0:
                    reviews_tab.click()
                    print("[Google Maps] Đã click chuyển sang tab Đánh giá thành công!")
                    time.sleep(random.uniform(3, 4))
            except Exception:
                pass

            # Cuộn trang để tải thêm dữ liệu review
            print("[Google Maps] Bắt đầu cuộn để tải thêm review...")
            for _ in range(15):
                try:
            # Dùng evaluate để cuộn trực tiếp vào khung chứa review của Google Maps
                    page.evaluate('''() => {
                let scrollableDiv = document.querySelector('.m6QErb.DxyBCb');
                if (scrollableDiv) {
                    scrollableDiv.scrollTop = scrollableDiv.scrollHeight;
                }
            }''')
                except Exception:
                    pass
            time.sleep(random.uniform(2, 3))

            # Parse nội dung HTML sau khi cuộn
            content = page.content()
            soup = BeautifulSoup(content, 'html.parser')

            review_elements = soup.select('div.jftiEf')
            print(f"[Google Maps Review] Tìm thấy {len(review_elements)} đánh giá.")

            for elem in review_elements:
                try:
                    text_elem = elem.select_one('span.wiI7pd')
                    text = text_elem.get_text(strip=True) if text_elem else ""

                    rating_elem = elem.select_one('span.kvMYJ')
                    rating_str = rating_elem.get_attribute('aria-label') if rating_elem else "5"

                    if text:
                        reviews_list.append({
                            "source": "google maps",
                            "rating": rating_str,
                            "review_text": text
                        })
                except Exception:
                    continue

        except Exception as e:
            print(f"[Google Maps Review] Lỗi khi cào review: {e}")
        finally:
            browser.close()

    # Lưu dữ liệu vào file CSV kho
    if reviews_list:
        df_new = pd.DataFrame(reviews_list)
        df_new.to_csv("data/raw/raw_reviews.csv", mode="a", index=False, header=not os.path.exists("data/raw/raw_reviews.csv"))
        print(f"[Google Maps] Đã lưu cộng dồn {len(reviews_list)} review vào kho thành công!")

    return reviews_list
if __name__ == "__main__":
    print("=== BẮT ĐẦU TIẾN TRÌNH CÀO DỮ LIỆU ĐA NỀN TẢNG ===")
    
    all_reviews = []
    foody_targets = []
    
    foody_urls =[]
    for target in foody_targets:
        if "/bo-suu-tap/" in target or target.endswith("/ha-noi") or "quan-an" in target or "an-vat" in target:
            print(f"[Foody Category] Đang quét danh mục: {target}")
            links = get_foody_links_from_category(target, max_links=1000)
            if links:
                foody_urls.extend(links)
        else:
            foody_urls.append(target)

    foody_urls = list(set(foody_urls))

    if foody_urls:
        print(f"[Foody] Tổng số quán Foody chuẩn bị cào: {len(foody_urls)}")
        foody_reviews = crawl_foody_reviews(foody_urls, limit_per_url=1000)
        if foody_reviews:
            all_reviews.extend(foody_reviews)

    gmaps_search_url = "https://www.google.com/maps/search/quan+an+quan+1+ho+chi+minh"
    print(f"[Google Maps Category] Đang quét danh mục tìm kiếm...")
    gmaps_links = get_gmaps_links_from_search(gmaps_search_url, max_restaurants=1000)

    if gmaps_links:
        print(f"[Google Maps] Tổng số quán lấy được từ Maps: {len(gmaps_links)}")
        for g_url in gmaps_links:
            print(f"[Google Maps Review] Đang cào quán: {g_url}")
            gmaps_reviews = crawl_gmaps_reviews(g_url, max_reviews=1000)
            if gmaps_reviews:
                all_reviews.extend(gmaps_reviews)
            time.sleep(random.uniform(3, 5))

        save_data(all_reviews, output_dir="data/raw")
        print(f"=== HOÀN TẤT! Tổng số lượng review thu về từ mọi nguồn: {len(all_reviews)} ===")
    else:
        print("Không tìm thấy dữ liệu nào được cào về từ các nguồn.")