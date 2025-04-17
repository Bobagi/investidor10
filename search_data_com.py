import time
from datetime import datetime
import requests
from selenium.webdriver.common.by import By
from utils import setup_driver, extract_table_header, extract_table_data

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

def fetch_latest_data_com(wallet_url: str, api_port: int = 5000) -> dict:
    resp = requests.get(
        f"http://localhost:{api_port}/assets",
        params={"wallet_url": wallet_url},
        timeout=300
    )
    resp.raise_for_status()
    assets_json = resp.json()
    driver = setup_driver()
    result = {}
    try:
        tables = []
        main = assets_json.get('assets_table', {})
        if main:
            tables.append({
                'table_name': 'assets',
                'header': main['header'].split(' | '),
                'rows': [r.split(' | ') for r in main['rows']]
            })
        for tbl in assets_json.get('collapsed_tables', []):
            hdr = tbl.get('header', '')
            rows = tbl.get('rows', [])
            tables.append({
                'table_name': tbl.get('table_name', ''),
                'header': hdr.split(' | '),
                'rows': [r.split(' | ') for r in rows]
            })
        for tbl in tables:
            if 'Data Com' not in tbl['header']:
                continue
            for row in tbl['rows']:
                code = row[0]
                detail_url = resolve_asset_url(code, tbl['table_name'])
                if not detail_url:
                    continue
                driver.get(detail_url)
                time.sleep(3)
                for table in driver.find_elements(By.TAG_NAME, 'table'):
                    cols = extract_table_header(table).split(' | ')
                    if 'Data Com' in cols:
                        data_rows = extract_table_data(table)
                        dates = []
                        for dr in data_rows:
                            try:
                                d = datetime.strptime(
                                    dr[cols.index('Data Com')], '%d/%m/%Y'
                                )
                                dates.append(d)
                            except:
                                pass
                        if dates:
                            result[code] = max(dates).strftime('%d/%m/%Y')
                        break
    finally:
        driver.quit()
    return result
