"""MEXC Futures client — async, paper and live modes.

Signature method (proven from staging):
  GET:  HMAC-SHA256(secret, apiKey + timestamp + sorted(queryString))
  POST: HMAC-SHA256(secret, apiKey + timestamp + rawBodyString)
"""

import asyncio
import hashlib
import hmac
import json as _json
import os
import time
from typing import Optional

import httpx

from config import PAPER_MODE

MEXC_API_BASE = "https://contract.mexc.com"

# Map scanner interval strings → MEXC futures interval names
_INTERVAL_MAP = {
    "1m":  "Min1",
    "3m":  "Min3",
    "5m":  "Min5",
    "15m": "Min15",
    "30m": "Min30",
    "1h":  "Min60",
    "4h":  "Hour4",
    "8h":  "Hour8",
    "1d":  "Day1",
}

# Seconds per bar for each MEXC interval (used to compute start timestamp)
_INTERVAL_SECONDS = {
    "Min1": 60, "Min3": 180, "Min5": 300, "Min15": 900,
    "Min30": 1800, "Min60": 3600, "Hour4": 14400,
    "Hour8": 28800, "Day1": 86400,
}


class MexcClient:
    def __init__(self):
        self._http        = httpx.AsyncClient(timeout=15.0)
        self._paper_mode  = PAPER_MODE
        self._api_key     = os.getenv("MEXC_API_KEY",    "")
        self._secret_key  = os.getenv("MEXC_SECRET_KEY", "")

    # ── Signature helpers ─────────────────────────────────────────────────────

    def _sign_get(self, params: dict, timestamp: str) -> str:
        """GET signature: HMAC-SHA256(secret, apiKey + timestamp + sortedQueryString)"""
        qs  = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        msg = self._api_key + timestamp + qs
        return hmac.new(
            self._secret_key.encode("utf-8"),
            msg.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _sign_post(self, body_str: str, timestamp: str) -> str:
        """POST signature: HMAC-SHA256(secret, apiKey + timestamp + rawBodyString)"""
        msg = self._api_key + timestamp + body_str
        return hmac.new(
            self._secret_key.encode("utf-8"),
            msg.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _auth_headers(self, timestamp: str, signature: str) -> dict:
        return {
            "ApiKey":       self._api_key,
            "Request-Time": timestamp,
            "Signature":    signature,
            "Content-Type": "application/json",
        }

    # ── Public market data ────────────────────────────────────────────────────

    async def get_price(self, symbol: str) -> Optional[float]:
        """Return latest traded price for symbol (e.g. 'ZEC_USDT')."""
        try:
            resp = await self._http.get(
                f"{MEXC_API_BASE}/api/v1/contract/ticker",
                params={"symbol": symbol},
            )
            resp.raise_for_status()
            data = resp.json()
            px = data.get("data", {}).get("lastPrice")
            return float(px) if px else None
        except Exception as e:
            print(f"[MexcClient] get_price({symbol}) error: {e}")
            return None

    async def get_candles(
        self, symbol: str, interval: str, limit: int = 100
    ) -> list[dict]:
        """
        Return the last `limit` OHLCV candles as a list of dicts.
        Keys: timestamp, open, high, low, close, volume
        interval examples: '5m', '15m', '1h'
        """
        mexc_interval = _INTERVAL_MAP.get(interval, "Min15")
        secs_per_bar  = _INTERVAL_SECONDS.get(mexc_interval, 900)
        start_ts      = int(time.time()) - limit * secs_per_bar
        try:
            resp = await self._http.get(
                f"{MEXC_API_BASE}/api/v1/contract/kline/{symbol}",
                params={"interval": mexc_interval, "start": start_ts},
            )
            resp.raise_for_status()
            data = resp.json()
            d      = data.get("data") or {}
            times  = d.get("time",  [])
            opens  = d.get("open",  [])
            highs  = d.get("high",  [])
            lows   = d.get("low",   [])
            closes = d.get("close", [])
            vols   = d.get("vol",   [])
            n = min(len(times), len(closes), len(highs), len(lows), len(vols))
            candles = [
                {
                    "timestamp": int(times[i]),
                    "open":      float(opens[i])  if i < len(opens)  else 0.0,
                    "high":      float(highs[i]),
                    "low":       float(lows[i]),
                    "close":     float(closes[i]),
                    "volume":    float(vols[i]),
                }
                for i in range(n)
            ]
            return candles[-limit:]   # trim to requested limit
        except Exception as e:
            print(f"[MexcClient] get_candles({symbol}, {interval}) error: {e}")
            return []

    async def get_orderbook(self, symbol: str, depth: int = 20) -> dict:
        """
        Return orderbook with 'bids' and 'asks' lists.
        Each entry: {'px': float, 'sz': float}
        Compatible with scanner._depth_pcts() which reads b['sz'].
        """
        try:
            resp = await self._http.get(
                f"{MEXC_API_BASE}/api/v1/contract/depth/{symbol}",
                params={"limit": depth},
            )
            resp.raise_for_status()
            data = resp.json()
            raw  = data.get("data") or {}

            def _parse(side: str) -> list[dict]:
                items = raw.get(side, [])
                out: list[dict] = []
                for item in items[:depth]:
                    try:
                        if isinstance(item, (list, tuple)) and len(item) >= 2:
                            out.append({"px": float(item[0]), "sz": float(item[1])})
                        elif isinstance(item, dict):
                            out.append({
                                "px": float(item.get("price", 0)),
                                "sz": float(item.get("quantity",
                                            item.get("vol", item.get("size", 0)))),
                            })
                    except (TypeError, ValueError):
                        pass
                return out

            return {"bids": _parse("bids"), "asks": _parse("asks")}
        except Exception as e:
            print(f"[MexcClient] get_orderbook({symbol}) error: {e}")
            return {"bids": [], "asks": []}

    # ── Private trading ───────────────────────────────────────────────────────

    async def open_position(
        self,
        symbol: str,
        direction: str,
        margin_usdc: float,
        leverage: int,
        entry_price: Optional[float] = None,
        order_type: str = "MARKET",
        limit_px: Optional[float] = None,
        sl_price: Optional[float] = None,
    ) -> dict:
        if self._paper_mode:
            price = entry_price or limit_px or await self.get_price(symbol) or 0.0
            size  = (margin_usdc * leverage) / price if price > 0 else 0.0
            if order_type == "LIMIT" and limit_px:
                return {
                    "status":    "pending",
                    "paper":     True,
                    "exchange":  "MEXC",
                    "order_id":  f"paper-{int(time.time())}",
                    "symbol":    symbol,
                    "direction": direction,
                    "limit_px":  limit_px,
                    "size":      size,
                    "margin":    margin_usdc,
                    "leverage":  leverage,
                    "timestamp": int(time.time()),
                }
            return {
                "status":      "ok",
                "paper":       True,
                "exchange":    "MEXC",
                "symbol":      symbol,
                "direction":   direction,
                "entry_price": price,
                "size":        size,
                "margin":      margin_usdc,
                "leverage":    leverage,
                "timestamp":   int(time.time()),
            }

        try:
            if not self._api_key or not self._secret_key:
                return {"status": "error", "msg": "MEXC_API_KEY / MEXC_SECRET_KEY not configured"}

            price   = entry_price or await self.get_price(symbol) or 0.0
            if not price:
                return {"status": "error", "msg": "Failed to fetch MEXC price"}

            exec_px   = limit_px if (order_type == "LIMIT" and limit_px) else price
            size      = round((margin_usdc * leverage) / exec_px, 6)
            side      = 1 if direction.upper() == "LONG" else 3
            order_t   = 1 if (order_type == "LIMIT" and limit_px) else 5

            body: dict = {
                "symbol":   symbol,
                "side":     side,
                "openType": 1,
                "type":     order_t,
                "vol":      size,
                "leverage": leverage,
            }
            if order_t == 1:
                body["price"] = exec_px
            if sl_price:
                body["stopLossPrice"] = sl_price

            body_str  = _json.dumps(body, separators=(",", ":"))
            ts        = str(int(time.time() * 1000))
            signature = self._sign_post(body_str, ts)

            resp = await self._http.post(
                f"{MEXC_API_BASE}/api/v1/private/order/submit",
                content=body_str,
                headers=self._auth_headers(ts, signature),
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("success"):
                base = {
                    "status":    "ok",
                    "paper":     False,
                    "exchange":  "MEXC",
                    "symbol":    symbol,
                    "direction": direction,
                    "size":      size,
                    "margin":    margin_usdc,
                    "leverage":  leverage,
                    "timestamp": int(time.time()),
                    "order_id":  str(data.get("data", "")),
                }
                if order_type == "LIMIT" and limit_px:
                    return {**base, "status": "pending", "limit_px": exec_px}
                return {**base, "entry_price": exec_px}
            return {"status": "error", "msg": data.get("message", "MEXC order rejected")}
        except Exception as e:
            return {"status": "error", "msg": str(e)}

    async def cancel_order(self, symbol: str, order_id: str) -> dict:
        if self._paper_mode:
            return {"status": "ok", "paper": True}
        try:
            if not self._api_key or not self._secret_key:
                return {"status": "error", "msg": "MEXC credentials not configured"}
            params    = {"symbol": symbol, "orderId": order_id}
            ts        = str(int(time.time() * 1000))
            signature = self._sign_get(params, ts)
            resp = await self._http.delete(
                f"{MEXC_API_BASE}/api/v1/private/order/cancel",
                params=params,
                headers=self._auth_headers(ts, signature),
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("success"):
                return {"status": "ok"}
            return {"status": "error", "msg": data.get("message", "cancel rejected")}
        except Exception as e:
            return {"status": "error", "msg": str(e)}

    async def close_position(self, symbol: str, direction: str, size: float) -> dict:
        if self._paper_mode:
            price = await self.get_price(symbol) or 0.0
            return {
                "status":      "ok",
                "paper":       True,
                "exchange":    "MEXC",
                "symbol":      symbol,
                "close_price": price,
                "timestamp":   int(time.time()),
            }
        try:
            if not self._api_key or not self._secret_key:
                return {"status": "error", "msg": "MEXC credentials not configured"}

            price = await self.get_price(symbol) or 0.0
            side  = 4 if direction.upper() == "LONG" else 2

            body: dict = {
                "symbol":   symbol,
                "side":     side,
                "openType": 1,
                "type":     5,
                "vol":      abs(size),
                "leverage": 1,
            }
            body_str  = _json.dumps(body, separators=(",", ":"))
            ts        = str(int(time.time() * 1000))
            signature = self._sign_post(body_str, ts)

            resp = await self._http.post(
                f"{MEXC_API_BASE}/api/v1/private/order/submit",
                content=body_str,
                headers=self._auth_headers(ts, signature),
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("success"):
                return {
                    "status":      "ok",
                    "paper":       False,
                    "exchange":    "MEXC",
                    "symbol":      symbol,
                    "close_price": price,
                    "timestamp":   int(time.time()),
                }
            return {"status": "error", "msg": data.get("message", "close rejected")}
        except Exception as e:
            return {"status": "error", "msg": str(e)}

    async def close(self):
        await self._http.aclose()
