import requests
from datetime import datetime, timezone
import sys
sys.path.insert(0, '.')
from scanner import _compute_kdj

BASE = "https://contract.mexc.com/api/v1/contract/kline"

PAIRS = [
    "LINK_USDT", "SOL_USDT", "BTC_USDT", "ETH_USDT",
    "XRP_USDT", "DOGE_USDT", "SUI_USDT", "NEAR_USDT",
    "AVAX_USDT", "ARB_USDT", "WIF_USDT", "HYPE_USDT",
    "LTC_USDT", "ADA_USDT", "ZEC_USDT"
]

import time

def fetch_mexc(symbol, interval, limit=100):
    end = int(time.time())
    interval_s = {
        "Min5": 300, "Min15": 900, "Min60": 3600
    }
    start = end - interval_s[interval] * (limit + 5)
    try:
        r = requests.get(
            f"{BASE}/{symbol}",
            params={
                "interval": interval,
                "start": start,
                "end": end
            },
            timeout=15
        )
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
                "close": float(raw["close"][i]),
                "high": float(raw["high"][i]),
                "low": float(raw["low"][i])
            })
        return sorted(out, key=lambda x: x["t"])
    except Exception as e:
        print(f"  ERROR fetching {symbol} {interval}: {e}")
        return []

def main():
    print(f"{'PAIR':>12} {'TF':>5} {'COUNT':>7} "
          f"{'J':>8} {'FLAG':>25}")
    print("-" * 62)

    for pair in PAIRS:
        for interval, label in [
            ("Min5",  "5M"),
            ("Min15", "15M"),
            ("Min60", "1H")
        ]:
            candles = fetch_mexc(pair, interval)
            count = len(candles)
            _, _, j = _compute_kdj(candles)
            j_val = round(j, 2)

            flag = ""
            if count == 0:
                flag = "*** NO CANDLES ***"
            elif count < 20:
                flag = f"*** LOW COUNT {count} ***"
            elif abs(j_val - 50.0) < 1.0:
                flag = "*** J=50 SEED STUCK ***"
            elif j_val < 0 or j_val > 110:
                flag = "*** J OUT OF RANGE ***"

            print(f"{pair:>12} {label:>5} "
                  f"{count:>7} {j_val:>8} "
                  f"{flag}")

    print("\nDone.")

main()
