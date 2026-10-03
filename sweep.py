import sqlite3
import requests
import time
DB = "osa.db"



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
if __name__ == "__main__":
    init_db()

    conn = sqlite3.connect(DB)

    stores = fetch_stores()
    save_stores(conn, stores)

    print("Total stores:", len(stores))
    print("Active stores:", sum(store["is_active"] for store in stores))

    conn.close()