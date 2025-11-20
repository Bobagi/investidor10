# Painel de Insights da API Investidor10

This project exposes a small Flask API that extracts data from public wallets on [Investidor10](https://investidor10.com.br/). You must have a publicly available wallet URL in order to use the endpoints. The API now retorna informações estruturadas por tipo de ativo e inclui detalhes adicionais na rota de datas‑com.

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

Fetch detailed order history from a wallet entries page (todas as tabelas paginadas de ordens, com o tipo da ordem prefixado em cada linha).
Parameters:

- `wallet_entries_url` – full URL to the wallet entries page on Investidor10.

### `GET /assets`

Extract every asset table from a wallet page. Each returned table now inclui:

- `table_name` – título exibido na carteira (ex.: Ações, FIIs, BDRs).
- `header` – lista de colunas na ordem apresentada pela carteira.
- `rows` – valores em formato de lista, preservando a ordem das colunas.
- `structured_rows` – linhas como dicionários `coluna -> valor` para facilitar consumo programático.
- `error` – mensagem de erro caso a tabela não seja acessível.

Parameters:

- `wallet_url` – full URL to the public wallet on Investidor10.

### `GET /data-com`

Retrieve the upcoming ex-dividend dates for each asset in the wallet, enriched with metadata:

- `asset` e `asset_name` – código e nome (quando disponível) do ativo.
- `asset_type` – classificação derivada da tabela (Ação, FII, ETF, Criptomoeda, etc.).
- `wallet_table` – nome da tabela de origem na carteira.
- `asset_url` – link direto para a página do ativo no Investidor10.
- `date_com` – próxima data‑com encontrada.
- `dividend_details` – linha completa da tabela de histórico de dividendos para referência.

Parameters:

- `wallet_url` – full URL to the public wallet on Investidor10.

### `GET /test`

Simple health‑check endpoint returning a confirmation message.

## Notes

Selenium is used under the hood with estratégia de carregamento "eager" para reduzir o tempo de scraping. Mesmo assim, páginas mais pesadas podem levar alguns segundos para serem carregadas.
