import os
from contextlib import asynccontextmanager
from datetime import datetime
from decimal import Decimal
from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import create_engine, text, select
from sqlalchemy.exc import OperationalError, IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from db import Transaction

class PaymentRequest(BaseModel):
    idempotency_key: str
    amount: Decimal
    currency: str
    sender: str



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

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

#Checks for bot attempts at payment
def detect_bots(payment: PaymentRequest, db: Session):

    return 1


#Checks for microtransactions in short amount of time
def detect_micro(payment: PaymentRequest, db: Session):


    return 1

def validate_idempotency(payment: PaymentRequest, db: Session):
    stmt = select(Transaction).where(Transaction.idempotency_key == payment.idempotency_key)
    existing = db.scalar(stmt)

    #Transaction not found = proceed
    if not existing:
        return None

    if existing.amount != payment.amount or existing.user_id != payment.sender:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency key reuse error: Payload parameters do not match original request."
        )

    #Return the first transaction, discard the retry attempt
    return existing


#App lifespan cycle
@asynccontextmanager
async def lifespan(app: FastAPI):
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


@app.post("/api/payment")
async def process_payment(payment: PaymentRequest, db: Session = Depends(get_db)):

    # Run checks
    validate_idempotency(payment, db)


    #Generate database entry
    new_transaction = Transaction(
        idempotency_key=payment.idempotency_key,
        amount=payment.amount,
        currency=payment.currency,
        user_id=payment.sender,
        status="PENDING")

    try:
        db.add(new_transaction)
        db.commit()
        db.refresh(new_transaction)

    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Transaction with this idempotency key already exists or conflict occurred.")

    except OperationalError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable. Please try again later.")

    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal database error occurred.")



    print(f"Received payment from {payment.sender} of {payment.amount} {payment.currency}")
    return {"status": "success", "received_amount": payment.amount} #what we actually return


