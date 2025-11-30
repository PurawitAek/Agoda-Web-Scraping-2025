import re, json, csv, time,logging
import requests
from lxml import html

from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException
from bs4 import BeautifulSoup


# ---------- SETUP INPUTS----------
# For strings, use the 'or' pattern for defaults
start_date = input("Enter Check In Date(YYYY-MM-DD): ") or "2025-12-23"
end_date = input("Enter Check Out Date(YYYY-MM-DD): ") or "2025-12-30"
location_search = input("Enter Location: ") or "Bangkok"

# For integers, use try-except to handle invalid inputs
try:
    target_adults = int(input("Enter Number of Adults: ")) # e.g. 2
except ValueError:
    target_adults = 2 # Sets default if input is empty ("") or invalid ("abc")
    
try:
    target_childs = int(input("Enter Number of Childs: ")) # e.g. 2
except ValueError:
    target_childs = 0 # Sets default if input is empty or invalid
    
try:
    target_rooms = int(input("Enter Number of Rooms: ")) # e.g. 1
except ValueError:
    target_rooms = 1 # Sets default if input is empty or invalid

print("--- INPUTS SUMMARY---")
print(f"Location: {location_search}")
print(f"Check-in: {start_date}")
print(f"Check-out: {end_date}")
print(f"Adults: {target_adults}")
print(f"Children: {target_childs}")
print(f"Rooms: {target_rooms}")

path_to_chrome_driver = "/Users/iaek/Desktop/CHULA/CU3.1/Data_Acquisition/WebScraperClass/Project_Final/Agoda-Web-Scraping-2025/chromedriver"
chrome_service = Service(executable_path=path_to_chrome_driver)

chrome_options = Options()
chrome_options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
# chrome_options.add_argument("--headless=new")  # ถ้าต้องการรันแบบ headless ค่อยเปิด

driver = webdriver.Chrome(service=chrome_service, options=chrome_options)
wait = WebDriverWait(driver, 20)

url = "https://www.agoda.com/?cid=1919571&tag=0002d4f2-d0b3-4684-9a42-27ea2c122dab"
driver.get(url)

# ---------- FUNCTIONS ----------

def click_if_present(selectors, timeout=3):
    """หา element ตามลำดับ selector แล้วคลิกตัวแรกที่เจอ"""
    for css in selectors:
        try:
            el = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((By.CSS_SELECTOR, css)))
            driver.execute_script("arguments[0].click();", el)
            return True
        except Exception:
            pass
    return False


def dismiss_overlays(timeout=3):
    """ปิด/ซ่อน overlay ที่อาจบังการคลิก (floater/cookie/promo)"""
    close_selectors = [
        "[data-testid='floater-container'] [aria-label*='Close']",
        "[data-testid='floater-container'] [data-testid*='close']",
        "[data-testid='cookie-accept']",
        "button[aria-label='Accept']",
        "button[aria-label*='ยอมรับ']",
        "[data-testid*='close']",
        "button[aria-label*='Close']",
    ]
    for css in close_selectors:
        try:
            btn = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((By.CSS_SELECTOR, css)))
            driver.execute_script("arguments[0].click();", btn)
        except Exception:
            pass
    # fallback: ซ่อน overlay โดยตรง
    try:
        overlays = driver.find_elements(By.CSS_SELECTOR, "[data-testid='floater-container'], .drone-po-vis")
        for ov in overlays:
            driver.execute_script("arguments[0].style.display='none';", ov)
    except Exception:
        pass
    # รอจน overlay หายไป
    try:
        WebDriverWait(driver, timeout).until(
            EC.invisibility_of_element_located((By.CSS_SELECTOR, "[data-testid='floater-container']"))
        )
    except TimeoutException:
        pass

def safe_click(css):
    """คลิก element แบบ scroll + JS fallback; ถ้าถูกบังจะพยายามปิด overlay แล้วคลิกใหม่"""
    elem = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, css)))
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", elem)
    try:
        elem.click()
    except ElementClickInterceptedException:
        dismiss_overlays()
        driver.execute_script("arguments[0].click();", elem)
    except Exception:
        driver.execute_script("arguments[0].click();", elem)

