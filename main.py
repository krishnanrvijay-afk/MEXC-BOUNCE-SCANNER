"""
main.py — MEXC Bounce Scanner FastAPI application.
"""

import asyncio
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import httpx

load_dotenv()

from config import (
    PAIRS, SCAN_INTERVAL_SECONDS, PRICE_INTERVAL_SECONDS, PAPER_MODE,
    LIVE_MANUAL_ENTRY_ONLY, SUPABASE_URL, SUPABASE_KEY,
    MARGIN_PER_TRADE, MARGIN_HARD_CAP, CONSECUTIVE_LOSS_STOP,
    DAILY_LOSS_LIMIT, TP1_R, TP2_R,
)
from mexc_client import MexcClient
import scanner as sc

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
)
log = logging.getLogger("main")

# ── Telegram ───────────────────────────────────────────────────────────────────

TELEGRAM_ENABLED = os.environ.get("TELEGRAM_ENABLED", "true").lower() == "true"
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")
_reminder_tasks: dict[str, asyncio.Task] = {}


async def _tg_post(text: str):
    if not TELEGRAM_ENABLED or not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log.info(f"[TG] {text[:100]}")
        return
    try:
        async with httpx.AsyncClient(timeout=6) as hc:
            await hc.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"},
            )
    except Exception as e:
        log.warning(f"[TG] send failed: {e}")


async def send_alert_telegram(alert: dict):
      sym   = alert["symbol"]
      disp  = sym.replace("_USDT", "")
      d     = alert["direction"]
      tier  = alert["tier"]
      lev   = alert["leverage"]
      price = alert["price"]
      sl    = alert["sl_price"]
      tp1   = alert["tp1_price"]
      tp2   = alert["tp2_price"]
      j15m  = alert["j15m"]
      j1h   = alert["j1h"]
      rsi   = alert["rsi15m"]
      adx   = alert["adx"]
      sess  = alert.get("session", "")
      arrow = chr(9660) if d == "SHORT" else chr(9650)
      NL    = chr(10)
      msg = (
          chr(128992) + " <b>MEXC BOUNCE</b>" + NL
          + f"{arrow} <b>{disp} {d}</b> [{tier} {lev}x]" + NL
          + f"Entry: <code>{price}</code>" + NL
          + f"SL:    <code>{sl}</code>" + NL
          + f"TP1:   <code>{tp1}</code>  (50% close)" + NL
          + f"TP2:   <code>{tp2}</code>  (50% close)" + NL
          + NL
          + f"J15M: {j15m:.1f}  J1H: {j1h:.1f}  RSI: {rsi:.1f}  ADX: {adx:.1f}" + NL
          + f"Session: {sess}  |  Margin: $" + str(MARGIN_PER_TRADE) + NL
          + f"#MEXC_BOUNCE #{disp} #{d}"
      )
      await _tg_post(msg)


async def _reminder_task(trade_id: str, sym: str, d: str, entry: float, sl: float, tp1: float, tp2: float):
      await asyncio.sleep(1800)
      disp  = sym.replace("_USDT", "")
      arrow = chr(9660) if d == "SHORT" else chr(9650)
      NL    = chr(10)
      msg = (
          chr(128992) + " <b>MEXC BOUNCE — 30m REMINDER</b>" + NL
          + f"{arrow} <b>{disp} {d}</b>  still open" + NL
          + f"Entry: {entry}  SL: {sl}  TP1: {tp1}  TP2: {tp2}"
      )
      await _tg_post(msg)


def start_reminder(trade_id: str, sym: str, d: str, entry: float, sl: float, tp1: float, tp2: float):
    cancel_reminder(trade_id)
    t = asyncio.create_task(_reminder_task(trade_id, sym, d, entry, sl, tp1, tp2))
    _reminder_tasks[trade_id] = t


def cancel_reminder(trade_id: str):
    t = _reminder_tasks.pop(trade_id, None)
    if t:
        t.cancel()


async def send_exit_telegram(trade: dict, reason: str, pnl: float):
      sym   = trade["symbol"]
      disp  = sym.replace("_USDT", "")
      d     = trade["direction"]
      entry = trade["entry_price"]
      exit_p = trade.get("exit_price", trade.get("close_price", 0))
      pnl_sign = "+" if pnl >= 0 else ""
      ok_emoji = chr(9989) if pnl >= 0 else chr(10060)
      NL    = chr(10)
      msg = (
          chr(128992) + " <b>MEXC BOUNCE — EXIT</b> " + ok_emoji + NL
          + f"<b>{disp} {d}</b>  [{reason}]" + NL
          + f"Entry: {entry}  Exit: {exit_p}" + NL
          + f"PnL: <b>{pnl_sign}{pnl:.2f} USDT</b>" + NL
          + f"#MEXC_BOUNCE #{disp}"
      )
      await _tg_post(msg)


