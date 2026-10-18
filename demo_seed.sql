-- Demo accounts: demo_warden, demo_asha, demo_rahul, demo_neha
-- Password for each: Demo@12345
-- Run once or more; existing demo rows are left as they are.
PRAGMA foreign_keys = ON;
BEGIN IMMEDIATE;

INSERT OR IGNORE INTO users(username,password_hash,full_name,phone,role,created_at) VALUES
('demo_warden','scrypt$16384$8$1$8fa9d200f942333b9fce490a23199869$efa19fd645e098671cd75b36a64448186e77d792809167283165dff13fac29757ec1560fa2001f634f318aba960fd2fe8c6fd2c846c64bfe43a6212313286352','Demo Warden','9876500000','WARDEN','2026-09-01T04:30:00+00:00'),
('demo_asha','scrypt$16384$8$1$9d906a2e14298b87d04d5ae2779d4a53$83978d0cc4fd1b095cbefc0c5ff37fbf49c0a3cc5f63fba8e9ecf280f6bde84867d4bd6d5ebd445aa3699c4a55ff87741774f661cdc4a748b75ce6d1cb4072a1','Asha Patel',NULL,'RESIDENT','2026-10-01T04:30:00+00:00'),
('demo_rahul','scrypt$16384$8$1$0e7053515d94804dbeac904270ea8d86$1ec3ab18569d2b96612bef8a085a4319191b9893deaa7c9b06a66f0a5837580a55f39beec3359da0220c413d6d91821578a5a6b960625ba56ca8fc4e1b5735ec','Rahul Shah',NULL,'RESIDENT','2026-10-01T04:30:00+00:00'),
('demo_neha','scrypt$16384$8$1$37b619d64ce152c9c1fea842fd44227e$5861c83a3a6087b23bdb405de0245eae026518bd0353a9f889819bdc6fb57c3af61fcce5b028ee25354c353d8abc036a4613bc06e8c840910b764ce07fea0ea3','Neha Desai',NULL,'RESIDENT','2026-09-01T04:30:00+00:00');

INSERT OR IGNORE INTO wardens(warden_id,employee_no)
SELECT user_id,'DEMO-W1' FROM users WHERE username='demo_warden';

INSERT OR IGNORE INTO hostels(hostel_code,name,address,warden_id)
SELECT 'DEMO-BLOCK','Demo Block','North Campus',warden_id
FROM wardens WHERE employee_no='DEMO-W1';

INSERT OR IGNORE INTO rooms(hostel_id,room_number,capacity,monthly_fee_paise)
SELECT hostel_id,'D101',2,500000 FROM hostels WHERE hostel_code='DEMO-BLOCK';
INSERT OR IGNORE INTO rooms(hostel_id,room_number,capacity,monthly_fee_paise)
SELECT hostel_id,'D102',2,650000 FROM hostels WHERE hostel_code='DEMO-BLOCK';
INSERT OR IGNORE INTO rooms(hostel_id,room_number,capacity,monthly_fee_paise)
SELECT hostel_id,'D103',1,450000 FROM hostels WHERE hostel_code='DEMO-BLOCK';

INSERT OR IGNORE INTO residents(resident_id,registration_no,hostel_id,admitted_on,status)
SELECT u.user_id,'DEMO-R1',h.hostel_id,'2026-10-05','ENROLLED'
FROM users u CROSS JOIN hostels h WHERE u.username='demo_asha' AND h.hostel_code='DEMO-BLOCK';
INSERT OR IGNORE INTO residents(resident_id,registration_no,hostel_id,admitted_on,status)
SELECT u.user_id,'DEMO-R2',h.hostel_id,'2026-10-03','ENROLLED'
FROM users u CROSS JOIN hostels h WHERE u.username='demo_rahul' AND h.hostel_code='DEMO-BLOCK';
INSERT OR IGNORE INTO residents(resident_id,registration_no,hostel_id,admitted_on,status)
SELECT u.user_id,'DEMO-R3',h.hostel_id,'2026-09-01','CHECKED_OUT'
FROM users u CROSS JOIN hostels h WHERE u.username='demo_neha' AND h.hostel_code='DEMO-BLOCK';

-- Asha has a current room and an unpaid balance.
INSERT INTO allocations(resident_id,room_id,checked_in_at,checked_out_at,monthly_fee_paise_snapshot,created_by)
SELECT r.resident_id,rm.room_id,'2026-10-05T04:30:00+00:00',NULL,rm.monthly_fee_paise,h.warden_id
FROM residents r JOIN hostels h ON h.hostel_id=r.hostel_id
JOIN rooms rm ON rm.hostel_id=h.hostel_id AND rm.room_number='D101'
WHERE r.registration_no='DEMO-R1' AND NOT EXISTS
(SELECT 1 FROM allocations a WHERE a.resident_id=r.resident_id AND a.checked_in_at='2026-10-05T04:30:00+00:00');

