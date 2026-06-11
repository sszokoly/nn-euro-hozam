#!/usr/bin/env python3

import json
import sqlite3
from loguru import logger
from pathlib import Path
from config import (
    DB_FILE,
    DB_FILE_BKP,
    DB_NN_TABLE_NAME,
    DB_ST_TABLE_NAME,
    ST_TABLE_SCHEMA,
    NN_TABLE_SCHEMA,
    TMP_DIR
)


class Database():
    def __init__(self,
        db_file=None,
        nn_table=None,
        st_table=None,
        init_db=False
    ):
        self.db_file = db_file if db_file else DB_FILE
        self.nn_table = nn_table if nn_table else DB_NN_TABLE_NAME
        self.st_table = st_table if st_table else DB_ST_TABLE_NAME 
        if init_db:
            self.init_db()

    def init_db(self):
        if Path(self.db_file).exists():
            logger.opt(colors=True).info(f"<red>Deleting</red> Database file")
            Path(self.db_file).unlink()

        logger.opt(colors=True).info(f"<green>Creating</green> Database file")
        with sqlite3.connect(self.db_file) as conn:
            try:
                cursor = conn.cursor()

                for table in "nn", "st":
                    table, table_schema = self._table_name_schema(table)
                    columns_def = self._create_columns_def(table_schema)
                    create_table_sql = f'''
                        CREATE TABLE IF NOT EXISTS {table} ({', '.join(columns_def)})
                    '''
                    logger.opt(colors=True).info(f"<green>Creating</green> TABLE <cyan>{table}</cyan>")
                    cursor.execute(create_table_sql)
            except Exception as e:
                logger.opt(colors=True).exception(f"<red>Exception</red> {e}")

    def insert(self, data, table_name=None):
        table, _ = self._table_name_schema(table_name)
                
        if not Path(self.db_file).exists():
            logger.opt(colors=True).warning(f"Database file doesn't exist")
            return

        with sqlite3.connect(self.db_file) as conn:
            try:
                cursor = conn.cursor()

                if self._table_exists(cursor, table_name):
                    logger.opt(colors=True).debug(f"<green>Inserting</green> data into <cyan>{table}</cyan>")
                    column_fields = ", ".join(data[0].keys())
                    value_fields = ", ".join(f":{x}" for x in data[0].keys())
                    cursor.executemany(f'''
                        INSERT INTO {table} ({column_fields})
                        VALUES ({value_fields})
                    ''', data)
                else:
                    logger.opt(colors=True).warning(f"TABLE <cyan>{table}</cyan> doesn't exist.")

            except Exception as e:
                logger.opt(colors=True).exception(f"<red>Exception</red> {e}")

    def fetchall(self, table_name=None):
        table, _ = self._table_name_schema(table_name)

        if not Path(self.db_file).exists():
            logger.opt(colors=True).warning(f"Database file doesn't exist")
            return

        with sqlite3.connect(self.db_file) as conn:
            try:
                cursor = conn.cursor()

                if self._table_exists(cursor, table_name):
                    logger.opt(colors=True).info(f"<green>Fetching</green> ALL data from TABLE <cyan>{table}</cyan>")
                    cursor.execute(f'SELECT * FROM {table}')
                    results = cursor.fetchall()
                else:
                    logger.opt(colors=True).warning(f"TABLE <cyan>{table}</cyan> doesn't exist")
                    results = []

            except Exception as e:
                logger.opt(colors=True).exception(f"<red>Exception</red> {e}")
                results = []                 

        return results

    def fetch_by_date(self, opening_date):
        table, _ = self._table_name_schema("nn")

        if not Path(self.db_file).exists():
            logger.opt(colors=True).warning(f"Database file doesn't exist")
            return

        with sqlite3.connect(self.db_file) as conn:
            try:
                cursor = conn.cursor()

                if self._table_exists(cursor, table_name="nn"):
                    logger.opt(colors=True).debug(f"<green>Fetching</green> data for date <yellow>{opening_date}</yellow>")
                    cursor.execute(f'SELECT * FROM {table} WHERE opening_date = ?', (opening_date,))
                    results = cursor.fetchall()
                else:
                    logger.opt(colors=True).warning(f"TABLE <cyan>{table}</cyan> doesn't exist")
                    results = []
            
            except Exception as e:
                logger.opt(colors=True).exception(f"<red>Exception</red> {e}")
                results = []

        return results

    def fetch_last(self):
        table, _ = self._table_name_schema("nn")

        if not Path(self.db_file).exists():
            logger.opt(colors=True).warning(f"Database file doesn't exist")
            return

        with sqlite3.connect(self.db_file) as conn:
            try:
                cursor = conn.cursor()

                if self._table_exists(cursor, table_name="nn"):
                    logger.opt(colors=True).debug(f"<green>Fetching</green> data for last date from <yellow>{table}</yellow>")
                    cursor.execute(f'SELECT * FROM {table} WHERE opening_date = (SELECT MAX(opening_date) FROM {table})',)
                    results = cursor.fetchall()
                else:
                    logger.opt(colors=True).warning(f"TABLE <cyan>{table}</cyan> doesn't exist")
                    results = []
            
            except Exception as e:
                logger.opt(colors=True).exception(f"<red>Exception</red> {e}")
                results = []

        return results

    def deleteall(self, table_name=None):
        table, _ = self._table_name_schema(table_name)
        
        if not Path(self.db_file).exists():
            logger.opt(colors=True).warning(f"Database file doesn't exist")
            return
        
        with sqlite3.connect(self.db_file) as conn:
            try:
                cursor = conn.cursor()

                if self._table_exists(cursor, table_name):
                    logger.opt(colors=True).info(f"<red>Deleting</red> ALL from <cyan>{table}</cyan>")
                    cursor.execute(f'DELETE FROM {table}')
                else:
                    logger.opt(colors=True).warning(f"TABLE <cyan>{table}</cyan> doesn't exist")
            
            except Exception as e:
                logger.opt(colors=True).exception(f"<red>Exception</red> {e}")

    def delete_by_date(self, opening_date):
        table, _ = self._table_name_schema("nn")

        if not Path(self.db_file).exists():
            logger.opt(colors=True).warning(f"Database file doesn't exist")
            return

        with sqlite3.connect(self.db_file) as conn:
            try:
                cursor = conn.cursor()

                if self._table_exists(cursor, table_name="nn"):
                    logger.opt(colors=True).debug(f"<red>Deleting</red> <yellow>{opening_date}</yellow> from <cyan>{table}</cyan>")
                    cursor.execute(f'DELETE FROM {table} WHERE opening_date = ?', (opening_date,))
                else:
                    logger.opt(colors=True).warning(f"TABLE <cyan>{table}</cyan> doesn't exist")
    
            except Exception as e:
                logger.opt(colors=True).exception(f"<red>Exception</red> {e}")

    def backup(self, db_file_bkp=None):
        db_file_bkp = db_file_bkp if db_file_bkp else DB_FILE_BKP

        with sqlite3.connect(self.db_file) as src, sqlite3.connect(db_file_bkp) as dst:
            try:
                src.backup(dst)
                logger.opt(colors=True).info(f"DB Backup <green>successful</green>")

            except sqlite3.Error as e:
                logger.opt(colors=True).exception(f"DB Backup <red>failed</red>: {e}")
                if db_file_bkp.exists():
                    db_file_bkp.unlink()
                raise

    def _table_exists(self, cursor, table_name=None):
        table, _ = self._table_name_schema(table_name)
        cursor.execute('''
            SELECT name FROM sqlite_master WHERE type='table' AND name=?;
        ''', (table,)
        )
        return cursor.fetchone() is not None

    def _table_name_schema(self, table_name=None):
        if table_name == "st":
            table = self.st_table
            table_schema = ST_TABLE_SCHEMA
        else:
            table_name = "nn"
            table = self.nn_table
            table_schema = NN_TABLE_SCHEMA
        return table, table_schema

    @staticmethod
    def _create_columns_def(schema):
        columns_def = []
        for col_name, col_type, constraints in schema:
            definition = f"{col_name} {col_type}"
            if constraints:
                definition += f" {constraints}"
            columns_def.append(definition)
        return columns_def