def _aria_label_variants(date_str: str):
    """คืนข้อความวันที่ที่น่าจะอยู่ใน aria-label ของปุ่มวัน (ภาษาอังกฤษ)"""
    d = datetime.strptime(date_str, "%Y-%m-%d")
    # บน macOS/Linux ใช้ %-d ได้; ถ้าไม่รองรับจะตกไปใช้ %d แล้วลบ 0 เอง
    try:
        full = d.strftime("%a %b %-d %Y")
        short = d.strftime("%b %-d %Y")
    except ValueError:
        full = d.strftime("%a %b %d %Y").replace(" 0", " ")
        short = d.strftime("%b %d %Y").replace(" 0", " ")
    return [full, short, f"{d.strftime('%b')} {d.day} {d.year}"]


def pick_date(date_str, max_next=14):    
    """
    เลือกวันบน Agoda calendar ให้แม่น:
      1) คลิก //div[@role='button' and descendant::span[@data-selenium-date='{date_str}'] and not(@aria-disabled='true')]
      2) ถ้าไม่พบ ใช้ aria-label contains (เช่น 'Dec 30 2025')
      3) ถ้าเดือนยังไม่ถึง → กด next แล้ววน (<= max_next)
    """
    next_btns = [
        "[aria-label*='Next']",
        "[aria-label*='ถัดไป']",
        "[data-selenium='calendarNext']",
        ".DayPicker-NavButton--next",
    ]

    def _try_click_once():
        # A) data-selenium-date (เสถียรสุด)
        xp = f"//div[@role='button' and descendant::span[@data-selenium-date='{date_str}'] and not(@aria-disabled='true')]"
        elems = driver.find_elements(By.XPATH, xp)
        visible = [e for e in elems if e.is_displayed()]
        if visible:
            btn = visible[0]
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
            try:
                btn.click()
            except Exception:
                driver.execute_script("arguments[0].click();", btn)
            return True

        # B) fallback: aria-label contains
        for frag in _aria_label_variants(date_str):
            xp2 = f"//div[@role='button' and contains(@aria-label, '{frag}') and not(@aria-disabled='true')]"
            elems2 = driver.find_elements(By.XPATH, xp2)
            visible2 = [e for e in elems2 if e.is_displayed()]
            if visible2:
                btn = visible2[0]
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                try:
                    btn.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", btn)
                return True
        return False

    for _ in range(max_next + 1):
        if _try_click_once():
            return True
        # ยังไม่เจอ → next month แล้วลองใหม่
        if not click_if_present(next_btns, timeout=2):
            break

    raise TimeoutException(f"Cannot select date {date_str}")

def read_box_date(kind="checkIn"):
    """อ่านค่าวันที่จากกล่อง checkIn/checkOut (ดูที่ data-date)"""
    box = driver.find_element(By.CSS_SELECTOR, f"div[data-selenium='{kind}Box']")
    return box.get_attribute("data-date")

