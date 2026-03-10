from flask import Flask, request
import requests, os, threading, time, ccxt, pandas as pd, math
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator, StochasticOscillator

app = Flask(__name__)

BOT_TOKEN = "8530174420:AAFTtuN2CjuA4PQd75fnD6jZKmOKOeq93m4"
CHAT_ID = "1603606771"
PAIRS = ["BTC/USDT","ETH/USDT","SOL/USDT","BNB/USDT","XRP/USDT","SUI/USDT","AVA/USDT","DOGE/USDT","HYPE/USDT","BCH/USDT","ASTER/USDT"]
alerted = {}
stats = {"win": 0, "loss": 0, "signals": 0}
active_signals = {}
exchange_global = None

def fmt(price):
    if price == 0:
        return "0"
    d = math.floor(math.log10(abs(price)))
    decimals = max(2, 4 - d)
    return str(round(price, decimals))

def send_tele(msg):
    requests.post("https://api.telegram.org/bot"+BOT_TOKEN+"/sendMessage", json={"chat_id":CHAT_ID,"text":msg,"parse_mode":"HTML"})

def get_winrate():
    total = stats["win"] + stats["loss"]
    if total == 0:
        return "N/A (baru mulai)"
    pct = round(stats["win"] / total * 100, 1)
    return str(pct)+"% ("+str(stats["win"])+"W/"+str(stats["loss"])+"L)"

def monitor_signal(pair, action, entry, tp1, tp2, sl):
    deadline = time.time() + 14400
    tp1_hit = False
    while time.time() < deadline:
        try:
            time.sleep(60)
            ticker = exchange_global.fetch_ticker(pair)
            price = ticker["last"]
            if action == "LONG":
                if not tp1_hit and price >= tp1:
                    tp1_hit = True
                    send_tele("TP1 HIT!\nPair: "+pair+"\nSignal: LONG\nEntry: $"+fmt(entry)+"\nTP1: $"+fmt(tp1)+"\n\nHolding for TP2: $"+fmt(tp2)+"...")
                elif tp1_hit and price >= tp2:
                    stats["win"] += 1
                    send_tele("TP2 HIT! WIN!\nPair: "+pair+"\nSignal: LONG\nEntry: $"+fmt(entry)+"\nTP2: $"+fmt(tp2)+"\n\nWin Rate: "+get_winrate())
                    active_signals.pop(pair, None)
                    return
                elif price <= sl:
                    if tp1_hit:
                        send_tele("SL HIT after TP1\nPair: "+pair+"\nSignal: LONG\nPartial win\n\nWin Rate: "+get_winrate())
                    else:
                        stats["loss"] += 1
                        send_tele("SL HIT!\nPair: "+pair+"\nSignal: LONG\nEntry: $"+fmt(entry)+"\nSL: $"+fmt(sl)+"\n\nWin Rate: "+get_winrate())
                    active_signals.pop(pair, None)
                    return
            else:
                if not tp1_hit and price <= tp1:
                    tp1_hit = True
                    send_tele("TP1 HIT!\nPair: "+pair+"\nSignal: SHORT\nEntry: $"+fmt(entry)+"\nTP1: $"+fmt(tp1)+"\n\nHolding for TP2: $"+fmt(tp2)+"...")
                elif tp1_hit and price <= tp2:
                    stats["win"] += 1
                    send_tele("TP2 HIT! WIN!\nPair: "+pair+"\nSignal: SHORT\nEntry: $"+fmt(entry)+"\nTP2: $"+fmt(tp2)+"\n\nWin Rate: "+get_winrate())
                    active_signals.pop(pair, None)
                    return
                elif price >= sl:
                    if tp1_hit:
                        send_tele("SL HIT after TP1\nPair: "+pair+"\nSignal: SHORT\nPartial win\n\nWin Rate: "+get_winrate())
                    else:
                        stats["loss"] += 1
                        send_tele("SL HIT!\nPair: "+pair+"\nSignal: SHORT\nEntry: $"+fmt(entry)+"\nSL: $"+fmt(sl)+"\n\nWin Rate: "+get_winrate())
                    active_signals.pop(pair, None)
                    return
        except:
            pass

def calc_tp_sl(price, action):
    if action == "LONG":
        tp1 = price * 1.02
        tp2 = price * 1.04
        sl = price * 0.99
    else:
        tp1 = price * 0.98
        tp2 = price * 0.96
        sl = price * 1.015
    return tp1, tp2, sl

def scan():
    global exchange_global
    exchange_global = ccxt.binance({"options":{"defaultType":"future"}})
    while True:
        for pair in PAIRS:
            if pair in active_signals:
                continue
            try:
                ohlcv = exchange_global.fetch_ohlcv(pair,"15m",limit=150)
                df = pd.DataFrame(ohlcv,columns=["t","o","h","l","c","v"])
                df["ema25"] = EMAIndicator(df["c"],25).ema_indicator()
                df["ema75"] = EMAIndicator(df["c"],75).ema_indicator()
                df["ema140"] = EMAIndicator(df["c"],140).ema_indicator()
                df["rsi"] = RSIIndicator(df["c"],14).rsi()
                stoch = StochasticOscillator(df["h"],df["l"],df["c"],window=14,smooth_window=3)
                df["stoch_k"] = stoch.stoch()
                df["stoch_d"] = stoch.stoch_signal()
                r = df.iloc[-1]
                p = df.iloc[-2]
                price = r["c"]
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
                        active_signals[pair] = 'LONG'
                        stats['signals'] += 1
                        msg = ("SIGNAL ALERT!\n"
                               "Pair: "+pair+"\n"
                               "Signal: LONG\n"
                               "Entry: $"+fmt(price)+"\n"
                               "TP1: $"+fmt(tp1)+" (+2%)\n"
                               "TP2: $"+fmt(tp2)+" (+4%)\n"
                               "SL: $"+fmt(sl)+" (-1%)\n"
                               "RSI: "+str(rsi)+" | Stoch: "+str(stoch_val)+"\n"
                               "Win Rate: "+get_winrate()+"\n"
                               "TF: 15m | Binance Futures")
                        send_tele(msg)
                        threading.Thread(target=monitor_signal,args=(pair,'LONG',price,tp1,tp2,sl),daemon=True).start()
                elif short_ema and short_stoch and short_rsi:
                    if last.get("dir") != "SELL" or now - last.get("t",0) > 14400:
                        alerted[pair]={"dir":"SELL","t":now}
                        tp1,tp2,sl = calc_tp_sl(price,"SHORT")
                        active_signals[pair] = 'SHORT'
                        stats['signals'] += 1
                        msg = ("SIGNAL ALERT!\n"
                               "Pair: "+pair+"\n"
                               "Signal: SHORT\n"
                               "Entry: $"+fmt(price)+"\n"
                               "TP1: $"+fmt(tp1)+" (-2%)\n"
                               "TP2: $"+fmt(tp2)+" (-4%)\n"
                               "SL: $"+fmt(sl)+" (+1.5%)\n"
                               "RSI: "+str(rsi)+" | Stoch: "+str(stoch_val)+"\n"
                               "Win Rate: "+get_winrate()+"\n"
                               "TF: 15m | Binance Futures")
                        send_tele(msg)
                        threading.Thread(target=monitor_signal,args=(pair,'SHORT',price,tp1,tp2,sl),daemon=True).start()
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
