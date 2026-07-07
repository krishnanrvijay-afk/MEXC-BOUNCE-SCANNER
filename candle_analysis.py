import requests, time
from datetime import datetime, timezone

BASE = (
  "https://contract.mexc.com"
  "/api/v1/contract/kline")

def fetch(symbol, interval,
          start, end):
    time.sleep(0.5)
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
        return []
    raw = d["data"]
    out = []
    for i in range(
            len(raw["time"])):
        out.append({
          "t": int(raw["time"][i]),
          "o": float(raw["open"][i]),
          "h": float(raw["high"][i]),
          "l": float(raw["low"][i]),
          "c": float(raw["close"][i]),
        })
    return sorted(
        out, key=lambda x: x["t"])

def compute_kdj(candles, n=9):
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
        result.append(
            round(3*K-2*D, 2))
    return result

def fmt(ts):
    return datetime.fromtimestamp(
        ts - 14400,
        tz=timezone.utc
    ).strftime("%H:%M")

def pnl_long(entry, price,
        margin=5000, lev=5):
    sz = (margin * lev) / entry
    return round(
        (price - entry) * sz, 2)

def ts(iso):
    return int(
        datetime.fromisoformat(
            iso.replace('+00','')
        ).replace(
            tzinfo=timezone.utc
        ).timestamp())

def analyze(label, symbol,
            entry, open_ts,
            close_ts, exit_pnl,
            direction="LONG"):
    print(f"\n{'='*72}")
    print(f"  {label}")
    print(f"  {symbol} {direction}"
          f"  entry={entry}"
          f"  exit_pnl={exit_pnl:+.2f}")
    print(f"  open={fmt(open_ts)} ET"
          f"  close={fmt(close_ts)} ET")
    print(f"{'='*72}")

    start = open_ts - 5400
    end   = close_ts + 3600

    c1m  = fetch(symbol,"Min1",
        start, end)
    c5m  = fetch(symbol,"Min5",
        start, end)
    c15m = fetch(symbol,"Min15",
        start, end)

    if not c1m:
        print("  no candle data")
        return

    j1m  = compute_kdj(c1m)
    j5m  = compute_kdj(c5m)
    j15m = compute_kdj(c15m)

    j5m_map = {}
    for i,c in enumerate(c5m):
        for o in range(5):
            j5m_map[c["t"]+o*60] = \
                j5m[i]

    j15m_map = {}
    for i,c in enumerate(c15m):
        for o in range(15):
            j15m_map[c["t"]+o*60] \
                = j15m[i]

    j5_first  = None
    j15_first = None
    post_peak = None

    print(f"  {'TIME':>5}"
          f"  {'CLOSE':>10}"
          f"  {'PNL':>9}"
          f"  {'J1M':>6}"
          f"  {'J5M':>6}"
          f"  {'J15M':>6}"
          f"  NOTE")
    print(f"  {'-'*65}")

    for i,c in enumerate(c1m):
        j1 = j1m[i]
        j5 = j5m_map.get(c["t"],0)
        j15= j15m_map.get(c["t"],0)
        p  = pnl_long(entry,c["c"])

        if (j5 < 20 and
                j5_first is None and
                c["t"] < open_ts):
            j5_first = c["t"]
        if (j15 < 20 and
                j15_first is None and
                c["t"] < open_ts):
            j15_first = c["t"]

        if (c["t"] > close_ts and
                (post_peak is None
                 or p > post_peak)):
            post_peak = p

        note = ""
        if abs(c["t"]-open_ts)<90:
            note = "★ ENTRY"
        elif abs(c["t"]-close_ts)<90:
            note = "★ EXIT"
        elif c["t"] < open_ts:
            if j5<20 and j15<20:
                note = "⚡BOTH<20"
            elif j5<20:
                note = "J5M<20"
            elif j15<20:
                note = "J15M<20"
        elif c["t"] > close_ts:
            note = "post"

        # only print pre-signal
        # window last 30 min,
        # trade duration, and
        # 30 min post-exit
        in_pre = (
            c["t"] >= open_ts-1800
            and c["t"] < open_ts)
        in_trade = (
            c["t"] >= open_ts
            and c["t"] <= close_ts)
        in_post = (
            c["t"] > close_ts
            and c["t"] <=
            close_ts+1800)

        if in_pre or in_trade \
                or in_post:
            print(
                f"  {fmt(c['t']):>5}"
                f"  {c['c']:10.5f}"
                f"  {p:9.2f}"
                f"  {j1:6.1f}"
                f"  {j5:6.1f}"
                f"  {j15:6.1f}"
                f"  {note}")

    print(f"\n  SUMMARY:")
    if j5_first:
        lag = (open_ts-j5_first)//60
        print(f"  J5M<20 first at"
              f" {fmt(j5_first)} ET"
              f" — {lag}m before"
              f" entry")
    else:
        print(f"  J5M never <20"
              f" pre-signal")
    if j15_first:
        lag=(open_ts-j15_first)//60
        print(f"  J15M<20 first at"
              f" {fmt(j15_first)} ET"
              f" — {lag}m before"
              f" entry")
    else:
        print(f"  J15M never <20"
              f" pre-signal")
    if post_peak is not None:
        print(f"  Post-exit best"
              f" PnL: +${post_peak:.2f}"
              f" (left on table"
              f" vs exit"
              f" {exit_pnl:+.2f})")

TRADES = [
    ("WIF PEAK_DECAY +$44",
     "WIF_USDT", 0.17140,
     ts("2026-07-06 20:45:44+00"),
     ts("2026-07-06 20:56:08+00"),
     43.76),

    ("ADA TP1+RUNNER +$338",
     "ADA_USDT", 0.18330,
     ts("2026-07-06 21:07:32+00"),
     ts("2026-07-06 21:10:59+00"),
     338.25),

    ("DOGE KILL -$101",
     "DOGE_USDT", 0.076810,
     ts("2026-07-06 23:31:13+00"),
     ts("2026-07-07 00:08:59+00"),
     -100.9),

    ("XRP SE +$2",
     "XRP_USDT", 0.11452,
     ts("2026-07-06 23:46:08+00"),
     ts("2026-07-07 00:00:43+00"),
     2.18),

    ("SOL 3C_LOWER_LOW +$98",
     "SOL_USDT", 81.970,
     ts("2026-07-06 23:55:43+00"),
     ts("2026-07-07 00:30:05+00"),
     97.6),

    ("SUI PEAK_DECAY +$113",
     "SUI_USDT", 0.74950,
     ts("2026-07-07 00:00:29+00"),
     ts("2026-07-07 00:28:44+00"),
     113.41),

    ("LINK PEAK_DECAY +$100",
     "LINK_USDT", 8.0240,
     ts("2026-07-07 00:16:22+00"),
     ts("2026-07-07 00:29:40+00"),
     99.7),
]

print("J5M vs J15M LAG FORENSIC")
print(f"{len(TRADES)} trades\n")

for t in TRADES:
    try:
        analyze(*t)
    except Exception as e:
        print(f"\n{t[0]}: ERROR {e}")

print("\nAll done.")
