from types import SimpleNamespace

import app as app_module
from app import Category, Post, User, app, db


def login_session(client, user_id):
    with client.session_transaction() as session:
        session.clear()
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def create_user(username, plan="free", role="user"):
    with app.app_context():
        user = User(
            username=username,
            email=f"{username}@example.test",
            password_hash="placeholder",
            plan=plan,
            role=role,
            is_active=True,
        )
        user.set_password("SenhaForte123!")
        db.session.add(user)
        db.session.commit()
        return user.id


def create_multi_file_post():
    with app.app_context():
        post = Post(
            title="Pacote BIOS e EC",
            content="Dois arquivos técnicos.",
            download_link="https://files.example.test/bios.bin",
            category_str="Geral",
            is_active=True,
        )
        post.set_metadata("download_files", [
            {"type": "BIOS", "url": "https://files.example.test/bios.bin", "name": "bios.bin", "size": "8 MB"},
            {"type": "BIOS", "url": "https://files.example.test/ec.bin", "name": "ec.bin", "size": "4 MB"},
        ])
        db.session.add(post)
        db.session.commit()
        return post.id


def test_register_preserves_selected_checkout_and_login_logout(client):
    response = client.post(
        "/register?plan=premium",
        data={
            "name": "Técnico Teste",
            "username": "tecnico_teste",
            "email": "tecnico@example.test",
            "password": "SenhaForte123!",
            "confirm_password": "SenhaForte123!",
            "terms": "on",
            "selected_plan": "premium",
        },
    )
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
    assert "checkout%3Dpremium" in response.headers["Location"]

    login = client.post(
        response.headers["Location"],
        data={"username_email": "tecnico@example.test", "password": "SenhaForte123!"},
    )
    assert login.status_code == 302
    assert "/planos?checkout=premium" in login.headers["Location"]

    logout = client.get("/logout")
    assert logout.status_code == 302


def test_download_requires_login_and_uses_file_index(client):
    post_id = create_multi_file_post()
    public_api = client.get(f"/api/posts/{post_id}")
    public_payload = public_api.get_json()
    assert public_api.status_code == 200
    assert "files.example.test" not in public_api.get_data(as_text=True)
    assert public_payload["download_files"][1]["url"] == f"/download/{post_id}?file=1"

    anonymous = client.get(f"/download/{post_id}?file=1")
    assert anonymous.status_code == 302
    assert "/login" in anonymous.headers["Location"]

    free_id = create_user("free_download", plan="free")
    login_session(client, free_id)
    first = client.get(f"/download/{post_id}?file=1")
    assert first.status_code == 302
    assert first.headers["Location"] == "https://files.example.test/ec.bin"

    limited = client.get(
        f"/download/{post_id}?file=0",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert limited.status_code == 403
    assert limited.get_json()["can_download"] is False


def test_vip_downloads_are_unlimited(client):
    post_id = create_multi_file_post()
    vip_id = create_user("vip_download", plan="vip")
    login_session(client, vip_id)

    for _ in range(3):
        response = client.get(f"/download/{post_id}?file=0")
        assert response.status_code == 302
        assert response.headers["Location"].startswith("https://files.example.test/")


def test_admin_requests_access_allowed(client):
    admin_id = create_user("admin_user", role="admin")
    login_session(client, admin_id)
    assert client.get("/admin/solicitacoes").status_code == 200


def test_post_detail_places_each_file_size_inside_download_button(client):
    post_id = create_multi_file_post()
    body = client.get(f"/post/{post_id}").get_data(as_text=True)
    assert '<span class="download-button-size">8 MB</span>' in body
    assert '<span class="download-button-size">4 MB</span>' in body


def test_admin_price_controls_card_checkout_and_public_api(client, monkeypatch):
    user_id = create_user("checkout_price", role="admin", plan="free")
    login_session(client, user_id)
    captured = {}

    settings_response = client.post("/admin/save_settings", json={
        "plan_price_premium": {"value": "43.21", "type": "float"},
    })
    assert settings_response.status_code == 200

    def fake_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(client_secret="secret-from-test")

    monkeypatch.setattr(app_module.stripe.checkout.Session, "create", fake_create)
    response = client.post("/create-checkout-session", json={"plan": "premium"})
    assert response.status_code == 200
    assert response.get_json()["clientSecret"] == "secret-from-test"
    assert captured["line_items"][0]["price_data"]["unit_amount"] == 4321
    assert captured["line_items"][0]["price_data"]["recurring"] == {"interval": "month"}

    public_prices = client.get("/api/plan-prices").get_json()
    assert public_prices["plans"]["premium"]["amount_cents"] == 4321


def test_admin_category_bulk_actions_remain_functional(client):
    admin_id = create_user("bulk_category_admin", role="admin")
    login_session(client, admin_id)
    with app.app_context():
        category = Category(name="Categoria em lote", slug="categoria-em-lote", is_active=True)
        db.session.add(category)
        db.session.commit()
        category_id = category.id

    response = client.post("/admin/categories/bulk-action", json={
        "action": "toggle-status",
        "category_ids": [category_id],
    })
    assert response.status_code == 200
    assert response.get_json()["success"] is True
    with app.app_context():
        assert db.session.get(Category, category_id).is_active is False


def test_dashboard_refresh_returns_stable_database_values(client):
    admin_id = create_user("dashboard_admin", role="admin")
    login_session(client, admin_id)
    first = client.get("/admin/dashboard/stats")
    second = client.get("/admin/dashboard/stats")
    assert first.status_code == second.status_code == 200
    assert first.get_json()["stats"] == second.get_json()["stats"]


def test_regular_user_can_update_own_profile_with_server_validation(client):
    user_id = create_user("profile_user")
    login_session(client, user_id)

    updated = client.post(
        "/admin/update-profile",
        data={
            "name": "Técnica Responsável",
            "username": "profile_user",
            "email": "PROFILE@EXAMPLE.TEST",
            "bio": "Reparo de placas.",
            "github": "https://github.com/profile-user",
        },
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert updated.status_code == 200
    assert updated.get_json()["success"] is True

    rejected = client.post(
        "/admin/update-profile",
        data={
            "name": "Técnica Responsável",
            "username": "profile_user",
            "email": "profile@example.test",
            "github": "javascript:alert(1)",
        },
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert rejected.status_code == 400
    with app.app_context():
        user = db.session.get(User, user_id)
        assert user.name == "Técnica Responsável"
        assert user.email == "profile@example.test"
        assert user.github == "https://github.com/profile-user"


def test_free_comment_daily_limit_is_enforced(client):
    post_id = create_multi_file_post()
    user_id = create_user("comment_user", plan="free")
    login_session(client, user_id)

    for index in range(3):
        response = client.post(
            f"/post/{post_id}/comments",
            json={"content": f"Comentário técnico {index}"},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        assert response.status_code == 201

    limited = client.post(
        f"/post/{post_id}/comments",
        json={"content": "Comentário excedente"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert limited.status_code == 403
    assert "3 comentários" in limited.get_json()["message"]
