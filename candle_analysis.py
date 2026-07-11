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
            "start":    start,
            "end":      end},
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
            "c": float(raw["close"][i]),
        })
    return sorted(out, key=lambda x: x["t"])

def fmt_et(ts):
    return datetime.fromtimestamp(
        ts - 14400,
        tz=timezone.utc
    ).strftime("%H:%M:%S")

def ts(iso):
    return int(
        datetime.fromisoformat(
            iso.replace("+00", "")
        ).replace(
            tzinfo=timezone.utc
        ).timestamp())

# ── Trade parameters ──────────────────────────────────────
SYMBOL    = "LINK_USDT"
DIRECTION = "SHORT"
ENTRY     = 8.081
OPEN_TS   = ts("2026-07-11 15:31:18+00")
CLOSE_TS  = ts("2026-07-11 15:42:32+00")
MARGIN    = 5000
LEV       = 5
SIZE      = (MARGIN * LEV) / ENTRY          # contracts

# ── Sentinel-reported peak & decay levels ─────────────────
SENTINEL_PEAK_USD  = 176.34
DECAY_THRESHOLD    = SENTINEL_PEAK_USD * 0.80   # $141.07

# Implied price levels from sentinel peak
PEAK_PRICE   = ENTRY - (SENTINEL_PEAK_USD / SIZE)
DECAY_PRICE  = PEAK_PRICE + (SENTINEL_PEAK_USD * 0.20 / SIZE)

print("=" * 75)
print(f"  {SYMBOL} {DIRECTION}  entry={ENTRY}  "
      f"size={SIZE:.2f} contracts")
print(f"  open={fmt_et(OPEN_TS)}  close={fmt_et(CLOSE_TS)}")
print(f"  Sentinel peak reported: ${SENTINEL_PEAK_USD:.2f}")
print(f"  Decay threshold (80%):  ${DECAY_THRESHOLD:.2f}")
print(f"  Implied peak price:     {PEAK_PRICE:.5f}")
print(f"  Decay trigger price:    {DECAY_PRICE:.5f}  "
      f"(SHORT decays when close > this)")
print("=" * 75)

candles = fetch(SYMBOL, "Min1",
                OPEN_TS - 120, CLOSE_TS + 120)

# ── Shadow tracker — mirrors main.py _peak_shadow logic ───
# peak_pnl_usd updated only when be_armed and new candle and new high.
# be_armed fires when close price crosses be_price.
# For simplicity here: assume be_armed=True from open (paper mode).
peak_pnl    = 0.0
peak_at     = None
peak_price  = None
decay_fired = False
decay_ts    = None
decay_pnl   = None

print(f"\n  {'TIME':>10}  {'CLOSE':>10}  {'PNL':>10}  "
      f"{'PEAK':>10}  {'DECAY%':>8}  "
      f"{'CROSS?':>7}  ACTION")
print(f"  {'-'*72}")

for c in candles:
    if c["t"] < OPEN_TS - 60:
        continue
    if c["t"] > CLOSE_TS + 120:
        break

    cpnl = round((ENTRY - c["c"]) * SIZE, 2)

    # Update peak (mirrors be_armed + new-candle gate)
    if cpnl > peak_pnl:
        peak_pnl   = cpnl
        peak_at    = c["t"]
        peak_price = c["c"]

    decay_pct = 0.0
    if peak_pnl > 0:
        decay_pct = round((1 - cpnl / peak_pnl) * 100, 1)

    # Decay breach check (mirrors PEAK_DECAY_20 condition)
    decay_now = (
        peak_pnl > 0
        and cpnl < peak_pnl * 0.80
        and not decay_fired
    )
    if decay_now:
        decay_fired = True
        decay_ts    = c["t"]
        decay_pnl   = cpnl

    # Did close cross above decay trigger price?
    cross = "YES" if c["c"] > DECAY_PRICE else "   "

    # Determine note / action
    if abs(c["t"] - OPEN_TS) < 90:
        action = "ENTRY candle"
    elif abs(c["t"] - CLOSE_TS) < 90:
        action = "EXIT candle (actual close)"
    elif c["t"] == peak_at and not decay_now:
        action = "PEAK"
    else:
        action = ""

    if decay_now:
        action = "★ DECAY BREACHED — scanner queues PEAK_DECAY_20 exit"
    elif decay_fired and cpnl < DECAY_THRESHOLD:
        action = "  (decay already fired)"

    print(
        f"  {fmt_et(c['t']):>10}"
        f"  {c['c']:10.4f}"
        f"  {cpnl:10.2f}"
        f"  {peak_pnl:10.2f}"
        f"  {decay_pct:7.1f}%"
        f"  {cross:>7}"
        f"  {action}")

print(f"\n  {'─'*72}")
print(f"\n  SUMMARY:")
print(f"  Entry price:              {ENTRY}")
print(f"  Size:                     {SIZE:.4f} contracts")
print(f"  Sentinel peak (reported): ${SENTINEL_PEAK_USD:.2f}")
print(f"  Decay threshold (80%):    ${DECAY_THRESHOLD:.2f}")
print(f"  Implied peak price:       {PEAK_PRICE:.5f}")
print(f"  20% decay trigger price:  {DECAY_PRICE:.5f}")

if peak_at:
    print(f"\n  Tracked peak in replay:   ${peak_pnl:.2f}"
          f"  at {fmt_et(peak_at)}"
          f"  price={peak_price:.4f}")

if decay_ts:
    print(f"  Decay breached at:        {fmt_et(decay_ts)}"
          f"  PnL=${decay_pnl:.2f}")
    if peak_at:
        gap = (decay_ts - peak_at) // 60
        print(f"  Gap peak → decay fire:    {gap} minutes")
else:
    print(f"  20% decay never breached in window")

print("\nDone.")
