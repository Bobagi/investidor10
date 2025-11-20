from typing import Dict, List

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By


def setup_headless_chrome_driver() -> webdriver.Chrome:
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--remote-debugging-port=9222")
    chrome_options.set_capability("pageLoadStrategy", "eager")
    chrome_options.binary_location = "/usr/bin/google-chrome"

    chrome_service = Service(executable_path="/usr/local/bin/chromedriver")
    chrome_driver = webdriver.Chrome(service=chrome_service, options=chrome_options)
    chrome_driver.set_page_load_timeout(120)
    chrome_driver.set_script_timeout(120)
    return chrome_driver


def extract_table_headers(table) -> List[str]:
    try:
        header_elem = table.find_element(By.TAG_NAME, "thead")
        header_row = header_elem.find_element(By.TAG_NAME, "tr")
        header_cols = header_row.find_elements(By.TAG_NAME, "th")
        return [col.text.strip() for col in header_cols if col.text.strip()]
    except Exception:
        return []


def extract_structured_table_rows(table, header_labels: List[str]) -> List[Dict[str, str]]:
    rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")
    structured_rows: List[Dict[str, str]] = []
    for row in rows:
        column_cells = row.find_elements(By.TAG_NAME, "td")
        cleaned_values = [cell.text.strip() for cell in column_cells if cell.text.strip()]
        if not cleaned_values:
            continue

        structured_row: Dict[str, str] = {}
        for index, value in enumerate(cleaned_values):
            if index < len(header_labels):
                structured_row[header_labels[index]] = value
            else:
                structured_row[f"column_{index + 1}"] = value
        structured_rows.append(structured_row)
    return structured_rows


def convert_rows_to_text(structured_rows: List[Dict[str, str]], header_labels: List[str]) -> List[str]:
    serialized_rows: List[str] = []
    for row in structured_rows:
        ordered_values = [row.get(label, "") for label in header_labels]
        extra_values = [
            value
            for key, value in row.items()
            if key not in header_labels
        ]
        joined_values = " | ".join([*ordered_values, *extra_values]).strip(" |")
        if joined_values:
            serialized_rows.append(joined_values)
    return serialized_rows
