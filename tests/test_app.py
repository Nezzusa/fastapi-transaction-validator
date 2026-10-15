from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy import func, select, text
from src.db import FraudLogs, Transaction


def test_verify_connected_database(db_session):
    db_name = db_session.execute(text("SELECT current_database()")).scalar()
    print(f"\n[TEST EXECUTION] Connected to database: {db_name}")

    assert db_name == "paymentprocessing_test"

def make_payload(key, amount="10.00", sender="user_test", currency="USD"):
    return {
        "idempotency_key": key,
        "amount": amount,
        "currency": currency,
        "sender": sender,
    }


def seed_transactions(db_session, user, count, amount, minutes_ago=5):
    created = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    for i in range(count):
        db_session.add(
            Transaction(
                idempotency_key=f"seed_{user}_{i}",
                amount=Decimal(amount),
                currency="USD",
                user_id=user,
                status="APPROVED",
                created_at=created,
            )
        )
    db_session.commit()


def fraud_entry(db_session, user, rule):
    db_session.expire_all()
    return db_session.scalar(
        select(FraudLogs).where(
            FraudLogs.user_id == user,
            FraudLogs.rule_triggered == rule,
        )
    )


def test_process_payment_success(client, db_session):
    res = client.post(
        "/api/payment", json=make_payload("tx_success_001", "150.00", "user_alice")
    )
    assert res.status_code == 200
    assert res.json()["status"] == "success"

    db_session.expire_all()
    tx = db_session.scalar(
        select(Transaction).where(Transaction.idempotency_key == "tx_success_001")
    )
    assert tx is not None
    assert tx.amount == Decimal("150.00")
    assert tx.status == "APPROVED"
    assert tx.user_id == "user_alice"


def test_idempotency_replay(client, db_session):
    payload = make_payload("tx_replay_001", "200.00", "user_bob")

    res1 = client.post("/api/payment", json=payload)
    assert res1.status_code == 200
    assert res1.json().get("idempotent_retry") is None

    res2 = client.post("/api/payment", json=payload)
    assert res2.status_code == 200
    assert res2.json().get("idempotent_retry") is True

    db_session.expire_all()
    count = db_session.scalar(
        select(func.count()).select_from(Transaction).where(
            Transaction.idempotency_key == "tx_replay_001"
        )
    )
    assert count == 1


def test_idempotency_payload_mismatch_triggers_fraud(client, db_session):
    first = client.post(
        "/api/payment", json=make_payload("tx_mismatch_001", "100.00", "user_charlie")
    )
    assert first.status_code == 200

    res = client.post(
        "/api/payment", json=make_payload("tx_mismatch_001", "999.00", "user_charlie")
    )
    assert res.status_code == 400
    assert fraud_entry(db_session, "user_charlie", "IDEMPOTENCY_PAYLOAD_MISMATCH")


def test_verify_payment_intensity_rate_limit(client, db_session):
    user = "user_spammer"

    for i in range(3):
        res = client.post("/api/payment", json=make_payload(f"tx_spam_{i}", sender=user))
        assert res.status_code == 200

    blocked = client.post("/api/payment", json=make_payload("tx_spam_blocked", sender=user))
    assert blocked.status_code == 429
    assert fraud_entry(db_session, user, "RATE_LIMIT_EXCEEDED")


def test_verify_payment_limits_volume_exceeded(client, db_session):
    user = "user_whale"

    res = client.post(
        "/api/payment", json=make_payload("tx_whale_001", "5001.00", user)
    )
    assert res.status_code == 429
    assert "Volume limit exceeded" in res.json()["detail"]
    assert fraud_entry(db_session, user, "VOLUME_LIMIT_EXCEEDED")


def test_cumulative_volume_limit_exceeded(client, db_session):
    user = "user_cumulative"
    seed_transactions(db_session, user, count=2, amount="2000.00")  # 4000 so far

    res = client.post("/api/payment", json=make_payload("tx_cum_over", "1500.00", user))
    assert res.status_code == 429
    assert "Volume limit exceeded" in res.json()["detail"]
    assert fraud_entry(db_session, user, "VOLUME_LIMIT_EXCEEDED")


def test_cumulative_volume_within_limit_succeeds(client, db_session):
    user = "user_within"
    seed_transactions(db_session, user, count=2, amount="2000.00")  # 4000 so far

    res = client.post("/api/payment", json=make_payload("tx_cum_ok", "1000.00", user))
    assert res.status_code == 200


def test_count_limit_exceeded(client, db_session):
    user = "user_counter"
    seed_transactions(db_session, user, count=5, amount="10.00")

    res = client.post("/api/payment", json=make_payload("tx_count_over", "10.00", user))
    assert res.status_code == 429
    assert fraud_entry(db_session, user, "COUNT_LIMIT_EXCEEDED")