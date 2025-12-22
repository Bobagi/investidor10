import re
import sys
import time
from datetime import date, datetime
from typing import Dict, List, Optional
from threading import Thread

from flask import Flask, jsonify, render_template, request
from flasgger import Swagger
from flask_cors import CORS
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from http_assets_extractor import extract_assets_via_http
from http_dividends_extractor import extract_dividend_dates_via_http
from data_com_jobs import DataComJobStore, DividendDateCache, DataComJobProgressUpdater
from utils import extract_table_data, extract_table_header, setup_driver
from wallet_entries import extract_wallet_entries

sys.stdout.reconfigure(line_buffering=True)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": [
    "http://localhost:8080", "https://localhost:8080"
]}})
Swagger(app)

DATA_COM_JOB_STORE = DataComJobStore()
DIVIDEND_DATE_CACHE = DividendDateCache(ttl_seconds=6 * 60 * 60)


class ProcessingTimeoutError(Exception):
    """Raised when the processing budget is exceeded."""


class TimeBudget:
    """Manages a time budget for long-running tasks."""

    def __init__(self, total_seconds: float):
        safe_seconds = total_seconds if total_seconds > 0 else 60
        self.deadline = time.monotonic() + safe_seconds

    def remaining_seconds(self) -> float:
        return max(0.0, self.deadline - time.monotonic())

    def ensure_time_available(self, minimum_required: float, context: str) -> None:
        if self.remaining_seconds() < minimum_required:
            raise ProcessingTimeoutError(f"Tempo limite atingido ao processar {context}.")

    def clamp_timeout(self, requested_seconds: float) -> float:
        remaining = self.remaining_seconds()
        if remaining <= 0:
            raise ProcessingTimeoutError("Tempo limite atingido.")
        return max(1.0, min(requested_seconds, remaining))


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


def _extract_timeout_seconds(data: Dict[str, object]) -> float:
    try:
        raw_timeout = float(data.get("timeout_seconds", 60))
    except (TypeError, ValueError):
        return 60
    return max(5.0, min(raw_timeout, 55.0))


def _resolve_wait_seconds(time_budget: Optional[TimeBudget], requested_seconds: float) -> float:
    if time_budget is None:
        return requested_seconds
    return time_budget.clamp_timeout(requested_seconds)


def _ensure_time_budget_available(
    time_budget: Optional[TimeBudget],
    minimum_required: float,
    context: str,
) -> None:
    if time_budget is None:
        return
    time_budget.ensure_time_available(minimum_required, context)


def _resolve_driver_timeouts(
    time_budget: Optional[TimeBudget],
    page_load_seconds: float,
    script_timeout_seconds: float,
) -> tuple[float, float]:
    if time_budget is None:
        return page_load_seconds, script_timeout_seconds
    return (
        time_budget.clamp_timeout(page_load_seconds),
        time_budget.clamp_timeout(script_timeout_seconds),
    )