-- Rahul transferred from D101 to D102; his October price remains D101's price.
INSERT INTO allocations(resident_id,room_id,checked_in_at,checked_out_at,monthly_fee_paise_snapshot,created_by)
SELECT r.resident_id,rm.room_id,'2026-10-03T04:30:00+00:00','2026-10-10T04:30:00+00:00',rm.monthly_fee_paise,h.warden_id
FROM residents r JOIN hostels h ON h.hostel_id=r.hostel_id
JOIN rooms rm ON rm.hostel_id=h.hostel_id AND rm.room_number='D101'
WHERE r.registration_no='DEMO-R2' AND NOT EXISTS
(SELECT 1 FROM allocations a WHERE a.resident_id=r.resident_id AND a.checked_in_at='2026-10-03T04:30:00+00:00');
INSERT INTO allocations(resident_id,room_id,checked_in_at,checked_out_at,monthly_fee_paise_snapshot,created_by)
SELECT r.resident_id,rm.room_id,'2026-10-10T04:30:00+00:00',NULL,rm.monthly_fee_paise,h.warden_id
FROM residents r JOIN hostels h ON h.hostel_id=r.hostel_id
JOIN rooms rm ON rm.hostel_id=h.hostel_id AND rm.room_number='D102'
WHERE r.registration_no='DEMO-R2' AND NOT EXISTS
(SELECT 1 FROM allocations a WHERE a.resident_id=r.resident_id AND a.checked_in_at='2026-10-10T04:30:00+00:00');

-- Neha shows a completed stay and paid checkout.
INSERT INTO allocations(resident_id,room_id,checked_in_at,checked_out_at,monthly_fee_paise_snapshot,created_by)
SELECT r.resident_id,rm.room_id,'2026-09-01T04:30:00+00:00','2026-09-30T12:30:00+00:00',rm.monthly_fee_paise,h.warden_id
FROM residents r JOIN hostels h ON h.hostel_id=r.hostel_id
JOIN rooms rm ON rm.hostel_id=h.hostel_id AND rm.room_number='D103'
WHERE r.registration_no='DEMO-R3' AND NOT EXISTS
(SELECT 1 FROM allocations a WHERE a.resident_id=r.resident_id AND a.checked_in_at='2026-09-01T04:30:00+00:00');

INSERT OR IGNORE INTO fee_charges(resident_id,billing_month,amount_paise,due_on,created_at,created_by)
SELECT r.resident_id,'2026-10',500000,'2026-10-31','2026-10-05T04:30:00+00:00',h.warden_id
FROM residents r JOIN hostels h ON h.hostel_id=r.hostel_id WHERE r.registration_no='DEMO-R1';
INSERT OR IGNORE INTO fee_charges(resident_id,billing_month,amount_paise,due_on,created_at,created_by)
SELECT r.resident_id,'2026-10',500000,'2026-10-31','2026-10-03T04:30:00+00:00',h.warden_id
FROM residents r JOIN hostels h ON h.hostel_id=r.hostel_id WHERE r.registration_no='DEMO-R2';
INSERT OR IGNORE INTO fee_charges(resident_id,billing_month,amount_paise,due_on,created_at,created_by)
SELECT r.resident_id,'2026-09',450000,'2026-09-30','2026-09-01T04:30:00+00:00',h.warden_id
FROM residents r JOIN hostels h ON h.hostel_id=r.hostel_id WHERE r.registration_no='DEMO-R3';

INSERT INTO payments(charge_id,amount_paise,paid_at,method,reference,recorded_by)
SELECT c.charge_id,200000,'2026-10-08T04:30:00+00:00','UPI','DEMO-ASHA-OCT',h.warden_id
FROM fee_charges c JOIN residents r ON r.resident_id=c.resident_id
JOIN hostels h ON h.hostel_id=r.hostel_id
WHERE r.registration_no='DEMO-R1' AND c.billing_month='2026-10' AND NOT EXISTS
(SELECT 1 FROM payments p WHERE p.reference='DEMO-ASHA-OCT');
INSERT INTO payments(charge_id,amount_paise,paid_at,method,reference,recorded_by)
SELECT c.charge_id,500000,'2026-10-11T04:30:00+00:00','CASH','DEMO-RAHUL-OCT',h.warden_id
FROM fee_charges c JOIN residents r ON r.resident_id=c.resident_id
JOIN hostels h ON h.hostel_id=r.hostel_id
WHERE r.registration_no='DEMO-R2' AND c.billing_month='2026-10' AND NOT EXISTS
(SELECT 1 FROM payments p WHERE p.reference='DEMO-RAHUL-OCT');
INSERT INTO payments(charge_id,amount_paise,paid_at,method,reference,recorded_by)
SELECT c.charge_id,450000,'2026-09-28T04:30:00+00:00','BANK','DEMO-NEHA-SEP',h.warden_id
FROM fee_charges c JOIN residents r ON r.resident_id=c.resident_id
JOIN hostels h ON h.hostel_id=r.hostel_id
WHERE r.registration_no='DEMO-R3' AND c.billing_month='2026-09' AND NOT EXISTS
(SELECT 1 FROM payments p WHERE p.reference='DEMO-NEHA-SEP');

COMMIT;
