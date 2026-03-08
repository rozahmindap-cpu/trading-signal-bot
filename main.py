from flask import Flask, request
import requests
import os

app = Flask(__name__)

BOT_TOKEN = "8530174420:AAFTtuN2CjuA4PQd75fnD6jZKmOKOeq93m4"
CHAT_ID = "1603606771"

@app.route('/')
def home():
return "Bot Running!", 200

@app.route('/webhook', methods=['POST'])
def webhook():
data = request.get_json(force=True)
ticker = data.get('ticker', 'N/A')
close = data.get('close', 'N/A')
action = str(data.get('action', '')).upper()
if action == "BUY":
emoji = "🟢 LONG"
else:
emoji = "🔴 SHORT"
msg = "🚨 SIGNAL!\nPair: " + ticker + "\nSignal: " + emoji + "\nPrice: $" + str(close)
requests.post("https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage", json={"chat_id": CHAT_ID, "text": msg})
return "OK", 200

port = int(os.environ.get('PORT', 8080))
app.run(host='0.0.0.0', port=port)
