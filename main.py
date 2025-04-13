from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
import time, os, re, sys
from dotenv import load_dotenv
from wallet_entries import extract_wallet_entries

sys.stdout.reconfigure(line_buffering=True)
load_dotenv()

WALLET_URL = os.getenv("WALLET_URL")
WALLET_ENTRIES_URL = os.getenv("WALLET_ENTRIES_URL")
if not WALLET_URL:
    raise Exception("WALLET_URL environment variable not set.")
if not WALLET_ENTRIES_URL:
    raise Exception("WALLET_ENTRIES_URL environment variable not set.")

def setup_driver():
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--remote-debugging-port=9222')
    options.binary_location = "/usr/bin/google-chrome"
    service = Service(executable_path="/usr/local/bin/chromedriver")
    return webdriver.Chrome(service=service, options=options)

def extract_table_header(table):
    try:
        header_elem = table.find_element(By.TAG_NAME, "thead")
        header_row = header_elem.find_element(By.TAG_NAME, "tr")
        header_cols = header_row.find_elements(By.TAG_NAME, "th")
        return " | ".join([col.text.strip() for col in header_cols if col.text.strip() != ""])
    except Exception:
        return ""

def extract_table_data(table):
    rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")
    data = []
    for row in rows:
        cols = row.find_elements(By.TAG_NAME, "td")
        row_data = [col.text.strip() for col in cols if col.text.strip() != ""]
        if row_data:
            data.append(" | ".join(row_data))
    return data

def extract_tables(driver, url):
    print("Accessing wallet...")
    driver.get(url)
    time.sleep(5)
    try:
        actions_table = driver.find_element(By.CSS_SELECTOR, "table")
        header = extract_table_header(actions_table)
        if header:
            print("Header from Actions table:")
            print(header)
        actions_data = extract_table_data(actions_table)
        print("Data extracted from Actions table:")
        if actions_data:
            for row in actions_data:
                print(row)
        else:
            print("No data found in Actions table.")
    except Exception as e:
        print("Error extracting Actions table:", e)
    toggle_elements = driver.find_elements(By.XPATH, "//*[contains(@onclick, 'MyWallets.toogleClass')]")
    if toggle_elements:
        print(f"{len(toggle_elements)} collapsed table element(s) found.")
    else:
        print("No collapsed table elements found.")
    for element in toggle_elements:
        try:
            table_name = element.find_element(By.CLASS_NAME, "name_value").text.strip()
        except Exception:
            table_name = "Unknown Table"
        try:
            registered_count = element.find_element(By.CLASS_NAME, "count_value").text.strip()
        except Exception:
            registered_count = "Not available"
        if "AÇÕES" in table_name.upper():
            print(f"Skipping table {table_name} that is already open.")
            continue
        onclick_value = element.get_attribute("onclick")
        match = re.search(r"toogleClass\('([^']+)'", onclick_value)
        if match:
            target_selector = match.group(1)
            try:
                driver.execute_script("arguments[0].scrollIntoView(true);", element)
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", element)
                time.sleep(2)
                container = driver.find_element(By.CSS_SELECTOR, target_selector)
                table = container.find_element(By.TAG_NAME, "table")
                header = extract_table_header(table)
                if header:
                    print(f"Header from table {table_name}:")
                    print(header)
                table_data = extract_table_data(table)
                print(f"Table: {table_name} | Registered assets: {registered_count} | Extracted assets: {len(table_data)}")
                if table_data:
                    for row in table_data:
                        print(row)
                else:
                    print(f"No data found in table {table_name}.")
            except Exception as e:
                print(f"Error processing table {table_name} ({target_selector}):", e)
        else:
            print("Could not identify target selector from onclick attribute.")

def main():
    print("Starting Investidor10 Bot application...")
    driver = setup_driver()
    try:
        extract_tables(driver, WALLET_URL)
        # entries_data = extract_wallet_entries(driver, WALLET_ENTRIES_URL)
        # print("\nWallet entries extracted:")
        # for table in entries_data:
        #     print(f"\nTable {table['table_index']} Header:")
        #     print(table["header"])
        #     for row in table["rows"]:
        #         print(row)
    except Exception as e:
        print("General error in application:", e)
    finally:
        driver.quit()
        print("Application finished, browser closed.")

if __name__ == "__main__":
    print("ABACAXOLA")
    main()
