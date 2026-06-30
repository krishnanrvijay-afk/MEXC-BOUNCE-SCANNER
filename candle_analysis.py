import requests, csv
from datetime import datetime, timezone

BASE = "https://contract.mexc.com/api/v1/contract/kline"

def to_ts(iso_str):
    return int(datetime.fromisoformat(
        iso_str.replace('+00','')
    ).replace(
        tzinfo=timezone.utc
    ).timestamp())

def fetch_klines(symbol, interval,
                 start_ts, end_ts):
    r = requests.get(
        f"{BASE}/{symbol}",
        params={
            "interval": interval,
            "start": start_ts,
            "end": end_ts,
        }, timeout=15)
    r.raise_for_status()
    d = r.json()
    if not d.get("success"):
        raise ValueError(str(d)[:120])
    raw = d["data"]
    out = []
    for i in range(len(raw["time"])):
        out.append({
            "t": int(raw["time"][i]),
            "h": float(raw["high"][i]),
            "l": float(raw["low"][i]),
            "c": float(raw["close"][i]),
        })
    return sorted(out, key=lambda x: x["t"])

# Use Min1 candles for fine-grained
# checkpoint analysis near entry

CHECKPOINTS_SEC = [90, 300, 600, 900,
                   1800, 2700, 3600]

# All 30 trades: 20 best/worst archive
# + WIF winner/loser from today
TRADES = [
    # (label, close_utc, duration_s,
    #  symbol, direction, entry_price,
    #  final_pnl, outcome)
    ("WIF-WINNER","2026-06-29 10:03:44+00",
     17190,"WIF_USDT","LONG",0.17500,
     1200.00,"WINNER"),
    ("WIF-LOSER","2026-06-29 15:05:00+00",
     3549,"WIF_USDT","LONG",0.18040,
     -554.32,"LOSER"),
    ("BEST-1","2026-06-12 09:27:21+00",
     26446,"ZEC_USDT","LONG",None,
     237.92,"WINNER"),
    ("BEST-2","2026-06-19 22:43:12+00",
     18765,"ZEC_USDT","LONG",None,
     234.59,"WINNER"),
    ("BEST-3","2026-06-12 09:01:32+00",
     7173,"ZEC_USDT","LONG",None,
     233.50,"WINNER"),
    ("BEST-4","2026-06-12 13:42:31+00",
     13700,"ZEC_USDT","SHORT",None,
     224.23,"WINNER"),
    ("BEST-5","2026-06-14 21:30:03+00",
     35771,"ZEC_USDT","LONG",None,
     220.35,"WINNER"),
    ("BEST-6","2026-06-20 14:19:03+00",
     51219,"ZEC_USDT","SHORT",None,
     193.98,"WINNER"),
    ("BEST-7","2026-06-19 19:50:54+00",
     1350,"AVAX_USDT","LONG",None,
     190.58,"WINNER"),
    ("BEST-8","2026-06-16 15:56:28+00",
     2739,"HYPE_USDT","LONG",None,
     181.25,"WINNER"),
    ("BEST-9","2026-06-19 13:38:56+00",
     31049,"AVAX_USDT","LONG",None,
     178.27,"WINNER"),
    ("BEST-10","2026-06-19 17:16:01+00",
     44074,"AVAX_USDT","LONG",None,
     160.08,"WINNER"),
    ("WORST-1","2026-06-15 11:06:12+00",
     15031,"ZEC_USDT","SHORT",None,
     -479.63,"LOSER"),
    ("WORST-2","2026-06-18 15:55:00+00",
     41604,"ZEC_USDT","LONG",None,
     -351.93,"LOSER"),
    ("WORST-3","2026-06-18 15:54:30+00",
     41557,"ZEC_USDT","LONG",None,
     -344.75,"LOSER"),
    ("WORST-4","2026-06-14 21:35:08+00",
     5149,"ZEC_USDT","SHORT",None,
     -337.39,"LOSER"),
    ("WORST-5","2026-06-14 23:45:37+00",
     4513,"ZEC_USDT","SHORT",None,
     -333.09,"LOSER"),
    ("WORST-6","2026-06-17 12:30:39+00",
     917,"ZEC_USDT","LONG",None,
     -327.55,"LOSER"),
    ("WORST-7","2026-06-26 17:46:46+00",
     6895,"AVAX_USDT","SHORT",None,
     -303.37,"LOSER"),
    ("WORST-8","2026-06-17 12:28:33+00",
     759,"ZEC_USDT","LONG",None,
     -298.54,"LOSER"),
    ("WORST-9","2026-06-14 23:46:11+00",
     4448,"ZEC_USDT","SHORT",None,
     -291.44,"LOSER"),
    ("WORST-10","2026-06-19 03:15:26+00",
     14565,"AVAX_USDT","LONG",None,
     -208.89,"LOSER"),
]

