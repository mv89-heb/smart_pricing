import unittest


class SmokeTest(unittest.TestCase):
    def test_wsgi_exports_flask_app(self):
        from wsgi import app
        self.assertIsNotNone(app)
        self.assertTrue(callable(app))


if __name__ == "__main__":
    unittest.main()
