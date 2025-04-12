from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
import time, os
from dotenv import load_dotenv
import sys
sys.stdout.reconfigure(line_buffering=True)

load_dotenv()

# Agora a URL da carteira vem da variável de ambiente "WALLET_URL"
WALLET_URL = os.getenv("WALLET_URL")
if not WALLET_URL:
    raise Exception("A variável de ambiente WALLET_URL não foi definida.")

def setup_driver():
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--remote-debugging-port=9222')

    # Utilizando Chrome Headless Shell:
    options.binary_location = "/usr/bin/google-chrome"
    
    service = Service(executable_path="/usr/local/bin/chromedriver")
    return webdriver.Chrome(service=service, options=options)

def extrair_lancamentos(driver, url):
    print("Acessando carteira...")
    driver.get(url)
    time.sleep(5)

    rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
    if not rows:
        print("Nenhum lançamento encontrado ou tabela não carregada.")
        return

    print(f"{len(rows)} lançamentos encontrados:")
    for row in rows:
        cols = row.find_elements(By.TAG_NAME, "td")
        dados = [col.text.strip() for col in cols]
        print(" | ".join(dados))

def main():
    print("Iniciando aplicação Investidor10 Bot...")
    driver = setup_driver()
    try:
        extrair_lancamentos(driver, WALLET_URL)
    except Exception as e:
        print("Erro geral na aplicação:", e)
    finally:
        driver.quit()
        print("Finalizando aplicação, navegador encerrado.")

if __name__ == "__main__":
    main()
