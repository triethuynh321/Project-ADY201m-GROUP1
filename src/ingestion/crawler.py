import os
import json
import re
import pandas as pd
from youtube_comment_downloader import YoutubeCommentDownloader
from playwright.sync_api import sync_playwright


def extract_video_id(url):
    """Tự động tách Video ID từ bất kỳ đường link YouTube nào."""
    regex = r"(?:v=|\/)([0-9A-Za-z_-]{11})"
    match = re.search(regex, url)
    if match:
        return match.group(1)
    return None
def crawl_tiktok_by_url(url_list, max_comments_per_video=1000):
    all_reviews = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        for url in url_list:
            print(f"Đang cào TikTok URL:{url}...")
            try:
                page.goto(url,timeout=60000)
                time.sleep(3)
                for _ in range(10):
                    page.mouse.wheel(0,1000)
                    time.sleep(1.5)
                    # Bóc tách các thẻ comment TikTok
                comments_elements = page.query_selector_all("[data-e2e='comment-level-1']")
                count = 0

                for elem in comments_elements:
                    if count >= max_comments_per_video:
                        break
                    
                    user_elem = elem.query_selector("[data-e2e='comment-user-username']")
                    text_elem = elem.query_selector("[data-e2e='comment-level-1-text']")
                    
                    user_name = user_elem.inner_text().strip() if user_elem else "Ẩn danh"
                    comment_text = text_elem.inner_text().strip() if text_elem else ""

                    if comment_text:
                        all_reviews.append({
                            "platform": "tiktok",
                            "user_name": user_name,
                            "comment_text": comment_text,
                            "rating": None,
                            "likes": 0,
                            "time": "",
                            "source_url": url
                        })
                        count += 1

                print(f"  └─ Lấy thành công {count} bình luận từ TikTok.")
            except Exception as e:
                print(f"Lỗi khi cào TikTok {url}: {e}")

        browser.close()

    return all_reviews
def crawl_google_maps_by_url(url_list, max_comments=1000):
    """Cào đánh giá quán ăn trên Google Maps."""
    all_reviews = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for url in url_list:
            print(f"Đang cào Google Maps URL: {url}...")
            try:
                page.goto(url, timeout=60000)
                time.sleep(4)

                # Cuộn khung danh sách đánh giá
                scrollable_div = page.query_selector("div.m6QE1c.PKSp3")
                if scrollable_div:
                    for _ in range(10):
                        scrollable_div.evaluate("el => el.scrollTop = el.scrollHeight")
                        time.sleep(1.5)

                review_cards = page.query_selector_all("div.jftiS")
                count = 0

                for card in review_cards:
                    if count >= max_comments:
                        break

                    author_elem = card.query_selector("div.d4r55")
                    text_elem = card.query_selector("span.wi84cd") or card.query_selector("span.My5S1d")
                    rating_elem = card.query_selector("span.kvm24c")

                    user_name = author_elem.inner_text().strip() if author_elem else "Ẩn danh"
                    comment_text = text_elem.inner_text().strip() if text_elem else ""
                    rating = rating_elem.get_attribute("aria-label") if rating_elem else ""

                    if comment_text:
                        all_reviews.append({
                            "platform": "google_maps",
                            "user_name": user_name,
                            "comment_text": comment_text,
                            "rating": rating,
                            "likes": 0,
                            "time": "",
                            "source_url": url
                        })
                        count += 1

                print(f"  └─ Lấy thành công {count} đánh giá từ Google Maps.")
            except Exception as e:
                print(f"Lỗi khi cào Google Maps {url}: {e}")

        browser.close()

    return all_reviews

