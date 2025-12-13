# Resumo das Alterações Recentes

## Extração de ativos via HTTP
- Criada a rota de extração que primeiro tenta baixar o HTML diretamente com `requests` usando cabeçalhos de navegador e validação explícita de respostas proibidas (403) antes de processar.
- O HTML é processado com BeautifulSoup para coletar a tabela principal e as tabelas colapsadas de ativos, com verificações de seletor e mensagens de erro claras quando estruturas esperadas não estão presentes.
- Caso o módulo `bs4` não esteja disponível ou o HTML não contenha linhas utilizáveis, o fluxo abandona a abordagem HTTP e registra a queda para o Selenium.

## Fallback garantido para Selenium/Chromium
- Quando a extração HTTP não encontra linhas válidas, o sistema executa automaticamente o scraping com Selenium/Chromium para recuperar os dados completos.
- A resolução de datas de "data-com" continua usando Selenium para navegar até as páginas de cada ativo e coletar o histórico de dividendos.
- Portanto, o Chromium **não foi removido**; ele permanece como mecanismo de fallback e para as operações que dependem de navegação dinâmica.

## Ajustes de tempo de execução
- O tempo limite da interface foi restaurado para 1200 segundos, acomodando operações de scraping mais longas sem encerrar prematuramente as requisições.

## Conformidade e robustez
- Incluído `beautifulsoup4` nas dependências para permitir o parsing estático.
- Melhorados logs para facilitar o diagnóstico de sucessos e quedas de HTTP para Selenium.
