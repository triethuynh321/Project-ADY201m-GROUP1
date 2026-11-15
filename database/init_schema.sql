
-- Xóa toàn bộ các bảng và view cũ nếu tồn tại để làm sạch
DROP VIEW IF EXISTS vw_region_stats, vw_city_stats, vw_rating_distribution, vw_restaurant_stats CASCADE;
DROP TABLE IF EXISTS reviews, users, platforms, restaurants CASCADE;

-- 1. BẢNG NHÀ HÀNG: restaurants (Thực thể gốc)
CREATE TABLE restaurants (
    restaurant_id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(255),
    city VARCHAR(100),
    total_reviews INT DEFAULT 0,
    avg_rating FLOAT DEFAULT 0.0,
    avg_comment_length FLOAT DEFAULT 0.0
);

-- 2. BẢNG NGƯỜI DÙNG: users (Tác giả viết đánh giá)
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    author_name VARCHAR(255) UNIQUE
);

-- 3. BẢNG NỀN TẢNG: platforms (Nguồn dữ liệu: GoogleMaps, Foody)
CREATE TABLE platforms (
    platform_id SERIAL PRIMARY KEY,
    platform_name VARCHAR(50) UNIQUE
);

-- 4. BẢNG CHI TIẾT ĐÁNH GIÁ: reviews (Bảng trung tâm liên kết các bảng trên)
CREATE TABLE reviews (
    review_id SERIAL PRIMARY KEY,
    restaurant_id VARCHAR(100) REFERENCES restaurants(restaurant_id),
    user_id INT REFERENCES users(user_id),
    platform_id INT REFERENCES platforms(platform_id),
    city VARCHAR(100),
    rating INT,
    comment_cleaned TEXT,
    comment_length INT
);

-- 5. CÁC VIEW TỔNG HỢP CHO R (Giữ nguyên để tiện vẽ biểu đồ)
CREATE VIEW vw_restaurant_stats AS
SELECT 
    r.restaurant_id,
    r.name,
    r.city,
    COUNT(rev.rating) AS total_reviews,
    AVG(rev.rating) AS avg_rating,
    AVG(rev.comment_length) AS avg_comment_length
FROM restaurants r
LEFT JOIN reviews rev ON r.restaurant_id = rev.restaurant_id
GROUP BY r.restaurant_id, r.name, r.city;

CREATE VIEW vw_rating_distribution AS
SELECT 
    p.platform_name AS platform,
    rev.rating,
    COUNT(*) AS review_count
FROM reviews rev
JOIN platforms p ON rev.platform_id = p.platform_id
GROUP BY p.platform_name, rev.rating;

CREATE OR REPLACE VIEW vw_city_stats AS
SELECT 
    city,
    COUNT(DISTINCT restaurant_id) AS total_restaurants,
    COUNT(*) AS total_reviews,
    AVG(rating) AS avg_rating,
    AVG(cardinality(regexp_split_to_array(trim(comment_cleaned), '\s+'))) AS avg_comment_length
FROM reviews
WHERE comment_cleaned IS NOT NULL
GROUP BY city;

