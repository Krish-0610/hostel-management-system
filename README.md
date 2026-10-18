# Hostel Management System

A small Python assignment using Tkinter and SQLite. It runs on one computer and uses only the Python standard library.

## Run

```powershell
python main.py
```

On first launch, create an administrator account. Then log in and follow this order:

```text
Admin → Add warden → Add hostel → Add room
      → Register resident → Allocate room
      → Generate monthly fee → Record payment → Check out
```

An admin can use every hostel. A warden can register residents, assign rooms and record fees only in their assigned hostels. A resident can view their own room, charges and payments. Room transfers are within the same hostel. Checkout requires full payment. A room's monthly fee is charged once for each occupied month; partial payments are allowed.

The database file is `data/hostel.db`. Existing records from the previous version are kept. For a separate demonstration database, run `python main.py --db demo.db`.

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
