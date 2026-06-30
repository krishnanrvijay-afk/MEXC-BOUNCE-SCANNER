import requests, csv
from datetime import datetime, timezone

BASE = "https://contract.mexc.com/api/v1/contract/kline"
SYMBOL = "WIF_USDT"

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
        raise ValueError(str(d)[:150])
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

def calc_kdj(candles, n=9):
    K, D = 50.0, 50.0
    result = []
    for i, c in enumerate(candles):
        w = candles[max(0,i-n+1):i+1]
        hi = max(x["h"] for x in w)
        lo = min(x["l"] for x in w)
        rng = hi - lo
        rsv = (c["c"]-lo)/rng*100 if rng>0 else 50.0
        K = (2/3)*K + (1/3)*rsv
        D = (2/3)*D + (1/3)*K
        result.append(round(3*K-2*D, 2))
    return result

def zone(j):
    if j is None: return "—"
    if j < 30: return "BEARISH"
    if j < 70: return "UNDECIDED"
    return "BULLISH"

def j1h_dir(vals):
    v = [x for x in vals if x is not None]
    if len(v) < 2: return "FLAT"
    d = v[-1] - v[0]
    if d > 10:  return "RISING"
    if d < -10: return "FALLING"
    return "FLAT"

def fmt_ts(ts):
    return datetime.fromtimestamp(
        ts, tz=timezone.utc
    ).strftime("%H:%M")

# Three WIF_USDT trades June 29-30
TRADES = [
    ("WIF-1 ASIA WINNER",
     "2026-06-29 10:03:00+00", 17190,
     "LONG", 0.17500, 1200.00),
    ("WIF-2 US LOSER",
     "2026-06-29 15:05:00+00", 3549,
     "LONG", 0.18040, -554.32),
    ("WIF-3 LATE ASIA LOSER",
     "2026-06-30 02:25:00+00", 13592,
     "LONG", None, -745.64),
]

print(f"\n{'LABEL':<22} {'J15M-IN':>8} "
      f"{'J1H-IN':>8} {'J1H-DIR':>8} "
      f"{'J15M-OUT':>9} {'J1H-OUT':>8} "
      f"{'J1H-RNG':>12} {'PnL':>10}")
print("-"*100)

rows = []

for (label, close_utc, dur, direction,
     entry_hint, pnl) in TRADES:

    close_ts = int(datetime.fromisoformat(
        close_utc.replace('+00','')
    ).replace(tzinfo=timezone.utc).timestamp())
    entry_ts = close_ts - dur
    warmup = 3 * 3600

    try:
        c15 = fetch_klines(
            SYMBOL, "Min15",
            entry_ts - warmup,
            close_ts + 900)
        c1h = fetch_klines(
            SYMBOL, "Min60",
            entry_ts - 6*3600,
            close_ts + 3600)
    except Exception as e:
        print(f"{label:<22} FETCH ERROR: {e}")
        continue

    j15 = calc_kdj(c15)
    j1h_all = calc_kdj(c1h)
    hmap = {}
    for idx, c in enumerate(c1h):
        hmap[c["t"]] = j1h_all[idx]
    def gj1h(t):
        h = (t//3600)*3600
        if h in hmap: return hmap[h]
        for d in [-3600,3600]:
            if h+d in hmap: return hmap[h+d]
        return None

    entry_c = [(c,j15[i]) for i,c in
               enumerate(c15) if c["t"]>=entry_ts]
    exit_c  = [(c,j15[i]) for i,c in
               enumerate(c15) if c["t"]<=close_ts]

    if not entry_c or not exit_c:
        print(f"{label:<22} NO CANDLES IN WINDOW")
        continue

    j15_in  = entry_c[0][1]
    j15_out = exit_c[-1][1]
    j1h_in  = gj1h(entry_c[0][0]["t"])
    j1h_out = gj1h(exit_c[-1][0]["t"])

    j1h_dur = [gj1h(c["t"]) for c,_ in entry_c
               if c["t"]<=close_ts
               and gj1h(c["t"]) is not None]
    jdir = j1h_dir(j1h_dur)
    jmin = min(j1h_dur) if j1h_dur else None
    jmax = max(j1h_dur) if j1h_dur else None

    entry_price = entry_hint or entry_c[0][0]["c"]

    prev_z = None
    crosses = []
    for c,j in entry_c:
        if c["t"] > close_ts: break
        z = zone(j)
        if prev_z and z != prev_z:
            sz = (5000*5)/entry_price
            cp = ((c["c"]-entry_price)*sz
                  if direction=="LONG"
                  else (entry_price-c["c"])*sz)
            crosses.append(
                f"{fmt_ts(c['t'])} "
                f"{prev_z[0]}→{z[0]} "
                f"(${cp:+.0f})")
        prev_z = z

    jrng = (f"{jmin:.0f}–{jmax:.0f}"
            if jmin is not None else "—")

    print(f"{label:<22} {j15_in:>8.1f} "
          f"{j1h_in or 0:>8.1f} {jdir:>8} "
          f"{j15_out:>9.1f} {j1h_out or 0:>8.1f} "
          f"{jrng:>12} {pnl:>+10.2f}")

    if crosses:
        print(f"  {'J15M crosses:':<16}"
              f"{' | '.join(crosses)}")

    print(f"  {'Entry price:':<16}"
          f"{entry_price:.5f}  "
          f"{'Exit price:':<14}"
          f"{exit_c[-1][0]['c']:.5f}")

    rows.append({
        "label": label,
        "direction": direction,
        "pnl": pnl,
        "j15m_entry": j15_in,
        "j15m_entry_zone": zone(j15_in),
        "j1h_entry": j1h_in,
        "j1h_entry_zone": zone(j1h_in),
        "j15m_exit": j15_out,
        "j15m_exit_zone": zone(j15_out),
        "j1h_exit": j1h_out,
        "j1h_exit_zone": zone(j1h_out),
        "j1h_direction": jdir,
        "j1h_min": jmin,
        "j1h_max": jmax,
        "entry_price": entry_price,
        "exit_price": exit_c[-1][0]["c"],
        "j15m_crosses": " | ".join(crosses),
    })
    print()

fields = ["label","direction","pnl",
    "j15m_entry","j15m_entry_zone",
    "j1h_entry","j1h_entry_zone",
    "j15m_exit","j15m_exit_zone",
    "j1h_exit","j1h_exit_zone",
    "j1h_direction","j1h_min","j1h_max",
    "entry_price","exit_price",
    "j15m_crosses"]
with open("wif_all_trades.csv",
          "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields,
                        extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)

print(f"Wrote wif_all_trades.csv — {len(rows)} rows")
