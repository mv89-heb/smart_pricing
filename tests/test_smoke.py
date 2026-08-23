import unittest
from unittest.mock import patch


class SmokeTest(unittest.TestCase):
    def test_wsgi_exports_flask_app(self):
        # Keep the test isolated from a real production database.
        with patch("performance.ensure_indexes"):
            from wsgi import app
        self.assertIsNotNone(app)
        self.assertTrue(callable(app))


if __name__ == "__main__":
    unittest.main()