def set_occupancy(item_type, target_count):
    """
    ปรับค่า Adults หรือ Rooms ให้ตรงตามเป้าหมาย
    item_type: 'adult' หรือ 'room'
    target_count: ตัวเลข (int) ที่ต้องการ
    """
    print(f"Setting {item_type}s to {target_count}...")
    
    # Selector หลักสำหรับอ่านค่า
    value_selector = f"[data-selenium*='desktop-occ-{item_type}-value']"
    
    # Selectors สำหรับปุ่ม (อ้างอิงจาก screenshot และโครงสร้าง Agoda)
    if item_type == "adult":
        add_selectors = ["[aria-label*='Add Adults']", "[data-selenium-plus='occupancy-selector']"]
        remove_selectors = ["[aria-label*='Remove Adults']", "[data-selenium-minus='occupancy-selector']"]
    else: # room
        add_selectors = ["[aria-label*='Add Rooms']", "[data-selenium-plus='room-selector']"]
        remove_selectors = ["[aria-label*='Remove Rooms']", "[data-selenium-minus='room-selector']"]

    # วนลูปพยายามปรับค่า (สูงสุด 15 ครั้ง)
    for _ in range(15):
        try:
            # อ่านค่าปัจจุบัน
            current_val_elem = driver.find_element(By.CSS_SELECTOR, value_selector)
            current_count = int(current_val_elem.get_attribute("data-element-value") or current_val_elem.text.strip())
            
            if current_count == target_count:
                print(f"✅ {item_type.capitalize()} count is correct ({current_count}).")
                return True # สำเร็จ
            
            # ถ้าค่าน้อยไป -> กดบวก
            elif current_count < target_count:
                if not click_if_present(add_selectors, timeout=2):
                    print(f"Cannot find ADD button for {item_type}")
                    return False
            
            # ถ้าค่ามากไป -> กดลบ
            elif current_count > target_count:
                if not click_if_present(remove_selectors, timeout=2):
                    print(f"Cannot find REMOVE button for {item_type}")
                    return False
            
            time.sleep(0.7) # รอ UI update หลังคลิก
            
        except Exception as e:
            print(f"Error reading/adjusting {item_type} count: {e}. Retrying...")
            time.sleep(0.5)

    print(f"❌ Failed to set {item_type} count to {target_count} after multiple attempts.")
    return False


# ---------- MAIN FLOW ----------
# 0) ปิด cookie/overlay เบื้องต้น
click_if_present([
    "[data-testid='cookie-accept']",
    "button[aria-label='Accept']",
    "button[aria-label*='ยอมรับ']",
    ".CookieBanner__accept"
], timeout=5)
time.sleep(0.5)

# 1) ใส่ปลายทาง + เลือก suggestion แรก

dest = wait.until(EC.element_to_be_clickable((By.ID, "textInput")))
dest.clear(); dest.send_keys(location_search)
click_if_present([
    "[data-selenium='suggestItem']",
    "[data-testid='destination-suggestion']",
    "li[role='option']"
], timeout=5)

# 2) เลือกวันที่ (มี verify)

print("Starting date selection...")
dismiss_overlays()
safe_click('div[data-selenium="checkInBox"]') # คลิกเปิด calendar ครั้งเดียว
time.sleep(0.5) # รอ animation

# 2.1) เลือก start_date
try:
    pick_date(start_date)
    time.sleep(1.0) # รอ UI update (สำคัญ)
    
    # 2.2) เลือก end_date ต่อเลย (calendar ยังเปิดอยู่)
    pick_date(end_date)
    time.sleep(1.0) # รอ UI update
except Exception as e:
    print(f"Error during date picking: {e}")

# 2.3) ตรวจสอบค่า
# Calendar อาจจะปิดเองแล้ว หรือยังค้างอยู่
# ลองคลิก body เพื่อปิด (ถ้ามันยังไม่ปิด)
try:
    driver.find_element(By.TAG_NAME, "body").click()
except Exception:
    pass # ไม่เป็นไรถ้าคลิกไม่ได้
time.sleep(0.5)

# 2.4) Verify ทั้งคู่หลัง calendar ปิดแล้ว
final_check_in = read_box_date("checkIn")
final_check_out = read_box_date("checkOut")

# ถ้าค่าไม่ตรง, ลองใหม่ทั้งหมดแค่ครั้งเดียว (Retry logic)
if final_check_in != start_date or final_check_out != end_date:
    print(f"Date selection failed (Got In: {final_check_in}, Out: {final_check_out}). Retrying...")
    dismiss_overlays()
    safe_click('div[data-selenium="checkInBox"]') # เปิดใหม่
    time.sleep(0.5)
    pick_date(start_date)
    time.sleep(1.0)
    pick_date(end_date) # เลือกคู่
    time.sleep(1.0)
    try:
        driver.find_element(By.TAG_NAME, "body").click() # ปิด
    except Exception:
        pass

print("Final check-in set to:", read_box_date("checkIn"))
print("Final check-out set to:", read_box_date("checkOut"))

# 2.5) เลือกจำนวนคนและห้อง
print("Starting occupancy selection...")
dismiss_overlays()