CREATE OR REPLACE VIEW vw_region_stats AS
WITH regional_reviews AS (
    SELECT 
        rev.rating,
        rev.comment_cleaned,
        CASE 
            -- Gom nhóm toàn diện Miền Bắc (bao gồm cả không dấu và viết hoa/thường)
            WHEN LOWER(r.city) IN ('hà nội', 'ha noi', 'hải phòng', 'hai phong', 'quảng ninh', 'quang ninh', 
                                   'nam định', 'nam dinh', 'thái bình', 'thai binh', 'ninh bình', 'ninh binh', 
                                   'hà nam', 'ha nam', 'hưng yên', 'hung yen', 'hải dương', 'hai duong', 
                                   'vĩnh phúc', 'vinh phuc', 'bắc ninh', 'bac ninh', 'bắc giang', 'bac giang', 
                                   'phú thọ', 'phu tho', 'thái nguyên', 'thai nguyen', 'lào cai', 'lao cai', 
                                   'yên bái', 'yen bai', 'tuyên quang', 'tuyen quang', 'hà giang', 'ha giang', 
                                   'cao bằng', 'cao bang', 'bắc kạn', 'bac kan', 'lạng sơn', 'lang son', 
                                   'sơn la', 'son la', 'hòa bình', 'hoa binh', 'điện biên', 'dien bien', 'lai châu', 'lai chau') THEN 'Miền Bắc'
            
            -- Gom nhóm Miền Trung & Huế
            WHEN LOWER(r.city) IN ('đà nẵng', 'da nang', 'huế', 'hue', 'thừa thiên huế', 'thua thien hue', 
                                   'quảng nam', 'quang nam', 'quảng ngãi', 'quang ngai', 'bình định', 'binh dinh', 
                                   'phú yên', 'phu yen', 'khánh hòa', 'khanh hoa', 'ninh thuận', 'ninh thuan', 
                                   'bình thuận', 'binh thuan', 'thanh hóa', 'thanh hoa', 'nghệ an', 'nghe an', 
                                   'hà tĩnh', 'ha tinh', 'quảng bình', 'quang binh', 'quảng trị', 'quang tri', 
                                   'kon tum', 'gia lai', 'đắk lắk', 'dak lak', 'đắk nông', 'dak nong', 'lâm đồng', 'lam dong') THEN 'Miền Trung'
            
            -- Gom nhóm Miền Nam & TP.HCM
            WHEN LOWER(r.city) IN ('hồ chí minh', 'ho chi minh', 'tp. hồ chí minh', 'tp hcm', 'tphcm', 
                                   'cần thơ', 'can tho', 'đồng nai', 'dong nai', 'bình dương', 'binh duong', 
                                   'bình phước', 'binh phuoc', 'tây ninh', 'tay ninh', 'bà rịa - vũng tàu', 'ba ria - vung tau', 
                                   'long an', 'tiền giang', 'tien giang', 'bến tre', 'ben tre', 'trà vinh', 'tra vinh', 
                                   'vĩnh long', 'vinh long', 'đồng tháp', 'dong thap', 'an giang', 'an giang', 
                                   'kiên giang', 'kien giang', 'hậu Giang', 'hau giang', 'sóc trăng', 'soc trang', 
                                   'bạc liêu', 'bac lieu', 'cà mau', 'ca mau') THEN 'Miền Nam'
            ELSE 'Khác'
        END AS region
    FROM restaurants r
    JOIN reviews rev ON r.restaurant_id = rev.restaurant_id
    WHERE rev.comment_cleaned IS NOT NULL
)
SELECT 
    region,
    AVG(rating) AS avg_rating,
    AVG(cardinality(regexp_split_to_array(trim(comment_cleaned), '\s+'))) AS avg_comment_length,
    COUNT(*) AS total_reviews
FROM regional_reviews
GROUP BY region;

-- TẠO INDEX TỐI ƯU TRUY VẤN
CREATE INDEX idx_restaurants_city ON restaurants(city);
CREATE INDEX idx_reviews_restaurant_id ON reviews(restaurant_id);
CREATE INDEX idx_reviews_city ON reviews(city);
-- VIEW THỐNG KÊ TOP CỤM 2 TỪ GHÉP XUẤT HIỆN NHIỀU NHẤT TRONG ĐÁNH GIÁ 1 SAO
-- VIEW THỐNG KÊ TOP CỤM 2 TỪ GHÉP XUẤT HIỆN NHIỀU NHẤT TRONG ĐÁNH GIÁ 1 SAO
CREATE OR REPLACE VIEW v_top_1star_bigrams AS
WITH filtered_reviews AS (
    SELECT comment_cleaned
    FROM reviews
    WHERE rating = 1 AND comment_cleaned IS NOT NULL
),
word_arrays AS (
    SELECT regexp_split_to_array(lower(trim(comment_cleaned)), E'\\s+') AS words
    FROM filtered_reviews
),
bigrams AS (
    SELECT 
        words[i] || ' ' || words[i+1] AS phrase
    FROM word_arrays,
    LATERAL generate_subscripts(words, 1) AS i
    WHERE i < array_length(words, 1)
      AND words[i] <> '' 
      AND words[i+1] <> ''
)
SELECT 
    phrase AS two_word_phrase,
    COUNT(*) AS frequency
FROM bigrams
-- Bổ sung danh sách các cụm từ vô nghĩa, từ dừng cần loại bỏ tại đây:
WHERE phrase NOT IN (
    'không có', 'cũng không', 'quay lại', 'không bao', 'bao giờ', 
    'là không', 'thì không', 'ở đây', 'mình thấy', 'được không',
    'mà không', 'và không', 'để lại', 'cho biết', 'còn không'
)
GROUP BY phrase
ORDER BY frequency DESC;
-- Cập nhật View phân tích mối quan hệ giữa Số sao và Số lượng từ trong bình luận
CREATE OR REPLACE VIEW vw_rating_vs_comment_length AS
SELECT 
    rating,
    COUNT(*) AS total_reviews,
    AVG(cardinality(regexp_split_to_array(trim(comment_cleaned), '\s+'))) AS avg_comment_length,
    MIN(cardinality(regexp_split_to_array(trim(comment_cleaned), '\s+'))) AS min_comment_length,
    MAX(cardinality(regexp_split_to_array(trim(comment_cleaned), '\s+'))) AS max_comment_length
