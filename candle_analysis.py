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
          "v": float(raw["vol"][i])
            if "vol" in raw else 0.0,
        })
    return sorted(
        out, key=lambda x: x["t"])

def fmt_et(ts):
    return datetime.fromtimestamp(
        ts - 14400,
        tz=timezone.utc
    ).strftime("%H:%M:%S")

def pnl_short(entry, price,
        margin=5000, lev=5):
    sz = (margin * lev) / entry
    return round(
        (entry - price) * sz, 2)

def r_val_short(entry, price,
        sl, margin=5000, lev=5):
    sz = (margin * lev) / entry
    risk = abs(sl - entry) * sz
    if risk == 0:
        return 0
    return round(
        (entry - price) * sz
        / risk, 3)

def ts(iso):
    return int(
        datetime.fromisoformat(
            iso.replace('+00','')
        ).replace(
            tzinfo=timezone.utc
        ).timestamp())

def simulate_3l(candles, entry,
        sl, open_ts, close_ts,
        boundary_secs, label):
    prices = []
    last_ts = 0
    triggered = None
    triggered_pnl = None
    triggered_r = None

    for c in candles:
        if c["t"] < open_ts:
            continue
        if c["t"] > close_ts + 60:
            break

        age = c["t"] - open_ts
        cpnl = pnl_short(
            entry, c["c"])
        cr = r_val_short(
            entry, c["c"], sl)

        now_b = (c["t"]
            // boundary_secs
            ) * boundary_secs

        if now_b > last_ts:
            prices.append(c["c"])
            if len(prices) > 3:
                prices = prices[-3:]
            last_ts = now_b

            if (age >= 180
                    and cpnl <= 0
                    and len(prices)
                        >= 3
                    and triggered
                        is None):
                p1 = prices[-3]
                p2 = prices[-2]
                p3 = prices[-1]
                if p3 > p2 > p1:
                    triggered = \
                        c["t"]
                    triggered_pnl =\
                        cpnl
                    triggered_r = cr

    return triggered, \
        triggered_pnl, \
        triggered_r

# ARB_USDT SHORT KILL
SYMBOL   = "ARB_USDT"
ENTRY    = 0.0763
SL       = 0.077445
OPEN_TS  = ts(
    "2026-07-08 05:00:07+00")
CLOSE_TS = ts(
    "2026-07-08 05:04:45+00")
EXIT_PNL = -157.27
EXIT_R   = -0.42

START = OPEN_TS - 600
END   = CLOSE_TS + 600

print("Fetching Min1 candles...")
c1m = fetch(SYMBOL, "Min1",
    START, END)

print(f"\n{'='*80}")
print(f"  ARB_USDT SHORT KILL"
      f" FORENSIC")
print(f"  Entry: {ENTRY}"
      f"  SL: {SL}")
print(f"  Open: {fmt_et(OPEN_TS)}"
      f" ET  Close:"
      f" {fmt_et(CLOSE_TS)} ET")
print(f"  Actual KILL:"
      f" {EXIT_PNL}"
      f" ({EXIT_R}R)"
      f" at {fmt_et(CLOSE_TS)} ET")
print(f"  Duration: {278}s")
print(f"{'='*80}")

print(f"\n  {'TIME':>10}"
      f"  {'CLOSE':>9}"
      f"  {'PNL':>9}"
      f"  {'R':>6}"
      f"  {'AGE':>5}"
      f"  {'BOUND_1M':>10}"
      f"  {'BOUND_5M':>10}"
      f"  NOTE")
print(f"  {'-'*80}")

bound_1m_prices = []
bound_5m_prices = []
last_1m = 0
last_5m = 0

