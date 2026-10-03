# AI Usage Log

## How AI was used

AI assistance was used throughout the take-home assignment for development support.

The main uses were:

- Understanding the assignment requirements and API contract.
- Planning the SQLite database schema.
- Designing the inventory sweep flow.
- Reviewing retry, timeout, rate-limit, and soft-ban handling.
- Debugging errors encountered while running the mock portal.
- Reviewing the provided `review_me.py` file.
- Suggesting and explaining targeted fixes.
- Creating pytest tests for the API and timestamp normalization.
- Reviewing the `/osa` calculation logic.
- Helping prepare project documentation.

## Verification

I did not treat generated code or explanations as automatically correct.

Important behavior was verified by running the project against the provided mock portal and checking the actual responses.

Examples of verification performed:

- Manually checked store pagination and active/inactive store flags.
- Checked inventory pagination and duplicate SKUs.
- Ran the required sweep timestamps.
- Verified retry behavior after transient HTTP errors.
- Verified handling of partial snapshots.
- Verified sweep idempotency by rerunning an existing timestamp.
- Tested `/osa` for Mumbai, Delhi, and Bengaluru.
- Tested invalid city handling.
- Tested no-data behavior.
- Tested missing-date behavior.
- Ran the pytest suite.

## Human understanding

The final implementation decisions were reviewed and understood before being kept in the project.

In particular, I verified why:

- `in_stock` is used instead of `qty` for OSA.
- Partial store-sweeps are excluded from OSA.
- Missing data is not converted into 0%.
- City OSA is calculated from total observations instead of averaging store percentages.
- `sku_id` is used as product identity.
- Sweep records use `(store_id, as_of)` for idempotency.
- Retry behavior is bounded.
- `Retry-After` is respected for HTTP 429.
- `meta.source` is checked for possible soft-ban/degraded responses.

The provided `mock_portal.py` and `API.md` were treated as the source of truth for the portal behavior and API contract.