import time, csv, logging, random
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# === CONFIG ===
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s')
path_to_chrome_driver = "/Users/iaek/Desktop/CHULA/CU3.1/Data_Acquisition/WebScraperClass/Project_Final/Agoda-Web-Scraping-2025/chromedriver"
chrome_service = Service(executable_path=path_to_chrome_driver)
chrome_options = Options()
chrome_options.add_argument("--headless=new")  # Headless is faster for this step เพราะเราไม่ต้อง render หน้าเว็บให้เห็น
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36")

driver = webdriver.Chrome(service=chrome_service, options=chrome_options)
wait = WebDriverWait(driver, 10)

# === READ LINKS ===
links = []
with open("hotel_links.csv", "r", encoding="utf-8") as f:
    reader = csv.reader(f)
    next(reader) # Skip header
    for row in reader:
        links.append(row[0])

logging.info(f"Loaded {len(links)} links to scrape.")

extracted_data = []

# === SCRAPE EACH PAGE ===
for i, link in enumerate(links):
    logging.info(f"[{i+1}/{len(links)}] Visiting: {link[:60]}...")
    
    try:
        driver.get(link)
        
        # Wait for the Hotel Name to appear (confirms page load)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '[data-selenium="hotel-header-name"]')))
        
        # Random sleep to behave like a human (Prevents blocking)
        time.sleep(random.uniform(2, 4))
        
        soup = BeautifulSoup(driver.page_source, "lxml")

        name = 'N/A'
        address = 'N/A'
        star = 'N/A'
        score = 'N/A'
        rating_word = 'N/A'
        review_count = 'N/A'

        # --- 1. Name ---
        name_elem = soup.select_one('[data-selenium="hotel-header-name"]')
        name = name_elem.get_text(strip=True) if name_elem else "N/A"

        # --- 2. Address ---
        addr_elem = soup.select_one('[data-selenium="hotel-address-map"]')
        address = addr_elem.get_text(strip=True) if addr_elem else "N/A"

        # --- 3. Star Rating ---
        star_elem = soup.select_one('[data-selenium="mosaic-hotel-rating"]>span') 
        star = star_elem.get_text(strip=True) if star_elem else "N/A"

        # --- 4. Review Score, Word, and Count ---
        # Define defaults
        

        # We use 'class*=' to find any class containing "ReviewScoreCompact__score"
        review_section = soup.select_one('div[class*="ReviewScoreCompact__score"]')
        
        if review_section:
            #Get Score and Word (inside the <h2> tag)
            header = review_section.select_one('h2')
            if header:
                spans = header.select('span')
                if len(spans) >= 1:
                    score = spans[0].get_text(strip=True) 
                if len(spans) >= 2:
                    rating_word = spans[1].get_text(strip=True) 

            # Get Review Count (inside data-testid="text")
            count_elem = review_section.select_one('[data-testid="text"]')
            if count_elem:
                raw_text = count_elem.get_text(strip=True) 
                # Split to get just the number
                review_count = raw_text.split()[0]        
        
        # # FALLBACK: If the compact view isn't there, try the standard header view
        # elif soup.select_one('[data-selenium="review-score-number"]'):
        #      score = soup.select_one('[data-selenium="review-score-number"]').get_text(strip=True)
        #      # (Add other fallbacks here if needed)

        # --- 5. Price ---
        price_elem = soup.select_one('[data-selenium="PriceDisplay"]')
        if not price_elem:
             price_elem = soup.select_one('.pd-price .price__num')
        
        price = price_elem.get_text(strip=True) if price_elem else "Sold Out/Check Dates"

        # --- 6. Description (Bonus!) ---
        desc_elem = soup.select_one('[data-selenium="hotel-description"]')
        description = desc_elem.get_text(strip=True)[:200] + "..." if desc_elem else "N/A"

        extracted_data.append([name, price, score, address, description, link])

    except Exception as e:
        logging.error(f"Failed to scrape {link}: {e}")

# === SAVE FINAL DATA ===
with open("agoda_final_details.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["name", "price", "score", "address", "description", "url"])
    writer.writerows(extracted_data)

driver.quit()
logging.info("✅ Done! Data saved to agoda_final_details.csv")