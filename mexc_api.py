import os, hmac, hashlib, time, requests

MEXC_API_KEY    = os.environ.get("MEXC_API_KEY", "")
MEXC_SECRET_KEY = os.environ.get("MEXC_SECRET_KEY", "")
BASE_URL        = "https://contract.mexc.com"


def _sign(params: dict) -> str:
    sorted_params = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    return hmac.new(MEXC_SECRET_KEY.encode(), sorted_params.encode(), hashlib.sha256).hexdigest()


def _get(path: str, params: dict = None) -> dict:
    params = params or {}
    params["timestamp"] = int(time.time() * 1000)
    params["ApiKey"]    = MEXC_API_KEY
    params["sign"]      = _sign(params)
    try:
        r = requests.get(BASE_URL + path, params=params, timeout=8)
        return r.json()
    except Exception as e:
        print(f"[MEXC API] error: {e}")
        return {}


def get_account() -> dict:
    """Return full account breakdown — equity, available, margin, unrealized PNL."""
    data = _get("/api/v1/private/account/assets")
    if not data.get("success"):
        return {}
    usdt = next((a for a in data.get("data", []) if a.get("currency") == "USDT"), {})
    return {
        "equity":         float(usdt.get("equity",           0)),
        "available":      float(usdt.get("availableBalance", 0)),
        "margin_used":    float(usdt.get("frozenBalance",    0)),
        "unrealized_pnl": float(usdt.get("unrealizedProfit", 0)),
    }


def get_position_count() -> int:
    """Return count of open positions."""
    data = _get("/api/v1/private/position/open_positions")
    if not data.get("success"):
        return 0
    return len(data.get("data", []))
