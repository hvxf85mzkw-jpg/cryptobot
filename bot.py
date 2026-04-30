import requests, feedparser, time, json, os
from datetime import datetime

TELEGRAM_TOKEN = "8764281464:AAFT9UM0M4Wd6Z_8DQ8A5XOO5xaPhChKGMw"
CHAT_ID = "1020078682"
GROQ_KEY = os.environ.get("GROQ_KEY")
HEADERS = {"User-Agent": "Mozilla/5.0"}
STORICO_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "storico_segnali.json")

ultimo_riassunto_giornaliero = ""
segnali_giornalieri = []
ultimo_segnale_testo = ""
ultimo_update_id = 0

def manda_messaggio(testo):
    global ultimo_segnale_testo
    if "BUY" in testo or "SELL" in testo or "SEGNALE" in testo.upper():
        ultimo_segnale_testo = testo
    url = "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": testo, "parse_mode": "HTML"})

def salva_segnale(token, segnale, target, stoploss, durata):
    storico = []
    if os.path.exists(STORICO_FILE):
        with open(STORICO_FILE, "r") as f:
            storico = json.load(f)
    storico.append({"data": datetime.now().strftime("%Y-%m-%d"), "token": token, "segnale": segnale, "target": target, "stoploss": stoploss, "durata": durata, "verificato": False})
    with open(STORICO_FILE, "w") as f:
        json.dump(storico, f)

def get_prezzo(token):
    simboli = {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "BNB": "binancecoin", "ADA": "cardano", "XRP": "ripple", "DOGE": "dogecoin", "MATIC": "matic-network"}
    nome = simboli.get(token.upper(), token.lower())
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=" + nome + "&vs_currencies=usd", timeout=10)
        return r.json()[nome]["usd"]
    except:
        return None

def analizza_news(titolo, tipo):
    if tipo == "whale":
        prompt = "Sei un trader crypto aggressivo. Analizza questo movimento di balena. Se non e significativo rispondi solo: IGNORA. Se importante rispondi ESATTAMENTE cosi:\nSEGNALE: COMPRA o VENDI\nTOKEN: simbolo\nRISCHIO: Basso o Medio o Alto\nDURATA: es 2 settimane\nTARGET: es +20%\nSTOP LOSS: es -10%\nMOTIVO: 4-5 righe, spiega bene cosa significa questo movimento di balena, come impatta il mercato e cosa dovrebbe fare il trader\n\nMovimento: " + titolo
    else:
        prompt = "Sei un trader crypto aggressivo. Utente investe a lungo termine 1-4 settimane con 100 CHF, vuole rendimenti alti. Se la news non conta rispondi solo: IGNORA. Se importante rispondi ESATTAMENTE cosi:\nSEGNALE: COMPRA o VENDI o NEUTRO\nTOKEN: simbolo\nRISCHIO: Basso o Medio o Alto\nDURATA: es 2 settimane\nTARGET: es +20%\nSTOP LOSS: es -10%\nMOTIVO: 4-5 righe, spiega bene perche questa news impatta il token, cosa potrebbe succedere al prezzo e perche e un buon momento per entrare o uscire\n\nNews: " + titolo
    r = requests.post("https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": "Bearer " + GROQ_KEY, "Content-Type": "application/json"},
        json={"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": prompt}], "max_tokens": 300})
    data = r.json()
    if "choices" in data:
        return data["choices"][0]["message"]["content"]
    return "IGNORA"

def formatta_segnale(titolo, analisi, fonte, tipo):
    righe = analisi.strip().split("\n")
    segnale = token = rischio = durata = target = stoploss = motivo = ""
    for riga in righe:
        if "SEGNALE:" in riga: segnale = riga.split(":",1)[1].strip()
        elif "TOKEN:" in riga: token = riga.split(":",1)[1].strip()
        elif "RISCHIO:" in riga: rischio = riga.split(":",1)[1].strip()
        elif "DURATA:" in riga: durata = riga.split(":",1)[1].strip()
        elif "TARGET:" in riga: target = riga.split(":",1)[1].strip()
        elif "STOP LOSS:" in riga: stoploss = riga.split(":",1)[1].strip()
        elif "MOTIVO:" in riga: motivo = riga.split(":",1)[1].strip()
    if "COMPRA" in segnale: emoji_segnale, emoji_top = "BUY", "📈"
    elif "VENDI" in segnale: emoji_segnale, emoji_top = "SELL", "📉"
    else: emoji_segnale, emoji_top = "WATCH", "👁"
    if "Alto" in rischio: emoji_rischio = "🔴"
    elif "Medio" in rischio: emoji_rischio = "🟡"
    else: emoji_rischio = "🟢"
    tipo_label = "🐋 WHALE ALERT" if tipo == "whale" else "📰 NEWS SIGNAL"
    salva_segnale(token, segnale, target, stoploss, durata)
    return (tipo_label + "  |  " + emoji_top + " <b>" + emoji_segnale + " " + token + "</b>\n" +
        "━━━━━━━━━━━━━━━━━━\n" +
        "🎯 <b>Target:</b> " + target + "\n" +
        "🛑 <b>Stop Loss:</b> " + stoploss + "\n" +
        "⏳ <b>Durata:</b> " + durata + "\n" +
        emoji_rischio + " <b>Rischio:</b> " + rischio + "\n" +
        "━━━━━━━━━━━━━━━━━━\n" +
        "💬 " + motivo + "\n" +
        "━━━━━━━━━━━━━━━━━━\n" +
        "📌 <i>" + titolo + "</i>\n" +
        "🔗 " + fonte)

