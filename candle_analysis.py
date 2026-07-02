import requests
from datetime import datetime, timezone

BASE = (
  "https://contract.mexc.com"
  "/api/v1/contract/kline")

def fetch_klines(symbol, interval,
                 start, end):
    r = requests.get(
        f"{BASE}/{symbol}",
        params={
          "interval": interval,
          "start": start,
          "end": end},
        timeout=15)
    r.raise_for_status()
    d = r.json()
    if not d.get("success"):
        raise ValueError(
            str(d)[:120])
    raw = d["data"]
    out = []
    for i in range(
            len(raw["time"])):
        out.append({
          "t": int(raw["time"][i]),
          "o": float(
            raw["open"][i]),
          "h": float(
            raw["high"][i]),
          "l": float(
            raw["low"][i]),
          "c": float(
            raw["close"][i]),
        })
    return sorted(
        out, key=lambda x: x["t"])

def calc_kdj(candles, n=9):
    K, D = 50.0, 50.0
    result = []
    for i, c in enumerate(candles):
        w = candles[
            max(0,i-n+1):i+1]
        hi = max(
            x["h"] for x in w)
        lo = min(
            x["l"] for x in w)
        rng = hi - lo
        rsv = ((c["c"]-lo)/rng*100
               if rng>0 else 50.0)
        K = (2/3)*K + (1/3)*rsv
        D = (2/3)*D + (1/3)*K
        result.append(
            round(3*K-2*D, 2))
    return result

def fmt(ts):
    return datetime.fromtimestamp(
        ts, tz=timezone.utc
    ).strftime("%H:%M:%S")

def analyze(label, symbol,
            direction, entry_ts,
            close_ts, confirm_px,
            entry_px, duration_s):
    # Use Min1 for trades
    # under 5 minutes
    interval = (
        "Min1"
        if duration_s < 300
        else "Min15")
    warmup = 1800
    candles = fetch_klines(
        symbol, interval,
        entry_ts - warmup,
        close_ts + 300)
    j_vals = calc_kdj(candles)

    trade_c = [
        (c, j_vals[i])
        for i, c in enumerate(
            candles)
        if c["t"] >= entry_ts
        and c["t"] <= close_ts+120]

    if not trade_c:
        print(f"\n{label}: "
              f"no candles")
        return

    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"  {symbol} {direction}"
          f"  dur={duration_s}s"
          f"  interval={interval}")
    print(f"  confirm_px={confirm_px}"
          f"  entry_px={entry_px}")
    print(f"{'='*60}")
    print(f"  {'TIME':>8}  "
          f"{'O':>9}  "
          f"{'H':>9}  "
          f"{'L':>9}  "
          f"{'C':>9}  "
          f"{'J':>7}  NOTE")
    print(f"  {'-'*68}")

    for c, j in trade_c:
        note = ""
        if c["t"] <= (
                entry_ts + 60):
            note = "ENTRY WINDOW"
        # Check if candle crossed
        # back through confirm_px
        if direction == "LONG":
            if c["l"] <= confirm_px:
                note = (
                    "\u26a1 CONFIRM BREAK"
                    f" lo={c['l']:.5f}"
                    f" < {confirm_px}")
        else:
            if c["h"] >= confirm_px:
                note = (
                    "\u26a1 CONFIRM BREAK"
                    f" hi={c['h']:.5f}"
                    f" > {confirm_px}")

        print(f"  {fmt(c['t']):>8} "
              f" {c['o']:9.5f}"
              f"  {c['h']:9.5f}"
              f"  {c['l']:9.5f}"
              f"  {c['c']:9.5f}"
              f"  {j:7.1f}"
              f"  {note}")

    print(f"\n  WHY IT REVERSED:")
    print(f"  confirm_px={confirm_px}"
          f" \u2014 price needed to stay"
          f" {'above' if direction=='LONG' else 'below'}"
          f" this level")
    print(f"  duration={duration_s}s"
          f" \u2014 exited in "
          f"{'< 1 min' if duration_s < 60 else str(duration_s//60)+'m'}")

def ts(y,mo,d,h,mi,s=0):
    return int(datetime(
        y,mo,d,h,mi,s,
        tzinfo=timezone.utc
    ).timestamp())

# 6 zero-MFE CONFIRM_REVERSAL
# trades -- July 1 2026
# All times UTC
# Entry prices and confirm_px
# will be updated once SQL
# results come back -- using
# approximate times from log
# close_time_et converted to UTC
# (ET = UTC-4 on July 1)

TRADES = [
    # LTC HL LONG 08:11 PM ET
    # = 00:11 UTC Jul 2, dur=4s
    ("LTC HL LONG dur=4s",
     "LTC_USDT", "LONG",
     ts(2026,7,2,0,11,0),
     ts(2026,7,2,0,11,4),
     None, None, 4),

    # SUI_USDT MX LONG 08:13 PM
    # = 00:13 UTC dur=10s
    ("SUI_USDT MX LONG dur=10s",
     "SUI_USDT", "LONG",
     ts(2026,7,2,0,13,0),
     ts(2026,7,2,0,13,10),
     None, None, 10),

    # ADA_USDT MX LONG 09:15 PM
    # = 01:15 UTC dur=8s
    ("ADA_USDT MX LONG dur=8s",
     "ADA_USDT", "LONG",
     ts(2026,7,2,1,15,0),
     ts(2026,7,2,1,15,8),
     None, None, 8),

    # BTC HL LONG 09:20 PM
    # = 01:20 UTC dur=35s
    ("BTC HL LONG dur=35s",
     "BTC_USDT", "LONG",
     ts(2026,7,2,1,20,0),
     ts(2026,7,2,1,20,35),
     None, None, 35),

    # ZEC HL LONG 08:37 PM
    # = 00:37 UTC dur=33s
    ("ZEC HL LONG dur=33s",
     "ZEC_USDT", "LONG",
     ts(2026,7,2,0,37,0),
     ts(2026,7,2,0,37,33),
     None, None, 33),

    # DOGE HL SHORT 06:30 PM
    # = 22:30 UTC dur=4s
    ("DOGE HL SHORT dur=4s",
     "DOGE_USDT", "SHORT",
     ts(2026,7,1,22,30,0),
     ts(2026,7,1,22,30,4),
     None, None, 4),
]

print("Zero-MFE CONFIRM_REVERSAL"
      " forensic analysis")
print("Fetching Min1 candles"
      " for all 6 trades...\n")

for t in TRADES:
    try:
        analyze(*t)
    except Exception as e:
        print(f"\n{t[0]}: "
              f"ERROR {e}")

print("\nDone.")
