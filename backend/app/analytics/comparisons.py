from decimal import Decimal


def compare_values(
    current: Decimal | None,
    previous: Decimal | None,
    unit: str,
) -> dict:
    if current is None or previous is None:
        return {
            "current": current,
            "previous": previous,
            "absolute_change": None,
            "percentage_change": None,
            "change_type": "percentage_points" if unit == "percent" else "absolute",
        }
    absolute = current - previous
    if unit == "percent":
        percentage_change = None
        change_type = "percentage_points"
    else:
        percentage_change = (absolute / previous * Decimal("100")) if previous != 0 else None
        change_type = "absolute"
    return {
        "current": current,
        "previous": previous,
        "absolute_change": absolute,
        "percentage_change": percentage_change,
        "change_type": change_type,
    }
