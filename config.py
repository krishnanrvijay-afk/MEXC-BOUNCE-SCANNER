# regression suite active
import os
from datetime import datetime, timezone

# -- Supabase persistence -------------------------------------------------------
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

# BTC_USDT first — ensures fresh regime/flash data before all other pairs
# ADA_USDT + ZEC_USDT removed: all-session blocks on both venues, persistent losses
PAIRS = ["BTC_USDT","LINK_USDT","SOL_USDT","ETH_USDT","XRP_USDT","DOGE_USDT","SUI_USDT","NEAR_USDT","AVAX_USDT","ARB_USDT","WIF_USDT","HYPE_USDT","LTC_USDT"]

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
J15M_LONG_FLOOR     = -10   # Block LONGs in free-fall (j15m < -10 = still crashing, not bouncing)
J15M_SHORT_CEILING  = 115   # Block SHORTs at extreme overbought (j15m > 115 = squeeze risk)
J1H_SHORT_MIN    = 30   # enforced hard gate: blocks SHORTs where 1H is in deep oversold (< 30 = recovering market)
J1H_SHORT_MAX    = 85   # Real trading ceiling — data: SHORT J1H 90-100 65.5% WR -$1,513
J1H_LONG_MIN     = 0    # Bounds validator — guards negative J1H calculation edge cases. Not a trading gate.
J1H_LONG_MAX     = 59   # No longer used as score gate — may be re-enabled via settings

RSI15M_SHORT_MIN = 35   # enforced hard gate: blocks SHORTs when 15m RSI approaching oversold (< 35)
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

SESSION_FILTER_ENABLED = True
BLOCKED_PAIR_SESSIONS: dict = {
    # HYPE_USDT LONG ASIA:
    # archive 11 trades -$178.02
    # live today 6 kills -$186.49
    # avg MAE -0.330R
    # HYPE_USDT LONG US: +$262.10
    ("HYPE_USDT", "LONG", "ASIA"): True,
    # NEW -- data: AVAX_USDT SHORT ASIA: 0% WR -$75 (3L exits into macro uptrend)
    ("AVAX_USDT", "SHORT", "ASIA"): True,
    # NEW -- data: SUI_USDT SHORT ASIA: 0% WR -$165 (back-to-back 3L exits)
    ("SUI_USDT",  "SHORT", "ASIA"): True,
    # R1 -- ADA_USDT all sessions LONG+SHORT: 6 trades 17% WR -$288.96 MEXC
    # Worst performing pair on MEXC; consistent losses across all sessions and directions
    ("ADA_USDT",  "LONG",  "ASIA"): True,
    ("ADA_USDT",  "LONG",  "EU"):   True,
    ("ADA_USDT",  "LONG",  "US"):   True,
    ("ADA_USDT",  "SHORT", "ASIA"): True,
    ("ADA_USDT",  "SHORT", "EU"):   True,
    ("ADA_USDT",  "SHORT", "US"):   True,
    # R9: ZEC — -$61 combined loss (HL -$29, MEXC -$32), chronically low volume
    # Volume rarely exceeds $500K/24h threshold; block all sessions/directions
    ("ZEC_USDT", "LONG",  "ASIA"): True,
    ("ZEC_USDT", "LONG",  "EU"):   True,
    ("ZEC_USDT", "LONG",  "US"):   True,
    ("ZEC_USDT", "SHORT", "ASIA"): True,
    ("ZEC_USDT", "SHORT", "EU"):   True,
    ("ZEC_USDT", "SHORT", "US"):   True,
}

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
    "ZEC":  0.030,   # matches HL — ZEC ASIA volatility 2-4%; default 1% caused -$211.80 SL 7/12
}
MIN_SL_PCT_DEFAULT = 0.010
# Per-pair per-session Sentinel minimum peak thresholds (as fraction of notional)
# Derived from p25 winner MFE per pair x $10k notional / $10k
# ASIA scaled to 60% -- winner peaks smaller in ASIA session
# Reviewed and updated first Monday of each month
SENTINEL_MIN_PEAK_PCT: dict = {
    ("NEAR_USDT",  "ASIA"): 0.0005,
    ("NEAR_USDT",  "EU"):   0.0005,
    ("NEAR_USDT",  "US"):   0.0005,
    ("WIF_USDT",   "ASIA"): 0.0020,
    ("WIF_USDT",   "EU"):   0.0033,
    ("WIF_USDT",   "US"):   0.0025,
    ("HYPE_USDT",  "ASIA"): 0.0029,
    ("HYPE_USDT",  "EU"):   0.0048,
    ("HYPE_USDT",  "US"):   0.0036,
    ("ETH_USDT",   "ASIA"): 0.0022,
    ("ETH_USDT",   "EU"):   0.0059,
    ("ETH_USDT",   "US"):   0.0044,
    ("DOGE_USDT",  "ASIA"): 0.0018,
    ("DOGE_USDT",  "EU"):   0.0030,
    ("DOGE_USDT",  "US"):   0.0023,
    ("BTC_USDT",   "ASIA"): 0.0022,
    ("BTC_USDT",   "EU"):   0.0066,
    ("BTC_USDT",   "US"):   0.0050,
    ("XRP_USDT",   "ASIA"): 0.0039,
    ("XRP_USDT",   "EU"):   0.0065,
    ("XRP_USDT",   "US"):   0.0049,
    ("LTC_USDT",   "ASIA"): 0.0018,
    ("LTC_USDT",   "EU"):   0.0030,
    ("LTC_USDT",   "US"):   0.0023,
    ("ADA_USDT",   "ASIA"): 0.0018,
    ("ADA_USDT",   "EU"):   0.0030,
    ("ADA_USDT",   "US"):   0.0023,
    ("SOL_USDT",   "ASIA"): 0.0030,
    ("SOL_USDT",   "EU"):   0.0036,
    ("SOL_USDT",   "US"):   0.0040,
    ("AVAX_USDT",  "ASIA"): 0.0017,
    ("AVAX_USDT",  "EU"):   0.0020,
    ("AVAX_USDT",  "US"):   0.0020,
    ("SUI_USDT",   "ASIA"): 0.0017,
    ("SUI_USDT",   "EU"):   0.0025,
    ("SUI_USDT",   "US"):   0.0020,
    ("ZEC_USDT",   "ASIA"): 0.0020,
    ("ZEC_USDT",   "EU"):   0.0033,
    ("ZEC_USDT",   "US"):   0.0025,
}
SENTINEL_MIN_PEAK_PCT_DEFAULT: float = 0.0018

