from .models import GoodsTrain


def get_goods_trains_for_route(route_id, data):
    trains = []

    for item in data:
        train = GoodsTrain(**item)

        if train.route_id == route_id and train.train_type == "GOODS":
            trains.append(train)

    return trains