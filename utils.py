import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

def setup_driver(page_load_timeout_seconds: float = 300, script_timeout_seconds: float = 300):
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--remote-debugging-port=9222')
    options.binary_location = "/usr/bin/google-chrome"
    service = Service(executable_path="/usr/local/bin/chromedriver")
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(page_load_timeout_seconds)
    driver.set_script_timeout(script_timeout_seconds)
    return driver

def extract_table_header(table):
    try:
        header_elem = table.find_element(By.TAG_NAME, "thead")
        header_row = header_elem.find_element(By.TAG_NAME, "tr")
        header_cols = header_row.find_elements(By.TAG_NAME, "th")
        return " | ".join([col.text.strip() for col in header_cols if col.text.strip()])
    except Exception:
        return ""

def extract_table_data(table):
    rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")
    data = []
    for row in rows:
        cols = row.find_elements(By.TAG_NAME, "td")
        row_data = [col.text.strip() for col in cols if col.text.strip()]
        if row_data:
            data.append(" | ".join(row_data))
    return data
