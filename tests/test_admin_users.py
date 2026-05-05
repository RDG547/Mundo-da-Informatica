from datetime import datetime, timedelta
import inspect

import app as app_module


class FakeUserQuery:
    def __init__(self, users):
        self._users = users

    def order_by(self, *_args, **_kwargs):
        return self

    def all(self):
        return list(self._users)


def make_user(index, role='user', is_active=True):
    user = app_module.User(
        username=f'user{index:02d}',
        email=f'user{index:02d}@example.com',
        name=f'User {index:02d}',
        role=role,
        is_active=is_active,
        date_joined=datetime(2026, 1, 1) + timedelta(days=index),
    )
    user.id = index
    user.password_hash = 'hash'
    return user


def test_admin_users_uses_global_totals_and_clamps_requested_page(monkeypatch):
    users = [make_user(1, role='admin')]
    users.extend(make_user(index, role='editor') for index in range(2, 4))
    users.extend(make_user(index, role='user', is_active=index != 12) for index in range(4, 13))

    captured = {}

    monkeypatch.setattr(app_module.User, 'query', FakeUserQuery(users), raising=False)
    monkeypatch.setattr(app_module, 'get_admin_sidebar_stats', lambda: {})

    def fake_render(template_name, **context):
        captured['template_name'] = template_name
        captured['context'] = context
        return context

    monkeypatch.setattr(app_module, 'render_template', fake_render)

    view = inspect.unwrap(app_module.admin_users)

    with app_module.app.test_request_context('/admin/users?page=99'):
        response_context = view()

    context = captured['context']
    pagination = context['pagination']
    totals = context['user_totals']

    assert captured['template_name'] == 'admin/users.html'
    assert response_context is context
    assert totals == {
        'total': 12,
        'admins': 1,
        'editors': 2,
        'users': 9,
        'active': 11,
    }
    assert pagination.total == 12
    assert pagination.pages == 2
    assert pagination.page == 2
    assert [user.id for user in context['users']] == [11, 12]
