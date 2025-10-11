import sqlite3
import pandas as pd
import os

# --- Configuration ---
DB_NAME = 'bank_data.db'
CSV_FILE = 'transactions.csv'
TABLE_NAME = 'transactions'

def setup_database():
    """Connects to SQLite, creates the table, and loads data from CSV."""
    
    # Check if the CSV file exists
    if not os.path.exists(CSV_FILE):
        print(f"Error: {CSV_FILE} not found. Did you save your file is proper directory?")
        return

    print(f"Connecting to database: {DB_NAME}...")
    # This line connects to the database file. If the file doesn't exist, it creates it.
    conn = sqlite3.connect(DB_NAME)
    
    try:
        # Load the data from the CSV file into a Pandas DataFrame
        df = pd.read_csv(CSV_FILE)
        
        print(f"Loaded {len(df)} records from {CSV_FILE}.")

        # --- SQL Data Type Mapping ---
        # The to_sql function handles most of this, but it's good to know the schema:
        # transaction_id (TEXT), account_id (TEXT), timestamp (TEXT), 
        # amount (REAL), merchant_category (TEXT), location (TEXT), is_fraud (INTEGER)
        
        print(f"Writing data to the '{TABLE_NAME}' table in the database...")
        
        # Write the DataFrame to the SQL database.
        # if_exists='replace' means if the table exists, it drops it and creates a new one.
        # index=False ensures we don't write the Pandas index as a column in the SQL table.
        df.to_sql(TABLE_NAME, conn, if_exists='replace', index=False)
        
        print("Data writing complete. Verifying record count...")

        # --- Verification Step ---
        #  we Run a simple query to confirm the data was loaded correctly
        count_query = f"SELECT COUNT(*) FROM {TABLE_NAME}"
        record_count = pd.read_sql_query(count_query, conn).iloc[0, 0]
        
        print(f"Database setup successful! Total records in table: {record_count}")

    except Exception as e:
        print(f"An error occurred during database setup: {e}")
        
    finally:
        # we close the connection when we're done
        conn.close()

# --- Main Execution ---
if __name__ == '__main__':
    setup_database()