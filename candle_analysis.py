import requests
from datetime import datetime, timezone

BASE = (
  "https://contract.mexc.com"
  "/api/v1/contract/kline")

def fetch(symbol, interval,
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
        J = round(3*K - 2*D, 2)
        result.append(J)
    return result

def fmt_et(ts):
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

# WIF_USDT LONG
# Signal: 16:45 ET = 20:45 UTC
# Close: 16:56 ET = 20:56 UTC
# Entry: 0.17140
# Exit: PEAK_DECAY_20 +$43.76

SYMBOL   = "WIF_USDT"
ENTRY    = 0.17140
SIGNAL_TS = ts(
    "2026-07-06 20:45:00+00")
CLOSE_TS  = ts(
    "2026-07-06 20:56:00+00")
START     = SIGNAL_TS - 3600
END       = CLOSE_TS + 1800

print("Fetching candles...")
c1m = fetch(SYMBOL, "Min1",
    START, END)
c5m = fetch(SYMBOL, "Min5",
    START, END)
c15m = fetch(SYMBOL, "Min15",
    START, END)

# Compute J values on all
# three timeframes
j1m_vals  = compute_kdj(c1m)
j5m_vals  = compute_kdj(c5m)
j15m_vals = compute_kdj(c15m)

# Map J5M and J15M values to
# minute timestamps for lookup
j5m_map = {}
for i, c in enumerate(c5m):
    for offset in range(5):
        j5m_map[c["t"] + offset*60] \
            = j5m_vals[i]

j15m_map = {}
for i, c in enumerate(c15m):
    for offset in range(15):
        j15m_map[c["t"]
            + offset*60] \
            = j15m_vals[i]

print(f"\n{'='*90}")
print(f"  WIF_USDT LONG FORENSIC"
      f" — J1M / J5M / J15M"
      f" RELATIONSHIP")
print(f"  Entry: {ENTRY}"
      f"  Signal: {fmt_et(SIGNAL_TS)}"
      f" ET")
print(f"{'='*90}")
print(f"  {'TIME':>5}"
      f"  {'CLOSE':>9}"
      f"  {'PNL':>9}"
      f"  {'J1M':>7}"
      f"  {'J5M':>7}"
      f"  {'J15M':>7}"
      f"  {'J5<20':>6}"
      f"  {'J15<20':>7}"
      f"  NOTE")
print(f"  {'-'*80}")

for i, c in enumerate(c1m):
    j1m  = j1m_vals[i]
    j5m  = j5m_map.get(c["t"], 0)
    j15m = j15m_map.get(c["t"], 0)
    cpnl = pnl_long(ENTRY, c["c"])
    j5_sig  = "YES" if j5m  < 20 \
        else "---"
    j15_sig = "YES" if j15m < 20 \
        else "---"

    note = ""
    if abs(c["t"]-SIGNAL_TS) < 90:
        note = "★ SIGNAL"
    elif c["t"] > SIGNAL_TS and \
            c["t"] <= CLOSE_TS:
        note = "IN TRADE"
    elif c["t"] > CLOSE_TS:
        note = "POST-EXIT"

    # flag when both J5M and
    # J15M are compressed
    if (j5m < 20 and j15m < 20
            and not note):
        note = "⚡ BOTH COMPRESSED"
    elif (j5m < 20 and j15m >= 20
            and not note):
        note = "J5M only compressed"
    elif (j5m >= 20 and j15m < 20
            and not note):
        note = "J15M only compressed"

    print(
        f"  {fmt_et(c['t']):>5}"
        f"  {c['c']:9.5f}"
        f"  {cpnl:9.2f}"
        f"  {j1m:7.1f}"
        f"  {j5m:7.1f}"
        f"  {j15m:7.1f}"
        f"  {j5_sig:>6}"
        f"  {j15_sig:>7}"
        f"  {note}")

print(f"\n{'='*90}")
print(f"  SUMMARY")
print(f"{'='*90}")

# Find when J5M first
# compressed below 20
j5m_first = None
j15m_first = None
for i, c in enumerate(c1m):
    j5m  = j5m_map.get(c["t"], 0)
    j15m = j15m_map.get(c["t"], 0)
    if j5m_first is None \
            and j5m < 20 \
            and c["t"] < SIGNAL_TS:
        j5m_first = c["t"]
    if j15m_first is None \
            and j15m < 20 \
            and c["t"] < SIGNAL_TS:
        j15m_first = c["t"]

if j5m_first:
    lag = (SIGNAL_TS - j5m_first) \
        // 60
    print(f"  J5M first compressed"
          f" <20: {fmt_et(j5m_first)}"
          f" ET ({lag} min before"
          f" signal)")
else:
    print(f"  J5M never compressed"
          f" <20 before signal")

if j15m_first:
    lag = (SIGNAL_TS - j15m_first) \
        // 60
    print(f"  J15M first compressed"
          f" <20: {fmt_et(j15m_first)}"
          f" ET ({lag} min before"
          f" signal)")
else:
    print(f"  J15M never compressed"
          f" <20 before signal")

if j5m_first and j15m_first:
    diff = (j15m_first - j5m_first) \
        // 60
    print(f"  J5M led J15M by:"
          f" {diff} minutes")

print(f"\n  Price at J5M compression:"
      f" entry reference {ENTRY}")
print(f"  Price at signal:"
      f" {ENTRY} (entry)")
print(f"  Best post-signal PnL:"
      f" +$43.76 (PEAK_DECAY_20)")
print("\nDone.")