rows = []
print(f"\n{'LABEL':<14} {'OUTCOME':<8} "
      f"{'90s':>9} {'5m':>9} {'10m':>9} "
      f"{'15m':>9} {'30m':>9} {'45m':>9} "
      f"{'60m':>9} {'FINAL':>10}")
print("-"*110)

for (label, close_utc, dur, sym,
     direction, entry_hint,
     final_pnl, outcome) in TRADES:

    close_ts = to_ts(close_utc)
    entry_ts = close_ts - dur

    try:
        # Min1 candles for fine
        # checkpoint resolution,
        # capped at min(duration, 1h)
        window = min(dur, 3700)
        c1m = fetch_klines(
            sym, "Min1",
            entry_ts,
            entry_ts + window + 60)
    except Exception as e:
        print(f"{label:<14} FETCH ERROR: {e}")
        continue

    if not c1m:
        print(f"{label:<14} NO CANDLES")
        continue

    entry_price = entry_hint or c1m[0]["c"]
    sz = (5000 * 5) / entry_price

    def pct_move(price):
        if direction == "LONG":
            return (price - entry_price) / entry_price * 100
        else:
            return (entry_price - price) / entry_price * 100

    def dollar_pnl(price):
        if direction == "LONG":
            return (price - entry_price) * sz
        else:
            return (entry_price - price) * sz

    row_vals = []
    csv_row = {
        "label": label,
        "outcome": outcome,
        "direction": direction,
        "symbol": sym,
        "final_pnl": final_pnl,
    }

    for cp_sec in CHECKPOINTS_SEC:
        if cp_sec > dur:
            row_vals.append("—")
            csv_row[f"pct_{cp_sec}s"] = ""
            csv_row[f"pnl_{cp_sec}s"] = ""
            continue
        target_ts = entry_ts + cp_sec
        # Find the lowest (worst) price
        # reached up to this checkpoint
        candles_so_far = [
            c for c in c1m
            if c["t"] <= target_ts
        ]
        if not candles_so_far:
            row_vals.append("—")
            csv_row[f"pct_{cp_sec}s"] = ""
            csv_row[f"pnl_{cp_sec}s"] = ""
            continue
        if direction == "LONG":
            worst_price = min(
                c["l"] for c in candles_so_far)
        else:
            worst_price = max(
                c["h"] for c in candles_so_far)
        pct = pct_move(worst_price)
        pnl = dollar_pnl(worst_price)
        row_vals.append(
            f"{pct:+.2f}%/${pnl:+.0f}")
        csv_row[f"pct_{cp_sec}s"] = round(pct,3)
        csv_row[f"pnl_{cp_sec}s"] = round(pnl,2)

    print(f"{label:<14} {outcome:<8} " +
          " ".join(f"{v:>9}" for v in row_vals) +
          f" {final_pnl:>+10.2f}")

    rows.append(csv_row)

fields = (["label","outcome","direction",
           "symbol","final_pnl"] +
          [f"pct_{c}s" for c in CHECKPOINTS_SEC] +
          [f"pnl_{c}s" for c in CHECKPOINTS_SEC])
with open("kill_threshold_data.csv",
          "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields,
                        extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)

print(f"\nWrote kill_threshold_data.csv"
      f" — {len(rows)} rows")
