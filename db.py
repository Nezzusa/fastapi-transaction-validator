import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import DateTime, Numeric, String, UUID, func, text, Index, BigInteger
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass

class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        Index("idx_transactions_user_created", "user_id", "created_at"))

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"))
    idempotency_key: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False)
    user_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False)
    amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="APPROVED")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now())


class FraudLogs(Base):
    __tablename__ = "fraud_logs"
    __table_args__ = (
        Index("idx_fraud_logs_user_triggered", "user_id", "triggered_at"))

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False)
    attempted_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False)
    rule_triggered: Mapped[str] = mapped_column(
        String(100),
        nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now())