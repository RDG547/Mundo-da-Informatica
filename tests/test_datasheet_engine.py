from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import create_engine, inspect

import app as app_module
from app import (
    BoardComponent, DatasheetDocument, DatasheetImportQueue, DatasheetProviderConfig,
    ElectronicComponent, HardwareBoard, Post, SiteConfig, User, app, db, ensure_default_datasheet_providers,
    materialize_datasheet_component,
)
from migrate_db import migrate
from technical_content.datasheets.normalization import normalize_manufacturer, normalize_part_number
from technical_content.datasheets.policy import provider_query_policy, publication_policy
from technical_content.datasheets.providers import SourcePartsProvider
from technical_content.datasheets.providers.base import (
    DatasheetProvider, ProviderRateLimitError, SlidingWindowLimiter,
)
from technical_content.datasheets.services.resolver import ConfiguredProvider, DatasheetResolver
from technical_content.datasheets.types import DatasheetCandidate


def _login(client, user_id):
    with client.session_transaction() as session:
        session['_user_id'] = str(user_id)
        session['_fresh'] = True


class _Response:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status_code = status
        self.headers = {'Content-Type': 'application/json'}
        self.text = ''

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f'HTTP {self.status_code}')


class _SourceSession:
    def __init__(self):
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if url.endswith('/parts/search'):
            return _Response({'results': [{
                'sku': 'source-sku-123', 'mpn': 'TPS51225C', 'manufacturer': 'TI',
                'package': 'QFN', 'datasheet_url': 'https://cdn.example.test/tps.pdf',
            }]})
        if url.endswith('/specs'):
            return _Response({'specifications': {'Input Voltage': '4.5 V to 28 V'}})
        if url.endswith('/datasheet'):
            return _Response({'url': 'https://cdn.example.test/tps.pdf', 'pages': 48})
        return _Response({'package': 'QFN', 'lifecycle_status': 'Active'})


class _StaticProvider(DatasheetProvider):
    def __init__(self, name, candidates):
        super().__init__(retry_limit=0)
        self.name = name
        self.candidates = candidates

    def search(self, _part_number):
        return list(self.candidates)

    def normalize(self, raw, query):  # pragma: no cover - interface obrigatória
        raise NotImplementedError


