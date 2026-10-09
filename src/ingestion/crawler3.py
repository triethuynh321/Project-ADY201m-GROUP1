import os
import re
import time
import random
import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from botocore.exceptions import NoCredentialsError
import json
import boto3

RAW_DIR = "data/raw"                # du lieu tho: file CSV/JSON cac review that cao duoc
PROCESSED_DIR = "data/processed"    # tien trinh: danh sach quan da xu ly, de resume

CSV_PATH = os.path.join(RAW_DIR, "gmaps_reviews_hanoi.csv")
JSON_PATH = os.path.join(RAW_DIR, "gmaps_reviews_hanoi.json")
DONE_PATH = os.path.join(PROCESSED_DIR, "gmaps_done_hanoi.txt") # quan da xu ly (ke ca quan 0 review)
DEBUG_PATH = os.path.join(PROCESSED_DIR, "debug_review_no_rating.html")

HN_DISTRICTS = [
    # Các quận nội thành
    "Quận Ba Đình",
    "Quận Hoàn Kiếm",
    "Quận Tây Hồ",
    "Quận Long Biên",
    "Quận Cầu Giấy",
    "Quận Đống Đa",
    "Quận Hai Bà Trưng",
    "Quận Hoàng Mai",
    "Quận Thanh Xuân",
    "Quận Hà Đông",
    "Quận Nam Từ Liêm",
    "Quận Bắc Từ Liêm",
    
    # Các huyện và thị xã
    "Huyện Sóc Sơn",
    "Huyện Đông Anh",
    "Huyện Gia Lâm",
    "Huyện Thanh Trì",
    "Huyện Mê Linh",
    "Thị xã Sơn Tây",
    "Huyện Ba Vì",
    "Huyện Phúc Thọ",
    "Huyện Đan Phượng",
    "Huyện Hoài Đức",
    "Huyện Quốc Oai",
    "Huyện Thạch Thất",
    "Huyện Chương Mỹ",
    "Huyện Thường Tín",
    "Huyện Phú Xuyên",
    "Huyện Ứng Hòa",
    "Huyện Mỹ Đức"
]
KEYWORDS = [
    # 1. Đồ ăn nhanh & Ăn vặt
    "tra sua",
    "tra chanh",
    "topping",
    "banh trang tron",
    "banh trang nuong",
    "xoai lac",
    "ga ran",
    "pizza",
    "mi cay",
    "hamburger",
    "xien ban",
    "ca vien chien",
    "khoai tay chien",

    # 2. Món nước truyền thống
    "pho bo",
    "pho ga",
    "bun bo hue",
    "bun rieu cua",
    "mi quang",
    "hu tieu",
    "banh canh",
    "bun dau mam tom",
    "bun cha",

    # 3. Món cơm & Món chính văn phòng
    "com tam",
    "com ga",
    "com chien duong chau",
    "com nieu",
    "com van phong",
    "com tho",
    "banh mi chao",
    "banh mi thit nuong",
    "banh mi pate",

    # 4. Đồ ngọt, Tráng miệng & Healthy
    "che thai",
    "che khuc bach",
    "che buoi",
    "banh ngot",
    "banh kem",
    "banh flan",
    "tiramisu",
    "salad",
    "nuoc ep trai cay",
    "sua chua deo",
    "trai cay to"
]

MAX_PLACES_PER_SEARCH = 70    # chi lay ~70 quan dau moi lan tim (cang ve sau cang lech tu khoa)
MIN_REVIEWS = 50              # quan co it hon 50 danh gia -> bo qua
MAX_REVIEWS_PER_PLACE = 200   # 50-200 danh gia: lay het | tren 200: chi lay 200

