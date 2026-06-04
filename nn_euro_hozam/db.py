#!/usr/bin/env python3

import sqlite3
from loguru import logger
from pathlib import Path

TABLE = "nn_euro_yields"
BASE_DIR = Path(__file__).resolve().parent.parent
DB_DIR = BASE_DIR / "db"
DB = DB_DIR /  f"{TABLE}.db"


class Database():
    def __init__(self, db=None, table=None, init_db=False):
        self.db = db if db else DB
        self.name = Path(self.db).name
        self.table = table if table else TABLE
        self.cursor = None
        self.conn = None
        if init_db:
            self.init_db()

    def init_db(self):
        if self.conn:
            self.conn.close()
        
        if Path(self.db).exists():
            logger.opt(colors=True).info(f"<red>Deleting</red> DB <yellow>{self.name}</yellow>")
            Path(self.db).unlink()
        
        logger.opt(colors=True).info(f"<green>Creating</green> DB <yellow>{self.name}</yellow>")
        self.conn = sqlite3.connect(self.db)
        self.cursor = self.conn.cursor()
        logger.opt(colors=True).info(f"<green>Creating</green> TABLE <cyan>{self.table}</cyan>")
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

    def insert(self, data):
        if not Path(self.db).exists():
            logger.opt(colors=True).warning(f"DB <yellow>{self.name}</yellow> doesn't exist. Skipping INSERT...")
            return

        if self.conn:
            self.conn.close()

        self.conn = sqlite3.connect(self.db)
        self.cursor = self.conn.cursor()
        if self._table_exists():
            logger.opt(colors=True).info(f"<green>Inserting</green> data into TABLE <cyan>{self.table}</cyan>")
            self.cursor.executemany(f'''
                INSERT INTO {self.table} (asset_name, date, opening_value, closing_value, period_yield)
                VALUES (:asset_name, :date, :opening_value, :closing_value, :period_yield)
            ''', data)
            self.conn.commit()
        else:
            logger.opt(colors=True).warning(f"TABLE <cyan>{self.table}</cyan> doesn't exist. Skipping INSERT...")
        self.conn.close()

    def fetchall(self):
        if not Path(self.db).exists():
            logger.opt(colors=True).warning(f"DB <yellow>{self.name}</yellow> doesn't exist. Skipping FETCHALL...")
            return
        
        if self.conn:
            self.conn.close()
        
        self.conn = sqlite3.connect(self.db)
        self.cursor = self.conn.cursor()
        if self._table_exists():
            logger.opt(colors=True).info(f"<green>Fetching</green> all data from TABLE <cyan>{self.table}</cyan>")
            self.cursor.execute(f'SELECT * FROM {self.table}')
            results = self.cursor.fetchall()
        else:
            logger.opt(colors=True).warning(f"TABLE <cyan>{self.table}</cyan> doesn't exist. Skipping FETCHALL...")
            results = []

        self.conn.close()
        return results

    def fetch_by_date(self, opening_date):
        if not Path(self.db).exists():
            logger.opt(colors=True).warning(f"DB <yellow>{self.name}</yellow> doesn't exist. Skipping FETCH...")
            return
        
        if self.conn:
            self.conn.close()
        
        self.conn = sqlite3.connect(self.db)
        self.cursor = self.conn.cursor()
        if self._table_exists():
            logger.opt(colors=True).info(f"<green>Fetching</green> data for date <yellow>{opening_date}</yellow> from TABLE <cyan>{self.table}</cyan>")
            self.cursor.execute(f'SELECT * FROM {self.table} WHERE date = ?', (opening_date,))
            results = self.cursor.fetchall()
        else:
            logger.opt(colors=True).warning(f"TABLE <cyan>{self.table}</cyan> doesn't exist. Skipping FETCH...")
            results = []

        self.conn.close()
        return results

    def dropall(self):
        if not Path(self.db).exists():
            logger.opt(colors=True).warning(f"DB <yellow>{self.name}</yellow> doesn't exist. Skipping DROP...")
            return
        
        if self.conn:
            self.conn.close()
        
        self.conn = sqlite3.connect(self.db)
        self.cursor = self.conn.cursor()
        if self._table_exists():
            logger.opt(colors=True).info(f"<red>Dropping</red> TABLE <cyan>{self.table}</cyan>")
            self.cursor.execute(f'DROP TABLE IF EXISTS {self.table}')
            self.conn.commit()
        else:
            logger.opt(colors=True).warning(f"TABLE <cyan>{self.table}</cyan> doesn't exist. Skipping DROP...")
        
        self.conn.close()

    def delete_by_date(self, opening_date):
        if not Path(self.db).exists():
            logger.opt(colors=True).warning(f"DB <yellow>{self.name}</yellow> doesn't exist. Skipping DELETE...")
            return
        
        if self.conn:
            self.conn.close()
        
        self.conn = sqlite3.connect(self.db)
        self.cursor = self.conn.cursor()
        if self._table_exists():
            logger.opt(colors=True).info(f"<red>Deleting</red> <yellow>{opening_date}</yellow> from TABLE <cyan>{self.table}</cyan>")
            self.cursor.execute(f'DELETE FROM {self.table} WHERE date = ?', (opening_date,))
            self.conn.commit()
        else:
            logger.opt(colors=True).warning(f"TABLE <cyan>{self.table}</cyan> doesn't exist. Skipping DELETE...")
        
        self.conn.close()

    def backup(self):
        db_path = Path(self.db).resolve()
        backup_path = Path(f"{self.db}.backup").resolve()

        with sqlite3.connect(db_path) as src, sqlite3.connect(backup_path) as dst:
            try:
                src.backup(dst)
                logger.opt(colors=True).info(f"DB Backup <green>successful</green> to <yellow>{backup_path}</yellow>")
            except sqlite3.Error as e:
                logger.opt(colors=True).error(f"DB Backup <red>failed</red>: {e}")
                # Optional: Delete partial backup file on failure
                if backup_path.exists():
                    backup_path.unlink()
                raise

    def _table_exists(self):
        self.cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?;",
            (self.table,)
        )
        return self.cursor.fetchone() is not None

if __name__ == '__main__':
    from logger_config import setup_logging
    setup_logging()
    from loguru import logger

    db = Database(db='test.db', table="test", init_db=True)
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
    results = db.fetch_by_date('2024-01-01')
    print(results)
    db.backup()
    