def _config(**overrides):
    values = {
        'enabled': True, 'mode': 'semi_automatic', 'api_enabled': True,
        'html_discovery_enabled': False, 'written_permission_confirmed': False,
        'source_policy_allows_html_discovery': False, 'robots_allowed': False,
        'priority': 1, 'auto_publish_threshold': 0.95,
        'metadata_persistence_allowed': False, 'public_republish_allowed': False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_normalization_preserves_relevant_suffix_and_manufacturer_alias():
    assert normalize_part_number('TPS-51225 C') == 'TPS51225C'
    assert normalize_part_number('TPS51225C') != normalize_part_number('TPS51225')
    assert normalize_manufacturer('Texas Instruments Inc.') == 'Texas Instruments'


def test_source_parts_uses_bearer_user_agent_and_search_sku_for_details():
    session = _SourceSession()
    provider = SourcePartsProvider('secret', 'MundoDaInformatica/1.0 (support@example.test)', session=session)
    candidates = provider.search('TPS51225C')
    candidate = candidates[0]
    assert candidate.part_number == 'TPS51225C'
    assert candidate.external_id == 'source-sku-123'
    assert candidate.specifications['Input Voltage'] == '4.5 V to 28 V'
    assert candidate.pages == 48
    assert any('/parts/source-sku-123/specs' in call[1] for call in session.calls)
    assert session.calls[0][2]['headers']['Authorization'] == 'Bearer secret'
    assert session.calls[0][2]['headers']['User-Agent'].startswith('MundoDaInformatica/')


def test_html_and_publication_are_denied_without_explicit_permissions():
    html_decision = provider_query_policy(
        _config(html_discovery_enabled=True, api_enabled=False), channel='html',
    )
    assert html_decision.allowed is False and html_decision.status == 'blocked_by_policy'
    publication = publication_policy(
        _config(mode='automatic', metadata_persistence_allowed=True), confidence=.99,
        has_conflicts=False, duplicate=False, required_fields_present=True,
        global_auto_publish=True,
    )
    assert publication.allowed is False
    assert 'republicação' in publication.reason


def test_publication_modes_and_provider_health_guard_automatic_flow():
    allowed = publication_policy(
        _config(
            mode='automatic', metadata_persistence_allowed=True,
            public_republish_allowed=True, written_permission_confirmed=True,
            provider_status='online',
        ),
        confidence=.99, has_conflicts=False, duplicate=False,
        required_fields_present=True, global_auto_publish=True,
    )
    assert allowed.allowed is True and allowed.status == 'approved'
    semi = publication_policy(
        _config(
            mode='semi_automatic', metadata_persistence_allowed=True,
            public_republish_allowed=True, written_permission_confirmed=True,
            provider_status='online',
        ),
        confidence=1.0, has_conflicts=False, duplicate=False,
        required_fields_present=True, global_auto_publish=True,
    )
    assert semi.allowed is False and semi.status == 'needs_review'
    unhealthy = publication_policy(
        _config(
            mode='automatic', metadata_persistence_allowed=True,
            public_republish_allowed=True, written_permission_confirmed=True,
            provider_status='failed',
        ),
        confidence=1.0, has_conflicts=False, duplicate=False,
        required_fields_present=True, global_auto_publish=True,
    )
    assert unhealthy.allowed is False and 'saúde' in unhealthy.reason


def test_disabled_provider_is_not_called_and_rate_limit_is_independent():
    candidate = DatasheetCandidate(
        provider='disabled', external_id='1', part_number='RT8206A',
        normalized_part_number='RT8206A', confidence=1.0, exact_match=True,
    )
    provider = _StaticProvider('disabled', [candidate])
    resolver = DatasheetResolver([ConfiguredProvider(provider, _config(enabled=False))])
    resolution = resolver.resolve('RT8206A')
    assert not resolution.found
    assert resolution.traces[0].status == 'disabled'
    limiter = SlidingWindowLimiter(1, 100, 100)
    limiter.check()
    try:
        limiter.check()
    except ProviderRateLimitError:
        pass
    else:  # pragma: no cover - garante que o limiter nunca seja silenciosamente removido
        raise AssertionError('O limite independente do provider não foi aplicado.')


def test_provider_failure_does_not_interrupt_fallback():
    class _OfflineProvider(_StaticProvider):
        def search(self, _part_number):
            raise RuntimeError('offline')

    available = DatasheetCandidate(
        provider='available', external_id='2', part_number='IT8587E',
        normalized_part_number='IT8587E', manufacturer='ITE',
        normalized_manufacturer='ITE', confidence=.98, exact_match=True,
    )
    resolver = DatasheetResolver([
        ConfiguredProvider(_OfflineProvider('offline', []), _config(priority=1)),
        ConfiguredProvider(_StaticProvider('available', [available]), _config(priority=2)),
    ])
    resolution = resolver.resolve('IT8587E')
    assert resolution.found
    assert [trace.status for trace in resolution.traces] == ['failed', 'success']


def test_resolver_compares_sources_and_marks_manufacturer_conflict():
    first = DatasheetCandidate(
        provider='one', external_id='1', part_number='TPS51225',
        normalized_part_number='TPS51225', manufacturer='Texas Instruments',
        normalized_manufacturer='Texas Instruments', confidence=.94, exact_match=True,
    )
    second = DatasheetCandidate(
        provider='two', external_id='2', part_number='TPS51225',
        normalized_part_number='TPS51225', manufacturer='Richtek',
        normalized_manufacturer='Richtek', confidence=.91, exact_match=True,
    )
    resolver = DatasheetResolver([
        ConfiguredProvider(_StaticProvider('one', [first]), _config(priority=1)),
        ConfiguredProvider(_StaticProvider('two', [second]), _config(priority=2)),
    ])
    resolution = resolver.resolve('TPS51225', strategy='parallel_compare')
    assert resolution.found
    assert {trace.provider for trace in resolution.traces} == {'one', 'two'}
    assert resolution.conflicts['manufacturer'] == ['Texas Instruments', 'Richtek']
    assert resolution.confidence < .94


def test_manual_preview_materializes_component_and_public_routes(client):
    with app.app_context():
        ensure_default_datasheet_providers()
        config = DatasheetProviderConfig.query.filter_by(provider_name='source_parts').one()
        config.enabled = True
        config.metadata_persistence_allowed = True
        config.public_republish_allowed = True
        config.pdf_reference_allowed = True
        config.pdf_stream_allowed = False
        config.written_permission_confirmed = True
        queue = DatasheetImportQueue(
            part_number='TPS51225', normalized_part_number='TPS51225', status='needs_review',
            selected_provider='source_parts', best_confidence=.97, candidate_count=1,
            result_json=app_module.json.dumps({'selected': {
                'part_number': 'TPS51225', 'manufacturer': 'Texas Instruments',
                'category': 'Controlador PWM', 'package': 'QFN',
                'lifecycle_status': 'Ativo', 'specifications': {'Tensão de entrada': '4.5 V a 28 V'},
                'datasheet_reference': 'https://cdn.example.test/tps51225.pdf',
            }, 'provider_candidates': [{
                'provider': 'source_parts', 'part_number': 'TPS51225',
                'manufacturer': 'Texas Instruments', 'confidence': .97,
            }]}),
        )
        db.session.add(queue)
        db.session.commit()
        component = materialize_datasheet_component(queue, reviewer_id=None, publish=True)
        component_id, slug = component.id, component.slug
        assert DatasheetDocument.query.filter_by(component_id=component_id).count() == 1
        assert component.post_id is not None
        post = db.session.get(Post, component.post_id)
        assert post is not None
        assert post.is_active is True
        assert post.category_str == 'Datasheet'
        assert post.title == component.title_ptbr

    library = client.get('/datasheets')
    detail = client.get(f'/datasheet/{slug}')
    search = client.get('/pesquisa?q=TPS51225&filter=datasheets')
    assert library.status_code == detail.status_code == search.status_code == 200
    assert 'TPS51225' in library.get_data(as_text=True)
    assert 'Tensão de entrada' in detail.get_data(as_text=True)
    assert 'Datasheets' in search.get_data(as_text=True)


def test_automatic_datasheet_materialization_creates_a_real_post():
    with app.app_context():
        ensure_default_datasheet_providers()
        config = DatasheetProviderConfig.query.filter_by(provider_name='source_parts').one()
        config.enabled = True
        config.metadata_persistence_allowed = True
        config.public_republish_allowed = True
        config.written_permission_confirmed = True
        queue = DatasheetImportQueue(
            part_number='IT8587E', normalized_part_number='IT8587E', status='processing',
            selected_provider='source_parts', best_confidence=.99, candidate_count=1,
            result_json=app_module.json.dumps({'selected': {
                'provider': 'source_parts', 'part_number': 'IT8587E',
                'manufacturer': 'ITE', 'category': 'Embedded Controller',
                'package': 'LQFP', 'specifications': {'Interface': 'LPC'},
            }}),
        )
        db.session.add(queue)
        db.session.commit()

        component = materialize_datasheet_component(
            queue, reviewer_id=None, publish=True, automatic=True,
        )
        post = db.session.get(Post, component.post_id)

        assert component.publication_mode == 'automatic'
        assert queue.status == 'published'
        assert post is not None and post.is_active is True
        assert post.download_link == f'/datasheet/{component.slug}'
        assert 'automaticamente' in post.technical_notes


def test_board_page_exposes_only_published_related_components(client):
    with app.app_context():
        board = HardwareBoard(board_code='LA-9999P', normalized_board_code='LA9999P', slug='la-9999p')
        component = ElectronicComponent(
            part_number='W25Q64', normalized_part_number='W25Q64', manufacturer='Winbond',
            normalized_manufacturer='Winbond', title_ptbr='W25Q64 Datasheet', slug='w25q64',
            is_published=True,
        )
        db.session.add_all([board, component])
        db.session.flush()
        db.session.add(BoardComponent(board_id=board.id, component_id=component.id, reference_designator='U6', verified=True))
        db.session.commit()
    response = client.get('/placa/la-9999p')
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'Componentes e datasheets' in body and 'W25Q64' in body and 'U6' in body


def test_document_proxy_requires_login_and_recorded_stream_permission(client):
    with app.app_context():
        ensure_default_datasheet_providers()
        config = DatasheetProviderConfig.query.filter_by(provider_name='source_parts').one()
        config.enabled = True
        config.public_republish_allowed = True
        config.written_permission_confirmed = True
        config.pdf_stream_allowed = True
        component = ElectronicComponent(
            part_number='RT8243', normalized_part_number='RT8243', manufacturer='Richtek',
            normalized_manufacturer='Richtek', title_ptbr='RT8243 Datasheet', slug='rt8243', is_published=True,
        )
        db.session.add(component)
        db.session.flush()
        document = DatasheetDocument(
            component_id=component.id, document_title='RT8243 Datasheet', source_provider='source_parts',
            source_reference='https://cdn.example.test/rt8243.pdf', distribution_policy='stream_allowed',
        )
        user = User(username='datasheet_reader', email='reader@example.test', password_hash='x', role='user', plan='free', is_active=True)
        db.session.add_all([document, user])
        db.session.commit()
        document_id, user_id = document.id, user.id
    anonymous = client.get(f'/datasheet/documento/{document_id}/download')
    assert anonymous.status_code == 302
    _login(client, user_id)
    with app.app_context():
        config = DatasheetProviderConfig.query.filter_by(provider_name='source_parts').one()
        config.pdf_stream_allowed = False
        db.session.commit()
    denied = client.get(f'/datasheet/documento/{document_id}/download')
    assert denied.status_code == 403


def test_admin_datasheet_center_is_merged_into_technical_content(client):
    with app.app_context():
        admin = User(
            username='datasheet_admin', email='datasheet-admin@example.test',
            password_hash='x', role='admin', plan='free', is_active=True,
        )
        db.session.add(admin)
        db.session.commit()
        admin_id = admin.id
    _login(client, admin_id)
    legacy = client.get('/admin/datasheets')
    assert legacy.status_code == 302
    assert legacy.headers['Location'].endswith('/admin/tools/import?section=datasheets')
    response = client.get('/admin/tools/import?section=datasheets')
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'Conteúdo Técnico' in body
    assert 'Automação de datasheets' in body
    assert 'Semiautomático — aprovação do técnico' in body
    assert 'Métricas e benchmark' not in body
    assert 'SOURCE_PARTS_API_KEY' not in body
    assert 'secret' not in body.lower()


def test_unified_mode_controls_datasheets_and_source_authorization(client):
    with app.app_context():
        admin = User(
            username='automation_admin', email='automation-admin@example.test',
            password_hash='x', role='admin', plan='free', is_active=True,
        )
        db.session.add(admin)
        db.session.commit()
        admin_id = admin.id
    _login(client, admin_id)

    mode_response = client.post('/api/admin/technical-import/settings', json={
        'technical_automation_mode': 'full',
    })
    assert mode_response.status_code == 200
    with app.app_context():
        assert SiteConfig.get_value('technical_automation_mode') == 'full'
        assert SiteConfig.get_value('datasheet_engine_enabled') is True
        assert SiteConfig.get_value('datasheet_auto_publish_enabled') is True
        assert {
            config.mode for config in DatasheetProviderConfig.query.all()
        } == {'automatic'}

    missing_reference = client.post('/api/admin/technical-import/datasheets/source-policy', json={
        'publication_authorized': True,
    })
    assert missing_reference.status_code == 400
    authorized = client.post('/api/admin/technical-import/datasheets/source-policy', json={
        'publication_authorized': True,
        'permission_reference': 'Contrato interno TEST-1',
    })
    assert authorized.status_code == 200
    with app.app_context():
        source = DatasheetProviderConfig.query.filter_by(provider_name='source_parts').one()
        assert source.metadata_persistence_allowed is True
        assert source.public_republish_allowed is True
        assert source.written_permission_confirmed is True


def test_additive_migration_creates_datasheet_tables_idempotently(tmp_path, monkeypatch):
    database = tmp_path / 'datasheets.db'
    url = f'sqlite:///{database}'
    monkeypatch.setenv('DATABASE_URL', url)
    migrate()
    migrate()
    tables = set(inspect(create_engine(url)).get_table_names())
    assert {
        'datasheet_provider_configs', 'electronic_components', 'component_aliases',
        'component_source_records', 'datasheet_documents', 'board_components',
        'datasheet_import_queue', 'datasheet_demands', 'datasheet_provider_events',
    }.issubset(tables)
    component_columns = {column['name'] for column in inspect(create_engine(url)).get_columns('electronic_components')}
    assert 'post_id' in component_columns
