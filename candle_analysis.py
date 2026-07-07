import requests, time
from datetime import datetime, timezone

BASE = (
    "https://contract.mexc.com"
    "/api/v1/contract/kline")

def fetch(symbol, interval, start, end):
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
    for i in range(len(raw["time"])):
        out.append({
            "t": int(raw["time"][i]),
            "o": float(raw["open"][i]),
            "h": float(raw["high"][i]),
            "l": float(raw["low"][i]),
            "c": float(raw["close"][i]),
            "v": float(raw["vol"][i])
                if "vol" in raw else 0.0,
        })
    return sorted(out, key=lambda x: x["t"])

def fmt_et(ts):
    return datetime.fromtimestamp(
        ts - 14400,
        tz=timezone.utc
    ).strftime("%H:%M:%S")

def pnl_long(entry, price, margin=5000, lev=5):
    sz = (margin * lev) / entry
    return round((price - entry) * sz, 2)

def r_val(entry, price, sl, margin=5000, lev=5):
    sz = (margin * lev) / entry
    risk = abs(entry - sl) * sz
    if risk == 0:
        return 0
    return round((price - entry) * sz / risk, 3)

def ts(iso):
    return int(
        datetime.fromisoformat(
            iso.replace('+00', '')
        ).replace(
            tzinfo=timezone.utc
        ).timestamp())

# DOGE_USDT LONG KILL
SYMBOL   = "DOGE_USDT"
ENTRY    = 0.07681
SL       = 0.076072
TP1      = 0.077608
OPEN_TS  = ts("2026-07-06 23:31:13+00")
CLOSE_TS = ts("2026-07-07 00:08:59+00")
EXIT_PX  = 0.0765
EXIT_PNL = -100.9
MAE_R    = -0.42
MFE_R    = 0.05

START = OPEN_TS - 1800
END   = CLOSE_TS + 900

print("Fetching candles...")
candles = fetch(SYMBOL, "Min1", START, END)

print(f"\n{'='*90}")
print(f"  DOGE_USDT LONG KILL FORENSIC")
print(f"  Entry: {ENTRY}  SL: {SL}  TP1: {TP1}")
print(f"  Open: {fmt_et(OPEN_TS)} ET  Close: {fmt_et(CLOSE_TS)} ET")
print(f"  Actual exit: {EXIT_PX}  PnL: {EXIT_PNL}  MAE: {MAE_R}R  MFE: {MFE_R}R")
print(f"  Duration: {2266}s (37m 46s)")
print(f"{'='*90}")
print(f"  {'TIME':>10}"
      f"  {'HIGH':>9}"
      f"  {'LOW':>9}"
      f"  {'CLOSE':>9}"
      f"  {'PNL':>9}"
      f"  {'R':>6}"
      f"  {'AGE':>5}"
      f"  {'BOUNDARY_H':>12}"
      f"  {'3H_SIGNAL':>10}"
      f"  NOTE")
print(f"  {'-'*105}")

# simulate 3H_LOWER_HIGH using candle close as boundary price proxy
boundary_prices = []
last_candle_ts = 0
triggered_3h = None
triggered_3h_pnl = None
triggered_3h_r = None

for c in candles:
    if c["t"] < OPEN_TS:
        continue
    if c["t"] > CLOSE_TS + 600:
        break

    age = c["t"] - OPEN_TS
    cpnl = pnl_long(ENTRY, c["c"])
    cr = r_val(ENTRY, c["c"], SL)

    now_candle = (c["t"] // 60) * 60
    boundary_signal = "---"

    if now_candle > last_candle_ts:
        boundary_prices.append(c["c"])
        if len(boundary_prices) > 3:
            boundary_prices = boundary_prices[-3:]
        last_candle_ts = now_candle

        if (age >= 180
                and cpnl <= 0
                and len(boundary_prices) >= 3
                and triggered_3h is None):
            b1 = boundary_prices[-3]
            b2 = boundary_prices[-2]
            b3 = boundary_prices[-1]
            if b3 < b2 < b1:
                triggered_3h = c["t"]
                triggered_3h_pnl = cpnl
                triggered_3h_r = cr
                boundary_signal = "★ FIRE"
            else:
                boundary_signal = "no"
        elif triggered_3h is None:
            boundary_signal = "warming"

    note = ""
    if c["t"] == OPEN_TS:
        note = "ENTRY"
    elif abs(c["t"] - CLOSE_TS) < 90:
        note = "★ KILL EXIT"
    elif c["t"] > CLOSE_TS:
        note = "post-exit"
    elif triggered_3h and c["t"] >= triggered_3h:
        note = "3H would have exited"

    bp_str = (
        f"{boundary_prices[-1]:.5f}"
        if boundary_prices else "---")

    print(
        f"  {fmt_et(c['t']):>10}"
        f"  {c['h']:9.5f}"
        f"  {c['l']:9.5f}"
        f"  {c['c']:9.5f}"
        f"  {cpnl:9.2f}"
        f"  {cr:6.3f}"
        f"  {age:5}s"
        f"  {bp_str:>12}"
        f"  {boundary_signal:>10}"
        f"  {note}")

print(f"\n{'='*90}")
print(f"  SIMULATION SUMMARY")
print(f"{'='*90}")
print(f"  Actual KILL exit: {EXIT_PX}  PnL: {EXIT_PNL}  at {fmt_et(CLOSE_TS)} ET")

if triggered_3h:
    saving = abs(EXIT_PNL) - abs(triggered_3h_pnl)
    print(f"  3H_LOWER_HIGH would have fired at: {fmt_et(triggered_3h)} ET")
    print(f"  PnL at 3H exit: {triggered_3h_pnl:.2f}")
    print(f"  R at 3H exit: {triggered_3h_r:.3f}R")
    print(f"  Capital saved vs KILL: ${saving:.2f}")
    print(f"  Time saved: {(CLOSE_TS-triggered_3h)//60} minutes earlier")
else:
    print(f"  3H_LOWER_HIGH did NOT trigger during this trade")

print("\nDone.")
