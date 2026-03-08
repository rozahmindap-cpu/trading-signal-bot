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
stats = {"win": 0, "loss": 0}
exchange_global = None

def send_tele(msg):
    requests.post("https://api.telegram.org/bot"+BOT_TOKEN+"/sendMessage", json={"chat_id":CHAT_ID,"text":msg,"parse_mode":"HTML"})

def get_winrate():
    total = stats["win"] + stats["loss"]
    if total == 0:
        return "N/A (baru mulai)"
    pct = round(stats["win"] / total * 100, 1)
    return str(pct)+"% ("+str(stats["win"])+"W/"+str(stats["loss"])+"L)"

def monitor_signal(pair, action, entry, tp1, sl):
    deadline = time.time() + 14400
    while time.time() < deadline:
        try:
            time.sleep(60)
            ticker = exchange_global.fetch_ticker(pair)
            price = ticker["last"]
            if action == "LONG":
                if price >= tp1:
                    stats["win"] += 1
                    send_tele("✅ <b>TP HIT!</b>\nPair: "+pair+"\nSignal: LONG\nEntry: $"+str(entry)+"\nTP1: $"+str(tp1)+"\n\n📊 Win Rate: "+get_winrate())
                    return
                elif price <= sl:
                    stats["loss"] += 1
                    send_tele("❌ <b>SL HIT!</b>\nPair: "+pair+"\nSignal: LONG\nEntry: $"+str(entry)+"\nSL: $"+str(sl)+"\n\n📊 Win Rate: "+get_winrate())
                    return
            else:
                if price <= tp1:
                    stats["win"] += 1
                    send_tele("✅ <b>TP HIT!</b>\nPair: "+pair+"\nSignal: SHORT\nEntry: $"+str(entry)+"\nTP1: $"+str(tp1)+"\n\n📊 Win Rate: "+get_winrate())
                    return
                elif price >= sl:
                    stats["loss"] += 1
                    send_tele("❌ <b>SL HIT!</b>\nPair: "+pair+"\nSignal: SHORT\nEntry: $"+str(entry)+"\nSL: $"+str(sl)+"\n\n📊 Win Rate: "+get_winrate())
                    return
        except:
            pass

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
    global exchange_global
    exchange_global = ccxt.binance({"options":{"defaultType":"future"}})
    while True:
        for pair in PAIRS:
            try:
                ohlcv = exchange_global.fetch_ohlcv(pair,"15m",limit=100)
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
                now = time.time()
                last = alerted.get(pair,{})
                if r["ema20"]>r["ema50"] and 40<r["rsi"]<70 and r["macd"]>r["sig"] and p["macd"]<=p["sig"]:
                    if last.get("dir") != "BUY" or now - last.get("t",0) > 14400:
                        alerted[pair]={"dir":"BUY","t":now}
                        tp1,tp2,sl = calc_tp_sl(price,"LONG")
                        msg = ("🚨 <b>SIGNAL ALERT!</b>\n"
                               "━━━━━━━━━━━━━━\n"
                               "📌 Pair: <b>"+pair+"</b>\n"
                               "📊 Signal: 🟢 <b>LONG</b>\n"
                               "━━━━━━━━━━━━━━\n"
                               "📈 Entry: <b>$"+str(price)+"</b>\n"
                               "🎯 TP1: $"+str(tp1)+" (+2%)\n"
                               "🎯 TP2: $"+str(tp2)+" (+4%)\n"
                               "🛑 SL: $"+str(sl)+" (-1%)\n"
                               "━━━━━━━━━━━━━━\n"
                               "🔍 <b>Analisis:</b>\n"
                               "• EMA20 &gt; EMA50 → Uptrend ✅\n"
                               "• MACD crossover bullish ✅\n"
                               "• RSI: "+str(rsi)+" → Momentum naik ✅\n"
                               "━━━━━━━━━━━━━━\n"
                               "📊 Win Rate: "+get_winrate()+"\n"
                               "⏰ TF: 15m | Binance Futures")
                        send_tele(msg)
                        threading.Thread(target=monitor_signal,args=(pair,"LONG",price,tp1,sl),daemon=True).start()
                elif r["ema20"]<r["ema50"] and 30<r["rsi"]<60 and r["macd"]<r["sig"] and p["macd"]>=p["sig"]:
                    if last.get("dir") != "SELL" or now - last.get("t",0) > 14400:
                        alerted[pair]={"dir":"SELL","t":now}
                        tp1,tp2,sl = calc_tp_sl(price,"SHORT")
                        msg = ("🚨 <b>SIGNAL ALERT!</b>\n"
                               "━━━━━━━━━━━━━━\n"
                               "📌 Pair: <b>"+pair+"</b>\n"
                               "📊 Signal: 🔴 <b>SHORT</b>\n"
                               "━━━━━━━━━━━━━━\n"
                               "📉 Entry: <b>$"+str(price)+"</b>\n"
                               "🎯 TP1: $"+str(tp1)+" (-2%)\n"
                               "🎯 TP2: $"+str(tp2)+" (-4%)\n"
                               "🛑 SL: $"+str(sl)+" (+1%)\n"
                               "━━━━━━━━━━━━━━\n"
                               "🔍 <b>Analisis:</b>\n"
                               "• EMA20 &lt; EMA50 → Downtrend ✅\n"
                               "• MACD crossover bearish ✅\n"
                               "• RSI: "+str(rsi)+" → Momentum turun ✅\n"
                               "━━━━━━━━━━━━━━\n"
                               "📊 Win Rate: "+get_winrate()+"\n"
                               "⏰ TF: 15m | Binance Futures")
                        send_tele(msg)
                        threading.Thread(target=monitor_signal,args=(pair,"SHORT",price,tp1,sl),daemon=True).start()
                else:
                    alerted[pair]={}
            except Exception as e:
                print(str(e))
        time.sleep(60)

threading.Thread(target=scan,daemon=True).start()

@app.route("/")
def home():
    total = stats["win"] + stats["loss"]
    wr = get_winrate()
    return "Bot Running! | Signals tracked: "+str(total)+" | Win Rate: "+wr, 200

@app.route("/webhook",methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    ticker = data.get("ticker","N/A")
    close = data.get("close","N/A")
    action = str(data.get("action","")).upper()
    emoji = "LONG" if action=="BUY" else "SHORT"
    send_tele("SIGNAL!\nPair: "+ticker+"\nSignal: "+emoji+"\nPrice: "+str(close))
    return "OK", 200