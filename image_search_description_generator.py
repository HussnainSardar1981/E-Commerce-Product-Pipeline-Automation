import os
import time
import json
import random
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from openai import OpenAI

client = OpenAI(api_key="Your API Key")  # replace with your actual key

TARGET_FOLDER = r"downloads\Chanel_Wallet"
PRODUCT_CATEGORY = "Wallet"
BRAND_NAME = "Chanel"
BRAND_DOMAINS = ["chanel.com"]

BAD_DOMAINS = ['pinterest.', 'reddit.', 'tumblr.', 'quora.', 'youtube.', 'google.', 'wikipedia.',
               'facebook.', 'instagram.', 'twitter.', 'tiktok.', '.kr', '.cn', '.jp', '.ru',
               'vestiairecollective.', 'therealreal.', 'depop.', 'buyma.', 'louisvuitton.com']

TOP_DOMAINS = ["farfetch", "nordstrom", "saksfifthavenue", "neimanmarcus", "bloomingdales", "ssense", "mytheresa", "net-a-porter", "ebay"]

def setup_driver():
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def handle_google_consent(driver):
    try:
        btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable(
            (By.XPATH, "//button//div[contains(text(), 'Accept all') or contains(text(), 'I agree')]")))
        btn.click()
        time.sleep(random.uniform(1, 2))
    except:
        pass

def close_brand_popups(driver):
    try:
        buttons = driver.find_elements(By.XPATH, "//button[contains(text(), 'OK') or contains(text(), 'Accept') or contains(text(), 'Agree') or contains(text(), 'Continue') or contains(text(), 'Stay') or contains(text(), 'Switch') or contains(@aria-label, 'Close') or text()='×' or contains(text(), 'Dismiss')]")
        for btn in buttons:
            try:
                btn.click()
                time.sleep(1)
            except:
                pass
    except:
        pass

def score_link(href):
    score = 0
    parsed = urlparse(href)
    netloc = parsed.netloc.lower()
    if any(brand_domain in netloc for brand_domain in BRAND_DOMAINS):
        score += 10
    if BRAND_NAME.lower() in href.lower():
        score += 3
    if any(domain in netloc for domain in TOP_DOMAINS):
        score += 5
    if netloc.endswith(('.com', '.co.uk', '.de', '.fr', '.it', '.net', '.eu')):
        score += 2
    if any(keyword in href.lower() for keyword in ["product", "buy", "shop"]):
        score += 1
    return score

def is_valid_text(text):
    if not text or len(text.strip()) < 5:
        return False
    lower_text = text.lower()
    if "just a moment" in lower_text:
        return False
    spam_keywords = ["paypal", "bonifico", "spedizione", "tracciabile", "contatti", "whatsapp", "imballaggio"]
    if any(spam in lower_text for spam in spam_keywords):
        return False
    return True

def contains_error_messages(text):
    lower_text = text.lower()
    error_keywords = ["this item does not exist", "we have detected unusual activity", "access denied", "this site can’t be reached", "this site cannot be reached", "page isn’t working"]
    return any(keyword in lower_text for keyword in error_keywords)

def collect_links(driver):
    WebDriverWait(driver, 10).until(lambda d: d.execute_script("return document.readyState") == "complete")
    time.sleep(random.uniform(2, 4))
    anchors = driver.find_elements(By.CSS_SELECTOR, "a[href]")
    scored = []
    for a in anchors:
        href = a.get_attribute("href")
        if href and href.startswith("http"):
            parsed = urlparse(href)
            netloc = parsed.netloc.lower()
            if not any(bad in netloc for bad in BAD_DOMAINS):
                score = score_link(href)
                if score > 0:
                    scored.append((score, href))
    scored.sort(reverse=True)
    return [h for _, h in scored]

def extract_product_details(driver):
    try:
        WebDriverWait(driver, 10).until(lambda x: x.execute_script("return document.readyState") == "complete")
        time.sleep(random.uniform(2, 3))

        page_title = driver.title or ""
        page_source = driver.page_source.lower()
        if contains_error_messages(page_title) or contains_error_messages(page_source):
            print("⚠️ Error message detected on page. Skipping.")
            return None, None

        scripts = driver.find_elements(By.XPATH, "//script[@type='application/ld+json']")
        for script in scripts:
            try:
                data = json.loads(script.get_attribute("innerHTML"))
                if isinstance(data, dict) and data.get("@type", "").lower() == "product":
                    name = data.get("name", "")
                    desc = data.get("description", "")
                    if contains_error_messages(name + desc):
                        return None, None
                    if is_valid_text(name) and is_valid_text(desc):
                        return name.strip(), desc.strip()
            except json.JSONDecodeError:
                continue

        try:
            title = driver.find_element(By.XPATH, "//meta[@property='og:title']").get_attribute("content")
        except:
            title = driver.title or "Unknown Product"
        try:
            desc = driver.find_element(By.XPATH, "//meta[@name='description']").get_attribute("content")
        except:
            desc = "No description available"

        if contains_error_messages(title + desc):
            return None, None

        extra_details = []
        possible_elements = driver.find_elements(By.XPATH, "//li | //p")
        for elem in possible_elements:
            text = elem.text.lower()
            if any(keyword in text for keyword in ["material", "composition", "dimension", "size", "measurement", "cm", "inch", "height", "width", "depth"]):
                clean_text = elem.text.strip()
                if clean_text and clean_text not in extra_details:
                    extra_details.append(clean_text)

        if extra_details:
            desc = desc + "\n" + "\n".join(extra_details)

        if is_valid_text(title) and is_valid_text(desc):
            return title.strip(), desc.strip()

    except Exception as e:
        print(f"⚠️ Error extracting product details: {e}")
    return None, None

