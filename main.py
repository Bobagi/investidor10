import re
import time
import sys
import os
import json
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from flask import Flask, jsonify, request
from flasgger import Swagger
from flask_cors import CORS
from wallet_entries import extract_wallet_entries
from utils import setup_driver, extract_table_header, extract_table_data
from datetime import datetime, date

sys.stdout.reconfigure(line_buffering=True)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": [
    "http://localhost:8080", "https://localhost:8080"
]}})
Swagger(app)

def extract_assets_data(driver, url):
    collapsed_tables = []
    driver.get(url)
    time.sleep(10)
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
                time.sleep(2)
                driver.execute_script("arguments[0].click();", element)
                time.sleep(10)
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

@app.route("/wallet-entries", methods=["GET"])
def get_wallet_entries():
    """Retrieve detailed wallet entries.
    ---
    parameters:
      - name: wallet_entries_url
        in: query
        type: string
        required: true
    responses:
      200:
        description: Wallet entries extracted from the provided URL
    """
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
        
@app.route("/assets", methods=["GET"])
def get_assets(wallet_url=None, jsonfy_return=True):
    """Retrieve wallet asset tables.
    ---
    parameters:
      - name: wallet_url
        in: query
        type: string
        required: true
    responses:
      200:
        description: Structured data for wallet assets
    """
    if wallet_url is None:
        data = request.get_json(silent=True) or request.args
        if "wallet_url" not in data:
            return jsonify({"error": "wallet_url parameter not provided"}), 400
        wallet_url = data["wallet_url"]
        
    driver = setup_driver()
    try:
        result = extract_assets_data(driver, wallet_url)
        if jsonfy_return:
            tables = []
            for tbl in result:
                header_str = tbl.get('header', '')
                rows_list = tbl.get('rows', [])
                header = header_str.split(' | ') if header_str else []
                rows = [row.split(' | ') for row in rows_list]
                tables.append({
                    'table_name': tbl.get('table_name', ''),
                    'header': header,
                    'rows': rows
                })
            return json.dumps({'tables': tables}, ensure_ascii=False)
        else:
            return result
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        driver.quit()

@app.route("/data-com", methods=["GET"])
def get_data_com():
    """Get the next dividend dates for wallet assets.
    ---
    parameters:
      - name: wallet_url
        in: query
        type: string
        required: true
    responses:
      200:
        description: Upcoming dividend dates
    """
    data = request.get_json(silent=True) or request.args
    if "wallet_url" not in data:
        return jsonify({"error": "wallet_url parameter not provided"}), 400
    
    try:
        print("Executing get_data_com...")
        data = get_assets(data["wallet_url"], False)
        print("Data returned!")
    except Exception as e:
        return e
    
    try:
        print("Executing fetch_latest_data_com...")
        result = fetch_latest_data_com(data)
        print("fetch_latest_data_com RETURNED!!: ", result)
        return result
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def fetch_latest_data_com(assets_json) -> str:
    if isinstance(assets_json, dict):
        tables = assets_json.get('tables', [])
    elif isinstance(assets_json, list):
        tables = assets_json
    else:
        return json.dumps({'error': 'invalid input format'}, ensure_ascii=False)
    driver = setup_driver()
    results = []
    for tbl in tables:
        table_name = tbl.get('table_name', '')
        for raw_row in tbl.get('rows', []):
            row = raw_row.split(' | ') if isinstance(raw_row, str) else raw_row
            code = row[0]
            url = resolve_asset_url(code, table_name)
            print(f"Resolving URL for {code}: {url}")
            if not url:
                continue
            driver.get(url)
            time.sleep(10)
            try:
                table = driver.find_element(By.ID, 'table-dividends-history')
            except NoSuchElementException:
                print(f"Table not found for {code}.")
                continue
            dates = []
            for tr in table.find_elements(By.CSS_SELECTOR, 'tbody tr'):
                cells = tr.find_elements(By.TAG_NAME, 'td')
                # print(f"Cells found: {len(cells)}")
                if len(cells) < 2:
                    continue
                try:
                    d = datetime.strptime(cells[1].text.strip(), '%d/%m/%Y')
                    dates.append(d)
                except:
                    pass
            if dates:
                print(f"Dates found for {code}: {dates}")
                latest = max(dates).strftime('%d/%m/%Y')
                results.append({'asset': code, 'date_com': latest})
    driver.quit()

    today = date.today()
    filtered = []
    for item in results:
        try:
            d = datetime.strptime(item['date_com'], '%d/%m/%Y').date()
        except Exception:
            continue
        if d >= today:
            filtered.append({'asset': item['asset'], 'date_com': item['date_com'], 'd': d})

    filtered.sort(key=lambda x: x['d'])
    sorted_results = [{'asset': f['asset'], 'date_com': f['date_com']} for f in filtered]

    return json.dumps(sorted_results, ensure_ascii=False)

def resolve_asset_url(code: str, table_name: str) -> str:
    slug = code.lower()
    if table_name == 'assets':
        path = 'acoes'
    else:
        primary = table_name.split('\n')[0].upper()
        if primary == 'FIIS':
            path = 'fiis'
        elif primary.startswith('CRIPTOMOEDAS'):
            path = 'criptomoedas'
        elif primary.startswith('ETFS INTERN'):
            path = 'etfs-global'
        elif primary.startswith('ETFS'):
            path = 'etfs'
        elif primary.startswith('STOCKS'):
            path = 'stocks'
        elif primary.startswith('BDRS'):
            path = 'bdrs'
        else:
            return None
    return f"https://investidor10.com.br/{path}/{slug}/"

@app.route("/test", methods=["GET"])
def test():
    """Simple health check endpoint."""
    return jsonify({"message": "Test successful"})

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000
    )
