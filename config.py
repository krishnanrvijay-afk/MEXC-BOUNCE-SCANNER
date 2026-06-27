import os
from datetime import datetime, timezone

# -- Supabase persistence -------------------------------------------------------
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

PAIRS = ["LINK_USDT","SOL_USDT","BTC_USDT","ETH_USDT","XRP_USDT","DOGE_USDT","SUI_USDT","NEAR_USDT","AVAX_USDT","ARB_USDT","WIF_USDT","HYPE_USDT","LTC_USDT","ADA_USDT"]

SCAN_INTERVAL_SECONDS  = 30
PRICE_INTERVAL_SECONDS = 8
PAPER_MODE             = True

# -- Live trading safety --------------------------------------------------------
# When PAPER_MODE is False and LIVE_MANUAL_ENTRY_ONLY is True, the scanner will
# never automatically open a live exchange position. Alerts fire and the overlay
# updates normally but all live trade entry requires deliberate human action via
# the symbol overlay Open MEXC buttons. SL and TP exits continue to
# execute automatically once a trade is open. This is the required mode for live
# trading. Only set LIVE_MANUAL_ENTRY_ONLY to False if you explicitly want fully
# automated live entry on every signal.
LIVE_MANUAL_ENTRY_ONLY = True

J15M_SHORT_GATE  = 80
J15M_LONG_GATE   = 20
J1H_SHORT_MIN    = 60
J1H_SHORT_MAX    = 89   # Real trading ceiling — data: SHORT J1H 90-100 65.5% WR -$1,513
J1H_LONG_MIN     = 0    # Bounds validator — guards negative J1H calculation edge cases. Not a trading gate.
J1H_LONG_MAX     = 59   # No longer used as score gate — may be re-enabled via settings

RSI15M_SHORT_MIN = 60
RSI15M_LONG_MAX  = 40

DEPTH_GATE_PCT   = 55

ATR_SL_MULTIPLIER = 1.0

TP1_R                = 1.0
TP1_CLOSE_PCT        = 0.70        # Trailblazer: close 70% at TP1 (runner 30% stays open)
TP2_R                = 1.2         # p75 MFE = 1.1-1.2R. 25% of winners reach 1.2R vs 10% reaching 1.5R.
TRAIL_ATR_MULTIPLIER = 0.5         # trail_stop = trail_best  (atr15m  TRAIL_ATR_MULTIPLIER)

LEVERAGE_HIGH = 10
LEVERAGE_MID  = 5
LEVERAGE_LOW  = 5

CONSECUTIVE_LOSS_STOP = 3
DAILY_LOSS_LIMIT      = -800.0

MARGIN_PER_TRADE = 2000.0
MARGIN_HARD_CAP  = 25000.0

ADX_MIN_LONG  = 20  # data: LONG ADX 0-19: 119 trades -$2,391
ADX_MIN_SHORT = 0   # data: SHORT ADX 0-14: 21 trades +$493. SHORTs profitable at all ADX levels

SESSION_FILTER_ENABLED = False
PLACE_EXCHANGE_SL      = True

MIN_SL_PCT: dict = {
    "BTC":  0.008,
    "ETH":  0.006,
    "SOL":  0.008,
    "XRP":  0.007,
    "DOGE": 0.007,
    "SUI":  0.010,
    "NEAR": 0.010,
    "LINK": 0.008,
    "ARB":  0.012,
}
MIN_SL_PCT_DEFAULT = 0.010
# Per-pair per-session Sentinel minimum peak thresholds
# Derived from p25 winner MFE per pair x $10k notional
# ASIA scaled to 60% -- winner peaks smaller in ASIA session
# Reviewed and updated first Monday of each month
SENTINEL_MIN_PEAK_USD: dict = {
    ("NEAR_USDT",  "ASIA"): 5.00,  ("NEAR_USDT",  "EU"): 5.00,  ("NEAR_USDT",  "US"): 5.00,
    ("WIF_USDT",   "ASIA"): 20.00, ("WIF_USDT",   "EU"): 33.00, ("WIF_USDT",   "US"): 25.00,
    ("HYPE_USDT",  "ASIA"): 29.00, ("HYPE_USDT",  "EU"): 48.00, ("HYPE_USDT",  "US"): 36.00,
    ("ETH_USDT",   "ASIA"): 22.00, ("ETH_USDT",   "EU"): 59.00, ("ETH_USDT",   "US"): 44.00,
    ("DOGE_USDT",  "ASIA"): 18.00, ("DOGE_USDT",  "EU"): 30.00, ("DOGE_USDT",  "US"): 23.00,
    ("BTC_USDT",   "ASIA"): 22.00, ("BTC_USDT",   "EU"): 66.00, ("BTC_USDT",   "US"): 50.00,
    ("XRP_USDT",   "ASIA"): 39.00, ("XRP_USDT",   "EU"): 65.00, ("XRP_USDT",   "US"): 49.00,
    ("LTC_USDT",   "ASIA"): 18.00, ("LTC_USDT",   "EU"): 30.00, ("LTC_USDT",   "US"): 23.00,
    ("ADA_USDT",   "ASIA"): 18.00, ("ADA_USDT",   "EU"): 30.00, ("ADA_USDT",   "US"): 23.00,
    ("SOL_USDT",   "ASIA"): 30.00, ("SOL_USDT",   "EU"): 36.00, ("SOL_USDT",   "US"): 40.00,
    ("AVAX_USDT",  "ASIA"): 17.00, ("AVAX_USDT",  "EU"): 20.00, ("AVAX_USDT",  "US"): 20.00,
    ("SUI_USDT",   "ASIA"): 17.00, ("SUI_USDT",   "EU"): 25.00, ("SUI_USDT",   "US"): 20.00,
}
SENTINEL_MIN_PEAK_USD_DEFAULT: float = 18.00  # ASIA-safe default
