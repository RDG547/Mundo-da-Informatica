from io import BytesIO
import json
import os
import zipfile

import pytest
from sqlalchemy import create_engine, inspect

import app as app_module
from app import (
    ContentSource,
    Download,
    FileContribution,
    HardwareBoard,
    ImportItem,
    ImportJob,
    Post,
    SiteConfig,
    TechnicalFile,
    TechnicalResource,
    User,
    app,
    db,
    ensure_default_content_sources,
    publish_import_item,
    technical_auto_publish_decision,
)
from migrate_db import migrate
from technical_content.parsers import ArchiveSafetyError, inspect_zip_archive, normalize_board_code, parse_technical_filename
from technical_content.providers import LicensedJsonFeedProvider, ProviderRecord
from technical_content.storage import (
    HttpStorageProvider,
    UnsafeStorageUrl,
    UpstreamDownload,
    sanitize_download_name,
)


def _login(client, user_id):
    with client.session_transaction() as session:
        session['_user_id'] = str(user_id)
        session['_fresh'] = True


def _user(username, *, role='user', plan='vip'):
    user = User(
        username=username,
        email=f'{username}@example.test',
        password_hash='placeholder',
        role=role,
        plan=plan,
        is_active=True,
    )
    user.set_password('SenhaForte123!')
    db.session.add(user)
    db.session.commit()
    return user


def _technical_file(provider_url='https://download.mediafire.com/private/file.bin'):
    post = Post(title='BIOS privada', content='Teste', download_link='/download/pending', is_active=True)
    db.session.add(post)
    db.session.flush()
    resource = TechnicalResource(post_id=post.id, resource_type='bios', title=post.title)
    db.session.add(resource)
    db.session.flush()
    technical_file = TechnicalFile(
        resource_id=resource.id,
        post_id=post.id,
        display_filename='bios.bin',
        file_type='BIOS',
        extension='bin',
        storage_provider='http',
        provider_url=provider_url,
        provider_direct_url=provider_url,
        is_active=True,
    )
    db.session.add(technical_file)
    db.session.flush()
    post.download_link = f'/download/file/{technical_file.id}'
    db.session.commit()
    return post, technical_file


def test_filename_parser_normalizes_board_and_classifies_multi_file_scenario():
    bios = parse_technical_filename('Lenovo-Z460-LA-5751P-U3.bin')
    ec = parse_technical_filename('Lenovo Z460 LA 5751P U9.bin')
    schematic = parse_technical_filename('LA-5751P.pdf')
    boardview = parse_technical_filename('LA5751P.brd')

    assert normalize_board_code('LA-8131P') == normalize_board_code('la 8131p') == normalize_board_code('LA8131P')
    assert normalize_board_code(bios.board_code) == 'LA5751P'
    assert bios.file_type == 'BIOS' and bios.chip_position == 'U3'
    assert ec.file_type == 'Firmware EC' and ec.chip_position == 'U9'
    assert schematic.file_type == 'Esquema'
    assert boardview.file_type == 'BoardView'
    assert bios.confidence >= 80


def test_zip_inspection_rejects_traversal_and_reports_safe_members(tmp_path):
    safe = tmp_path / 'safe.zip'
    with zipfile.ZipFile(safe, 'w') as archive:
        archive.writestr('LA-5751P/U3.bin', b'bios')
        archive.writestr('LA-5751P/U9.bin', b'ec')
    assert [member.name for member in inspect_zip_archive(safe)] == ['LA-5751P/U3.bin', 'LA-5751P/U9.bin']

    unsafe = tmp_path / 'unsafe.zip'
    with zipfile.ZipFile(unsafe, 'w') as archive:
        archive.writestr('../escape.bin', b'bad')
    try:
        inspect_zip_archive(unsafe)
    except ArchiveSafetyError as exc:
        assert 'inseguro' in str(exc)
    else:
        raise AssertionError('Traversal deveria ser bloqueado')


