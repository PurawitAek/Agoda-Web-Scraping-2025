# Agoda-Web-Scraping-2025

This project is part of a **Data Acquisition** coursework designed to scrape hotel data from Agoda.com using **Python**, **Selenium**, and **BeautifulSoup**.

It utilizes a stable **two-step scraping architecture** to handle Agoda's dynamic content, infinite scrolling, and anti-bot mechanisms (like "Black Friday" layouts or dynamic class names).

## 🚀 Features

  * **Bypasses UI Obstructions:** Constructs search URLs directly to avoid clicking calendar/occupancy popups that often trigger bot detection.
  * **Two-Step Process:** Separates link collection from data extraction for maximum stability.
  * **Robust Selectors:** Uses `data-selenium` and `data-testid` attributes instead of random CSS classes.
  * **Deep Data Extraction:** Scrapes detailed information including:
      * Hotel Name
      * Price (Numeric)
      * Star Rating
      * Review Score (e.g., 8.6) & Rating Word (e.g., Excellent)
      * Review Count
      * Address & Distance to Center
      * Benefits & Facilities
      * Hotel Images

## 🛠️ Prerequisites
Before running the script, ensure you have the following installed:
1.  **Python 3.8+**
2.  **Google Chrome** (Latest version)
3.  **ChromeDriver** (Must match your Chrome version)
      * *Note: Update the `path_to_chrome_driver` variable in the scripts to point to your local chromedriver file.*

### Required Python Libraries
Install the dependencies using pip:
```bash
pip install selenium beautifulsoup4 lxml requests
```

## 📂 Project Structure
  * `scrapelink.py`: **(Step 1)** Search logic. Takes user inputs (Location, Date, Guests), constructs the search URL, scrolls through results, and saves unique hotel URLs.
  * `scrapeinfo.py`: **(Step 2)** Detail scraper. Reads the URLs, visits each hotel page, and extracts specific details.
  * `hotel_links.csv`: Intermediate output containing only URLs.
  * `agoda_final_details.csv`: Final output containing the clean dataset.

## 📖 How to Use
To ensure data integrity and avoid timeouts, follow this strict two-step process:


### Step 1: Collect Hotel Links
Run the link collector script. You will be prompted to enter the destination, dates, and number of guests.
```bash
python scrapelink.py
```

  * **Inputs:** Terminal prompts (Location, Check-in, Check-out, etc.).
  * **Process:** The script opens Chrome, searches Agoda, handles infinite scrolling, and grabs the URL of every hotel found.
  * **Output:** Generates `hotel_links.csv`.


### Step 2: Extract Hotel Details
Once the links are saved, run the detail scraper. This script will read the CSV generated in Step 1.
```bash
python scrapeinfo.py
```

  * **Process:** The script visits every link in `hotel_links.csv` one by one. It waits for dynamic elements (like prices and reviews) to load before scraping.
  * **Output:** Generates `agoda_final_details.csv`.

## 📊 CSV Output Format
The final `agoda_final_details.csv` will contain the following columns:

| Column | Description |
| :--- | :--- |
| `name` | Name of the hotel |
| `price` | Price per night (numeric) |
| `score` | Review score (e.g., 8.6) |
| `rating_word` | Qualitative rating (e.g., Excellent) |
| `review_count` | Total number of reviews |
| `address` | Physical address or distance from landmarks |
| `description` | Brief hotel description |
| `url` | Direct link to the hotel page |

## ⚠️ Disclaimer
This project is for **educational and research purposes only**.
  * Web scraping may violate Agoda's Terms of Service.
  * Do not aggressively scrape the website (the scripts include `time.sleep` to mimic human behavior).
  * The authors are not responsible for any IP bans or legal issues resulting from the use of this code.