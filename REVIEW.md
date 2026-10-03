# Review of review_me.py

## 1. Infinite retry loop

The `fetch_inventory` function retries forever when any exception occurs.

For example, if the portal returns 404 because a store does not exist, the code keeps retrying every 0.1 seconds instead of stopping. A permanent failure can therefore hang the program indefinitely.

## 2. Wrong OSA calculation using qty

The `city_osa` function uses `qty > 0` to decide whether an item is in stock.

The API contract says `in_stock` is the authoritative availability field and `qty` is informational. Therefore an item with `in_stock = false` and `qty > 0` could incorrectly be counted as available.

## 3. City OSA is calculated as an unweighted average

The code calculates an OSA percentage for each store and then averages those percentages.

For example, if one store has 1 observation with 100% availability and another has 100 observations with 50% availability, this code gives 75%. The correct city-level calculation should use total in-stock observations divided by total observations, which gives about 50.5%.

## 4. Missing data is treated as zero

For a store with no inventory rows, the code adds `0.0` to `per_store`.

This makes missing data reduce the reported OSA even though there is no observation proving that the products were out of stock. Missing data should not be converted into an out-of-stock result.

## 5. Partial snapshots are not handled

The inventory API can return `partial=true` when a store snapshot is incomplete.

This code has no way to detect or exclude incomplete snapshots, so incomplete inventory could be included in the OSA calculation and produce a misleading result.

## 6. Mutable default argument

`fetch_inventory` uses `results=[]` as a default argument.

The same list is reused between calls to the function. For example, after fetching one store, a later call without an explicit `results` argument can contain items from the previous call.

## 7. SQL is built using string interpolation

The `save` function inserts values directly into an SQL string.

For example, a product name containing a single quote can break the SQL statement. Parameterized SQL should be used instead.

## 8. All exceptions are treated as retryable

The function catches `Exception`, so errors such as malformed data, programming errors, authentication failures, or missing resources are retried as if they were temporary network failures.

This can hide real problems and delay failure diagnosis.

## 9. The demo uses an invalid naive timestamp

The `__main__` section calls `datetime.utcnow().isoformat()`, which produces a timestamp without timezone information.

The inventory API requires a timezone-aware `as_of` value. Therefore running `python review_me.py` can fail with HTTP 400 before the review code can demonstrate its behavior.

## Fixes made

The following three areas were fixed:

1. Inventory retries are now bounded and only appropriate transient failures are retried.
2. SQL inserts use parameters instead of string interpolation.
3. City OSA uses the authoritative `in_stock` field and calculates the city percentage from total observations instead of averaging store percentages. Missing observations do not become zero.