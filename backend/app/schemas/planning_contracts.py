"""
Canonical planning contracts shared by data integration,
prioritization, and block planning.
"""

from __future__ import annotations

from datetime import date, time

from pydantic import BaseModel, Field

from backend.app.schemas.unified_data import Priority


class MaintenanceWork(BaseModel):
    """Canonical maintenance work item entering the planning pipeline."""

    maintenance_id: str = Field(min_length=1)
    asset_id: str = Field(min_length=1)
    asset_type: str = Field(min_length=1)
    location: str = Field(min_length=1)
    maintenance_type: str = Field(min_length=1)

    maintenance_required: bool
    priority: Priority

    duration_minutes: int = Field(gt=0)
    requested_date: date
    preferred_start: time

    required_resources: int = Field(gt=0)
    equipment: str = Field(min_length=1)

    status: str = Field(min_length=1)
    source: str | None = None


class BlockAvailability(BaseModel):
    """Available railway block window for planning."""

    block_id: str = Field(min_length=1)
    location: str = Field(min_length=1)
    available_date: date
    start_time: time
    end_time: time

    available: bool = True
    source: str | None = None


class TimetableConstraints(BaseModel):
    """Timetable constraints that a maintenance block must respect."""

    train_id: str = Field(min_length=1)
    service_date: date
    station_code: str = Field(min_length=1)

    arrival: time | None = None
    departure: time | None = None

    platform: int | None = Field(default=None, gt=0)
    sequence: int | None = Field(default=None, gt=0)

    source: str | None = None


class GoodsForecast(BaseModel):
    """Canonical goods-train forecast information."""

    route_id: str = Field(min_length=1)
    forecast_date: date

    expected_train_count: int = Field(ge=0)
    expected_volume: float = Field(ge=0)

    source: str | None = None


class PlanningHorizon(BaseModel):
    """Date range used by the planning system."""

    start_date: date
    end_date: date

    def model_post_init(self, __context) -> None:
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")


class WeeklyPlan(BaseModel):
    """Weekly maintenance planning result."""

    week_start: date
    week_end: date
    maintenance_ids: list[str] = Field(default_factory=list)


class MonthlyPlan(BaseModel):
    """Monthly maintenance planning result."""

    month_start: date
    month_end: date
    maintenance_ids: list[str] = Field(default_factory=list)