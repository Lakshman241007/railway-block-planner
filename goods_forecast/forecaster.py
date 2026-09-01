from datetime import timedelta


# Prototype-only baseline.
# This is NOT a live train-speed input.
PROTOTYPE_SPEED_KMPH = 40

# COA data older than this is considered unreliable.
STALE_DATA_MINUTES = 45


def get_station(route, station_id):
    """Return station information from a route."""
    for station in route["stations"]:
        if station["station_id"] == station_id:
            return station

    return None


def forecast_train(train, location, route, block):
    """
    Estimate whether a train may conflict with a maintenance block.

    Returns:
        dict containing forecast information and one of:
        CONFLICT / SAFE / UNCERTAIN
    """

    # --------------------------------------------------
    # 1. Missing COA information
    # --------------------------------------------------

    if location is None:
        return {
            "train_id": train.train_id,
            "last_known_location": None,
            "predicted_entry": None,
            "predicted_exit": None,
            "result": "UNCERTAIN",
            "conflict": False,
            "reason": "No COA location available",
            "confidence": "LOW"
        }

    # --------------------------------------------------
    # 2. Check whether COA data is stale
    # --------------------------------------------------

    data_is_stale = location.data_age_minutes > STALE_DATA_MINUTES

    # --------------------------------------------------
    # 3. Find relevant stations
    # --------------------------------------------------

    current_station = get_station(
        route,
        location.last_known_location
    )

    block_start_station = get_station(
        route,
        block.start_station
    )

    block_end_station = get_station(
        route,
        block.end_station
    )

    if current_station is None:
        return {
            "train_id": train.train_id,
            "last_known_location": location.last_known_location,
            "predicted_entry": None,
            "predicted_exit": None,
            "result": "UNCERTAIN",
            "conflict": False,
            "reason": "Last known station is not present in route data",
            "confidence": "LOW"
        }

    if block_start_station is None or block_end_station is None:
        return {
            "train_id": train.train_id,
            "last_known_location": location.last_known_location,
            "predicted_entry": None,
            "predicted_exit": None,
            "result": "UNCERTAIN",
            "conflict": False,
            "reason": "Maintenance block station data is invalid",
            "confidence": "LOW"
        }

    # --------------------------------------------------
    # 4. Determine movement direction
    # --------------------------------------------------

    current_distance = current_station["distance_from_origin_km"]
    block_start_distance = block_start_station[
        "distance_from_origin_km"
    ]
    block_end_distance = block_end_station[
        "distance_from_origin_km"
    ]

    # For UP trains, block starts at the lower distance.
    if train.direction == "UP":

        if current_distance >= block_end_distance:
            return {
                "train_id": train.train_id,
                "last_known_location": location.last_known_location,
                "predicted_entry": None,
                "predicted_exit": None,
                "result": "SAFE",
                "conflict": False,
                "reason": "Train has already passed the maintenance block",
                "confidence": "HIGH"
            }

        distance_to_block = max(
            0,
            block_start_distance - current_distance
        )

    # For DOWN trains, block starts at the higher distance.
    elif train.direction == "DOWN":

        if current_distance <= block_start_distance:
            return {
                "train_id": train.train_id,
                "last_known_location": location.last_known_location,
                "predicted_entry": None,
                "predicted_exit": None,
                "result": "SAFE",
                "conflict": False,
                "reason": "Train has already passed the maintenance block",
                "confidence": "HIGH"
            }

        distance_to_block = max(
            0,
            current_distance - block_end_distance
        )

    else:
        return {
            "train_id": train.train_id,
            "last_known_location": location.last_known_location,
            "predicted_entry": None,
            "predicted_exit": None,
            "result": "UNCERTAIN",
            "conflict": False,
            "reason": "Unknown train direction",
            "confidence": "LOW"
        }

    # --------------------------------------------------
    # 5. Estimate entry time
    # --------------------------------------------------

    travel_minutes = (
        distance_to_block / PROTOTYPE_SPEED_KMPH
    ) * 60

    predicted_entry = (
        location.last_seen_time
        + timedelta(minutes=travel_minutes)
    )

    # --------------------------------------------------
    # 6. Estimate exit time
    # --------------------------------------------------

    block_distance = abs(
        block_end_distance - block_start_distance
    )

    block_travel_minutes = (
        block_distance / PROTOTYPE_SPEED_KMPH
    ) * 60

    predicted_exit = (
        predicted_entry
        + timedelta(minutes=block_travel_minutes)
    )

    # --------------------------------------------------
    # 7. Check overlap with maintenance block
    # --------------------------------------------------

    conflict = (
        predicted_entry < block.block_end
        and predicted_exit > block.block_start
    )

    # --------------------------------------------------
    # 8. Handle stale data
    # --------------------------------------------------

    if data_is_stale:
        return {
            "train_id": train.train_id,
            "last_known_location": location.last_known_location,
            "predicted_entry": predicted_entry,
            "predicted_exit": predicted_exit,
            "result": "UNCERTAIN",
            "conflict": conflict,
            "reason": (
                "COA location is stale; "
                "forecast requires human verification"
            ),
            "confidence": "LOW"
        }

    # --------------------------------------------------
    # 9. Normal result
    # --------------------------------------------------

    if conflict:
        result = "CONFLICT"
        reason = "Predicted movement overlaps maintenance block"
    else:
        result = "SAFE"
        reason = "Predicted movement does not overlap maintenance block"

    if location.data_age_minutes <= 15:
        confidence = "HIGH"
    else:
        confidence = "MEDIUM"

    return {
        "train_id": train.train_id,
        "last_known_location": location.last_known_location,
        "predicted_entry": predicted_entry,
        "predicted_exit": predicted_exit,
        "result": result,
        "conflict": conflict,
        "reason": reason,
        "confidence": confidence
    }