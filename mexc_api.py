import os, hmac, hashlib, time, requests

MEXC_API_KEY    = os.environ.get("MEXC_API_KEY", "")
MEXC_SECRET_KEY = os.environ.get("MEXC_SECRET_KEY", "")
BASE_URL        = "https://contract.mexc.com"


def _sign(api_key: str, timestamp: str, params: dict, secret: str) -> str:
    query_string = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    message = api_key + timestamp + query_string
    return hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()


def _headers(timestamp: str, signature: str) -> dict:
    return {
        "ApiKey":       MEXC_API_KEY,
        "Request-Time": timestamp,
        "Signature":    signature,
        "Content-Type": "application/json",
    }


def _safe_json(r: requests.Response, label: str) -> dict:
    if not r.content:
        msg = f"HTTP {r.status_code}: empty response body"
        print(f"[MEXC API] {label} -> {msg}")
        return {"success": False, "message": msg}
    try:
        return r.json()
    except Exception:
        raw = r.text[:300]
        msg = f"HTTP {r.status_code}: non-JSON: {raw!r}"
        print(f"[MEXC API] {label} -> {msg}")
        return {"success": False, "message": msg}


def _get(endpoint: str, params: dict = None) -> dict:
    params = params or {}
    timestamp = str(int(time.time() * 1000))
    signature = _sign(MEXC_API_KEY, timestamp, params, MEXC_SECRET_KEY)
    try:
        r = requests.get(
            BASE_URL + endpoint,
            headers=_headers(timestamp, signature),
            params=params,
            timeout=10,
        )
        return _safe_json(r, f"GET {endpoint}")
    except Exception as e:
        import traceback
        print(f"[MEXC API] _get error on {endpoint}: {e}")
        print(f"[MEXC API] traceback: {traceback.format_exc()}")
        return {}


def get_account() -> dict:
    """Return full account breakdown."""
    print(f"[MEXC API] get_account called -- key={MEXC_API_KEY[:6]}...")
    data = _get("/api/v1/private/account/assets")
    print(f"[MEXC API] get_account response: success={data.get('success')} keys={list(data.keys())[:5]}")
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


def get_open_position_size(symbol: str):
    """Return current open position size on MEXC for `symbol`.
    0.0 = no position. None = API error (skip check)."""
    data = _get("/api/v1/private/position/open_positions")
    if not data.get("success"):
        return None  # API error — skip check
    for pos in data.get("data", []):
        if pos.get("symbol") == symbol:
            return abs(float(pos.get("holdVol", 0)))
    return 0.0  # symbol not found = fully closed

