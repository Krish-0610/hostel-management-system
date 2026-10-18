"""A small Tkinter interface. All rules are checked by the services."""

import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk

from .core import money


class HostelApp:
    def __init__(self, root, auth, hostel, billing):
        self.root, self.auth, self.hostel, self.billing = root, auth, hostel, billing
        self.token = None
        self.selected_resident_id = None
        root.title("Hostel Management")
        root.geometry("950x650")
        self.show_login()

    def clear(self):
        for child in self.root.winfo_children():
            child.destroy()
        self.page = ttk.Frame(self.root, padding=16)
        self.page.pack(fill="both", expand=True)

    def show_login(self):
        self.clear()
        initial = not self.auth.store.has_admin()
        ttk.Label(self.page, text="Create administrator" if initial else "Hostel login",
                  font=("TkDefaultFont", 17)).pack(pady=16)
        fields = {}
        for key, label in (("name", "Full name"), ("username", "Username"),
                           ("password", "Password")) if initial else (("username", "Username"),
                                                                        ("password", "Password")):
            row = ttk.Frame(self.page)
            row.pack(pady=5)
            ttk.Label(row, text=label, width=14).pack(side="left")
            entry = ttk.Entry(row, width=30, show="*" if key == "password" else "")
            entry.pack(side="left")
            fields[key] = entry

        def submit():
            try:
                if initial:
                    self.auth.setup_admin(fields["username"].get(), fields["password"].get(),
                                          fields["name"].get())
                    messagebox.showinfo("Ready", "Administrator created. Please log in.")
                    self.show_login()
                else:
                    self.token = self.auth.login(fields["username"].get(), fields["password"].get())
                    self.root.unbind("<Return>")
                    self.show_home()
            except (ValueError, sqlite3.Error) as exc:
                messagebox.showerror("Cannot continue", str(exc))

        ttk.Button(self.page, text="Create" if initial else "Log in", command=submit).pack(pady=12)
        fields["username"].focus_set()
        self.root.bind("<Return>", lambda _event: submit())

    def logout(self):
        self.auth.logout(self.token)
        self.token = None
        self.selected_resident_id = None
        self.root.unbind("<Return>")
        self.show_login()

    def show_home(self):
        previous = None
        if hasattr(self, "tabs") and self.tabs.winfo_exists():
            previous = self.tabs.tab(self.tabs.select(), "text")
        self.clear()
        user = self.auth.require(self.token)
        top = ttk.Frame(self.page)
        top.pack(fill="x", pady=(0, 12))
        ttk.Label(top, text=f"{user['full_name']} ({user['role'].title()})",
                  font=("TkDefaultFont", 13)).pack(side="left")
        ttk.Button(top, text="Log out", command=self.logout).pack(side="right")
        tabs = ttk.Notebook(self.page)
        tabs.pack(fill="both", expand=True)
        self.tabs = tabs
        if user["role"] == "ADMIN":
            setup = ttk.Frame(tabs, padding=10)
            tabs.add(setup, text="Setup")
            self.build_setup(setup)
        residents = ttk.Frame(tabs, padding=10)
        tabs.add(residents, text="Residents" if user["role"] != "RESIDENT" else "My room")
        self.build_residents(residents, user)
        fees = ttk.Frame(tabs, padding=10)
        tabs.add(fees, text="Fees" if user["role"] != "RESIDENT" else "My fees")
        self.build_fees(fees, user)
        for tab in tabs.tabs():
            if tabs.tab(tab, "text") == previous:
                tabs.select(tab)
                break

    def action(self, call):
        try:
            result = call()
            self.show_home()
            return result
        except (ValueError, sqlite3.Error) as exc:
            messagebox.showerror("Cannot complete action", str(exc))
            return None

    def form(self, title, fields, save):
        """fields: (key, caption, optional list of (caption, value))."""
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.transient(self.root)
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill="both", expand=True)
        widgets, choices = {}, {}
        for key, label, options in fields:
            row = ttk.Frame(frame)
            row.pack(fill="x", pady=5)
            ttk.Label(row, text=label, width=20).pack(side="left")
            if options is None:
                widget = ttk.Entry(row, width=34, show="*" if key == "password" else "")
            else:
                captions = [caption for caption, _ in options]
                widget = ttk.Combobox(row, values=captions, state="readonly", width=31)
                if captions:
                    widget.current(0)
                choices[key] = dict(options)
            widget.pack(side="left")
            widgets[key] = widget

        def submit():
            values = {}
            for key, widget in widgets.items():
                text = widget.get()
                values[key] = choices[key].get(text) if key in choices else text
            try:
                if save(values) is False:
                    return
            except (ValueError, sqlite3.Error) as exc:
                messagebox.showerror("Cannot save", str(exc), parent=dialog)
                return
            dialog.destroy()
            self.show_home()

        buttons = ttk.Frame(frame)
        buttons.pack(pady=(14, 0))
        ttk.Button(buttons, text="Save", command=submit).pack(side="left", padx=5)
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="left", padx=5)
        if widgets:
            next(iter(widgets.values())).focus_set()

    @staticmethod
    def table(parent, headings, rows, height=8):
        table = ttk.Treeview(parent, columns=[key for key, _ in headings],
                             show="headings", height=height)
        for key, label in headings:
            table.heading(key, text=label)
            table.column(key, width=125, anchor="w")
        table.pack(fill="both", expand=True, pady=6)
        for iid, values in rows:
            table.insert("", "end", iid=str(iid), values=values)
        return table

    @staticmethod
    def selected(table, label):
        chosen = table.selection()
        if not chosen:
            raise ValueError(f"Select a {label} first")
        return int(chosen[0])

    def build_setup(self, page):
        wardens = self.hostel.wardens(self.token)
        hostels = self.hostel.hostels(self.token)
        rooms = self.hostel.rooms(self.token)
        buttons = ttk.Frame(page)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Add warden", command=lambda: self.form("Add warden", [
            ("username", "Username", None), ("password", "Password", None),
            ("name", "Full name", None), ("employee", "Employee no.", None)],
            lambda v: self.hostel.add_warden(self.token, v["username"], v["password"],
                                             v["name"], v["employee"]))).pack(side="left", padx=4)
        ttk.Button(buttons, text="Add hostel", command=lambda: self.form("Add hostel", [
            ("code", "Code", None), ("name", "Name", None), ("address", "Address", None),
            ("warden", "Warden", [(f"{w['full_name']} ({w['employee_no']})", w["warden_id"])
                                     for w in wardens if w["is_active"]])],
            lambda v: self.hostel.add_hostel(self.token, v["code"], v["name"],
                                             v["address"], v["warden"]))).pack(side="left", padx=4)
        ttk.Button(buttons, text="Add room", command=lambda: self.form("Add room", [
            ("hostel", "Hostel", [(h["hostel_code"], h["hostel_id"])
                                   for h in hostels if h["is_active"]]),
            ("number", "Room no.", None), ("capacity", "Beds", None),
            ("fee", "Monthly fee (₹)", None)],
            lambda v: self.hostel.add_room(self.token, v["hostel"], v["number"],
                                           v["capacity"], v["fee"]))).pack(side="left", padx=4)
        ttk.Label(page, text="Wardens").pack(anchor="w", pady=(15, 0))
        self.table(page, [("name", "Name"), ("employee", "Employee no.")],
                   [(w["warden_id"], (w["full_name"], w["employee_no"])) for w in wardens], 4)
        ttk.Label(page, text="Hostels and rooms").pack(anchor="w")
        self.table(page, [("hostel", "Hostel"), ("room", "Room"), ("beds", "Occupied / beds"),
                          ("fee", "Monthly fee")],
                   [(r["room_id"], (r["hostel_code"], r["room_number"],
                                    f"{r['occupied']} / {r['capacity']}",
                                    money(r["monthly_fee_paise"]))) for r in rooms], 8)

    def build_residents(self, page, user):
        residents = self.hostel.residents(self.token)
        if user["role"] == "RESIDENT":
            resident = residents[0]
            ttk.Label(page, text=f"{resident['full_name']} · {resident['registration_no']}",
                      font=("TkDefaultFont", 13)).pack(anchor="w")
            ttk.Label(page, text=f"Hostel {resident['hostel_code']} · "
                                 f"Room {resident['room_number'] or 'Not allocated'} · "
                                 f"{resident['status']}").pack(anchor="w", pady=8)
            stays = self.hostel.stays(self.token, resident["resident_id"])
            self.table(page, [("room", "Room"), ("from", "Check in"), ("to", "Check out")],
                       [(a["allocation_id"], (a["room_number"], a["checked_in_at"][:16],
                                                (a["checked_out_at"] or "Current")[:16]))
                        for a in stays])
            return
        toolbar = ttk.Frame(page)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="Register", command=self.register_dialog).pack(side="left", padx=3)
        table = self.table(page, [("reg", "Registration"), ("name", "Name"),
                                  ("hostel", "Hostel"), ("room", "Room"), ("status", "Status")],
                           [(r["resident_id"], (r["registration_no"], r["full_name"],
                                                r["hostel_code"], r["room_number"] or "—",
                                                r["status"])) for r in residents], 16)

        def room_dialog(transfer):
            try:
                resident_id = self.selected(table, "resident")
                resident = next(r for r in residents if r["resident_id"] == resident_id)
                options = [(f"{r['room_number']} ({r['occupied']}/{r['capacity']} beds)", r["room_id"])
                           for r in self.hostel.rooms(self.token)
                           if r["hostel_id"] == resident["hostel_id"] and r["status"] == "OPEN"
                           and r["occupied"] < r["capacity"] and r["room_id"] != resident["room_id"]]
                if not options:
                    raise ValueError("No available room in this hostel")
                operation = self.hostel.transfer if transfer else self.hostel.allocate
                self.form("Transfer room" if transfer else "Allocate room", [("room", "Room", options)],
                          lambda v: operation(self.token, resident_id, v["room"]))
            except ValueError as exc:
                messagebox.showerror("Cannot continue", str(exc))

        ttk.Button(toolbar, text="Allocate", command=lambda: room_dialog(False)).pack(side="left", padx=3)
        ttk.Button(toolbar, text="Transfer", command=lambda: room_dialog(True)).pack(side="left", padx=3)
        ttk.Button(toolbar, text="Check out", command=lambda: self.action(
            lambda: self.hostel.checkout(self.token, self.selected(table, "resident")))).pack(side="left", padx=3)

    def register_dialog(self):
        hostels = self.hostel.hostels(self.token)
        self.form("Register resident", [
            ("hostel", "Hostel", [(h["hostel_code"], h["hostel_id"])
                                   for h in hostels if h["is_active"]]),
            ("reg", "Registration no.", None), ("name", "Full name", None),
            ("username", "Username", None), ("password", "Password", None)],
            lambda v: self.hostel.register(self.token, v["hostel"], v["username"],
                                           v["password"], v["name"], v["reg"]))

    def build_fees(self, page, user):
        residents = self.hostel.residents(self.token)
        if not residents:
            ttk.Label(page, text="No residents yet.").pack(anchor="w")
            return
        picker = ttk.Frame(page)
        picker.pack(fill="x")
        if user["role"] == "RESIDENT":
            self.selected_resident_id = user["user_id"]
        else:
            options = {f"{r['registration_no']} · {r['full_name']}": r["resident_id"] for r in residents}
            selected = next((name for name, rid in options.items()
                             if rid == self.selected_resident_id), next(iter(options)))
            combo = ttk.Combobox(picker, values=list(options), state="readonly", width=35)
            combo.set(selected)
            combo.pack(side="left", padx=4)
            self.selected_resident_id = options[selected]

            def change(_event):
                self.selected_resident_id = options[combo.get()]
                fill()

            combo.bind("<<ComboboxSelected>>", change)
            ttk.Button(picker, text="Generate missing fees", command=lambda: self.action(
                lambda: self.billing.generate(self.token, self.selected_resident_id))).pack(side="left", padx=4)

        ttk.Label(page, text="Monthly charges").pack(anchor="w", pady=(14, 0))
        charge_frame = ttk.Frame(page)
        charge_frame.pack(fill="both", expand=True)
        ttk.Label(page, text="Payments (payment ID is the receipt number)").pack(anchor="w", pady=(14, 0))
        payment_frame = ttk.Frame(page)
        payment_frame.pack(fill="both", expand=True)
        if user["role"] != "RESIDENT":
            def payment_dialog():
                try:
                    charge_id = self.selected(charge_table[0], "charge")
                    self.form("Record payment", [("amount", "Amount (₹)", None),
                                                  ("method", "Method", [(m, m) for m in
                                                                         ("CASH", "UPI", "BANK")])],
                              lambda v: self._save_payment(charge_id, v))
                except ValueError as exc:
                    messagebox.showerror("Cannot continue", str(exc))
            ttk.Button(picker, text="Record payment", command=payment_dialog).pack(side="left", padx=4)
        charge_table = [None]

        def fill():
            for frame in (charge_frame, payment_frame):
                for child in frame.winfo_children():
                    child.destroy()
            charges, payments = self.billing.statement(self.token, self.selected_resident_id)
            charge_table[0] = self.table(charge_frame,
                [("month", "Month"), ("charge", "Charge"), ("paid", "Paid"), ("due", "Balance")],
                [(c["charge_id"], (c["billing_month"], money(c["amount_paise"]),
                                   money(c["paid_paise"]), money(c["balance_paise"])))
                 for c in charges], 7)
            self.table(payment_frame,
                [("id", "Receipt"), ("month", "Month"), ("amount", "Amount"),
                 ("method", "Method"), ("date", "Paid at")],
                [(p["payment_id"], (p["payment_id"], p["billing_month"],
                                    money(p["amount_paise"]), p["method"], p["paid_at"][:16]))
                 for p in payments], 7)

        fill()

    def _save_payment(self, charge_id, values):
        if not messagebox.askyesno("Confirm payment", "Save this payment? Payments cannot be edited."):
            return False
        self.billing.pay(self.token, charge_id, values["amount"], values["method"])