# คลิกเปิดกล่อง Occupancy
try:
    # ลองคลิก selector หลัก
    safe_click("[data-selenium='occupancyBox']")
    time.sleep(1.2) # รอ animation
except Exception as e:
    print(f"Could not open occupancy box with main selector: {e}. Trying alternatives...")
    # ลอง selector สำรอง
    if not click_if_present(["[data-testid='occupancy-box']", "div[data-element-name*='occupancy']"], timeout=3):
        print("❌ Failed to open occupancy box. Skipping adjustment.")
    time.sleep(1.2)

# เรียกใช้ Helper เพื่อปรับค่า
try:
    set_occupancy("adult", target_adults)
    time.sleep(0.5)
    set_occupancy("room", target_rooms)
    time.sleep(0.5)
    
    # ปิดกล่อง (บางทีมีปุ่ม Done บางทีก็ไม่มี)
    if not click_if_present(["[data-selenium='ok-button']", "[data-testid='occupancy-done-btn']"], timeout=2):
        driver.find_element(By.TAG_NAME, "body").click() # ถ้าไม่มีปุ่ม Done ให้คลิกที่ body
        print("Occupancy dropdown closed.")
    
except Exception as e:
    print(f"Error during occupancy adjustment: {e}")
    
time.sleep(0.5)

# 3) กดค้นหา
dismiss_overlays()
click_if_present([
    "[data-selenium='searchButton']",
    "[data-testid='search-button']",
    "button[type='submit']"
], timeout=5)

time.sleep(5) # รอ page load เบื้องต้น

if len(driver.window_handles) > 1:
    driver.switch_to.window(driver.window_handles[-1]) # Switch to the newest tab
    print("Switched to new search results tab.")

#------- WAIT FOR THE NEW PAGE TO LOAD -------
print("⏳ Waiting for search results to load...")
try:
    # Wait up to 30 seconds for the Hotel Card element to appear
    # We use the same selector that you use for scraping later
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '[data-selenium="hotel-item"]')))
    print("✅ Search results loaded! Starting scraper...")
except TimeoutException:
    print("❌ Error: Search results did not load within 30 seconds.")
    # Debug: Save a screenshot to see what happened
    driver.save_screenshot("search_error.png") 
    driver.quit()
    exit()


# === SCROLL & COLLECT LINKS ===
SCROLL_PAUSE_TIME = 2.0
hotel_links = set()
scroll_position = 0

# Limit how many you want to collect (optional)
MAX_LINKS = 50 

while len(hotel_links) < MAX_LINKS:
    # Scroll down
    driver.execute_script(f"window.scrollTo(0, {scroll_position});")
    time.sleep(SCROLL_PAUSE_TIME) # Wait for cards to render

    soup = BeautifulSoup(driver.page_source, "lxml")
    
    # Select all property cards
    cards = soup.select('[data-selenium="hotel-item"]')
    
    # If no cards found (rare if we passed the wait above), just continue scrolling
    if not cards:
        print("⚠️ No cards visible yet, scrolling more...")

    current_batch_count = 0
    for card in cards:
        link_elem = card.select_one('a.PropertyCard__Link')
        if not link_elem:
            link_elem = card.select_one('a[href]')
            
        if link_elem and link_elem.has_attr('href'):
            full_url = "https://www.agoda.com" + link_elem['href']
            if full_url not in hotel_links:
                hotel_links.add(full_url)
                current_batch_count += 1

    logging.info(f"Collected {len(hotel_links)} links so far...")

    # Calculate new scroll position
    scroll_position += 1000 
    
    # Check if we hit the bottom
    new_height = driver.execute_script("return document.body.scrollHeight")
    
    # Logic to break if we can't scroll anymore
    if scroll_position > new_height:
        # Try one last small scroll to trigger lazy loading
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)
        final_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == final_height:
            logging.info("✅ Reached end of page.")
            break
        else:
            new_height = final_height

driver.quit()

# === SAVE LINKS ===
with open("hotel_links.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["url"])
    for link in hotel_links:
        writer.writerow([link])

logging.info("✅ Step 1 Done: Links saved to hotel_links.csv")

