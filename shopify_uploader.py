import os
import time
import json

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Setup options for the browser
options = Options()
options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)

# Initialize the WebDriver
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
wait = WebDriverWait(driver, 20)


# Function to load the last processed album index to resume where it stopped
def load_last_processed(category_folder):
    try:
        with open(f"{category_folder}_last_processed.json", "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return {"album_index": 0}

# Function to save the last processed album index
def save_last_processed(category_folder, album_index):
    with open(f"{category_folder}_last_processed.json", "w") as file:
        json.dump({"album_index": album_index}, file)

# Function to parse product details from a text file
def parse_product_details(details_file_path):
    with open(details_file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    name, description, price, brand = "", "", "", ""
    for line in lines:
        if line.startswith("Product Name:"):
            name = line.split(":", 1)[1].strip()
        elif line.startswith("Description:"):
            description = line.split(":", 1)[1].strip()
        elif line.startswith("Price:"):
            price = line.split("$", 1)[1].strip()
        elif line.startswith("Brand:"):
            brand = line.split(":", 1)[1].strip()

    return name, description, price, brand


ROOT_FOLDER = r"downloads\LouisVuitton_Bags"  # Define your brand folder here

category_folder = ROOT_FOLDER.split("\\")[-1]  # Extract category name from ROOT_FOLDER path
last_processed_albums = load_last_processed(category_folder)

for album_index, album_folder in enumerate(os.listdir(ROOT_FOLDER)):
    if album_index < last_processed_albums["album_index"]:
        continue  # Skip already processed albums

    album_path = os.path.join(ROOT_FOLDER, album_folder)
    if not os.path.isdir(album_path):
        continue

    details_file = os.path.join(album_path, "product_details.txt")
    if not os.path.exists(details_file):
        print(f"❌ No product_details.txt in {album_path}, skipping.")
        continue

    title, desc, price, brand = parse_product_details(details_file)
    final_title = f"{brand} {title}"

    print(f"\n➡️ Starting upload for album: {album_folder} ({final_title})")  # Print album name and title

    driver.get("https://admin.shopify.com/store/4ydup3-zv/products/new")
    time.sleep(3)

    # Title
    title_input = wait.until(EC.presence_of_element_located((By.NAME, "title")))
    title_input.clear()
    title_input.send_keys(final_title)
    print("✅ Title set.")

    # Description
    iframe = wait.until(EC.presence_of_element_located((By.ID, "product-description_ifr")))
    driver.switch_to.frame(iframe)
    body = wait.until(EC.presence_of_element_located((By.ID, "tinymce")))
    body.clear()
    body.send_keys(desc)
    driver.switch_to.default_content()
    print("✅ Description set.")

    # Price
    price_input = wait.until(EC.presence_of_element_located((By.NAME, "price")))
    price_input.clear()
    price_input.send_keys(price)
    print("✅ Price set.")

    # --- Product type ---
    type_input = wait.until(EC.presence_of_element_located((By.NAME, "productType")))
    type_input.clear()
    prod_type = "Bags"  # Hardcoded as per your request
    type_input.send_keys(prod_type)  # Just inputting the product type without hitting enter
    print(f"🗂️ Product type set: {prod_type}")

    # --- Quantity ---
    qty_input = wait.until(EC.presence_of_element_located((By.NAME, "inventoryLevels[0]")))
    qty_input.clear()
    qty_input.send_keys("10")  # Set quantity to 10
    print("📦 Quantity set: 10")

    # --- Images ---
    image_paths = [
        os.path.abspath(os.path.join(album_path, img_file))
        for img_file in os.listdir(album_path)
        if img_file.lower().endswith((".jpg", ".jpeg", ".png"))
    ]
    upload_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']")))

    # Upload all images first
    for idx, img_path in enumerate(image_paths, start=1):
        upload_input.send_keys(img_path)
        print(f"🖼️ Uploaded image {idx}: {os.path.basename(img_path)}")
        time.sleep(4)  # Reduce the time delay to make the process faster

    print("✅ All images uploaded.")

    # --- Save ---
    save_button = WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, "//button[@type='submit' and text()='Save']")))
    save_button.click()
    print(f"💾 Saved product: {final_title}")

    save_last_processed(category_folder, album_index + 1)  # Save progress after each album
    time.sleep(7)

print("\n🎉 All products uploaded successfully!")


