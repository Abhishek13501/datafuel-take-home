import sqlite3
from datetime import datetime, date, timedelta, timezone
from fastapi import FastAPI, HTTPException

DB = "osa.db"

CITIES = {"Mumbai", "Delhi", "Bengaluru"}

IST = timezone(timedelta(hours=5, minutes=30))

app = FastAPI()


def get_connection():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def yesterday_in_ist():
    now = datetime.now(IST)
    return (now.date() - timedelta(days=1)).isoformat()


def validate_date(value):
    try:
        date.fromisoformat(value)
    except ValueError:
        raise HTTPException(400, "date must be YYYY-MM-DD")


def get_sweep_date(as_of):
    value = as_of

    if value.endswith("Z"):
        value = value[:-1] + "+00:00"

    dt = datetime.fromisoformat(value)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(IST).date().isoformat()


def build_report(conn, city, day):
    stores = conn.execute(
        """
        SELECT store_id
        FROM stores
        WHERE city = ? AND is_active = 1
        ORDER BY store_id
        """,
        (city,)
    ).fetchall()

    expected_stores = [row["store_id"] for row in stores]

    sweeps = conn.execute(
        """
        SELECT id, store_id, as_of, status, reason
        FROM sweeps
        WHERE store_id IN (
            SELECT store_id
            FROM stores
            WHERE city = ? AND is_active = 1
        )
        """,
        (city,)
    ).fetchall()

    day_sweeps = []

    for sweep in sweeps:
        if get_sweep_date(sweep["as_of"]) == day:
            day_sweeps.append(sweep)

    complete_sweeps = [
        sweep for sweep in day_sweeps
        if sweep["status"] == "complete"
    ]

    incomplete = []

    for sweep in day_sweeps:
        if sweep["status"] != "complete":
            incomplete.append({
                "store_id": sweep["store_id"],
                "sweep": sweep["as_of"],
                "reason": sweep["reason"] or sweep["status"]
            })

    complete_stores = {
        sweep["store_id"]
        for sweep in complete_sweeps
    }

    if not day_sweeps:
        return {
            "city": city,
            "date": day,
            "status": "no_data",
            "osa_pct": None,
            "observations": 0,
            "coverage": {
                "stores_expected": len(expected_stores),
                "stores_complete": 0,
                "incomplete": []
            },
            "skus": []
        }

    if not complete_sweeps:
        return {
            "city": city,
            "date": day,
            "status": "no_data",
            "osa_pct": None,
            "observations": 0,
            "coverage": {
                "stores_expected": len(expected_stores),
                "stores_complete": 0,
                "incomplete": incomplete
            },
            "skus": []
        }

    ids = [sweep["id"] for sweep in complete_sweeps]
    placeholders = ",".join("?" for _ in ids)

    rows = conn.execute(
        f"""
        SELECT
            i.sku_id,
            i.name,
            i.in_stock,
            i.observed_at
        FROM inventory i
        WHERE i.sweep_id IN ({placeholders})
        ORDER BY i.observed_at DESC
        """,
        ids
    ).fetchall()

    sku_data = {}

    for row in rows:
        sku_id = row["sku_id"]

        if sku_id not in sku_data:
            sku_data[sku_id] = {
                "sku_id": sku_id,
                "name": row["name"],
                "observations": 0,
                "in_stock": 0
            }

        sku_data[sku_id]["observations"] += 1

        if row["in_stock"] == 1:
            sku_data[sku_id]["in_stock"] += 1

    skus = []

    total_observations = 0
    total_in_stock = 0

    for sku in sku_data.values():
        observations = sku["observations"]
        in_stock = sku["in_stock"]

        sku["osa_pct"] = round(
            in_stock / observations * 100,
            2
        )

        total_observations += observations
        total_in_stock += in_stock

        skus.append(sku)

    osa_pct = None

    if total_observations > 0:
        osa_pct = round(
            total_in_stock / total_observations * 100,
            2
        )

    status = "ok"

    if incomplete:
        status = "partial"

    return {
        "city": city,
        "date": day,
        "status": status,
        "osa_pct": osa_pct,
        "observations": total_observations,
        "coverage": {
            "stores_expected": len(expected_stores),
            "stores_complete": len(complete_stores),
            "incomplete": incomplete
        },
        "skus": skus
    }


@app.get("/osa")
def osa(city: str, date: str | None = None):
    if city not in CITIES:
        raise HTTPException(
            400,
            f"city must be one of {sorted(CITIES)}"
        )

    day = date or yesterday_in_ist()

    validate_date(day)

    conn = get_connection()

    try:
        return build_report(conn, city, day)
    finally:
        conn.close()