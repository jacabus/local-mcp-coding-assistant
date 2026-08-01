"""Clean pure function: no I/O, no network, no HTTP."""


def clamp(value: float, low: float, high: float) -> float:
    if low > high:
        low, high = high, low
    if value < low:
        return low
    if value > high:
        return high
    return value