def backup_db(db_file=DB_FILE):
    database = Database(db_file=db_file)
    database.backup()

def save_settings(data, db_file=DB_FILE):
    serialized_data = [
        {k: json.dumps(v) if k == "value" else v for k, v in row.items()}
        for row in data
    ]
    database = Database(db_file=db_file)
    database.deleteall(table_name="st")
    database.insert(serialized_data, table_name="st")

def load_settings(db_file=DB_FILE):
    database = Database(db_file=db_file)
    data = database.fetchall(table_name="st")
    deserialized_data = {}
    for _, k, v in data:
        try:
            deserialized_data[k] = json.loads(v)
        except (json.JSONDecodeError, TypeError):
            deserialized_data[k] = v
    return deserialized_data


if __name__ == '__main__':
    from logger_config import setup_logging
    setup_logging()
    from loguru import logger
    import json

    database = Database(db_file=TMP_DIR / 'tmp.db', nn_table="tmp", init_db=True)
    data = [
        {
            'asset': 'Asset A',
            'opening_date': '2024-01-01',
            'opening_euro_value': 100.0,
            'closing_date': '2024-01-02',
            'closing_euro_value': 105.0,
            'period_yield_pct': 0.05
        },
        {
            'asset': 'Asset B',
            'opening_date': '2024-01-01',
            'opening_euro_value': 100.0,
            'closing_date': '2024-01-02',
            'closing_euro_value': 101.0,
            'period_yield_pct': 0.01,
        },
    ]
    database.insert(data)
    results = database.fetch_by_date('2024-01-01')
    print(results)
    database.delete_by_date('2024-01-01')
    
    data = [{"key": "selected_assets", "value": ["Euró likviditás eszközalap - D"]},
            {"key": "asset_percentages", "value": {"Euró likviditás eszközalap - D": 100}},
            {"key": "start_date", "value": "2025-01-01"}, {"key": "end_date", "value": "2026-01-01"}]
    save_settings(data)
    data = load_settings()
    print(data)
    
