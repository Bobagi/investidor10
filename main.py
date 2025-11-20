import sys
from flask import Flask, jsonify, request, render_template
from flasgger import Swagger
from flask_cors import CORS
from wallet_entries import extract_wallet_entries
from utils import setup_driver
from services.assets_service import fetch_latest_data_com, retrieve_wallet_assets

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
    """Retrieve wallet asset tables with richer context.
    ---
    parameters:
      - name: wallet_url
        in: query
        type: string
        required: true
    responses:
      200:
        description: Structured data for wallet assets, including table headers and rows.
    """
    if wallet_url is None:
        payload = request.get_json(silent=True) or request.args
        if "wallet_url" not in payload:
            return jsonify({"error": "wallet_url parameter not provided"}), 400
        wallet_url = payload["wallet_url"]

    try:
        assets_tables = retrieve_wallet_assets(wallet_url)
        if not jsonfy_return:
            return assets_tables

        formatted_tables = []
        for table in assets_tables:
            header_str = table.get("header", "")
            rows_list = table.get("rows", [])
            header = header_str.split(" | ") if header_str else []
            rows = [row.split(" | ") for row in rows_list]
            formatted_tables.append(
                {
                    "table_name": table.get("table_name", ""),
                    "header": header,
                    "rows": rows,
                    "error": table.get("error"),
                }
            )
        return jsonify({"tables": formatted_tables})
    except Exception as raw_error:
        return jsonify({"error": str(raw_error)}), 500

@app.route("/data-com", methods=["GET"])
def get_data_com():
    """Get enriched dividend calendar for wallet assets.
    ---
    parameters:
      - name: wallet_url
        in: query
        type: string
        required: true
    responses:
      200:
        description: Upcoming dividend dates with asset type, name and last dividend value.
    """
    data = request.get_json(silent=True) or request.args
    if "wallet_url" not in data:
        return jsonify({"error": "wallet_url parameter not provided"}), 400

    try:
        assets_data = get_assets(data["wallet_url"], False)
        if isinstance(assets_data, tuple):
            return assets_data
        return fetch_latest_data_com(assets_data)
    except Exception as raw_error:
        return jsonify({"error": str(raw_error)}), 500

@app.route("/test", methods=["GET"])
def test():
    """Simple health check endpoint."""
    return jsonify({"message": "Test successful"})

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000
    )
