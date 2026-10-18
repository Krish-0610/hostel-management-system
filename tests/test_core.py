import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from hostel.core import AuthService, BillingService, HostelService
from hostel.store import Store


class HostelTests(unittest.TestCase):
    def setUp(self):
        test_root = Path(__file__).resolve().parents[1] / ".test-data"
        test_root.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=test_root)
        self.path = Path(self.temp.name) / "hostel.db"
        self.store = Store(self.path)
        self.now = datetime(2026, 1, 15, 6, tzinfo=timezone.utc)
        self.auth = AuthService(self.store)
        self.billing = BillingService(self.store, self.auth, lambda: self.now)
        self.hostel = HostelService(self.store, self.auth, self.billing)
        self.auth.setup_admin("admin", "secret", "Admin")
        self.admin = self.auth.login("admin", "secret")
        self.warden_id = self.hostel.add_warden(self.admin, "warden", "secret", "Warden", "E1")
        self.hostel_id = self.hostel.add_hostel(self.admin, "H1", "North", "Campus", self.warden_id)
        self.room1 = self.hostel.add_room(self.admin, self.hostel_id, "101", 1, "5000")
        self.room2 = self.hostel.add_room(self.admin, self.hostel_id, "102", 1, "7000")
        self.resident_id = self.hostel.register(self.admin, self.hostel_id, "resident", "secret",
                                                "Resident", "R1")
        self.warden = self.auth.login("warden", "secret")
        self.resident = self.auth.login("resident", "secret")

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_login_permissions_and_registration_rollback(self):
        with self.assertRaises(ValueError):
            self.auth.login("admin", "wrong")
        with self.assertRaises(ValueError):
            self.hostel.add_room(self.warden, self.hostel_id, "103", 1, "4000")
        with self.assertRaises(ValueError):
            self.hostel.allocate(self.resident, self.resident_id, self.room1)
        with self.assertRaises(ValueError):
            self.hostel.register(self.admin, self.hostel_id, "other", "secret", "Other", "R1")
        self.assertIsNone(self.store.username("other"))
        self.assertNotEqual(self.store.user(self.resident_id)["password_hash"], "secret")
        self.assertEqual(self.hostel.residents(self.resident)[0]["resident_id"], self.resident_id)

    def test_allocation_transfer_billing_and_checkout(self):
        self.hostel.allocate(self.warden, self.resident_id, self.room1)
        first_charge = self.billing.statement(self.resident, self.resident_id)[0][0]
        self.assertEqual(first_charge["amount_paise"], 500000)
        with self.assertRaises(ValueError):
            self.hostel.allocate(self.admin, self.resident_id, self.room2)
        another = self.hostel.register(self.admin, self.hostel_id, "second", "secret", "Second", "R2")
        with self.assertRaises(ValueError):
            self.hostel.allocate(self.admin, another, self.room1)
        self.now = datetime(2026, 1, 20, 6, tzinfo=timezone.utc)
        self.billing.pay(self.warden, first_charge["charge_id"], "2000", "CASH")
        with self.assertRaisesRegex(ValueError, "before transfer"):
            self.hostel.transfer(self.admin, self.resident_id, self.room2)
        self.assertEqual(self.store.current_allocation(self.resident_id)["room_id"], self.room1)
        self.billing.pay(self.admin, first_charge["charge_id"], "3000", "UPI")
        self.hostel.transfer(self.admin, self.resident_id, self.room2)
        self.assertEqual(len(self.hostel.stays(self.resident, self.resident_id)), 2)
        self.assertEqual(self.billing.generate(self.warden, self.resident_id), 0)
        self.now = datetime(2026, 2, 2, 6, tzinfo=timezone.utc)
        self.assertEqual(self.billing.generate(self.admin, self.resident_id), 1)
        charges, _ = self.billing.statement(self.admin, self.resident_id)
        self.assertEqual([(c["billing_month"], c["amount_paise"]) for c in charges],
                         [("2026-01", 500000), ("2026-02", 700000)])
        with self.assertRaises(ValueError):
            self.billing.pay(self.admin, charges[1]["charge_id"], "7000.01", "UPI")
        with self.assertRaisesRegex(ValueError, "outstanding"):
            self.hostel.checkout(self.admin, self.resident_id)
        self.assertEqual(self.store.occupancy(self.room2), 1)
        self.billing.pay(self.admin, charges[1]["charge_id"], "7000", "BANK")
        self.hostel.checkout(self.warden, self.resident_id)
        self.assertEqual(self.store.occupancy(self.room2), 0)
        self.assertEqual(self.store.resident(self.resident_id)["status"], "CHECKED_OUT")
        self.assertEqual(len(self.billing.statement(self.resident, self.resident_id)[1]), 3)

    def test_password_reset(self):
        with self.assertRaises(ValueError):
            self.auth.reset_password(self.warden, self.resident_id, "new-secret")
        with self.assertRaises(ValueError):
            self.auth.reset_password(self.admin, 1, "new-secret")
        self.auth.reset_password(self.admin, self.warden_id, "new-warden-password")
        with self.assertRaises(ValueError):
            self.auth.login("warden", "secret")
        with self.assertRaises(ValueError):
            self.auth.require(self.warden)
        self.assertEqual(self.auth.require(self.auth.login("warden", "new-warden-password"))["role"],
                         "WARDEN")
        self.auth.reset_password(self.admin, self.resident_id, "new-resident-password")
        with self.assertRaises(ValueError):
            self.auth.require(self.resident)
        self.assertEqual(self.auth.require(self.auth.login("resident", "new-resident-password"))["role"],
                         "RESIDENT")

    def test_warden_assignment_and_resident_details(self):
        second = self.hostel.add_warden(self.admin, "w2", "secret", "New Warden", "E2",
                                        "9999999999")
        details = self.hostel.resident_hostel_details(self.resident, self.resident_id)
        self.assertEqual((details["name"], details["warden_name"]), ("North", "Warden"))
        with self.assertRaises(ValueError):
            self.hostel.assign_warden(self.warden, self.hostel_id, second)
        self.hostel.assign_warden(self.admin, self.hostel_id, second)
        details = self.hostel.resident_hostel_details(self.resident, self.resident_id)
        self.assertEqual((details["address"], details["warden_name"], details["warden_phone"]),
                         ("Campus", "New Warden", "9999999999"))
        with self.assertRaises(ValueError):
            self.hostel.register(self.warden, self.hostel_id, "x", "secret", "X", "R3")
        new_warden = self.auth.login("w2", "secret")
        self.assertEqual(self.hostel.hostels(new_warden)[0]["warden_id"], second)

    def test_transfer_posts_missing_month_before_fee_check(self):
        self.hostel.allocate(self.admin, self.resident_id, self.room1)
        january = self.billing.statement(self.admin, self.resident_id)[0][0]
        self.billing.pay(self.admin, january["charge_id"], "5000", "CASH")
        self.now = datetime(2026, 2, 2, 6, tzinfo=timezone.utc)
        with self.assertRaisesRegex(ValueError, "before transfer"):
            self.hostel.transfer(self.admin, self.resident_id, self.room2)
        self.assertEqual(self.store.current_allocation(self.resident_id)["room_id"], self.room1)
        charges, _ = self.billing.statement(self.admin, self.resident_id)
        self.assertEqual([c["billing_month"] for c in charges], ["2026-01", "2026-02"])
        self.assertEqual(charges[1]["amount_paise"], 500000)
        self.billing.pay(self.admin, charges[1]["charge_id"], "5000", "CASH")
        self.hostel.transfer(self.admin, self.resident_id, self.room2)

    def test_warden_scope_and_failed_transfer(self):
        other_warden = self.hostel.add_warden(self.admin, "w2", "secret", "Other", "E2")
        other_hostel = self.hostel.add_hostel(self.admin, "H2", "South", "Campus", other_warden)
        other_room = self.hostel.add_room(self.admin, other_hostel, "101", 1, "4000")
        with self.assertRaises(ValueError):
            self.hostel.register(self.warden, other_hostel, "x", "secret", "X", "R3")
        self.hostel.allocate(self.admin, self.resident_id, self.room1)
        with self.assertRaises(ValueError):
            self.hostel.transfer(self.admin, self.resident_id, other_room)
        self.assertEqual(self.store.current_allocation(self.resident_id)["room_id"], self.room1)
        self.assertEqual(self.billing.statement(self.resident, self.resident_id)[0][0]["billing_month"],
                         "2026-01")

    def test_persistence_and_foreign_keys(self):
        self.hostel.allocate(self.admin, self.resident_id, self.room1)
        self.store.close()
        self.store = Store(self.path)
        self.assertEqual(self.store.db.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        self.assertEqual(self.store.occupancy(self.room1), 1)
        self.assertEqual(len(self.store.charges(self.resident_id)), 1)

    def test_tk_role_screens(self):
        try:
            import tkinter as tk
            from tkinter import ttk
            from hostel.app import HostelApp
            root = tk.Tk()
        except tk.TclError:
            self.skipTest("Tk display unavailable")
        try:
            root.withdraw()
            app = HostelApp(root, self.auth, self.hostel, self.billing)
            for token, expected in ((self.admin, ["Setup", "Residents", "Fees"]),
                                    (self.warden, ["Residents", "Fees"]),
                                    (self.resident, ["My room", "My fees"])):
                app.token = token
                app.show_home()
                notebook = next(w for w in app.page.winfo_children() if isinstance(w, ttk.Notebook))
                self.assertEqual([notebook.tab(tab, "text") for tab in notebook.tabs()], expected)
                def descendants(widget):
                    for child in widget.winfo_children():
                        yield child
                        yield from descendants(child)
                widgets = list(descendants(app.page))
                if token == self.admin:
                    buttons = [w.cget("text") for w in widgets if isinstance(w, ttk.Button)]
                    self.assertIn("Change password", buttons)
                    self.assertIn("Change assigned warden", buttons)
                if token == self.resident:
                    labels = [w.cget("text") for w in widgets if isinstance(w, ttk.Label)]
                    self.assertTrue(any(text.startswith("Warden:") for text in labels))
                    self.assertTrue(any(text.startswith("Hostel / block:") for text in labels))
            root.update_idletasks()
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
