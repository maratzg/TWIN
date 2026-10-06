from dataclasses import dataclass
from datetime import date, timedelta
import calendar


GRAINS = {"day", "week", "month", "quarter", "year"}


@dataclass(frozen=True)
class Period:
    from_date: date
    to_date: date

    def response(self) -> dict[str, str]:
        return {"from_date": self.from_date.isoformat(), "to_date": self.to_date.isoformat()}

    @property
    def days(self) -> int:
        return (self.to_date - self.from_date).days + 1


def previous_period(period: Period) -> Period:
    previous_to = period.from_date - timedelta(days=1)
    return Period(previous_to - timedelta(days=period.days - 1), previous_to)


def subtract_months(value: date, months: int) -> date:
    absolute = value.year * 12 + value.month - 1 - months
    year, month_index = divmod(absolute, 12)
    month = month_index + 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


def baseline_period(period: Period, window: str) -> Period:
    end = period.from_date - timedelta(days=1)
    if window == "trailing_4_weeks":
        return Period(end - timedelta(days=27), end)
    if window == "trailing_8_weeks":
        return Period(end - timedelta(days=55), end)
    if window == "trailing_3_months":
        return Period(subtract_months(period.from_date, 3), end)
    raise ValueError("Baseline must be trailing_4_weeks, trailing_8_weeks, or trailing_3_months.")


def bucket_start(value: date, grain: str) -> date:
    if grain == "day":
        return value
    if grain == "week":
        return value - timedelta(days=value.weekday())
    if grain == "month":
        return date(value.year, value.month, 1)
    if grain == "quarter":
        return date(value.year, ((value.month - 1) // 3) * 3 + 1, 1)
    if grain == "year":
        return date(value.year, 1, 1)
    raise ValueError(f"Unsupported time grain: {grain}")


def next_bucket(value: date, grain: str) -> date:
    if grain == "day":
        return value + timedelta(days=1)
    if grain == "week":
        return value + timedelta(days=7)
    if grain == "month":
        return subtract_months(value, -1).replace(day=1)
    if grain == "quarter":
        return subtract_months(value, -3).replace(day=1)
    if grain == "year":
        return date(value.year + 1, 1, 1)
    raise ValueError(f"Unsupported time grain: {grain}")


def bucket_period(start: date, grain: str, report_end: date) -> Period:
    return Period(start, min(next_bucket(start, grain) - timedelta(days=1), report_end))


def iter_buckets(period: Period, grain: str) -> list[Period]:
    start = bucket_start(period.from_date, grain)
    values: list[Period] = []
    while start <= period.to_date:
        current = bucket_period(start, grain, period.to_date)
        values.append(Period(max(current.from_date, period.from_date), current.to_date))
        start = next_bucket(start, grain)
    return values
