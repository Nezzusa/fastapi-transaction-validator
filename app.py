import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import create_engine, text, select, func
from sqlalchemy.exc import OperationalError, IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from db import Transaction, FraudLogs

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
        conn.exec_driver_sql(sql)
    print(f"File {file} loaded successfully")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def log_fraud(db: Session, user_id: str, attempted_amount: Decimal, rule_triggered: str):
    try:
        fraud_entry = FraudLogs(
            user_id=user_id,
            attempted_amount=attempted_amount,
            rule_triggered=rule_triggered
        )
        db.add(fraud_entry)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Failed to record fraud log: {e}")


def verify_payment_intensity(user_id: str, attempted_amount: Decimal, db: Session, limit: int = 3, time_window_seconds: int = 10):
    time_threshold = datetime.now(timezone.utc) - timedelta(seconds=time_window_seconds)


    tx_stmt = select(Transaction.id.label("id")).where(
        Transaction.user_id == user_id,
        Transaction.created_at >= time_threshold
    )

    fraud_stmt = select(FraudLogs.id.label("id")).where(
        FraudLogs.user_id == user_id,
        FraudLogs.triggered_at >= time_threshold
    )

    combined_subquery = tx_stmt.union_all(fraud_stmt).subquery()
    recent_count = db.scalar(select(func.count()).select_from(combined_subquery)) or 0

    if recent_count >= limit:
        log_fraud(db, user_id=user_id, attempted_amount=attempted_amount,
                  rule_triggered="RATE_LIMIT_EXCEEDED")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: Maximum {limit} transactions per "
                   f"{time_window_seconds} seconds."
        )


def verify_payment_limits(payment: PaymentRequest, db: Session, max_count: int = 5,
                          max_volume: Decimal = Decimal("5000.00"),
                          time_window_seconds: int = 3600):

    time_threshold = datetime.now(timezone.utc) - timedelta(seconds=time_window_seconds)

    stmt = (
        select(
            func.count(Transaction.id).label("count"),
            func.coalesce(func.sum(Transaction.amount), Decimal("0.00")).label("total_amount")
        ).where(
            Transaction.user_id == payment.sender,
            Transaction.created_at >= time_threshold,
            Transaction.status == "APPROVED"
        )
    )

    recent_count, recent_volume = db.execute(stmt).one()

    if recent_count >= max_count:
        log_fraud(db, user_id=payment.sender, attempted_amount=payment.amount,
                  rule_triggered="COUNT_LIMIT_EXCEEDED")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: Maximum {max_count} transactions per window."
        )

    if (recent_volume + payment.amount) > max_volume:
        log_fraud(db, user_id=payment.sender, attempted_amount=payment.amount,
                  rule_triggered="VOLUME_LIMIT_EXCEEDED")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Volume limit exceeded: Maximum ${max_volume} cumulative limit. "
                   f"Current total: ${recent_volume:.2f}."
        )


def validate_idempotency(payment: PaymentRequest, db: Session):
    stmt = select(Transaction).where(Transaction.idempotency_key == payment.idempotency_key)
    existing = db.scalar(stmt)

    if not existing:
        return None

    if existing.amount != payment.amount or existing.user_id != payment.sender:
        log_fraud(db, user_id=payment.sender, attempted_amount=payment.amount,
                  rule_triggered="IDEMPOTENCY_PAYLOAD_MISMATCH")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency key reuse error: Payload parameters do not match original request.")
    return existing


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

    #Security checks
    existing_transaction = validate_idempotency(payment, db)
    if existing_transaction:
        return {
            "status": "success",
            "received_amount": existing_transaction.amount
        }
    verify_payment_intensity(payment.sender, payment.amount, db)
    verify_payment_limits(payment, db)

    #Create new transaction
    new_transaction = Transaction(
        idempotency_key=payment.idempotency_key,
        amount=payment.amount,
        currency=payment.currency,
        user_id=payment.sender,
        status="APPROVED")

    try:
        db.add(new_transaction)
        db.commit()
        db.refresh(new_transaction)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Transaction with this idempotency key already exists or conflict occurred."
        )
    except OperationalError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable. Please try again later."
        )
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal database error occurred."
        )

    return {"status": "success", "received_amount": new_transaction.amount}