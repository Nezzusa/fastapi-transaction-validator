from sqlalchemy import create_engine, text

def db_init():
    engine = create_engine("sqlite:///paymentprocessing.db", connect_args={"check_same_thread": False})

    with open("tables.sql" ,'r') as f:
        tables = f.read()

    with engine.begin() as conn:
        conn.execute(text(tables))
        print(f"Database initialized successfully")


