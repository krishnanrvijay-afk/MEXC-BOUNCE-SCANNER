import requests, csv
from datetime import datetime, timezone

BASE = "https://contract.mexc.com/api/v1/contract/kline"

SYM_MAP = {
    "@107": "HYPE_USDT",
    "ZEC":  "ZEC_USDT",
}
def to_mexc(sym):
    if sym in SYM_MAP: return SYM_MAP[sym]
    if sym.endswith("_USDT"): return sym
    return sym + "_USDT"

TRADES = [
    # (label, venue, pair, dir, session,
    #  close_ts_utc, duration_s, pnl)
    ("HYPE SHORT US","mexc","HYPE_USDT","SHORT","US",
     1782756300,6598,-545.18),
    ("AVAX SHORT US","hl","AVAX","SHORT","US",
     1782756300,5238,-452.44),
    ("@107 SHORT US","hl","@107","SHORT","US",
     1782756300,6546,-572.25),
    ("WIF LONG US","hl","WIF","LONG","US",
     1782756300,14216,386.78),
    ("BTC LONG US","mexc","BTC_USDT","LONG","US",
     1782751920,8777,211.02),
    ("XRP LONG US","mexc","XRP_USDT","LONG","US",
     1782751920,5994,230.39),
    ("DOGE LONG US","mexc","DOGE_USDT","LONG","US",
     1782751920,8770,186.75),
    ("DOGE LONG US","hl","DOGE","LONG","US",
     1782751860,8603,125.23),
    ("BTC LONG US","hl","BTC","LONG","US",
     1782751860,8728,219.13),
    ("HYPE SHORT EU","mexc","HYPE_USDT","SHORT","EU",
     1782745500,14395,-189.86),
    ("WIF LONG US","mexc","WIF_USDT","LONG","US",
     1782745500,3549,-554.32),
    ("ETH LONG US","mexc","ETH_USDT","LONG","US",
     1782745440,2871,93.93),
    ("ADA LONG US","hl","ADA","LONG","US",
     1782745440,2904,78.24),
    ("AVAX LONG US","hl","AVAX","LONG","US",
     1782745440,2080,125.84),
    ("SOL SHORT EU","hl","SOL","SHORT","EU",
     1782739080,9996,-384.88),
    ("AVAX SHORT EU","hl","AVAX","SHORT","EU",
     1782739080,9989,-157.57),
    ("@107 SHORT EU","hl","@107","SHORT","EU",
     1782739080,7933,-442.32),
    ("BTC SHORT EU","hl","BTC","SHORT","EU",
     1782737580,8076,84.47),
    ("ZEC LONG EU","mexc","ZEC_USDT","LONG","EU",
     1782737580,3998,50.31),
    ("ADA SHORT EU","mexc","ADA_USDT","SHORT","EU",
     1782737520,7292,68.97),
    ("AVAX SHORT EU","mexc","AVAX_USDT","SHORT","EU",
     1782737520,7912,106.21),
    ("BTC SHORT EU","mexc","BTC_USDT","SHORT","EU",
     1782737520,8202,107.73),
    ("SUI LONG EU","hl","SUI","LONG","EU",
     1782735900,2278,296.71),
    ("ADA LONG ASIA","mexc","ADA_USDT","LONG","ASIA",
     1782727380,16796,313.81),
    ("XRP LONG ASIA","mexc","XRP_USDT","LONG","ASIA",
     1782727380,17140,274.17),
    ("ZEC LONG ASIA","mexc","ZEC_USDT","LONG","ASIA",
     1782727380,17193,505.33),
    ("WIF LONG ASIA","mexc","WIF_USDT","LONG","ASIA",
     1782727380,17190,1200.00),
    ("DOGE LONG ASIA","mexc","DOGE_USDT","LONG","ASIA",
     1782727380,17184,200.39),
    ("SUI LONG ASIA","hl","SUI","LONG","ASIA",
     1782727320,16273,439.80),
    ("@107 LONG ASIA","hl","@107","LONG","ASIA",
     1782727320,16593,307.50),
    ("XRP LONG ASIA","hl","XRP","LONG","ASIA",
     1782727320,17144,283.67),
    ("DOGE LONG ASIA","hl","DOGE","LONG","ASIA",
     1782727320,17136,193.74),
    ("ZEC LONG ASIA","hl","ZEC","LONG","ASIA",
     1782727260,17109,538.48),
    ("ETH SHORT ASIA","hl","ETH","SHORT","ASIA",
     1782706980,820,36.37),
    ("AVAX SHORT ASIA","mexc","AVAX_USDT","SHORT","ASIA",
     1782706980,1174,37.91),
    ("BTC SHORT ASIA","mexc","BTC_USDT","SHORT","ASIA",
     1782706980,2143,54.93),
    ("ETH SHORT ASIA","mexc","ETH_USDT","SHORT","ASIA",
     1782706980,1626,62.86),
    ("SOL SHORT ASIA","hl","SOL","SHORT","ASIA",
     1782706980,1230,141.94),
    ("DOGE SHORT ASIA","hl","DOGE","SHORT","ASIA",
     1782706920,1844,127.49),
]

