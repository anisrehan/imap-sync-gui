"""
Re-usable modal dialogs — modernized with ttkbootstrap.
"""
import tkinter as tk
from tkinter import messagebox
from typing import Optional, Dict

import ttkbootstrap as tb

import app.database as db


# ---------------------------------------------------------------------------
# Field helpers
# ---------------------------------------------------------------------------

def _field(parent, label_text: str, row: int, show: str = "") -> tk.StringVar:
    tb.Label(parent, text=label_text, anchor="e").grid(
        row=row, column=0, sticky="e", padx=(0, 8), pady=5)
    var = tk.StringVar()
    tb.Entry(parent, textvariable=var, width=34, show=show).grid(
        row=row, column=1, sticky="ew", pady=5)
    return var


def _int_field(parent, label_text: str, row: int) -> tk.IntVar:
    tb.Label(parent, text=label_text, anchor="e").grid(
        row=row, column=0, sticky="e", padx=(0, 8), pady=5)
    var = tk.IntVar()
    tb.Entry(parent, textvariable=var, width=10).grid(
        row=row, column=1, sticky="w", pady=5)
    return var


def _bool_field(parent, label_text: str, row: int) -> tk.BooleanVar:
    tb.Label(parent, text=label_text, anchor="e").grid(
        row=row, column=0, sticky="e", padx=(0, 8), pady=5)
    var = tk.BooleanVar(value=True)
    tb.Checkbutton(parent, variable=var, bootstyle="success-round-toggle").grid(
        row=row, column=1, sticky="w", pady=5)
    return var


def _section_banner(parent, text: str, row: int, bootstyle: str = "primary"):
    """A coloured full-width section header inside a dialog."""
    banner = tb.Frame(parent, bootstyle=bootstyle, height=2)
    banner.grid(row=row, column=0, columnspan=2, sticky="ew",
                pady=(10, 0), padx=0)
    tb.Label(parent, text=text,
             font=("", 9, "bold"), bootstyle=bootstyle).grid(
        row=row + 1, column=0, columnspan=2,
        sticky="w", padx=4, pady=(2, 6))


# ---------------------------------------------------------------------------
# Server dialog
# ---------------------------------------------------------------------------

class ServerDialog(tb.Toplevel):
    """Dialog for creating or editing a server profile."""

    def __init__(self, parent, server: Optional[Dict] = None):
        super().__init__(parent)
        self.result = None
        self.title("Edit Server" if server else "Add Server")
        self.resizable(False, False)
        self.grab_set()

        # Accent bar
        tb.Frame(self, bootstyle="primary", height=4).pack(fill="x")

        frame = tb.Frame(self, padding=(20, 16))
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)

        self._name     = _field(frame, "Profile Name:",            0)
        self._host     = _field(frame, "Host / IP:",               1)
        self._port     = _int_field(frame, "Port:",                2)
        self._ssl      = _bool_field(frame, "Use SSL / TLS:",      3)
        self._username = _field(frame, "Admin User (optional):",   4)
        self._password = _field(frame, "Admin Password (opt.):",   5, show="\u2022")

        if server:
            self._name.set(server.get("name", ""))
            self._host.set(server.get("host", ""))
            self._port.set(server.get("port", 993))
            self._ssl.set(bool(server.get("use_ssl", 1)))
            self._username.set(server.get("username", ""))
            self._password.set(server.get("password", ""))
        else:
            self._port.set(993)

        btn_f = tb.Frame(frame, padding=(0, 10))
        btn_f.grid(row=6, column=0, columnspan=2)
        tb.Button(btn_f, text="Save",   bootstyle="primary",          width=10,
                  command=self._save).pack(side="left", padx=4)
        tb.Button(btn_f, text="Cancel", bootstyle="secondary-outline", width=10,
                  command=self.destroy).pack(side="left", padx=4)

        self.transient(parent)
        self.wait_window()

    def _save(self):
        name = self._name.get().strip()
        host = self._host.get().strip()
        try:
            port = int(self._port.get())
        except (ValueError, tk.TclError):
            port = 993
        if not name or not host:
            messagebox.showwarning(
                "Validation", "Profile Name and Host are required.",
                parent=self)
            return
        self.result = {
            "name":     name,
            "host":     host,
            "port":     port,
            "use_ssl":  bool(self._ssl.get()),
            "username": self._username.get().strip(),
            "password": self._password.get(),
        }
        self.destroy()