# ---- Loc dia diem KHONG phai quan an ----
# Nhom 1 - CHAC CHAN khong phai quan an: gap la loai (du ten co chu gi di nua)
NON_FOOD_STRONG = [
    # Hanh chinh / co quan nha nuoc
    "chi cục", "ủy ban", "ubnd", r"\bsở\b", r"\bcục\b", "viện kiểm sát", "tòa án",
    "công an", "kho bạc", "hội đồng nhân dân", r"\bhđnd\b", "văn phòng đăng ký",
    "bảo hiểm xã hội", "đảng ủy", "mặt trận tổ quốc",
    # Y te
    "bệnh viện", "phòng khám", "trạm y tế", "đông y", "nha khoa", "trung tâm y tế",
    "nhà thuốc", "hiệu thuốc", "thẩm mỹ viện", "phòng xét nghiệm",
    # Giao duc
    "trường mầm non", "trường tiểu học", "trường thcs", "trường thpt", "trường trung học",
    "trường đại học", "trường cao đẳng", "trung tâm giáo dục", "trung tâm ngoại ngữ",
    # Tai chinh
    "ngân hàng", r"\batm\b", "phòng giao dịch", "tiệm vàng", "chứng khoán",
    # Xang dau / xe / buu chinh / tang le
    "cây xăng", "trạm xăng", "xăng dầu", "gara", "rửa xe", "sửa xe", "showroom",
    "bưu điện", "bưu cục", "nghĩa trang", "nhà tang lễ",
    # Doanh nghiep
    "công ty tnhh", "công ty cổ phần",
]
# Nhom 2 - THUONG khong phai quan an, NHUNG giu lai neu ten co chu an uong
# (vd "Cafe Công Viên", "Nhà hàng chay Chùa X", "Nhà hàng Sen - Khách sạn Y" van la quan an)
NON_FOOD_WEAK = [
    # Ton giao / van hoa / cong cong
    r"\bchùa\b", "nhà thờ", r"\bđền\b", r"\bmiếu\b", r"\bphủ\b", "thánh đường", "giáo xứ",
    "bảo tàng", "nhà hát", "rạp chiếu phim", "di tích", "thư viện", "nhà văn hóa",
    "công viên", "vườn hoa", r"\bđại học\b", "học viện", "mầm non",
    # The thao
    "sân vận động", "trung tâm thể thao", "sân tennis", "sân bóng", "bể bơi",
    r"\bgym\b", "yoga", "trung tâm thể dục", "võ thuật",
    # Giao thong
    "bến xe", r"\bga\b", "sân bay", "bến tàu", "trạm xe buýt", "bãi đỗ xe", "bãi gửi xe",
    # Nha o / luu tru / dich vu / mua sam
    "chung cư", "tòa nhà", "khu đô thị", "khách sạn", "hotel", "homestay", "nhà nghỉ",
    "spa", "salon", "cắt tóc", "làm tóc", "nail", "massage", "siêu thị", "điện thoại",
    "điện máy", "nội thất", "thời trang", "quần áo", "nhà sách", "karaoke", "khu vui chơi",
]
FOOD_WORDS = [
    "nhà hàng", "quán", "phở", "bún", "miến", "cơm", "bánh", "lẩu", "nướng", "cà phê",
    "cafe", "coffee", "trà", "bia", "chè", "xôi", "cháo", "restaurant", "bistro",
    "buffet", "ẩm thực", "food", "kitchen", "bbq", "pizza", "sushi", "chay", "hải sản",
]
NON_FOOD_STRONG_PATTERN = re.compile("|".join(NON_FOOD_STRONG), re.IGNORECASE)
NON_FOOD_WEAK_PATTERN = re.compile("|".join(NON_FOOD_WEAK), re.IGNORECASE)
FOOD_PATTERN = re.compile("|".join(FOOD_WORDS), re.IGNORECASE)
s3_client = boto3.client(
    's3',
    endpoint_url='http://localhost:9000',
    aws_access_key_id='dat666',
    aws_secret_access_key='dat@123456'
)
def get_next_part_index():
    """Tự động quét S3 để tìm số part lớn nhất hiện có và trả về số tiếp theo."""
    try:
        # Đảm bảo bucket tồn tại trước khi liệt kê
        s3_client.head_bucket(Bucket='gmaps-raw-data')
    except Exception:
        return 1

    try:
        response = s3_client.list_objects_v2(Bucket='gmaps-raw-data', Prefix='gmaps/raw/HN_part_')
        if 'Contents' not in response:
            return 1
        
        max_index = 0
        for obj in response['Contents']:
            key = obj['Key']
            # Dùng Regex để bắt số thứ tự trong tên file (VD: HP_part_005.json -> bắt được 5)
            match = re.search(r'HN_part_(\d+)\.json', key)
            if match:
                idx = int(match.group(1))
                if idx > max_index:
                    max_index = idx
        return max_index + 1
    except Exception as e:
        print(f"Lỗi khi quét S3 tìm part cũ: {e}")
        return 1