def _get_supabase():
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    try:
        from supabase import create_client
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        log.warning(f"[DB] Supabase init failed: {e}")
        return None


def _save_state(state: dict):
    sb = _get_supabase()
    if not sb:
        return
    try:
        existing = sb.table("scanner_state").select("id").execute()
        payload  = {"key": "mexc_bounce_scanner", "state": state}
        if existing.data:
            sb.table("scanner_state").update(payload).eq("id", existing.data[0]["id"]).execute()
        else:
            sb.table("scanner_state").insert(payload).execute()
    except Exception as e:
        log.warning(f"[DB] save_state: {e}")


def _load_state() -> Optional[dict]:
    sb = _get_supabase()
    if not sb:
        return None
    try:
        res = sb.table("scanner_state").select("state").eq("key", "mexc_bounce_scanner").execute()
        if res.data:
            return res.data[0]["state"]
    except Exception as e:
        log.warning(f"[DB] load_state: {e}")
    return None


def _append_trade_log(trade: dict):
    sb = _get_supabase()
    if not sb:
        return
    try:
        row = {**trade, "exchange": "MEXC"}
        sb.table("trade_log").insert(row).execute()
    except Exception as e:
        log.warning(f"[DB] append_trade_log: {e}")


def _load_trade_log() -> list:
    sb = _get_supabase()
    if not sb:
        return []
    try:
        res = (
            sb.table("trade_log")
            .select("*")
            .eq("exchange", "MEXC")
            .order("opened_at", desc=True)
            .limit(1000)
            .execute()
        )
        return res.data or []
    except Exception as e:
        log.warning(f"[DB] load_trade_log: {e}")
        return []


# ── App state ──────────────────────────────────────────────────────────────────

class AppState:
    def __init__(self):
        self.paper_mode: bool = PAPER_MODE
        self.live_manual: bool = LIVE_MANUAL_ENTRY_ONLY
        self.scan_count: int = 0
        self.prices: dict[str, float] = {}
        self.pair_data: dict[str, dict] = {}
        self.open_trades: list[dict] = []
        self.trade_log: list[dict] = []
        self.alerts: list[dict] = []
        self.market_health: dict = {}
        self.daily_pnl: float = 0.0
        self.daily_pnl_date: str = ""
        self.consecutive_losses: int = 0
        self.circuit_breaker: bool = False
        self.last_scan_ts: float = 0.0

    @property
    def deployed_margin(self) -> float:
        return sum(t.get("margin", 0) for t in self.open_trades)

    def serialise(self) -> dict:
        return {
            "paper_mode":         self.paper_mode,
            "live_manual":        self.live_manual,
            "scan_count":         self.scan_count,
            "prices":             self.prices,
            "pair_data":          self.pair_data,
            "open_trades":        self.open_trades,
            "trade_log":          self.trade_log[-200:],
            "alerts":             self.alerts[-50:],
            "market_health":      self.market_health,
            "daily_pnl":          round(self.daily_pnl, 2),
            "deployed_margin":    round(self.deployed_margin, 2),
            "consecutive_losses": self.consecutive_losses,
            "circuit_breaker":    self.circuit_breaker,
            "last_scan_ts":       self.last_scan_ts,
            "session":            sc.get_session_name(),
        }


state = AppState()
mexc  = MexcClient()


# ── Trade lifecycle ────────────────────────────────────────────────────────────

def _ensure_daily_reset():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if state.daily_pnl_date != today:
        state.daily_pnl_date   = today
        state.daily_pnl        = 0.0
        state.consecutive_losses = 0
        state.circuit_breaker  = False


def _calc_pnl(trade: dict, exit_price: float) -> float:
    d     = trade["direction"]
    entry = trade["entry_price"]
    margin = trade.get("margin", MARGIN_PER_TRADE)
    lev   = trade.get("leverage", 5)
    pos_val = margin * lev
    if d == "LONG":
        return (exit_price - entry) / entry * pos_val
    else:
        return (entry - exit_price) / entry * pos_val


