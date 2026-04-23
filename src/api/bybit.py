import os
import math
from pybit.unified_trading import HTTP
from src.logic.calculator import OrderPlan


class BybitClient:
    def __init__(self):
        api_key = os.environ.get("BYBIT_API_KEY", "")
        api_secret = os.environ.get("BYBIT_API_SECRET", "")
        self._session = HTTP(
            testnet=False,
            api_key=api_key,
            api_secret=api_secret,
        )

    def validate_ticker(self, symbol: str) -> dict:
        """Check that symbol exists as a linear perpetual. Returns instrument info dict."""
        resp = self._session.get_instruments_info(category="linear", symbol=symbol)
        instruments = resp.get("result", {}).get("list", [])
        if not instruments:
            raise ValueError(f"Тикер {symbol} не найден на Bybit")
        return instruments[0]

    def get_last_price(self, symbol: str) -> float:
        """Return last traded price for a linear perpetual symbol."""
        resp = self._session.get_tickers(category="linear", symbol=symbol)
        items = resp.get("result", {}).get("list", [])
        if not items:
            raise ValueError(f"Не удалось получить цену для {symbol}")
        return float(items[0]["lastPrice"])

    def get_open_position_side(self, symbol: str) -> str | None:
        """Return 'LONG' or 'SHORT' if there is an open position for symbol, else None."""
        resp = self._session.get_positions(category="linear", symbol=symbol)
        for pos in resp.get("result", {}).get("list", []):
            size = float(pos.get("size", 0) or 0)
            if size == 0:
                continue
            return "LONG" if pos.get("side") == "Buy" else "SHORT"
        return None

    def get_margin_mode(self) -> str:
        """Return current account margin mode as a short label."""
        resp = self._session.get_account_info()
        mode = resp.get("result", {}).get("marginMode", "")
        return {"REGULAR_MARGIN": "Кросс", "ISOLATED_MARGIN": "Изолир", "PORTFOLIO_MARGIN": "Portfolio"}.get(mode, mode or "—")

    def get_available_balance(self) -> float:
        """Return available USDT balance from UNIFIED account."""
        resp = self._session.get_wallet_balance(accountType="UNIFIED")
        accounts = resp.get("result", {}).get("list", [])
        if not accounts:
            raise ValueError("Не удалось получить баланс: пустой ответ")
        account = accounts[0]
        # account-level total available balance
        val = account.get("totalAvailableBalance", "")
        if val != "":
            return float(val)
        # fallback: USDT coin entry
        for coin in account.get("coin", []):
            if coin.get("coin") == "USDT":
                avail = coin.get("availableToWithdraw") or coin.get("walletBalance", "")
                if avail:
                    return float(avail)
        raise ValueError("Не удалось получить баланс USDT")

    def place_orders(self, plan: OrderPlan, dry_run: bool = True) -> None:
        """Build and execute orders for the given plan.

        dry_run=True  — print calls to console, do NOT contact the exchange.
        dry_run=False — execute real API calls (enable only after dry-run verification).
        """
        side       = "Buy"  if plan.direction == "LONG" else "Sell"
        close_side = "Sell" if plan.direction == "LONG" else "Buy"
        qty        = round(plan.position_size / plan.entry_price, 6)
        # hedge mode: 1=long side, 2=short side; one-way mode: 0
        if plan.hedge_mode:
            pos_idx = 1 if plan.direction == "LONG" else 2
        else:
            pos_idx = 0

        # Ordered list of (method_name, kwargs) to execute
        calls = []

        # [0] Set leverage
        lev = str(int(plan.leverage))
        calls.append(("set_leverage", {
            "category":    "linear",
            "symbol":      plan.symbol,
            "buyLeverage": lev,
            "sellLeverage": lev,
        }))

        # [2] Main entry order with SL and final TP
        main_order: dict = {
            "category":    "linear",
            "symbol":      plan.symbol,
            "side":        side,
            "orderType":   "Market" if plan.is_market else "Limit",
            "qty":         str(qty),
            "stopLoss":    str(plan.sl_price),
            "takeProfit":  str(plan.final_tp_price),
            "tpslMode":    "Full",
            "positionIdx": pos_idx,
        }
        if not plan.is_market:
            main_order["price"] = str(plan.entry_price)
        calls.append(("place_order", main_order))

        if plan.is_market:
            step = plan.qty_step if plan.qty_step > 0 else 1e-8

            def _floor_to_step(q: float) -> float:
                return round(math.floor(q / step) * step, 10)

            tp1_qty = _floor_to_step(qty * plan.tp1_size_pct / 100)
            tp2_qty = _floor_to_step(qty * plan.tp2_size_pct / 100)

            # [3] TP1 — closing limit (hedge mode uses positionIdx; one-way mode uses reduceOnly)
            tp1_order: dict = {
                "category":    "linear",
                "symbol":      plan.symbol,
                "side":        close_side,
                "orderType":   "Limit",
                "price":       str(plan.tp1_price),
                "qty":         str(tp1_qty),
                "positionIdx": pos_idx,
            }
            if not plan.hedge_mode:
                tp1_order["reduceOnly"] = True
            calls.append(("place_order", tp1_order))

            # [4] TP2 — closing limit
            tp2_order: dict = {
                "category":    "linear",
                "symbol":      plan.symbol,
                "side":        close_side,
                "orderType":   "Limit",
                "price":       str(plan.tp2_price),
                "qty":         str(tp2_qty),
                "positionIdx": pos_idx,
            }
            if not plan.hedge_mode:
                tp2_order["reduceOnly"] = True
            calls.append(("place_order", tp2_order))

            # [5] Trailing stop — distance set so stop lands at breakeven when activating at TP1
            calls.append(("set_trading_stop", {
                "category":     "linear",
                "symbol":       plan.symbol,
                "trailingStop": str(plan.trailing_distance),
                "activePrice":  str(plan.trailing_active_price),
                "positionIdx":  pos_idx,
            }))

        if dry_run:
            print("=== DRY RUN — calls NOT sent to exchange ===")
            for i, (method, kwargs) in enumerate(calls):
                args_str = ", ".join(f"{k}={repr(v)}" for k, v in kwargs.items())
                print(f"  [{i}] session.{method}({args_str})")
            print("============================================")
        else:
            for i, (method, kwargs) in enumerate(calls):
                try:
                    getattr(self._session, method)(**kwargs)
                except Exception as e:
                    err = str(e)
                    if i == 0:
                        # 110043 = leverage not modified (already correct) — safe to skip
                        if "110043" in err or "not modified" in err.lower():
                            print(f"[{method}] already set, skipped")
                        else:
                            raise
                    else:
                        raise
