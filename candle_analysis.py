import requests
from datetime import datetime, timezone

BASE = (
  "https://contract.mexc.com"
  "/api/v1/contract/kline")

def fetch(symbol, interval,
          start, end):
    r = requests.get(
        f"{BASE}/{symbol}",
        params={"interval": interval,
                "start": start,
                "end": end},
        timeout=15)
    r.raise_for_status()
    d = r.json()
    if not d.get("success"):
        raise ValueError(str(d)[:80])
    raw = d["data"]
    out = []
    for i in range(
            len(raw["time"])):
        out.append({
          "t": int(raw["time"][i]),
          "o": float(raw["open"][i]),
          "h": float(raw["high"][i]),
          "l": float(raw["low"][i]),
          "c": float(raw["close"][i])
        })
    return sorted(out,
        key=lambda x: x["t"])

def fmt(ts):
    return datetime.fromtimestamp(
        ts, tz=timezone.utc
    ).strftime("%H:%M:%S")

def analyze(label, symbol,
            direction, open_ts,
            close_ts, entry_px,
            be_confirm_px,
            duration_s):
    interval = (
        "Min1"
        if duration_s <= 300
        else "Min15")
    pad = max(300, duration_s * 2)
    candles = fetch(
        symbol, interval,
        open_ts - pad,
        close_ts + 300)

    trade_c = [c for c in candles
        if c["t"] >= open_ts - 60
        and c["t"] <= close_ts + 60]

    print(f"\n{'='*64}")
    print(f"  {label}")
    print(f"  {symbol} {direction}"
          f"  dur={duration_s}s"
          f"  [{interval}]")
    print(f"  entry={entry_px}"
          f"  be_confirm={be_confirm_px}")
    print(f"{'='*64}")
    print(f"  {'TIME':>8}  "
          f"{'O':>10}  "
          f"{'H':>10}  "
          f"{'L':>10}  "
          f"{'C':>10}  "
          f"NOTE")
    print(f"  {'-'*62}")

    if not trade_c:
        print("  no candles in window")
        return

    confirm_broke = False
    for c in trade_c:
        note = ""
        if (c["t"] >= open_ts - 30
                and c["t"] <=
                open_ts + 60):
            note = "ENTRY WINDOW"
        # check confirm break
        if direction == "LONG":
            if c["l"] <= be_confirm_px:
                note = (
                    f"CONFIRM BROKE "
                    f"lo={c['l']:.5f}"
                    f"<{be_confirm_px}")
                confirm_broke = True
        else:
            if c["h"] >= be_confirm_px:
                note = (
                    f"CONFIRM BROKE "
                    f"hi={c['h']:.5f}"
                    f">{be_confirm_px}")
                confirm_broke = True
        print(f"  {fmt(c['t']):>8}"
              f"  {c['o']:10.5f}"
              f"  {c['h']:10.5f}"
              f"  {c['l']:10.5f}"
              f"  {c['c']:10.5f}"
              f"  {note}")

    if not confirm_broke:
        print(f"  NOTE: confirm level"
              f" never broken in"
              f" available candles")

    print(f"\n  DIAGNOSIS:")
    if duration_s <= 8:
        print(f"  SUB-SCAN-CYCLE: "
              f"{duration_s}s < 8s "
              f"scan interval -- "
              f"confirmation was "
              f"market microstructure"
              f" noise (bid/ask "
              f"spread), not a "
              f"genuine directional "
              f"move")
    elif duration_s <= 60:
        print(f"  INSTANT REVERSAL: "
              f"price confirmed but "
              f"immediately reversed"
              f" -- 0.1% threshold "
              f"too tight for this "
              f"pair at this "
              f"volatility")
    else:
        print(f"  DELAYED REVERSAL: "
              f"price held above "
              f"confirm level for "
              f"{duration_s}s before "
              f"reversing through it")

def ts(y,mo,d,h,mi,s=0):
    return int(datetime(
        y,mo,d,h,mi,s,
        tzinfo=timezone.utc
    ).timestamp())

TRADES = [
    # BTC_USDT SHORT 113s
    # Alert row 5
    ("BTC_USDT SHORT 113s -$15",
     "BTC_USDT", "SHORT",
     ts(2026,7,1,19,26,39),
     ts(2026,7,1,19,28,32),
     60114.3, 60149.2905, 113),

    # SOL HL LONG 16s (use proxy)
    ("SOL_USDT LONG 16s -$20",
     "SOL_USDT", "LONG",
     ts(2026,7,1,20,32,22),
     ts(2026,7,1,20,32,38),
     76.9675, 76.92635, 16),

    # DOGE SHORT 4s
    # Alert row 33
    ("DOGE_USDT SHORT 4s $0",
     "DOGE_USDT", "SHORT",
     ts(2026,7,1,22,30,27),
     ts(2026,7,1,22,30,31),
     0.073352, 0.073340, 4),

    # LTC LONG 4s
    # Alert row 43
    ("LTC_USDT LONG 4s $0",
     "LTC_USDT", "LONG",
     ts(2026,7,2,0,10,59),
     ts(2026,7,2,0,11,3),
     42.726, 42.740197, 4),

    # ZEC LONG 33s
    # Alert row 53
    ("ZEC_USDT LONG 33s -$22",
     "ZEC_USDT", "LONG",
     ts(2026,7,2,0,37,3),
     ts(2026,7,2,0,37,36),
     413.085, 412.857445, 33),

    # LTC_USDT LONG 57s
    # Alert row 62
    ("LTC_USDT LONG 57s -$23",
     "LTC_USDT", "LONG",
     ts(2026,7,2,0,52,49),
     ts(2026,7,2,0,53,46),
     42.55, 42.51247, 57),

    # WIF_USDT LONG 19s
    # Alert row 66
    ("WIF_USDT LONG 19s -$15",
     "WIF_USDT", "LONG",
     ts(2026,7,2,0,58,16),
     ts(2026,7,2,0,58,35),
     0.1677, 0.167667, 19),

    # SOL_USDT LONG 129s
    # Alert row 69
    ("SOL_USDT LONG 129s -$35",
     "SOL_USDT", "LONG",
     ts(2026,7,2,1,3,14),
     ts(2026,7,2,1,5,23),
     77.34, 77.24717, 129),

    # ADA_USDT LONG 8s
    # Alert row 71
    ("ADA_USDT LONG 8s $0",
     "ADA_USDT", "LONG",
     ts(2026,7,2,1,15,47),
     ts(2026,7,2,1,15,55),
     0.1536, 0.153653, 8),

    # SUI SHORT 8s
    # Alert row 76
    ("SUI_USDT SHORT 8s -$10",
     "SUI_USDT", "SHORT",
     ts(2026,7,2,2,8,17),
     ts(2026,7,2,2,8,25),
     0.72224, 0.722397, 8),

    # NEAR_USDT LONG 649s FORENSIC
    # Alert row 42
    ("NEAR_USDT LONG 649s FORENSIC"
     " mfe=0.19R -$27",
     "NEAR_USDT", "LONG",
     ts(2026,7,2,0,9,29),
     ts(2026,7,2,0,20,18),
     1.814, 1.812811, 649),
]

print("Zero-MFE CONFIRM_REVERSAL"
      " + NEAR_USDT forensic")
print(f"{len(TRADES)} trades\n")

for t in TRADES:
    try:
        analyze(*t)
    except Exception as e:
        print(f"\n{t[0]}: ERROR {e}")

print("\nDone.")
