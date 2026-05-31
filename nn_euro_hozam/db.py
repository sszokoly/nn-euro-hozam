#!/usr/bin/env python3

import shutil
import sqlite3
from loguru import logger
from pathlib import Path

TABLE = "nn_euro_yields"
BASE_DIR = Path(__file__).resolve().parent.parent
DB_DIR = BASE_DIR / "db"
DB = DB_DIR /  f"{TABLE}.db"


class Database():
    def __init__(self, db=None, table=None):
        self.db = db if db else DB
        self.name = Path(self.db).name
        self.table = table if table else TABLE
        self.cursor = None
        self.conn = None

    def create(self):
        if not Path(self.db).exists():
            logger.opt(colors=True).warning(f"DB <yellow>{self.name}</yellow> doesn't exist.")
            return
        
        if self.conn:
            self.conn.close()
        
        self.conn = sqlite3.connect(self.db)
        self.cursor = self.conn.cursor()
        if not self._table_exists():
            logger.opt(colors=True).info(f"<green>Creating</green> <cyan>{self.table}</cyan> TABLE in <yellow>{self.name}</yellow>.")
            self.cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS {self.table} (
                    id INTEGER PRIMARY KEY,
                    asset_name TEXT,
                    date TEXT,
                    opening_value REAL,
                    closing_value REAL,
                    period_yield REAL
                )'''
            )
            self.conn.commit()
        self.conn.close()

    def drop(self):
        if not Path(self.db).exists():
            logger.opt(colors=True).warning(f"DB <yellow>{self.name}</yellow> doesn't exist.")
            return
        
        if self.conn:
            self.conn.close()
        
        self.conn = sqlite3.connect(self.db)
        self.cursor = self.conn.cursor()
        if self._table_exists():
            logger.opt(colors=True).info(f"<red>Dropping</red> <cyan>{self.table}</cyan> TABLE from <yellow>{self.name}</yellow>.")
            self.cursor.execute(f'DROP TABLE IF EXISTS {self.table}')
            self.conn.commit()
        
        self.conn.close()

    def insert(self, data):
        if not Path(self.db).exists():
            logger.opt(colors=True).warning(f"Database <yellow>{self.name}</yellow> does not exist.")
            return

        if self.conn:
            self.conn.close()

        self.conn = sqlite3.connect(self.db)
        self.cursor = self.conn.cursor()
        logger.opt(colors=True).info(f"<yellow>Inserting</yellow> data into <cyan>{self.table}</cyan> <green>TABLE in</green> <yellow>{self.name}</yellow>.")
        self.cursor.executemany(f'''
            INSERT INTO {self.table} (asset_name, date, opening_value, closing_value, period_yield)
            VALUES (:asset_name, :date, :opening_value, :closing_value, :period_yield)
        ''', data)
        self.conn.commit()
        self.conn.close()

    def fetchall(self):
        if not Path(self.db).exists():
            logger.opt(colors=True).warning(f"Database <yellow>{self.name}</yellow> does not exist. Skipping query.")
            return
        
        if self.conn:
            self.conn.close()
        
        self.conn = sqlite3.connect(self.db)
        self.cursor = self.conn.cursor()
        if self._table_exists():
            logger.opt(colors=True).info(f"<yellow>Querying</yellow> data from <cyan>{self.table}</cyan> <yellow>TABLE in</yellow> <yellow>{self.name}</yellow>")
            self.cursor.execute(f'SELECT * FROM {self.table}')
            results = self.cursor.fetchall()
        else:
            logger.opt(colors=True).warning(f"Table <cyan>{self.table}</cyan> does not exist in <yellow>{self.name}</yellow>.")
            results = []

        self.conn.close()
        return results

    def backup(self):
        logger.opt(colors=True).info(f"Creating backup copy of <yellow>{self.db}</yellow>.")
        shutil.copy2(self.db, f"{self.db}.backup")

    def _table_exists(self):
        self.cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?;",
            (self.table,)
        )
        return self.cursor.fetchone() is not None

if __name__ == '__main__':
    db = Database(db=DB, table="test")
    db.create()
    data = [
        {
            'asset_name': 'Asset A',
            'date': '2024-01-01',
            'opening_value': 100.0,
            'closing_value': 105.0,
            'period_yield': 5.0},
        {
            'asset_name': 'Asset B',
            'date': '2024-01-01',
            'opening_value': 200.0,
            'closing_value': 210.0,
            'period_yield': 5.0
        },
    ]
    db.insert(data)
    results = db.fetchall()
    print(results)
    db.drop()
