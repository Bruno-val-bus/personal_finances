import os
import sqlite3
from typing import List

file_directory_path = os.path.dirname(__file__)
OCR_DB_PATH = os.path.join(file_directory_path, "ocr.db")
ADD_RECEIPTS_SQL = os.path.join(file_directory_path, "sql", "add_receipt.sql")
CREATE_RECEIPTS_SQL = os.path.join(file_directory_path, "sql", "create_receipts.sql")
ID = "id"
FILE_NAME = "file_name"
ADDED2SPLITWISE = "added2splitwise"
OCR_PARSED = "ocr_parsed"
col_name_idx_map = {
    ID: 0,
    FILE_NAME: 1,
    ADDED2SPLITWISE: 2,
    OCR_PARSED: 3
}


def create_receipts() -> None:
    # create connection
    conn = sqlite3.connect(OCR_DB_PATH)
    # Create a cursor
    cur = conn.cursor()
    # get raw sql query
    raw_sql = read_sql_query(CREATE_RECEIPTS_SQL)
    cur.execute(raw_sql)
    # Commit the changes and close the connection
    conn.commit()
    cur.close()
    conn.close()


def insert_receipt(file_name: str, added2splitwise: bool, ocr_parsed: bool) -> List:
    # create connection
    conn = sqlite3.connect(OCR_DB_PATH)
    # Create a cursor
    cur = conn.cursor()
    # get raw sql query
    raw_sql = read_sql_query(ADD_RECEIPTS_SQL)
    # execute SQL command to insert a row into the table
    cur.execute(raw_sql, (file_name, added2splitwise, ocr_parsed))
    # commit transaction
    conn.commit()
    cur.execute("SELECT * FROM receipts")
    rows = cur.fetchall()
    # close the cursor and connection objects
    cur.close()
    conn.close()
    return rows


def get_receipts_table() -> List:
    # create connection
    conn = sqlite3.connect(OCR_DB_PATH)
    # Create a cursor
    cur = conn.cursor()
    # get raw sql query
    raw_sql = "SELECT * FROM receipts;"
    # execute SQL command to insert a row into the table
    cur.execute(raw_sql)
    # close the cursor and connection objects
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def get_receipts_added2splitwise(col_name: str = "*") -> List:
    # create connection
    conn = sqlite3.connect(OCR_DB_PATH)
    # Create a cursor
    cur = conn.cursor()
    # get raw sql query
    raw_sql = f"SELECT {col_name} FROM receipts WHERE added2splitwise=1"
    # execute SQL command to insert a row into the table
    cur.execute(raw_sql)
    # close the cursor and connection objects
    rows = cur.fetchall()
    if col_name != "*":
        rows = [tp[0] for tp in rows]
    cur.close()
    conn.close()
    return rows


def read_sql_query(sql_path: str) -> str:
    with open(sql_path, 'r') as f:
        sql_query = f.read()
    return sql_query
