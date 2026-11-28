import unittest
import indexnow as m

class IndexNowTests(unittest.TestCase):
    def test_only_public_same_host(self):
        self.assertTrue(m.allowed(m.ORIGIN + '/'))
        for url in ('https://other.example/', m.ORIGIN + '/admin', m.ORIGIN + '/login', m.ORIGIN + '/?token=x', m.ORIGIN + '/api/private', m.ORIGIN + '/bios/x/comments'):
            self.assertFalse(m.allowed(url), url)

    def test_sitemap_and_changes(self):
        u = m.ORIGIN + '/example'
        xml = ('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>' + u + '</loc><lastmod>2026-11-28T12:00:00Z</lastmod></url></urlset>').encode()
        current = m.parse_sitemap(xml)
        self.assertEqual(m.changed_urls({}, current), [u])
        self.assertEqual(m.changed_urls(current, current), [])
        self.assertEqual(m.changed_urls({u:'old'}, current), [u])
        with self.assertRaises(ValueError):
            m.parse_sitemap(xml.replace(u.encode(), b'https://other.example/'))
        with self.assertRaises(ValueError):
            m.parse_sitemap(b'<html/>')

if __name__ == '__main__':
    unittest.main()
