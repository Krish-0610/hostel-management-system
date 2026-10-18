# PC503 - Assignment 8: Hostel Management System with GUI

Student ID: 202611013, 202611016, 202611019


## Run

```powershell
python main.py
```

On first launch, create an administrator account. Then log in and follow this order:

```text
Admin → Add warden → Add hostel → Add room
      → Register resident → Allocate room
      → Generate monthly fee → Record payment → Transfer or check out
```

An admin can use every hostel, change a warden's or resident's password, and change a hostel/block's assigned warden. A warden can register residents, assign rooms and record fees only in their assigned hostels. A resident can view their own room, hostel, warden, charges and payments.

Room transfers stay within one hostel and require all posted and missing monthly fees to be paid first. The destination room's rate applies to future months; the first room occupied in a month sets that month's charge. Checkout also requires full payment. Partial payments are allowed.

The database file is `data/hostel.db`.

## Demo data

Close the app, then import [demo_seed.sql](demo_seed.sql) into the main database:

```powershell
sqlite3 -bail .\data\hostel.db ".read demo_seed.sql"
```

This adds one warden, one hostel/block, three rooms, and three residents with charges and payments. All four demo accounts (`demo_warden`, `demo_asha`, `demo_rahul`, `demo_neha`) use password `Demo@12345`. Asha has ₹3,000 outstanding; Rahul has a room-transfer history; Neha has checked out. Running the import again does not duplicate the demo rows.

## Codebase

| File | What it does |
|---|---|
| `main.py` | Starts SQLite, services and the Tkinter window. |
| `hostel/schema.sql` | Eight linked tables and database constraints. |
| `hostel/store.py` | SQL queries and transactions. |
| `hostel/core.py` | Login, permissions, rooms, residents, fees and payments. |
| `hostel/security.py` | Salted password hashes. |
| `hostel/app.py` | Forms, tables and buttons. |

The tables are `users`, `wardens`, `hostels`, `residents`, `rooms`, `allocations`, `fee_charges` and `payments`. `hostels.warden_id` replaces a separate `manages` table. `allocations` keeps past room stays; `payments` links to monthly charges.

The OOP design is intentionally simple: `Store` handles persistence, service classes handle rules, and `HostelApp` handles display. Services receive the store through their constructors. The GUI does not contain SQL, and database queries do not depend on Tkinter.

## Tests

```powershell
python -m unittest discover -s tests -v
```

Tests use temporary databases in `.test-data`; they do not change `data/hostel.db`.
