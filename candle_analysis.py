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

def fmt_et(ts):
    return datetime.fromtimestamp(
        ts - 14400,
        tz=timezone.utc
    ).strftime("%H:%M:%S")

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

SYMBOL   = "NEAR_USDT"
ENTRY    = 1.8658
SL       = None
BE_PRICE = ENTRY * 0.999
OPEN_TS  = ts(
    "2026-07-08 21:01:17+00")
CLOSE_TS = ts(
    "2026-07-08 21:14:01+00")
EXIT_PNL = -44.89
MAE_R    = -0.14

START = OPEN_TS - 300
END   = CLOSE_TS + 300

print("Fetching candles...")
c1m = fetch(SYMBOL, "Min1",
    START, END)

print(f"\n{'='*90}")
print(f"  NEAR_USDT LONG —"
      f" 3H_LOWER_HIGH FORENSIC")
print(f"  Entry: {ENTRY}"
      f"  BE_PRICE: {BE_PRICE:.5f}")
print(f"  Open: {fmt_et(OPEN_TS)}"
      f" ET  Close:"
      f" {fmt_et(CLOSE_TS)} ET")
print(f"  Actual exit: {EXIT_PNL}"
      f"  MAE: {MAE_R}R")
print(f"{'='*90}")
print(f"  {'TIME':>10}"
      f"  {'CLOSE':>9}"
      f"  {'PNL':>9}"
      f"  {'AGE':>5}"
      f"  {'BE_ARMED':>8}"
      f"  {'BOUNDARY':>10}"
      f"  {'PRICES[-3:]':>22}"
      f"  {'3H_SIG':>8}"
      f"  NOTE")
print(f"  {'-'*100}")

boundary_prices = []
last_candle_ts = 0
be_armed = False
triggered = None
triggered_pnl = None

for c in c1m:
    if c["t"] < OPEN_TS:
        continue
    if c["t"] > CLOSE_TS + 120:
        break

    age = c["t"] - OPEN_TS
    cpnl = pnl_long(ENTRY, c["c"])

    # be_armed tracking
    if not be_armed and \
            c["c"] <= BE_PRICE:
        be_armed = True

    # 1M boundary
    now_b = (c["t"] // 60) * 60
    sig = "---"
    boundary_str = ""

    if now_b > last_candle_ts:
        boundary_prices.append(
            c["c"])
        if len(boundary_prices) > 3:
            boundary_prices = \
                boundary_prices[-3:]
        last_candle_ts = now_b
        boundary_str = str(
            [round(x,5) for x in
             boundary_prices])

        if (age >= 180
                and cpnl <= 0
                and not be_armed
                and len(
                    boundary_prices)
                    >= 3
                and triggered
                    is None):
            p1 = boundary_prices[-3]
            p2 = boundary_prices[-2]
            p3 = boundary_prices[-1]
            if p3 < p2 < p1:
                triggered = c["t"]
                triggered_pnl = cpnl
                sig = "★ FIRE"
            else:
                sig = "no"
        elif triggered is None:
            sig = "warm"

    note = ""
    if abs(c["t"]-OPEN_TS) < 90:
        note = "ENTRY"
    elif abs(c["t"]-
             CLOSE_TS) < 90:
        note = "★ EXIT"
    elif triggered and \
            c["t"] >= triggered:
        note = "post-fire"

    print(
        f"  {fmt_et(c['t']):>10}"
        f"  {c['c']:9.5f}"
        f"  {cpnl:9.2f}"
        f"  {age:5}s"
        f"  {str(be_armed):>8}"
        f"  {now_b:>10}"
        f"  {boundary_str:>22}"
        f"  {sig:>8}"
        f"  {note}")

print(f"\n{'='*90}")
print(f"  SUMMARY")
print(f"{'='*90}")
if triggered:
    diff = abs(EXIT_PNL) - \
        abs(triggered_pnl)
    print(f"  3H fired at:"
          f" {fmt_et(triggered)} ET")
    print(f"  PnL at fire:"
          f" {triggered_pnl:.2f}")
    print(f"  Actual exit:"
          f" {EXIT_PNL}")
    print(f"  Difference:"
          f" ${diff:.2f}")
else:
    print(f"  3H never fired"
          f" in simulation")
    print(f"  be_armed at close:"
          f" {be_armed}")
    print(f"  Final boundary"
          f" prices: {boundary_prices}")

print("\nDone.")