def test_admin_upload_generates_preview_then_publishes_local_file(client, tmp_path):
    with app.app_context():
        admin = _user('technical_admin', role='admin')
        admin_id = admin.id
    _login(client, admin_id)
    app.config['TECHNICAL_IMPORT_TEMP_DIR'] = str(tmp_path / 'imports')
    app.config['TECHNICAL_LOCAL_STORAGE_DIR'] = str(tmp_path / 'storage')

    response = client.post('/api/admin/technical-import/analyze', data={
        'type': 'files',
        'source': 'Admin',
        'files': (BytesIO(b'firmware-content'), 'Lenovo-Z460-LA-5751P-U3.bin'),
    }, content_type='multipart/form-data')
    assert response.status_code == 201
    item_id = response.get_json()['job_id']
    with app.app_context():
        item = ImportItem.query.filter_by(job_id=item_id).one()
        assert item.status == 'pending_review'
        assert item.normalized_data()['board_code'] == 'LA-5751P'
        preview_id = item.id

    approved = client.post(f'/api/admin/technical-import/items/{preview_id}/approve')
    assert approved.status_code == 200
    post_id = approved.get_json()['post_id']
    with app.app_context():
        post = db.session.get(Post, post_id)
        technical_file = TechnicalFile.query.filter_by(post_id=post_id).one()
        board = HardwareBoard.query.one()
        assert post.download_link == f'/download/file/{technical_file.id}'
        assert technical_file.storage_provider == 'local'
        assert board.normalized_board_code == 'LA5751P'
        assert os.path.isfile(tmp_path / 'storage' / technical_file.provider_file_id)

    public_api = client.get(f'/api/posts/{post_id}')
    body = public_api.get_data(as_text=True)
    assert public_api.status_code == 200
    assert 'provider_url' not in body
    assert 'storage_provider' not in body
    assert 'technical-files' not in body


def test_proxy_streams_range_without_exposing_provider_and_records_plan(client, monkeypatch):
    with app.app_context():
        user = _user('proxy_vip', plan='vip')
        post, technical_file = _technical_file()
        user_id, file_id = user.id, technical_file.id
    _login(client, user_id)
    app.config['DOWNLOAD_DELIVERY_MODE'] = 'proxy'

    seen = {}
    def fake_open(_self, url, range_header=None):
        seen['url'] = url
        seen['range'] = range_header
        return UpstreamDownload(
            status_code=206,
            headers={
                'Content-Type': 'application/octet-stream',
                'Content-Length': '4',
                'Content-Range': 'bytes 2-5/8',
                'Accept-Ranges': 'bytes',
                'Content-Disposition': 'attachment; filename="Lenovo Z460 [U3] BIOS.bin"',
            },
            iterator=iter([b'2345']),
            close=lambda: None,
        )
    monkeypatch.setattr(app_module.HttpStorageProvider, 'open', fake_open)

    response = client.get(f'/download/file/{file_id}', headers={'Range': 'bytes=2-5'})
    assert response.status_code == 206
    assert response.data == b'2345'
    assert response.headers['Content-Range'] == 'bytes 2-5/8'
    assert 'Location' not in response.headers
    assert 'mediafire' not in response.get_data(as_text=True).lower()
    assert "Lenovo%20Z460%20%5BU3%5D%20BIOS.bin" in response.headers['Content-Disposition']
    assert seen['range'] == 'bytes=2-5'
    with app.app_context():
        record = Download.query.one()
        stored_file = db.session.get(TechnicalFile, file_id)
        assert record.technical_file_id == file_id
        assert record.plan_snapshot == 'vip'
        assert stored_file.display_filename == 'Lenovo Z460 [U3] BIOS.bin'
        assert stored_file.original_filename == 'Lenovo Z460 [U3] BIOS.bin'


def test_download_name_preserves_provider_identifiers():
    assert sanitize_download_name('Lenovo Z460 [U3] BIOS + EC.bin') == 'Lenovo Z460 [U3] BIOS + EC.bin'


