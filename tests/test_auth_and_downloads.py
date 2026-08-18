from app import Post, User, app, db


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
            is_active=True,
        )
        post.set_metadata("download_files", [
            {"type": "BIOS", "url": "https://files.example.test/bios.bin", "name": "bios.bin"},
            {"type": "BIOS", "url": "https://files.example.test/ec.bin", "name": "ec.bin"},
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
