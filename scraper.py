import os
import time
import re
import requests
import hashlib
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Configure logging
import logging
logging.basicConfig(filename='scraper.log', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

# ========== CONFIG ==========
BASE_URL = "https://luxurysotre999.x.yupoo.com" # Chinese Website URL
TARGET_CATEGORIES = [
   "/categories/2994023",  # Prada Bags
   #  "/categories/3396640"   # Loro Piana Shoes
]
BASE_DOWNLOAD_DIR = "downloads/LouisVuitton_Bags"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Referer": "https://luxurysotre999.x.yupoo.com/"
}
# ============================

def clean_name(name):
    """Sanitize names for filesystem compatibility."""
    return re.sub(r'[\\\\/*?:\"<>|]', "_", name)

def setup_driver():
    """Initialize Selenium WebDriver with Chrome options."""
    options = Options()
    options.add_argument("--start-maximized")
    # options.add_argument("--headless")  # Uncomment to run in headless mode
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-extensions")
    logging.info("Starting ChromeDriver using webdriver-manager")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

def get_category(driver, category_url):
    """Get the target category based on the provided URL and extract its name."""
    logging.info(f"Collecting category from {BASE_URL}{category_url}")
    try:
        full_url = f"{BASE_URL}{category_url}" if not category_url.startswith("http") else category_url
        driver.get(full_url)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, f"//a[@href='{category_url}']")))
        category_element = driver.find_element(By.XPATH, f"//a[@href='{category_url}']")
        category_name = category_element.text.strip() or "Unknown_Category"  # Fallback name
        return {"name": clean_name(category_name), "url": full_url}
    except Exception as e:
        logging.error(f"Failed to collect category {category_url}: {e}")
        print(f"[!] Failed to collect category {category_url}: {e}")
        return None

def scroll_to_bottom(driver):
    """Scroll to the bottom of the page to load all content."""
    try:
        last_height = driver.execute_script("return document.body.scrollHeight")
        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
    except Exception as e:
        logging.error(f"Failed to scroll: {e}")

def get_album_links(driver):
    """Collect album links from a category page without pagination."""
    logging.info("Collecting album links from current page")
    all_albums = []
    try:
        scroll_to_bottom(driver)
        WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'a.album__main')))
        albums = driver.find_elements(By.CSS_SELECTOR, 'a.album__main')
        for a in albums:
            href = a.get_attribute("href")
            title = a.get_attribute("title") or "Untitled_Album"
            if href:
                if not href.startswith("http"):
                    href = BASE_URL.split("/categories")[0] + href
                all_albums.append({"title": clean_name(title), "url": href})

        logging.info(f"Found {len(all_albums)} albums on current page")
        print(f"[✓] Found {len(all_albums)} albums on current page.\n")
        return all_albums
    except Exception as e:
        logging.error(f"Failed to collect album links: {e}")
        print(f"[!] Failed to collect album links: {e}")
        return []

def get_image_links(driver):
    """Extract image URLs from an album page using data-origin-src."""
    logging.info("Collecting image links")
    try:
        scroll_to_bottom(driver)
        WebDriverWait(driver, 20).until(EC.presence_of_all_elements_located(
            (By.CSS_SELECTOR, 'img.autocover.image__img.image__portrait[data-type="photo"][data-origin-src]')))
        image_elements = driver.find_elements(By.CSS_SELECTOR, 
            'img.autocover.image__img.image__portrait[data-type="photo"][data-origin-src]')
        print(f"Found {len(image_elements)} images on album page")
        full_image_urls = []

        for i, img in enumerate(image_elements):
            try:
                fallback_url = driver.execute_script("return arguments[0].getAttribute('data-origin-src');", img)
                if fallback_url:
                    if fallback_url.startswith("//"):
                        fallback_url = "https:" + fallback_url
                    full_image_urls.append(fallback_url)
                    print(f"Image {i+1}: {fallback_url}")
                else:
                    logging.warning(f"No data-origin-src for image {i+1}")
            except Exception as e:
                logging.error(f"Failed to process image {i+1}: {e}")
                continue

        logging.info(f"Found {len(full_image_urls)} unique image URLs")
        print(f"    ↳ Found {len(full_image_urls)} images")
        return full_image_urls
    except Exception as e:
        logging.error(f"Failed to collect image links: {e}")
        print(f"    [!] Failed to collect images: {e}")
        return []

def download_images(image_links, category_name, album, cookies):
    """Download up to the first 5 images to the specified directory with session cookies and retries."""
    save_path = os.path.join(BASE_DOWNLOAD_DIR, clean_name(category_name), clean_name(album))
    os.makedirs(save_path, exist_ok=True)
    s = requests.Session()
    for cookie in cookies:
        s.cookies.set(cookie['name'], cookie['value'])
    s.headers.update(HEADERS)

    # Limit to the first 5 images
    image_links = image_links[:5]
    print(f"    ↳ Processing up to {len(image_links)} images (limited to first 5)")

    for idx, img_url in enumerate(image_links):
        try:
            ext = img_url.split(".")[-1].split("?")[0][:4]
            hash_id = hashlib.md5(img_url.encode()).hexdigest()[:8]
            filename = f"image_{idx+1}_{hash_id}.{ext}"
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = s.get(img_url, timeout=30)
                    if response.status_code == 200:
                        with open(os.path.join(save_path, filename), "wb") as f:
                            f.write(response.content)
                        print(f"Downloaded {filename} to {save_path}")
                        logging.info(f"Downloaded {filename} to {save_path}")
                        break
                    else:
                        print(f"[!] Attempt {attempt+1} failed with status {response.status_code}")
                except Exception as e:
                    print(f"[!] Attempt {attempt+1} failed: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(5)
            else:
                print(f"[!] Failed to download {img_url} after {max_retries} attempts")
                logging.error(f"Failed to download {img_url} after {max_retries} attempts")
        except Exception as e:
            print(f"[!] Failed to download {img_url} - {e}")
            logging.error(f"Failed to download {img_url}: {e}")
        time.sleep(1)

def main():
    driver = setup_driver()
    try:
        for cat_idx, category_url in enumerate(TARGET_CATEGORIES, 1):
            print(f"\n[→] Processing category {cat_idx}/{len(TARGET_CATEGORIES)}: {category_url}")
            category = get_category(driver, category_url)
            if not category:
                print(f"[!] No valid category found for {category_url}. Skipping.")
                continue

            print(f"[✓] Found category: {category['name']}.\n")
            print(f"[→] Opening category: {category['name']}")
            driver.get(category['url'])
            time.sleep(3)
            print("[*] Scrolling and grabbing all product albums...")
            albums = get_album_links(driver)
            print(f"[✓] Found {len(albums)} albums.\n")

            for idx, album in enumerate(albums, 1):
                print(f"[{idx}/{len(albums)}] Visiting album: {album['url']}")
                try:
                    driver.get(album['url'])
                    time.sleep(2)
                    image_links = get_image_links(driver)
                    cookies = driver.get_cookies()
                    print(f"    ↳ Downloading up to 5 images...")
                    download_images(image_links, category['name'], album['title'], cookies)
                except Exception as e:
                    print(f"    [!] Failed album: {album['url']} - {e}")
                    logging.error(f"Failed album {album['url']}: {e}")

    except Exception as e:
        print(f"[!] Scraper failed: {e}")
        logging.error(f"Scraper failed: {e}")
    finally:
        driver.quit()
        print("\n[✓] Done downloading all categories and albums.")

if __name__ == "__main__":
    main()