FROM reviews
WHERE rating IS NOT NULL AND comment_cleaned IS NOT NULL
GROUP BY rating
ORDER BY rating;
-- Tạo View xu hướng kết hợp số lượng review và đánh giá trung bình theo từng nhà hàng
CREATE OR REPLACE VIEW vw_trend_reviews_vs_rating AS
SELECT 
    r.restaurant_id,
    r.name,
    r.city,
    COUNT(rev.rating) AS total_reviews,
    AVG(rev.rating) AS avg_rating
FROM restaurants r
LEFT JOIN reviews rev ON r.restaurant_id = rev.restaurant_id
GROUP BY r.restaurant_id, r.name, r.city;
CREATE OR REPLACE VIEW vw_review_bins_trend AS
WITH restaurant_totals AS (
    SELECT 
        r.restaurant_id,
        COUNT(rev.rating) AS total_reviews,
        AVG(rev.rating) AS avg_rating
    FROM restaurants r
    LEFT JOIN reviews rev ON r.restaurant_id = rev.restaurant_id
    GROUP BY r.restaurant_id
),
binned_data AS (
    SELECT 
        FLOOR(total_reviews / 10) * 10 AS bin_start,
        (FLOOR(total_reviews / 10) * 10) + 10 AS bin_end,
        avg_rating
    FROM restaurant_totals
    -- Chỉ lấy các nhà hàng có số lượng review strictly nhỏ hơn 200 (hoặc chặn ở 199.9) để không bị đẩy sang mốc 200-210
    WHERE total_reviews >= 0 AND total_reviews < 200
)
SELECT 
    CONCAT(bin_start, '-', bin_end) AS review_range,
    bin_start,
    AVG(avg_rating) AS mean_rating_in_bin,
    COUNT(*) AS restaurant_count
FROM binned_data
GROUP BY bin_start, bin_end
ORDER BY bin_start;
-- Cập nhật hoặc tạo mới View phân tích từ khóa phổ biến theo từng Vùng miền
CREATE OR REPLACE VIEW vw_region_top_bigrams AS
WITH review_regions AS (
    SELECT 
        CASE 
            WHEN city IN ('Hanoi', 'Ha Noi', 'Hai Phong', 'Quang Ninh', 'Bac Ninh') THEN 'Miền Bắc'
            WHEN city IN ('Da Nang', 'Hue', 'Thua Thien Hue') THEN 'Miền Trung'
            WHEN city IN ('Ho Chi Minh', 'Can Tho', 'Dong Nai') THEN 'Miền Nam'
            ELSE 'Khác'
        END AS region,
        comment_cleaned
    FROM reviews
    WHERE comment_cleaned IS NOT NULL
),
word_arrays AS (
    SELECT 
        region,
        regexp_split_to_array(lower(trim(comment_cleaned)), E'\\s+') AS words
    FROM review_regions
    WHERE region <> 'Khác'
),
bigrams AS (
    SELECT 
        region,
        words[i] || ' ' || words[i+1] AS phrase
    FROM word_arrays,
    LATERAL generate_subscripts(words, 1) AS i
    WHERE i < array_length(words, 1)
      AND words[i] <> '' 
      AND words[i+1] <> ''
),
ranked_bigrams AS (
    SELECT 
        region,
        phrase AS top_phrase,
        COUNT(*) AS frequency,
        ROW_NUMBER() OVER (PARTITION BY region ORDER BY COUNT(*) DESC) as rnk
    FROM bigrams
    -- Loại bỏ các từ dừng / từ phụ trợ chung chung nếu cần
    WHERE phrase NOT IN ('không có', 'cũng không', 'quay lại', 'ở đây', 'mình thấy')
    GROUP BY region, phrase
)
SELECT 
    region,
    top_phrase,
    frequency
FROM ranked_bigrams
WHERE rnk = 1; -- Lấy cụm từ đứng đầu (xuất hiện nhiều nhất) cho mỗi miền