def test_full_automation_requires_trusted_enabled_source_and_threshold(tmp_path):
    with app.app_context():
        ensure_default_content_sources()
        SiteConfig.set_value('technical_import_enabled', True, 'bool', is_public=False)
        SiteConfig.set_value('technical_automation_mode', 'full', is_public=False)
        SiteConfig.set_value('technical_automation_percentage', 100, 'int', is_public=False)
        SiteConfig.set_value('technical_auto_publish_threshold', 85, 'int', is_public=False)
        source = ContentSource.query.filter_by(name='Dell').one()
        source.distribution_allowed = True
        job = ImportJob(job_type='files', source='Dell', automation_mode='full')
        db.session.add(job)
        db.session.flush()
        path = tmp_path / 'Dell-Latitude-LA-1234-U3.bin'
        path.write_bytes(b'official-bios')
        metadata = {
            'original_name': path.name,
            'manufacturer': 'Dell',
            'model': 'Latitude',
            'board_code': 'LA-1234',
            'file_type': 'BIOS',
            'extension': 'bin',
            'confidence': 96,
            'distribution_policy': 'local_allowed',
            'copy': app_module.build_post_copy({'manufacturer': 'Dell', 'model': 'Latitude', 'board_code': 'LA-1234', 'file_type': 'BIOS'}),
        }
        item = ImportItem(
            job=job,
            source_name=path.name,
            status='pending_review',
            confidence=96,
            normalized_data_json=json.dumps(metadata),
            temp_path=str(path),
            sha256='a' * 64,
        )
        db.session.add(item)
        db.session.commit()
        allowed, reason = technical_auto_publish_decision(item, source)
        assert allowed is True
        assert 'Elegível' in reason

        source.enabled = False
        db.session.commit()
        allowed, reason = technical_auto_publish_decision(item, source)
        assert allowed is False
        assert 'fonte' in reason.lower()


def test_non_admin_cannot_use_import_api(client):
    with app.app_context():
        user_id = _user('normal_user', role='user').id
    _login(client, user_id)
    response = client.post('/api/admin/technical-import/analyze', data={'type': 'files'})
    assert response.status_code == 302


def test_additive_migration_creates_technical_tables_idempotently(tmp_path, monkeypatch):
    database = tmp_path / 'migration.db'
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{database}')
    migrate()
    migrate()
    tables = set(inspect(create_engine(f'sqlite:///{database}')).get_table_names())
    assert {
        'hardware_boards', 'technical_resources', 'technical_files',
        'import_jobs', 'import_items', 'content_sources', 'file_contributions',
    }.issubset(tables)


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f'HTTP {self.status_code}')


class _FakeProviderSession:
    def __init__(self, *, post_payload=None, get_payload=None):
        self.post_payload = post_payload or {}
        self.get_payload = get_payload or {}
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append(('POST', url, kwargs))
        return _FakeResponse(self.post_payload)

    def get(self, url, **kwargs):
        self.calls.append(('GET', url, kwargs))
        return _FakeResponse(self.get_payload)

    def request(self, method, url, **kwargs):
        return self.post(url, **kwargs) if method.upper() == 'POST' else self.get(url, **kwargs)


def test_licensed_feed_provider_is_parsed_with_mocked_http():
    session = _FakeProviderSession(get_payload={'items': [{
        'part_number': 'LA-8131P',
        'manufacturer': 'Parceiro autorizado',
        'title': 'BIOS E430C',
        'description': 'Metadados licenciados',
        'datasheet_url': 'https://storage.example.test/la-8131p.pdf',
        'product_url': 'https://catalog.example.test/la-8131p',
    }]})
    provider = LicensedJsonFeedProvider(
        'Feed licenciado',
        'https://catalog.example.test/api',
        'secret',
        session=session,
    )
    record = provider.lookup('LA-8131P')[0]
    assert record.part_number == 'LA-8131P'
    assert record.manufacturer == 'Parceiro autorizado'
    call = session.calls[0]
    assert call[2]['params']['q'] == 'LA-8131P'
    assert call[2]['headers']['Authorization'] == 'Bearer secret'


def test_storage_proxy_rejects_private_dns_resolution(monkeypatch):
    monkeypatch.setattr(
        'technical_content.storage.socket.getaddrinfo',
        lambda *_args, **_kwargs: [(2, 1, 6, '', ('127.0.0.1', 443))],
    )
    with pytest.raises(UnsafeStorageUrl):
        HttpStorageProvider().open('https://storage.example.test/firmware.bin')


def test_active_content_disguised_as_firmware_is_rejected(client):
    with app.app_context():
        admin_id = _user('security_admin', role='admin').id
    _login(client, admin_id)
    response = client.post('/api/admin/technical-import/analyze', data={
        'type': 'files',
        'source': 'Admin',
        'files': (BytesIO(b'<script>alert(1)</script>'), 'firmware.bin'),
    }, content_type='multipart/form-data')
    assert response.status_code == 400
    assert 'ativo' in response.get_json()['message'].lower()


