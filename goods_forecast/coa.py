from datetime import datetime
from .models import TrainLocation


def get_train_locations(train_ids, data):
    locations = {}

    for item in data:
        location = TrainLocation(
            train_id=item["train_id"],
            last_known_location=item["last_known_location"],
            location_type=item["location_type"],
            last_seen_time=datetime.fromisoformat(item["last_seen_time"]),
            data_age_minutes=item["data_age_minutes"]
        )

        if location.train_id in train_ids:
            locations[location.train_id] = location

    return locations