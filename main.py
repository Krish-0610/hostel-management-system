"""Run with: python main.py [--db path/to/hostel.db]."""

import argparse
from pathlib import Path
import tkinter as tk

from hostel.app import HostelApp
from hostel.core import AuthService, BillingService, HostelService
from hostel.store import Store


def main():
    parser = argparse.ArgumentParser(description="Hostel Management System")
    parser.add_argument("--db", type=Path, default=Path(__file__).parent / "data" / "hostel.db")
    args = parser.parse_args()
    store = Store(args.db)
    try:
        auth = AuthService(store)
        billing = BillingService(store, auth)
        hostel = HostelService(store, auth, billing)
        root = tk.Tk()
        HostelApp(root, auth, hostel, billing)
        root.mainloop()
    finally:
        store.close()


if __name__ == "__main__":
    main()
