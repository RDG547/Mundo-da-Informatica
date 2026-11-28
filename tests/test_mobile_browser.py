"""Browser smoke tests using Flask's isolated database and local asset responses."""
import re
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import sync_playwright
from app import app, db, Category, Post, User, Subcategory

ORIGIN = 'https://mundodainformatica.com'

@pytest.fixture
def browser_page(client):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width':390,'height':844}, is_mobile=True, has_touch=True)
        page = context.new_page()
        def serve(route):
            u = urlsplit(route.request.url)
            if u.netloc != 'mundodainformatica.com':
                route.abort()
                return
            if route.request.method != 'GET':
                route.fulfill(status=403, body='Smoke test: no write operations')
                return
            response = client.get(u.path + ('?' + u.query if u.query else ''), base_url=ORIGIN)
            headers = {k:v for k,v in response.headers.items() if k.lower() not in ('content-length','content-encoding','set-cookie')}
            route.fulfill(status=response.status_code, headers=headers, body=response.data)
        page.route('**/*', serve)
        yield page
        browser.close()

@pytest.fixture
def catalog():
    with app.app_context():
        category = Category(name='BIOS', slug='bios', is_active=True, is_visible=True, show_in_menu=True)
        other = Category(name='Esquemas', slug='esquemas', is_active=True, is_visible=True, show_in_menu=True)
        db.session.add_all([category, other])
        db.session.flush()
        sub = Subcategory(name='Notebook', slug='notebook', category_id=category.id)
        db.session.add(sub)
        db.session.add(Post(title='BIOS Lenovo LA-K091P', content='Arquivo técnico para consulta.', download_link='https://example.test/bios.bin', category_rel=category, category_str='BIOS', slug='bios-lenovo-la-k091p', is_active=True))
        db.session.commit()

def ready(page, path):
    response = page.goto(ORIGIN+path, wait_until='domcontentloaded')
    assert response and response.status == 200, path
    page.wait_for_function("window.__mdiMobileReady === true")
    page.wait_for_timeout(350)

def no_overflow(page, path):
    widths = page.evaluate("({viewport:document.documentElement.clientWidth,content:document.documentElement.scrollWidth})")
    assert widths['content'] <= widths['viewport'] + 2, (path, widths)

@pytest.mark.parametrize('width', [320,390,768])
def test_mobile_public_layout(browser_page,catalog,width):
    page=browser_page
    page.set_viewport_size({'width':width,'height':844})
    for path in ['/','/categorias','/categoria/bios','/bios/bios-lenovo-la-k091p','/pesquisa?q=bios','/login','/register','/planos','/faq','/contato','/datasheets']:
        ready(page,path)
        no_overflow(page,path)

def test_navigation_touch(browser_page,catalog):
    page=browser_page
    ready(page,'/')
    menu=page.locator('.mobile-menu-toggle')
    menu.click()
    assert menu.get_attribute('aria-expanded') == 'true'
    group=page.locator('[data-nav-group="categories"]')
    group.click()
    assert group.get_attribute('aria-expanded') == 'true'
    assert page.locator('#primary-navigation .dropdown.active > .dropdown-menu').is_visible()
    plain=page.locator('#primary-navigation .dropdown-item-main').filter(has_text='Esquemas')
    assert plain.count() == 1
    plain.click()
    page.wait_for_function("location.pathname.includes('/categoria/esquemas')")
    assert menu.get_attribute('aria-expanded') == 'false'
    page.set_viewport_size({'width':1024,'height':768})
    menu.click()
    group.click()
    assert group.get_attribute('aria-expanded') == 'true'
    page.keyboard.press('Escape')
    assert menu.get_attribute('aria-expanded') == 'false'

def test_desktop_mobile_styles_inactive(browser_page,catalog):
    page=browser_page
    page.set_viewport_size({'width':1440,'height':900})
    ready(page,'/')
    assert not page.locator('.mobile-menu-toggle').is_visible()
    assert not page.evaluate("matchMedia('(max-width:1100px)').matches")
    assert page.locator('#primary-navigation').is_visible()
    assert page.locator('#primary-navigation').evaluate("(el) => getComputedStyle(el).position") != 'fixed'
    no_overflow(page,'desktop homepage')

def test_admin_drawer_and_modal_styles(browser_page,client):
    with app.app_context():
        user=User(username='mobile_admin',email='mobile@example.test',password_hash='unused',role='admin',plan='free',is_active=True)
        db.session.add(user)
        db.session.commit()
        uid=user.id
    with client.session_transaction() as session:
        session['_user_id']=str(uid)
        session['_fresh']=True
    page=browser_page
    ready(page,'/admin/posts')
    toggle=page.locator('.mdi-mobile-admin-toggle')
    toggle.click()
    assert toggle.get_attribute('aria-expanded') == 'true'
    assert page.locator('#adminSidebar').evaluate("(el)=>el.classList.contains('show') && !el.inert")
    page.keyboard.press('Escape')
    assert toggle.get_attribute('aria-expanded') == 'false'
    assert page.locator('#adminSidebar').evaluate("(el)=>el.inert")
    # Use existing modal DOM without creating a real post or touching payment operations.
    modal=page.locator('#addPostModal')
    if modal.count():
        modal.evaluate("(el)=>{el.classList.add('show');el.style.display='flex'}")
        content=modal.locator('.modal-content').first
        rect=content.bounding_box()
        assert rect and rect['width'] <= 390 and rect['height'] <= 844
