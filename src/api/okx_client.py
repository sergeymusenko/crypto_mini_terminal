import os
import sys
import math

# Our entry-point okx.py shadows the python-okx package when the project root
# is in sys.path. Temporarily remove it so the installed package is found first.
_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
_saved_path = sys.path[:]
sys.path = [p for p in sys.path if os.path.abspath(p) != _root and p != '']
import okx.Account as Account
import okx.Trade as Trade
import okx.MarketData as MarketData
import okx.PublicData as PublicData
sys.path[:] = _saved_path

from src.logic.calculator import OrderPlan


def _flag() -> str:
    return "1" if os.environ.get("OKX_DEMO", "false").strip().lower() == "true" else "0"


def _to_inst_id(symbol: str) -> str:
    """BTCUSDT → BTC-USDT-SWAP"""
    if symbol.endswith("USDT"):
        return f"{symbol[:-4]}-USDT-SWAP"
    return symbol


def _check(resp: dict, skip_codes: tuple = ()) -> dict:
    """Raise on non-zero OKX response code unless it's in skip_codes."""
    code = str(resp.get("code", "0"))
    if code != "0" and code not in skip_codes:
        msg = resp.get("msg", "Unknown OKX error")
        raise Exception(f"OKX [{code}]: {msg}")
    return resp


