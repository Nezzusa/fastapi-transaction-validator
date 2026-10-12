from decimal import Decimal
from sqlalchemy import select, func
from src.db import Transaction, FraudLogs


def test_process_payment_success(client, db_session):
    payload = {
        "idempotency_key": "tx_success_001",
        "amount": "150.00",
        "currency": "USD",
        "sender": "user_alice"
    }
    response = client.post("/api/payment", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # Verify record in transactions
    tx = db_session.scalar(
        select(Transaction).where(Transaction.idempotency_key == "tx_success_001")
    )
    assert tx is not None
    assert tx.amount == Decimal("150.00")
    assert tx.status == "APPROVED"


def test_idempotency_replay(client):
    payload = {
        "idempotency_key": "tx_replay_001",
        "amount": "200.00",
        "currency": "USD",
        "sender": "user_bob"
    }
    # Initial payment
    res1 = client.post("/api/payment", json=payload)
    assert res1.status_code == 200

    # Same request replayed
    res2 = client.post("/api/payment", json=payload)
    assert res2.status_code == 200
    assert res2.json().get("idempotent_retry") is True


def test_idempotency_payload_mismatch_triggers_fraud(client, db_session):
    original_payload = {
        "idempotency_key": "tx_mismatch_001",
        "amount": "100.00",
        "currency": "USD",
        "sender": "user_charlie"
    }
    client.post("/api/payment", json=original_payload)

    # Reusing same key with altered amount
    tampered_payload = {
        "idempotency_key": "tx_mismatch_001",
        "amount": "999.00",  # Different amount
        "currency": "USD",
        "sender": "user_charlie"
    }
    response = client.post("/api/payment", json=tampered_payload)
    assert response.status_code == 400

    # Verify fraud log created
    fraud_entry = db_session.scalar(
        select(FraudLogs).where(
            FraudLogs.user_id == "user_charlie",
            FraudLogs.rule_triggered == "IDEMPOTENCY_PAYLOAD_MISMATCH"
        )
    )
    assert fraud_entry is not None


def test_verify_payment_intensity_rate_limit(client, db_session):
    user = "user_spammer"

    # Send 3 rapid requests (limit = 3 per 10s)
    for i in range(3):
        res = client.post("/api/payment", json={
            "idempotency_key": f"tx_spam_{i}",
            "amount": "10.00",
            "currency": "USD",
            "sender": user
        })
        assert res.status_code == 200

    # 4th request must fail with 429
    blocked_res = client.post("/api/payment", json={
        "idempotency_key": "tx_spam_blocked",
        "amount": "10.00",
        "currency": "USD",
        "sender": user
    })
    assert blocked_res.status_code == 429

    # Verify fraud log created
    fraud_entry = db_session.scalar(
        select(FraudLogs).where(
            FraudLogs.user_id == user,
            FraudLogs.rule_triggered == "RATE_LIMIT_EXCEEDED"
        )
    )
    assert fraud_entry is not None


def test_verify_payment_limits_volume_exceeded(client, db_session):
    user = "user_whale"

    # Send transaction exceeding $5,000 limit
    res = client.post("/api/payment", json={
        "idempotency_key": "tx_whale_001",
        "amount": "5001.00",
        "currency": "USD",
        "sender": user
    })
    assert res.status_code == 429
    assert "Volume limit exceeded" in res.json()["detail"]

    # Verify fraud log created
    fraud_entry = db_session.scalar(
        select(FraudLogs).where(
            FraudLogs.user_id == user,
            FraudLogs.rule_triggered == "VOLUME_LIMIT_EXCEEDED"
        )
    )
    assert fraud_entry is not None