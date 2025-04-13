from selenium.webdriver.common.by import By
import time

def extract_table_header(table):
    try:
        header_elem = table.find_element(By.TAG_NAME, "thead")
        header_row = header_elem.find_element(By.TAG_NAME, "tr")
        header_cols = header_row.find_elements(By.TAG_NAME, "th")
        header = " | ".join([col.text.strip() for col in header_cols if col.text.strip() != ""])
        return "Order Type | " + header if header else "Order Type"
    except Exception:
        return "FAILED TO RETRIEVE HEADER"

def extract_detailed_table_data(driver, table):
    row_elements = table.find_elements(By.CSS_SELECTOR, "tbody tr")
    detailed_rows = []
    for row in row_elements:
        # Determine the Order Type based on the row's class attribute.
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
    return detailed_rows

def process_table(driver, table, index):
    header = extract_table_header(table)
    detailed_rows = extract_detailed_table_data(driver, table)
    print(f"\nProcessing table {index}:")
    if header:
        print("Header:")
        print(header)
    else:
        print("No header found.")
    print(f"Extracted {len(detailed_rows)} row(s) from table {index}.")
    for row in detailed_rows:
        print(row)
    return {
        "table_index": index,
        "header": header,
        "rows": detailed_rows
    }

def extract_wallet_entries(driver, url):
    print("Accessing wallet entries...")
    driver.get(url)
    time.sleep(5)
    tables = driver.find_elements(By.CSS_SELECTOR, "table")
    if not tables:
        print("No tables found on wallet entries page.")
        return []
    print(f"{len(tables)} table(s) found on wallet entries page.")
    results = []
    for i, table in enumerate(tables, start=1):
        result = process_table(driver, table, i)
        results.append(result)
    return results