def fetch_klines(symbol, interval,
                 start_ts, end_ts):
    url = f"{BASE}/{symbol}"
    r = requests.get(url, params={
        "interval": interval,
        "start": start_ts,
        "end": end_ts,
    }, timeout=15)
    r.raise_for_status()
    d = r.json()
    if not d.get("success"):
        raise ValueError(str(d))
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
        result.append(round(3*K - 2*D, 2))
    return result

def zone(j):
    if j < 30: return "BEARISH"
    if j < 70: return "UNDECIDED"
    return "BULLISH"

def fmt_ts(ts):
    return datetime.fromtimestamp(
        ts, tz=timezone.utc
    ).strftime("%H:%M")

def j1h_direction(j1h_vals):
    if len(j1h_vals) < 2:
        return "FLAT"
    delta = j1h_vals[-1] - j1h_vals[0]
    if delta > 10:  return "RISING"
    if delta < -10: return "FALLING"
    return "FLAT"

csv_rows = []

for (label, venue, pair, direction,
     session, close_ts, duration,
     pnl) in TRADES:

    entry_ts = close_ts - duration
    sym = to_mexc(pair)
    warmup = 2 * 3600

    print(f"\nProcessing: {label} "
          f"({sym}) pnl={pnl:+.2f}")

    try:
        c15 = fetch_klines(
            sym, "Min15",
            entry_ts - warmup,
            close_ts + 900)
        c1h = fetch_klines(
            sym, "Min60",
            entry_ts - 4*3600,
            close_ts + 3600)
    except Exception as e:
        print(f"  FETCH ERROR: {e}")
        csv_rows.append({
            "label": label,
            "venue": venue,
            "pair": pair,
            "direction": direction,
            "session": session,
            "pnl": pnl,
            "error": str(e),
        })
        continue

    j15_vals = calc_kdj(c15)
    j1h_vals_all = calc_kdj(c1h)

    # Build 1h J lookup
    h1map = {}
    for idx, c in enumerate(c1h):
        h1map[c["t"]] = j1h_vals_all[idx]
    def get_j1h(t):
        h = (t // 3600) * 3600
        if h in h1map: return h1map[h]
        for d in [-3600, 3600]:
            if h+d in h1map:
                return h1map[h+d]
        return None

    # Filter to trade window
    trade_candles = [
        (c, j15_vals[i])
        for i, c in enumerate(c15)
        if entry_ts - 900 <= c["t"]
        <= close_ts + 900
    ]

    if not trade_candles:
        print("  NO CANDLES IN WINDOW")
        continue

    # Entry / exit J values
    entry_candles = [
        (c, j) for c, j in trade_candles
        if c["t"] >= entry_ts
    ]
    exit_candles = [
        (c, j) for c, j in trade_candles
        if c["t"] <= close_ts
    ]

    j15m_entry = (entry_candles[0][1]
                  if entry_candles else None)
    j15m_exit = (exit_candles[-1][1]
                 if exit_candles else None)

    j1h_entry = (get_j1h(entry_candles[0][0]["t"])
                 if entry_candles else None)
    j1h_exit = (get_j1h(exit_candles[-1][0]["t"])
                if exit_candles else None)

    # J1H values during trade
    j1h_during = [
        get_j1h(c["t"])
        for c, _ in trade_candles
        if c["t"] >= entry_ts
           and get_j1h(c["t"]) is not None
    ]
    j1h_dir = j1h_direction(j1h_during)
    j1h_min = (min(j1h_during)
               if j1h_during else None)
    j1h_max = (max(j1h_during)
               if j1h_during else None)

    # Zone crossings
    prev_zone = None
    crossings = []
    for c, j in trade_candles:
        if c["t"] < entry_ts:
            prev_zone = zone(j)
            continue
        z = zone(j)
        if prev_zone and z != prev_zone:
            crossings.append(
                f"{fmt_ts(c['t'])}"
                f" {prev_zone[0]}"
                f"→{z[0]}"
            )
        prev_zone = z

    cross_str = " | ".join(crossings) if crossings else "NONE"

    # Print summary
    j15_entry_str = (
        f"{j15m_entry:.1f}"
        f"({zone(j15m_entry)[0]})"
        if j15m_entry is not None
        else "—"
    )
    j15_exit_str = (
        f"{j15m_exit:.1f}"
        f"({zone(j15m_exit)[0]})"
        if j15m_exit is not None
        else "—"
    )
    j1h_entry_str = (
        f"{j1h_entry:.1f}"
        f"({zone(j1h_entry)[0]})"
        if j1h_entry is not None
        else "—"
    )
    j1h_exit_str = (
        f"{j1h_exit:.1f}"
        f"({zone(j1h_exit)[0]})"
        if j1h_exit is not None
        else "—"
    )

    print(f"  J15M: {j15_entry_str} → {j15_exit_str}")
    print(f"  J1H:  {j1h_entry_str} → "
          f"{j1h_exit_str} [{j1h_dir}]")
    print(f"  J1H range: "
          f"{j1h_min:.1f}–{j1h_max:.1f}"
          if j1h_min is not None
          else "  J1H range: —")
    print(f"  CROSSES: {cross_str}")
    print(f"  PnL: {pnl:+.2f}")

    csv_rows.append({
        "label":        label,
        "venue":        venue,
        "pair":         pair,
        "direction":    direction,
        "session":      session,
        "pnl":          pnl,
        "j15m_entry":   j15m_entry,
        "j15m_entry_zone": (
            zone(j15m_entry)
            if j15m_entry else ""
        ),
        "j1h_entry":    j1h_entry,
        "j1h_entry_zone": (
            zone(j1h_entry)
            if j1h_entry else ""
        ),
        "j15m_exit":    j15m_exit,
        "j15m_exit_zone": (
            zone(j15m_exit)
            if j15m_exit else ""
        ),
        "j1h_exit":     j1h_exit,
        "j1h_exit_zone": (
            zone(j1h_exit)
            if j1h_exit else ""
        ),
        "j1h_direction": j1h_dir,
        "j1h_min":      j1h_min,
        "j1h_max":      j1h_max,
        "zone_crossings": cross_str,
        "error":        "",
    })

# Write CSV
fields = [
    "label","venue","pair",
    "direction","session","pnl",
    "j15m_entry","j15m_entry_zone",
    "j1h_entry","j1h_entry_zone",
    "j15m_exit","j15m_exit_zone",
    "j1h_exit","j1h_exit_zone",
    "j1h_direction",
    "j1h_min","j1h_max",
    "zone_crossings","error",
]
with open("all_trades_candles.csv",
          "w", newline="") as f:
    w = csv.DictWriter(f,
        fieldnames=fields,
        extrasaction="ignore")
    w.writeheader()
    w.writerows(csv_rows)

print(f"\nWrote all_trades_candles.csv"
      f" — {len(csv_rows)} rows")
