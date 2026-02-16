import pymysql
import os
from contextlib import contextmanager

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_USER = os.environ.get('DB_USER', 'root')
DB_PASS = os.environ.get('DB_PASS', 'root')
DB_NAME = os.environ.get('DB_NAME', 'mrm_panel')

@contextmanager
def get_db():
    conn = pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
    try:
        yield conn
    finally:
        conn.close()

def execute_query(sql, params=None):
    with get_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params or ())
            conn.commit()
            return cursor

def fetch_one(sql, params=None):
    with get_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params or ())
            return cursor.fetchone()

def fetch_all(sql, params=None):
    with get_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params or ())
            return cursor.fetchall()

def insert(table, data):
    cols = list(data.keys())
    vals = list(data.values())
    placeholders = ','.join(['%s'] * len(cols))
    sql = f"INSERT INTO `{table}` ({','.join([f'`{col}`' for col in cols])}) VALUES ({placeholders})"
    cursor = execute_query(sql, vals)
    return cursor.lastrowid

def update(table, data, where_clause, where_params):
    sets = ','.join([f"`{k}`=%s" for k in data.keys()])
    sql = f"UPDATE `{table}` SET {sets} WHERE {where_clause}"
    params = list(data.values()) + list(where_params)
    execute_query(sql, params)
def delete(table, where_clause, where_params):
    sql = f"DELETE FROM `{table}` WHERE {where_clause}"
    execute_query(sql, where_params)