def extract_assets_data(driver, url, time_budget: Optional[TimeBudget] = None):
    collapsed_tables = []
    page_load_timeout, script_timeout = _resolve_driver_timeouts(time_budget, 25, 25)
    driver.set_page_load_timeout(page_load_timeout)
    driver.set_script_timeout(script_timeout)
    driver.get(url)
    try:
        wait_seconds = _resolve_wait_seconds(time_budget, 20)
        WebDriverWait(driver, wait_seconds).until(
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
        _ensure_time_budget_available(time_budget, 4, "a leitura de grupos de ativos")
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
                wait_seconds = _resolve_wait_seconds(time_budget, 15)
                WebDriverWait(driver, wait_seconds).until(
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
    request_payload = request.get_json(silent=True) or request.args
    if wallet_url is None:
        if "wallet_url" not in request_payload:
            return jsonify({"error": "wallet_url parameter not provided"}), 400
        wallet_url = request_payload["wallet_url"]
        
    try:
        timeout_seconds = _extract_timeout_seconds(request_payload)
        time_budget = TimeBudget(timeout_seconds)
        result = collect_assets_tables(wallet_url, time_budget)
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
        return result
    except ProcessingTimeoutError as timeout_error:
        return jsonify({"error": str(timeout_error)}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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

    should_run_async = _extract_async_preference(data)
    if should_run_async:
        job_id = start_data_com_job(
            wallet_url=data["wallet_url"],
            timeout_seconds=_extract_timeout_seconds(data),
        )
        return jsonify({
            "job_id": job_id,
            "status": "pending"
        })

    timeout_seconds = _extract_timeout_seconds(data)
    time_budget = TimeBudget(timeout_seconds)

    try:
        print("Executing get_data_com...")
        tables = collect_assets_tables(data["wallet_url"], time_budget)
        print("Data returned!")
    except ProcessingTimeoutError as timeout_error:
        return jsonify({"error": str(timeout_error)}), 504
    except Exception as exception_info:
        return jsonify({"error": str(exception_info)}), 500

    try:
        print("Executing fetch_latest_data_com...")
        results_payload = build_data_com_payload(tables, time_budget, DIVIDEND_DATE_CACHE)
        print("fetch_latest_data_com RETURNED!!: ", results_payload)
        return jsonify(results_payload)
    except ProcessingTimeoutError as timeout_error:
        return jsonify({"error": str(timeout_error)}), 504
    except Exception as exception_info:
        return jsonify({"error": str(exception_info)}), 500


@app.route("/data-com/status", methods=["GET"])
def get_data_com_status():
    data = request.get_json(silent=True) or request.args
    if "job_id" not in data:
        return jsonify({"error": "job_id parameter not provided"}), 400
    job = DATA_COM_JOB_STORE.get_job(data["job_id"])
    if job is None:
        return jsonify({"error": "job_id not found"}), 404
    payload = {
        "job_id": data["job_id"],
        "status": job.status,
        "results": job.results,
        "failures": job.failures,
        "error_message": job.error_message,
        "total_assets": job.total_assets,
        "processed_assets": job.processed_assets,
        "current_asset": job.current_asset,
        "last_message": job.last_message,
    }
    return jsonify(payload)


def start_data_com_job(wallet_url: str, timeout_seconds: float) -> str:
    job_id = DATA_COM_JOB_STORE.create_job()

    def run_job() -> None:
        time_budget = TimeBudget(timeout_seconds)
        try:
            print(f"[data-com][job {job_id}] Iniciando coleta de ativos para {wallet_url}.")
            tables = collect_assets_tables(wallet_url, time_budget)
            total_assets = count_assets_in_tables(tables)
            progress_updater = DataComJobProgressUpdater(
                DATA_COM_JOB_STORE,
                job_id,
                total_assets,
            )
            progress_updater.mark_running()
            results_payload = build_data_com_payload(
                tables,
                time_budget,
                DIVIDEND_DATE_CACHE,
                progress_updater,
            )
            progress_updater.mark_completed(
                results_payload["results"],
                results_payload["failures"],
            )
        except ProcessingTimeoutError as timeout_error:
            DataComJobProgressUpdater(DATA_COM_JOB_STORE, job_id, 0).mark_failed(str(timeout_error))
        except Exception as exception_info:
            DataComJobProgressUpdater(DATA_COM_JOB_STORE, job_id, 0).mark_failed(str(exception_info))

    Thread(target=run_job, daemon=True).start()
    return job_id


def build_data_com_payload(
    assets_json,
    time_budget: TimeBudget,
    dividend_date_cache: DividendDateCache,
    progress_updater: Optional[DataComJobProgressUpdater] = None,
) -> Dict[str, List[Dict[str, str]]]:
    tables = _normalize_tables_payload(assets_json)
    if tables is None:
        return {"results": [], "failures": [{"asset": "-", "reason": "invalid input format"}]}

    selenium_driver = None
    results: List[Dict[str, object]] = []
    failures: List[Dict[str, str]] = []
    processed_assets = 0

    for table_payload in tables:
        table_name = table_payload.get('table_name', '')
        for raw_row in table_payload.get('rows', []):
            row = raw_row.split(' | ') if isinstance(raw_row, str) else raw_row
            if not row:
                continue
            asset_code = row[0]
            latest_dividend_date, failure_reason, selenium_driver = _resolve_latest_dividend_date_for_asset(
                asset_code,
                table_name,
                time_budget,
                selenium_driver,
                dividend_date_cache,
            )
            if latest_dividend_date:
                results.append({
                    'asset': asset_code,
                    'date_com_date': latest_dividend_date
                })
            if failure_reason:
                failures.append({
                    'asset': asset_code,
                    'reason': failure_reason
                })
            processed_assets += 1
            if progress_updater:
                progress_message = (
                    f"Ativo {asset_code} processado."
                    if not failure_reason
                    else f"Ativo {asset_code} processado com falha."
                )
                progress_updater.report_progress(
                    processed_assets,
                    asset_code,
                    _format_results_snapshot(results),
                    failures,
                    progress_message,
                )

    if selenium_driver:
        selenium_driver.quit()

    filtered_results = _filter_and_sort_dividend_dates(results)
    formatted_results = [
        {'asset': item['asset'], 'date_com': item['date_com_date'].strftime('%d/%m/%Y')}
        for item in filtered_results
    ]

    return {
        'results': formatted_results,
        'failures': failures
    }


def _format_results_snapshot(results: List[Dict[str, object]]) -> List[Dict[str, str]]:
    formatted_results: List[Dict[str, str]] = []
    for result_item in results:
        date_value = result_item.get('date_com_date')
        asset_code = result_item.get('asset')
        if isinstance(date_value, date) and isinstance(asset_code, str):
            formatted_results.append({
                'asset': asset_code,
                'date_com': date_value.strftime('%d/%m/%Y')
            })
    return formatted_results


def _resolve_latest_dividend_date_for_asset(
    asset_code: str,
    table_name: str,
    time_budget: TimeBudget,
    selenium_driver: object | None,
    dividend_date_cache: DividendDateCache,
) -> tuple[date | None, str | None, object | None]:
    try:
        time_budget.ensure_time_available(3, f"o ativo {asset_code}")
    except ProcessingTimeoutError as timeout_error:
        return None, str(timeout_error), selenium_driver

    asset_url = resolve_asset_url(asset_code, table_name)
    print(f"Resolving URL for {asset_code}: {asset_url}")
    if not asset_url:
        return None, f"URL do ativo {asset_code} não pôde ser resolvida.", selenium_driver

    cached_date = dividend_date_cache.get(asset_url)
    if cached_date:
        return cached_date, None, selenium_driver

    try:
        latest_dividend_date = _extract_latest_dividend_date(asset_url, time_budget)
    except ProcessingTimeoutError as timeout_error:
        return None, str(timeout_error), selenium_driver

    if latest_dividend_date is None:
        selenium_driver = selenium_driver or setup_driver()
        try:
            latest_dividend_date = _extract_latest_dividend_date_with_selenium(
                selenium_driver, asset_url, asset_code, time_budget
            )
        except ProcessingTimeoutError as timeout_error:
            return None, str(timeout_error), selenium_driver
        except Exception as selenium_error:
            return (
                None,
                f"Falha ao ler dividendos via Selenium para {asset_code}: {selenium_error}",
                selenium_driver,
            )

    if latest_dividend_date is None:
        return None, f"Nenhuma data de dividendo encontrada para {asset_code}.", selenium_driver

    if latest_dividend_date:
        dividend_date_cache.set(asset_url, latest_dividend_date)

    return latest_dividend_date, None, selenium_driver


def _extract_async_preference(data: Dict[str, object]) -> bool:
    raw_value = data.get("async", "true")
    if isinstance(raw_value, str):
        return raw_value.strip().lower() not in {"false", "0", "no"}
    if isinstance(raw_value, bool):
        return raw_value
    return True


def count_assets_in_tables(assets_json) -> int:
    tables = _normalize_tables_payload(assets_json)
    if not tables:
        return 0
    total_assets = 0
    for table_payload in tables:
        for raw_row in table_payload.get('rows', []):
            row = raw_row.split(' | ') if isinstance(raw_row, str) else raw_row
            if row and row[0]:
                total_assets += 1
    return total_assets


def _normalize_tables_payload(assets_json) -> List[Dict[str, object]] | None:
    if isinstance(assets_json, dict):
        return assets_json.get('tables', [])
    if isinstance(assets_json, list):
        return assets_json
    return None


def _extract_latest_dividend_date(asset_url: str, time_budget: TimeBudget) -> date | None:
    try:
        http_timeout = time_budget.clamp_timeout(15)
        dividend_dates = extract_dividend_dates_via_http(asset_url, http_timeout)
    except ProcessingTimeoutError:
        raise
    except Exception as http_error:
        print(f"HTTP dividend extraction failed for {asset_url}: {http_error}")
        return None

    if not dividend_dates:
        return None

    return max(dividend_dates)


def _extract_latest_dividend_date_with_selenium(
    driver,
    asset_url: str,
    asset_code: str,
    time_budget: TimeBudget,
) -> date | None:
    try:
        page_load_timeout, script_timeout = _resolve_driver_timeouts(time_budget, 20, 20)
        driver.set_page_load_timeout(page_load_timeout)
        driver.set_script_timeout(script_timeout)
        max_wait = time_budget.clamp_timeout(15)
        driver.get(asset_url)
        WebDriverWait(driver, max_wait).until(
            EC.presence_of_element_located((By.ID, 'table-dividends-history'))
        )
    except ProcessingTimeoutError:
        raise
    except TimeoutException:
        print(f"Timeout while waiting for dividends history for {asset_code}.")
        return None

    for attempt_number in range(3):
        time_budget.ensure_time_available(3, f"a leitura de dividendos de {asset_code}")
        try:
            dividends_history_table = driver.find_element(By.ID, 'table-dividends-history')
        except NoSuchElementException:
            print(f"Table not found for {asset_code}.")
            return None

        try:
            selenium_dates = _collect_dividend_dates_from_table(dividends_history_table)
            if not selenium_dates:
                return None

            print(f"Dates found for {asset_code}: {selenium_dates}")
            return max(selenium_dates)
        except StaleElementReferenceException:
            remaining_attempts = 2 - attempt_number
            print(
                f"Stale element encountered while reading dividends for {asset_code}. "
                f"Retrying ({remaining_attempts} attempts left)."
            )
            remaining_wait = time_budget.clamp_timeout(5)
            WebDriverWait(driver, remaining_wait).until(
                EC.presence_of_element_located((By.ID, 'table-dividends-history'))
            )

    print(f"Unable to read dividends table for {asset_code} after retries.")
    return None


def _collect_dividend_dates_from_table(dividends_table: WebElement) -> List[date]:
    selenium_dates: List[date] = []
    for dividends_row in dividends_table.find_elements(By.CSS_SELECTOR, 'tbody tr'):
        cells = dividends_row.find_elements(By.TAG_NAME, 'td')
        if len(cells) < 2:
            continue
        parsed_date = _parse_brazilian_date(cells[1].text.strip())
        if parsed_date:
            selenium_dates.append(parsed_date)
    return selenium_dates


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


def collect_assets_tables(wallet_url: str, time_budget: Optional[TimeBudget] = None):
    driver = None
    try:
        assets_via_http = []
        try:
            http_timeout = time_budget.clamp_timeout(15) if time_budget else 30
            assets_via_http = extract_assets_via_http(wallet_url, http_timeout)
        except ProcessingTimeoutError:
            raise
        except Exception as extraction_error:
            print(f"HTTP assets extraction failed: {extraction_error}")

        if contains_usable_asset_rows(assets_via_http):
            return assets_via_http

        if assets_via_http:
            print("HTTP assets extraction returned no usable rows. Falling back to Selenium scraping.")

        if time_budget:
            time_budget.ensure_time_available(10, "coleta via Selenium")
        page_load_timeout, script_timeout = _resolve_driver_timeouts(time_budget, 25, 25)
        driver = setup_driver(page_load_timeout, script_timeout)
        return extract_assets_data(driver, wallet_url, time_budget)
    finally:
        if driver:
            driver.quit()

@app.route("/test", methods=["GET"])
def test():
    """Simple health check endpoint."""
    return jsonify({"message": "Test successful"})

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000
    )