def _open_paper_trade(alert: dict) -> dict:
    trade_id = str(uuid.uuid4())[:8]
    trade = {
        "id":          trade_id,
        "symbol":      alert["symbol"],
        "direction":   alert["direction"],
        "tier":        alert["tier"],
        "leverage":    alert["leverage"],
        "margin":      MARGIN_PER_TRADE,
        "entry_price": alert["price"],
        "sl_price":    alert["sl_price"],
        "tp1_price":   alert["tp1_price"],
        "tp2_price":   alert["tp2_price"],
        "be_price":    alert.get("be_price", alert["price"]),
        "sl_dist":     alert.get("sl_dist", 0),
        "tp1_hit":     False,
        "status":      "OPEN",
        "opened_at":   datetime.now(timezone.utc).isoformat(),
        "j15m":        alert.get("j15m"),
        "j1h":         alert.get("j1h"),
        "rsi15m":      alert.get("rsi15m"),
        "adx":         alert.get("adx"),
        "session":     alert.get("session"),
        "exchange":    "MEXC",
    }
    state.open_trades.append(trade)
    _append_trade_log({**trade, "status": "OPEN"})
    start_reminder(trade_id, trade["symbol"], trade["direction"],
                   trade["entry_price"], trade["sl_price"],
                   trade["tp1_price"], trade["tp2_price"])
    return trade


def _close_trade(trade: dict, exit_price: float, reason: str):
    pnl = _calc_pnl(trade, exit_price)
    if trade.get("tp1_hit"):
        pnl = pnl / 2   # only 50% remains after TP1
    trade.update({
        "status":       "CLOSED",
        "exit_price":   exit_price,
        "close_reason": reason,
        "pnl":          round(pnl, 2),
        "closed_at":    datetime.now(timezone.utc).isoformat(),
    })
    state.open_trades = [t for t in state.open_trades if t["id"] != trade["id"]]
    state.trade_log.insert(0, trade)
    state.daily_pnl += pnl
    if pnl < 0:
        state.consecutive_losses += 1
        if state.consecutive_losses >= CONSECUTIVE_LOSS_STOP:
            state.circuit_breaker = True
            log.warning(f"[CB] Circuit breaker ON — {state.consecutive_losses} consecutive losses")
    else:
        state.consecutive_losses = 0
    cancel_reminder(trade["id"])
    _append_trade_log(trade)
    asyncio.create_task(send_exit_telegram(trade, reason, pnl))


def _partial_close_tp1(trade: dict, price: float):
    pnl_half = _calc_pnl(trade, price) / 2
    state.daily_pnl += pnl_half
    trade["tp1_hit"] = True
    trade["tp1_price_actual"] = price
    trade["tp1_pnl"] = round(pnl_half, 2)
    # Move SL to BE
    trade["sl_price"] = trade.get("be_price", trade["entry_price"])
    log.info(f"[TP1] {trade['symbol']} {trade['direction']} partial close @ {price}, PnL: {pnl_half:.2f}")
    asyncio.create_task(
        send_exit_telegram(trade, "TP1 hit (50% closed)", pnl_half)
    )
    _append_trade_log({**trade, "status": "TP1_HIT"})


# ── Exit monitor ───────────────────────────────────────────────────────────────

async def _exit_monitor_loop():
    while True:
        try:
            await asyncio.sleep(PRICE_INTERVAL_SECONDS)
            _ensure_daily_reset()
            trades_to_check = list(state.open_trades)
            for trade in trades_to_check:
                sym   = trade["symbol"]
                price = state.prices.get(sym)
                if not price:
                    continue
                d      = trade["direction"]
                sl     = trade["sl_price"]
                tp1    = trade["tp1_price"]
                tp2    = trade["tp2_price"]
                tp1hit = trade.get("tp1_hit", False)

                if d == "LONG":
                    if not tp1hit and price >= tp1:
                        _partial_close_tp1(trade, price)
                    elif tp1hit and price >= tp2:
                        _close_trade(trade, price, "TP2")
                    elif price <= sl:
                        _close_trade(trade, price, "SL")
                else:  # SHORT
                    if not tp1hit and price <= tp1:
                        _partial_close_tp1(trade, price)
                    elif tp1hit and price <= tp2:
                        _close_trade(trade, price, "TP2")
                    elif price >= sl:
                        _close_trade(trade, price, "SL")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.error(f"[EXIT] monitor error: {e}", exc_info=True)


# ── Price loop ─────────────────────────────────────────────────────────────────

async def _price_loop():
    while True:
        try:
            tasks = {sym: mexc.fetch_price(sym) for sym in PAIRS}
            results = await asyncio.gather(*tasks.values(), return_exceptions=True)
            for sym, result in zip(tasks.keys(), results):
                if isinstance(result, float) and result > 0:
                    state.prices[sym] = result
                    # Update price in pair_data cache
                    if sym in state.pair_data:
                        state.pair_data[sym]["price"] = result
        except Exception as e:
            log.error(f"[PRICE] loop error: {e}")
        await asyncio.sleep(PRICE_INTERVAL_SECONDS)


