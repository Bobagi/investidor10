import datetime
from typing import List

import requests

from http_assets_extractor import DEFAULT_REQUEST_HEADERS, load_beautiful_soup_constructor


def extract_dividend_dates_via_http(asset_url: str) -> List[datetime.date]:
    page_html = _download_asset_page_html(asset_url)
    if not page_html:
        return []

    beautiful_soup_constructor = load_beautiful_soup_constructor()
    if beautiful_soup_constructor is None:
        return []

    soup = beautiful_soup_constructor(page_html, "html.parser")
    dividends_table = soup.find(id="table-dividends-history")
    if dividends_table is None:
        return []

    parsed_dates: List[datetime.date] = []
    for row in dividends_table.select("tbody tr"):
        date_cells = row.find_all("td")
        if len(date_cells) < 2:
            continue
        parsed_date = _parse_brazilian_date(date_cells[1].get_text(strip=True))
        if parsed_date:
            parsed_dates.append(parsed_date)
    return parsed_dates


def _download_asset_page_html(asset_url: str) -> str:
    response = requests.get(asset_url, headers=DEFAULT_REQUEST_HEADERS, timeout=30)
    response.raise_for_status()
    return response.text


def _parse_brazilian_date(date_value: str) -> datetime.date | None:
    try:
        return datetime.datetime.strptime(date_value, "%d/%m/%Y").date()
    except Exception:
        return None
