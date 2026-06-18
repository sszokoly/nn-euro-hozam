#!/usr/bin/env python3

from loguru import logger
from config import (
    DB_FILE,
    DB_FILE_BKP,
    DB_NN_TABLE_NAME,
    DB_ST_TABLE_NAME,
    ST_TABLE_SCHEMA,
    NN_TABLE_SCHEMA,
)

import json
import sqlite3
from datetime import datetime, date
from pathlib import Path


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
        if init_db or not Path(self.db_file).exists():
            self.init_db()


    def init_db(self):
        if Path(self.db_file).exists():
            logger.opt(colors=True).info(f"<red>Deleting</red> database file")
            Path(self.db_file).unlink()

        logger.opt(colors=True).info(f"<green>Creating</green> database file")
        with sqlite3.connect(self.db_file) as conn:
            try:
                cursor = conn.cursor()

                for table_name in "nn", "st":
                    self._ensure_table(cursor, table_name)

            except Exception as e:
                logger.opt(colors=True).exception(f"<red>Exception</red> {e}")


    def insert(self, data, table_name: str = "nn") -> None:
        if not data:
            return

        table, _ = self._table_name_schema(table_name)
        
        with sqlite3.connect(self.db_file) as conn:
            try:
                cursor = conn.cursor()
                self._ensure_table(cursor, table_name)

                logger.opt(colors=True).debug(
                    f"<green>Inserting</green> data into <cyan>{table}</cyan>"
                )
                column_fields = ", ".join(data[0].keys())
                value_fields = ", ".join(f":{x}" for x in data[0].keys())
                cursor.executemany(f'''
                    INSERT INTO {table} ({column_fields})
                    VALUES ({value_fields})
                ''', data)

            except Exception as e:
                logger.opt(colors=True).exception(f"<red>Exception</red> {e}")


    def fetchall(self, table_name: str = "nn") -> list:
        table, _ = self._table_name_schema(table_name)

        with sqlite3.connect(self.db_file) as conn:
            try:
                cursor = conn.cursor()
                self._ensure_table(cursor, table_name)

                logger.opt(colors=True).info(
                    f"<green>Fetching</green> ALL from TABLE <cyan>{table}</cyan>"
                )
                cursor.execute(f'SELECT * FROM {table}')
                results = cursor.fetchall()

            except Exception as e:
                logger.opt(colors=True).exception(f"<red>Exception</red> {e}")
                results = []                 

        return results


    def fetch_nn_by_date(self, opening_date: str) -> list:
        table, _ = self._table_name_schema("nn")        
        sql = f'''SELECT * FROM {table} WHERE opening_date = ?'''
        return self._fetch_nn(sql, opening_date)


    def fetch_first_nn(self) -> list:
        table, _ = self._table_name_schema("nn")
        sql = f'''
            SELECT * FROM {table}
            WHERE opening_date = (
                SELECT MIN(opening_date) FROM {table}
            )
        '''
        return self._fetch_nn(sql)


    def fetch_last_nn(self) -> list:
        table, _ = self._table_name_schema("nn")
        sql = f'''
            SELECT * FROM {table}
            WHERE opening_date = (
                SELECT MAX(opening_date) FROM {table}
            )
        '''
        return self._fetch_nn(sql)


    def _fetch_nn(self, sql: str, opening_date: str | None = None) -> list:
        table_name = "nn"
        table, _ = self._table_name_schema(table_name)
        
        with sqlite3.connect(self.db_file) as conn:
            try:
                cursor = conn.cursor()
                self._ensure_table(cursor, table_name)
                
                logger.opt(colors=True).info(
                    f"<green>Fetching</green> from TABLE <cyan>{table}</cyan>"
                )
                
                if opening_date is not None:
                    cursor.execute(sql, (opening_date,))
                else:
                    cursor.execute(sql)
                results = cursor.fetchall()
            
            except Exception as e:
                logger.opt(colors=True).exception(f"<red>Exception</red> {e}")
                results = []

        return results


    def deleteall(self, table_name: str = "nn") -> None:
        table, _ = self._table_name_schema(table_name)

        with sqlite3.connect(self.db_file) as conn:
            try:
                cursor = conn.cursor()
                cursor.execute(f'DROP TABLE IF EXISTS {table}')
                logger.opt(colors=True).info(
                    f"<red>Dropped</red> TABLE <cyan>{table}</cyan>"
                )
                self._ensure_table(cursor, table_name)
                #cursor.execute(f'DELETE FROM {table}')
            
            except Exception as e:
                logger.opt(colors=True).exception(f"<red>Exception</red> {e}")


    def delete_nn_by_date(self, opening_date: str) -> None:
        table_name = "nn"
        table, _ = self._table_name_schema("nn")

        with sqlite3.connect(self.db_file) as conn:
            try:
                cursor = conn.cursor()
                self._ensure_table(cursor, table_name)

                logger.opt(colors=True).debug(
                    f"<red>Deleting</red> <yellow>{opening_date}</yellow> "
                    f"from <cyan>{table}</cyan>"
                )
                cursor.execute(f'DELETE FROM {table} WHERE opening_date = ?', (opening_date,))
            
            except Exception as e:
                logger.opt(colors=True).exception(f"<red>Exception</red> {e}")


    def backup(self, db_file_bkp: str = None) -> None:
        db_file_bkp = Path(db_file_bkp) if db_file_bkp else DB_FILE_BKP
        

        with (sqlite3.connect(self.db_file) as src,
              sqlite3.connect(db_file_bkp)  as dst
            ):
            try:
                src.backup(dst)
                logger.opt(colors=True).info(
                    f"Database backed up <green>successfully</green>"
                )

            except sqlite3.Error as e:
                logger.opt(colors=True).exception(
                    f"Database backup <red>failed</red> with: {e}"
                )
                if db_file_bkp.exists():
                    db_file_bkp.unlink()
                raise

    
    def _ensure_table(self, cursor, table_name: str = "nn") -> None:
        table, table_schema = self._table_name_schema(table_name)
        columns_def = self._create_columns_def(table_schema)
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {table} ({', '.join(columns_def)})
        ''')


    def _table_name_schema(self, table_name: str = "nn") -> tuple[str, list]:
        if table_name == "nn":
            table = self.nn_table
            table_schema = NN_TABLE_SCHEMA
            return table, table_schema
        
        elif table_name == "st":
            table = self.st_table
            table_schema = ST_TABLE_SCHEMA
            return table, table_schema
        
        raise ValueError(
            f"Invalid {table_name} 'table_name' provided, "
            f"valid arguments are: 'nn' or 'st'"
        )

    @staticmethod
    def _create_columns_def(schema: list) -> list:
        columns_def = []
        for col_name, col_type, constraints in schema:
            definition = f"{col_name} {col_type}"
            if constraints:
                definition += f" {constraints}"
            columns_def.append(definition)
        return columns_def


    @property
    def start_date(self) -> date:
        results = self.fetch_first_nn()
        if results:
            return datetime.strptime(results[0][2], "%Y-%m-%d").date()


    @property
    def end_date(self) -> date:
        results = self.fetch_last_nn()
        if results:
            return datetime.strptime(results[0][2], "%Y-%m-%d").date()


def backup_db(db_file: str = None) -> None:
    db_file = Path(db_file) if db_file else DB_FILE
    database = Database(db_file=db_file)
    database.backup()


def save_settings(data, db_file: str = None) -> None:
    db_file = Path(db_file) if db_file else DB_FILE
    serialized_data = [
        {k: json.dumps(v) if k == "value" else v for k, v in row.items()}
        for row in data
    ]
    database = Database(db_file=db_file)
    database.deleteall(table_name="st")
    database.insert(serialized_data, table_name="st")


def load_settings(db_file: str = None) -> dict:
    db_file = Path(db_file) if db_file else DB_FILE
    database = Database(db_file=db_file)
    data = database.fetchall(table_name="st")
    deserialized_data = []
    
    for _, k, v in data:
        try:
            d = {"key": k, "value": json.loads(v)}
        except (json.JSONDecodeError, TypeError):
            d = {"key": k, "value": v}
        deserialized_data.append(d)
    
    return deserialized_data


if __name__ == '__main__':
    from config import setup_logging
    setup_logging()
    from loguru import logger
    import json
    from config import TMP_DIR

    database = Database(db_file=TMP_DIR / 'tmp.db', nn_table="tmp", init_db=True)

    ## NN test
    nn_data_bkp = database.fetchall(table_name="nn") 
    nn_data_new = [
        {
            'asset': 'Asset A',
            'opening_date': '2026-05-01',
            'opening_euro_value': 100.0,
            'closing_date': '2026-05-02',
            'closing_euro_value': 105.0,
            'yield_ratio': 0.05
        },
        {
            'asset': 'Asset B',
            'opening_date': '2026-05-02',
            'opening_euro_value': 100.0,
            'closing_date': '2026-05-03',
            'closing_euro_value': 101.0,
            'yield_ratio': 0.01,
        },
    ]
    database.insert(nn_data_new)
    results = database.fetch_nn_by_date('2026-05-01')
    print(f"==== RESULT ====\n", results)
    print(f"==== START DATE ====\n", database.start_date)
    print(f"==== END DATE ====\n", database.end_date)
    database.delete_nn_by_date('2026-05-02')
    database.deleteall(table_name="nn")
    database.insert(nn_data_bkp)
    
    ## Streamlit config test
    st_settings_backup = load_settings()
    st_settings = [
        {
            "key": "selected_assets",
            "value": ["Euró likviditás eszközalap - D"]
        },
        {
            "key": "asset_percentages",
            "value": {"Euró likviditás eszközalap - D": 100}
        },
        {
            "key": "start_date",
            "value": "2025-01-01"
        }, 
        {
            "key": "end_date",
            "value": "2026-01-01"
        }
    ]
    save_settings(st_settings)
    st_settings = load_settings()
    print(f"==== ST SETTINGS ====\n", st_settings)
    save_settings(st_settings_backup)
