import re
import time
import sys
import os
from selenium.webdriver.common.by import By
from flask import Flask, jsonify, request
from flask_cors import CORS
from wallet_entries import extract_wallet_entries
from utils import setup_driver, extract_table_header, extract_table_data
from search_data_com import fetch_latest_data_com

sys.stdout.reconfigure(line_buffering=True)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": [
    "http://localhost:8080", "https://localhost:8080"
]}})

def extract_assets_data(driver, url):
    collapsed_tables = []
    driver.get(url)
    time.sleep(5)
    try:
        assets_table = driver.find_element(By.CSS_SELECTOR, "table")
        header = extract_table_header(assets_table)
        assets_data = extract_table_data(assets_table)
    except Exception as e:
        print("Error:", str(e))
        collapsed_tables = str(e)
        
    collapsed_tables.append({
        "table_name": "assets",
        "header": header,
        "rows": assets_data
    })
    toggle_elements = driver.find_elements(
        By.XPATH, "//*[contains(@onclick, 'MyWallets.toogleClass')]"
    )
    for element in toggle_elements:
        try:
            table_name = element.find_element(
                By.CLASS_NAME, "name_value"
            ).text.strip()
        except:
            table_name = "Unknown Table"
        if "AÇÕES" in table_name.upper():
            continue
        onclick = element.get_attribute("onclick")
        match = re.search(r"toogleClass\('([^']+)'", onclick)
        if match:
            selector = match.group(1)
            try:
                driver.execute_script(
                    "arguments[0].scrollIntoView(true);", element
                )
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", element)
                time.sleep(2)
                container = driver.find_element(
                    By.CSS_SELECTOR, selector
                )
                table = container.find_element(By.TAG_NAME, "table")
                header = extract_table_header(table)
                rows = extract_table_data(table)
                collapsed_tables.append({
                    "table_name": table_name,
                    "header": header,
                    "rows": rows
                })
            except Exception as e:
                collapsed_tables.append({
                    "table_name": table_name,
                    "error": str(e)
                })
        else:
            collapsed_tables.append({
                "table_name": table_name,
                "error": "Could not identify target selector"
            })
    return collapsed_tables

@app.route("/assets", methods=["GET"])
def get_assets():
    data = request.get_json(silent=True) or request.args
    if "wallet_url" not in data:
        return jsonify({"error": "wallet_url parameter not provided"}), 400
    driver = setup_driver()
    try:
        result = extract_assets_data(driver, data["wallet_url"])
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        driver.quit()

@app.route("/wallet-entries", methods=["GET"])
def get_wallet_entries():
    data = request.get_json(silent=True) or request.args
    if "wallet_entries_url" not in data:
        return jsonify({"error": "wallet_entries_url parameter not provided"}), 400
    driver = setup_driver()
    try:
        result = extract_wallet_entries(driver, data["wallet_entries_url"])
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        driver.quit()

@app.route("/data-com", methods=["GET"])
def get_data_com():
    data = request.get_json(silent=True) or request.args
    if "wallet_url" not in data:
        return jsonify({"error": "wallet_url parameter not provided"}), 400
    port = int(os.getenv("API_PORT", "5000"))
    try:
        result = fetch_latest_data_com(data["wallet_url"], port)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/test", methods=["GET"])
def test():
    return jsonify({"message": "Test successful"})

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("API_PORT", "5000"))
    )
