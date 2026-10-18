"""Business rules for a small hostel desk application."""

import calendar
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import secrets

from .security import PasswordHasher

IST = timezone(timedelta(hours=5, minutes=30))


def rupees_to_paise(value):
    try:
        amount = Decimal(str(value).strip()) * 100
        if (
            not amount.is_finite()
            or amount != amount.to_integral_value()
            or amount <= 0
        ):
            raise ValueError
        return int(amount)
    except (InvalidOperation, ValueError):
        raise ValueError(
            "Enter a positive amount in rupees (up to 2 decimal places)"
        ) from None


def money(paise):
    return f"₹{paise // 100}.{paise % 100:02d}"


def required(*values):
    if any(not str(value).strip() for value in values):
        raise ValueError("Complete all fields")


class AuthService:
    def __init__(self, store, hasher=None):
        self.store = store
        self.hasher = hasher or PasswordHasher()
        self.sessions = {}

    def setup_admin(self, username, password, name):
        required(username, password, name)
        with self.store.transaction():
            if self.store.has_admin():
                raise ValueError("Administrator already exists")
            return self.store.add_user(
                username.strip(),
                self.hasher.hash(password),
                name.strip(),
                "ADMIN",
                datetime.now(timezone.utc).isoformat(),
            )

    def login(self, username, password):
        user = self.store.username(username.strip())
        if (
            not user
            or not user["is_active"]
            or not self.hasher.verify(password, user["password_hash"])
        ):
            raise ValueError("Incorrect username or password")
        token = secrets.token_urlsafe(24)
        self.sessions[token] = user["user_id"]
        return token

    def logout(self, token):
        self.sessions.pop(token, None)

    def require(self, token, roles=None, hostel_id=None):
        user_id = self.sessions.get(token)
        user = self.store.user(user_id) if user_id else None
        if not user or not user["is_active"] or (roles and user["role"] not in roles):
            raise ValueError("You do not have permission for this action")
        if hostel_id is not None and user["role"] == "WARDEN":
            hostel = self.store.hostel(hostel_id)
            if not hostel or hostel["warden_id"] != user_id:
                raise ValueError("This hostel is not assigned to you")
        return user


class BillingService:
    def __init__(self, store, auth, clock=None):
        self.store, self.auth = store, auth
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def _resident_access(self, token, resident_id, staff_only=False):
        user = self.auth.require(token)
        resident = self.store.resident(resident_id)
        if not resident:
            raise ValueError("Resident not found")
        if user["role"] == "RESIDENT":
            if staff_only or user["user_id"] != resident_id:
                raise ValueError("You can only view your own records")
        else:
            self.auth.require(token, ("ADMIN", "WARDEN"), resident["hostel_id"])
        return user, resident

    def ensure_charges(self, resident_id, actor_id, now=None, end_current_at=None):
        """Insert each missing occupied month; caller holds the transaction."""
        now = now or self.clock()
        end_current_at = end_current_at or now
        existing = {c["billing_month"] for c in self.store.charges(resident_id)}
        count = 0
        for stay in self.store.allocations(resident_id):
            start = datetime.fromisoformat(stay["checked_in_at"])
            end = (
                datetime.fromisoformat(stay["checked_out_at"])
                if stay["checked_out_at"]
                else end_current_at
            )
            end = min(end, now)
            if end <= start:
                if stay["checked_out_at"] is not None:
                    continue
                end = start + timedelta(microseconds=1)
            first = start.astimezone(IST).date().replace(day=1)
            last = (
                (end - timedelta(microseconds=1)).astimezone(IST).date().replace(day=1)
            )
            month = first
            while month <= last:
                key = month.strftime("%Y-%m")
                if key not in existing:
                    due = month.replace(
                        day=calendar.monthrange(month.year, month.month)[1]
                    )
                    self.store.add_charge(
                        resident_id,
                        key,
                        stay["monthly_fee_paise_snapshot"],
                        due.isoformat(),
                        now.isoformat(),
                        actor_id,
                    )
                    existing.add(key)
                    count += 1
                month = (month.replace(day=28) + timedelta(days=4)).replace(day=1)
        return count

    def generate(self, token, resident_id):
        user, _ = self._resident_access(token, resident_id, staff_only=True)
        with self.store.transaction():
            return self.ensure_charges(resident_id, user["user_id"])

    def statement(self, token, resident_id):
        self._resident_access(token, resident_id)
        charges = self.store.charges(resident_id)
        for charge in charges:
            charge["balance_paise"] = charge["amount_paise"] - charge["paid_paise"]
        return charges, self.store.payments(resident_id)

    def pay(self, token, charge_id, rupees, method):
        charge = self.store.charge(charge_id)
        if not charge:
            raise ValueError("Charge not found")
        user, _ = self._resident_access(token, charge["resident_id"], staff_only=True)
        amount = rupees_to_paise(rupees)
        if method not in ("CASH", "UPI", "BANK"):
            raise ValueError("Choose a payment method")
        with self.store.transaction():
            self.ensure_charges(charge["resident_id"], user["user_id"])
            current = next(
                c
                for c in self.store.charges(charge["resident_id"])
                if c["charge_id"] == charge_id
            )
            if amount > current["amount_paise"] - current["paid_paise"]:
                raise ValueError("Payment exceeds the remaining balance")
            return self.store.add_payment(
                charge_id, amount, self.clock().isoformat(), method, user["user_id"]
            )


