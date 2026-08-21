from types import SimpleNamespace

import app as app_module
from app import (
    Category,
    Favorite,
    NewsletterGroup,
    Post,
    Subscriber,
    TechnicalFile,
    User,
    _get_chat_permissions_for_user,
    app,
    can_request_specific_content,
    check_device_limit,
    check_download_history_access,
    check_favorite_limit,
    check_support_priority,
    check_user_download_limit,
    db,
)


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
            {"type": "EC", "url": "https://files.example.test/ec.bin", "name": "ec.bin", "size": "4 MB"},
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


def test_admin_role_does_not_bypass_free_plan_entitlements(client, monkeypatch):
    post_id = create_multi_file_post()
    admin_id = create_user("admin_free_limits", role="admin", plan="free")
    login_session(client, admin_id)

    first = client.get(f"/download/{post_id}?file=0")
    limited = client.get(
        f"/download/{post_id}?file=1",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert first.status_code == 302
    assert limited.status_code == 403

    for index in range(3):
        response = client.post(
            f"/post/{post_id}/comments",
            json={"content": f"Comentário administrativo {index}"},
        )
        assert response.status_code == 201
    fourth_comment = client.post(
        f"/post/{post_id}/comments",
        json={"content": "Comentário administrativo acima do limite"},
    )
    assert fourth_comment.status_code == 403

    monkeypatch.setattr(app_module, "_get_firestore_client", lambda: None)
    monkeypatch.setattr(app_module, "is_firebase_admin_configured", lambda: False)
    bootstrap = client.get("/api/chat/bootstrap")
    assert bootstrap.status_code == 200
    assert bootstrap.get_json()["permissions"] == {
        "public_read": False,
        "public_write": False,
        "support_read": True,
        "support_write": True,
        "vip_area": False,
    }

    with app.app_context():
        user = db.session.get(User, admin_id)
        user.active_sessions = 1
        db.session.commit()
        assert check_user_download_limit(user)[0] is False
        assert check_download_history_access(user) == (False, 0)
        assert check_device_limit(user)[0] is False
        assert check_support_priority(user) == "Suporte em até 48h"
        assert can_request_specific_content(user) is False
        permissions = _get_chat_permissions_for_user(user)
        assert permissions["public_write"] is False
        assert permissions["support_write"] is True


def test_admin_role_does_not_bypass_premium_plan_limits():
    admin_id = create_user("admin_premium_limits", role="admin", plan="premium")
    with app.app_context():
        user = db.session.get(User, admin_id)
        user.weekly_downloads = 15
        user.active_sessions = 2
        db.session.commit()
        assert check_user_download_limit(user)[0] is False
        assert check_download_history_access(user) == (True, 5)
        assert check_device_limit(user)[0] is False
        assert check_support_priority(user) == "Suporte em até 24h"
        assert can_request_specific_content(user) is False
        assert _get_chat_permissions_for_user(user)["public_write"] is False


def test_admin_role_respects_free_favorite_limit():
    admin_id = create_user("admin_favorite_limits", role="admin", plan="free")
    with app.app_context():
        for index in range(10):
            post = Post(
                title=f"Post {index}",
                content="Conteúdo",
                download_link=f"https://files.example.test/{index}.bin",
                is_active=True,
            )
            db.session.add(post)
            db.session.flush()
            db.session.add(Favorite(user_id=admin_id, post_id=post.id))
        db.session.commit()
        allowed, message = check_favorite_limit(db.session.get(User, admin_id))
        assert allowed is False
        assert "10 favoritos" in message


def test_post_detail_places_each_file_size_inside_download_button(client):
    post_id = create_multi_file_post()
    body = client.get(f"/post/{post_id}").get_data(as_text=True)
    assert '<span class="download-button-size">8 MB</span>' in body
    assert '<span class="download-button-size">4 MB</span>' in body
    assert '<span>Download BIOS</span>' in body
    assert '<span>Download EC</span>' in body
    assert "Download bios.bin" not in body
    assert "Download ec.bin" not in body
    assert body.count("Miniatura ilustrativa") == 1
    assert body.count("<strong>Atenção:</strong>") == 1


def test_download_metadata_remains_source_of_truth_after_out_of_order_download(client):
    post_id = create_multi_file_post()
    with app.app_context():
        db.session.add_all([
            TechnicalFile(
                post_id=post_id, display_filename="arquivo-generico.bin", file_type="Arquivo",
                storage_provider="http", provider_url="https://files.example.test/ec.bin",
                provider_direct_url="https://files.example.test/ec.bin", is_active=True,
            ),
            TechnicalFile(
                post_id=post_id, display_filename="tipo-incorreto.bin", file_type="EC",
                storage_provider="http", provider_url="https://files.example.test/bios.bin",
                provider_direct_url="https://files.example.test/bios.bin", is_active=True,
            ),
        ])
        db.session.commit()

    payload = client.get(f"/api/posts/{post_id}").get_json()
    assert [item["type"] for item in payload["download_files"]] == ["BIOS", "EC"]

    vip_id = create_user("download_order", plan="vip")
    login_session(client, vip_id)
    response = client.get(f"/download/{post_id}?file=0")
    assert response.status_code == 302
    assert response.headers["Location"] == "https://files.example.test/bios.bin"


def test_admin_post_modals_use_simplified_file_fields_and_visual_steps(client):
    admin_id = create_user("post_modal_admin", role="admin")
    with app.app_context():
        db.session.add(Category(name="BIOS", slug="bios", is_active=True, is_visible=True))
        db.session.commit()
    login_session(client, admin_id)

    body = client.get("/admin/posts").get_data(as_text=True)
    assert body.count('class="steps-progress-track"') == 2
    assert "Informações técnicas" not in body
    assert "Nome do arquivo (opcional)" not in body
    assert "SHA-256 (opcional)" not in body
    assert 'data-icon="fas fa-microchip" data-color="#3a86ff">BIOS</option>' in body
    assert 'data-icon="fas fa-project-diagram"' in body
    assert body.count('data-value="verified" data-icon="fas fa-check-circle"') == 2
    assert body.index('name="download_size_unit_0"') < body.index('name="download_size_0"')
    assert "window.enhanceDownloadTypeSelect" in body


def test_search_suggestions_expose_all_download_file_types(client):
    create_multi_file_post()
    payload = client.get("/api/search/suggestions?q=Pacote").get_json()
    suggestion = next(item for item in payload if item["type"] == "post")
    assert suggestion["file_types"] == ["BIOS", "EC"]
    assert "BIOS/EC" in suggestion["description"]


def test_newsletter_group_counts_use_real_active_subscribers(client):
    admin_id = create_user("newsletter_admin", role="admin")
    login_session(client, admin_id)
    with app.app_context():
        active = Subscriber(email="active@example.test", is_active=True)
        inactive = Subscriber(email="inactive@example.test", is_active=False)
        group = NewsletterGroup(name="Técnicos", description="Grupo real")
        group.subscribers.extend([active, inactive])
        db.session.add_all([active, inactive, group])
        db.session.commit()

    body = client.get("/admin/newsletter").get_data(as_text=True)
    assert "450" not in body
    assert "280" not in body
    assert "170" not in body
    assert "Técnicos" in body
    assert "Grupo real" in body


def test_profile_sidebar_and_thumbnail_preference_use_platform_layout(client):
    user_id = create_user("profile_navigation", role="admin")
    login_session(client, user_id)
    body = client.get("/profile").get_data(as_text=True)
    sidebar = body.split('<aside class="profile-admin-sidebar">', 1)[1].split("</aside>", 1)[0]
    management = sidebar.split("GERENCIAMENTO", 1)[1].split("CONFIGURAÇÕES", 1)[0]
    assert ">Posts<" not in sidebar
    assert ">Categorias<" not in sidebar
    assert "Editar Perfil" in management
    assert "Alterar Senha" in management
    assert 'id="thumbnailPreferenceModal"' in body
    assert "alert('O aviso sobre miniaturas" not in body


def test_admin_recent_posts_table_has_header_icons_and_valid_action_icon(client):
    admin_id = create_user("recent_posts_admin", role="admin")
    login_session(client, admin_id)
    create_multi_file_post()
    body = client.get("/admin").get_data(as_text=True)
    assert 'dashboard-recent-posts-table' in body
    for icon in ("fa-heading", "fa-folder", "fa-calendar-alt", "fa-eye", "fa-download", "fa-toggle-on", "fa-sliders-h"):
        assert icon in body
    assert "fa-star-o" not in body


def test_admin_user_information_is_read_only_and_reset_is_inside_edit(client):
    admin_id = create_user("users_layout_admin", role="admin")
    create_user("managed_user")
    login_session(client, admin_id)
    body = client.get("/admin/users").get_data(as_text=True)
    info_modal = body.split('id="userInfoModal"', 1)[1].split("{% endblock %}", 1)[0]
    assert "Cadastro" in info_modal
    assert "Último acesso" in info_modal
    assert "Dados de Rastreamento" in info_modal
    assert 'id="infoUsername"' not in info_modal
    assert 'id="saveUserInfo"' not in info_modal
    assert 'onclick="openResetPasswordFromEdit()"' in body
    assert 'data-admin-action="reset-password"' not in body


def test_faq_chat_uses_support_widget_instead_of_placeholder_alert(client):
    user_id = create_user("faq_support_user", plan="free")
    login_session(client, user_id)
    body = client.get("/faq").get_data(as_text=True)
    assert "openFaqSupportChat(event)" in body
    assert "chat online estará disponível em breve" not in body.lower()
    assert "faq-support-cta" in body


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


def test_admin_controls_plan_name_and_payment_methods(client):
    user_id = create_user("plan_configuration", role="admin", plan="free")
    login_session(client, user_id)

    response = client.post("/admin/save_settings", json={
        "plan_name_premium": {"value": "Profissional", "type": "string"},
        "plan_card_enabled_premium": {"value": False, "type": "bool"},
        "plan_pix_enabled_premium": {"value": True, "type": "bool"},
    })
    assert response.status_code == 200

    public_config = client.get("/api/plan-prices").get_json()["plans"]["premium"]
    assert public_config["label"] == "Profissional"
    assert public_config["card_enabled"] is False
    assert public_config["pix_enabled"] is True

    plans_body = client.get("/planos").get_data(as_text=True)
    assert 'data-plan-name="premium">Profissional</' in plans_body
    assert 'data-plan-card-enabled="false"' in plans_body
    assert ".payment-unavailable[hidden]" in plans_body
    assert '<div class="faq-item active"' not in plans_body

    card_response = client.post("/create-checkout-session", json={"plan": "premium"})
    assert card_response.status_code == 409
    assert "cartão" in card_response.get_json()["error"]

    response = client.post("/admin/save_settings", json={
        "plan_card_enabled_premium": {"value": True, "type": "bool"},
        "plan_pix_enabled_premium": {"value": False, "type": "bool"},
    })
    assert response.status_code == 200
    pix_response = client.post("/create-pix-checkout", json={"plan": "premium"})
    assert pix_response.status_code == 409
    assert "PIX" in pix_response.get_json()["error"]


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