class OkxClient:
    def __init__(self):
        key        = os.environ.get("OKX_API_KEY", "")
        secret     = os.environ.get("OKX_API_SECRET", "")
        passphrase = os.environ.get("OKX_PASSPHRASE", "")
        f = _flag()
        self._trade   = Trade.TradeAPI(key, secret, passphrase, flag=f)
        self._account = Account.AccountAPI(key, secret, passphrase, flag=f)
        self._market  = MarketData.MarketAPI(flag=f)
        self._public  = PublicData.PublicAPI(flag=f)

    def _get_instrument(self, inst_id: str) -> dict:
        resp = self._public.get_instruments(instType="SWAP", instId=inst_id)
        items = resp.get("data", [])
        if not items:
            raise ValueError(f"Instrument {inst_id} not found on OKX")
        return items[0]

    def validate_ticker(self, symbol: str) -> dict:
        """Check that symbol exists as a SWAP perpetual. Returns instrument info in Bybit-compatible format."""
        inst_id = _to_inst_id(symbol)
        inst = self._get_instrument(inst_id)
        ct_val = float(inst.get("ctVal", 1))   # contract value in base currency (e.g. 0.01 BTC)
        lot_sz = float(inst.get("lotSz", 1))   # min order increment in contracts
        min_sz = float(inst.get("minSz", 1))   # minimum order size in contracts
        # Express limits in coin units so main_window qty calculation works unchanged
        return {
            "lotSizeFilter": {
                "minOrderQty":    min_sz * ct_val,
                "qtyStep":        lot_sz * ct_val,
                "minNotionalValue": 0,
            },
            "leverageFilter": {
                "maxLeverage": inst.get("lever", "125"),
            },
            "_ctVal": ct_val,
        }

    def get_last_price(self, symbol: str) -> float:
        inst_id = _to_inst_id(symbol)
        resp = self._market.get_ticker(instId=inst_id)
        items = resp.get("data", [])
        if not items:
            raise ValueError(f"Failed to get price for {inst_id}")
        return float(items[0]["last"])

    def get_open_position_side(self, symbol: str) -> str | None:
        inst_id = _to_inst_id(symbol)
        resp = self._account.get_positions(instType="SWAP", instId=inst_id)
        for pos in resp.get("data", []):
            if float(pos.get("pos", 0) or 0) != 0:
                return "LONG" if pos.get("posSide") == "long" else "SHORT"
        return None

    def get_margin_mode(self) -> str:
        # OKX has no global margin mode — it's per position.
        # Read from open positions when available; show "—" otherwise.
        try:
            resp = self._account.get_positions(instType="SWAP")
            for pos in resp.get("data", []):
                if float(pos.get("pos", 0) or 0) != 0:
                    return pos.get("mgnMode", "—")
        except Exception:
            pass
        return "—"

    def get_available_balance(self) -> float:
        resp = self._account.get_account_balance(ccy="USDT")
        for item in resp.get("data", []):
            for coin in item.get("details", []):
                if coin.get("ccy") == "USDT":
                    val = coin.get("availEq") or coin.get("availBal", "")
                    if val:
                        return float(val)
        raise ValueError("Failed to get USDT balance")

    def place_orders(self, plan: OrderPlan, dry_run: bool = True) -> None:
        inst_id  = _to_inst_id(plan.symbol)
        inst     = self._get_instrument(inst_id)
        ct_val   = float(inst.get("ctVal", 1))

        side      = "buy"  if plan.direction == "LONG" else "sell"
        close_side = "sell" if plan.direction == "LONG" else "buy"
        pos_side  = "long" if plan.direction == "LONG" else "short"
        td_mode   = plan.margin_type.lower() if plan.margin_type.lower() in ("cross", "isolated") else "cross"

        # qty in contracts (OKX uses contracts, not coins)
        qty_coins     = plan.position_size / plan.entry_price
        qty_contracts = max(1, round(qty_coins / ct_val))

        calls = []  # list of (api_object, method_name, kwargs)

        # [0] Set leverage
        lev_kwargs = {
            "instId":  inst_id,
            "lever":   str(int(plan.leverage)),
            "mgnMode": td_mode,
        }
        if plan.hedge_mode:
            lev_kwargs["posSide"] = pos_side
        calls.append((self._account, "set_leverage", lev_kwargs))

        # [1] Main entry order — SL/TP via attachAlgoOrds (required by OKX API)
        main_order: dict = {
            "instId":  inst_id,
            "tdMode":  td_mode,
            "side":    side,
            "ordType": "market" if plan.is_market else "limit",
            "sz":      str(qty_contracts),
            "attachAlgoOrds": [{
                "tpTriggerPx":      str(plan.final_tp_price),
                "tpOrdPx":          "-1",
                "slTriggerPx":      str(plan.sl_price),
                "slOrdPx":          "-1",
                "tpTriggerPxType":  "last",
                "slTriggerPxType":  "last",
            }],
        }
        if plan.hedge_mode:
            main_order["posSide"] = pos_side
        if not plan.is_market:
            main_order["px"] = str(plan.entry_price)
        calls.append((self._trade, "place_order", main_order))

        if plan.is_market:
            def _floor_contracts(ratio: float) -> int:
                return math.floor(qty_contracts * ratio / 100)

            tp1_qty = max(1, _floor_contracts(plan.tp1_size_pct))
            tp2_qty = min(_floor_contracts(plan.tp2_size_pct), qty_contracts - tp1_qty)
            remaining = qty_contracts - tp1_qty - max(tp2_qty, 0)

            # [2] TP1 closing limit order
            tp1_order: dict = {
                "instId":  inst_id,
                "tdMode":  td_mode,
                "side":    close_side,
                "ordType": "limit",
                "px":      str(plan.tp1_price),
                "sz":      str(tp1_qty),
            }
            if plan.hedge_mode:
                tp1_order["posSide"] = pos_side
            else:
                tp1_order["reduceOnly"] = "true"
            calls.append((self._trade, "place_order", tp1_order))

            # [3] TP2 closing limit order (skip if no contracts left)
            if tp2_qty > 0:
                tp2_order: dict = {
                    "instId":  inst_id,
                    "tdMode":  td_mode,
                    "side":    close_side,
                    "ordType": "limit",
                    "px":      str(plan.tp2_price),
                    "sz":      str(tp2_qty),
                }
                if plan.hedge_mode:
                    tp2_order["posSide"] = pos_side
                else:
                    tp2_order["reduceOnly"] = "true"
                calls.append((self._trade, "place_order", tp2_order))

            # [4] Trailing stop algo order (skip if no contracts left)
            if remaining > 0:
                trail_order: dict = {
                    "instId":         inst_id,
                    "tdMode":         td_mode,
                    "side":           close_side,
                    "ordType":        "move_order_stop",
                    "sz":             str(remaining),
                    "activePx":       str(plan.trailing_active_price),
                    "callbackSpread": str(plan.trailing_distance),
                }
                if plan.hedge_mode:
                    trail_order["posSide"] = pos_side
                else:
                    trail_order["reduceOnly"] = "true"
                calls.append((self._trade, "place_algo_order", trail_order))

        if dry_run:
            print("=== DRY RUN — calls NOT sent to exchange ===")
            for i, (_, method, kwargs) in enumerate(calls):
                args_str = ", ".join(f"{k}={repr(v)}" for k, v in kwargs.items())
                print(f"  [{i}] {method}({args_str})")
            print("============================================")
        else:
            for i, (api, method, kwargs) in enumerate(calls):
                try:
                    resp = getattr(api, method)(**kwargs)
                    _check(resp, skip_codes=("51400",))  # 51400 = leverage already set
                except Exception as e:
                    err = str(e)
                    if i == 0 and ("51400" in err or "leverage" in err.lower()):
                        print(f"[set_leverage] already set, skipped")
                    else:
                        raise
