import requests
from bs4 import BeautifulSoup
import re
import sys
import time

# --- Cấu hình chung ---
BASE_URL = "https://govolunteerhcmc.vn"
FALLBACK_IMAGE_URL = "https://govolunteerhcmc.vn/wp-content/uploads/2024/02/logo-gv-tron.png"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
    'Referer': 'https://www.google.com/'
}

def get_high_res_image_url(url: str):
    """Loại bỏ các hậu tố kích thước ảnh (-150x150, -300x200, v.v.) để lấy ảnh gốc chất lượng cao."""
    if not url:
        return FALLBACK_IMAGE_URL
    return re.sub(r'-\d{2,4}x\d{2,4}(?=\.\w+$)', '', url)

def _scrape_generic_page(url: str, container_selector: str):
    """Hàm chung để cào các trang có cấu trúc section > h2 > article."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"❌ Lỗi khi cào {url}: {e}", file=sys.stderr)
        return []

    soup = BeautifulSoup(response.text, "lxml")
    sections_data = []
    page_container = soup.select_one(container_selector)
    if not page_container:
        print(f"❌ Không tìm thấy container '{container_selector}' tại {url}", file=sys.stderr)
        return []

    for sec in page_container.select("section.elementor-top-section"):
        h2 = sec.select_one("h2.elementor-heading-title")
        if not h2 or not h2.text.strip():
            continue
        category_name = h2.text.strip()
        
        articles = []
        for post in sec.select("article.elementor-post"):
            a_tag = post.select_one("h3.elementor-post__title a")
            if not a_tag or not a_tag.get('href'):
                continue

            img_tag = post.select_one(".elementor-post__thumbnail img")
            image_url = FALLBACK_IMAGE_URL
            if img_tag:
                src = img_tag.get('src') or img_tag.get('data-src')
                if src:
                    image_url = get_high_res_image_url(src)

            excerpt_tag = post.select_one(".elementor-post__excerpt p")
            excerpt = excerpt_tag.text.strip() if excerpt_tag else "Không có mô tả."
            
            articles.append({
                "title": a_tag.text.strip(),
                "link": a_tag['href'],
                "imageUrl": image_url,
                "excerpt": excerpt,
            })

        if articles:
            unique_articles = list({article['link']: article for article in articles}.values())
            sections_data.append({"category": category_name, "articles": unique_articles})
    
    return sections_data

# --- TRIỂN KHAI CÁC HÀM SCRAPE ---

def scrape_news():
    """Cào toàn bộ bài viết từ trang /news và các trang con."""
    print("🚀 Bắt đầu cào dữ liệu từ /news/...")
    all_articles = []
    page = 1
    max_pages = 1
    category_name = "Nhật ký tình nguyện"
    base_news_url = f"{BASE_URL}/news/"

    while page <= max_pages:
        current_url = f"{base_news_url}{page}/" if page > 1 else base_news_url
        print(f"📄 Đang cào trang: {current_url}")
        try:
            response = requests.get(current_url, headers=HEADERS, timeout=20)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"❌ Lỗi khi cào trang {current_url}: {e}", file=sys.stderr)
            break

        soup = BeautifulSoup(response.text, "lxml")
        if page == 1:
            anchor = soup.select_one(".e-load-more-anchor[data-max-page]")
            if anchor: max_pages = int(anchor['data-max-page'])
            print(f"🔍 Tìm thấy tổng cộng {max_pages} trang.")

        container = soup.select_one(".elementor-1096")
        if not container:
            page += 1
            continue
            
        for post in container.select("article.elementor-post"):
            a_tag = post.select_one("h3.elementor-post__title a")
            if not a_tag or not a_tag.get('href'): continue
            img_tag = post.select_one(".elementor-post__thumbnail img")
            image_url = get_high_res_image_url(img_tag.get('src') if img_tag else None)
            excerpt_tag = post.select_one(".elementor-post__excerpt p")
            all_articles.append({
                "title": a_tag.text.strip(),
                "link": a_tag['href'],
                "imageUrl": image_url,
                "excerpt": excerpt_tag.text.strip() if excerpt_tag else "Không có mô tả.",
            })
        page += 1
        if page <= max_pages: time.sleep(1)

    unique_articles = list({article['link']: article for article in all_articles}.values())
    print(f"✅ Cào xong! Tìm thấy {len(unique_articles)} bài viết độc nhất.")
    return [{"category": category_name, "articles": unique_articles}] if unique_articles else []

def scrape_clubs():
    """Cào dữ liệu các CLB, Đội, Nhóm từ trang /clubs một cách ổn định."""
    url = f"{BASE_URL}/clubs/"
    print(f"🚀 Bắt đầu cào dữ liệu từ {url}...")
    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"❌ Lỗi khi cào {url}: {e}", file=sys.stderr)
        return []

    soup = BeautifulSoup(response.text, "lxml")
    page_container = soup.select_one(".elementor-1048")
    if not page_container:
        return []

    category_map = {}
    current_category = None

    for section in page_container.select("section.elementor-top-section"):
        # Nếu section này là một tiêu đề, đặt nó làm danh mục hiện tại
        title_tag = section.select_one("h2.elementor-heading-title")
        if title_tag and title_tag.text.strip():
            current_category = title_tag.text.strip()
            if current_category not in category_map:
                category_map[current_category] = []
            continue

        # Nếu section này chứa bài viết và đã có danh mục, thêm bài viết vào đó
        if current_category:
            posts = section.select("article.ecs-post-loop, article.elementor-post")
            for post in posts:
                button = post.select_one("a.elementor-button")
                if not button or not button.get('href'): continue

                title = button.text.strip()
                link = button['href']
                img_tag = post.select_one(".elementor-widget-theme-post-featured-image img")
                image_url = get_high_res_image_url(img_tag.get('src') if img_tag else None)
                
                category_map[current_category].append({
                    "title": title, 
                    "link": link, 
                    "imageUrl": image_url, 
                    "excerpt": ""
                })

    # Chuyển đổi map thành list output cuối cùng
    final_data = []
    for name, articles in category_map.items():
        if articles:
            unique_articles = list({article['link']: article for article in articles}.values())
            final_data.append({"category": name, "articles": unique_articles})

    print(f"✅ Cào xong /clubs! Tìm thấy {len(final_data)} danh mục.")
    return final_data


def scrape_chuong_trinh_chien_dich_du_an():
    """Cào dữ liệu từ trang /chuong-trinh-chien-dich-du-an."""
    url = f"{BASE_URL}/chuong-trinh-chien-dich-du-an/"
    print(f"🚀 Bắt đầu cào dữ liệu từ {url}...")
    data = _scrape_generic_page(url, ".elementor-1165")
    print(f"✅ Cào xong {url}! Tìm thấy {len(data)} danh mục.")
    return data

def scrape_skills():
    """Cào dữ liệu từ trang /skills."""
    url = f"{BASE_URL}/skills/"
    print(f"🚀 Bắt đầu cào dữ liệu từ {url}...")
    data = _scrape_generic_page(url, ".elementor-1181")
    print(f"✅ Cào xong {url}! Tìm thấy {len(data)} danh mục.")
    return data

def scrape_ideas():
    """Cào dữ liệu từ trang /ideas."""
    url = f"{BASE_URL}/ideas/"
    print(f"🚀 Bắt đầu cào dữ liệu từ {url}...")
    data = _scrape_generic_page(url, ".elementor-1242")
    print(f"✅ Cào xong {url}! Tìm thấy {len(data)} danh mục.")
    return data

def scrape_article_with_requests(article_url: str):
    """Lấy nội dung chi tiết của một bài viết."""
    print(f"🚀 Sử dụng `requests` để lấy dữ liệu bài viết: {article_url}")
    try:
        response = requests.get(article_url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")
        content_div = soup.select_one(".elementor-widget-theme-post-content .elementor-widget-container")
        if not content_div:
            print("❌ Không tìm thấy thẻ div chứa nội dung.", file=sys.stderr)
            return None
        print("✅ Lấy nội dung bài viết thành công!")
        return str(content_div)
    except requests.RequestException as e:
        print(f"❌ Lỗi khi dùng requests cho bài viết: {e}", file=sys.stderr)
        return None