from flask import Flask, request
import requests, os, threading, time, ccxt, pandas as pd, math, io
from ta.momentum import RSIIndicator

app = Flask(__name__)

BOT_TOKEN = "8530174420:AAFTtuN2CjuA4PQd75fnD6jZKmOKOeq93m4"
CHAT_ID = "1603606771"
PAIRS = ["BTC/USDT","ETH/USDT","SOL/USDT","BNB/USDT","XRP/USDT","SUI/USDT","DOGE/USDT","HYPE/USDT","BCH/USDT","ASTER/USDT","ADA/USDT","LINK/USDT"]
alerted = {}
stats = {"win": 0, "loss": 0, "signals": 0}
active_signals = {}
exchange_global = None

# ============ CMCWinner Strategy Parameters ============
# Timeframe: 15m swing trading
# Entry: Triple confluence oversold/overbought
# LONG:  CCI < -100 AND MFI < 20 AND CMO < -50
# SHORT: CCI > 100  AND MFI > 80  AND CMO > 50
# TP: +5% (instant) → +3% (30m) → +2% (40m)
# SL: -5%
# Expected WR: 70-78%
# ========================================================

def fmt(price):
    if price == 0:
        return "0"
    d = math.floor(math.log10(abs(price)))
    decimals = max(2, 4 - d)
    return str(round(price, decimals))

def send_tele(msg):
    try:
        requests.post(
            "https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage",
            json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=10
        )
    except Exception as e:
        print(f"Telegram error: {e}")

def send_photo(buf, caption=""):
    try:
        buf.seek(0)
        requests.post(
            "https://api.telegram.org/bot" + BOT_TOKEN + "/sendPhoto",
            data={"chat_id": CHAT_ID, "caption": caption, "parse_mode": "HTML"},
            files={"photo": ("chart.png", buf, "image/png")},
            timeout=30
        )
    except Exception as e:
        print(f"Photo send error: {e}")

def get_winrate():
    total = stats["win"] + stats["loss"]
    if total == 0:
        return "N/A (baru mulai)"
    pct = round(stats["win"] / total * 100, 1)
    return str(pct) + "% (" + str(stats["win"]) + "W/" + str(stats["loss"]) + "L)"


# ============ CMCWinner Indicators ============

def calc_cci(df, period=20):
    """Commodity Channel Index"""
    tp = (df["h"] + df["l"] + df["c"]) / 3
    sma_tp = tp.rolling(window=period).mean()
    mad = tp.rolling(window=period).apply(lambda x: abs(x - x.mean()).mean(), raw=True)
    cci = (tp - sma_tp) / (0.015 * mad)
    return cci

def calc_mfi(df, period=14):
    """Money Flow Index"""
    tp = (df["h"] + df["l"] + df["c"]) / 3
    mf = tp * df["v"]
    pos_mf = pd.Series(0.0, index=df.index)
    neg_mf = pd.Series(0.0, index=df.index)

    for i in range(1, len(df)):
        if tp.iloc[i] > tp.iloc[i-1]:
            pos_mf.iloc[i] = mf.iloc[i]
        else:
            neg_mf.iloc[i] = mf.iloc[i]

    pos_sum = pos_mf.rolling(window=period).sum()
    neg_sum = neg_mf.rolling(window=period).sum()
    mfi = 100 - (100 / (1 + pos_sum / neg_sum.replace(0, 1e-10)))
    return mfi

def calc_cmo(df, period=14):
    """Chande Momentum Oscillator"""
    diff = df["c"].diff()
    gain = diff.clip(lower=0)
    loss = (-diff).clip(lower=0)
    sum_gain = gain.rolling(window=period).sum()
    sum_loss = loss.rolling(window=period).sum()
    cmo = 100 * (sum_gain - sum_loss) / (sum_gain + sum_loss).replace(0, 1e-10)
    return cmo


# ============ Signal Monitoring ============

