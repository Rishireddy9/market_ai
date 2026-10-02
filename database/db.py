"""SQLite persistence for paper-order audit records."""

import json
import sqlite3
from pathlib import Path
from typing import Any


class TradeDatabase:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS paper_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    entry_price REAL NOT NULL,
                    stop_price REAL NOT NULL,
                    target_price REAL NOT NULL,
                    status TEXT NOT NULL,
                    details_json TEXT NOT NULL
                )
                """
            )

    def record_order(self, order: dict[str, Any]) -> int:
        self.initialize()
        with sqlite3.connect(self.database_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO paper_orders (
                    created_at, symbol, direction, quantity, entry_price,
                    stop_price, target_price, status, details_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order["created_at"],
                    order["symbol"],
                    order["direction"],
                    order["quantity"],
                    order["entry_price"],
                    order["stop_price"],
                    order["target_price"],
                    order["status"],
                    json.dumps(order, allow_nan=False),
                ),
            )
            return int(cursor.lastrowid)
