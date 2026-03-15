import json

import pytest

import app as app_module


@pytest.fixture
def client():
    app_module.app.config['TESTING'] = True
    with app_module.app.test_client() as client:
        yield client


def test_stripe_webhook_missing_signature_returns_400_and_does_not_process(client, monkeypatch):
    monkeypatch.setenv('STRIPE_WEBHOOK_SECRET', 'whsec_test')

    processed = {'called': False}

    def fake_handle_checkout_completed(_session):
        processed['called'] = True

    monkeypatch.setattr(app_module, 'handle_checkout_completed', fake_handle_checkout_completed)

    response = client.post(
        '/stripe-webhook',
        data=json.dumps({'type': 'checkout.session.completed', 'data': {'object': {'id': 'cs_test'}}}),
        content_type='application/json',
    )

    assert response.status_code == 400
    assert response.get_json() == {'error': 'Missing signature'}
    assert processed['called'] is False


def test_stripe_webhook_invalid_signature_returns_400_and_does_not_process(client, monkeypatch):
    monkeypatch.setenv('STRIPE_WEBHOOK_SECRET', 'whsec_test')

    processed = {'called': False}

    def fake_handle_checkout_completed(_session):
        processed['called'] = True

    def fake_construct_event(_payload, _sig_header, _secret):
        raise app_module.SignatureVerificationError('invalid signature', 'Stripe-Signature')

    monkeypatch.setattr(app_module, 'handle_checkout_completed', fake_handle_checkout_completed)
    monkeypatch.setattr(app_module.stripe.Webhook, 'construct_event', fake_construct_event)

    response = client.post(
        '/stripe-webhook',
        data=json.dumps({'type': 'checkout.session.completed', 'data': {'object': {'id': 'cs_test'}}}),
        headers={'Stripe-Signature': 't=1,v1=invalid'},
        content_type='application/json',
    )

    assert response.status_code == 400
    assert response.get_json() == {'error': 'Invalid signature'}
    assert processed['called'] is False


def test_stripe_webhook_valid_signature_processes_event(client, monkeypatch):
    monkeypatch.setenv('STRIPE_WEBHOOK_SECRET', 'whsec_test')

    processed = {'called': False, 'session_id': None}

    def fake_handle_checkout_completed(session):
        processed['called'] = True
        processed['session_id'] = session['id']

    def fake_construct_event(_payload, _sig_header, _secret):
        return {
            'type': 'checkout.session.completed',
            'data': {'object': {'id': 'cs_valid'}},
        }

    monkeypatch.setattr(app_module, 'handle_checkout_completed', fake_handle_checkout_completed)
    monkeypatch.setattr(app_module.stripe.Webhook, 'construct_event', fake_construct_event)

    response = client.post(
        '/stripe-webhook',
        data=json.dumps({'placeholder': True}),
        headers={'Stripe-Signature': 't=1,v1=valid'},
        content_type='application/json',
    )

    assert response.status_code == 200
    assert response.get_json() == {'status': 'success'}
    assert processed['called'] is True
    assert processed['session_id'] == 'cs_valid'
