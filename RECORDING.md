# Recording

## Screen Recording

The complete development session was screen recorded as required by the assignment.

Recording link:

https://drive.google.com/file/d/1OKuSgNre-LkmPa474I9Mn-fpacfqENqq/view?usp=sharing

## Technical Walkthrough

A short technical walkthrough will cover:

1. Assignment requirements and API contract.
2. Store discovery and active-store tracking.
3. SQLite schema and relationships.
4. Inventory pagination and SKU deduplication.
5. Rate limiting, retries, timeouts, and 429 handling.
6. Soft-ban detection using `meta.source`.
7. Partial snapshot handling.
8. Sweep idempotency.
9. IST date handling for `/osa`.
10. OSA calculation using `in_stock`.
11. API validation and no-data behavior.
12. Tests and review of `review_me.py`.

## Important Results

Required sweep timestamps:

- `2026-09-27T04:30:00Z`
- `2026-09-27T10:30:00Z`
- `2026-09-27T19:00:00Z`
- `2026-09-28T04:30:00Z`
- `2026-09-28T10:30:00Z`
- `2026-09-28T18:40:00Z`

The required sweeps were completed, with one partial store snapshot for DEL-004 at `2026-09-28T10:30:00Z`.

The partial snapshot is excluded from OSA calculations and reported in coverage.

## Final API Verification

The `/osa` endpoint was tested for:

- Mumbai
- Delhi
- Bengaluru
- Invalid city
- No-data date
- Missing date
- Invalid date format

The pytest suite contains five tests and all five pass.