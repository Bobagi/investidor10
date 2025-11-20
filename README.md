# Coletor rápido de dados públicos do Investidor10

This project exposes a small Flask API that extracts data from public wallets on [Investidor10](https://investidor10.com.br/). You must have a publicly available wallet URL in order to use the endpoints.

## Requirements

- Python 3.11
- Google Chrome and ChromeDriver (already installed when using the provided `Dockerfile`)
- An Investidor10 account with a public wallet URL

All Python dependencies are listed in `requirements.txt`.

## Running

You can run the API directly with Python or use Docker:

```bash
# direct execution
python main.py

# using Docker
docker compose up
```

After starting, Swagger UI is available at `http://localhost:5000/apidocs`.

## Endpoints

### `GET /wallet-entries`

Fetch detailed order history from a wallet entries page.
Parameters:

- `wallet_entries_url` – full URL to the wallet entries page on Investidor10.

### `GET /assets`

Extract asset tables from a wallet page. Besides returning column headers and rows, the response now normalizes grouped tables (FIIs, ETFs, BDRs, etc.) so that each table is easier to consume programmatically.

Parameters:

- `wallet_url` – full URL to the public wallet on Investidor10.

### `GET /data-com`

Retrieve the upcoming ex-dividend dates for the assets in the wallet. The endpoint now enriches each result with the asset type, friendly name (when available), the most recent dividend value and a direct link to the asset page used for scraping.

Parameters:

- `wallet_url` – full URL to the public wallet on Investidor10.

### `GET /test`

Simple health‑check endpoint returning a confirmation message.

## Notes

Selenium is used under the hood, so requests may take some time while the pages are loaded and scraped.