def test_additive_migration_preserves_legacy_rows_and_extends_download(tmp_path, monkeypatch):
    database = tmp_path / 'legacy.db'
    database_url = f'sqlite:///{database}'
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.exec_driver_sql('CREATE TABLE "user" (id INTEGER PRIMARY KEY, plan VARCHAR(20))')
        connection.exec_driver_sql('CREATE TABLE posts (id INTEGER PRIMARY KEY, title VARCHAR(200))')
        connection.exec_driver_sql('CREATE TABLE download (id INTEGER PRIMARY KEY, user_id INTEGER, post_id INTEGER)')
        connection.exec_driver_sql("INSERT INTO \"user\" (id, plan) VALUES (1, 'free')")
        connection.exec_driver_sql("INSERT INTO posts (id, title) VALUES (1, 'Legado')")
        connection.exec_driver_sql('INSERT INTO download (id, user_id, post_id) VALUES (1, 1, 1)')
    monkeypatch.setenv('DATABASE_URL', database_url)
    migrate()
    migrate()
    with engine.connect() as connection:
        download_columns = {column['name'] for column in inspect(connection).get_columns('download')}
        assert {'technical_file_id', 'resource_id', 'plan_snapshot'}.issubset(download_columns)
        resource_columns = {column['name'] for column in inspect(connection).get_columns('technical_resources')}
        file_columns = {column['name'] for column in inspect(connection).get_columns('technical_files')}
        item_columns = {column['name'] for column in inspect(connection).get_columns('import_items')}
        contribution_columns = {column['name'] for column in inspect(connection).get_columns('file_contributions')}
        assert {'external_id', 'external_version', 'last_synced_at'}.issubset(resource_columns)
        assert 'last_link_http_status' in file_columns
        assert 'published_automatically' in item_columns
        assert 'import_item_id' in contribution_columns
        assert connection.exec_driver_sql('SELECT COUNT(*) FROM download').scalar_one() == 1


def test_configured_source_sync_creates_admin_preview_without_real_network(monkeypatch):
    from jobs import sync_configured_sources

    with app.app_context():
        ensure_default_content_sources()
        source = ContentSource.query.filter_by(name='Feed licenciado').one()
        source.config_json = json.dumps({'part_numbers': ['TPS51225']})
        db.session.commit()
        SiteConfig.set_value('technical_import_enabled', True, 'bool', is_public=False)
        SiteConfig.set_value('technical_automation_mode', 'semi', is_public=False)

    record = ProviderRecord(
        source='Feed licenciado',
        part_number='TPS51225',
        manufacturer='Texas Instruments',
        title='Power controller',
        description='Official metadata',
        datasheet_url='https://example.test/tps51225.pdf',
        product_url='https://example.test/product/tps51225',
        raw={'external_id': 'licensed-TPS51225', 'version': '1'},
    )
    monkeypatch.setattr(sync_configured_sources, '_records_for_source', lambda _source, _part: [record])
    result = sync_configured_sources.run({'Feed licenciado'})
    assert result['items'] == 1
    assert result['published'] == 0
    with app.app_context():
        job = ImportJob.query.one()
        item = ImportItem.query.one()
        source = ContentSource.query.filter_by(name='Feed licenciado').one()
        assert job.job_type == 'source_sync' and job.status == 'reviewing'
        assert item.status == 'pending_review'
        assert item.normalized_data()['external_id'] == 'licensed-TPS51225'
        assert source.last_sync_at is not None


def test_admin_center_renders_controls_and_board_enters_sitemap(client):
    with app.app_context():
        admin_id = _user('center_admin', role='admin').id
        board = HardwareBoard(
            board_code='LA-8131P',
            normalized_board_code='LA8131P',
            slug='la-8131p',
        )
        db.session.add(board)
        db.session.commit()
    _login(client, admin_id)
    center = client.get('/admin/tools/import')
    assert center.status_code == 200
    assert 'Controle da automação' in center.get_data(as_text=True)
    assert 'Sincronizar agora' in center.get_data(as_text=True)

    sitemap = client.get('/sitemap.xml')
    assert sitemap.status_code == 200
    assert '/placa/la-8131p' in sitemap.get_data(as_text=True)


