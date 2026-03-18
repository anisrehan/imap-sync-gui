"""
Main application window powered by ttkbootstrap.
"""
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Dict

import ttkbootstrap as tb
from ttkbootstrap.scrolled import ScrolledFrame

import app.database as db
from app.sync import SyncManager
from app.ui.dialogs import AccountDialog, ServerDialog
from app.version import APP_DESCRIPTION, APP_NAME, APP_SUBTITLE, APP_VERSION

_STATE_IDLE = ("secondary", "#adb5bd")
_STATE_RUNNING = ("info", "#0dcaf0")
_STATE_DONE = ("success", "#198754")
_STATE_ERROR = ("danger", "#dc3545")
_STATE_STOPPED = ("warning", "#fd7e14")


def _msg_state(msg: str) -> tuple:
    message = msg.lower()
    if "error" in message:
        return _STATE_ERROR
    if "done" in message or "completed" in message:
        return _STATE_DONE
    if "cancelled" in message or "stopped" in message:
        return _STATE_STOPPED
    if any(keyword in message for keyword in ("connecting", "syncing", "found", "starting", "empty")):
        return _STATE_RUNNING
    return _STATE_IDLE


def _asset(filename: str) -> str:
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.normpath(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets")
        )
    return os.path.join(base, filename)


