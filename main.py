from flask import Flask, request
import requests
import os

app = Flask(__name__)

BOT_TOKEN = "8530174420:AAFTtuN2CjuA4PQd75fnD6jZKmOKOeq93m4"
CHAT_ID = "1603606771"

@app.route('/webhook', methods=['POST'])
def webhook():
try:
data = request.json

ticker = data.get('ticker', 'N/A')
close = data.get('close', 'N/A')
action = data.get('action', 'N/A').upper()

emoji = "🟢 LONG" if action == "BUY" else "🔴 SHORT"

msg = f"""
🚨 SIGNAL MASUK!
━━━━━━━━━━━━━━
Pair: {ticker}
Signal: {emoji}
Price: ${close}
━━━━━━━━━━━━━━
⚡️ Powered by Trading Bot
"""

requests.post(
f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
json={"chat_id": CHAT_ID, "text": msg}
)
return "OK", 200
except Exception as e:
return str(e), 500

@app.route('/')
def home():
return "Trading Signal Bot is Running! 🔥"

if __name__ == '__main__':
port = int(os.environ.get('PORT', 5000))
app.run(host='0.0.0.0', port=port)
