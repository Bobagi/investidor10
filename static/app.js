if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/service-worker.js');
    });
}

async function callApi(endpoint, params) {
    const loader = document.getElementById('loader');
    const output = document.getElementById('output');
    loader.classList.remove('hidden');
    output.textContent = '';
    try {
        const url = new URL(endpoint, window.location.origin);
        Object.keys(params).forEach(k => url.searchParams.append(k, params[k]));
        const response = await fetch(url);
        const text = await response.text();
        output.textContent = text;
    } catch (e) {
        output.textContent = 'Erro: ' + e;
    } finally {
        loader.classList.add('hidden');
    }
}

document.getElementById('assetsBtn').addEventListener('click', () => {
    callApi('/assets', {wallet_url: document.getElementById('walletUrl').value});
});

document.getElementById('entriesBtn').addEventListener('click', () => {
    callApi('/wallet-entries', {wallet_entries_url: document.getElementById('walletEntriesUrl').value});
});

document.getElementById('dataComBtn').addEventListener('click', () => {
    callApi('/data-com', {wallet_url: document.getElementById('walletUrl').value});
});
