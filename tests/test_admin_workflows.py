from datetime import datetime, timedelta

from app import (
    Category,
    Comment,
    Post,
    ScheduledPost,
    Subcategory,
    User,
    VisitorLog,
    app,
    db,
    publish_due_scheduled_posts,
)


def _login(client, user_id):
    with client.session_transaction() as session:
        session['_user_id'] = str(user_id)
        session['_fresh'] = True


def _admin(username='workflow_admin'):
    user = User(
        username=username,
        email=f'{username}@example.test',
        password_hash='placeholder',
        role='admin',
        plan='free',
        is_active=True,
    )
    user.set_password('SenhaForte123!')
    db.session.add(user)
    db.session.commit()
    return user


def test_admin_can_schedule_post_and_due_job_publishes_it(client):
    with app.app_context():
        admin = _admin()
        category = Category(name='BIOS', slug='bios', is_active=True, is_visible=True)
        db.session.add(category)
        db.session.commit()
        admin_id, category_id = admin.id, category.id

    _login(client, admin_id)
    future_local = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M')
    response = client.post(
        '/admin/posts/create',
        data={
            'title': 'Post agendado',
            'content': 'Conteúdo técnico agendado.',
            'category': str(category_id),
            'download_link': 'https://www.mediafire.com/file/teste/arquivo.bin/file',
            'status': 'scheduled',
            'publish_date': future_local,
        },
        headers={'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest'},
    )

    assert response.status_code == 200
    assert response.get_json()['post']['publication_status'] == 'scheduled'

    listing = client.get('/admin/posts?status=scheduled')
    assert listing.status_code == 200
    assert b'Post agendado' in listing.data
    assert b'Agendado' in listing.data

    with app.app_context():
        post = Post.query.filter_by(title='Post agendado').one()
        schedule = ScheduledPost.query.filter_by(post_id=post.id).one()
        assert post.is_active is False
        assert schedule.status == 'pending'

        schedule.scheduled_for = datetime.utcnow() - timedelta(seconds=1)
        db.session.commit()
        assert publish_due_scheduled_posts() == 1

        db.session.refresh(post)
        db.session.refresh(schedule)
        assert post.is_active is True
        assert schedule.status == 'published'
        assert schedule.published_at is not None


def test_post_modals_render_single_icon_type_select_and_embedded_schedule(client):
    with app.app_context():
        admin = _admin('modal_admin')
        category = Category(name='BIOS', slug='bios', is_active=True, is_visible=True)
        db.session.add(category)
        db.session.commit()
        admin_id = admin.id

    _login(client, admin_id)
    response = client.get('/admin/posts')
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'class="schedule-picker"' in body
    assert 'id="publishDateDay"' in body
    assert 'id="publishHour"' in body
    assert 'id="publishMinute"' in body
    assert 'id="publishDate" name="publish_date"' in body
    assert 'download-type-select icon-select-native" data-project-select="native"' in body
    assert 'download-size-unit icon-select-native" data-project-select="native"' in body
    assert '#editPostModal .icon-select[data-source-select="editPostCategory"] .icon-select-menu' in body

    download_type_select = body.split('name="download_type_0"', 1)[1].split('</select>', 1)[0]
    assert download_type_select.index('value="BIOS"') < download_type_select.index('value="EC"')
    assert download_type_select.index('value="EC"') < download_type_select.index('value="BoardView"')
    assert download_type_select.index('value="BoardView"') < download_type_select.index('value="ME"')


def test_comment_moderation_uses_json_without_redirect_and_bulk_persists(client):
    with app.app_context():
        admin = _admin('comments_admin')
        post = Post(
            title='Post com comentários',
            content='Conteúdo.',
            download_link='https://example.test/arquivo.bin',
            is_active=True,
        )
        db.session.add(post)
        db.session.flush()
        first = Comment(content='Primeiro', author_name='Autor 1', post_id=post.id)
        second = Comment(content='Segundo', author_name='Autor 2', post_id=post.id)
        db.session.add_all([first, second])
        db.session.commit()
        admin_id, first_id, second_id = admin.id, first.id, second.id

    _login(client, admin_id)
    headers = {'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest'}
    approved = client.post(f'/admin/comments/{first_id}/approve', headers=headers)
    assert approved.status_code == 200
    assert approved.is_json
    assert approved.get_json()['status'] == 'approved'

    bulk = client.post(
        '/admin/comments/bulk',
        json={'action': 'reject', 'comment_ids': [second_id]},
        headers=headers,
    )
    assert bulk.status_code == 200
    assert bulk.is_json
    assert bulk.get_json()['action'] == 'rejected'

    with app.app_context():
        assert db.session.get(Comment, first_id).status == 'approved'
        assert db.session.get(Comment, second_id).status == 'rejected'


