# DataFuel Take-Home Notes

## 1. Main Decisions

### Store tracking

I track stores where `is_active` is true.

I do not use `is_serviceable` to decide whether a store should be tracked because serviceability can change. An active store is still part of the network even when it is temporarily not serviceable.

From the store discovery, there were 30 stores in total:
- Mumbai: 10 stores, 9 active
- Delhi: 10 stores, 9 active
- Bengaluru: 10 stores, 8 active

So the scraper tracks 26 active stores.

### Rate limiting and 429 errors

Inventory requests are paced through a shared `Pacer` so requests are not sent too quickly.

For HTTP 429, the scraper reads the `Retry-After` header and waits before retrying. Retries are bounded instead of continuing forever.

### 500 and 503 errors

HTTP 500 and 503 are treated as temporary errors. The request is retried a limited number of times with a short delay.

If the retries are exhausted, the store sweep is recorded as incomplete instead of blocking the complete sweep.

### Slow requests

Inventory requests use a timeout so one slow request cannot hang the entire sweep indefinitely.

### Soft ban

The portal can return HTTP 200 but still provide degraded data when requests are sent too quickly.

I check `meta.source`. A valid inventory response is expected to come from `origin`. If the source is not `origin`, I treat it as a possible soft ban.

I also check for a shortened page when another page is expected. If a response has fewer than 15 items while `next_cursor` is still present, I treat it as suspicious.

When a soft ban is detected, the current store attempt is restarted after a delay rather than saving potentially incorrect inventory.

### Partial snapshots

The API can return `partial=true`.

I save the store-sweep as `partial` with a reason, but the `/osa` calculation uses only complete store-sweeps. This prevents incomplete inventory from being interpreted as real stock-outs.

For the required sweeps, DEL-004 had a partial snapshot during the `2026-09-28T10:30:00Z` sweep. It is reported in `/osa` coverage and excluded from the OSA calculation.

### Duplicate products

The same SKU can appear on more than one inventory page.

I use `sku_id` as the product identity and deduplicate the items before saving a complete store-sweep.

During manual exploration, SKU-0033 appeared on multiple pages for MUM-001, confirming that page-level duplicates need to be handled.

### Timezones

Sweep timestamps are supplied as UTC. I normalize timestamps to UTC before storing them.

For `/osa`, the requested date represents the IST calendar day.

The required sweep mapping is:

| Sweep UTC | IST | IST date |
|---|---|---|
| 2026-09-27 04:30 | 2026-09-27 10:00 | 2026-09-27 |
| 2026-09-27 10:30 | 2026-09-27 16:00 | 2026-09-27 |
| 2026-09-27 19:00 | 2026-09-28 00:30 | 2026-09-28 |
| 2026-09-28 04:30 | 2026-09-28 10:00 | 2026-09-28 |
| 2026-09-28 10:30 | 2026-09-28 16:00 | 2026-09-28 |
| 2026-09-28 18:40 | 2026-09-29 00:10 | 2026-09-29 |

Therefore `/osa?date=2026-09-28` uses the three sweeps whose UTC timestamps correspond to 28 September in IST.

I group sweeps by their `as_of` timestamp because the complete store snapshot belongs to that sweep as a unit.

### Price types

The database stores price as `REAL`. The scraper saves the value returned by the API without using price to determine stock availability.

### Product rename

The product identity is `sku_id`, not the product name.

The `/osa` API orders observations by `observed_at` and uses the latest known name for a SKU.

### Store before launch / no products

An active store can legitimately have no products. I do not convert an empty result into out-of-stock observations.

### Re-running a sweep

The database has a unique `(store_id, as_of)` constraint.

If a complete sweep already exists, running the same sweep again does not create another sweep. If an earlier attempt was incomplete, a later successful run can replace the incomplete inventory for that same store and timestamp.

This makes the sweep idempotent.

---

## 2. Required Sweep Results

The six required sweep timestamps were completed:

| Sweep | Result |
|---|---|
| 2026-09-27T04:30:00Z | 26/26 complete |
| 2026-09-27T10:30:00Z | 26/26 complete |
| 2026-09-27T19:00:00Z | 26/26 complete after retry |
| 2026-09-28T04:30:00Z | 26/26 complete |
| 2026-09-28T10:30:00Z | 25 complete, 1 partial |
| 2026-09-28T18:40:00Z | 26/26 complete |

The partial store was DEL-004 during the `2026-09-28T10:30:00Z` sweep.

A repeat run of an existing sweep reused the existing store-sweep records instead of creating duplicate records.

---

## 3. OSA Results for 2026-09-28

The three required city reports were checked manually.

### Mumbai

- OSA: 86.06%
- Observations: 753
- Expected stores: 9
- Complete stores: 9
- Incomplete stores: 0

### Delhi

- OSA: 79.63%
- Observations: 761
- Expected stores: 9
- Complete stores: 9
- Incomplete:
  - DEL-004 — 2026-09-28T10:30:00Z — partial

### Bengaluru

- OSA: 89.57%
- Observations: 690
- Expected stores: 8
- Complete stores: 8
- Incomplete stores: 0

These percentages use total in-stock observations divided by total observations. They are not averages of store-level percentages.

---

## 4. Short Answers

### Delhi availability fell from 92% to 41%. What would I check first?

I would first check data quality before assuming that real stock availability fell.

I would check coverage, incomplete or partial store-sweeps, soft-ban indicators, the number of observations, which sweeps belong to the IST date, timestamp conversion, and whether the tracked store list changed.

Only after confirming that the data is complete and comparable would I investigate actual stock-outs.

### Dashboard says ₹4.20 lakh but store-level sum says ₹4.61 lakh. Which number would I show?

I would not choose one number just because it looks more convenient.

I would investigate the difference first, including possible double counting, inactive stores, timezone/day-boundary differences, returns or cancellations, and differences in the underlying data.

I would show the number that can be traced reliably to its source and explain the difference rather than hiding the discrepancy.

### Where would I not use an AI/LLM in this project?

I would not use an LLM to produce the actual inventory numbers or OSA calculations.

Parsing important fields, deciding availability from `in_stock`, deduplicating SKUs, mapping timestamps, and calculating OSA should be deterministic and auditable.

AI can help with development, debugging, documentation, or suggesting approaches, but the final data pipeline should make these decisions explicitly in code.

---

## 5. Optional Scaling Thoughts

For 20,000 stores every 30 minutes, I would move from a single sequential process to a job-based architecture with controlled concurrency.

I would use a queue for store-sweep jobs, workers with strict rate limiting, retry scheduling, and monitoring for coverage and soft bans.

I would also consider PostgreSQL instead of SQLite for concurrent workers, add monitoring and alerts, and design retention/partitioning because the amount of inventory observation data would grow quickly.