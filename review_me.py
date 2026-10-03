"""
review_me.py: written by an AI coding assistant in one shot and merged without review.

Your job (write it in REVIEW.md):
  1. Find at least 5 real problems, most serious first. For each, say what goes wrong,
     with a concrete example (not just "bad practice").
  2. Fix the 2-3 most serious ones in this file.
Don't rewrite it from scratch. Reviewing is the skill being tested.
"""
import sqlite3
import time
from datetime import date, datetime, timedelta

import requests

PORTAL = "http://127.0.0.1:8765"
HEADERS = {"X-Api-Key": "dfhire-2026"}


def fetch_inventory(store_id, as_of, cursor="0", results=None):
    """Fetch every inventory page for a store."""
    if results is None:
        results = []

    for attempt in range(3):
        try:
            r = requests.get(
                f"{PORTAL}/v1/stores/{store_id}/inventory",
                params={"as_of": as_of, "cursor": cursor},
                headers=HEADERS,
                timeout=15,
            )

            if r.status_code == 429:
                if attempt == 2:
                    r.raise_for_status()

                retry_after = int(r.headers.get("Retry-After", "2"))
                time.sleep(retry_after)
                continue

            if r.status_code in (500, 503):
                if attempt == 2:
                    r.raise_for_status()

                time.sleep(1)
                continue

            r.raise_for_status()
            break

        except requests.Timeout:
            if attempt == 2:
                raise
            time.sleep(1)

    body = r.json()
    results.extend(body["items"])

    if body["next_cursor"]:
        return fetch_inventory(
            store_id,
            as_of,
            body["next_cursor"],
            results
        )

    return results


def save(conn, store_id, items):
    for it in items:
        conn.execute(
            """
            INSERT INTO inventory
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                store_id,
                it["sku_id"],
                it["name"],
                int(it["in_stock"]),
                it["qty"],
                it["observed_at"],
            ),
        )

    conn.commit()


def city_osa(conn, city, day=None):
    """On-shelf availability for a city on a day."""
    day = day or (date.today() - timedelta(days=1)).isoformat()

    stores = [
        r[0]
        for r in conn.execute(
            "SELECT store_id FROM stores WHERE city = ?",
            (city,),
        )
    ]

    total_observations = 0
    total_in_stock = 0

    for store_id in stores:
        rows = conn.execute(
            """
            SELECT in_stock
            FROM inventory
            WHERE store_id = ?
            AND substr(observed_at, 1, 10) = ?
            """,
            (store_id, day),
        ).fetchall()

        for (in_stock,) in rows:
            total_observations += 1
            if in_stock:
                total_in_stock += 1

    if total_observations == 0:
        return None

    return round(
        100 * total_in_stock / total_observations,
        2,
    )


if __name__ == "__main__":
    conn = sqlite3.connect("osa.db")
    conn.execute("CREATE TABLE IF NOT EXISTS stores (store_id TEXT, city TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS inventory (store_id TEXT, sku_id TEXT, name TEXT, "
                 "in_stock INT, qty INT, observed_at TEXT)")
    for sid in ["MUM-001", "MUM-002"]:
        save(conn, sid, fetch_inventory(sid, datetime.utcnow().isoformat()))
    print(city_osa(conn, "Mumbai"))