def test_admin_manages_nested_subcategories_and_parent_includes_descendant_posts(client):
    with app.app_context():
        admin = _admin('subcategory_admin')
        category = Category(name='BIOS', slug='bios', is_active=True, is_visible=True, show_in_menu=True)
        db.session.add(category)
        db.session.commit()
        admin_id, category_id = admin.id, category.id

    _login(client, admin_id)
    headers = {'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest'}
    version_before = client.get('/api/public-content-version').get_json()['version']

    root_response = client.post('/admin/subcategories', json={
        'category_id': category_id, 'name': 'BIOS Notebook', 'slug': 'bios-notebook',
    }, headers=headers)
    assert root_response.status_code == 201
    root_id = root_response.get_json()['subcategory_id']

    brand_response = client.post('/admin/subcategories', json={
        'category_id': category_id, 'parent_id': root_id, 'name': 'HP', 'slug': 'bios-notebook-hp',
    }, headers=headers)
    assert brand_response.status_code == 201
    brand_id = brand_response.get_json()['subcategory_id']

    with app.app_context():
        post = Post(
            title='BIOS HP EliteBook', slug='bios-hp-elitebook', content='Firmware de teste.',
            category_id=category_id, category_str='BIOS', subcategory_id=brand_id,
            subcategory='bios-notebook-hp', download_link='https://example.test/bios.bin', is_active=True,
        )
        db.session.add(post)
        db.session.commit()

    parent_page = client.get('/subcategoria/bios-notebook').get_data(as_text=True)
    assert 'BIOS HP EliteBook' in parent_page
    assert 'category-tree-item' in parent_page
    assert client.get('/api/public-content-version').get_json()['version'] != version_before

    renamed = client.put(f'/admin/subcategories/{brand_id}', json={
        'category_id': category_id, 'parent_id': root_id, 'name': 'HP Corporativo',
        'slug': 'bios-notebook-hp-corporativo',
    }, headers=headers)
    assert renamed.status_code == 200
    with app.app_context():
        post = Post.query.filter_by(title='BIOS HP EliteBook').one()
        assert post.subcategory == 'bios-notebook-hp-corporativo'

    deleted = client.delete(f'/admin/subcategories/{root_id}', headers=headers)
    assert deleted.status_code == 200
    with app.app_context():
        assert db.session.get(Subcategory, root_id) is None
        post = Post.query.filter_by(title='BIOS HP EliteBook').one()
        assert post.subcategory_id is None


def test_admin_can_exclude_self_from_statistics_and_ajax_delete_is_json(client):
    with app.app_context():
        admin = _admin('statistics_admin')
        disposable = _admin('disposable_admin')
        db.session.add(VisitorLog(ip_address='127.0.0.1', user_id=admin.id))
        db.session.commit()
        admin_id, disposable_id = admin.id, disposable.id

    _login(client, admin_id)
    headers = {'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest'}
    excluded = client.post(
        f'/admin/users/{admin_id}/statistics', json={'excluded': True}, headers=headers,
    )
    assert excluded.status_code == 200
    assert excluded.get_json()['user']['exclude_from_statistics'] is True
    with app.app_context():
        assert db.session.get(User, admin_id).exclude_from_statistics is True
        assert VisitorLog.query.filter_by(user_id=admin_id).count() == 0

    deleted = client.post(f'/admin/users/{disposable_id}/delete', headers=headers)
    assert deleted.status_code == 200
    assert deleted.is_json
    assert deleted.get_json()['user_id'] == disposable_id


def test_admin_user_page_exposes_granular_live_controls(client):
    with app.app_context():
        admin = _admin('users_live_admin')
        admin_id = admin.id
    _login(client, admin_id)
    body = client.get('/admin/users?page=2').get_data(as_text=True)
    assert 'data-user-statistics=' in body
    assert 'window.syncUserRow?.(userId)' in body
    assert '__adminUsersLiveTimer' in body
