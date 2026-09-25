def filter_relevant_trains(trains, locations, route_data, block):
    relevant = []

    route = next(
        (r for r in route_data if r["route_id"] == block.route_id),
        None
    )

    if route is None:
        return relevant

    station_order = {
        station["station_id"]: station["sequence"]
        for station in route["stations"]
    }

    block_start_seq = station_order[block.start_station]
    block_end_seq = station_order[block.end_station]

    for train in trains:

        # Ignore completed/cancelled trains
        if train.status != "RUNNING":
            continue

        location = locations.get(train.train_id)

        if location is None:
            continue

        current_seq = station_order.get(location.last_known_location)

        if current_seq is None:
            continue

        # UP direction
        if train.direction == "UP":
            if current_seq <= block_end_seq:
                relevant.append((train, location))

        # DOWN direction
        elif train.direction == "DOWN":
            if current_seq >= block_start_seq:
                relevant.append((train, location))

    return relevant