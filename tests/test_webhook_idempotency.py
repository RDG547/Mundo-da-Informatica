import base64
import hashlib
import hmac
import json
from unittest.mock import patch

from app import PaymentWebhookEvent, SignatureVerificationError, Transaction, User, app, db


def test_stripe_webhook_is_idempotent(client):
    with app.app_context():
        user = User(
            username="pagante",
            email="pagante@example.test",
            password_hash="not-used-in-tests",
            plan="free",
            role="user",
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    event = {
        "id": "evt_idempotent_1",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_idempotent_1",
                "metadata": {"user_id": str(user_id), "plan": "premium"},
                "payment_status": "paid",
                "amount_total": 2990,
                "currency": "brl",
                "customer": "cus_test",
                "subscription": "sub_test",
            }
        },
    }

    with patch("app.stripe.Webhook.construct_event", return_value=event):
        first = client.post("/stripe-webhook", data=b"signed-payload", headers={"Stripe-Signature": "test"})
        second = client.post("/stripe-webhook", data=b"signed-payload", headers={"Stripe-Signature": "test"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.get_json()["status"] == "duplicate"
    with app.app_context():
        assert Transaction.query.filter_by(stripe_session_id="cs_idempotent_1").count() == 1
        webhook_event = PaymentWebhookEvent.query.one()
        assert webhook_event.status == "processed"
        assert db.session.get(User, user_id).plan == "premium"


def test_stripe_rejects_missing_signature(client):
    response = client.post("/stripe-webhook", data=b"{}")
    assert response.status_code == 400
    with app.app_context():
        assert PaymentWebhookEvent.query.count() == 0


def test_stripe_rejects_invalid_signature(client):
    with patch(
        "app.stripe.Webhook.construct_event",
        side_effect=SignatureVerificationError("bad signature", "sig"),
    ):
        response = client.post(
            "/stripe-webhook",
            data=b"{}",
            headers={"Stripe-Signature": "invalid"},
        )
    assert response.status_code == 400


def test_stripe_records_failed_processing_for_retry(client):
    event = {
        "id": "evt_unpaid_1",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_unpaid_1",
                "metadata": {"user_id": "999", "plan": "premium"},
                "payment_status": "unpaid",
            }
        },
    }
    with patch("app.stripe.Webhook.construct_event", return_value=event):
        response = client.post(
            "/stripe-webhook",
            data=b"signed-payload",
            headers={"Stripe-Signature": "test"},
        )

    assert response.status_code == 500
    with app.app_context():
        webhook_event = PaymentWebhookEvent.query.one()
        assert webhook_event.status == "failed"
        assert "pagamento confirmado" in webhook_event.error_message


def test_abacatepay_webhook_is_idempotent(client):
    with app.app_context():
        user = User(
            username="pix-user",
            email="pix@example.test",
            password_hash="not-used",
            plan="free",
            role="user",
            is_active=True,
        )
        db.session.add(user)
        db.session.flush()
        transaction = Transaction(
            user_id=user.id,
            payment_gateway="abacatepay",
            abacatepay_billing_id="external-pix-1",
            abacatepay_charge_id="pix-charge-1",
            plan_type="vip",
            amount=4990,
            status="pending",
        )
        db.session.add(transaction)
        db.session.commit()
        user_id = user.id

    payload = {
        "id": "ab-event-1",
        "event": "transparent.completed",
        "data": {"transparent": {"id": "pix-charge-1", "status": "PAID"}},
    }
    raw_body = json.dumps(payload, separators=(",", ":")).encode()
    public_key = "public-test-key"
    signature = base64.b64encode(hmac.new(public_key.encode(), raw_body, hashlib.sha256).digest()).decode()
    app.config.update(ABACATEPAY_PUBLIC_KEY=public_key, ABACATEPAY_WEBHOOK_SECRET="query-secret")
    url = "/abacatepay-webhook?webhookSecret=query-secret"
    headers = {"Content-Type": "application/json", "X-Webhook-Signature": signature}

    first = client.post(url, data=raw_body, headers=headers)
    second = client.post(url, data=raw_body, headers=headers)
    assert first.status_code == 200
    assert second.get_json()["status"] == "duplicate"

    with app.app_context():
        assert db.session.get(User, user_id).plan == "vip"
        assert Transaction.query.filter_by(abacatepay_charge_id="pix-charge-1", status="completed").count() == 1
        assert PaymentWebhookEvent.query.filter_by(provider="abacatepay").count() == 1
