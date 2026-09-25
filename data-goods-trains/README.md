# Mock Data

This directory contains synthetic data used for prototyping the
Goods Train Conflict Forecasting module.

The data is not real Indian Railways operational data.

## Files

### route_goods_trains.json
Contains goods train information including:
- train ID
- route ID
- train type
- direction
- operational status

### coa_train_locations.json
Represents the latest train location information obtained from COA:
- train ID
- last known location
- location type
- last observed timestamp
- data freshness

### routes.json
Contains synthetic route topology:
- route ID
- station sequence
- distance from route origin

### maintenance_blocks.json
Defines maintenance blocks:
- block ID
- affected route
- start and end stations
- maintenance start time
- maintenance end time

## Purpose

The mock data is designed to test:
- route-based goods train identification
- train location retrieval
- relevance filtering
- conflict forecasting
- stale location handling
- cancelled/completed train filtering