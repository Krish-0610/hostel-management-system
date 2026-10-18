"""SQLite queries for the eight tables. Application rules live in core.py."""

from contextlib import contextmanager
from pathlib import Path
import sqlite3


class Store:
    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, isolation_level=None, timeout=5)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version == 0:
            if self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table'").fetchone():
                raise RuntimeError("Unrecognized database schema")
            schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
            self.db.executescript("BEGIN;\n" + schema + "\nPRAGMA user_version = 1;\nCOMMIT;")
        elif version != 1:
            raise RuntimeError("Unsupported database version")

    def close(self):
        self.db.close()

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.commit()
        except sqlite3.IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Duplicate value or invalid database reference") from exc
        except Exception:
            self.db.rollback()
            raise

    def _one(self, sql, values=()):
        row = self.db.execute(sql, values).fetchone()
        return dict(row) if row else None

    def _all(self, sql, values=()):
        return [dict(row) for row in self.db.execute(sql, values)]

    def has_admin(self):
        return bool(self._one("SELECT 1 FROM users WHERE role='ADMIN' LIMIT 1"))

    def user(self, user_id):
        return self._one("SELECT * FROM users WHERE user_id=?", (user_id,))

    def username(self, username):
        return self._one("SELECT * FROM users WHERE username=?", (username,))

    def add_user(self, username, password_hash, name, role, now):
        return self.db.execute(
            "INSERT INTO users(username,password_hash,full_name,role,created_at) VALUES(?,?,?,?,?)",
            (username, password_hash, name, role, now),
        ).lastrowid

    def add_warden(self, user_id, employee_no):
        self.db.execute("INSERT INTO wardens(warden_id,employee_no) VALUES(?,?)", (user_id, employee_no))

    def wardens(self):
        return self._all("""SELECT w.warden_id,u.full_name,u.username,w.employee_no,u.is_active
                            FROM wardens w JOIN users u ON u.user_id=w.warden_id
                            ORDER BY u.full_name""")

    def hostel(self, hostel_id):
        return self._one("SELECT * FROM hostels WHERE hostel_id=?", (hostel_id,))

    def hostels(self):
        return self._all("""SELECT h.*,u.full_name AS warden_name
                            FROM hostels h JOIN users u ON u.user_id=h.warden_id
                            ORDER BY h.hostel_code""")

    def add_hostel(self, code, name, address, warden_id):
        return self.db.execute(
            "INSERT INTO hostels(hostel_code,name,address,warden_id) VALUES(?,?,?,?)",
            (code, name, address, warden_id),
        ).lastrowid

    def room(self, room_id):
        return self._one("SELECT * FROM rooms WHERE room_id=?", (room_id,))

    def rooms(self):
        return self._all("""SELECT r.*,h.hostel_code,
                                   COUNT(a.allocation_id) AS occupied
                            FROM rooms r JOIN hostels h ON h.hostel_id=r.hostel_id
                            LEFT JOIN allocations a ON a.room_id=r.room_id AND a.checked_out_at IS NULL
                            GROUP BY r.room_id ORDER BY h.hostel_code,r.room_number""")

    def occupancy(self, room_id):
        return self._one("SELECT COUNT(*) AS n FROM allocations WHERE room_id=? AND checked_out_at IS NULL", (room_id,))["n"]

    def add_room(self, hostel_id, number, capacity, fee_paise):
        return self.db.execute(
            "INSERT INTO rooms(hostel_id,room_number,capacity,monthly_fee_paise) VALUES(?,?,?,?)",
            (hostel_id, number, capacity, fee_paise),
        ).lastrowid

    def resident(self, resident_id):
        return self._one("""SELECT r.*,u.full_name,u.username,u.is_active,h.hostel_code,
                                   a.room_id,rm.room_number
                            FROM residents r JOIN users u ON u.user_id=r.resident_id
                            JOIN hostels h ON h.hostel_id=r.hostel_id
                            LEFT JOIN allocations a ON a.resident_id=r.resident_id AND a.checked_out_at IS NULL
                            LEFT JOIN rooms rm ON rm.room_id=a.room_id
                            WHERE r.resident_id=?""", (resident_id,))

    def residents(self):
        return self._all("""SELECT r.*,u.full_name,u.username,u.is_active,h.hostel_code,
                                   a.room_id,rm.room_number
                            FROM residents r JOIN users u ON u.user_id=r.resident_id
                            JOIN hostels h ON h.hostel_id=r.hostel_id
                            LEFT JOIN allocations a ON a.resident_id=r.resident_id AND a.checked_out_at IS NULL
                            LEFT JOIN rooms rm ON rm.room_id=a.room_id
                            ORDER BY u.full_name""")

    def add_resident(self, user_id, number, hostel_id, admitted_on):
        self.db.execute(
            "INSERT INTO residents(resident_id,registration_no,hostel_id,admitted_on) VALUES(?,?,?,?)",
            (user_id, number, hostel_id, admitted_on),
        )

    def check_out(self, resident_id):
        self.db.execute("UPDATE residents SET status='CHECKED_OUT' WHERE resident_id=?", (resident_id,))

    def allocations(self, resident_id):
        return self._all("""SELECT a.*,r.room_number FROM allocations a
                            JOIN rooms r ON r.room_id=a.room_id
                            WHERE a.resident_id=? ORDER BY a.checked_in_at,a.allocation_id""", (resident_id,))

    def current_allocation(self, resident_id):
        return self._one("SELECT * FROM allocations WHERE resident_id=? AND checked_out_at IS NULL", (resident_id,))

    def add_allocation(self, resident_id, room_id, now, fee_paise, actor_id):
        return self.db.execute("""INSERT INTO allocations
            (resident_id,room_id,checked_in_at,monthly_fee_paise_snapshot,created_by)
            VALUES(?,?,?,?,?)""", (resident_id, room_id, now, fee_paise, actor_id)).lastrowid

    def end_allocation(self, allocation_id, now):
        self.db.execute("UPDATE allocations SET checked_out_at=? WHERE allocation_id=?", (now, allocation_id))

    def charges(self, resident_id):
        return self._all("""SELECT c.*,COALESCE(SUM(p.amount_paise),0) AS paid_paise
                            FROM fee_charges c LEFT JOIN payments p ON p.charge_id=c.charge_id
                            WHERE c.resident_id=? GROUP BY c.charge_id ORDER BY c.billing_month""", (resident_id,))

    def charge(self, charge_id):
        return self._one("SELECT * FROM fee_charges WHERE charge_id=?", (charge_id,))

    def add_charge(self, resident_id, month, amount, due_on, now, actor_id):
        self.db.execute("""INSERT INTO fee_charges
            (resident_id,billing_month,amount_paise,due_on,created_at,created_by)
            VALUES(?,?,?,?,?,?)""", (resident_id, month, amount, due_on, now, actor_id))

    def payments(self, resident_id):
        return self._all("""SELECT p.*,c.billing_month FROM payments p
                            JOIN fee_charges c ON c.charge_id=p.charge_id
                            WHERE c.resident_id=? ORDER BY p.paid_at,p.payment_id""", (resident_id,))

    def add_payment(self, charge_id, amount, now, method, actor_id):
        return self.db.execute("""INSERT INTO payments
            (charge_id,amount_paise,paid_at,method,recorded_by) VALUES(?,?,?,?,?)""",
            (charge_id, amount, now, method, actor_id)).lastrowid