PAIR_COOLDOWN_SECONDS: int = 1800
# Post-KILL cooldown -- blocks re-entry
# on same pair same direction for this
# many seconds after a KILL exit.
# Evidence: every re-entry within 30
# min of a KILL was wrong in 11-trade
# sample June 27.
KILL_GRACE_SECONDS: int = 90
# Grace period before KILL fires.
# Trade must be open >= this many
# seconds AND cpnl <= 0 to trigger.
# Evidence: 5-trade candle analysis
# June 27. 4/5 correct at 90s.
# ETH miss saves ~$44 at 90s.
# 120s creates LTC SL risk.
# Two-tier percentage-based KILL.
# Replaces flat time/cpnl<=0 rule.
# Evidence: 22-trade checkpoint
# analysis June 29 2026. Every
# winner stayed inside 0.54% adverse
# at any checkpoint measured.
# Tier 1: continuous floor, any time.
# Tier 2: tighter check at 5min mark
# -- a trade still bleeding at 5min
# has not earned the same patience
# as a fresh trade.
KILL_PCT_FLOOR: float = 0.006
# 0.6% adverse from entry, checked
# every scan, any time elapsed.
SE_J1H_DECAY_PTS: float = 10.0
# J1H decay threshold for Signal Exhaustion.
# LONG: SE fires when J1H drops 10+ pts below peak.
# SHORT: SE fires when J1H rises 10+ pts above trough.
# Evidence: June 29 39-trade analysis + June 30 HYPE/ADA confirmation.
# 0.4% adverse from entry, checked
# once trade has been open >= 300s.
# Tighter than the floor because
# time without recovery is itself
# a signal.
