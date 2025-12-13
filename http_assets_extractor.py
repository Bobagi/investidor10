import importlib
import re
from typing import List, Optional, Dict

import requests

DEFAULT_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://investidor10.com.br/",
    "Connection": "keep-alive",
}


def extract_assets_via_http(wallet_url: str) -> List[Dict[str, str]]:
    html_content = fetch_wallet_html(wallet_url)
    return build_assets_from_static_html(html_content)


def fetch_wallet_html(wallet_url: str) -> str:
    response = requests.get(
        wallet_url,
        timeout=30,
        headers=DEFAULT_REQUEST_HEADERS,
    )
    if response.status_code == 403:
        raise requests.HTTPError("Forbidden while fetching wallet HTML", response=response)
    response.raise_for_status()
    return response.text


def build_assets_from_static_html(html_content: str) -> List[Dict[str, str]]:
    beautiful_soup_constructor = load_beautiful_soup_constructor()
    if beautiful_soup_constructor is None:
        print("BeautifulSoup not available. Skipping HTTP asset parsing.")
        return []

    soup = beautiful_soup_constructor(html_content, "html.parser")
    collected_tables: List[Dict[str, str]] = []

    primary_table = soup.select_one("table")
    if primary_table:
        collected_tables.append(
            build_table_payload("assets", primary_table)
        )

    toggle_elements = soup.find_all(
        lambda tag: tag.has_attr("onclick") and "MyWallets.toogleClass" in tag.get("onclick", "")
    )

    for toggle_element in toggle_elements:
        table_name = extract_table_name(toggle_element)
        if "AÇÕES" in table_name.upper():
            continue

        selector = extract_selector(toggle_element.get("onclick", ""))
        if selector is None:
            collected_tables.append(
                {"table_name": table_name, "error": "Could not identify target selector"}
            )
            continue

        table_container = soup.select_one(selector)
        if table_container is None:
            collected_tables.append(
                {"table_name": table_name, "error": "Target selector not found in static HTML"}
            )
            continue

        table_tag = table_container.find("table")
        if table_tag is None:
            collected_tables.append(
                {"table_name": table_name, "error": "No table element found for selector"}
            )
            continue

        collected_tables.append(build_table_payload(table_name, table_tag))

    return collected_tables


def build_table_payload(table_name: str, table_tag) -> Dict[str, str]:
    header = parse_table_header_from_soup(table_tag)
    rows = parse_table_rows_from_soup(table_tag)
    return {
        "table_name": table_name,
        "header": header,
        "rows": rows,
    }


def parse_table_header_from_soup(table_tag) -> str:
    header_cells = table_tag.select("thead tr th")
    header_values = [cell.get_text(strip=True) for cell in header_cells if cell.get_text(strip=True)]
    return " | ".join(header_values)


def parse_table_rows_from_soup(table_tag) -> List[str]:
    parsed_rows: List[str] = []
    for row in table_tag.select("tbody tr"):
        cell_values = [cell.get_text(strip=True) for cell in row.find_all("td") if cell.get_text(strip=True)]
        if cell_values:
            parsed_rows.append(" | ".join(cell_values))
    return parsed_rows


def extract_table_name(toggle_element) -> str:
    name_element = toggle_element.find(class_="name_value")
    if name_element is None:
        return "Unknown Table"
    return name_element.get_text(strip=True) or "Unknown Table"


def extract_selector(onclick_value: str) -> Optional[str]:
    match = re.search(r"toogleClass\\\('([^']+)'", onclick_value)
    if not match:
        return None
    return match.group(1)


def load_beautiful_soup_constructor():
    beautiful_soup_spec = importlib.util.find_spec("bs4")
    if beautiful_soup_spec is None:
        return None

    bs4_module = importlib.import_module("bs4")
    return getattr(bs4_module, "BeautifulSoup", None)
