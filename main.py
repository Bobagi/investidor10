import re
import sys
import time
from datetime import date, datetime
from typing import Dict, List, Optional

from flask import Flask, jsonify, render_template, request
from flasgger import Swagger
from flask_cors import CORS
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from utils import (
    convert_rows_to_text,
    extract_structured_table_rows,
    extract_table_headers,
    setup_headless_chrome_driver,
)
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

def extract_assets_data(driver, url):
    collapsed_tables = []
    driver.get(url)

    collapsed_tables.append(
        extract_table_data_with_resilience(
            driver=driver,
            table_selector="table",
            table_name="Ações",
            wait_timeout_seconds=20,
        )
    )

    toggle_elements_length = len(
        driver.find_elements(By.XPATH, "//*[contains(@onclick, 'MyWallets.toogleClass')]")
    )

    for toggle_index in range(toggle_elements_length):
        element = refresh_toggle_element(driver, toggle_index)
        if element is None:
            continue

        table_name = extract_toggle_table_name(element)
        if "AÇÕES" in table_name.upper():
            continue

        selector = extract_toggle_selector(element)
        if selector is None:
            collapsed_tables.append({
                "table_name": table_name,
                "error": "Não foi possível identificar o seletor da tabela",
            })
            continue

        toggle_table_result = extract_expanded_table(driver, element, selector, table_name)
        collapsed_tables.append(toggle_table_result)

    return collapsed_tables


def refresh_toggle_element(driver, toggle_index):
    try:
        refreshed_toggles = driver.find_elements(
            By.XPATH, "//*[contains(@onclick, 'MyWallets.toogleClass')]"
        )
        if toggle_index < len(refreshed_toggles):
            return refreshed_toggles[toggle_index]
    except StaleElementReferenceException:
        return None
    return None


def extract_toggle_table_name(toggle_element) -> str:
    try:
        return toggle_element.find_element(By.CLASS_NAME, "name_value").text.strip()
    except Exception:
        return "Tabela desconhecida"


def extract_toggle_selector(toggle_element) -> Optional[str]:
    onclick = toggle_element.get_attribute("onclick")
    match = re.search(r"toogleClass\('([^']+)'", onclick)
    if match:
        return match.group(1)
    return None


def extract_expanded_table(driver, toggle_element, selector: str, table_name: str):
    try:
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", toggle_element
        )
        driver.execute_script("arguments[0].click();", toggle_element)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, f"{selector} table"))
        )
        return extract_table_data_with_resilience(
            driver=driver,
            table_selector=f"{selector} table",
            table_name=table_name,
            wait_timeout_seconds=5,
        )
    except TimeoutException:
        return {
            "table_name": table_name,
            "error": "Tempo limite ao carregar os dados deste grupo de ativos.",
        }
    except Exception as e:
        return {
            "table_name": table_name,
            "error": str(e)
        }


def extract_table_data_with_resilience(
    driver,
    table_selector: str,
    table_name: str,
    wait_timeout_seconds: int,
):
    try:
        WebDriverWait(driver, wait_timeout_seconds).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, table_selector))
        )
    except TimeoutException:
        return {
            "table_name": table_name,
            "error": "Tempo limite ao carregar a tabela principal de ativos.",
        }

    for attempt in range(3):
        try:
            table_element = driver.find_element(By.CSS_SELECTOR, table_selector)
            header_labels = extract_table_headers(table_element)
            structured_rows = extract_structured_table_rows(table_element, header_labels)
            return {
                "table_name": table_name,
                "header": header_labels,
                "rows": convert_rows_to_text(structured_rows, header_labels),
                "structured_rows": structured_rows,
            }
        except StaleElementReferenceException:
            if attempt == 2:
                return {
                    "table_name": table_name,
                    "error": "Não foi possível capturar os dados desta tabela (referência expirada)",
                }
            time.sleep(0.35)
    return {
        "table_name": table_name,
        "error": "Falha desconhecida ao extrair tabela",
    }

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
    driver = setup_headless_chrome_driver()
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

    driver = setup_headless_chrome_driver()
    try:
        result = extract_assets_data(driver, wallet_url)
        if jsonfy_return:
            tables = []
            for tbl in result:
                tables.append({
                    'table_name': tbl.get('table_name', ''),
                    'header': tbl.get('header', []),
                    'rows': [row.split(' | ') for row in tbl.get('rows', [])],
                    'structured_rows': tbl.get('structured_rows', []),
                    'error': tbl.get('error')
                })
            return jsonify({'tables': tables})
        else:
            return result
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        driver.quit()

