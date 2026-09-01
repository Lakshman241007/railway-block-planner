from .data_loader import load_json
from .models import MaintenanceBlock
from .routes_goods import get_goods_trains_for_route
from .coa import get_train_locations
from .filterer import filter_relevant_trains
from .forecaster import forecast_train
from datetime import datetime


def run_forecast():

    # -------------------------
    # Load data
    # -------------------------

    goods_data = load_json("route_goods_trains.json")
    coa_data = load_json("coa_train_locations.json")
    routes_data = load_json("routes.json")
    blocks_data = load_json("maintenance_blocks.json")

    # -------------------------
    # Select maintenance block
    # -------------------------

    block_data = blocks_data[0]

    block = MaintenanceBlock(
        block_id=block_data["block_id"],
        route_id=block_data["route_id"],
        start_station=block_data["start_station"],
        end_station=block_data["end_station"],
        block_start=datetime.fromisoformat(
            block_data["block_start"]
        ),
        block_end=datetime.fromisoformat(
            block_data["block_end"]
        )
    )

    # -------------------------
    # ROUTE GOODS TRAINS
    # -------------------------

    trains = get_goods_trains_for_route(
        block.route_id,
        goods_data
    )

    # -------------------------
    # COA
    # -------------------------

    train_ids = [train.train_id for train in trains]

    locations = get_train_locations(
        train_ids,
        coa_data
    )

    # -------------------------
    # FILTERER
    # -------------------------

    relevant_trains = filter_relevant_trains(
        trains,
        locations,
        routes_data,
        block
    )

    # -------------------------
    # FORECAST
    # -------------------------

    route = next(
        r for r in routes_data
        if r["route_id"] == block.route_id
    )

    results = []

    for train, location in relevant_trains:

        result = forecast_train(
            train,
            location,
            route,
            block
        )

        if result:
            results.append(result)

    return results


if __name__ == "__main__":
    results = run_forecast()

    print("\n===== GOODS TRAIN CONFLICT FORECAST =====\n")

    for result in results:

        print(f"Train: {result['train_id']}")
        print(
            f"Last Location: "
            f"{result['last_known_location']}"
        )
        print(
            f"Predicted Entry: "
            f"{result['predicted_entry']}"
        )
        print(
            f"Predicted Exit: "
            f"{result['predicted_exit']}"
        )
        print(
            f"Result: {result['result']}"
        )
        print(
            f"Confidence: "
            f"{result['confidence']}"
        )
        print(
            f"Reason: "
            f"{result['reason']}"
        )
        print("-" * 50)