def get_category_price(folder_name):
    name = folder_name.lower()
    if "bag" in name:
        return random.randint(300, 350)
    elif "wallet" in name:
        return random.randint(230, 250)
    elif any(keyword in name for keyword in ["shoe", "sneaker", "trainer", "slipper", "sandal"]):
        return random.randint(260, 290)
    elif "jewlery" in name or "jewellery" in name:
        return random.randint(155, 165)
    elif "belt" in name or "glass" in name:
        return random.randint(155, 165)
    elif "watch" in name:
        return random.randint(270, 290)
    else:
        return random.randint(250, 300)

def save_product_details(folder, brand, name, desc, price):
    details_file = os.path.join(folder, "product_details.txt")
    with open(details_file, "w", encoding="utf-8") as f:
        f.write(f"Brand: {brand}\n")
        f.write(f"Product Name: {name}\n")
        f.write(f"Description: {desc}\n")
        f.write(f"Price: ${price}\n")
    print(f"✔️ Saved details to {details_file}")
    return details_file

def improve_product_text(context_details, original_name, original_desc, category):
    prompt = (
        f"You are an expert fashion product copywriter.\n\n"
        f"Rewrite the product name and description for a high-end online store, using simple, sophisticated, and inviting language.\n\n"
        f"Guidelines:\n"
        f"- Create a short, catchy product name (max 7 words).\n"
        f"- Write a soft, smooth, story-like description in 3 to 4 lines.\n"
        f"- Mention material or dimensions if available, in a natural way.\n"
        f"- Do not mention color.\n"
        f"- Highlight comfort, style, or daily use, so it feels relatable.\n"
        f"- Do not mention store names, disclaimers, or brand name in the name.\n"
        f"- Do not invent new details.\n\n"
        f"Context Details:\n{context_details}\n\n"
        f"Original Product Name: {original_name}\n"
        f"Original Description: {original_desc}\n\n"
        f"Return the new product name first, then the new description, separated by a line break.\n"
    )
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a professional luxury product copywriter."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )
        improved_text = response.choices[0].message.content.strip()
        lines = improved_text.split("\n", 1)
        if len(lines) >= 2:
            return lines[0].strip(), lines[1].strip()
        else:
            return original_name, original_desc
    except Exception as e:
        print(f"⚠️ OpenAI error: {e}")
        return original_name, original_desc

def process_single_folder(folder_path):
    driver = setup_driver()
    try:
        print(f"Processing folder: {folder_path}")
        albums = os.listdir(folder_path)
        for album in albums:
            album_path = os.path.join(folder_path, album)
            if not os.path.isdir(album_path):
                continue

            images = [f for f in os.listdir(album_path) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
            if not images:
                continue

            best_name, best_desc = None, None

            for image_path in images[:6]:  # Upload first 6 images
                full_image_path = os.path.join(album_path, image_path)
                driver.get("https://www.google.com/imghp?hl=en")
                handle_google_consent(driver)

                camera_icon = WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "div[aria-label='Search by image']")))
                camera_icon.click()
                upload_input = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']")))
                upload_input.send_keys(os.path.abspath(full_image_path))

                WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[href]")))

                links = collect_links(driver)
                for link in links:
                    driver.execute_script("window.open(arguments[0]);", link)
                    WebDriverWait(driver, 10).until(lambda d: len(d.window_handles) > 1)

                    new_handle = [h for h in driver.window_handles if h != driver.current_window_handle][0]
                    driver.switch_to.window(new_handle)

                    close_brand_popups(driver)
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(random.uniform(2, 4))

                    name, desc = extract_product_details(driver)
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])

                    if name and desc:
                        best_name, best_desc = name, desc
                        break  # Stop if found valid details

                if best_name and best_desc:
                    break  # Stop processing more images if we already have best

            price = get_category_price(os.path.basename(folder_path))

            if not best_name:
                best_name = "Unknown Product"
            if not best_desc:
                best_desc = "No valid description found"

            txt_file = save_product_details(album_path, BRAND_NAME, best_name, best_desc, price)

            with open(txt_file, "r", encoding="utf-8") as f:
                content = f.read()

            improved_name, improved_desc = improve_product_text(content, best_name, best_desc, PRODUCT_CATEGORY)

            with open(txt_file, "w", encoding="utf-8") as f:
                f.write(f"Brand: {BRAND_NAME}\n")
                f.write(f"Product Name: {improved_name}\n")
                f.write(f"Description: {improved_desc}\n")
                f.write(f"Price: ${price}\n")

            print(f"✅ Improved and updated: {txt_file}")

            time.sleep(random.uniform(2, 4))
    finally:
        driver.quit()
        print("\n✅ All albums processed.")

if __name__ == "__main__":
    process_single_folder(TARGET_FOLDER)