@app.route("/data-com", methods=["GET"])
def get_data_com():
    """Get the next dividend dates for wallet assets with metadata.
    ---
    parameters:
      - name: wallet_url
        in: query
        type: string
        required: true
    responses:
      200:
        description: Upcoming dividend dates enriched with asset type and origin table
    """
    data = request.get_json(silent=True) or request.args
    if "wallet_url" not in data:
        return jsonify({"error": "wallet_url parameter not provided"}), 400

    try:
        assets_payload = get_assets(data["wallet_url"], False)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    try:
        result = fetch_latest_data_com(assets_payload)
        return result
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def fetch_latest_data_com(assets_json):
    tables = extract_tables_from_assets_payload(assets_json)
    driver = setup_headless_chrome_driver()
    results = []
    for tbl in tables:
        table_name = tbl.get('table_name', '')
        header_labels = tbl.get('header', [])
        structured_rows = build_structured_rows(tbl)
        for row in structured_rows:
            ticker = resolve_ticker_from_row(row, header_labels)
            asset_name = resolve_asset_name_from_row(row)
            if not ticker:
                continue
            url = resolve_asset_url(ticker, table_name)
            asset_type = derive_asset_type_from_table(table_name)
            if not url:
                continue
            latest_dividend = fetch_latest_dividend_entry(driver, url)
            if not latest_dividend:
                continue
            results.append({
                'asset': ticker,
                'asset_name': asset_name,
                'asset_type': asset_type,
                'wallet_table': table_name,
                'asset_url': url,
                'date_com': latest_dividend['date_com'],
                'dividend_details': latest_dividend['row_snapshot'],
            })
    driver.quit()

    today = date.today()
    filtered = []
    for item in results:
        try:
            parsed_date = datetime.strptime(item['date_com'], '%d/%m/%Y').date()
        except Exception:
            continue
        if parsed_date >= today:
            filtered.append({**item, 'parsed_date': parsed_date})

    filtered.sort(key=lambda x: x['parsed_date'])
    sorted_results = [
        {
            'asset': entry['asset'],
            'asset_name': entry['asset_name'],
            'asset_type': entry['asset_type'],
            'wallet_table': entry['wallet_table'],
            'asset_url': entry['asset_url'],
            'date_com': entry['date_com'],
            'dividend_details': entry['dividend_details'],
        }
        for entry in filtered
    ]

    return jsonify(sorted_results)


def extract_tables_from_assets_payload(assets_json) -> List[Dict]:
    if isinstance(assets_json, dict):
        return assets_json.get('tables', [])
    if isinstance(assets_json, list):
        return assets_json
    return []


def build_structured_rows(table_payload: Dict) -> List[Dict[str, str]]:
    structured_rows: List[Dict[str, str]] = table_payload.get('structured_rows', []) or []
    if structured_rows:
        return structured_rows

    header_labels = table_payload.get('header', []) or []
    textual_rows: List[str] = table_payload.get('rows', []) or []
    parsed_rows: List[Dict[str, str]] = []
    for row in textual_rows:
        parts = row.split(' | ')
        row_dict: Dict[str, str] = {}
        for index, value in enumerate(parts):
            if index < len(header_labels):
                row_dict[header_labels[index]] = value
            else:
                row_dict[f"column_{index + 1}"] = value
        parsed_rows.append(row_dict)
    return parsed_rows


def resolve_ticker_from_row(row: Dict[str, str], header_labels: List[str]) -> Optional[str]:
    prioritized_keys = [
        'Código',
        'Codigo',
        'Ticker',
        'Ativo',
    ]
    for key in prioritized_keys:
        if key in row and row[key]:
            return row[key]
    if header_labels:
        first_label = header_labels[0]
        return row.get(first_label)
    return next(iter(row.values()), None)


def resolve_asset_name_from_row(row: Dict[str, str]) -> Optional[str]:
    for key in ['Nome', 'Empresa', 'Descrição']:
        if key in row and row[key]:
            return row[key]
    return None


def derive_asset_type_from_table(table_name: str) -> str:
    normalized = table_name.upper()
    if 'FIIS' in normalized:
        return 'Fundo Imobiliário'
    if 'CRIPTO' in normalized:
        return 'Criptomoeda'
    if 'ETF' in normalized:
        return 'ETF'
    if 'STOCKS' in normalized:
        return 'Ação Internacional'
    if 'BDRS' in normalized:
        return 'BDR'
    return 'Ação'


def fetch_latest_dividend_entry(driver, url: str) -> Optional[Dict[str, str]]:
    driver.get(url)
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, 'table-dividends-history'))
        )
    except TimeoutException:
        return None
    try:
        table = driver.find_element(By.ID, 'table-dividends-history')
    except NoSuchElementException:
        return None

    candidates: List[Dict[str, str]] = []
    for tr in table.find_elements(By.CSS_SELECTOR, 'tbody tr'):
        cells = tr.find_elements(By.TAG_NAME, 'td')
        if len(cells) < 2:
            continue
        row_snapshot = [cell.text.strip() for cell in cells if cell.text.strip()]
        try:
            parsed_date = datetime.strptime(cells[1].text.strip(), '%d/%m/%Y')
        except Exception:
            continue
        candidates.append({
            'date_com': parsed_date.strftime('%d/%m/%Y'),
            'row_snapshot': row_snapshot,
            'parsed_date': parsed_date,
        })

    if not candidates:
        return None

    candidates.sort(key=lambda item: item['parsed_date'])
    latest_candidate = candidates[-1]
    return {
        'date_com': latest_candidate['date_com'],
        'row_snapshot': latest_candidate['row_snapshot'],
    }


def resolve_asset_url(code: str, table_name: str) -> Optional[str]:
    slug = code.lower()
    primary = table_name.split('\n')[0].upper()
    if 'AÇÃO' in primary or 'AÇÕES' in primary or 'AÇÕES BR' in primary:
        path = 'acoes'
    elif 'FIIS' in primary:
        path = 'fiis'
    elif 'CRIPTOMOEDA' in primary:
        path = 'criptomoedas'
    elif 'ETF' in primary and 'INTERN' in primary:
        path = 'etfs-global'
    elif 'ETF' in primary:
        path = 'etfs'
    elif 'STOCKS' in primary:
        path = 'stocks'
    elif 'BDR' in primary:
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