# ── Scan loop ──────────────────────────────────────────────────────────────────

async def _scan_loop():
    while True:
        try:
            _ensure_daily_reset()

            # Safety checks
            if state.circuit_breaker:
                log.warning("[SCAN] Circuit breaker active — skipping")
                await asyncio.sleep(SCAN_INTERVAL_SECONDS)
                continue
            if state.daily_pnl <= DAILY_LOSS_LIMIT:
                log.warning(f"[SCAN] Daily loss limit hit ({state.daily_pnl:.2f}) — halting")
                await asyncio.sleep(SCAN_INTERVAL_SECONDS)
                continue
            if state.deployed_margin >= MARGIN_HARD_CAP:
                log.warning(f"[SCAN] Margin cap reached ({state.deployed_margin:.0f}) — skipping")
                await asyncio.sleep(SCAN_INTERVAL_SECONDS)
                continue

            alerts = await sc.run_full_scan(mexc)
            state.scan_count = sc.get_scan_count()
            state.last_scan_ts = time.time()

            # Update market health
            pair_states = list(state.pair_data.values())
            state.market_health = sc.compute_market_health(pair_states, state.trade_log[:50])

            for alert in alerts:
                sym = alert["symbol"]
                d   = alert["direction"]

                # Margin cap check
                if state.deployed_margin + MARGIN_PER_TRADE > MARGIN_HARD_CAP:
                    log.warning(f"[SCAN] Margin cap would be exceeded — skipping {sym} {d}")
                    continue

                state.alerts.insert(0, {**alert, "ts": datetime.now(timezone.utc).isoformat()})

                await send_alert_telegram(alert)

                if state.paper_mode:
                    trade = _open_paper_trade(alert)
                    log.info(f"[PAPER] Opened {sym} {d} id={trade['id']}")

            # Persist state every scan
            _save_state(state.serialise())

        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.error(f"[SCAN] loop error: {e}", exc_info=True)

        await asyncio.sleep(SCAN_INTERVAL_SECONDS)


# ── Pair data update loop ──────────────────────────────────────────────────────

async def _pair_data_loop():
    """Update pair_data (indicators) after each scan — runs immediately then every SCAN_INTERVAL_SECONDS."""
    while True:
        try:
            for sym in PAIRS:
                await asyncio.sleep(0.3)
                fast = await sc.scan_pair_fast(mexc, sym)
                if fast.get("price"):
                    state.pair_data[sym] = fast
                    if fast["price"]:
                        state.prices[sym] = fast["price"]
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.error(f"[PAIR_DATA] loop error: {e}")
        await asyncio.sleep(SCAN_INTERVAL_SECONDS)


# ── Lifespan ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("[BOOT] MEXC Bounce Scanner starting...")

    # Restore persisted state
    saved = _load_state()
    if saved:
        state.open_trades  = saved.get("open_trades", [])
        state.trade_log    = saved.get("trade_log", [])
        state.daily_pnl    = saved.get("daily_pnl", 0.0)
        state.scan_count   = saved.get("scan_count", 0)
        log.info(f"[BOOT] Restored {len(state.open_trades)} open trades, {len(state.trade_log)} log entries")
    else:
        log.info("[BOOT] No persisted state — loading trade log from DB")
        state.trade_log = _load_trade_log()

    # Start background tasks
    tasks = [
        asyncio.create_task(_price_loop(),      name="price_loop"),
        asyncio.create_task(_scan_loop(),       name="scan_loop"),
        asyncio.create_task(_exit_monitor_loop(), name="exit_monitor"),
        asyncio.create_task(_pair_data_loop(),  name="pair_data"),
    ]

    yield

    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    await mexc.close()
    log.info("[SHUTDOWN] MEXC Bounce Scanner stopped")


# ── FastAPI app ────────────────────────────────────────────────────────────────

app = FastAPI(title="MEXC Bounce Scanner", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="dashboard.html")


@app.get("/api/state")
async def api_state():
    return JSONResponse(state.serialise())


