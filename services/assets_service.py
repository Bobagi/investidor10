from datetime import date, datetime
import re
from typing import Any, Dict, List, Optional

from flask import jsonify
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as expected_conditions
from selenium.webdriver.support.ui import WebDriverWait

from utils import extract_table_data, extract_table_header, setup_driver


def retrieve_wallet_assets(wallet_url: str) -> List[Dict[str, Any]]:
    driver = setup_driver()
    try:
        return _extract_assets_data(driver, wallet_url)
    finally:
        driver.quit()


def _extract_assets_data(driver, wallet_url: str) -> List[Dict[str, Any]]:
    collapsed_tables: List[Dict[str, Any]] = []
    driver.get(wallet_url)
    try:
        WebDriverWait(driver, 20).until(
            expected_conditions.presence_of_element_located((By.CSS_SELECTOR, "table"))
        )
        assets_table = driver.find_element(By.CSS_SELECTOR, "table")
        header = extract_table_header(assets_table)
        assets_data = extract_table_data(assets_table)
        collapsed_tables.append(
            {
                "table_name": "assets",
                "header": header,
                "rows": assets_data,
            }
        )
    except TimeoutException:
        collapsed_tables.append(
            {
                "table_name": "assets",
                "error": "Tempo limite ao carregar a tabela principal de ativos.",
            }
        )
    except Exception as raw_error:
        collapsed_tables.append(
            {
                "table_name": "assets",
                "error": str(raw_error),
            }
        )

    toggle_elements = driver.find_elements(
        By.XPATH, "//*[contains(@onclick, 'MyWallets.toogleClass')]"
    )
    for element in toggle_elements:
        table_name = _safe_extract_table_name(element)
        if "AÇÕES" in table_name.upper():
            continue
        onclick = element.get_attribute("onclick")
        match = re.search(r"toogleClass\('([^']+)'", onclick)
        if not match:
            collapsed_tables.append(
                {
                    "table_name": table_name,
                    "error": "Could not identify target selector",
                }
            )
            continue

        selector = match.group(1)
        try:
            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", element
            )
            driver.execute_script("arguments[0].click();", element)
            WebDriverWait(driver, 15).until(
                expected_conditions.presence_of_element_located(
                    (By.CSS_SELECTOR, f"{selector} table")
                )
            )
            container = driver.find_element(By.CSS_SELECTOR, selector)
            table = container.find_element(By.TAG_NAME, "table")
            header = extract_table_header(table)
            rows = extract_table_data(table)
            collapsed_tables.append(
                {
                    "table_name": table_name,
                    "header": header,
                    "rows": rows,
                }
            )
        except TimeoutException:
            collapsed_tables.append(
                {
                    "table_name": table_name,
                    "error": "Tempo limite ao carregar os dados deste grupo de ativos.",
                }
            )
        except Exception as raw_error:
            collapsed_tables.append(
                {
                    "table_name": table_name,
                    "error": str(raw_error),
                }
            )
    return collapsed_tables


def _safe_extract_table_name(element) -> str:
    try:
        return element.find_element(By.CLASS_NAME, "name_value").text.strip()
    except Exception:
        return "Unknown Table"


def fetch_latest_data_com(assets_json: Any):
    if isinstance(assets_json, dict):
        tables = assets_json.get("tables", [])
    elif isinstance(assets_json, list):
        tables = assets_json
    else:
        return jsonify({"error": "invalid input format"}), 400
    driver = setup_driver()
    results = []
    for table in tables:
        table_name = table.get("table_name", "")
        for raw_row in table.get("rows", []):
            row = raw_row.split(" | ") if isinstance(raw_row, str) else raw_row
            if not row:
                continue
            code = row[0]
            asset_name = row[1] if len(row) > 1 else ""
            url = resolve_asset_url(code, table_name)
            asset_type = _normalize_asset_type(table_name)
            if not url:
                continue
            driver.get(url)
            try:
                WebDriverWait(driver, 15).until(
                    expected_conditions.presence_of_element_located(
                        (By.ID, "table-dividends-history")
                    )
                )
            except TimeoutException:
                continue
            try:
                table_element = driver.find_element(By.ID, "table-dividends-history")
            except NoSuchElementException:
                continue
            dividend_info = _collect_dividend_info(table_element)
            if dividend_info is None:
                continue
            latest_date, latest_value = dividend_info
            results.append(
                {
                    "asset": code,
                    "asset_name": asset_name,
                    "asset_type": asset_type,
                    "date_com": latest_date,
                    "last_dividend_value": latest_value,
                    "details_url": url,
                }
            )
    driver.quit()

    today = date.today()
    filtered_results = []
    for item in results:
        try:
            dividend_date = datetime.strptime(item["date_com"], "%d/%m/%Y").date()
        except Exception:
            continue
        if dividend_date >= today:
            filtered_results.append({**item, "parsed_date": dividend_date})

    filtered_results.sort(key=lambda entry: entry["parsed_date"])
    sorted_results = [
        {
            "asset": entry["asset"],
            "asset_name": entry["asset_name"],
            "asset_type": entry["asset_type"],
            "date_com": entry["date_com"],
            "last_dividend_value": entry["last_dividend_value"],
            "details_url": entry["details_url"],
        }
        for entry in filtered_results
    ]

    return jsonify(sorted_results)


def _collect_dividend_info(table_element) -> Optional[tuple[str, Optional[str]]]:
    dates: List[datetime] = []
    latest_value: Optional[str] = None
    for row in table_element.find_elements(By.CSS_SELECTOR, "tbody tr"):
        cells = row.find_elements(By.TAG_NAME, "td")
        if len(cells) < 2:
            continue
        try:
            dividend_date = datetime.strptime(cells[1].text.strip(), "%d/%m/%Y")
            dates.append(dividend_date)
            if len(cells) > 2 and not latest_value:
                latest_value = cells[2].text.strip()
        except Exception:
            continue
    if not dates:
        return None
    latest = max(dates).strftime("%d/%m/%Y")
    return latest, latest_value


def resolve_asset_url(code: str, table_name: str) -> Optional[str]:
    slug = code.lower()
    path = _resolve_asset_path(table_name)
    if path is None:
        return None
    return f"https://investidor10.com.br/{path}/{slug}/"


def _normalize_asset_type(table_name: str) -> str:
    primary = table_name.split("\n")[0].upper()
    if table_name == "assets":
        return "Ações"
    if primary == "FIIS":
        return "Fundos Imobiliários"
    if primary.startswith("CRIPTOMOEDAS"):
        return "Criptomoedas"
    if primary.startswith("ETFS INTERN"):
        return "ETFs Internacionais"
    if primary.startswith("ETFS"):
        return "ETFs"
    if primary.startswith("STOCKS"):
        return "Stocks"
    if primary.startswith("BDRS"):
        return "BDRs"
    return "Desconhecido"


def _resolve_asset_path(table_name: str) -> Optional[str]:
    if table_name == "assets":
        return "acoes"
    primary = table_name.split("\n")[0].upper()
    if primary == "FIIS":
        return "fiis"
    if primary.startswith("CRIPTOMOEDAS"):
        return "criptomoedas"
    if primary.startswith("ETFS INTERN"):
        return "etfs-global"
    if primary.startswith("ETFS"):
        return "etfs"
    if primary.startswith("STOCKS"):
        return "stocks"
    if primary.startswith("BDRS"):
        return "bdrs"
    return None
