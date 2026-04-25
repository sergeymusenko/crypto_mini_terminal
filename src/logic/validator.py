class ValidationError(Exception):
    def __init__(self, message, field=None):
        super().__init__(message)
        self.field = field  # key matching _FIELD_WIDGETS in main_window


def validate_inputs(data: dict) -> None:
    """Raise ValidationError if any field value is out of range or inconsistent.

    data keys: symbol, direction, position_size, leverage, entry_price, is_market,
               stop_loss_pct, final_tp_pct,
               tp1_size_pct, tp1_offset_pct,   <- market orders only
               tp2_size_pct, tp2_offset_pct    <- market orders only
    """
    if not data.get("symbol"):
        raise ValidationError("Symbol is required", field="symbol")

    if data["direction"] not in ("LONG", "SHORT"):
        raise ValidationError("Direction must be LONG or SHORT", field="direction")

    if data["position_size"] <= 0:
        raise ValidationError("Position size must be > 0", field="position_size")

    if data["leverage"] < 1:
        raise ValidationError("Leverage must be ≥ 1", field="leverage")

    if data["entry_price"] < 0:
        raise ValidationError("Entry price cannot be negative", field="entry_price")

    if not (0 < data["stop_loss_pct"] <= 100):
        raise ValidationError("Stop loss must be between 0.01% and 100%", field="stop_loss_pct")

    if not (0 < data["final_tp_pct"] <= 10_000):
        raise ValidationError("Final TP must be > 0%", field="final_tp_pct")

    if data["is_market"]:
        tp1 = data["tp1_size_pct"]
        tp2 = data["tp2_size_pct"]
        if not (0 < tp1 < 100):
            raise ValidationError("TP1 size must be between 0.01% and 99%", field="tp1_size_pct")
        if not (0 < tp2 < 100):
            raise ValidationError("TP2 size must be between 0.01% and 99%", field="tp2_size_pct")
        if tp1 + tp2 >= 100:
            raise ValidationError(f"TP1 + TP2 = {tp1 + tp2:.1f}% — total must be < 100%", field="tp1_size_pct")

        if data["tp1_offset_pct"] <= 0:
            raise ValidationError("TP1 offset must be > 0%", field="tp1_offset_pct")
        if data["tp2_offset_pct"] <= 0:
            raise ValidationError("TP2 offset must be > 0%", field="tp2_offset_pct")
        if data["tp2_offset_pct"] <= data["tp1_offset_pct"]:
            raise ValidationError("TP2 offset must be greater than TP1 offset", field="tp2_offset_pct")

