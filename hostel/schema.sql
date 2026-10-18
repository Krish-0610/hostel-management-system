CREATE TABLE users (
    user_id INTEGER PRIMARY KEY,
    username TEXT NOT NULL COLLATE NOCASE UNIQUE CHECK(length(trim(username)) > 0),
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL CHECK(length(trim(full_name)) > 0),
    phone TEXT,
    role TEXT NOT NULL CHECK(role IN ('ADMIN','WARDEN','RESIDENT')),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1)),
    created_at TEXT NOT NULL
);
CREATE TABLE wardens (
    warden_id INTEGER PRIMARY KEY REFERENCES users(user_id) ON DELETE RESTRICT,
    employee_no TEXT NOT NULL COLLATE NOCASE UNIQUE
);
CREATE TABLE hostels (
    hostel_id INTEGER PRIMARY KEY,
    hostel_code TEXT NOT NULL COLLATE NOCASE UNIQUE,
    name TEXT NOT NULL,
    address TEXT NOT NULL,
    warden_id INTEGER NOT NULL REFERENCES wardens(warden_id) ON DELETE RESTRICT,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1))
);
CREATE TABLE residents (
    resident_id INTEGER PRIMARY KEY REFERENCES users(user_id) ON DELETE RESTRICT,
    registration_no TEXT NOT NULL COLLATE NOCASE UNIQUE,
    hostel_id INTEGER NOT NULL REFERENCES hostels(hostel_id) ON DELETE RESTRICT,
    admitted_on TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ENROLLED' CHECK(status IN ('ENROLLED','CHECKED_OUT')),
    emergency_contact TEXT
);
CREATE TABLE rooms (
    room_id INTEGER PRIMARY KEY,
    hostel_id INTEGER NOT NULL REFERENCES hostels(hostel_id) ON DELETE RESTRICT,
    room_number TEXT NOT NULL COLLATE NOCASE,
    floor TEXT,
    capacity INTEGER NOT NULL CHECK(typeof(capacity) = 'integer' AND capacity > 0),
    monthly_fee_paise INTEGER NOT NULL CHECK(typeof(monthly_fee_paise) = 'integer' AND monthly_fee_paise > 0),
    status TEXT NOT NULL DEFAULT 'OPEN' CHECK(status IN ('OPEN','MAINTENANCE','ARCHIVED')),
    UNIQUE(hostel_id, room_number)
);
CREATE TABLE allocations (
    allocation_id INTEGER PRIMARY KEY,
    resident_id INTEGER NOT NULL REFERENCES residents(resident_id) ON DELETE RESTRICT,
    room_id INTEGER NOT NULL REFERENCES rooms(room_id) ON DELETE RESTRICT,
    checked_in_at TEXT NOT NULL,
    checked_out_at TEXT CHECK(checked_out_at IS NULL OR checked_out_at >= checked_in_at),
    monthly_fee_paise_snapshot INTEGER NOT NULL CHECK(typeof(monthly_fee_paise_snapshot) = 'integer' AND monthly_fee_paise_snapshot > 0),
    created_by INTEGER NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT
);
CREATE UNIQUE INDEX one_current_allocation ON allocations(resident_id) WHERE checked_out_at IS NULL;
CREATE TABLE fee_charges (
    charge_id INTEGER PRIMARY KEY,
    resident_id INTEGER NOT NULL REFERENCES residents(resident_id) ON DELETE RESTRICT,
    billing_month TEXT NOT NULL CHECK(billing_month GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]' AND substr(billing_month,6,2) BETWEEN '01' AND '12'),
    amount_paise INTEGER NOT NULL CHECK(typeof(amount_paise) = 'integer' AND amount_paise > 0),
    due_on TEXT NOT NULL,
    created_at TEXT NOT NULL,
    created_by INTEGER NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    UNIQUE(resident_id, billing_month)
);
CREATE TABLE payments (
    payment_id INTEGER PRIMARY KEY,
    charge_id INTEGER NOT NULL REFERENCES fee_charges(charge_id) ON DELETE RESTRICT,
    amount_paise INTEGER NOT NULL CHECK(typeof(amount_paise) = 'integer' AND amount_paise > 0),
    paid_at TEXT NOT NULL,
    method TEXT NOT NULL CHECK(method IN ('CASH','UPI','BANK')),
    reference TEXT,
    recorded_by INTEGER NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT
);
CREATE INDEX hostels_warden ON hostels(warden_id);
CREATE INDEX residents_hostel ON residents(hostel_id);
CREATE INDEX allocations_room ON allocations(room_id, checked_out_at);
CREATE INDEX allocations_history ON allocations(resident_id, checked_in_at);
CREATE INDEX payments_charge ON payments(charge_id);
CREATE TRIGGER warden_role BEFORE INSERT ON wardens
WHEN (SELECT role FROM users WHERE user_id = NEW.warden_id) <> 'WARDEN'
BEGIN SELECT RAISE(ABORT, 'Warden profile requires WARDEN role'); END;
CREATE TRIGGER resident_role BEFORE INSERT ON residents
WHEN (SELECT role FROM users WHERE user_id = NEW.resident_id) <> 'RESIDENT'
BEGIN SELECT RAISE(ABORT, 'Resident profile requires RESIDENT role'); END;
CREATE TRIGGER fixed_user_role BEFORE UPDATE OF role ON users
WHEN NEW.role <> OLD.role
BEGIN SELECT RAISE(ABORT, 'User roles cannot be changed'); END;
CREATE TRIGGER immutable_payment_update BEFORE UPDATE ON payments
BEGIN SELECT RAISE(ABORT, 'Payments are immutable'); END;
CREATE TRIGGER immutable_payment_delete BEFORE DELETE ON payments
BEGIN SELECT RAISE(ABORT, 'Payments are immutable'); END;
CREATE TRIGGER immutable_charge_update BEFORE UPDATE ON fee_charges
BEGIN SELECT RAISE(ABORT, 'Charges are immutable'); END;
CREATE TRIGGER immutable_charge_delete BEFORE DELETE ON fee_charges
BEGIN SELECT RAISE(ABORT, 'Charges are immutable'); END;
