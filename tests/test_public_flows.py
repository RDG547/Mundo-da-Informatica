import app as app_module
from app import Category, ContentRequest, Post, User, app, db


def create_user(*, username="usuario", plan="free", role="user"):
    with app.app_context():
        user = User(
            username=username,
            email=f"{username}@example.test",
            password_hash="not-used-in-tests",
            plan=plan,
            role=role,
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()
        return user.id


def login(client, user_id):
    with client.session_transaction() as session:
        session.clear()
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def test_homepage_and_post_expose_technical_seo(client):
    with app.app_context():
        category = Category(name="BIOS", slug="bios", is_active=True, is_visible=True)
        post = Post(
            title="BIOS Lenovo LA-K091P",
            content="Arquivo de BIOS para consulta técnica.",
            download_link="https://example.test/bios.bin",
            category_rel=category,
            category_str="BIOS",
            slug="bios-lenovo-la-k091p",
            model="IdeaPad 3",
            board_code="LA-K091P",
            verification_status="verified",
            sha256="a" * 64,
            is_active=True,
        )
        db.session.add_all([category, post])
        db.session.commit()
        post_slug = post.slug

    home = client.get("/")
    assert home.status_code == 200
    assert "Encontre o arquivo certo para o reparo!" in home.get_data(as_text=True)
    assert "application/ld+json" in home.get_data(as_text=True)

    detail = client.get(f"/bios/{post_slug}")
    body = detail.get_data(as_text=True)
    assert detail.status_code == 200
    assert "LA-K091P" in body
    assert "a" * 64 in body
    assert 'rel="canonical"' in body
    assert "TechArticle" in body


def test_home_search_copy_and_footer_year(client):
    body = client.get("/").get_data(as_text=True)
    current_year = app_module.datetime.now(app_module.BRAZIL_TZ).year

    assert "Encontre o arquivo certo para o reparo!" in body
    assert "BIOS, EC, BoardView, esquemas e recursos técnicos organizados por modelo e placa." in body
    assert "Busca por modelo e placa" not in body
    assert "Recursos técnicos centralizados" not in body
    assert "Histórico conforme seu plano" not in body
    assert f'data-current-year>{current_year}</span>' in body


def test_content_requests_reuses_faq_visual_standard(client):
    faq_body = client.get("/faq").get_data(as_text=True)
    requests_body = client.get("/solicitacoes").get_data(as_text=True)

    assert 'class="faq-hero"' in faq_body
    assert 'class="faq-hero request-hero"' in requests_body
    assert 'id="faq-css"' in requests_body


def test_feature_modal_controller_is_available_from_first_page_load(client):
    home_body = client.get("/").get_data(as_text=True)
    categories_body = client.get("/categorias").get_data(as_text=True)

    expected_script = 'static/js/feature-modals.js'
    assert expected_script in home_body
    assert 'data-static-base-script="true"' in home_body
    assert 'class="feature-item" data-feature="verified"' in categories_body
    assert 'id="feature-modal"' in categories_body


def test_anonymous_suggestion_is_stored(client):
    response = client.post(
        "/solicitacoes",
        data={
            "request_type": "suggestion",
            "title": "Esquema LA-K091P",
            "board_code": "LA-K091P",
            "requester_name": "Pessoa Técnica",
            "requester_email": "pessoa@example.test",
        },
    )
    assert response.status_code == 302
    with app.app_context():
        request_item = ContentRequest.query.one()
        assert request_item.request_type == "suggestion"
        assert request_item.priority == 0


def test_only_vip_can_create_priority_request(client):
    free_user = create_user(username="free-user", plan="free")
    login(client, free_user)
    response = client.post(
        "/solicitacoes",
        data={"request_type": "vip_priority", "title": "BIOS rara"},
    )
    assert response.status_code == 302
    with app.app_context():
        assert ContentRequest.query.count() == 0

    vip_user = create_user(username="vip-user", plan="vip")
    login(client, vip_user)
    response = client.post(
        "/solicitacoes",
        data={"request_type": "vip_priority", "title": "BIOS rara"},
    )
    assert response.status_code == 302
    with app.app_context():
        request_item = ContentRequest.query.one()
        assert request_item.user_id == vip_user
        assert request_item.priority == 100


def test_admin_requests_page_is_protected(client):
    response = client.get("/admin/solicitacoes")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_hidden_category_is_not_publicly_addressable(client):
    with app.app_context():
        db.session.add(Category(name="Interna", slug="interna", is_active=True, is_visible=False))
        db.session.commit()

    assert client.get("/categoria/interna").status_code == 404


def test_empty_active_category_obeys_public_and_menu_controls(client):
    with app.app_context():
        db.session.add_all([
            Category(
                name="Sem posts pública",
                slug="sem-posts-publica",
                is_active=True,
                is_visible=True,
                show_in_menu=True,
            ),
            Category(
                name="Sem posts interna",
                slug="sem-posts-interna",
                is_active=True,
                is_visible=False,
                show_in_menu=True,
            ),
        ])
        db.session.commit()

    body = client.get("/").get_data(as_text=True)
    assert "Sem posts pública" in body
    assert "/categoria/sem-posts-publica" in body
    assert "Sem posts interna" not in body

    categories_body = client.get("/categorias").get_data(as_text=True)
    assert "Sem posts pública" in categories_body
    assert "/categoria/sem-posts-publica" in categories_body
    assert "Sem posts interna" not in categories_body


def test_platform_stats_render_even_when_all_values_are_zero(client):
    body = client.get("/sobre").get_data(as_text=True)
    assert "Dados da plataforma" in body
    assert "Downloads Realizados" in body
    assert "Usuários<br>Ativos" in body
    assert "Posts<br>Disponíveis" in body
    assert "Inscritos Newsletter" in body


def test_non_vip_priority_option_is_locked_in_ui(client):
    body = client.get("/solicitacoes").get_data(as_text=True)
    assert 'id="vipRequestLocked"' in body
    assert "Somente VIP" in body
    assert 'name="request_type" value="suggestion"' in body