class HostelService:
    def __init__(self, store, auth, billing):
        self.store, self.auth, self.billing = store, auth, billing

    def _staff_resident(self, token, resident_id):
        user = self.auth.require(token, ("ADMIN", "WARDEN"))
        resident = self.store.resident(resident_id)
        if not resident:
            raise ValueError("Resident not found")
        self.auth.require(token, hostel_id=resident["hostel_id"])
        return user, resident

    def wardens(self, token):
        self.auth.require(token, ("ADMIN",))
        return self.store.wardens()

    def hostels(self, token):
        user = self.auth.require(token, ("ADMIN", "WARDEN"))
        return [
            h
            for h in self.store.hostels()
            if user["role"] == "ADMIN" or h["warden_id"] == user["user_id"]
        ]

    def rooms(self, token):
        user = self.auth.require(token)
        rooms = self.store.rooms()
        if user["role"] == "ADMIN":
            return rooms
        if user["role"] == "WARDEN":
            allowed = {h["hostel_id"] for h in self.hostels(token)}
            return [r for r in rooms if r["hostel_id"] in allowed]
        resident = self.store.resident(user["user_id"])
        return [r for r in rooms if resident and r["room_id"] == resident["room_id"]]

    def residents(self, token):
        user = self.auth.require(token)
        residents = self.store.residents()
        if user["role"] == "ADMIN":
            return residents
        if user["role"] == "WARDEN":
            allowed = {h["hostel_id"] for h in self.hostels(token)}
            return [r for r in residents if r["hostel_id"] in allowed]
        return [r for r in residents if r["resident_id"] == user["user_id"]]

    def stays(self, token, resident_id):
        self.billing._resident_access(token, resident_id)
        return self.store.allocations(resident_id)

    def add_warden(self, token, username, password, name, employee_no):
        self.auth.require(token, ("ADMIN",))
        required(username, password, name, employee_no)
        with self.store.transaction():
            user_id = self.store.add_user(
                username.strip(),
                self.auth.hasher.hash(password),
                name.strip(),
                "WARDEN",
                self.billing.clock().isoformat(),
            )
            self.store.add_warden(user_id, employee_no.strip())
            return user_id

    def add_hostel(self, token, code, name, address, warden_id):
        self.auth.require(token, ("ADMIN",))
        required(code, name, address)
        warden = next(
            (w for w in self.store.wardens() if w["warden_id"] == warden_id), None
        )
        if not warden or not warden["is_active"]:
            raise ValueError("Choose an active warden")
        with self.store.transaction():
            return self.store.add_hostel(
                code.strip(), name.strip(), address.strip(), warden_id
            )

    def add_room(self, token, hostel_id, number, capacity, monthly_rupees):
        self.auth.require(token, ("ADMIN",))
        required(number)
        hostel = self.store.hostel(hostel_id)
        if not hostel or not hostel["is_active"]:
            raise ValueError("Choose an active hostel")
        try:
            beds = int(capacity)
            if beds <= 0:
                raise ValueError
        except (TypeError, ValueError):
            raise ValueError("Capacity must be a positive whole number") from None
        fee = rupees_to_paise(monthly_rupees)
        with self.store.transaction():
            return self.store.add_room(hostel_id, number.strip(), beds, fee)

    def register(self, token, hostel_id, username, password, name, registration_no):
        self.auth.require(token, ("ADMIN", "WARDEN"), hostel_id)
        required(username, password, name, registration_no)
        hostel = self.store.hostel(hostel_id)
        if not hostel or not hostel["is_active"]:
            raise ValueError("Choose an active hostel")
        with self.store.transaction():
            user_id = self.store.add_user(
                username.strip(),
                self.auth.hasher.hash(password),
                name.strip(),
                "RESIDENT",
                self.billing.clock().isoformat(),
            )
            self.store.add_resident(
                user_id,
                registration_no.strip(),
                hostel_id,
                self.billing.clock().astimezone(IST).date().isoformat(),
            )
            return user_id

    def _eligible_room(self, resident, room_id):
        room = self.store.room(room_id)
        if (
            not room
            or room["hostel_id"] != resident["hostel_id"]
            or room["status"] != "OPEN"
        ):
            raise ValueError("Choose an open room in the resident's hostel")
        if self.store.occupancy(room_id) >= room["capacity"]:
            raise ValueError("Room is full")
        return room

    def allocate(self, token, resident_id, room_id):
        user, resident = self._staff_resident(token, resident_id)
        with self.store.transaction():
            if resident["status"] != "ENROLLED" or self.store.current_allocation(
                resident_id
            ):
                raise ValueError("Resident already has a room or has checked out")
            room = self._eligible_room(resident, room_id)
            now = self.billing.clock().isoformat()
            allocation_id = self.store.add_allocation(
                resident_id, room_id, now, room["monthly_fee_paise"], user["user_id"]
            )
            self.billing.ensure_charges(resident_id, user["user_id"])
            return allocation_id

    def transfer(self, token, resident_id, room_id):
        user, resident = self._staff_resident(token, resident_id)
        with self.store.transaction():
            current = self.store.current_allocation(resident_id)
            if resident["status"] != "ENROLLED" or not current:
                raise ValueError("Resident has no current room")
            if current["room_id"] == room_id:
                raise ValueError("Choose another room")
            room = self._eligible_room(resident, room_id)
            now = self.billing.clock().isoformat()
            self.store.end_allocation(current["allocation_id"], now)
            allocation_id = self.store.add_allocation(
                resident_id, room_id, now, room["monthly_fee_paise"], user["user_id"]
            )
            self.billing.ensure_charges(resident_id, user["user_id"])
            return allocation_id

    def checkout(self, token, resident_id):
        user, resident = self._staff_resident(token, resident_id)
        if resident["status"] != "ENROLLED":
            raise ValueError("Resident has already checked out")
        with self.store.transaction():
            now = self.billing.clock()
            self.billing.ensure_charges(resident_id, user["user_id"], now, now)
            unpaid = sum(
                c["amount_paise"] - c["paid_paise"]
                for c in self.store.charges(resident_id)
            )
            if unpaid == 0:
                current = self.store.current_allocation(resident_id)
                if current:
                    self.store.end_allocation(current["allocation_id"], now.isoformat())
                self.store.check_out(resident_id)
        if unpaid:
            raise ValueError(f"Pay the outstanding {money(unpaid)} before checkout")
