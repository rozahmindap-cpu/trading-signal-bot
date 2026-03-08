import os
from flask import Flask, request
import requests

app = Flask(__name__)

BOT_TOKEN = "8530174420:AAFTtuN2CjuA4PQd75fnD6jZKmOKOeq93m4"
CHAT_ID = "1603606771"

@app.route('/', methods=['GET'])
def home():
return "Bot is Running! 🔥", 200

@app.route('/webhook', methods=['POST'])
def webhook():
data = request.get_json(force=True)
ticker = data.get('ticker', 'N/A')
close = data.get('close', 'N/A')
action = data.get('action', 'N/A').upper()
emoji = "🟢 LONG" if action == "BUY" else "🔴 SHORT"
msg = f"🚨 SIGNAL!\nPair: {ticker}\nSignal: {emoji}\nPrice: ${close}"
url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
requests.post(url, json={"chat_id": CHAT_ID, "text": msg})
return "OK", 200

if __name__ == '__main__':
port = int(os.environ.get('PORT', 8080))
app.run(host='0.0.0.0', port=port)