@app.get("/api/pair/{symbol}")
async def api_pair(symbol: str):
    sym = symbol.upper()
    if sym not in PAIRS and sym + "_USDT" in PAIRS:
        sym = sym + "_USDT"
    if sym not in PAIRS:
        raise HTTPException(404, "Symbol not found")
    cached = state.pair_data.get(sym)
    if cached:
        return JSONResponse({
            **cached,
            "open_trade":  next((t for t in state.open_trades if t["symbol"] == sym), None),
            "cooldown_short": sc.get_cooldown_remaining(sym, "SHORT"),
            "cooldown_long":  sc.get_cooldown_remaining(sym, "LONG"),
        })
    # Fall back to live fetch
    fast = await sc.scan_pair_fast(mexc, sym)
    return JSONResponse({
        **fast,
        "open_trade":  next((t for t in state.open_trades if t["symbol"] == sym), None),
        "cooldown_short": sc.get_cooldown_remaining(sym, "SHORT"),
        "cooldown_long":  sc.get_cooldown_remaining(sym, "LONG"),
    })


@app.get("/api/tradelog")
async def api_tradelog():
    all_trades = state.open_trades + state.trade_log
    headers = ["id","symbol","direction","tier","leverage","margin","entry_price",
               "exit_price","sl_price","tp1_price","tp2_price","status","close_reason",
               "pnl","opened_at","closed_at","session","exchange"]
    rows = [",".join(str(t.get(h, "")) for h in headers) for t in all_trades]
    csv  = ",".join(headers) + "\n" + "\n".join(rows)
    return StreamingResponse(
        iter([csv]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=mexc_trade_log.csv"},
    )


@app.post("/api/paper/open")
async def api_paper_open(request: Request):
    body = await request.json()
    sym  = body.get("symbol", "").upper()
    d    = body.get("direction", "").upper()
    if sym not in PAIRS:
        raise HTTPException(400, "Invalid symbol")
    if d not in ("LONG", "SHORT"):
        raise HTTPException(400, "direction must be LONG or SHORT")
    cached = state.pair_data.get(sym) or {}
    price  = state.prices.get(sym) or cached.get("price", 0)
    if not price:
        raise HTTPException(400, "No price available")
    atr15m = cached.get("atr15m", price * 0.005)
    from config import MIN_SL_PCT, MIN_SL_PCT_DEFAULT, ATR_SL_MULTIPLIER, TP1_R, TP2_R
    from scanner import _leverage_tier
    adx = cached.get("adx1h", 0)
    sl_dist = max(atr15m * ATR_SL_MULTIPLIER, price * MIN_SL_PCT.get(sym, MIN_SL_PCT_DEFAULT))
    tier, lev = _leverage_tier(adx)
    if d == "SHORT":
        sl_price  = round(price + sl_dist, 8)
        tp1_price = round(price - sl_dist * TP1_R, 8)
        tp2_price = round(price - sl_dist * TP2_R, 8)
        be_price  = round(price - price * 0.001, 8)
    else:
        sl_price  = round(price - sl_dist, 8)
        tp1_price = round(price + sl_dist * TP1_R, 8)
        tp2_price = round(price + sl_dist * TP2_R, 8)
        be_price  = round(price + price * 0.001, 8)
    alert = {
        "symbol": sym, "direction": d, "tier": tier, "leverage": lev,
        "price": price, "sl_price": sl_price, "tp1_price": tp1_price,
        "tp2_price": tp2_price, "be_price": be_price, "sl_dist": sl_dist,
        "j15m": cached.get("j15m"), "j1h": cached.get("j1h"),
        "rsi15m": cached.get("rsi15m"), "adx": adx,
        "session": sc.get_session_name(),
    }
    trade = _open_paper_trade(alert)
    return JSONResponse({"ok": True, "trade_id": trade["id"]})


@app.post("/api/paper/close")
async def api_paper_close(request: Request):
    body     = await request.json()
    trade_id = body.get("trade_id")
    sym      = body.get("symbol", "").upper()
    force    = body.get("force", False)
    trade    = None
    if trade_id:
        trade = next((t for t in state.open_trades if t["id"] == trade_id), None)
    elif sym:
        trade = next((t for t in state.open_trades if t["symbol"] == sym), None)
    if not trade:
        raise HTTPException(404, "Trade not found")
    price = state.prices.get(trade["symbol"], trade["entry_price"])
    reason = "FORCE_CLOSE" if force else "MANUAL_CLOSE"
    _close_trade(trade, price, reason)
    return JSONResponse({"ok": True})


@app.post("/api/settings")
async def api_settings(request: Request):
    body = await request.json()
    if "paper_mode" in body:
        state.paper_mode = bool(body["paper_mode"])
    if "live_manual" in body:
        state.live_manual = bool(body["live_manual"])
    if body.get("reset_circuit_breaker"):
        state.circuit_breaker = False
        state.consecutive_losses = 0
    return JSONResponse({"ok": True, "paper_mode": state.paper_mode, "live_manual": state.live_manual})
