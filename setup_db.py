import os
import time
import pandas as pd
from sqlalchemy import create_engine, text, DDL
from sqlalchemy.types import String, TIMESTAMP, Float, Integer # Import SQLAlchemy types
from sqlalchemy.exc import OperationalError

# --- Configuration ---
CSV_FILE = 'transactions.csv'
TABLE_NAME = 'transactions'
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://user:password@localhost/bankdb")

def setup_database():
    """
    Connects to PostgreSQL and seeds it with initial data from a CSV
    if the transactions table is empty.
    """
    # ... (connection logic remains the same)
    if not os.path.exists(CSV_FILE):
        print(f"Error: {CSV_FILE} not found. Please run generate_data.py first.")
        return

    print("Waiting for database to be ready...")
    engine = None
    for _ in range(5):
        try:
            engine = create_engine(DATABASE_URL)
            with engine.connect() as connection:
                print("Database connection successful.")
                break
        except OperationalError as e:
            print(f"Database connection failed: {e}. Retrying in 5 seconds...")
            time.sleep(5)
    
    if engine is None:
        print("Could not connect to the database. Aborting.")
        return

    try:
        with engine.connect() as connection:
            # Check if table exists
            from sqlalchemy import inspect
            inspector = inspect(engine)
            if not inspector.has_table(TABLE_NAME):
                 # If table doesn't exist, create it and load data
                print(f"Table '{TABLE_NAME}' not found. Creating and seeding table.")
                df = pd.read_csv(CSV_FILE)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                
                # Use SQLAlchemy Type objects
                dtype = {
                    'transaction_id': String, 'account_id': String, 'timestamp': TIMESTAMP,
                    'amount': Float, 'merchant_category': String, 'location': String,
                    'is_fraud': Integer
                }
                df.to_sql(TABLE_NAME, connection, if_exists='fail', index=False, dtype=dtype)
                connection.execute(DDL(f'ALTER TABLE "{TABLE_NAME}" ADD PRIMARY KEY (transaction_id);'))
                connection.commit()
                print("Table created and seeded successfully.")
            else:
                # If table exists, check if it's empty
                count = connection.execute(text(f"SELECT COUNT(*) FROM {TABLE_NAME}")).scalar_one()
                if count == 0:
                    print("Table is empty. Seeding data...")
                    df = pd.read_csv(CSV_FILE)
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    # Use SQLAlchemy Type objects for appending as well
                    dtype = {
                        'transaction_id': String, 'account_id': String, 'timestamp': TIMESTAMP,
                        'amount': Float, 'merchant_category': String, 'location': String,
                        'is_fraud': Integer
                    }
                    df.to_sql(TABLE_NAME, connection, if_exists='append', index=False, dtype=dtype)
                    connection.commit()
                    print(f"Seeded {len(df)} records into '{TABLE_NAME}'.")
                else:
                    print(f"Table '{TABLE_NAME}' already contains {count} records. No action taken.")

    except Exception as e:
        print(f"An error occurred during database setup: {e}")
    finally:
        if engine:
            engine.dispose()

if __name__ == '__main__':
    setup_database()