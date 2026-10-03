from datetime import datetime, timezone
import sqlite3
import requests
import time
DB = "osa.db"
class SoftBanned(Exception):
    pass
class Pacer:
    def __init__(self, per_second=2):
        self.gap = 1 / per_second
        self.last = 0

    def wait(self):
        wait_time = self.last + self.gap - time.monotonic()

        if wait_time > 0:
            time.sleep(wait_time)

        self.last = time.monotonic()


def init_db():
    conn = sqlite3.connect(DB)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS stores (
            store_id TEXT PRIMARY KEY,
            city TEXT NOT NULL,
            name TEXT NOT NULL,
            is_active INTEGER NOT NULL,
            is_serviceable INTEGER NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS sweeps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store_id TEXT NOT NULL,
            as_of TEXT NOT NULL,
            status TEXT NOT NULL,
            partial INTEGER NOT NULL,
            observed_at TEXT,
            created_at TEXT NOT NULL,
            reason TEXT,
            UNIQUE(store_id, as_of),
            FOREIGN KEY(store_id) REFERENCES stores(store_id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            sweep_id INTEGER NOT NULL,
            sku_id TEXT NOT NULL,
            name TEXT NOT NULL,
            in_stock INTEGER NOT NULL,
            qty INTEGER,
            price REAL,
            observed_at TEXT NOT NULL,
            PRIMARY KEY(sweep_id, sku_id),
            FOREIGN KEY(sweep_id) REFERENCES sweeps(id)
        )
    """)
    columns = conn.execute("PRAGMA table_info(sweeps)").fetchall()

    if not any(column[1] == "reason" for column in columns):
        conn.execute("ALTER TABLE sweeps ADD COLUMN reason TEXT")
    conn.commit()
    conn.close()



PORTAL = "http://127.0.0.1:8765"
HEADERS = {"X-Api-Key": "dfhire-2026"}


def fetch_stores():
    stores = []
    page = 1
    attempts = 3

    while page is not None:
        for attempt in range(attempts):
            try:
                response = requests.get(
                    f"{PORTAL}/v1/stores",
                    params={"page": page},
                    headers=HEADERS,
                    timeout=10
                )

                if response.status_code in (500, 503):
                    if attempt == attempts - 1:
                        response.raise_for_status()
                    time.sleep(1)
                    continue

                response.raise_for_status()
                break

            except requests.RequestException:
                if attempt == attempts - 1:
                    raise
                time.sleep(1)

        body = response.json()
        stores.extend(body["stores"])
        page = body["next_page"]

    return stores


def save_stores(conn, stores):
    for store in stores:
        conn.execute(
            """
            INSERT INTO stores
            (store_id, city, name, is_active, is_serviceable)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(store_id) DO UPDATE SET
                city = excluded.city,
                name = excluded.name,
                is_active = excluded.is_active,
                is_serviceable = excluded.is_serviceable
            """,
            (
                store["store_id"],
                store["city"],
                store["name"],
                int(store["is_active"]),
                int(store["is_serviceable"])
            )
        )

    conn.commit()
PORTAL = "http://127.0.0.1:8765"
HEADERS = {"X-Api-Key": "dfhire-2026"}

def normalize_timestamp(value):
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"

    dt = datetime.fromisoformat(value)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    dt = dt.astimezone(timezone.utc)

    return dt.isoformat().replace("+00:00", "Z")

def fetch_inventory(store_id, as_of, pacer):
    for soft_ban_round in range(3):
        items = []
        cursor = "0"
        partial = False
        observed_at = None

        try:
            while cursor is not None:
                for attempt in range(3):
                    try:
                        pacer.wait()

                        response = requests.get(
                            f"{PORTAL}/v1/stores/{store_id}/inventory",
                            params={
                                "as_of": as_of,
                                "cursor": cursor
                            },
                            headers=HEADERS,
                            timeout=15
                        )

                        if response.status_code == 429:
                            if attempt == 2:
                                response.raise_for_status()

                            retry_after = int(
                                response.headers.get("Retry-After", "2")
                            )
                            time.sleep(retry_after)
                            continue

                        if response.status_code in (500, 503):
                            if attempt == 2:
                                response.raise_for_status()
                            time.sleep(1)
                            continue

                        response.raise_for_status()
                        break

                    except requests.Timeout:
                        if attempt == 2:
                            raise
                        time.sleep(1)

                    except requests.RequestException:
                        raise

                body = response.json()
                source = body.get("meta", {}).get("source")

                if source != "origin":
                    raise SoftBanned()

                page_items = body["items"]
                next_cursor = body["next_cursor"]

                if next_cursor is not None and len(page_items) < 15:
                    raise SoftBanned()

                items.extend(page_items)

                if body["partial"]:
                    partial = True

                if observed_at is None and page_items:
                    observed_at = page_items[0]["observed_at"]

                cursor = next_cursor

            unique_items = {}

            for item in items:
                unique_items[item["sku_id"]] = item

            duplicates = len(items) - len(unique_items)

            return list(unique_items.values()), partial, observed_at, duplicates

        except SoftBanned:
            print(
                f"  Soft ban detected for {store_id}. "
                f"Waiting 30 seconds before restart "
                f"({soft_ban_round + 1}/3)"
            )
            time.sleep(30)

    raise SoftBanned()  

def save_sweep(conn, store_id, as_of, items, partial, observed_at, reason=None):
    existing = conn.execute(
        "SELECT id, status FROM sweeps WHERE store_id = ? AND as_of = ?",
        (store_id, as_of)
    ).fetchone()

    if existing:
        sweep_id, status = existing

        if status == "complete":
            return sweep_id

        conn.execute(
            """
            UPDATE sweeps
            SET status = ?,
                partial = ?,
                observed_at = ?,
                reason = ?
            WHERE id = ?
            """,
            (
                "complete" if not partial else "partial",
                int(partial),
                observed_at,
                reason,
                sweep_id
            )
        )

        conn.execute(
            "DELETE FROM inventory WHERE sweep_id = ?",
            (sweep_id,)
        )

    else:
        conn.execute(
            """
            INSERT INTO sweeps
            (store_id, as_of, status, partial, observed_at, created_at, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                store_id,
                as_of,
                "complete" if not partial else "partial",
                int(partial),
                observed_at,
                datetime.now().isoformat(),
                reason
            )
        )

        sweep_id = conn.execute(
            "SELECT id FROM sweeps WHERE store_id = ? AND as_of = ?",
            (store_id, as_of)
        ).fetchone()[0]

    for item in items:
        conn.execute(
            """
            INSERT INTO inventory
            (sweep_id, sku_id, name, in_stock, qty, price, observed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sweep_id,
                item["sku_id"],
                item["name"],
                int(item["in_stock"]),
                item["qty"],
                item["price"],
                normalize_timestamp(item["observed_at"])
            )
        )

    conn.commit()

    return sweep_id

def run_sweep(as_of):
    conn = sqlite3.connect(DB)

    stores = conn.execute(
        "SELECT store_id FROM stores WHERE is_active = 1 ORDER BY store_id"
    ).fetchall()

    total = len(stores)
    completed = 0
    failed = 0

    pacer = Pacer()

    print("Starting sweep:", as_of)
    print("Active stores:", total)

    for index, (store_id,) in enumerate(stores, 1):
        print(f"[{index}/{total}] {store_id}")

        try:


            items, partial, observed_at, duplicates = fetch_inventory(
                store_id,
                as_of,
                pacer
            )
            if partial:
                save_sweep(
                    conn,
                    store_id,
                    as_of,
                    items,
                    True,
                    observed_at,
                    "partial"
                )

                failed += 1
                print("  Incomplete snapshot - saved as partial")
                continue

            sweep_id = save_sweep(
                conn,
                store_id,
                as_of,
                items,
                partial,
                observed_at
            )

            completed += 1

            print(
                f"  Saved sweep {sweep_id} | "
                f"SKUs: {len(items)} | "
                f"duplicates: {duplicates}"
            )

        except SoftBanned:
            failed += 1

            save_sweep(
                conn,
                store_id,
                as_of,
                [],
                True,
                None,
                "soft_ban"
            )

            print("  Failed: soft_ban")

        except requests.Timeout:
            failed += 1

            save_sweep(
                conn,
                store_id,
                as_of,
                [],
                True,
                None,
                "timeout"
            )

            print("  Failed: timeout")

        except requests.RequestException as e:
            failed += 1

            save_sweep(
                conn,
                store_id,
                as_of,
                [],
                True,
                None,
                "http_error"
            )

            print(f"  Failed: {e}")

        except Exception as e:
            failed += 1

            save_sweep(
                conn,
                store_id,
                as_of,
                [],
                True,
                None,
                "error"
            )

            print(f"  Failed: {e}")

    conn.close()

    print()
    print("Sweep finished")
    print("Expected:", total)
    print("Completed:", completed)
    print("Failed:", failed)



if __name__ == "__main__":
    init_db()

    stores = fetch_stores()

    conn = sqlite3.connect(DB)
    save_stores(conn, stores)
    conn.close()

    run_sweep("2026-09-28T18:40:00Z")