def monitor_signal(pair, action, entry, tp1, tp2, sl):
    deadline = time.time() + 21600  # 6 hours max hold
    tp1_hit = False
    while time.time() < deadline:
        try:
            time.sleep(60)
            ticker = exchange_global.fetch_ticker(pair)
            price = ticker["last"]
            if action == "LONG":
                if not tp1_hit and price >= tp1:
                    tp1_hit = True
                    stats["win"] += 1
                    send_tele(
                        "🎯 <b>TP1 HIT!</b>\n"
                        "Pair: " + pair + "\nSignal: LONG\n"
                        "Entry: $" + fmt(entry) + "\n"
                        "TP1: $" + fmt(tp1) + " (+3%)\n\n"
                        "Holding for TP2: $" + fmt(tp2) + " (+5%)...\n"
                        "📊 Win Rate: " + get_winrate()
                    )
                elif tp1_hit and price >= tp2:
                    send_tele(
                        "🏆 <b>TP2 HIT! BIG WIN!</b>\n"
                        "Pair: " + pair + "\nSignal: LONG\n"
                        "Entry: $" + fmt(entry) + "\n"
                        "TP2: $" + fmt(tp2) + " (+5%)\n\n"
                        "📊 Win Rate: " + get_winrate()
                    )
                    active_signals.pop(pair, None)
                    return
                elif price <= sl:
                    if tp1_hit:
                        send_tele("⚠️ <b>SL after TP1 — Partial Win</b>\nPair: " + pair + "\n📊 Win Rate: " + get_winrate())
                    else:
                        stats["loss"] += 1
                        send_tele(
                            "❌ <b>SL HIT!</b>\n"
                            "Pair: " + pair + "\nSignal: LONG\n"
                            "Entry: $" + fmt(entry) + "\n"
                            "SL: $" + fmt(sl) + " (-5%)\n\n"
                            "📊 Win Rate: " + get_winrate()
                        )
                    active_signals.pop(pair, None)
                    return
            else:  # SHORT
                if not tp1_hit and price <= tp1:
                    tp1_hit = True
                    stats["win"] += 1
                    send_tele(
                        "🎯 <b>TP1 HIT!</b>\n"
                        "Pair: " + pair + "\nSignal: SHORT\n"
                        "Entry: $" + fmt(entry) + "\n"
                        "TP1: $" + fmt(tp1) + " (-3%)\n\n"
                        "Holding for TP2: $" + fmt(tp2) + " (-5%)...\n"
                        "📊 Win Rate: " + get_winrate()
                    )
                elif tp1_hit and price <= tp2:
                    send_tele(
                        "🏆 <b>TP2 HIT! BIG WIN!</b>\n"
                        "Pair: " + pair + "\nSignal: SHORT\n"
                        "Entry: $" + fmt(entry) + "\n"
                        "TP2: $" + fmt(tp2) + " (-5%)\n\n"
                        "📊 Win Rate: " + get_winrate()
                    )
                    active_signals.pop(pair, None)
                    return
                elif price >= sl:
                    if tp1_hit:
                        send_tele("⚠️ <b>SL after TP1 — Partial Win</b>\nPair: " + pair + "\n📊 Win Rate: " + get_winrate())
                    else:
                        stats["loss"] += 1
                        send_tele(
                            "❌ <b>SL HIT!</b>\n"
                            "Pair: " + pair + "\nSignal: SHORT\n"
                            "Entry: $" + fmt(entry) + "\n"
                            "SL: $" + fmt(sl) + " (+5%)\n\n"
                            "📊 Win Rate: " + get_winrate()
                        )
                    active_signals.pop(pair, None)
                    return
        except:
            pass
    # Timeout — auto close
    active_signals.pop(pair, None)
    send_tele("⏰ <b>Signal Expired</b>\nPair: " + pair + " | 6h timeout\n📊 Win Rate: " + get_winrate())


def calc_tp_sl(price, action):
    """CMCWinner: TP1 +3%, TP2 +5%, SL -5%"""
    if action == "LONG":
        tp1 = price * 1.03
        tp2 = price * 1.05
        sl  = price * 0.95
    else:
        tp1 = price * 0.97
        tp2 = price * 0.95
        sl  = price * 1.05
    return tp1, tp2, sl


