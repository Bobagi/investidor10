from datetime import datetime, timezone

from selenium.webdriver.common.by import By
import time


def _format_log_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %z")

def extract_table_header(table):
    header_elem = table.find_element(By.TAG_NAME, "thead")
    header_row = header_elem.find_element(By.TAG_NAME, "tr")
    header_cols = header_row.find_elements(By.TAG_NAME, "th")
    header = " | ".join([col.text.strip() for col in header_cols if col.text.strip() != ""])
    return "Order Type | " + header if header else "Order Type"

def extract_detailed_table_data(driver, table, paginate_id=None):
    detailed_rows = []
    row_elements = table.find_elements(By.CSS_SELECTOR, "tbody tr")
    for row in row_elements:
        row_class = row.get_attribute("class") or ""
        if "Compra" in row_class:
            order_type = "COMPRA"
        elif "Venda" in row_class:
            order_type = "VENDA"
        else:
            order_type = "N/A"
        cells = row.find_elements(By.TAG_NAME, "td")
        cell_texts = [cell.text.strip() for cell in cells]
        detailed_rows.append(f"{order_type} | " + " | ".join(cell_texts))
    
    if paginate_id:
        while True:
            try:
                paginate = driver.find_element(By.ID, paginate_id)
                next_button = paginate.find_element(By.XPATH, ".//a[contains(@class, 'next')]")
                if "disabled" in next_button.get_attribute("class"):
                    break
                driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
                time.sleep(2)
                driver.execute_script("arguments[0].click();", next_button)
                time.sleep(10)
                row_elements = table.find_elements(By.CSS_SELECTOR, "tbody tr")
                for row in row_elements:
                    row_class = row.get_attribute("class") or ""
                    if "Compra" in row_class:
                        order_type = "COMPRA"
                    elif "Venda" in row_class:
                        order_type = "VENDA"
                    else:
                        order_type = "N/A"
                    cells = row.find_elements(By.TAG_NAME, "td")
                    cell_texts = [cell.text.strip() for cell in cells]
                    detailed_rows.append(f"{order_type} | " + " | ".join(cell_texts))
            except Exception as pagination_exception:
                print(f"{_format_log_timestamp()} [wallet-entries] Pagination error: {pagination_exception}")
                break
    return detailed_rows

def process_table(driver, table, index):
    header = extract_table_header(table)
    paginate_id = None
    if index == 1:
        paginate_id = "ticker-entries_paginate"
    elif index == 2:
        paginate_id = "crypto-entries_paginate"
    detailed_rows = extract_detailed_table_data(driver, table, paginate_id)
    print(f"{_format_log_timestamp()} [wallet-entries] Processing table {index}.")
    print(f"{_format_log_timestamp()} [wallet-entries] Header: {header}")
    #print(f"Extracted {len(detailed_rows)} row(s) from table {index}.")
    for row in detailed_rows:
        print(row)
    return {
        "table_index": index,
        "header": header,
        "rows": detailed_rows
    }

def extract_wallet_entries(driver, url):
    print(f"{_format_log_timestamp()} [wallet-entries] Accessing wallet entries...")
    driver.get(url)
    time.sleep(10)
    tables = driver.find_elements(By.CSS_SELECTOR, "table")
    if len(tables) < 4:
        print(f"{_format_log_timestamp()} [wallet-entries] Insufficient tables found on the page.")
        return []
    tables = tables[:4]
    print(f"{_format_log_timestamp()} [wallet-entries] {len(tables)} table(s) found (adjusted to 4).")
    results = []
    for i, table in enumerate(tables, start=1):
        result = process_table(driver, table, i)
        results.append(result)
    return results
