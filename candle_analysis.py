import requests, time
from datetime import datetime, timezone

BASE = (
    "https://contract.mexc.com"
    "/api/v1/contract/kline")

def fetch(symbol, interval, start, end):
    time.sleep(0.5)
    r = requests.get(
        f"{BASE}/{symbol}",
        params={"interval": interval, "start": start, "end": end},
        timeout=15)
    r.raise_for_status()
    d = r.json()
    if not d.get("success"):
        return []
    raw = d["data"]
    out = []
    for i in range(len(raw["time"])):
        out.append({
            "t": int(raw["time"][i]),
            "o": float(raw["open"][i]),
            "h": float(raw["high"][i]),
            "l": float(raw["low"][i]),
            "c": float(raw["close"][i]),
            "v": float(raw["vol"][i]) if "vol" in raw else 0.0,
        })
    return sorted(out, key=lambda x: x["t"])

def compute_kdj(candles, n=9):
    K, D = 50.0, 50.0
    result = []
    for i, c in enumerate(candles):
        w = candles[max(0, i - n + 1):i + 1]
        hi = max(x["h"] for x in w)
        lo = min(x["l"] for x in w)
        rng = hi - lo
        rsv = ((c["c"] - lo) / rng * 100 if rng > 0 else 50.0)
        K = (2/3)*K + (1/3)*rsv
        D = (2/3)*D + (1/3)*K
        result.append(round(3*K - 2*D, 2))
    return result

def fmt(ts):
    return datetime.fromtimestamp(
        ts - 14400, tz=timezone.utc).strftime("%H:%M")

def ts(iso):
    return int(
        datetime.fromisoformat(
            iso.replace('+00', '')
        ).replace(tzinfo=timezone.utc).timestamp())

def analyze(label, symbol, entry, open_ts, close_ts, exit_pnl):
    print(f"\n{'='*72}")
    print(f"  {label}")
    print(f"  entry={entry}  open={fmt(open_ts)} ET"
          f"  close={fmt(close_ts)} ET  exit_pnl={exit_pnl:+.2f}")
    print(f"{'='*72}")

    start = open_ts - 9000
    end   = close_ts + 1800

    c1m = fetch(symbol, "Min1", start, end)
    c5m = fetch(symbol, "Min5", start, end)

    if not c1m:
        print("  no candle data")
        return

    j1m = compute_kdj(c1m)
    j5m_list = compute_kdj(c5m)

    j5m_map = {}
    for i, c in enumerate(c5m):
        for o in range(5):
            j5m_map[c["t"] + o*60] = (j5m_list[i], c5m[i]["v"])

    baseline_vols = [
        c["v"] for c in c1m
        if c["t"] < open_ts - 3600
    ]
    avg_vol = (
        sum(baseline_vols) / len(baseline_vols)
        if baseline_vols else 1.0)

    comp_candles = []
    for i, c in enumerate(c1m):
        if c["t"] >= open_ts:
            break
        j5 = j5m_map.get(c["t"], (50.0, 0))[0]
        if j5 < 20:
            comp_candles.append((c, j1m[i], j5))

    if not comp_candles:
        print("  no J5M<20 window found pre-signal")
        return

    comp_start = comp_candles[0][0]["t"]
    comp_end   = comp_candles[-1][0]["t"]
    comp_duration = (comp_end - comp_start) // 60

    print(f"\n  COMPRESSION WINDOW:")
    print(f"  {fmt(comp_start)} — {fmt(comp_end)} ET ({comp_duration} min)")
    print(f"  Baseline avg vol (pre-compression): {avg_vol:.1f}")
    print(f"\n  {'TIME':>5}  {'CLOSE':>10}  {'J1M':>6}  {'J5M':>6}"
          f"  {'VOL':>10}  {'VOL/AVG':>8}  {'PATTERN'}")
    print(f"  {'-'*62}")

    for c, j1, j5 in comp_candles:
        vol_ratio = (c["v"] / avg_vol if avg_vol > 0 else 0)
        if vol_ratio < 0.5:
            pattern = "LOW VOL <- exhaustion"
        elif vol_ratio > 1.5:
            pattern = "HIGH VOL <- selling pressure"
        else:
            pattern = "NORMAL VOL"
        print(f"  {fmt(c['t']):>5}  {c['c']:10.5f}  {j1:6.1f}  {j5:6.1f}"
              f"  {c['v']:10.1f}  {vol_ratio:8.2f}x  {pattern}")

    comp_vols = [c["v"] for c, _, _ in comp_candles]
    avg_comp_vol = (
        sum(comp_vols) / len(comp_vols)
        if comp_vols else 0)
    vol_vs_baseline = (
        avg_comp_vol / avg_vol if avg_vol > 0 else 0)

    declining = (
        len(comp_vols) >= 3 and
        comp_vols[-1] < comp_vols[0])

    print(f"\n  VOLUME SUMMARY:")
    print(f"  Avg vol at compression: {avg_comp_vol:.1f}"
          f" ({vol_vs_baseline:.2f}x baseline)")
    print(f"  Volume trend: {'DECLINING' if declining else 'NOT DECLINING'}")

    if vol_vs_baseline < 0.7:
        print(f"  -> EXHAUSTION SIGNAL: volume dried up at compression bottom")
    elif vol_vs_baseline > 1.3:
        print(f"  -> CAPITULATION SIGNAL: high volume selling at bottom"
              f" (can also mark a bottom)")
    else:
        print(f"  -> NEUTRAL VOLUME: no clear exhaustion or capitulation signal")

    print(f"\n  Entry at {fmt(open_ts)} ET"
          f" — {(open_ts - comp_end) // 60} min after compression ended")
    print(f"  Exit PnL: {exit_pnl:+.2f}")


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

print("VOLUME AT COMPRESSION FORENSIC -- 7 trades")
print(f"{len(TRADES)} trades\n")

for t in TRADES:
    try:
        analyze(*t)
    except Exception as e:
        print(f"\n{t[0]}: ERROR {e}")

print("\nAll done.")