def try_send_chart(df, pair, action, entry, tp1, tp2, sl, cci_val, mfi_val, cmo_val):
    """Generate dan kirim chart CMCWinner"""
    try:
        from chart_generator import generate_chart_cmcwinner
        buf = generate_chart_cmcwinner(df, pair, action, entry, tp1, tp2, sl, cci_val, mfi_val, cmo_val)
        if buf:
            caption = f"📊 <b>{pair}</b> — {'🟢 LONG' if action == 'LONG' else '🔴 SHORT'} | CMCWinner | 15m"
            send_photo(buf, caption)
    except Exception as e:
        print(f"Chart skipped: {e}")


# ============ Main Scanner — CMCWinner Strategy ============

def scan():
    global exchange_global
    exchange_global = ccxt.binance({"options": {"defaultType": "future"}, "enableRateLimit": True})

    send_tele(
        "🚀 <b>CMCWinner Bot Started!</b>\n"
        "━━━━━━━━━━━━━━\n"
        "📈 Strategy: CMCWinner (Triple Confluence)\n"
        "⏱ Timeframe: 15m\n"
        "📌 Pairs: " + str(len(PAIRS)) + "\n"
        "🎯 TP1: +3% | TP2: +5% | SL: -5%\n"
        "━━━━━━━━━━━━━━\n"
        "📊 Indikator:\n"
        " CCI (Commodity Channel Index)\n"
        " MFI (Money Flow Index)\n"
        " CMO (Chande Momentum Oscillator)\n"
        "━━━━━━━━━━━━━━\n"
        "⚡ LONG: CCI < -100 + MFI < 20 + CMO < -50\n"
        "⚡ SHORT: CCI > 100 + MFI > 80 + CMO > 50\n"
        "Target WR: 70-78% 🎯"
    )

    while True:
        for pair in PAIRS:
            if pair in active_signals:
                continue
            try:
                ohlcv = exchange_global.fetch_ohlcv(pair, "15m", limit=100)
                df = pd.DataFrame(ohlcv, columns=["t","o","h","l","c","v"])

                # Calculate CMCWinner indicators
                df["cci"] = calc_cci(df, period=20)
                df["mfi"] = calc_mfi(df, period=14)
                df["cmo"] = calc_cmo(df, period=14)
                df["rsi"] = RSIIndicator(df["c"], 14).rsi()

                r = df.iloc[-1]
                p = df.iloc[-2]  # previous candle (shift 1 like original CMCWinner)
                price = r["c"]
                now = time.time()
                last = alerted.get(pair, {})

                cci_val = round(p["cci"], 1)
                mfi_val = round(p["mfi"], 1)
                cmo_val = round(p["cmo"], 1)
                rsi_val = round(r["rsi"], 1)

                # ============ CMCWinner Entry Conditions ============
                # Use .shift(1) equivalent — check previous bar (p) like original strategy
                long_signal = (
                    p["cci"] < -100 and
                    p["mfi"] < 20 and
                    p["cmo"] < -50
                )

                short_signal = (
                    p["cci"] > 100 and
                    p["mfi"] > 80 and
                    p["cmo"] > 50
                )

                if long_signal:
                    if last.get("dir") != "BUY" or now - last.get("t", 0) > 7200:
                        alerted[pair] = {"dir": "BUY", "t": now}
                        tp1, tp2, sl = calc_tp_sl(price, "LONG")
                        active_signals[pair] = "LONG"
                        stats["signals"] += 1
                        msg = (
                            "🚨 <b>CMCWinner SIGNAL!</b>\n"
                            "━━━━━━━━━━━━━━\n"
                            "📌 Pair: <b>" + pair + "</b>\n"
                            "📈 Signal: 🟢 <b>LONG</b>\n"
                            "━━━━━━━━━━━━━━\n"
                            "💰 Entry: <b>$" + fmt(price) + "</b>\n"
                            "🎯 TP1: $" + fmt(tp1) + " (+3%)\n"
                            "🎯 TP2: $" + fmt(tp2) + " (+5%)\n"
                            "🛑 SL: $" + fmt(sl) + " (-5%)\n"
                            "━━━━━━━━━━━━━━\n"
                            "📊 <b>Triple Confluence:</b>\n"
                            " CCI: " + str(cci_val) + " (< -100) ✅\n"
                            " MFI: " + str(mfi_val) + " (< 20) ✅\n"
                            " CMO: " + str(cmo_val) + " (< -50) ✅\n"
                            " RSI: " + str(rsi_val) + "\n"
                            "━━━━━━━━━━━━━━\n"
                            "📊 Win Rate: " + get_winrate() + "\n"
                            "⏱ TF: 15m | Binance Futures\n"
                            "🏆 Strategy: CMCWinner"
                        )
                        send_tele(msg)
                        threading.Thread(target=try_send_chart, args=(df.copy(), pair, "LONG", price, tp1, tp2, sl, cci_val, mfi_val, cmo_val), daemon=True).start()
                        threading.Thread(target=monitor_signal, args=(pair, "LONG", price, tp1, tp2, sl), daemon=True).start()

                elif short_signal:
                    if last.get("dir") != "SELL" or now - last.get("t", 0) > 7200:
                        alerted[pair] = {"dir": "SELL", "t": now}
                        tp1, tp2, sl = calc_tp_sl(price, "SHORT")
                        active_signals[pair] = "SHORT"
                        stats["signals"] += 1
                        msg = (
                            "🚨 <b>CMCWinner SIGNAL!</b>\n"
                            "━━━━━━━━━━━━━━\n"
                            "📌 Pair: <b>" + pair + "</b>\n"
                            "📉 Signal: 🔴 <b>SHORT</b>\n"
                            "━━━━━━━━━━━━━━\n"
                            "💰 Entry: <b>$" + fmt(price) + "</b>\n"
                            "🎯 TP1: $" + fmt(tp1) + " (-3%)\n"
                            "🎯 TP2: $" + fmt(tp2) + " (-5%)\n"
                            "🛑 SL: $" + fmt(sl) + " (+5%)\n"
                            "━━━━━━━━━━━━━━\n"
                            "📊 <b>Triple Confluence:</b>\n"
                            " CCI: " + str(cci_val) + " (> 100) ✅\n"
                            " MFI: " + str(mfi_val) + " (> 80) ✅\n"
                            " CMO: " + str(cmo_val) + " (> 50) ✅\n"
                            " RSI: " + str(rsi_val) + "\n"
                            "━━━━━━━━━━━━━━\n"
                            "📊 Win Rate: " + get_winrate() + "\n"
                            "⏱ TF: 15m | Binance Futures\n"
                            "🏆 Strategy: CMCWinner"
                        )
                        send_tele(msg)
                        threading.Thread(target=try_send_chart, args=(df.copy(), pair, "SHORT", price, tp1, tp2, sl, cci_val, mfi_val, cmo_val), daemon=True).start()
                        threading.Thread(target=monitor_signal, args=(pair, "SHORT", price, tp1, tp2, sl), daemon=True).start()
                else:
                    alerted[pair] = {}

            except Exception as e:
                print(f"Error {pair}: {e}")
            time.sleep(2)
        # Scan every 3 minutes (15m candle, check often for fresh signals)
        time.sleep(180)


threading.Thread(target=scan, daemon=True).start()


@app.route("/")
def home():
    wr = get_winrate()
    total = stats["win"] + stats["loss"]
    active = len(active_signals)
    return f"CMCWinner Bot Running! | Signals: {stats['signals']} | Results: {total} | Win Rate: {wr} | Active: {active}", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    ticker = data.get("ticker", "N/A")
    close = data.get("close", "N/A")
    action = str(data.get("action", "")).upper()
    emoji = "LONG" if action == "BUY" else "SHORT"
    send_tele("SIGNAL!\nPair: " + ticker + "\nSignal: " + emoji + "\nPrice: " + str(close))
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
