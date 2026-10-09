import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:admin@localhost:5432/paymentprocessing",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


def db_read(file: str):
    with open(file, "r") as f:
        sql = f.read()
    with engine.begin() as conn:
        conn.exec_driver_sql(sql)  # runs raw SQL; text() would treat ":" as bind params
    print(f"File {file} loaded successfully")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Verify the connection on startup and fail with a clear message
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("Connected to PostgreSQL")
    except OperationalError as e:
        raise RuntimeError(f"Cannot connect to PostgreSQL: {e.orig}") from e
    db_read("tables.sql")
    yield
    engine.dispose()


app = FastAPI(lifespan=lifespan)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Payment(BaseModel):
    idempotency_key: int
    sender: str
    amount: float
    currency: str
    receiver: str


@app.post("/api/payment")
async def process_payment(payment: Payment, db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))  # replace with your INSERT once the schema is settled
    except OperationalError:
        raise HTTPException(status_code=503, detail="Database unavailable")

    print(f"Received payment from {payment.sender} of {payment.amount} {payment.currency}")
    return {"status": "success", "received_amount": payment.amount}