def genera_riassunto(segnali):
    prompt = "Sei un trader crypto aggressivo. Utente ha 100 CHF, TOP 3 opportunita. Diretto. Segnali: " + " | ".join(segnali)
    r = requests.post("https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": "Bearer " + GROQ_KEY, "Content-Type": "application/json"},
        json={"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": prompt}], "max_tokens": 400})
    data = r.json()
    if "choices" in data:
        return data["choices"][0]["message"]["content"]
    return None

def riassunto_serale(segnali):
    if not segnali:
        manda_messaggio("🌙 Nessun segnale oggi.")
        return
    prompt = "Recap serale TOP 3. Segnali: " + " | ".join(segnali)
    r = requests.post("https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": "Bearer " + GROQ_KEY, "Content-Type": "application/json"},
        json={"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": prompt}], "max_tokens": 500})
    data = r.json()
    if "choices" in data:
        manda_messaggio("🌙 RECAP SERALE\n" + data["choices"][0]["message"]["content"])

def revisione_settimanale():
    if not os.path.exists(STORICO_FILE):
        return
    with open(STORICO_FILE, "r") as f:
        storico = json.load(f)
    da_verificare = [s for s in storico if not s["verificato"]]
    if not da_verificare:
        return
    testo = ""
    for s in da_verificare:
        prezzo = get_prezzo(s["token"])
        prezzo_str = str(prezzo) + " USD" if prezzo else "?"
        testo += s["data"] + " | " + s["token"] + " | " + s["segnale"] + " | Target: " + s["target"] + " | Stop: " + s["stoploss"] + " | Ora: " + prezzo_str + "\n"
        s["verificato"] = True
    with open(STORICO_FILE, "w") as f:
        json.dump(storico, f)
    prompt = "Analisi performance settimanale: " + testo
    r = requests.post("https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": "Bearer " + GROQ_KEY, "Content-Type": "application/json"},
        json={"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": prompt}], "max_tokens": 600})
    data = r.json()
    if "choices" in data:
        manda_messaggio("📊 REVISIONE SETTIMANALE\n" + data["choices"][0]["message"]["content"])

def gestisci_comandi():
    global ultimo_update_id
    try:
        r = requests.get("https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/getUpdates",
                        params={"offset": ultimo_update_id + 1, "timeout": 5})
        dati = r.json()
        if dati["ok"] and dati["result"]:
            for msg in dati["result"]:
                if "message" in msg and "text" in msg["message"]:
                    testo = msg["message"]["text"]
                    chat_id = msg["message"]["chat"]["id"]
                    ultimo_update_id = msg["update_id"]
                    if testo == "/start":
                        risp = "🤖 Crypto Bot attivo!\n/btc - Prezzo Bitcoin\n/top5 - Top 5 crypto\n/ultimo - Ultimo segnale\n/aiuto - Comandi"
                    elif testo == "/btc":
                        risp = get_prezzo_btc()
                    elif testo == "/top5":
                        risp = get_top5()
                    elif testo == "/ultimo":
                        risp = ultimo_segnale_testo or "Nessun segnale"
                    elif testo == "/aiuto":
                        risp = "/start /btc /top5 /ultimo /aiuto"
                    else:
                        continue
                    requests.post("https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendMessage",
                                data={"chat_id": chat_id, "text": risp})
    except:
        pass

def get_prezzo_btc():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd", timeout=10)
        return f"💰 Bitcoin: ${r.json()['bitcoin']['usd']:,.2f} USD"
    except:
        return "Errore prezzo BTC"

def get_top5():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=5&page=1", timeout=10)
        coins = r.json()
        risp = "🏆 Top 5 Crypto:\n"
        for i, c in enumerate(coins, 1):
            risp += f"{i}. {c['name']} ({c['symbol'].upper()}) - ${c['current_price']:,.2f}\n"
        return risp
    except:
        return "Errore top 5"

FEEDS = [
    "https://cointelegraph.com/rss",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://whale-alert.io/feed"
]

notizie_viste = set()
print("Bot avviato!")
manda_messaggio("⚡ CRYPTO BOT ATTIVO ⚡")

while True:
    ora = datetime.now().strftime("%H:%M")
    data = datetime.now().strftime("%Y-%m-%d")
    giorno = datetime.now().strftime("%A")

    if ora == "20:00" and ultimo_riassunto_giornaliero != data:
        ultimo_riassunto_giornaliero = data
        riassunto_serale(segnali_giornalieri)
        segnali_giornalieri = []

    if giorno == "Sunday" and ora == "12:00" and ultimo_riassunto_giornaliero != "sun_" + data:
        ultimo_riassunto_giornaliero = "sun_" + data
        revisione_settimanale()

    # Controlla comandi ogni 5 secondi per 15 minuti
    for _ in range(180):
        gestisci_comandi()
        time.sleep(5)

    # Poi controlla le news
    for feed_url in FEEDS:
        tipo = "whale" if "whale-alert" in feed_url else "news"
        try:
            r = requests.get(feed_url, headers=HEADERS, timeout=10)
            feed = feedparser.parse(r.content)
        except:
            continue
        for entry in feed.entries[:10]:
            if entry.link not in notizie_viste:
                notizie_viste.add(entry.link)
                analisi = analizza_news(entry.title, tipo)
                if "IGNORA" not in analisi:
                    segnali_giornalieri.append(entry.title)
                    msg = formatta_segnale(entry.title, analisi, entry.link, tipo)
                    manda_messaggio(msg)
