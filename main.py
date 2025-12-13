import re
import sys
from datetime import date, datetime
from typing import Dict, List

from flask import Flask, jsonify, render_template, request
from flasgger import Swagger
from flask_cors import CORS
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from http_assets_extractor import extract_assets_via_http
from http_dividends_extractor import extract_dividend_dates_via_http
from utils import extract_table_data, extract_table_header, setup_driver
from wallet_entries import extract_wallet_entries

sys.stdout.reconfigure(line_buffering=True)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": [
    "http://localhost:8080", "https://localhost:8080"
]}})
Swagger(app)


@app.route("/")
def index():
    """Serve a simple HTML page for manual testing."""
    return render_template("index.html")


def contains_usable_asset_rows(assets_payload: List[Dict[str, object]]) -> bool:
    if not isinstance(assets_payload, list):
        return False

    for table_payload in assets_payload:
        if not isinstance(table_payload, dict):
            continue
        rows = table_payload.get("rows", [])
        if isinstance(rows, list) and any(rows):
            return True
    return False

def extract_assets_data(driver, url):
    collapsed_tables = []
    driver.get(url)
    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table"))
        )
        assets_table = driver.find_element(By.CSS_SELECTOR, "table")
        header = extract_table_header(assets_table)
        assets_data = extract_table_data(assets_table)
        collapsed_tables.append({
            "table_name": "assets",
            "header": header,
            "rows": assets_data
        })
    except TimeoutException:
        collapsed_tables.append({
            "table_name": "assets",
            "error": "Tempo limite ao carregar a tabela principal de ativos."
        })
    except Exception as e:
        print("Error:", str(e))
        collapsed_tables.append({
            "table_name": "assets",
            "error": str(e)
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
                    "arguments[0].scrollIntoView({block: 'center'});", element
                )
                driver.execute_script("arguments[0].click();", element)
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, f"{selector} table"))
                )
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
            except TimeoutException:
                collapsed_tables.append({
                    "table_name": table_name,
                    "error": "Tempo limite ao carregar os dados deste grupo de ativos."
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
        
    print("Executing /assets route...")
    driver = None
    try:
        assets_via_http = []
        try:
            assets_via_http = extract_assets_via_http(wallet_url)
        except Exception as extraction_error:
            print(f"HTTP assets extraction failed: {extraction_error}")

        if contains_usable_asset_rows(assets_via_http):
            result = assets_via_http
        else:
            if assets_via_http:
                print("HTTP assets extraction returned no usable rows. Falling back to Selenium scraping.")
            driver = setup_driver()
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
                    'rows': rows,
                    'error': tbl.get('error')
                })
            return jsonify({'tables': tables})
        else:
            return result
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if driver:
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
        return jsonify({"error": str(e)}), 500
    
    try:
        print("Executing fetch_latest_data_com...")
        result = fetch_latest_data_com(data)
        print("fetch_latest_data_com RETURNED!!: ", result)
        return result
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def fetch_latest_data_com(assets_json):
    tables = _normalize_tables_payload(assets_json)
    if tables is None:
        return jsonify({'error': 'invalid input format'}), 400

    selenium_driver = None
    results: List[Dict[str, object]] = []

    for table_payload in tables:
        table_name = table_payload.get('table_name', '')
        for raw_row in table_payload.get('rows', []):
            row = raw_row.split(' | ') if isinstance(raw_row, str) else raw_row
            if not row:
                continue
            asset_code = row[0]
            asset_url = resolve_asset_url(asset_code, table_name)
            print(f"Resolving URL for {asset_code}: {asset_url}")
            if not asset_url:
                continue

            latest_dividend_date = _extract_latest_dividend_date(asset_url)
            if latest_dividend_date is None:
                selenium_driver = selenium_driver or setup_driver()
                latest_dividend_date = _extract_latest_dividend_date_with_selenium(
                    selenium_driver, asset_url, asset_code
                )

            if latest_dividend_date:
                results.append({
                    'asset': asset_code,
                    'date_com_date': latest_dividend_date
                })

    if selenium_driver:
        selenium_driver.quit()

    filtered_results = _filter_and_sort_dividend_dates(results)
    formatted_results = [
        {'asset': item['asset'], 'date_com': item['date_com_date'].strftime('%d/%m/%Y')}
        for item in filtered_results
    ]

    return jsonify(formatted_results)


def _normalize_tables_payload(assets_json) -> List[Dict[str, object]] | None:
    if isinstance(assets_json, dict):
        return assets_json.get('tables', [])
    if isinstance(assets_json, list):
        return assets_json
    return None


def _extract_latest_dividend_date(asset_url: str) -> date | None:
    try:
        dividend_dates = extract_dividend_dates_via_http(asset_url)
    except Exception as http_error:
        print(f"HTTP dividend extraction failed for {asset_url}: {http_error}")
        return None

    if not dividend_dates:
        return None

    return max(dividend_dates)


def _extract_latest_dividend_date_with_selenium(driver, asset_url: str, asset_code: str) -> date | None:
    try:
        driver.get(asset_url)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, 'table-dividends-history'))
        )
    except TimeoutException:
        print(f"Timeout while waiting for dividends history for {asset_code}.")
        return None

    try:
        table = driver.find_element(By.ID, 'table-dividends-history')
    except NoSuchElementException:
        print(f"Table not found for {asset_code}.")
        return None

    selenium_dates = []
    for dividends_row in table.find_elements(By.CSS_SELECTOR, 'tbody tr'):
        cells = dividends_row.find_elements(By.TAG_NAME, 'td')
        if len(cells) < 2:
            continue
        parsed_date = _parse_brazilian_date(cells[1].text.strip())
        if parsed_date:
            selenium_dates.append(parsed_date)

    if not selenium_dates:
        return None

    print(f"Dates found for {asset_code}: {selenium_dates}")
    return max(selenium_dates)


def _parse_brazilian_date(date_value: str) -> date | None:
    try:
        return datetime.strptime(date_value, '%d/%m/%Y').date()
    except Exception:
        return None


def _filter_and_sort_dividend_dates(results: List[Dict[str, object]]) -> List[Dict[str, object]]:
    today = date.today()
    filtered = [
        result for result in results
        if isinstance(result.get('date_com_date'), date) and result['date_com_date'] >= today
    ]

    filtered.sort(key=lambda item: item['date_com_date'])
    return filtered

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