for c in c1m:
    if c["t"] < OPEN_TS:
        continue
    if c["t"] > CLOSE_TS + 60:
        break

    age = c["t"] - OPEN_TS
    cpnl = pnl_short(ENTRY, c["c"])
    cr = r_val_short(
        ENTRY, c["c"], SL)

    b1m = (c["t"]//60)*60
    b5m = (c["t"]//300)*300

    note_1m = ""
    note_5m = ""

    if b1m > last_1m:
        bound_1m_prices.append(
            c["c"])
        if len(bound_1m_prices) > 3:
            bound_1m_prices = \
                bound_1m_prices[-3:]
        last_1m = b1m
        if (age >= 180
                and cpnl <= 0
                and len(
                    bound_1m_prices)
                    >= 3):
            p1 = bound_1m_prices[-3]
            p2 = bound_1m_prices[-2]
            p3 = bound_1m_prices[-1]
            if p3 > p2 > p1:
                note_1m = \
                    "★3L_1M_FIRE"

    if b5m > last_5m:
        bound_5m_prices.append(
            c["c"])
        if len(bound_5m_prices) > 3:
            bound_5m_prices = \
                bound_5m_prices[-3:]
        last_5m = b5m
        if (age >= 180
                and cpnl <= 0
                and len(
                    bound_5m_prices)
                    >= 3):
            p1 = bound_5m_prices[-3]
            p2 = bound_5m_prices[-2]
            p3 = bound_5m_prices[-1]
            if p3 > p2 > p1:
                note_5m = \
                    "★3L_5M_FIRE"

    note = ""
    if abs(c["t"]-OPEN_TS) < 90:
        note = "ENTRY"
    elif abs(c["t"]-CLOSE_TS) < 90:
        note = "★ KILL"

    bp1m = (
        f"{bound_1m_prices[-1]:.5f}"
        if bound_1m_prices else "---")
    bp5m = (
        f"{bound_5m_prices[-1]:.5f}"
        if bound_5m_prices else "---")

    print(
        f"  {fmt_et(c['t']):>10}"
        f"  {c['c']:9.5f}"
        f"  {cpnl:9.2f}"
        f"  {cr:6.3f}"
        f"  {age:5}s"
        f"  {bp1m:>10}"
        f"  {bp5m:>10}"
        f"  {note}"
        f" {note_1m} {note_5m}")

# run simulations
t1m, pnl1m, r1m = simulate_3l(
    c1m, ENTRY, SL,
    OPEN_TS, CLOSE_TS, 60,
    "1M")
t5m, pnl5m, r5m = simulate_3l(
    c1m, ENTRY, SL,
    OPEN_TS, CLOSE_TS, 300,
    "5M")

print(f"\n{'='*80}")
print(f"  SIMULATION SUMMARY")
print(f"{'='*80}")
print(f"  Actual KILL:"
      f" {EXIT_PNL:.2f}"
      f" ({EXIT_R}R)"
      f" at {fmt_et(CLOSE_TS)} ET")

if t1m:
    saved = abs(EXIT_PNL) - \
        abs(pnl1m)
    print(f"\n  3L_HIGHER_LOW"
          f" on 1M boundary:")
    print(f"  Would fire at:"
          f" {fmt_et(t1m)} ET")
    print(f"  PnL: {pnl1m:.2f}"
          f" ({r1m:.3f}R)")
    print(f"  Capital saved"
          f" vs KILL:"
          f" ${saved:.2f}")
    print(f"  Time earlier:"
          f" {(CLOSE_TS-t1m)//60}"
          f" min"
          f" {(CLOSE_TS-t1m)%60}s")
else:
    print(f"\n  3L on 1M:"
          f" did NOT trigger"
          f" during trade")

if t5m:
    saved = abs(EXIT_PNL) - \
        abs(pnl5m)
    print(f"\n  3L_HIGHER_LOW"
          f" on 5M boundary:")
    print(f"  Would fire at:"
          f" {fmt_et(t5m)} ET")
    print(f"  PnL: {pnl5m:.2f}"
          f" ({r5m:.3f}R)")
    print(f"  Capital saved"
          f" vs KILL:"
          f" ${saved:.2f}")
else:
    print(f"\n  3L on 5M:"
          f" did NOT trigger"
          f" during trade"
          f" (only"
          f" {278//300} 5M"
          f" boundary in"
          f" 278s trade)")

print("\nDone.")