def upload_batch_to_s3(data_batch, part_index):
    """Hàm phụ trợ đẩy từng phần dữ liệu lên S3 ngay lập tức"""
    filename = f"HN_part_{part_index:03d}.json"
    file_content = json.dumps(data_batch, ensure_ascii=False, indent=2)
    # Đảm bảo bucket tồn tại trước khi upload
    try:
        s3_client.head_bucket(Bucket='gmaps-raw-data')
    except Exception:
        try:
            s3_client.create_bucket(Bucket='gmaps-raw-data')
        except Exception:
            pass
    # Đẩy lên bucket
    s3_client.put_object(
        Bucket='gmaps-raw-data',
        Key=f'gmaps/raw/{filename}',
        Body=file_content
    )
    print(f"Đã tự động đẩy {filename} lên S3 thành công!")


def is_non_food(name):
    """True neu ten cho thay day KHONG phai quan an."""
    if not name:
        return False
    if NON_FOOD_STRONG_PATTERN.search(name):
        return True
    if NON_FOOD_WEAK_PATTERN.search(name) and not FOOD_PATTERN.search(name):
        return True
    return False


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

# Doc TEN + so review hien san trong danh sach tim kiem (vd "(1.360)") de biet quan nao dang cao
EXTRACT_COUNT_JS = r"""
() => {
  const out = [];
  document.querySelectorAll('a.hfpxzc').forEach(a => {
    let el = a.parentElement, count = null;
    for (let i = 0; i < 6 && el; i++) {
      if (el.querySelectorAll('a.hfpxzc').length > 1) break;
      const m = el.textContent.match(/\(([\d]{1,3}(?:[.,]\d{3})*)\)/);
      if (m) { count = parseInt(m[1].replace(/[.,]/g, ''), 10); break; }
      el = el.parentElement;
    }
    out.push({ href: a.href, name: a.getAttribute('aria-label') || '', review_count: count });
  });
  return out;
}
"""

