"""Domain models: a trip and the summary of a day.

All money values are integers (whole tenge) so sums are always exact.
"""
import datetime as dt
from enum import Enum
from typing import Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class PaymentMethod(str, Enum):
    CASH = "cash"
    CARD = "card"


class Trip(BaseModel):
    """A single completed trip. Immutable and validated on creation."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    id: str = Field(min_length=1, max_length=64, description="Client-generated unique id")
    start: AwareDatetime = Field(description="ISO-8601 with timezone offset")
    end: AwareDatetime = Field(description="ISO-8601 with timezone offset")
    amount: int = Field(gt=0, strict=True, description="Fare, whole currency units")
    payment: PaymentMethod
    commission: int = Field(ge=0, strict=True, description="Service commission, whole currency units")

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        if self.end <= self.start:
            raise ValueError("end must be later than start")
        if self.commission > self.amount:
            raise ValueError("commission cannot exceed amount")
        return self


class PaymentTotals(BaseModel):
    trips: int = 0
    revenue: int = 0
    commission: int = 0
    net: int = Field(0, description="revenue - commission ('на руки')")


class DaySummary(PaymentTotals):
    date: dt.date
    by_payment: dict[PaymentMethod, PaymentTotals]
