from dataclasses import dataclass
from typing import Optional


@dataclass
class OrderPlan:
    symbol: str
    direction: str          # "LONG" | "SHORT"
    margin_type: str        # "Изолир" | "Кросс"
    position_size: float    # USDT
    leverage: float
    margin: float           # position_size / leverage
    entry_price: float      # resolved real price (never 0)
    is_market: bool
    stop_loss_pct: float
    sl_price: float
    final_tp_pct: float
    final_tp_price: float
    # market-only fields (None for limit orders)
    tp1_size_pct: Optional[float]
    tp1_offset_pct: Optional[float]
    tp1_price: Optional[float]
    tp2_size_pct: Optional[float]
    tp2_offset_pct: Optional[float]
    tp2_price: Optional[float]
    trailing_active_price: Optional[float]
    trailing_distance: Optional[float]
    breakeven_price: Optional[float]
    qty_step: float = 0.0
    hedge_mode: bool = False
    position_size_rounded: bool = False


def calculate(data: dict) -> OrderPlan:
    """Calculate SL/TP absolute prices from percentage offsets.

    For LONG:  sl = entry * (1 - pct/100),  tp = entry * (1 + pct/100)
    For SHORT: sl = entry * (1 + pct/100),  tp = entry * (1 - pct/100)
    entry_price in data must already be resolved (non-zero) before calling.
    """
    direction = data["direction"]
    entry = data["entry_price"]
    is_market = data["is_market"]
    sign = 1 if direction == "LONG" else -1

    sl_price = round(entry * (1 - sign * data["stop_loss_pct"] / 100), 8)
    final_tp_price = round(entry * (1 + sign * data["final_tp_pct"] / 100), 8)

    if is_market:
        tp1_price = round(entry * (1 + sign * data["tp1_offset_pct"] / 100), 8)
        tp2_price = round(entry * (1 + sign * data["tp2_offset_pct"] / 100), 8)
        tp1_size_pct = data["tp1_size_pct"]
        tp1_offset_pct = data["tp1_offset_pct"]
        tp2_size_pct = data["tp2_size_pct"]
        tp2_offset_pct = data["tp2_offset_pct"]
        # trailing distance in price units = same % as tp1 offset (editable in form)
        trailing_pct = data.get("trailing_distance_pct", tp1_offset_pct)
        trailing_distance = round(entry * trailing_pct / 100, 8)
        # breakeven: entry shifted by total round-trip fee
        fee = data.get("fee_rate_pct", 0.075) / 100
        breakeven_price = round(entry * (1 + sign * fee), 8)
        # activate at TP1; if trigger (active - distance) would be worse than breakeven, shift active outward
        trailing_active_price = tp1_price
        trigger_price = trailing_active_price - sign * trailing_distance
        if sign * (trigger_price - breakeven_price) < 0:
            trailing_active_price = round(breakeven_price + sign * trailing_distance, 8)
        else:
            trailing_active_price = round(trailing_active_price, 8)
    else:
        tp1_price = tp2_price = None
        tp1_size_pct = tp1_offset_pct = tp2_size_pct = tp2_offset_pct = None
        trailing_active_price = trailing_distance = breakeven_price = None

    return OrderPlan(
        symbol=data["symbol"],
        direction=direction,
        margin_type=data.get("margin_type", ""),
        position_size=data["position_size"],
        leverage=data["leverage"],
        margin=round(data["position_size"] / data["leverage"], 4),
        entry_price=entry,
        is_market=is_market,
        stop_loss_pct=data["stop_loss_pct"],
        sl_price=sl_price,
        final_tp_pct=data["final_tp_pct"],
        final_tp_price=final_tp_price,
        tp1_size_pct=tp1_size_pct,
        tp1_offset_pct=tp1_offset_pct,
        tp1_price=tp1_price,
        tp2_size_pct=tp2_size_pct,
        tp2_offset_pct=tp2_offset_pct,
        tp2_price=tp2_price,
        trailing_active_price=trailing_active_price,
        trailing_distance=trailing_distance,
        breakeven_price=breakeven_price,
        qty_step=data.get("qty_step", 0.0),
        hedge_mode=data.get("hedge_mode", False),
        position_size_rounded=data.get("position_size_rounded", False),
    )
