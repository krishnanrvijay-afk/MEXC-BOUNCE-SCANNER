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

# All 20 trades: best 10 + worst 10
# (close_utc, duration_s, symbol,
#  direction, session, pnl, label)
TRADES = [
    # ── BEST 10 ────────────────────
    ("2026-06-12 09:27:21+00", 26446,
     "ZEC_USDT","LONG","ASIA",
     237.92,"BEST-1 ZEC HL LONG ASIA TP1"),
    ("2026-06-19 22:43:12+00", 18765,
     "ZEC_USDT","LONG","ASIA",
     234.59,"BEST-2 ZEC HL LONG ASIA TP1"),
    ("2026-06-12 09:01:32+00", 7173,
     "ZEC_USDT","LONG","EU",
     233.50,"BEST-3 ZEC MEXC LONG EU TP1"),
    ("2026-06-12 13:42:31+00", 13700,
     "ZEC_USDT","SHORT","EU",
     224.23,"BEST-4 ZEC MEXC SHORT EU TP1"),
    ("2026-06-14 21:30:03+00", 35771,
     "ZEC_USDT","LONG","EU",
     220.35,"BEST-5 ZEC HL LONG EU TP1"),
    ("2026-06-20 14:19:03+00", 51219,
     "ZEC_USDT","SHORT","ASIA",
     193.98,"BEST-6 ZEC HL SHORT ASIA MAN"),
    ("2026-06-19 19:50:54+00", 1350,
     "AVAX_USDT","LONG","ASIA",
     190.58,"BEST-7 AVAX HL LONG ASIA TP1"),
    ("2026-06-16 15:56:28+00", 2739,
     "HYPE_USDT","LONG","US",
     181.25,"BEST-8 HYPE MEXC LONG US TP1"),
    ("2026-06-19 13:38:56+00", 31049,
     "AVAX_USDT","LONG","ASIA",
     178.27,"BEST-9 AVAX HL LONG ASIA TP1"),
    ("2026-06-19 17:16:01+00", 44074,
     "AVAX_USDT","LONG","ASIA",
     160.08,"BEST-10 AVAX HL LONG ASIA MAN"),
    # ── WORST 10 ─────────────────
    ("2026-06-15 11:06:12+00", 15031,
     "ZEC_USDT","SHORT","ASIA",
     -479.63,"WORST-1 ZEC MEXC SHORT ASIA SL"),
    ("2026-06-18 15:55:00+00", 41604,
     "ZEC_USDT","LONG","ASIA",
     -351.93,"WORST-2 ZEC MEXC LONG ASIA SL"),
    ("2026-06-18 15:54:30+00", 41557,
     "ZEC_USDT","LONG","ASIA",
     -344.75,"WORST-3 ZEC HL LONG ASIA SL"),
    ("2026-06-14 21:35:08+00", 5149,
     "ZEC_USDT","SHORT","ASIA",
     -337.39,"WORST-4 ZEC MEXC SHORT ASIA SL"),
    ("2026-06-14 23:45:37+00", 4513,
     "ZEC_USDT","SHORT","ASIA",
     -333.09,"WORST-5 ZEC HL SHORT ASIA SL"),
    ("2026-06-17 12:30:39+00", 917,
     "ZEC_USDT","LONG","US",
     -327.55,"WORST-6 ZEC HL LONG US SL"),
    ("2026-06-26 17:46:46+00", 6895,
     "AVAX_USDT","SHORT","US",
     -303.37,"WORST-7 AVAX MEXC SHORT US DOA"),
    ("2026-06-17 12:28:33+00", 759,
     "ZEC_USDT","LONG","US",
     -298.54,"WORST-8 ZEC MEXC LONG US SL"),
    ("2026-06-14 23:46:11+00", 4448,
     "ZEC_USDT","SHORT","ASIA",
     -291.44,"WORST-9 ZEC HL SHORT ASIA SL"),
    ("2026-06-19 03:15:26+00", 14565,
     "AVAX_USDT","LONG","ASIA",
     -208.89,"WORST-10 AVAX HL LONG ASIA SL"),
]

rows = []
print(f"\n{'LABEL':<36} {'J15M-IN':>8} "
      f"{'J1H-IN':>8} {'J1H-DIR':>8} "
      f"{'J15M-OUT':>9} {'J1H-OUT':>8} "
      f"{'J1H-RNG':>12} {'PnL':>9}")
print("-"*104)

