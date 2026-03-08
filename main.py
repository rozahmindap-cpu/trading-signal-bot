from flask import Flask, request
import requests, os, threading, time, ccxt, pandas as pd
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator

app = Flask(__name__)

BOT_TOKEN = "8530174420:AAFTtuN2CjuA4PQd75fnD6jZKmOKOeq93m4"
CHAT_ID = "1603606771"
PAIRS = ["BTC/USDT","ETH/USDT","SOL/USDT","BNB/USDT","XRP/USDT"]
alerted = {}

def send_tele(msg):
    requests.post("https://api.telegram.org/bot"+BOT_TOKEN+"/sendMessage", json={"chat_id":CHAT_ID,"text":msg})

def scan():
    exchange = ccxt.bybit({"options":{"defaultType":"linear"}})
    while True:
        for pair in PAIRS:
            try:
                ohlcv = exchange.fetch_ohlcv(pair,"15m",limit=100)
                df = pd.DataFrame(ohlcv,columns=["t","o","h","l","c","v"])
                df["ema20"] = EMAIndicator(df["c"],20).ema_indicator()
                df["ema50"] = EMAIndicator(df["c"],50).ema_indicator()
                df["rsi"] = RSIIndicator(df["c"],14).rsi()
                macd = MACD(df["c"])
                df["macd"] = macd.macd()
                df["sig"] = macd.macd_signal()
                r,p = df.iloc[-1],df.iloc[-2]
                if r["ema20"]>r["ema50"] and 40<r["rsi"]<70 and r["macd"]>r["sig"] and p["macd"]<=p["sig"]:
                    if alerted.get(pair) != "BUY":
                        alerted[pair]="BUY"
                        send_tele("SIGNAL!\nPair: "+pair+"\nLONG\nPrice: "+str(round(r["c"],4))+"\nRSI: "+str(round(r["rsi"],1)))
                elif r["ema20"]<r["ema50"] and 30<r["rsi"]<60 and r["macd"]<r["sig"] and p["macd"]>=p["sig"]:
                    if alerted.get(pair) != "SELL":
                        alerted[pair]="SELL"
                        send_tele("SIGNAL!\nPair: "+pair+"\nSHORT\nPrice: "+str(round(r["c"],4))+"\nRSI: "+str(round(r["rsi"],1)))
                else:
                    alerted[pair]=None
            except Exception as e:
                print(str(e))
        time.sleep(60)

threading.Thread(target=scan,daemon=True).start()

@app.route("/")
def home():
    return "Bot Running!", 200

@app.route("/webhook",methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    ticker = data.get("ticker","N/A")
    close = data.get("close","N/A")
    action = str(data.get("action","")).upper()
    emoji = "LONG" if action=="BUY" else "SHORT"
    send_tele("SIGNAL!\nPair: "+ticker+"\nSignal: "+emoji+"\nPrice: "+str(close))
    return "OK", 200