# ---------------------------------------------------------
# 5. HÀM ĐIỀU HƯỚNG TỔNG (ROUTER)
# ---------------------------------------------------------
def crawl_by_url(url_list, max_comments=1000):
    """Tự động nhận diện nền tảng dựa trên URL để gọi hàm cào phù hợp."""
    youtube_urls = []
    tiktok_urls = []
    gmaps_urls = []

    for url in url_list:
        if "youtube.com" in url or "youtu.be" in url:
            youtube_urls.append(url)
        elif "tiktok.com" in url:
            tiktok_urls.append(url)
        elif "google.com/maps" in url or "maps.app.goo.gl" in url:
            gmaps_urls.append(url)
        else:
            print(f"⚠️ Nền tảng chưa hỗ trợ hoặc link sai định dạng: {url}")

    results = []
    if youtube_urls:
        results.extend(crawl_youtube_by_url(youtube_urls, max_comments_per_video=max_comments))
    if tiktok_urls:
        results.extend(crawl_tiktok_by_url(tiktok_urls, max_comments_per_video=max_comments))
    if gmaps_urls:
        results.extend(crawl_google_maps_by_url(gmaps_urls, max_comments=max_comments))

    return results

def crawl_youtube_by_url(url_list, max_comments_per_video=1000):
    """Cào bình luận trực tiếp bằng đường link YouTube."""
    downloader = YoutubeCommentDownloader()
    all_reviews = []

    for url in url_list:
        video_id = extract_video_id(url)
        if not video_id:
            print(f"URL không hợp lệ: {url}")
            continue

        print(f"Đang cào bình luận từ link: {url}")
        try:
            comments = downloader.get_comments_from_url(
                f"https://www.youtube.com/watch?v={video_id}"
            )
            count = 0

            for comment in comments:
                if count >= max_comments_per_video:
                    break

                text = comment.get("text", "").strip()
                author = comment.get("author", "Anonymous")

                if text:
                    all_reviews.append(
                        {
                            "platform": "YouTube",
                            "user_name": author,
                            "rating": None,
                            "comment_text": text,
                            "time": comment.get("time", "N/A"),
                            "source_url":url,

                        }
                    )
                    count += 1

            print(f"Lấy thành công {count} bình luận!")
        except Exception as e:
            print(f"Lỗi khi cào link: {e}")

    return all_reviews


def save_data(data, output_dir="data/raw"):
    """Lưu và cộng dồn (accumulate) dữ liệu mới vào file cũ, tự động xóa trùng lặp."""
    os.makedirs(output_dir, exist_ok=True)
    csv_path = os.path.join(output_dir, "raw_reviews.csv")
    json_path = os.path.join(output_dir, "raw_reviews.json")

    # 1. Chuyển dữ liệu mới cào thành DataFrame
    df_new = pd.DataFrame(data)

    # 2. Kiểm tra nếu đã có file cũ thì đọc lên để cộng dồn
    if os.path.exists(csv_path):
        try:
            df_old = pd.read_csv(csv_path)
            # Gộp dữ liệu cũ và mới
            df_combined = pd.concat([df_old, df_new], ignore_index=True)
            print(f"Đã đọc {len(df_old)} dòng dữ liệu cũ từ file.")
        except Exception:
            df_combined = df_new
    else:
        df_combined = df_new

    # 3. Loại bỏ các bình luận bị trùng lặp (dựa trên user_name và comment_text)
    initial_count = len(df_combined)
    df_combined.drop_duplicates(
        subset=["user_name", "comment_text"], keep="first", inplace=True
    )
    final_count = len(df_combined)

    # 4. Lưu lại toàn bộ dữ liệu đã cộng dồn vào CSV và JSON
    df_combined.to_csv(csv_path, index=False, encoding="utf-8-sig")

    # Lưu dạng JSON
    combined_dict = df_combined.to_dict(orient="records")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(combined_dict, f, ensure_ascii=False, indent=4)

    print(
        f"TỔNG CỘNG DỒN: {final_count} bình luận trong '{csv_path}' (Đã lọc {initial_count - final_count} trùng lặp)!"
    )


if __name__ == "__main__":
    youtube_urls = [
        "https://youtu.be/O-LJ9oBi7eQ",
        "https://youtu.be/D_qBYMbDp-Y?si=2CtLRF9-wuFVkNaC",
    ]

    print("Bắt đầu cào dữ liệu bình luận từ link YouTube...")
    # Truyền trực tiếp số 1000 vào đây
    reviews = crawl_youtube_by_url(youtube_urls, max_comments_per_video=1000)

    if reviews:
        save_data(reviews, output_dir="data/raw")
    else:
        print("Không lấy được bình luận nào.")
