import csv, time, logging
from datetime import datetime
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException

# ==========================================
# 1. SETUP INPUTS
# ==========================================
start_date = input("Enter Check In Date(YYYY-MM-DD): ") or "2025-12-23"
end_date = input("Enter Check Out Date(YYYY-MM-DD): ") or "2025-12-30"
location_search = input("Enter Location: ") or "Bangkok"

try:
    target_adults = int(input("Enter Number of Adults: ")) 
except ValueError:
    target_adults = 2 
    
try:
    target_childs = int(input("Enter Number of Childs: ")) 
except ValueError:
    target_childs = 0 
    
try:
    target_rooms = int(input("Enter Number of Rooms: ")) 
except ValueError:
    target_rooms = 1 

print("\n--- INPUTS SUMMARY ---")
print(f"Location: {location_search}")
print(f"Check-in: {start_date}")
print(f"Check-out: {end_date}")
print(f"Guests: {target_adults} Adults, {target_childs} Children")

# ==========================================
# 2. DRIVER SETUP
# ==========================================
# ⚠️ UPDATE PATH
path_to_chrome_driver = "/Users/iaek/Desktop/CHULA/CU3.1/Data_Acquisition/WebScraperClass/Project_Final/Agoda-Web-Scraping-2025/chromedriver"
chrome_service = Service(executable_path=path_to_chrome_driver)

chrome_options = Options()
chrome_options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")

driver = webdriver.Chrome(service=chrome_service, options=chrome_options)
wait = WebDriverWait(driver, 20)

# Open Homepage
driver.get("https://www.agoda.com/?cid=1919571")

# ==========================================
# 3. HELPER FUNCTIONS
# ==========================================
def click_if_present(selectors, timeout=3):
    for css in selectors:
        try:
            el = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((By.CSS_SELECTOR, css)))
            driver.execute_script("arguments[0].click();", el)
            return True
        except Exception:
            pass
    return False

def dismiss_overlays():
    """Closes popups/overlays"""
    close_selectors = [
        "[data-testid='floater-container'] [aria-label*='Close']",
        "button[aria-label='Close']",
        "[data-testid='cookie-accept']",
        "button[aria-label*='Accept']"
    ]
    click_if_present(close_selectors, timeout=2)

def safe_click(css):
    dismiss_overlays()
    try:
        elem = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, css)))
        driver.execute_script("arguments[0].click();", elem)
    except Exception:
        print(f"⚠️ Could not click {css}")

# ==========================================
# 4. EXECUTE UI ACTIONS
# ==========================================

# --- A. Set Location ---
try:
    print("📍 Setting Location...")
    dest = wait.until(EC.element_to_be_clickable((By.ID, "textInput")))
    dest.clear()
    dest.send_keys(location_search)
    time.sleep(2) # Wait for suggestions
    click_if_present(["[data-selenium='suggestItem']", "li[role='option']"], timeout=5)
except Exception as e:
    print(f"⚠️ Error setting location: {e}")

# --- B. Set Dates (Simplified Logic) ---
# We assume manual date selection is complex, so we try to open calendar 
# and rely on user or simple logic. If this fails, consider the URL method.
print("📅 Opening Calendar...")
safe_click('div[data-selenium="checkInBox"]')
time.sleep(1)

try:
    # Attempt to click exact date in calendar
    start_xpath = f"//span[@data-selenium-date='{start_date}']"
    end_xpath = f"//span[@data-selenium-date='{end_date}']"
    
    driver.find_element(By.XPATH, start_xpath).click()
    time.sleep(0.5)
    driver.find_element(By.XPATH, end_xpath).click()
except Exception:
    print("⚠️ Could not click dates automatically. Please select manually if needed.")

# Close calendar if still open
try:
    driver.find_element(By.TAG_NAME, "body").click()
except: pass

# --- C. Set Occupancy ---
print("👥 Setting Occupancy...")
safe_click("[data-selenium='occupancyBox']")
time.sleep(1)

# Just setting adults for brevity (Logic from your previous code)
try:
    curr_val = driver.find_element(By.CSS_SELECTOR, "[data-selenium*='desktop-occ-adult-value']").text
    if int(curr_val) < target_adults:
        for _ in range(target_adults - int(curr_val)):
            click_if_present(["[data-selenium-plus='occupancy-selector']"])
except: pass

# Click anywhere to close occupancy box
driver.find_element(By.TAG_NAME, "body").click()

# --- D. CLICK SEARCH ---
print("🔍 Clicking Search...")
dismiss_overlays()
clicked = click_if_present([
    "[data-element-name='search-button']",
    "button[type='button']"
], timeout=5)

if not clicked:
    print("❌ Failed to click search button.")
    driver.quit()
    exit()

# ==========================================
# 5. ✅ CRITICAL STEP: WAIT FOR RESULTS PAGE
# ==========================================
print("⏳ Waiting for search results to load...")

# 1. Switch tab if a new one opened
time.sleep(3)
if len(driver.window_handles) > 1:
    driver.switch_to.window(driver.window_handles[-1])
    print("🔀 Switched to new results tab.")

# 2. Wait for the Hotel Cards to appear
try:
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '[data-selenium="hotel-item"]')))
    print("✅ Search results loaded! Starting scraper...")
except TimeoutException:
    print("❌ Error: Search results did not load. The search click might have failed.")
    driver.quit()
    exit()

# ==========================================
# 6. SCROLL & COLLECT LINKS (Current Page)
# ==========================================
SCROLL_PAUSE_TIME = 2.5
hotel_links = set()
scroll_position = 0
MAX_LINKS = 100

while len(hotel_links) < MAX_LINKS:
    driver.execute_script(f"window.scrollTo(0, {scroll_position});")
    time.sleep(SCROLL_PAUSE_TIME) 

    soup = BeautifulSoup(driver.page_source, "lxml")
    cards = soup.select('[data-selenium="hotel-item"]')
    
    if not cards:
        print("⚠️ No cards visible yet, scrolling more...")

    for card in cards:
        link_elem = card.select_one('a.PropertyCard__Link')
        if not link_elem:
            link_elem = card.select_one('a[href]')
            
        if link_elem and link_elem.has_attr('href'):
            full_url = "https://www.agoda.com" + link_elem['href']
            if full_url not in hotel_links:
                hotel_links.add(full_url)

    print(f"Collected {len(hotel_links)} links so far...")

    scroll_position += 1000 
    new_height = driver.execute_script("return document.body.scrollHeight")
    
    if scroll_position > new_height:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)
        final_height = driver.execute_script("return document.body.scrollHeight")
        
        if new_height == final_height:
            print("✅ Reached end of page.")
            break
        else:
            new_height = final_height

driver.quit()

# ==========================================
# 7. SAVE TO CSV
# ==========================================
with open("hotel_links.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["url"])
    for link in hotel_links:
        writer.writerow([link])

print(f"✅ Step 1 Done: {len(hotel_links)} links saved to hotel_links.csv")