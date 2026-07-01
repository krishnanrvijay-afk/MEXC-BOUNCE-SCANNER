import requests, csv
from datetime import datetime, timezone

BASE = "https://contract.mexc.com/api/v1/contract/kline"

def fetch_klines(symbol, interval,
                 start_ts, end_ts):
    r = requests.get(
        f"{BASE}/{symbol}",
        params={"interval": interval,
                "start": start_ts,
                "end": end_ts},
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
    if j < 30: return "BEARISH"
    if j < 70: return "UNDECIDED"
    return "BULLISH"

def fmt(ts):
    return datetime.fromtimestamp(
        ts, tz=timezone.utc
    ).strftime("%H:%M")

def pnl_usd(entry, close, direction,
            margin=5000, lev=5):
    sz = (margin * lev) / entry
    return round(
        (close-entry)*sz if direction=="LONG"
        else (entry-close)*sz, 2)

def analyze(label, symbol, direction,
            entry_ts, close_ts,
            entry_hint=None):
    warmup = 3 * 3600
    print(f"\n{'='*68}")
    print(f"  {label}")
    print(f"  {symbol} {direction}")
    print(f"  Entry: {fmt(entry_ts)} UTC  "
          f"Close: {fmt(close_ts)} UTC  "
          f"Dur: {(close_ts-entry_ts)//60}m")
    print(f"{'='*68}")

    c15 = fetch_klines(symbol, "Min15",
        entry_ts-warmup, close_ts+900)
    c1h = fetch_klines(symbol, "Min60",
        entry_ts-6*3600, close_ts+3600)

    j15 = calc_kdj(c15)
    j1h_all = calc_kdj(c1h)
    hmap = {}
    for i,c in enumerate(c1h):
        hmap[c["t"]] = j1h_all[i]
    def gj1h(t):
        h=(t//3600)*3600
        if h in hmap: return hmap[h]
        for d in [-3600,3600]:
            if h+d in hmap: return hmap[h+d]
        return None

    entry_c = [(c,j15[i])
               for i,c in enumerate(c15)
               if c["t"]>=entry_ts]
    exit_c  = [(c,j15[i])
               for i,c in enumerate(c15)
               if c["t"]<=close_ts]
    if not entry_c: return
    entry_px = entry_hint or entry_c[0][0]["c"]
    exit_px  = exit_c[-1][0]["c"] if exit_c else None

    j15_in  = entry_c[0][1]
    j15_out = exit_c[-1][1] if exit_c else None
    j1h_in  = gj1h(entry_c[0][0]["t"])
    j1h_out = gj1h(exit_c[-1][0]["t"]) if exit_c else None

    j1h_vals = [gj1h(c["t"]) for c,_ in entry_c
                if c["t"]<=close_ts
                and gj1h(c["t"]) is not None]
    j1h_dir = ("RISING" if len(j1h_vals)>=2 and
                j1h_vals[-1]-j1h_vals[0]>10
                else "FALLING" if len(j1h_vals)>=2 and
                j1h_vals[-1]-j1h_vals[0]<-10
                else "FLAT")

    print(f"  Entry px: {entry_px:.5f}  "
          f"Exit px: {exit_px:.5f}")
    print(f"  J15M: {j15_in:.1f}({zone(j15_in)[0]}) → "
          f"{j15_out:.1f}({zone(j15_out)[0]})"
          if j15_out else
          f"  J15M entry: {j15_in:.1f}")
    print(f"  J1H:  {j1h_in:.1f}({zone(j1h_in)[0]}) → "
          f"{j1h_out:.1f}({zone(j1h_out)[0]}) [{j1h_dir}]"
          if j1h_in and j1h_out else "")

    # Signal Exhaustion simulation
    se_ts = None
    se_pnl = None
    se_j15 = None
    arm = False
    prev_z = None

    print(f"\n  {'TIME':>6}  {'PRICE':>8}  "
          f"{'J15M':>7}  {'ZONE':>9}  "
          f"{'J1H':>6}  {'PnL':>9}  NOTE")
    print(f"  {'-'*72}")

    rows = []
    for c,j in entry_c:
        if c["t"] > close_ts: break
        j1h = gj1h(c["t"])
        p = pnl_usd(entry_px, c["c"], direction)
        z = zone(j)

        # SE arming and fire
        if direction=="LONG":
            if j < 50: arm=True
            se_fire=(arm and j>=50 and
                     se_ts is None and p>0)
        else:
            if j > 50: arm=True
            se_fire=(arm and j<=50 and
                     se_ts is None and p>0)

        note=""
        if c["t"]==entry_c[0][0]["t"]:
            note="ENTRY"
        if se_fire:
            se_ts=c["t"]; se_pnl=p; se_j15=j
            note="SE⚡ WOULD FIRE"

        # Zone crossings
        if prev_z and z!=prev_z:
            note=(note+" " if note else "")+(
                f"{prev_z[0]}→{z[0]}")
        prev_z=z

        if c["t"]>=entry_ts:
            print(f"  {fmt(c['t']):>6}  "
                  f"{c['c']:8.5f}  "
                  f"{j:7.1f}  {z:>9}  "
                  f"{j1h or 0:6.1f}  "
                  f"{p:+9.2f}  {note}")
            rows.append({
                "time":fmt(c["t"]),
                "price":c["c"],
                "j15m":j,
                "zone":z,
                "j1h":j1h,
                "pnl":p,
                "note":note
            })

    print(f"\n  J15M at entry: {j15_in:.1f} "
          f"({zone(j15_in)})")
    print(f"  J1H at entry:  "
          f"{j1h_in:.1f} ({zone(j1h_in)})"
          if j1h_in else "")
    if se_ts:
        print(f"  SE would fire: {fmt(se_ts)} "
              f"J15M={se_j15:.1f} "
              f"PnL=+${se_pnl:.2f}")
        final_pnl = pnl_usd(
            entry_px,
            exit_c[-1][0]["c"] if exit_c else entry_px,
            direction)
        print(f"  Actual exit:   {fmt(close_ts)} "
              f"PnL=${final_pnl:.2f}")
        print(f"  SE vs actual:  "
              f"${se_pnl-final_pnl:+.2f} delta")
    else:
        print("  SE never fired "
              "(never in profit past 50)")
    return rows

# ── TRADE DEFINITIONS ─────────────────
# All timestamps in UTC seconds

# Case 1: HYPE_USDT LONG US
# Close 6/30 07:17 PM EDT = 23:17 UTC
# Duration 23193s → entry ~16:51 UTC
HYPE_CLOSE = int(datetime(
    2026,6,30,23,17,0,
    tzinfo=timezone.utc).timestamp())
HYPE_ENTRY = HYPE_CLOSE - 23193

# Case 2: ADA_USDT SHORT US (MEXC)
# Close 6/30 07:04 PM EDT = 23:04 UTC
# Duration 29954s → entry ~14:45 UTC
ADA_CLOSE = int(datetime(
    2026,6,30,23,4,0,
    tzinfo=timezone.utc).timestamp())
ADA_ENTRY = ADA_CLOSE - 29954

# Case 3: WIF_USDT three KILL exits
# All 6/30 8:20 PM / 8:58 PM / 9:05 PM
# EDT = 7/1 00:20 / 00:58 / 01:05 UTC
WIF1_CLOSE = int(datetime(
    2026,7,1,0,20,0,
    tzinfo=timezone.utc).timestamp())
WIF1_ENTRY = WIF1_CLOSE - 355

WIF2_CLOSE = int(datetime(
    2026,7,1,0,58,0,
    tzinfo=timezone.utc).timestamp())
WIF2_ENTRY = WIF2_CLOSE - 371

WIF3_CLOSE = int(datetime(
    2026,7,1,1,5,0,
    tzinfo=timezone.utc).timestamp())
WIF3_ENTRY = WIF3_CLOSE - 467

print("Fetching candles for 5 trades...")

r1 = analyze(
    "CASE 1 — HYPE_USDT LONG US "
    "(PEAK_DECAY_20 at 0.24R, MFE 1.92R)",
    "HYPE_USDT", "LONG",
    HYPE_ENTRY, HYPE_CLOSE)

r2 = analyze(
    "CASE 2 — ADA_USDT SHORT US "
    "(MFE 1.17R → reversed to KILL -$116)",
    "ADA_USDT", "SHORT",
    ADA_ENTRY, ADA_CLOSE)

r3 = analyze(
    "CASE 3a — WIF_USDT LONG ASIA KILL 1 "
    "(355s, -$105)",
    "WIF_USDT", "LONG",
    WIF1_ENTRY, WIF1_CLOSE)

r4 = analyze(
    "CASE 3b — WIF_USDT LONG ASIA KILL 2 "
    "(371s, -$105)",
    "WIF_USDT", "LONG",
    WIF2_ENTRY, WIF2_CLOSE)

r5 = analyze(
    "CASE 3c — WIF_USDT LONG ASIA KILL 3 "
    "(467s, -$108)",
    "WIF_USDT", "LONG",
    WIF3_ENTRY, WIF3_CLOSE)

print("\nDone.")