def test_user_contribution_always_becomes_human_review_preview(client, tmp_path):
    app.config['TECHNICAL_IMPORT_TEMP_DIR'] = str(tmp_path / 'imports')
    app.config['TECHNICAL_LOCAL_STORAGE_DIR'] = str(tmp_path / 'storage')
    with app.app_context():
        user_id = _user('contributor', role='user').id
        admin_id = _user('contribution_admin', role='admin').id
    _login(client, user_id)
    uploaded = client.post('/contribuir-arquivo', data={
        'title': 'BIOS Lenovo Z460',
        'board_code': 'LA-5751P',
        'notes': 'Arquivo autorizado para revisão.',
        'file': (BytesIO(b'user-firmware'), 'Lenovo-Z460-LA-5751P-U3.bin'),
    }, content_type='multipart/form-data')
    assert uploaded.status_code == 201
    with app.app_context():
        contribution_id = FileContribution.query.one().id

    _login(client, admin_id)
    analyzed = client.post(f'/api/admin/technical-import/contributions/{contribution_id}/analyze')
    assert analyzed.status_code == 201
    item_id = analyzed.get_json()['item_id']
    with app.app_context():
        item = db.session.get(ImportItem, item_id)
        contribution = db.session.get(FileContribution, contribution_id)
        assert item.status == 'pending_review'
        assert item.job.automation_mode == 'semi'
        assert contribution.import_item_id == item.id

    approved = client.post(f'/api/admin/technical-import/items/{item_id}/approve')
    assert approved.status_code == 200
    with app.app_context():
        contribution = db.session.get(FileContribution, contribution_id)
        assert contribution.status == 'published'


def test_zip_members_for_same_board_share_one_post_and_resource(client, tmp_path):
    app.config['TECHNICAL_IMPORT_TEMP_DIR'] = str(tmp_path / 'imports')
    app.config['TECHNICAL_LOCAL_STORAGE_DIR'] = str(tmp_path / 'storage')
    with app.app_context():
        admin_id = _user('zip_admin', role='admin').id
    _login(client, admin_id)
    archive_buffer = BytesIO()
    with zipfile.ZipFile(archive_buffer, 'w') as archive:
        archive.writestr('LA-5751P-U3.bin', b'bios-file')
        archive.writestr('LA-5751P-U9.bin', b'ec-file')
        archive.writestr('LA-5751P.pdf', b'%PDF schematic')
        archive.writestr('LA-5751P.brd', b'boardview-file')
    archive_buffer.seek(0)
    analyzed = client.post('/api/admin/technical-import/analyze', data={
        'type': 'files',
        'source': 'Admin',
        'files': (archive_buffer, 'Lenovo-Z460-LA-5751P.zip'),
    }, content_type='multipart/form-data')
    assert analyzed.status_code == 201
    job_id = analyzed.get_json()['job_id']
    with app.app_context():
        item_ids = [item.id for item in ImportItem.query.filter_by(job_id=job_id).order_by(ImportItem.id.asc()).all()]
    assert len(item_ids) == 4
    for item_id in item_ids:
        assert client.post(f'/api/admin/technical-import/items/{item_id}/approve').status_code == 200
    with app.app_context():
        assert Post.query.count() == 1
        assert TechnicalResource.query.count() == 1
        files = TechnicalFile.query.order_by(TechnicalFile.id.asc()).all()
        assert len(files) == 4
        assert {'BIOS', 'Firmware EC', 'Esquema', 'BoardView'} == {file.file_type for file in files}
        assert len({file.post_id for file in files}) == 1


def test_admin_health_check_records_missing_local_file_as_broken(client, tmp_path):
    app.config['TECHNICAL_LOCAL_STORAGE_DIR'] = str(tmp_path / 'storage')
    with app.app_context():
        admin_id = _user('health_admin', role='admin').id
        _post, technical_file = _technical_file()
        technical_file.storage_provider = 'local'
        technical_file.provider_file_id = 'arquivo-ausente.bin'
        technical_file.provider_url = None
        technical_file.provider_direct_url = None
        db.session.commit()
        file_id = technical_file.id

    _login(client, admin_id)
    response = client.post(f'/api/admin/technical-import/files/{file_id}/health')

    assert response.status_code == 200
    assert response.get_json() == {
        'success': True,
        'online': False,
        'status': 'broken',
        'message': 'Arquivo local ausente.',
        'http_status': None,
    }
    with app.app_context():
        technical_file = db.session.get(TechnicalFile, file_id)
        assert technical_file.link_status == 'broken'
        assert technical_file.last_link_check_at is not None
