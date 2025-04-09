from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
import time, os
from dotenv import load_dotenv
import sys
sys.stdout.reconfigure(line_buffering=True)

load_dotenv()

EMAIL = os.getenv("INVESTIDOR10_EMAIL")
PASSWORD = os.getenv("INVESTIDOR10_PASSWORD")

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


def login_investidor10(driver):
    print("Tentando realizar login no Investidor10...")
    try:
        driver.set_page_load_timeout(10)
        driver.get("https://investidor10.com.br/login/")
        print("Página de login carregada.")

        driver.save_screenshot("login_page.png")
        driver.find_element(By.NAME, "email").send_keys(EMAIL)
        driver.find_element(By.NAME, "password").send_keys(PASSWORD)
        driver.find_element(By.CSS_SELECTOR, "form button[type='submit']").click()
        print("Login realizado (formulário enviado).")
    except Exception as e:
        print("Erro ao tentar fazer login:", e)


def extrair_lancamentos(driver):
    print("Acessando página da carteira...")
    driver.get("https://investidor10.com.br/carteira")
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
        login_investidor10(driver)
        extrair_lancamentos(driver)
    except Exception as e:
        print("Erro geral na aplicação:", e)
    finally:
        driver.quit()
        print("Finalizando aplicação, navegador encerrado.")

if __name__ == "__main__":
    main()
