"""Long-only ATR trailing-stop rules shared by paper simulations and backtests."""

import math


def ratchet_trailing_stop(
    *,
    entry_price: float,
    initial_stop: float,
    current_stop: float,
    high_water_mark: float,
    current_atr: float,
    activation_r: float = 1.0,
    atr_multiple: float = 2.0,
) -> float:
    """Tighten a long stop after the trade advances by activation_r; never loosen it."""
    values = (
        entry_price,
        initial_stop,
        current_stop,
        high_water_mark,
        current_atr,
        activation_r,
        atr_multiple,
    )
    if not all(math.isfinite(value) for value in values):
        raise ValueError("Trailing-stop inputs must be finite.")
    if (
        entry_price <= 0
        or initial_stop <= 0
        or current_stop <= 0
        or current_atr <= 0
        or activation_r <= 0
        or atr_multiple <= 0
        or initial_stop >= entry_price
        or current_stop < initial_stop
        or high_water_mark < entry_price
    ):
        raise ValueError("Trailing-stop inputs are outside valid long-position ranges.")

    initial_risk = entry_price - initial_stop
    if high_water_mark < entry_price + initial_risk * activation_r:
        return current_stop

    candidate = high_water_mark - current_atr * atr_multiple
    return max(current_stop, candidate)
