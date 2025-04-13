import re
import time
import sys
from flask import Flask, jsonify, request
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from wallet_entries import extract_wallet_entries

sys.stdout.reconfigure(line_buffering=True)

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

def extract_actions_data(driver, url):
    result = {}
    driver.get(url)
    time.sleep(5)
    try:
        actions_table = driver.find_element(By.CSS_SELECTOR, "table")
        header = extract_table_header(actions_table)
        actions_data = extract_table_data(actions_table)
        result["actions_table"] = {"header": header, "rows": actions_data}
    except Exception as e:
        result["actions_table_error"] = str(e)
    collapsed_tables = []
    toggle_elements = driver.find_elements(By.XPATH, "//*[contains(@onclick, 'MyWallets.toogleClass')]")
    for element in toggle_elements:
        try:
            table_name = element.find_element(By.CLASS_NAME, "name_value").text.strip()
        except Exception:
            table_name = "Unknown Table"
        if "AÇÕES" in table_name.upper():
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
                table_data = extract_table_data(table)
                collapsed_tables.append({
                    "table_name": table_name,
                    "header": header,
                    "rows": table_data
                })
            except Exception as e:
                collapsed_tables.append({
                    "table_name": table_name,
                    "error": str(e)
                })
        else:
            collapsed_tables.append({
                "table_name": table_name,
                "error": "Could not identify target selector from onclick attribute"
            })
    result["collapsed_tables"] = collapsed_tables
    return result

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": ["http://localhost:8080", "https://localhost:8080"]}})

@app.route("/api/actions", methods=["GET"])
def get_actions():
    data = request.get_json(silent=True)
    if not data:
        data = request.args
    if "wallet_url" not in data:
        return jsonify({"error": "wallet_url parameter not provided"}), 400
    wallet_url = data["wallet_url"]
    driver = setup_driver()
    try:
        result = extract_actions_data(driver, wallet_url)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        driver.quit()

@app.route("/api/wallet-entries", methods=["GET"])
def get_wallet_entries():
    data = request.get_json(silent=True)
    if not data:
        data = request.args
    if "wallet_entries_url" not in data:
        return jsonify({"error": "wallet_entries_url parameter not provided"}), 400
    wallet_entries_url = data["wallet_entries_url"]
    driver = setup_driver()
    try:
        result = extract_wallet_entries(driver, wallet_entries_url)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        driver.quit()

@app.route("/api/test", methods=["GET"])
def test():
    try:
        return jsonify({"message": "Test successful"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
