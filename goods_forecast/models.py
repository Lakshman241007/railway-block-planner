from dataclasses import dataclass
from datetime import datetime


@dataclass
class GoodsTrain:
    train_id: str
    route_id: str
    train_type: str
    direction: str
    status: str


@dataclass
class TrainLocation:
    train_id: str
    last_known_location: str
    location_type: str
    last_seen_time: datetime
    data_age_minutes: int


@dataclass
class MaintenanceBlock:
    block_id: str
    route_id: str
    start_station: str
    end_station: str
    block_start: datetime
    block_end: datetime


@dataclass
class ForecastResult:
    train_id: str
    last_known_location: str
    predicted_entry: datetime | None
    predicted_exit: datetime | None
    conflict: bool
    reason: str
    confidence: str