class AboutDialog(tb.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title(f"About {APP_NAME}")
        self.resizable(False, False)
        self.grab_set()

        tb.Frame(self, bootstyle="primary", height=5).pack(fill="x")

        body = tb.Frame(self, padding=(28, 20))
        body.pack(fill="both", expand=True)

        try:
            raw = tk.PhotoImage(file=_asset("icon.png"))
            img = raw.subsample(4, 4)
            lbl = tb.Label(body, image=img)
            lbl.image = img
            lbl.pack(pady=(0, 8))
        except Exception:
            tb.Label(body, text="Mail", font=("", 22, "bold")).pack(pady=(0, 8))

        tb.Label(body, text=APP_NAME, font=("", 16, "bold"), bootstyle="primary").pack()
        tb.Label(body, text=f"Version {APP_VERSION}", font=("", 9), bootstyle="secondary").pack(pady=(2, 4))
        tb.Label(body, text=APP_SUBTITLE, font=("", 10, "italic")).pack()

        tb.Separator(body).pack(fill="x", pady=10)
        tb.Label(body, text=APP_DESCRIPTION, wraplength=340, justify="center", font=("", 9)).pack()
        tb.Separator(body).pack(fill="x", pady=10)

        tb.Label(
            body,
            text="Credentials encrypted with AES-128 Fernet.\nData stored in: ~/.config/imap-sync-gui/",
            font=("", 8),
            bootstyle="secondary",
            justify="center",
        ).pack()

        tb.Button(body, text="Close", bootstyle="primary-outline", command=self.destroy, width=12).pack(
            pady=(16, 0)
        )

        self.transient(parent)
        self.wait_window()


class MainWindow(tb.Window):
    def __init__(self):
        super().__init__(
            title=f"{APP_NAME}   -   {APP_SUBTITLE}",
            themename="flatly",
            size=(1160, 680),
        )
        self.minsize(960, 540)

        self._sync_mgr = SyncManager()
        self._is_closing = False
        self._close_deadline_job = None
        self._close_poll_job = None
        self._progress_widgets: Dict[int, dict] = {}

        try:
            icon = tk.PhotoImage(file=_asset("icon.png"))
            self.iconphoto(True, icon)
        except Exception:
            pass

        self._build_menu()
        self._build_ui()
        self._refresh_servers()
        self._refresh_accounts()
        self._tick_statusbar()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_menu(self):
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Import Accounts from CSV...", command=self._import_csv)
        file_menu.add_separator()
        file_menu.add_command(label="Quit", command=self._on_close)
        menubar.add_cascade(label="File", menu=file_menu)

        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label=f"About {APP_NAME}...", command=lambda: AboutDialog(self))
        menubar.add_cascade(label="Help", menu=help_menu)

        self.configure(menu=menubar)

    def _build_ui(self):
        main = tb.Frame(self, padding=(8, 6, 8, 2))
        main.pack(fill="both", expand=True)

        container = tb.Frame(main)
        container.pack(fill="both", expand=True)

        left = tb.Frame(container, width=415)
        left.pack_propagate(False)
        left.pack(side="left", fill="y")

        tb.Separator(container, orient="vertical").pack(side="left", fill="y", padx=(0, 4))

        nb = tb.Notebook(left, bootstyle="primary")
        nb.pack(fill="both", expand=True)

        srv_tab = tb.Frame(nb, padding=(4, 6))
        nb.add(srv_tab, text="   Servers   ")
        self._build_server_tab(srv_tab)

        acc_tab = tb.Frame(nb, padding=(4, 6))
        nb.add(acc_tab, text="   Accounts   ")
        self._build_account_tab(acc_tab)

        right = tb.Frame(container, padding=(8, 0, 0, 0))
        right.pack(side="left", fill="both", expand=True)

        hdr = tb.Frame(right)
        hdr.pack(fill="x", pady=(0, 4))

        tb.Label(hdr, text="Sync Dashboard", font=("", 13, "bold"), bootstyle="primary").pack(side="left")

        toolbar = tb.Frame(hdr)
        toolbar.pack(side="right")

        tb.Button(toolbar, text="Refresh", bootstyle="secondary-outline", command=self._refresh_dashboard).pack(
            side="right", padx=(2, 0)
        )
        tb.Separator(toolbar, orient="vertical").pack(side="right", padx=6, fill="y", pady=2)
        tb.Button(toolbar, text="Stop All", bootstyle="warning-outline", command=self._stop_all).pack(
            side="right", padx=2
        )
        tb.Button(toolbar, text="Stop Selected", bootstyle="warning-outline", command=self._stop_selected).pack(
            side="right", padx=2
        )
        tb.Button(toolbar, text="Start All", bootstyle="success", command=self._start_all).pack(
            side="right", padx=2
        )
        tb.Button(
            toolbar,
            text="Start Selected",
            bootstyle="success-outline",
            command=self._start_selected,
        ).pack(side="right", padx=2)

        tb.Separator(right).pack(fill="x", pady=(0, 6))

        sf = ScrolledFrame(right, autohide=True, bootstyle="round")
        sf.pack(fill="both", expand=True)
        self._prog_frame = sf
        self._prog_frame.columnconfigure(0, weight=1)

        sb = tb.Frame(self, bootstyle="dark", padding=(10, 3))
        sb.pack(fill="x", side="bottom")

        self._sb_accounts = tb.Label(sb, text="", bootstyle="inverse-dark", font=("", 8))
        self._sb_accounts.pack(side="left")

        self._sb_running = tb.Label(sb, text="", bootstyle="inverse-dark", font=("", 8))
        self._sb_running.pack(side="left", padx=(14, 0))

        tb.Label(sb, text=f"v{APP_VERSION}", bootstyle="inverse-dark", font=("", 8)).pack(side="right")

    def _tick_statusbar(self):
        if self._is_closing:
            return
        try:
            account_count = len(db.get_accounts())
            running_count = self._sync_mgr.running_count()
            self._sb_accounts.configure(text=f"{account_count} account{'s' if account_count != 1 else ''} configured")
            if running_count:
                self._sb_running.configure(text=f"  -  {running_count} running", bootstyle="inverse-success")
            else:
                self._sb_running.configure(text="  -  Idle", bootstyle="inverse-dark")
        except tk.TclError:
            return
        self.after(2000, self._tick_statusbar)

    def _build_server_tab(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        cols = ("name", "host", "port", "ssl")
        self._srv_tree = tb.Treeview(parent, columns=cols, show="headings", selectmode="browse", height=10)

        for col, text, width, anchor in (
            ("name", "Profile Name", 128, "w"),
            ("host", "Host / IP", 145, "w"),
            ("port", "Port", 55, "center"),
            ("ssl", "SSL", 45, "center"),
        ):
            self._srv_tree.heading(col, text=text)
            self._srv_tree.column(col, width=width, anchor=anchor)

        vsb = tb.Scrollbar(parent, orient="vertical", command=self._srv_tree.yview, bootstyle="round")
        self._srv_tree.configure(yscrollcommand=vsb.set)
        self._srv_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        btns = tb.Frame(parent, padding=(0, 6))
        btns.grid(row=1, column=0, columnspan=2)
        tb.Button(btns, text="+ Add", bootstyle="primary", width=9, command=self._add_server).pack(side="left", padx=2)
        tb.Button(btns, text="Edit", bootstyle="secondary-outline", width=9, command=self._edit_server).pack(side="left", padx=2)
        tb.Button(btns, text="Delete", bootstyle="danger-outline", width=9, command=self._delete_server).pack(side="left", padx=2)

    def _refresh_servers(self):
        self._srv_tree.delete(*self._srv_tree.get_children())
        for server in db.get_servers():
            self._srv_tree.insert(
                "",
                "end",
                iid=str(server["id"]),
                values=(server["name"], server["host"], server["port"], "Yes" if server["use_ssl"] else "No"),
            )

    def _add_server(self):
        dlg = ServerDialog(self)
        if dlg.result:
            db.add_server(**dlg.result)
            self._refresh_servers()
            self._refresh_accounts()

    def _edit_server(self):
        sel = self._srv_tree.selection()
        if not sel:
            return
        server = db.get_server(int(sel[0]))
        if not server:
            return
        dlg = ServerDialog(self, server)
        if dlg.result:
            db.update_server(server["id"], **dlg.result)
            self._refresh_servers()
            self._refresh_accounts()

    def _delete_server(self):
        sel = self._srv_tree.selection()
        if not sel:
            return
        if not messagebox.askyesno(
            "Confirm Delete",
            "Delete this server? All associated accounts will also be removed.",
            parent=self,
        ):
            return
        db.delete_server(int(sel[0]))
        self._refresh_servers()
        self._refresh_accounts()
        self._refresh_dashboard()

    def _build_account_tab(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        cols = ("src_email", "src_server", "dst_email", "dst_server")
        self._acc_tree = tb.Treeview(parent, columns=cols, show="headings", selectmode="browse", height=10)

        for col, text, width in (
            ("src_email", "Source Email", 145),
            ("src_server", "Source Server", 90),
            ("dst_email", "Dest Email", 145),
            ("dst_server", "Dest Server", 90),
        ):
            self._acc_tree.heading(col, text=text)
            self._acc_tree.column(col, width=width)

        vsb = tb.Scrollbar(parent, orient="vertical", command=self._acc_tree.yview, bootstyle="round")
        self._acc_tree.configure(yscrollcommand=vsb.set)
        self._acc_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        btns = tb.Frame(parent, padding=(0, 6))
        btns.grid(row=1, column=0, columnspan=2)
        tb.Button(btns, text="+ Add", bootstyle="primary", width=9, command=self._add_account).pack(side="left", padx=2)
        tb.Button(btns, text="Edit", bootstyle="secondary-outline", width=9, command=self._edit_account).pack(side="left", padx=2)
        tb.Button(btns, text="Delete", bootstyle="danger-outline", width=9, command=self._delete_account).pack(side="left", padx=2)
        tb.Button(btns, text="CSV", bootstyle="info-outline", width=9, command=self._import_csv).pack(side="left", padx=2)

    def _refresh_accounts(self):
        self._acc_tree.delete(*self._acc_tree.get_children())
        for account in db.get_accounts():
            self._acc_tree.insert(
                "",
                "end",
                iid=str(account["id"]),
                values=(
                    account["src_email"],
                    account["src_server_name"],
                    account["dst_email"],
                    account["dst_server_name"],
                ),
            )
        self._refresh_dashboard()

    def _add_account(self):
        dlg = AccountDialog(self)
        if dlg.result:
            db.add_account(**dlg.result)
            self._refresh_accounts()

    def _edit_account(self):
        sel = self._acc_tree.selection()
        if not sel:
            return
        account = db.get_account(int(sel[0]))
        if not account:
            return
        dlg = AccountDialog(self, account)
        if dlg.result:
            db.update_account(account["id"], **dlg.result)
            self._refresh_accounts()

    def _delete_account(self):
        sel = self._acc_tree.selection()
        if not sel:
            return
        if not messagebox.askyesno("Confirm Delete", "Delete this account?", parent=self):
            return
        db.delete_account(int(sel[0]))
        self._refresh_accounts()

    def _import_csv(self):
        servers = db.get_servers()
        if len(servers) < 2:
            messagebox.showinfo("Import CSV", "You need at least two server profiles before importing.", parent=self)
            return
        dlg = _ServerPickerDialog(self, servers)
        if not dlg.result:
            return
        src_id, dst_id = dlg.result
        path = filedialog.askopenfilename(
            parent=self,
            title="Select CSV file",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            count = db.import_accounts_csv(path, src_id, dst_id)
            messagebox.showinfo("Import", f"Imported {count} account(s).", parent=self)
        except Exception as exc:
            messagebox.showerror("Import Error", str(exc), parent=self)
        self._refresh_accounts()

    def _refresh_dashboard(self):
        for widget in self._prog_frame.winfo_children():
            widget.destroy()
        self._progress_widgets.clear()

        accounts = db.get_accounts()
        if not accounts:
            tb.Label(
                self._prog_frame,
                text="No accounts configured yet.\nAdd servers and accounts in the left panel.",
                font=("", 10),
                bootstyle="secondary",
                justify="center",
            ).grid(row=0, column=0, pady=40)
            return

        for row_idx, acc in enumerate(accounts):
            self._add_progress_row(row_idx, acc)

    def _add_progress_row(self, row_idx: int, acc: dict):
        aid = acc["id"]

        card = tb.Frame(self._prog_frame, bootstyle="light")
        card.grid(row=row_idx, column=0, sticky="ew", padx=6, pady=3)
        card.columnconfigure(2, weight=1)

        _, idle_hex = _STATE_IDLE
        indicator = tk.Frame(card, width=5, bg=idle_hex)
        indicator.grid(row=0, column=0, rowspan=5, sticky="ns")

        sel_var = tk.BooleanVar(value=False)
        tb.Checkbutton(card, variable=sel_var, bootstyle="primary").grid(row=0, column=1, rowspan=2, padx=(6, 2), sticky="w")

        tb.Label(card, text=f"  {acc['src_email']}   ->   {acc['dst_email']}", font=("", 10, "bold")).grid(
            row=0, column=2, sticky="w", padx=(0, 6), pady=(6, 0)
        )

        tb.Label(
            card,
            text=f"  {acc['src_server_name']} ({acc['src_host']}) -> {acc['dst_server_name']} ({acc['dst_host']})",
            bootstyle="secondary",
            font=("", 8),
        ).grid(row=1, column=2, sticky="w", padx=(0, 6))

        bar = tb.Progressbar(card, orient="horizontal", mode="determinate", maximum=100, value=0, bootstyle="info-striped")
        bar.grid(row=2, column=1, columnspan=2, sticky="ew", padx=(8, 6), pady=(4, 2))

        status_var = tk.StringVar(value="Idle")
        status_lbl = tb.Label(card, textvariable=status_var, bootstyle="secondary", font=("", 8))
        status_lbl.grid(row=3, column=1, columnspan=2, sticky="w", padx=(8, 6), pady=(0, 6))

        btn_col = tb.Frame(card)
        btn_col.grid(row=0, column=3, rowspan=4, padx=(4, 8))
        tb.Button(btn_col, text="Start", bootstyle="success-outline", width=6, command=lambda a=acc: self._start_one(a)).pack(pady=2)
        tb.Button(btn_col, text="Stop", bootstyle="warning-outline", width=6, command=lambda a=acc: self._stop_one(a)).pack(pady=2)

        self._progress_widgets[aid] = {
            "sel_var": sel_var,
            "bar": bar,
            "status_var": status_var,
            "status_lbl": status_lbl,
            "indicator": indicator,
        }

    def _handle_progress(self, account_id: int, folder: str, done: int, total: int, msg: str):
        if self._is_closing:
            return
        try:
            self.after(0, self._apply_progress, account_id, folder, done, total, msg)
        except tk.TclError:
            pass

    def _apply_progress(self, account_id: int, folder: str, done: int, total: int, msg: str):
        if self._is_closing:
            return
        widgets = self._progress_widgets.get(account_id)
        if not widgets:
            return

        widgets["status_var"].set(msg)
        bootstyle, hex_colour = _msg_state(msg)

        try:
            widgets["indicator"].configure(bg=hex_colour)
            widgets["status_lbl"].configure(bootstyle=bootstyle)
        except tk.TclError:
            return

        bar_style = {
            "secondary": "info-striped",
            "info": "info-striped",
            "success": "success",
            "danger": "danger",
            "warning": "warning",
        }.get(bootstyle, "info-striped")

        try:
            widgets["bar"].configure(bootstyle=bar_style)
        except Exception:
            pass

        if total > 0:
            widgets["bar"]["value"] = int((done / total) * 100)
        elif bootstyle == "success":
            widgets["bar"]["value"] = 100

    def _start_one(self, account: dict):
        self._sync_mgr.start(account, self._handle_progress)
        widgets = self._progress_widgets.get(account["id"])
        if widgets:
            widgets["status_var"].set("Starting...")
            widgets["bar"]["value"] = 0

    def _stop_one(self, account: dict):
        self._sync_mgr.stop(account["id"])

    def _start_selected(self):
        accounts_by_id = {a["id"]: a for a in db.get_accounts()}
        for aid, widgets in self._progress_widgets.items():
            if widgets["sel_var"].get():
                account = accounts_by_id.get(aid)
                if account:
                    self._start_one(account)

    def _stop_selected(self):
        for aid, widgets in self._progress_widgets.items():
            if widgets["sel_var"].get():
                self._sync_mgr.stop(aid)

    def _start_all(self):
        for acc in db.get_accounts():
            self._start_one(acc)

    def _stop_all(self):
        self._sync_mgr.stop_all()

    def _on_close(self):
        if self._is_closing:
            return
        self._is_closing = True
        self._sync_mgr.stop_all()

        try:
            self.unbind_all("<MouseWheel>")
            self.unbind_all("<Button-4>")
            self.unbind_all("<Button-5>")
        except tk.TclError:
            pass

        for child in self.winfo_children():
            self._disable_widgets(child)

        self._close_poll_job = self.after(100, self._finish_close_if_idle)
        self._close_deadline_job = self.after(2500, self._force_close)

    def _finish_close_if_idle(self):
        if self._sync_mgr.running_count() == 0:
            self._force_close()
            return
        self._close_poll_job = self.after(100, self._finish_close_if_idle)

    def _force_close(self):
        for job_attr in ("_close_poll_job", "_close_deadline_job"):
            jid = getattr(self, job_attr, None)
            if jid:
                try:
                    self.after_cancel(jid)
                except tk.TclError:
                    pass
                setattr(self, job_attr, None)
        try:
            self.quit()
        except tk.TclError:
            pass
        try:
            self.destroy()
        except tk.TclError:
            pass

    def _disable_widgets(self, widget):
        try:
            widget.configure(state="disabled")
        except tk.TclError:
            pass
        for child in widget.winfo_children():
            self._disable_widgets(child)


class _ServerPickerDialog(tb.Toplevel):
    def __init__(self, parent, servers):
        super().__init__(parent)
        self.result = None
        self.title("Select Servers for Import")
        self.resizable(False, False)
        self.grab_set()

        tb.Frame(self, bootstyle="info", height=4).pack(fill="x")

        frame = tb.Frame(self, padding=(20, 16))
        frame.pack()

        names = [s["name"] for s in servers]
        ids = [s["id"] for s in servers]

        for row_i, (label, attr) in enumerate((
            ("Source Server (Plesk):", "_src"),
            ("Destination Server (cPanel):", "_dst"),
        )):
            tb.Label(frame, text=label).grid(row=row_i, column=0, sticky="e", padx=6, pady=6)
            var = tk.StringVar()
            cb = tb.Combobox(frame, textvariable=var, values=names, state="readonly", width=30, bootstyle="primary")
            cb.current(row_i if row_i < len(names) else 0)
            cb.grid(row=row_i, column=1, padx=6, pady=6)
            setattr(self, attr, var)

        btn_f = tb.Frame(frame, padding=(0, 8))
        btn_f.grid(row=2, column=0, columnspan=2)
        tb.Button(btn_f, text="OK", bootstyle="primary", width=10, command=lambda: self._ok(ids, names)).pack(
            side="left", padx=4
        )
        tb.Button(btn_f, text="Cancel", bootstyle="secondary-outline", width=10, command=self.destroy).pack(
            side="left", padx=4
        )

        self.transient(parent)
        self.wait_window()

    def _ok(self, ids, names):
        try:
            src_id = ids[names.index(self._src.get())]
            dst_id = ids[names.index(self._dst.get())]
        except ValueError:
            self.destroy()
            return
        self.result = (src_id, dst_id)
        self.destroy()
