from flask import Flask, request
import requests, os, threading, time, ccxt, pandas as pd
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator

app = Flask(__name__)

BOT_TOKEN = "8530174420:AAFTtuN2CjuA4PQd75fnD6jZKmOKOeq93m4"
CHAT_ID = "1603606771"
PAIRS = [
    "BTC/USDT","ETH/USDT","SOL/USDT","BNB/USDT","XRP/USDT",
    "BANANA/USDT","PIPPIN/USDT","DEGO/USDT","COS/USDT",
    "RESOLVE/USDT","MATRA/USDT","KATA/USDT","SUI/USDT","AVA/USDT"
]
alerted = {}

def send_tele(msg):
    requests.post("https://api.telegram.org/bot"+BOT_TOKEN+"/sendMessage", json={"chat_id":CHAT_ID,"text":msg})

def calc_tp_sl(price, action):
    if action == "LONG":
        tp1 = round(price * 1.02, 4)
        tp2 = round(price * 1.04, 4)
        sl = round(price * 0.99, 4)
    else:
        tp1 = round(price * 0.98, 4)
        tp2 = round(price * 0.96, 4)
        sl = round(price * 1.01, 4)
    return tp1, tp2, sl

def scan():
    exchange = ccxt.binance({"options":{"defaultType":"future"}})
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
                price = round(r["c"],4)
                rsi = round(r["rsi"],1)
                if r["ema20"]>r["ema50"] and 40<r["rsi"]<70 and r["macd"]>r["sig"] and p["macd"]<=p["sig"]:
                    if alerted.get(pair) != "BUY":
                        alerted[pair]="BUY"
                        tp1,tp2,sl = calc_tp_sl(price,"LONG")
                        msg = ("🚨 SIGNAL!\n"
                               "━━━━━━━━━━━━━━\n"
                               "Pair: "+pair+"\n"
                               "Signal: 🟢 LONG\n"
                               "━━━━━━━━━━━━━━\n"
                               "📈 Entry: $"+str(price)+"\n"
                               "🎯 TP1: $"+str(tp1)+" (+2%)\n"
                               "🎯 TP2: $"+str(tp2)+" (+4%)\n"
                               "🛑 SL: $"+str(sl)+" (-1%)\n"
                               "━━━━━━━━━━━━━━\n"
                               "RSI: "+str(rsi)+" | TF: 15m")
                        send_tele(msg)
                elif r["ema20"]<r["ema50"] and 30<r["rsi"]<60 and r["macd"]<r["sig"] and p["macd"]>=p["sig"]:
                    if alerted.get(pair) != "SELL":
                        alerted[pair]="SELL"
                        tp1,tp2,sl = calc_tp_sl(price,"SHORT")
                        msg = ("🚨 SIGNAL!\n"
                               "━━━━━━━━━━━━━━\n"
                               "Pair: "+pair+"\n"
                               "Signal: 🔴 SHORT\n"
                               "━━━━━━━━━━━━━━\n"
                               "📉 Entry: $"+str(price)+"\n"
                               "🎯 TP1: $"+str(tp1)+" (-2%)\n"
                               "🎯 TP2: $"+str(tp2)+" (-4%)\n"
                               "🛑 SL: $"+str(sl)+" (+1%)\n"
                               "━━━━━━━━━━━━━━\n"
                               "RSI: "+str(rsi)+" | TF: 15m")
                        send_tele(msg)
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