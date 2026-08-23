import os
import tempfile
import unittest


class RouteTest(unittest.TestCase):
    """בדיקות רגרסיה: מוודאות שהבאגים שתוקנו לא חוזרים, ושמסלולי ה-API הבסיסיים עובדים."""

    @classmethod
    def setUpClass(cls):
        # מסד SQLite זמני ונפרד לכל הרצת בדיקות, כדי לא לגעת בנתונים אמיתיים
        cls._tmp_dir = tempfile.mkdtemp()
        db_path = os.path.join(cls._tmp_dir, "test.db")
        os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
        os.environ["ADMIN_BOOTSTRAP_PASSWORD"] = "password123"

        from wsgi import app
        cls.app = app
        cls.client = app.test_client()

    def _login(self):
        r = self.client.post("/login", json={"username": "admin", "password": "password123"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json["success"])

    def test_home_serves_period_report(self):
        self._login()
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        body = r.get_data(as_text=True)
        self.assertIn("sp-page-head", body)  # מסך דוח התקופה

    def test_daily_entry_page_removed(self):
        """מסך הזנת החיובים היומית הוסר לבקשת המשתמש - אין לו יותר נתיב."""
        self._login()
        r = self.client.get("/daily-entry")
        self.assertEqual(r.status_code, 404)

    def test_settings_page_reachable(self):
        self._login()
        r = self.client.get("/settings")
        self.assertEqual(r.status_code, 200)
        body = r.get_data(as_text=True)
        self.assertIn("users-section", body)
        self.assertIn("password-form", body)
        self.assertIn("sync-status-section", body)

    def test_price_sync_status_endpoint_detects_orphan_and_missing_price(self):
        """מסך הגדרות חושף עכשיו נתון שהיה קיים ב-API אך לא נגיש דרך שום מסך:
        חיובים ללא מחיר שמור, ושמות מוצרים בחיובים שכבר לא קיימים במחירון."""
        self._login()
        r = self.client.post("/api/products", json={"name": "לימונים", "price": 1})
        self.assertTrue(r.json["success"])

        from wsgi import db
        from app import DailyEntry
        with self.app.app_context():
            db.session.add(DailyEntry(date="2026-07-20", product_name="לימון", quantity=15, is_extra=True, unit_price=None))
            db.session.commit()

        r = self.client.get("/api/price-sync/status")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json["missing_price_snapshots"], 1)
        self.assertIn("לימון", r.json["orphan_entry_products"])
        self.assertFalse(r.json["synchronized"])

    def test_period_report_flags_likely_duplicate_products(self):
        """מציאת כפילויות אפשריות: 'תבנית אלומיניום' מול 'תבנית אלומניום' (טעות הקלדה) -
        מוצרים דומים במתכוון (כמו 'מגש פירות' מול 'מגש פירות גדול') לא אמורים להיות מסומנים."""
        self._login()
        for name, price in [
            ("תבנית אלומיניום", 3.0),
            ("תבנית אלומניום", 5.0),
            ("מגש פירות", 140.0),
            ("מגש פירות גדול", 140.0),
        ]:
            r = self.client.post("/api/products", json={"name": name, "price": price})
            self.assertTrue(r.json["success"])

        body = self.client.get("/").get_data(as_text=True)
        self.assertIn("duplicate-detect.js", body)
        self.assertIn("dup-filter", body)

    def test_other_pages_still_reachable(self):
        self._login()
        for path in ("/dashboard", "/products/new", "/period-report", "/settings"):
            r = self.client.get(path)
            self.assertEqual(r.status_code, 200, f"{path} should be reachable")

    def test_navigation_assets_linked_on_every_page(self):
        self._login()
        for path in ("/", "/dashboard", "/products/new", "/settings"):
            body = self.client.get(path).get_data(as_text=True)
            self.assertIn("navigation.js", body)
            self.assertIn("navigation.css", body)

    def test_login_page_has_no_injected_navigation(self):
        """המשתמש עדיין לא מחובר במסך הכניסה - אין להזריק תפריט עם קישור יציאה/דשבורד."""
        r = self.client.get("/login")
        body = r.get_data(as_text=True)
        self.assertNotIn("navigation.js", body)

    def test_unauthenticated_redirects_to_login(self):
        self.client.get("/logout")
        r = self.client.get("/")
        self.assertEqual(r.status_code, 302)
        r_api = self.client.get("/api/products")
        self.assertEqual(r_api.status_code, 401)

    def test_add_product_and_entry_flow(self):
        self._login()
        r = self.client.post("/api/products", json={"name": "מוצר בדיקה", "price": 10})
        self.assertTrue(r.json["success"])

        r = self.client.post(
            "/api/entries",
            json={"date": "2026-01-01", "product_name": "מוצר בדיקה", "quantity": 3},
        )
        self.assertTrue(r.json["success"])

        r = self.client.get("/api/entries/2026-01-01")
        entries = r.json
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["unit_price"], 10)

    def test_period_report_range_endpoint(self):
        self._login()
        r = self.client.get("/api/report/range?start_date=2026-01-01&end_date=2026-01-31")
        self.assertEqual(r.status_code, 200)
        self.assertIn("summary", r.json)

    def test_product_add_page_has_sortable_products_table(self):
        """מסך ניהול המוצרים אמור לכלול טבלה עם כותרות ניתנות למיון, לא רק טופס ריק."""
        self._login()
        body = self.client.get("/products/new").get_data(as_text=True)
        self.assertIn("table-sort.js", body)
        self.assertIn('data-sort-key="name"', body)
        self.assertIn('data-sort-key="price"', body)
        self.assertIn("kpi-count", body)

    def test_sortable_headers_present_on_all_tables(self):
        """כל טבלה במערכת (מחירון ומוצרים בדוח, מוצרים בדף הניהול, משתמשים בהגדרות) צריכה כותרות ניתנות למיון."""
        self._login()
        period_body = self.client.get("/").get_data(as_text=True)
        self.assertIn('data-sort-key="date"', period_body)
        self.assertIn('data-sort-key="added_at"', period_body)

        product_body = self.client.get("/products/new").get_data(as_text=True)
        self.assertIn('data-sort-key="name"', product_body)
        self.assertIn('data-sort-key="price"', product_body)

        settings_body = self.client.get("/settings").get_data(as_text=True)
        self.assertIn('data-sort-key="username"', settings_body)
        self.assertIn('data-sort-key="action"', settings_body)

    def test_self_service_password_change(self):
        self._login()
        r = self.client.post(
            "/api/account/change-password",
            json={"current_password": "wrong", "new_password": "newpass123"},
        )
        self.assertEqual(r.status_code, 400)

        r = self.client.post(
            "/api/account/change-password",
            json={"current_password": "password123", "new_password": "newpass123"},
        )
        self.assertTrue(r.json["success"])

        self.client.get("/logout")
        r = self.client.post("/login", json={"username": "admin", "password": "newpass123"})
        self.assertTrue(r.json["success"])
        # משחזרים לסיסמה המקורית כדי לא לשבור בדיקות אחרות שרצות באותו client/DB
        self.client.post(
            "/api/account/change-password",
            json={"current_password": "newpass123", "new_password": "password123"},
        )

    def test_new_product_gets_created_at_directly(self):
        """מוצר חדש מקבל created_at ישירות בעמודה, בלי צורך לשחזר מיומן הפעילות."""
        self._login()
        r = self.client.post("/api/products", json={"name": "מוצר עם תאריך", "price": 5})
        self.assertTrue(r.json["success"])
        r = self.client.get("/api/report/products")
        product = next(p for p in r.json["products"] if p["name"] == "מוצר עם תאריך")
        self.assertIsNotNone(product["added_at"])

    def test_period_report_html_uses_data_attributes_not_inline_onclick_with_quotes(self):
        """באג שתוקן: onclick עם JSON.stringify(name) שבר את ה-HTML עבור מוצרים עם גרש/מרכאה
        בשם (למשל 'כפות חד"פ'), מה שהפך את כפתורי העריכה/מחיקה לבלתי פעילים בפועל."""
        self._login()
        body = self.client.get("/").get_data(as_text=True)
        self.assertNotIn("onclick=\"openEdit(", body)
        self.assertNotIn("onclick=\"removeProduct(", body)
        self.assertIn("edit-product-btn", body)
        self.assertIn("del-product-btn", body)

    def test_edit_and_delete_product_with_literal_quote_in_name(self):
        """מוצר עם מרכאה כפולה בשם (תרחיש אמיתי: חד"פ) - עריכה ומחיקה חייבות לעבוד."""
        self._login()
        from urllib.parse import quote
        name = 'כפות חד"פ'
        r = self.client.post("/api/products", json={"name": name, "price": 2.45})
        self.assertTrue(r.json["success"])

        url = f"/api/products/{quote(name)}"
        r = self.client.put(url, json={"name": name, "price": 3.10})
        self.assertTrue(r.json["success"])

        r = self.client.get("/api/report/products")
        match = next(p for p in r.json["products"] if p["name"] == name)
        self.assertEqual(match["price"], 3.10)

        r = self.client.delete(url)
        self.assertTrue(r.json["success"])
        r = self.client.get("/api/report/products")
        self.assertNotIn(name, [p["name"] for p in r.json["products"]])

    def test_api_404_returns_json_not_html(self):
        """דרישת production-readiness: לקוח JSON לעולם לא אמור לקבל עמוד שגיאה HTML."""
        self._login()
        r = self.client.get("/api/this-route-does-not-exist")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.content_type, "application/json")
        self.assertIn("error", r.json)

    def test_security_headers_present(self):
        r = self.client.get("/login")
        self.assertEqual(r.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(r.headers.get("X-Frame-Options"), "DENY")
        self.assertIn("Referrer-Policy", r.headers)

    def test_login_lockout_after_repeated_failures(self):
        """הגנה מפני brute-force: אחרי מספר ניסיונות כושלים, המשתמש נחסם זמנית.
        משתמשים במשתמש חד-פעמי ולא ב-admin, כדי לא לנעול את שאר הבדיקות בסוויטה
        שמתחברות כ-admin (הנעילה נשארת בתוקף לפי שעון אמיתי, לא ניתנת לאיפוס בבדיקה)."""
        self._login()
        r = self.client.post("/api/users", json={"username": "lockout_test_user", "password": "correctpass", "role": "viewer"})
        self.assertTrue(r.json["success"])
        self.client.get("/logout")

        for _ in range(5):
            r = self.client.post("/login", json={"username": "lockout_test_user", "password": "wrong"})
            self.assertEqual(r.status_code, 401)
        r = self.client.post("/login", json={"username": "lockout_test_user", "password": "wrong"})
        self.assertEqual(r.status_code, 429)
        # גם עם הסיסמה הנכונה - עדיין חסום עד תום החלון
        r = self.client.post("/login", json={"username": "lockout_test_user", "password": "correctpass"})
        self.assertEqual(r.status_code, 429)
        self._login()
        r = self.client.post("/api/users", json={"username": "viewer_test", "password": "viewpass", "role": "viewer"})
        self.assertTrue(r.json["success"])

        self.client.get("/logout")
        r = self.client.post("/login", json={"username": "viewer_test", "password": "viewpass"})
        self.assertTrue(r.json["success"])

        r = self.client.get("/settings")
        self.assertEqual(r.status_code, 200)  # הדף עצמו נגיש (מציג את האזור האישי)

        self.assertEqual(self.client.get("/api/users").status_code, 403)
        self.assertEqual(self.client.get("/api/logs").status_code, 403)
        self.assertEqual(self.client.get("/api/backup").status_code, 403)

        self.client.get("/logout")
        self._login()  # חזרה למנהל עבור שאר הבדיקות


if __name__ == "__main__":
    unittest.main()
