import sqlite3
from color_logger import logger

TABLE_NAME = 'nn_euro_yields'
DB_FOLDER = 'db'
DB_FILE = f'{DB_FOLDER}/{TABLE_NAME}.db'

def drop():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    logger.info(f"Dropping #y<{TABLE_NAME}> table if it exists...")
    cursor.execute(f'DROP TABLE IF EXISTS {TABLE_NAME}')
    conn.commit()
    conn.close()

def create():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    logger.info(f"Creating #y<{TABLE_NAME}> table if it doesn't exist...")
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id INTEGER PRIMARY KEY,
            asset_name TEXT,
            date TEXT,
            opening_value REAL,
            closing_value REAL,
            period_yield REAL
        )'''
    )
    conn.commit()
    conn.close()

def insert(data):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()  
    logger.info(f"Inserting data into #y<{TABLE_NAME}> table...")
    cursor.executemany(f'''
        INSERT INTO {TABLE_NAME} (asset_name, date, opening_value, closing_value, period_yield)
        VALUES (:asset_name, :date, :opening_value, :closing_value, :period_yield)
    ''', data)
    conn.commit()
    conn.close()

def query_all():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(f'SELECT * FROM {TABLE_NAME}')
    results = cursor.fetchall()
    conn.close()
    return results

if __name__ == '__main__':
    drop()
    create()
    # Example data insertion
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
    insert(data)
    logger.info(f"Querying all data from #y<{TABLE_NAME}> table...")
    results = query_all()
    print(results)