for (close_utc, dur, sym, direction,
     session, pnl, label) in TRADES:

    close_ts = to_ts(close_utc)
    entry_ts = close_ts - dur
    warmup   = 3 * 3600

    try:
        c15 = fetch_klines(
            sym, "Min15",
            entry_ts - warmup,
            close_ts + 900)
        c1h = fetch_klines(
            sym, "Min60",
            entry_ts - 6*3600,
            close_ts + 3600)
    except Exception as e:
        print(f"{label:<36} FETCH ERROR: {e}")
        rows.append({
            "label":label,"symbol":sym,
            "direction":direction,
            "session":session,"pnl":pnl,
            "error":str(e)
        })
        continue

    j15 = calc_kdj(c15)
    j1h_all = calc_kdj(c1h)

    # 1h J lookup
    hmap = {}
    for idx, c in enumerate(c1h):
        hmap[c["t"]] = j1h_all[idx]
    def gj1h(t):
        h = (t//3600)*3600
        if h in hmap: return hmap[h]
        for d in [-3600,3600]:
            if h+d in hmap:
                return hmap[h+d]
        return None

    # Entry candle
    entry_c = [(c,j15[i])
               for i,c in enumerate(c15)
               if c["t"] >= entry_ts]
    exit_c  = [(c,j15[i])
               for i,c in enumerate(c15)
               if c["t"] <= close_ts]

    j15_in  = entry_c[0][1] if entry_c else None
    j15_out = exit_c[-1][1] if exit_c  else None
    j1h_in  = gj1h(entry_c[0][0]["t"]) if entry_c else None
    j1h_out = gj1h(exit_c[-1][0]["t"]) if exit_c  else None

    # J1H during trade
    j1h_dur = [
        gj1h(c["t"])
        for c,_ in entry_c
        if gj1h(c["t"]) is not None
    ]
    jdir  = j1h_dir(j1h_dur)
    jmin  = min(j1h_dur) if j1h_dur else None
    jmax  = max(j1h_dur) if j1h_dur else None

    # Zone crossings on J15M
    prev_z = None
    crosses = []
    for c,j in entry_c:
        z = zone(j)
        if prev_z and z != prev_z:
            t_str = datetime.fromtimestamp(
                c["t"],tz=timezone.utc
            ).strftime("%H:%M")
            crosses.append(
                f"{t_str} {prev_z[0]}→{z[0]}")
        prev_z = z

    # Signal exhaustion point
    se_time = None
    se_j15  = None
    se_pnl  = None
    below50 = False
    for c,j in entry_c:
        entry_price = entry_c[0][0]["c"]
        sz = (5000*5)/entry_price
        cp = ((c["c"]-entry_price)*sz
              if direction=="LONG"
              else (entry_price-c["c"])*sz)
        if j < 50: below50 = True
        if (below50 and j >= 50
                and se_time is None
                and cp > 0
                and direction == "LONG"):
            se_time = datetime.fromtimestamp(
                c["t"],tz=timezone.utc
            ).strftime("%H:%M")
            se_j15 = j
            se_pnl = round(cp,2)
        # For SHORT: J crossing below 50
        if (direction == "SHORT"
                and j > 50 and se_time is None):
            above50_ref = True
        elif (direction == "SHORT"
                and j <= 50
                and se_time is None
                and cp > 0):
            se_time = datetime.fromtimestamp(
                c["t"],tz=timezone.utc
            ).strftime("%H:%M")
            se_j15 = j
            se_pnl = round(cp,2)

    jrng = (f"{jmin:.0f}–{jmax:.0f}"
            if jmin is not None else "—")
    j15i = f"{j15_in:.1f}" if j15_in else "—"
    j1hi = f"{j1h_in:.1f}" if j1h_in else "—"
    j15o = f"{j15_out:.1f}" if j15_out else "—"
    j1ho = f"{j1h_out:.1f}" if j1h_out else "—"

    print(f"{label:<36} {j15i:>8} "
          f"{j1hi:>8} {jdir:>8} "
          f"{j15o:>9} {j1ho:>8} "
          f"{jrng:>12} {pnl:>+9.2f}")

    if crosses:
        print(f"  {'J15M crosses:':<14} "
              f"{' | '.join(crosses[:6])}")
    if se_time:
        print(f"  {'SE fires:':<14} "
              f"{se_time} J15M={se_j15} "
              f"PnL={se_pnl:+.2f} "
              f"(vs final {pnl:+.2f})")

    rows.append({
        "label":        label,
        "symbol":       sym,
        "direction":    direction,
        "session":      session,
        "pnl":          pnl,
        "j15m_entry":   j15_in,
        "j15m_entry_zone": zone(j15_in),
        "j1h_entry":    j1h_in,
        "j1h_entry_zone": zone(j1h_in),
        "j15m_exit":    j15_out,
        "j15m_exit_zone": zone(j15_out),
        "j1h_exit":     j1h_out,
        "j1h_exit_zone": zone(j1h_out),
        "j1h_direction": jdir,
        "j1h_min":      jmin,
        "j1h_max":      jmax,
        "j15m_crosses": " | ".join(crosses[:8]),
        "se_time":      se_time or "",
        "se_j15m":      se_j15 or "",
        "se_pnl":       se_pnl or "",
        "error":        "",
    })

# Write CSV
fields = [
    "label","symbol","direction",
    "session","pnl",
    "j15m_entry","j15m_entry_zone",
    "j1h_entry","j1h_entry_zone",
    "j15m_exit","j15m_exit_zone",
    "j1h_exit","j1h_exit_zone",
    "j1h_direction","j1h_min","j1h_max",
    "j15m_crosses","se_time",
    "se_j15m","se_pnl","error",
]
with open("sentinel_case.csv",
          "w", newline="") as f:
    w = csv.DictWriter(
        f, fieldnames=fields,
        extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)

print(f"\nWrote sentinel_case.csv"
      f" — {len(rows)} rows")
