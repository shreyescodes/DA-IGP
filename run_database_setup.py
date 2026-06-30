import os
import subprocess
import sys
import pandas as pd
from sqlalchemy import create_engine, text

from dotenv import load_dotenv

# Load .env file from the current working directory
load_dotenv(dotenv_path=os.path.join(os.getcwd(), '.env'))

MYSQL_USER = os.getenv("DB_USER", "root")
MYSQL_PASS = os.getenv("DB_PASSWORD")
MYSQL_HOST = os.getenv("DB_HOST", "localhost")
MYSQL_PORT = int(os.getenv("DB_PORT", 3306))

def split_sql_statements(sql_content):
    # Basic splitter that handles simple SQL statements
    statements = []
    current_statement = []
    
    # We want to strip out single-line comments starting with --
    lines = sql_content.split('\n')
    for line in lines:
        cleaned_line = line.strip()
        # Skip comment-only lines
        if cleaned_line.startswith('--') or not cleaned_line:
            continue
        # Also strip trailing -- comments
        if '--' in cleaned_line:
            # Simple check, assuming no literal strings with '--'
            cleaned_line = cleaned_line.split('--')[0].strip()
            
        current_statement.append(cleaned_line)
        if cleaned_line.endswith(';'):
            stmt = ' '.join(current_statement)
            if stmt.strip() and stmt.strip() != ';':
                statements.append(stmt)
            current_statement = []
            
    # Add any remaining statement
    if current_statement:
        stmt = ' '.join(current_statement).strip()
        if stmt and stmt != ';':
            statements.append(stmt)
            
    return statements

def run_sql_file_sections(sql_path, engine, start_marker=None, end_marker=None):
    with open(sql_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Split content if markers are provided
    if start_marker or end_marker:
        # We can search for comments that look like the markers
        lines = content.split('\n')
        sub_lines = []
        capture = True if not start_marker else False
        for line in lines:
            if start_marker and start_marker in line:
                capture = True
                continue
            if end_marker and end_marker in line:
                capture = False
                break
            if capture:
                sub_lines.append(line)
        content_to_run = '\n'.join(sub_lines)
    else:
        content_to_run = content
        
    statements = split_sql_statements(content_to_run)
    
    with engine.begin() as conn:
        for stmt in statements:
            print(f"Executing: {stmt[:100]}...")
            conn.execute(text(stmt))

def main():
    sql_path = r"c:\Users\hp\OneDrive\Desktop\DA-IGP\02_mysql_schema_views.sql"
    
    # Connect to base MySQL server to set up database
    base_connection_string = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASS}@{MYSQL_HOST}:{MYSQL_PORT}/mysql?charset=utf8mb4"
    print("Connecting to MySQL base server...")
    base_engine = create_engine(base_connection_string)
    
    print("\n--- Running PART 1: Database Setup ---")
    run_sql_file_sections(sql_path, base_engine, start_marker="PART 1:", end_marker="PART 2:")
    
    # Now connect to retailiq database
    retailiq_connection_string = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASS}@{MYSQL_HOST}:{MYSQL_PORT}/retailiq?charset=utf8mb4"
    print("\nConnecting to retailiq database...")
    db_engine = create_engine(retailiq_connection_string)
    
    print("\n--- Running PART 2: Table Creation ---")
    run_sql_file_sections(sql_path, db_engine, start_marker="PART 2:", end_marker="PART 3:")
    
    print("\n--- Running 02_mysql_loader.py to load data (might take 2-3 minutes) ---")
    # Run the existing loader script using the venv python interpreter
    loader_path = r"c:\Users\hp\OneDrive\Desktop\DA-IGP\02_mysql_loader.py"
    venv_python = r"c:\Users\hp\OneDrive\Desktop\DA-IGP\venv\Scripts\python.exe"
    
    result = subprocess.run([venv_python, loader_path], capture_output=True, text=True, cwd=r"c:\Users\hp\OneDrive\Desktop\DA-IGP")
    print("Loader stdout:")
    print(result.stdout)
    if result.stderr:
        print("Loader stderr:")
        print(result.stderr)
        
    if result.returncode != 0:
        print("ERROR: Loader failed!")
        sys.exit(1)
        
    print("\n--- Running PART 3: Verifying Data Loaded ---")
    # We can run these verification queries and display outputs
    with db_engine.connect() as conn:
        res = conn.execute(text("""
            SELECT 'fact_orders' AS table_name, COUNT(*) AS row_count FROM fact_orders
            UNION ALL SELECT 'dim_customers', COUNT(*) FROM dim_customers
            UNION ALL SELECT 'dim_products',  COUNT(*) FROM dim_products
            UNION ALL SELECT 'dim_sellers',   COUNT(*) FROM dim_sellers;
        """))
        print("\nRow Counts:")
        for r in res:
            print(f"  {r[0]}: {r[1]:,}")
            
        res_sanity = pd.read_sql("""
            SELECT
                MIN(order_purchase_date)         AS earliest_order,
                MAX(order_purchase_date)         AS latest_order,
                SUM(revenue)                     AS total_revenue_R$,
                AVG(order_value)                 AS avg_order_value_R$,
                COUNT(*)                          AS total_orders,
                AVG(review_score)                AS avg_review_score,
                AVG(delivery_days)               AS avg_delivery_days,
                SUM(was_late)/COUNT(*)*100       AS late_pct
            FROM fact_orders;
        """, conn)
        print("\nFact Table Sanity Check:")
        print(res_sanity.to_string(index=False))

    print("\n--- Running PART 4: Creating Indexes ---")
    run_sql_file_sections(sql_path, db_engine, start_marker="PART 4:", end_marker="PART 5:")
    
    print("\n--- Running PART 5: Creating Analytical Views ---")
    run_sql_file_sections(sql_path, db_engine, start_marker="PART 5:", end_marker="PART 6:")
    
    print("\n--- Running PART 6: Verifying All Views ---")
    with db_engine.connect() as conn:
        res = conn.execute(text("""
            SELECT 'vw_monthly_revenue'    AS view_name, COUNT(*) AS `rows` FROM vw_monthly_revenue
            UNION ALL SELECT 'vw_category_performance', COUNT(*) FROM vw_category_performance
            UNION ALL SELECT 'vw_rfm_segments',         COUNT(*) FROM vw_rfm_segments
            UNION ALL SELECT 'vw_state_performance',    COUNT(*) FROM vw_state_performance
            UNION ALL SELECT 'vw_seller_performance',   COUNT(*) FROM vw_seller_performance
            UNION ALL SELECT 'vw_payment_analysis',     COUNT(*) FROM vw_payment_analysis;
        """))
        print("\nView Row Counts:")
        for r in res:
            print(f"  {r[0]}: {r[1]}")

    print("\nPipeline Complete!")

if __name__ == "__main__":
    main()
