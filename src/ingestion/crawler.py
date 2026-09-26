import os
import re
import time
import random
import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

RAW_DIR = "data/raw"                # du lieu tho: file CSV/JSON cac review that cao duoc
PROCESSED_DIR = "data/processed"    # tien trinh: danh sach quan da xu ly, de resume

CSV_PATH = os.path.join(RAW_DIR, "gmaps_reviews.csv")
JSON_PATH = os.path.join(RAW_DIR, "gmaps_reviews.json")
DONE_PATH = os.path.join(PROCESSED_DIR, "gmaps_done.txt")

HANOI_DISTRICTS = [
    "Hoan Kiem", "Ba Dinh", "Dong Da", "Hai Ba Trung", "Cau Giay", "Thanh Xuan",
    "Tay Ho", "Hoang Mai", "Long Bien", "Nam Tu Liem", "Bac Tu Liem", "Ha Dong",
]
KEYWORDS = ["quan an", "nha hang", "quan ca phe"]


class BlockedError(Exception):
    pass


def is_blocked(page):
    """Google chuyen sang trang /sorry/ khi nghi ngo bot."""
    return "/sorry/" in page.url or "unusual traffic" in page.content().lower()


def extract_place_key(url):
    """Ma dinh danh on dinh cua quan (khong phu thuoc toa do trong URL)."""
    m = re.search(r'!1s(0x[0-9a-fA-F]+:0x[0-9a-fA-F]+)', url)
    if m:
        return m.group(1)
    m = re.search(r'/place/([^/@]+)', url)
    return m.group(1) if m else url


def load_done_keys():
    done = set()
    if os.path.exists(DONE_PATH):
        with open(DONE_PATH, encoding="utf-8") as f:
            done = {line.strip() for line in f if line.strip()}
    if os.path.exists(CSV_PATH):
        done |= set(pd.read_csv(CSV_PATH)["restaurant_id"].dropna().astype(str))
    return done


def mark_done(key):
    """Ghi vao data/processed -> danh dau tien trinh, KHONG phai du lieu tho."""
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    with open(DONE_PATH, "a", encoding="utf-8") as f:
        f.write(key + "\n")


def append_reviews(rows):
    """Ghi vao data/raw -> du lieu tho that. Luu NGAY sau moi quan,
       dung giua chung khong mat du lieu."""
    if not rows:
        return
    os.makedirs(RAW_DIR, exist_ok=True)
    df_new = pd.DataFrame(rows)
    if os.path.exists(CSV_PATH):
        df = pd.concat([pd.read_csv(CSV_PATH), df_new], ignore_index=True)
        df.drop_duplicates(subset=["restaurant_id", "user_name", "review_text"], keep="last", inplace=True)
    else:
        df = df_new
    df.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")
    df.to_json(JSON_PATH, orient="records", force_ascii=False, indent=4)


def get_gmaps_links_from_search(page, search_url, max_restaurants=120):
    """Cuon den khi het danh sach (Google gioi han ~120 ket qua/lan tim)."""
    print(f"[Search] {search_url}")
    page.goto(search_url, timeout=60000)
    time.sleep(random.uniform(3, 5))
    if is_blocked(page):
        raise BlockedError()

    try:
        page.wait_for_selector('div[role="feed"]', timeout=10000)
    except Exception:
        print("  Khong thay danh sach ket qua (co the chi co 1 quan hoac sai selector).")
        return []

    last_count, stuck = 0, 0
    for _ in range(60):
        page.evaluate("""() => {
            const feed = document.querySelector('div[role="feed"]');
            if (feed) feed.scrollTop = feed.scrollHeight;
        }""")
        time.sleep(random.uniform(1.5, 3))
        count = page.locator('a.hfpxzc').count()
        text = page.content()
        if "Bạn đã xem hết danh sách" in text or "reached the end of the list" in text:
            break
        stuck = stuck + 1 if count == last_count else 0
        if stuck >= 3 or count >= max_restaurants:
            break
        last_count = count

    if is_blocked(page):
        raise BlockedError()

    urls = []
    for link in page.locator('a.hfpxzc').all():
        href = link.get_attribute('href')
        if href and href not in urls:
            urls.append(href)
    print(f"  -> {len(urls)} quan")
    return urls[:max_restaurants]


def crawl_gmaps_reviews(page, place_url, max_reviews=100):
    rows = []
    page.goto(place_url, timeout=60000)
    time.sleep(random.uniform(3, 5))
    if is_blocked(page):
        raise BlockedError()

    try:
        tab = page.locator('button[role="tab"]:has-text("Đánh giá"), button[role="tab"]:has-text("Reviews")').first
        if tab.count() > 0:
            tab.click()
            time.sleep(random.uniform(2, 4))
    except Exception:
        pass

    for _ in range(15):
        page.evaluate("""() => {
            const d = document.querySelector('.m6QErb.DxyBCb');
            if (d) d.scrollTop = d.scrollHeight;
        }""")
        time.sleep(random.uniform(1.5, 3))

    for btn in page.locator('button.w8nwRe').all():
        try:
            btn.click(timeout=1000)
        except Exception:
            pass

    if is_blocked(page):
        raise BlockedError()

    soup = BeautifulSoup(page.content(), 'html.parser')
    key = extract_place_key(place_url)
    for elem in soup.select('div.jftiEf')[:max_reviews]:
        text_el = elem.select_one('span.wiI7pd')
        text = text_el.get_text(strip=True) if text_el else ""
        name_el = elem.select_one('div.d4r55')
        rate_el = elem.select_one('span.kvMYJ')
        if text:
            rows.append({
                "platform": "GoogleMaps",
                "restaurant_id": key,
                "user_name": name_el.get_text(strip=True) if name_el else "N/A",
                "rating": rate_el.get('aria-label') if rate_el else "N/A",
                "review_text": text,
            })
    return rows


def main():
    queries = [f"{kw} {d} Ha Noi" for d in HANOI_DISTRICTS for kw in KEYWORDS]
    done = load_done_keys()
    print(f"Da xu ly truoc do: {len(done)} quan | So tu khoa: {len(queries)}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
        context = browser.new_context(locale="vi-VN", viewport={'width': 1280, 'height': 800})
        page = context.new_page()
        total_new = 0
        try:
            for q in queries:
                search_url = f"https://www.google.com/maps/search/{q.replace(' ', '+')}"
                links = get_gmaps_links_from_search(page, search_url)
                for url in links:
                    key = extract_place_key(url)
                    if key in done:
                        continue
                    rows = crawl_gmaps_reviews(page, url)
                    append_reviews(rows)
                    mark_done(key)
                    done.add(key)
                    total_new += len(rows)
                    print(f"  [{len(done)}] {key}: +{len(rows)} review (tong moi: {total_new})")
                    time.sleep(random.uniform(3, 6))
        except BlockedError:
            print("!!! GOOGLE DA CHAN. Du lieu da luu den quan cuoi cung. Doi 1-2 tieng roi chay lai, code se tu chay tiep.")
        except KeyboardInterrupt:
            print("Da dung bang tay. Chay lai de tiep tuc.")
        finally:
            browser.close()
    print(f"=== XONG. Review moi lan nay: {total_new} ===")


if __name__ == "__main__":
    main()