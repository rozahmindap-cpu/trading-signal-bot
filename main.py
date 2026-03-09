from flask import Flask, request
import requests, os, threading, time, ccxt, pandas as pd
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator, StochasticOscillator

app = Flask(__name__)

BOT_TOKEN = "8530174420:AAFTtuN2CjuA4PQd75fnD6jZKmOKOeq93m4"
CHAT_ID = "1603606771"
PAIRS = [
    "BTC/USDT","ETH/USDT","SOL/USDT","BNB/USDT","XRP/USDT",
    "BANANA/USDT","PIPPIN/USDT","DEGO/USDT","COS/USDT","SUI/USDT","AVA/USDT"
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
        sl = round(price * 1.015, 4)
    return tp1, tp2, sl

def scan():
    global exchange_global
    exchange_global = ccxt.binance({"options":{"defaultType":"future"}})
    while True:
        for pair in PAIRS:
            try:
                ohlcv = exchange_global.fetch_ohlcv(pair,"15m",limit=150)
                df = pd.DataFrame(ohlcv,columns=["t","o","h","l","c","v"])
                df["ema25"] = EMAIndicator(df["c"],25).ema_indicator()
                df["ema75"] = EMAIndicator(df["c"],75).ema_indicator()
                df["ema140"] = EMAIndicator(df["c"],140).ema_indicator()
                df["rsi"] = RSIIndicator(df["c"],14).rsi()
                macd = MACD(df["c"])
                df["macd"] = macd.macd()
                df["sig"] = macd.macd_signal()
                stoch = StochasticOscillator(df["h"],df["l"],df["c"],window=14,smooth_window=3)
                df["stoch_k"] = stoch.stoch()
                df["stoch_d"] = stoch.stoch_signal()
                r = df.iloc[-1]
                p = df.iloc[-2]
                price = round(r["c"],4)
                rsi = round(r["rsi"],1)
                stoch_val = round(r["stoch_k"],1)
                now = time.time()
                last = alerted.get(pair,{})

                long_ema = r["ema25"] > r["ema75"] > r["ema140"]
                long_stoch = r["stoch_k"] < 30 and r["stoch_k"] > r["stoch_d"] and p["stoch_k"] <= p["stoch_d"]
                long_rsi = 30 < r["rsi"] < 60

                short_ema = r["ema25"] < r["ema75"] < r["ema140"]
                short_stoch = r["stoch_k"] > 70 and r["stoch_k"] < r["stoch_d"] and p["stoch_k"] >= p["stoch_d"]
                short_rsi = r["rsi"] > 55 and p["rsi"] > r["rsi"]

                if long_ema and long_stoch and long_rsi:
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
                               "• EMA25 > EMA75 > EMA140 → Uptrend ✅\n"
                               "• Stochastic oversold crossup ✅\n"
                               "• RSI: "+str(rsi)+" | Stoch: "+str(stoch_val)+" ✅\n"
                               "━━━━━━━━━━━━━━\n"
                               "📊 Win Rate: "+get_winrate()+"\n"
                               "⏰ TF: 15m | Binance Futures")
                        send_tele(msg)
                        threading.Thread(target=monitor_signal,args=(pair,"LONG",price,tp1,sl),daemon=True).start()
                elif short_ema and short_stoch and short_rsi:
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
                               "🛑 SL: $"+str(sl)+" (+1.5%)\n"
                               "━━━━━━━━━━━━━━\n"
                               "🔍 <b>Analisis:</b>\n"
                               "• EMA25 < EMA75 < EMA140 → Downtrend ✅\n"
                               "• Stochastic overbought crossdown ✅\n"
                               "• RSI: "+str(rsi)+" | Stoch: "+str(stoch_val)+" ✅\n"
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
    wr = get_winrate()
    total = stats["win"] + stats["loss"]
    return "Bot Running! | Signals: "+str(total)+" | Win Rate: "+wr, 200

@app.route("/webhook",methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    ticker = data.get("ticker","N/A")
    close = data.get("close","N/A")
    action = str(data.get("action","")).upper()
    emoji = "LONG" if action=="BUY" else "SHORT"
    send_tele("SIGNAL!\nPair: "+ticker+"\nSignal: "+emoji+"\nPrice: "+str(close))
    return "OK", 200