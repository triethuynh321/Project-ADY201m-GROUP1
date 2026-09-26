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
DONE_PATH = os.path.join(PROCESSED_DIR, "gmaps_done.txt")   # quan da xu ly (ke ca quan 0 review)
DEBUG_PATH = os.path.join(PROCESSED_DIR, "debug_review_no_rating.html")

HANOI_DISTRICTS = [
    "Hoan Kiem", "Ba Dinh", "Dong Da", "Hai Ba Trung", "Cau Giay", "Thanh Xuan",
    "Tay Ho", "Hoang Mai", "Long Bien", "Nam Tu Liem", "Bac Tu Liem", "Ha Dong",
]
KEYWORDS = ["quan an", "nha hang", "quan ca phe"]


# JavaScript chay TRUC TIEP trong trinh duyet: doc tung review, dem sao vang theo MAU hien thi
READ_REVIEWS_JS = r"""
() => {
  const isYellow = (el) => {
    const c = getComputedStyle(el).color.match(/\d+/g);
    if (!c) return false;
    const [r, g, b] = c.map(Number);
    return r > 180 && g > 120 && b < 120;          // vang/cam = sao duoc to; xam = sao trong
  };
  const out = [];
  document.querySelectorAll('div.jftiEf').forEach(block => {
    // Chi xu ly khoi review TRONG CUNG (bo khoi boc ngoai chua nhieu review)
    if (block.querySelector('div.jftiEf')) return;

    // Moi tim kiem deu gioi han TRONG block nay -> khong the lay diem chung cua quan
    let rating = null, method = null;

    // Cach 1: nhan an cua hang sao, vd "5 sao" / "1 star" (bo qua dang thap phan "4,7 sao")
    for (const el of block.querySelectorAll('[aria-label]')) {
      const m = (el.getAttribute('aria-label') || '').match(/(?<![\d.,])([1-5])\s*(sao|star)/i);
      if (m) { rating = +m[1]; method = 'aria-label'; break; }
    }
    // Cach 2: dem sao MAU VANG - chi xet dung icon ngoi sao, khong xet icon khac
    if (rating === null) {
      let stars = [...block.querySelectorAll('span.hCCjke')];
      if (stars.length < 5)
        stars = [...block.querySelectorAll('[class*="google-symbols"]')]
                  .filter(el => ['star', 'star_half', '★', ''].includes(el.textContent.trim()));
      if (stars.length >= 5) {
        const n = stars.slice(0, 5).filter(isYellow).length;
        if (n >= 1 && n <= 5) { rating = n; method = 'dem-sao-vang'; }
      }
    }
    // Cach 3: chu "4/5" o phan dau review - BO QUA noi dung binh luan va phan hoi chu quan
    if (rating === null) {
      const clone = block.cloneNode(true);
      clone.querySelectorAll('.wiI7pd, .CDe7pd, .MyEned').forEach(el => el.remove());
      const m = clone.textContent.match(/(?<!\d)([1-5])\s*\/\s*5(?!\d)/);
      if (m) { rating = +m[1]; method = 'x/5'; }
    }
    const name = block.querySelector('div.d4r55');
    const text = block.querySelector('span.wiI7pd');
    out.push({
      user_name: name ? name.innerText.trim() : 'N/A',
      review_text: text ? text.innerText.trim() : '',
      rating: rating,
      method: method,
      html: rating === null ? block.outerHTML.slice(0, 5000) : null,
    });
  });
  return out;
}
"""


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
    try:
        if os.path.exists(CSV_PATH):
            df = pd.concat([pd.read_csv(CSV_PATH), df_new], ignore_index=True)
            df.drop_duplicates(subset=["restaurant_id", "user_name", "review_text"], keep="last", inplace=True)
        else:
            df = df_new
        df["rating"] = pd.to_numeric(df["rating"], errors="coerce").astype("Int64")  # so: dung de tinh toan
        df = df.drop(columns=["rating_text"], errors="ignore")   # xoa cot 4/5 neu lo co tu lan truoc
        df.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")
        df.to_json(JSON_PATH, orient="records", force_ascii=False, indent=4)
    except PermissionError:
        print("!!! KHONG GHI DUOC FILE - co the dang mo bang Excel. Dong file lai.")


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

    h1 = BeautifulSoup(page.content(), "html.parser").select_one("h1")
    shop_name = h1.get_text(strip=True) if h1 else "N/A"

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

    for btn in page.locator('button.w8nwRe').all():   # nut "Thêm" mo review dai
        try:
            btn.click(timeout=1000)
        except Exception:
            pass

    if is_blocked(page):
        raise BlockedError()

    key = extract_place_key(place_url)
    for r in page.evaluate(READ_REVIEWS_JS)[:max_reviews]:
        if r["rating"] is None and r["html"] and not os.path.exists(DEBUG_PATH):
            os.makedirs(PROCESSED_DIR, exist_ok=True)
            with open(DEBUG_PATH, "w", encoding="utf-8") as f:
                f.write(r["html"])
            print(f"  (!) Khong doc duoc sao - da luu mau HTML vao {DEBUG_PATH}")
        if r["review_text"]:
            rows.append({
                "platform": "GoogleMaps",
                "restaurant_id": key,
                "shop_name": shop_name,
                "user_name": r["user_name"],
                "rating": r["rating"],
                "review_text": r["review_text"],
            })
    got = sum(1 for r in rows if r["rating"] is not None)
    print(f"  {shop_name}: {len(rows)} review, doc duoc sao {got}/{len(rows)}")
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