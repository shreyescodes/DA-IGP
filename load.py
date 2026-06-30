"""
RetailIQ — MySQL Data Loader (Python / SQLAlchemy)
Class 2 | Part B — Use this if LOAD DATA INFILE fails in MySQL Workbench

INSTALL:
  pip install pymysql sqlalchemy pandas

BEFORE RUNNING:
  1. Make sure MySQL Workbench is open and connected
  2. Run ONLY Part 1 and Part 2 from setup.sql first
     (CREATE DATABASE + CREATE TABLE statements)
  3. Then run this script to load data
  4. Then run Part 5 onwards from the SQL file (indexes + views)

WHY TWO-STEP?
  pandas to_sql creates tables without primary keys or proper data types.
  We create the schema properly in SQL first, then append data via Python.
"""

import os
import pandas as pd
# pyrefly: ignore [missing-import]
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(dotenv_path=os.path.join(os.getcwd(), '.env'))

# =====================================================================
# CONFIG — Loaded from environment variables (.env)
# =====================================================================
MYSQL_USER = os.getenv("DB_USER", "root")
MYSQL_PASS = os.getenv("DB_PASSWORD")
MYSQL_HOST = os.getenv("DB_HOST", "localhost")
MYSQL_PORT = int(os.getenv("DB_PORT", 3306))
MYSQL_DB   = os.getenv("DB_NAME", "retailiq")

CLEAN = "./data/clean/"

# =====================================================================
# CONNECT
# =====================================================================
connection_string = (
    f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASS}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"
    "?charset=utf8mb4"
)

print(f"Connecting to MySQL: {MYSQL_HOST}/{MYSQL_DB}...")
engine = create_engine(connection_string)

# Quick connection test
try:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT VERSION()"))
        version = result.fetchone()[0]
        print(f"Connected. MySQL version: {version}")
except Exception as e:
    print(f"Connection failed: {e}")
    print("Check your MYSQL_USER, MYSQL_PASS, and MYSQL_HOST above.")
    exit(1)

# =====================================================================
# LOAD TABLES
# =====================================================================
tables = [
    ("dim_customers",  f"{CLEAN}dim_customers.csv"),
    ("dim_products",   f"{CLEAN}dim_products.csv"),
    ("dim_sellers",    f"{CLEAN}dim_sellers.csv"),
    ("fact_orders",    f"{CLEAN}fact_orders.csv"),   # load fact last
]

print("\nLoading clean CSVs into MySQL...")

for table_name, filepath in tables:
    print(f"\n  Loading {table_name}...")
    df = pd.read_csv(filepath)

    # Convert date columns to proper format
    for col in df.columns:
        if 'date' in col.lower() or 'timestamp' in col.lower():
            df[col] = pd.to_datetime(df[col], errors='coerce')

    # Replace booleans with int (MySQL TINYINT)
    for col in ['was_late', 'is_delivered', 'has_comment']:
        if col in df.columns:
            df[col] = df[col].fillna(0).astype(int)

    # Append into the schema we already created
    # if_exists='append' means: insert rows without re-creating the table
    df.to_sql(
        name       = table_name,
        con        = engine,
        if_exists  = 'append',   # do NOT use 'replace' — that drops the schema
        index      = False,
        chunksize  = 500,         # 500 rows per INSERT batch
        method     = 'multi'      # batched inserts — much faster than row-by-row
    )
    print(f"  Loaded: {len(df):,} rows into {table_name}")

# =====================================================================
# VERIFY
# =====================================================================
print("\nVerifying row counts...")
verify_query = """
    SELECT 'fact_orders'   AS tbl, COUNT(*) AS row_count FROM fact_orders
    UNION ALL
    SELECT 'dim_customers', COUNT(*) FROM dim_customers
    UNION ALL
    SELECT 'dim_products',  COUNT(*) FROM dim_products
    UNION ALL
    SELECT 'dim_sellers',   COUNT(*) FROM dim_sellers
"""
with engine.connect() as conn:
    result = pd.read_sql(verify_query, conn)
    print(result.to_string(index=False))

print("\nDone. Now run Part 5 onwards in setup.sql")
print("(CREATE INDEX and CREATE VIEW statements)")