# ---------------------------------------------------------------------------
# Account dialog
# ---------------------------------------------------------------------------

class AccountDialog(tb.Toplevel):
    """Dialog for creating or editing an email account pair."""

    def __init__(self, parent, account: Optional[Dict] = None):
        super().__init__(parent)
        self.result = None
        self.title("Edit Account" if account else "Add Account")
        self.resizable(False, False)
        self.grab_set()

        servers = db.get_servers()
        if not servers:
            messagebox.showerror(
                "No Servers",
                "Please add at least two server profiles first.",
                parent=parent)
            self.destroy()
            return

        self._server_ids = [s["id"]   for s in servers]
        server_names     = [s["name"] for s in servers]

        # Accent bar
        tb.Frame(self, bootstyle="primary", height=4).pack(fill="x")

        frame = tb.Frame(self, padding=(20, 12))
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)

        # ── Source ──
        _section_banner(frame, "Source Server  (Plesk)", row=0,
                        bootstyle="primary")
        tb.Label(frame, text="Server:", anchor="e").grid(
            row=2, column=0, sticky="e", padx=(0, 8), pady=5)
        self._src_srv = tk.StringVar()
        cb_src = tb.Combobox(frame, textvariable=self._src_srv,
                             values=server_names, state="readonly",
                             width=32, bootstyle="primary")
        cb_src.grid(row=2, column=1, sticky="ew", pady=5)
        self._src_email = _field(frame, "Email:",    3)
        self._src_pass  = _field(frame, "Password:", 4, show="\u2022")

        # ── Destination ──
        _section_banner(frame, "Destination Server  (cPanel)", row=5,
                        bootstyle="success")
        tb.Label(frame, text="Server:", anchor="e").grid(
            row=7, column=0, sticky="e", padx=(0, 8), pady=5)
        self._dst_srv = tk.StringVar()
        cb_dst = tb.Combobox(frame, textvariable=self._dst_srv,
                             values=server_names, state="readonly",
                             width=32, bootstyle="success")
        cb_dst.grid(row=7, column=1, sticky="ew", pady=5)
        self._dst_email = _field(frame, "Email:",    8)
        self._dst_pass  = _field(frame, "Password:", 9, show="\u2022")

        # Pre-fill
        if account:
            src_id = account.get("src_server_id")
            dst_id = account.get("dst_server_id")
            if src_id in self._server_ids:
                cb_src.current(self._server_ids.index(src_id))
            if dst_id in self._server_ids:
                cb_dst.current(self._server_ids.index(dst_id))
            self._src_email.set(account.get("src_email", ""))
            self._src_pass.set(account.get("src_password", ""))
            self._dst_email.set(account.get("dst_email", ""))
            self._dst_pass.set(account.get("dst_password", ""))
        else:
            if server_names:
                cb_src.current(0)
                cb_dst.current(min(1, len(server_names) - 1))

        btn_f = tb.Frame(frame, padding=(0, 10))
        btn_f.grid(row=10, column=0, columnspan=2)
        tb.Button(btn_f, text="Save",   bootstyle="primary",          width=10,
                  command=self._save).pack(side="left", padx=4)
        tb.Button(btn_f, text="Cancel", bootstyle="secondary-outline", width=10,
                  command=self.destroy).pack(side="left", padx=4)

        self.transient(parent)
        self.wait_window()

    def _save(self):
        src_name  = self._src_srv.get()
        dst_name  = self._dst_srv.get()
        smap      = {s["name"]: s["id"] for s in db.get_servers()}
        src_id    = smap.get(src_name)
        dst_id    = smap.get(dst_name)
        src_email = self._src_email.get().strip()
        src_pass  = self._src_pass.get()
        dst_email = self._dst_email.get().strip()
        dst_pass  = self._dst_pass.get()

        if not src_id or not dst_id:
            messagebox.showwarning(
                "Validation",
                "Please select both source and destination servers.",
                parent=self)
            return
        if not src_email or not dst_email:
            messagebox.showwarning(
                "Validation",
                "Both source and destination email addresses are required.",
                parent=self)
            return
        if src_id == dst_id and src_email == dst_email:
            messagebox.showwarning(
                "Validation",
                "Source and destination cannot be the same account.",
                parent=self)
            return

        self.result = {
            "src_server_id": src_id,
            "dst_server_id": dst_id,
            "src_email":     src_email,
            "src_password":  src_pass,
            "dst_email":     dst_email,
            "dst_password":  dst_pass,
        }
        self.destroy()
