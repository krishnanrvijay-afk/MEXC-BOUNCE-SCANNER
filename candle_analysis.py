import requests
from datetime import datetime, timezone

BASE = "https://contract.mexc.com/api/v1/contract/kline"

def fetch_klines(symbol, interval,
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
        raise ValueError(str(d)[:120])
    raw = d["data"]
    out = []
    for i in range(len(raw["time"])):
        out.append({
            "t": int(raw["time"][i]),
            "c": float(raw["close"][i]),
            "h": float(raw["high"][i]),
            "l": float(raw["low"][i]),
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
        rsv = ((c["c"]-lo)/rng*100
               if rng > 0 else 50.0)
        K = (2/3)*K + (1/3)*rsv
        D = (2/3)*D + (1/3)*K
        result.append(round(3*K-2*D, 2))
    return result

def fmt(ts):
    return datetime.fromtimestamp(
        ts, tz=timezone.utc
    ).strftime("%H:%M")

def analyze(label, symbol, direction,
            entry_ts, close_ts,
            j1h_entry, loss_dollars):
    warmup15 = 3 * 3600
    warmup1h = 6 * 3600

    # J15M for intra-trade momentum
    c15 = fetch_klines(symbol, "Min15",
        entry_ts - warmup15,
        close_ts + 900)
    j15_vals = calc_kdj(c15)

    # J1H for background context only
    c1h = fetch_klines(symbol, "Min60",
        entry_ts - warmup1h,
        close_ts + 3600)
    j1h_vals = calc_kdj(c1h)

    # build J1H lookup by hour
    j1h_map = {}
    for i, c in enumerate(c1h):
        j1h_map[c["t"]] = j1h_vals[i]

    def get_j1h(t):
        h = (t // 3600) * 3600
        for delta in [0, -3600, 3600]:
            if h + delta in j1h_map:
                return j1h_map[h+delta]
        return None

    # trade candles
    trade_c = [
        (c, j15_vals[i])
        for i, c in enumerate(c15)
        if c["t"] >= entry_ts
        and c["t"] <= close_ts
    ]

    if not trade_c:
        print(f"\n{label}: no candles")
        return

    # derive entry price from first
    # candle at or after entry_ts
    entry_price = trade_c[0][0]["c"]

    # tracking state
    j15_peak = None
    j15_peak_time = None
    j15_at_cross = None
    decay_at_cross = None
    ever_profitable = False
    se_would_fire_ts = None
    se_would_fire_pnl = None

    print(f"\n{'='*68}")
    print(f"  {label}")
    print(f"  {symbol} {direction}  "
          f"j1h_entry={j1h_entry:.1f}  "
          f"loss=${loss_dollars}")
    print(f"  Entry: {fmt(entry_ts)} UTC  "
          f"Close: {fmt(close_ts)} UTC  "
          f"Dur: "
          f"{(close_ts-entry_ts)//60}m")
    print(f"  Entry price (1st candle): "
          f"{entry_price:.5f}")
    print(f"{'='*68}")
    print(f"  {'TIME':>5}  {'PRICE':>9}  "
          f"{'J15M':>7}  {'PEAK':>7}  "
          f"{'DECAY':>7}  "
          f"{'J1H':>6}  NOTE")
    print(f"  {'-'*64}")

    for c, j15 in trade_c:
        j1h = get_j1h(c["t"])
        sz = 1000.0 / entry_price
        cpnl = ((c["c"] - entry_price)
                * sz
                if direction == "LONG"
                else
                (entry_price - c["c"])
                * sz)

        if cpnl > 0:
            ever_profitable = True

        # track J15M peak (LONG) or
        # trough (SHORT)
        if direction == "LONG":
            if (j15_peak is None or
                    j15 > j15_peak):
                j15_peak = j15
                j15_peak_time = c["t"]
            decay = (j15_peak - j15
                     if j15_peak else 0)
            price_adverse = (
                c["c"] < entry_price)
        else:
            if (j15_peak is None or
                    j15 < j15_peak):
                j15_peak = j15
                j15_peak_time = c["t"]
            decay = (j15 - j15_peak
                     if j15_peak else 0)
            price_adverse = (
                c["c"] > entry_price)

        # when did price cross back
        # through entry
        if (price_adverse and
                j15_at_cross is None
                and ever_profitable):
            j15_at_cross = j15
            decay_at_cross = decay

        # SE fire simulation —
        # current: cpnl > 0 AND
        # decay >= 10
        # proposed: ever_profitable
        # AND decay >= threshold
        se_current = (cpnl > 0 and
                      decay >= 10)
        se_proposed = (ever_profitable
                       and decay >= 10)

        note = ""
        if c["t"] == trade_c[0][0]["t"]:
            note = "ENTRY"
        if (j15_peak_time and
                c["t"] == j15_peak_time
                and note == ""):
            note = "J15M PEAK"
        if (price_adverse and
                j15_at_cross == j15
                and decay_at_cross == decay
                and not note):
            note = "PRICE→NEGATIVE"
        if (se_would_fire_ts is None
                and se_proposed
                and not se_current):
            se_would_fire_ts = c["t"]
            se_would_fire_pnl = cpnl
            note = "SE★PROPOSED FIRES"
        elif (se_would_fire_ts is None
              and se_current):
            se_would_fire_ts = c["t"]
            se_would_fire_pnl = cpnl
            note = "SE CURRENT FIRES"

        print(f"  {fmt(c['t']):>5}  "
              f"{c['c']:9.5f}  "
              f"{j15:7.1f}  "
              f"{j15_peak or 0:7.1f}  "
              f"{decay:7.1f}  "
              f"{j1h or 0:6.1f}  "
              f"{note}")

    print(f"\n  SUMMARY:")
    print(f"  J1H at entry:        "
          f"{j1h_entry:.1f} (hourly "
          f"context — barely moves "
          f"in {(close_ts-entry_ts)//60}m)")
    if j15_peak:
        print(f"  J15M peak:           "
              f"{j15_peak:.1f} "
              f"at {fmt(j15_peak_time)}")
    if j15_at_cross is not None:
        print(f"  J15M when price went "
              f"negative: "
              f"{j15_at_cross:.1f}")
        print(f"  J15M decay at that   "
              f"moment: "
              f"{decay_at_cross:.1f} pts")
    if se_would_fire_ts:
        print(f"  SE fires at:         "
              f"{fmt(se_would_fire_ts)} "
              f"PnL={se_would_fire_pnl:+.2f}")
    else:
        print(f"  SE never fires "
              f"(decay never >= 10)")

def ts(y, mo, d, h, mi):
    return int(datetime(
        y, mo, d, h, mi,
        tzinfo=timezone.utc
    ).timestamp())

TRADES = [
    ("NEAR_USDT LONG MFE 0.30R -$139",
     "NEAR_USDT", "LONG",
     ts(2026,7,1,8,2),
     ts(2026,7,1,8,23),
     55.0, -139.51),
    ("ZEC_USDT LONG MFE 0.23R -$125",
     "ZEC_USDT", "LONG",
     ts(2026,7,1,8,4),
     ts(2026,7,1,8,23),
     45.91, -125.51),
    ("XRP_USDT LONG MFE 0.15R -$110",
     "XRP_USDT", "LONG",
     ts(2026,7,1,7,28),
     ts(2026,7,1,8,34),
     69.45, -110.35),
    ("LTC_USDT LONG MFE 0.18R -$111",
     "LTC_USDT", "LONG",
     ts(2026,7,1,7,29),
     ts(2026,7,1,8,0),
     68.47, -111.68),
    ("SOL_USDT SHORT MFE 0.27R -$110",
     "SOL_USDT", "SHORT",
     ts(2026,7,1,3,17),
     ts(2026,7,1,3,36),
     90.56, -110.68),
    ("BTC_USDT SHORT MFE 0.12R -$110",
     "BTC_USDT", "SHORT",
     ts(2026,7,1,3,18),
     ts(2026,7,1,3,52),
     99.94, -110.18),
]

print("Fetching Min15 candles for "
      f"{len(TRADES)} KILL trades...")
print("SE current = cpnl>0 + 10pt decay")
print("SE proposed = ever_profitable "
      "+ 10pt decay")
print()

for t in TRADES:
    try:
        analyze(*t)
    except Exception as e:
        print(f"\n{t[0]}: ERROR {e}")

print("\nDone.")
