import csv
import os
from datetime import datetime

from src.logic.calculator import OrderPlan

_LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "log.csv")

_FIELDNAMES = [
    "datetime", "symbol", "direction",
    "position_size", "leverage", "margin",
    "entry_price", "is_market",
    "stop_loss_pct", "sl_price",
    "final_tp_pct", "final_tp_price",
    "tp1_size_pct", "tp1_offset_pct", "tp1_price",
    "tp2_size_pct", "tp2_offset_pct", "tp2_price",
    "breakeven_price", "trailing_active_price", "trailing_distance",
]


def log_order(plan: OrderPlan) -> None:
    """Append one row to log.csv. Creates file with header if missing."""
    file_exists = os.path.exists(_LOG_PATH)
    with open(_LOG_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": plan.symbol,
            "direction": plan.direction,
            "position_size": plan.position_size,
            "leverage": plan.leverage,
            "margin": plan.margin,
            "entry_price": plan.entry_price,
            "is_market": plan.is_market,
            "stop_loss_pct": plan.stop_loss_pct,
            "sl_price": plan.sl_price,
            "final_tp_pct": plan.final_tp_pct,
            "final_tp_price": plan.final_tp_price,
            "tp1_size_pct": plan.tp1_size_pct,
            "tp1_offset_pct": plan.tp1_offset_pct,
            "tp1_price": plan.tp1_price,
            "tp2_size_pct": plan.tp2_size_pct,
            "tp2_offset_pct": plan.tp2_offset_pct,
            "tp2_price": plan.tp2_price,
            "breakeven_price": plan.breakeven_price,
            "trailing_active_price": plan.trailing_active_price,
            "trailing_distance": plan.trailing_distance,
        })