# Tim TAT CA khoi review, tu leo len tim the CHA THAT SU cuon duoc (khong doan ten class co dinh).
# QUET CA khoi review, khong chi khoi DAU TIEN: sau khi bam "mo rong danh sach", review moi
# thuong nam trong 1 khung RIENG, khong phai khung chua khoi review xem truoc dau tien.
# Cập nhật lại SCROLL_JS trong file crawler.py
SCROLL_JS = r"""
() => {
    const scrollablePane = document.querySelector('div.m6QErb.DxyBCb') || document.querySelector('div.m6QErb');
    if (scrollablePane) {
        scrollablePane.scrollTop = scrollablePane.scrollHeight;
        return true;
    }
    const blocks = document.querySelectorAll('div.jftiEf');
    for (const block of blocks) {
        let el = block.parentElement;
        for (let i = 0; i < 10 && el; i++) {
            if (el.scrollHeight > el.clientHeight) {
                el.scrollTop = el.scrollHeight;
                return true;
            }
            el = el.parentElement;
        }
    }
    return false;
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
    """Chi GHI THEM dong moi vao cuoi file (khong doc lai ca file) -> file lon van nhanh."""
    if not rows:
        return
    os.makedirs(RAW_DIR, exist_ok=True)
    df = pd.DataFrame(rows).drop_duplicates(subset=["restaurant_id", "user_name", "review_text"])
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce").astype("Int64")
    try:
        # File cu khac cot (vd con cot rating_text tu ban truoc) -> sua 1 lan cho khop
        if os.path.exists(CSV_PATH):
            with open(CSV_PATH, encoding="utf-8-sig") as f:
                header = f.readline().strip().split(",")
            if header != list(df.columns):
                old = pd.read_csv(CSV_PATH).reindex(columns=df.columns)
                old.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")
        first_time = not os.path.exists(CSV_PATH)
        df.to_csv(CSV_PATH, mode="a", header=first_time, index=False,
                  encoding="utf-8-sig" if first_time else "utf-8")
    except PermissionError:
        print("!!! KHONG GHI DUOC FILE - co the dang mo bang Excel. Dong file lai.")


def export_json():
    """Tao file JSON 1 lan o cuoi (thay vi moi quan 1 lan) va in tong ket."""
    if os.path.exists(CSV_PATH):
        df = pd.read_csv(CSV_PATH)
        df["rating"] = pd.to_numeric(df["rating"], errors="coerce").astype("Int64")
        df.to_json(JSON_PATH, orient="records", force_ascii=False, indent=2)
        size_mb = os.path.getsize(CSV_PATH) / 1024 / 1024
        print(f"Tong: {len(df)} review, {df['restaurant_id'].nunique()} quan, file CSV {size_mb:.1f} MB")


def get_gmaps_links_from_search(page, search_url, max_restaurants=MAX_PLACES_PER_SEARCH):
    """Tra ve list [{href, name, review_count}] cua ~70 quan DAU TIEN (du so thi dung cuon)."""
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
        text = page.content()  # de kiem tra chu "da xem het danh sach" ben duoi
        if "Bạn đã xem hết danh sách" in text or "reached the end of the list" in text:
            break
        stuck = stuck + 1 if count == last_count else 0
        if stuck >= 6 or count >= max_restaurants:
            break
        last_count = count

    if is_blocked(page):
        raise BlockedError()

    entries, seen = [], set()
    for r in page.evaluate(EXTRACT_COUNT_JS):
        if r["href"] and r["href"] not in seen:
            seen.add(r["href"])
            entries.append(r)
    print(f"  -> {len(entries)} quan")
    return entries[:max_restaurants]


def crawl_gmaps_reviews(page, place_url, max_reviews=100,batch_data=None, tracker=None, batch_size=500):
    rows = []
    page.goto(place_url, timeout=60000)
    time.sleep(random.uniform(3, 5))
    if is_blocked(page):
        raise BlockedError()

    h1 = BeautifulSoup(page.content(), "html.parser").select_one("h1")
    shop_name = h1.get_text(strip=True) if h1 else "N/A"
    if is_non_food(shop_name):
        print(f"  Bo qua (khong phai quan an): {shop_name}")
        return []
    # Click vào tab "Bài đánh giá" trước
    clicked = False
    tab_selectors = [
        'button[tabindex][jsaction*="reviews"]',
        'button[role="tab"]:has-text("Bài đánh giá")',
        'button[role="tab"]:has-text("Reviews")',
        'div[role="tablist"] button:nth-child(2)'
    ]
    
    for sel in tab_selectors:
        try:
            element = page.locator(sel).first
            if element.count() > 0 and element.is_visible():
                element.click()
                time.sleep(random.uniform(2, 4))
                clicked = True
                break
        except Exception:
            continue

    # QUAN TRỌNG: Click tiếp vào nút "Xem các bài đánh giá khác (...)" nếu nó xuất hiện trên màn hình tóm tắt
    try:
        see_all_btn = page.locator('button, a').filter(has_text=re.compile(r"xem các bài đánh giá khác|\(\d+[.,]?\d*\)", re.I)).first
        if see_all_btn.count() > 0 and see_all_btn.is_visible():
            see_all_btn.click()
            time.sleep(random.uniform(3, 5))
    except Exception:
        pass

    # Chờ khung cuộn xuất hiện
    try:
        page.wait_for_selector('div.m6QErb.DxyBCb', timeout=5000)
    except Exception:
        pass
    # Cach 1: kieu giao dien co thanh TAB ro rang (Overview | Menu | Reviews | About)
    try:
        tab = page.get_by_text(re.compile(r"reviews|bài đánh giá|đánh giá", re.I)).first
        if tab.count() > 0:
            tab.click()
            time.sleep(random.uniform(2, 4))
    except Exception:
        pass

    # Cach 2: nut mo rong danh sach - Google dung nhieu cach dien dat khac nhau
    try:
        candidates = page.locator("a, button").filter(
            has_text=re.compile(r"(more reviews|xem (thêm|các bài|tất cả)[^\n]*đánh giá|\d{1,3}[.,]\d{3}\s*\)?\s*$)", re.I)
        )
        if candidates.count() > 0:
            candidates.first.click()
            time.sleep(random.uniform(2, 4))
    except Exception:
        pass

    # Cach 3: kieu giao dien cu, tab co gan dung role="tab"
    try:
        tab2 = page.locator('button[role="tab"]:has-text("Đánh giá"), button[role="tab"]:has-text("Reviews"), button[role="tab"]:has-text("Bài đánh giá")').first
        if tab2.count() > 0:
            tab2.click()
            time.sleep(random.uniform(2, 4))
    except Exception:
        pass

    if is_blocked(page):
        raise BlockedError()

    
    last_count, stuck = 0, 0
    for _ in range(60):
        page.evaluate(SCROLL_JS)
        time.sleep(random.uniform(1.5, 3))
        count = page.locator('div.jftiEf').count()
        if count >= max_reviews:
            break
        stuck = stuck + 1 if count == last_count else 0
        if stuck >= 8:
            break
        last_count = count

    for btn in page.locator('button.w8nwRe').all():   # nut "Thêm" mo review dai
        try:
            btn.click(timeout=1000)
        except Exception:
            pass

    if is_blocked(page):
        raise BlockedError()

    # Neu van bi ket o so qua thap (nghi ngo chua mo dung khung review) -> tu chup lai bang chung
    stuck_count = page.locator('div.jftiEf').count()
    if stuck_count <= 5:
        os.makedirs(PROCESSED_DIR, exist_ok=True)
        shot_path = os.path.join(PROCESSED_DIR, "debug_stuck_screenshot.png")
        html_path = os.path.join(PROCESSED_DIR, "debug_stuck_page.html")
        try:
            page.screenshot(path=shot_path, full_page=True)
        except Exception:
            pass
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(page.content())
        print(f"  (!) Chi thay {stuck_count} review - da luu {shot_path} va {html_path} de kiem tra")

    key = extract_place_key(place_url)
    for r in page.evaluate(READ_REVIEWS_JS)[:max_reviews]:
        if r["rating"] is None and r["html"] and not os.path.exists(DEBUG_PATH):
            os.makedirs(PROCESSED_DIR, exist_ok=True)
            with open(DEBUG_PATH, "w", encoding="utf-8") as f:
                f.write(r["html"])
            print(f"  (!) Khong doc duoc sao - da luu mau HTML vao {DEBUG_PATH}")
        if r["review_text"]:
            review_item = {
                "platform": "GoogleMaps",
                "restaurant_id": key,
                "shop_name": shop_name,
                "user_name": r.get("user_name") if r.get("user_name") and r.get("user_name") != 'N/A' else "Unknown",
                "rating": r["rating"],
                "review_text": r["review_text"],
            }
            rows.append(review_item)
            
            # --- THÊM ĐOẠN NÀY ĐỂ ĐẨY LÊN S3 REAL-TIME ---
            if batch_data is not None and tracker is not None:
                batch_data.append(review_item)
                if len(batch_data) >= batch_size:
                    upload_batch_to_s3(batch_data, tracker["part"])
                    batch_data.clear()
                    tracker["part"] += 1
    got = sum(1 for r in rows if r["rating"] is not None)
    print(f"  {shop_name}: {len(rows)} review, doc duoc sao {got}/{len(rows)}")
    return rows


def main():
    batch_data = []
    # Tự động tiếp nối số part từ lần cào trước trên S3
    part_counter = get_next_part_index() 
    print(f"-> Sẽ tiếp tục lưu file part bắt đầu từ số: {part_counter:03d}")
    batch_size = 500  # Cứ đủ 500 review thì đẩy lên S3 một lần

    queries = [f"{kw} {d}" for d in HN_DISTRICTS for kw in KEYWORDS]
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
                entries = get_gmaps_links_from_search(page, search_url)
                for entry in entries:
                    url, rc = entry["href"], entry["review_count"]
                    key = extract_place_key(url)
                    if key in done:
                        continue
                    name = entry.get("name", "")
                    if is_non_food(name):
                        print(f"  Bo qua (khong phai quan an): {name}")
                        mark_done(key)
                        done.add(key)
                        continue
                    if rc is None or rc < MIN_REVIEWS:
                        print(f"  Bo qua (chi co {rc} danh gia, duoi {MIN_REVIEWS}): {name or key}")
                        mark_done(key)   # danh dau da xet, lan sau khoi kiem tra lai
                        done.add(key)
                        continue

                    # 50-200 danh gia: lay het | tren 200: chi lay 200
                    target = min(rc, MAX_REVIEWS_PER_PLACE)
                    print(f"  {name}: {rc} danh gia -> lay toi da {target}")
                    tracker = {"part": part_counter}
                    rows = crawl_gmaps_reviews(
                        page, url, max_reviews=target, 
                        batch_data=batch_data, tracker=tracker, batch_size=batch_size
                    )
                    
                    # Cập nhật lại part_counter từ tracker sau khi cào xong một quán
                    part_counter = tracker["part"]
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
    export_json()
    print(f"=== XONG. Review moi lan nay: {total_new} ===")
    # Đặt ở cuối hàm main():
    if batch_data:
        upload_batch_to_s3(batch_data, tracker["part"])
        print(f"Đã đẩy phần dữ liệu cuối cùng lên S3 thành công!")


if __name__ == "__main__":
    main()