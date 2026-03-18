"""
IMAP sync engine.

Copies all messages from every folder on the source server to the
destination server, preserving flags and folder structure.

Progress is reported via a callback so the GUI can update in real-time.
Each sync job runs in its own thread so the UI stays responsive.
"""
import imaplib
import threading
import email
import time
from typing import Callable, Optional

# ---------------------------------------------------------------------------
# Progress callback type: (account_id, folder, done, total, status_msg)
# ---------------------------------------------------------------------------
ProgressCallback = Callable[[int, str, int, int, str], None]


def _connect(host: str, port: int, use_ssl: bool,
             username: str, password: str) -> imaplib.IMAP4:
    if use_ssl:
        conn = imaplib.IMAP4_SSL(host, port)
    else:
        conn = imaplib.IMAP4(host, port)
    conn.login(username, password)
    return conn


def _list_folders(conn: imaplib.IMAP4):
    """Return a list of folder name strings on the server."""
    status, folder_list = conn.list()
    if status != "OK" or not folder_list:
        return []
    folders = []
    for item in folder_list:
        if item is None:
            continue
        if isinstance(item, tuple):
            item = b" ".join(part for part in item if isinstance(part, bytes))
        if isinstance(item, memoryview):
            item = item.tobytes()
        if isinstance(item, bytes):
            item = item.decode("utf-8", errors="replace")
        if not isinstance(item, str):
            continue
        # Format: (\Flags) "delimiter" "name"
        parts = item.strip().split('"')
        if len(parts) >= 3:
            name = parts[-1].strip().strip('"')
        else:
            # Try space-split fallback
            name = item.split()[-1].strip('"')
        if name:
            folders.append(name)
    return folders


def _ensure_folder(conn: imaplib.IMAP4, folder: str) -> None:
    """Create folder on destination if it doesn't already exist."""
    quoted = f'"{folder}"'
    status, _ = conn.select(quoted)
    if status != "OK":
        conn.create(quoted)


def _sync_folder(src: imaplib.IMAP4, dst: imaplib.IMAP4,
                 folder: str, account_id: int,
                 progress_cb: Optional[ProgressCallback],
                 stop_event: threading.Event) -> None:
    """Copy all messages from one folder source → destination."""
    quoted = f'"{folder}"'

    # Select folder on source
    status, data = src.select(quoted, readonly=True)
    if status != "OK":
        if progress_cb:
            progress_cb(account_id, folder, 0, 0, f"Skipped (cannot select): {folder}")
        return

    total_str = data[0].decode() if data and data[0] else "0"
    try:
        total = int(total_str)
    except ValueError:
        total = 0

    if total == 0:
        if progress_cb:
            progress_cb(account_id, folder, 0, 0, f"Empty folder: {folder}")
        return

    # Ensure destination folder exists
    _ensure_folder(dst, folder)
    dst.select(quoted)

    # Fetch all message UIDs from source
    status, uid_data = src.uid("SEARCH", "ALL")
    if status != "OK" or not uid_data or not uid_data[0]:
        return

    uids = uid_data[0].split()
    total = len(uids)

    # Fetch UIDs already on destination to avoid duplicates
    dst_status, dst_uid_data = dst.uid("SEARCH", "ALL")

    existing_msg_ids: set = set()
    if dst_status == "OK" and dst_uid_data and dst_uid_data[0]:
        dst_uids_list = dst_uid_data[0].split()
        if dst_uids_list:
            fetch_range = b",".join(dst_uids_list).decode("ascii", errors="ignore")
            hdr_status, hdr_data = dst.uid("FETCH", fetch_range, "(BODY[HEADER.FIELDS (MESSAGE-ID)])")
            if hdr_status == "OK":
                for part in hdr_data:
                    if isinstance(part, tuple):
                        raw_hdr = part[1]
                        msg = email.message_from_bytes(raw_hdr)
                        mid = msg.get("Message-ID", "").strip()
                        if mid:
                            existing_msg_ids.add(mid)

    done = 0
    for uid in uids:
        if stop_event.is_set():
            if progress_cb:
                progress_cb(account_id, folder, done, total, "Cancelled")
            return

        # Fetch full message with flags
        status, msg_data = src.uid("FETCH", uid, "(FLAGS BODY.PEEK[])")
        if status != "OK" or not msg_data or msg_data[0] is None:
            done += 1
            continue

        # Parse flags and raw message bytes
        raw_flags = b""
        raw_message = b""
        for part in msg_data:
            if isinstance(part, tuple):
                raw_flags = part[0]
                raw_message = part[1]

        # Extract flags
        flags_str = ""
        if raw_flags:
            decoded = raw_flags.decode("utf-8", errors="replace")
            start = decoded.find("FLAGS (")
            if start != -1:
                end = decoded.find(")", start + 7)
                flags_str = decoded[start + 7: end] if end != -1 else ""

        # Check deduplication via Message-ID
        try:
            parsed = email.message_from_bytes(raw_message)
            msg_id = parsed.get("Message-ID", "").strip()
        except Exception:
            msg_id = ""

        if msg_id and msg_id in existing_msg_ids:
            done += 1
            if progress_cb:
                progress_cb(account_id, folder, done, total,
                            f"Syncing {folder} ({done}/{total})")
            continue

        # Convert flags to imaplib format tuple
        imap_flags = ""
        flag_map = {
            "\\Seen": "\\Seen",
            "\\Answered": "\\Answered",
            "\\Flagged": "\\Flagged",
            "\\Deleted": "\\Deleted",
            "\\Draft": "\\Draft",
        }
        final_flags = []
        for f, v in flag_map.items():
            if f.lower() in flags_str.lower():
                final_flags.append(v)
        imap_flags = "(" + " ".join(final_flags) + ")"

        # Append message to destination
        try:
            dst.append(quoted, imap_flags, imaplib.Time2Internaldate(time.time()), raw_message)
            if msg_id:
                existing_msg_ids.add(msg_id)
        except Exception as e:
            pass  # Do not abort the whole folder on a single message failure

        done += 1
        if progress_cb:
            progress_cb(account_id, folder, done, total,
                        f"Syncing {folder} ({done}/{total})")

    if progress_cb:
        progress_cb(account_id, folder, total, total,
                    f"Completed {folder} ({total} messages)")


def sync_account(account: dict,
                 progress_cb: Optional[ProgressCallback],
                 stop_event: threading.Event) -> None:
    """
    Sync a single account dict (as returned by database.get_account or
    database.get_accounts) from source to destination.

    account keys used:
        id, src_host, src_port, src_ssl, src_email, src_password,
              dst_host, dst_port, dst_ssl, dst_email, dst_password
    """
    account_id = account["id"]
    try:
        if progress_cb:
            progress_cb(account_id, "", 0, 0, "Connecting to source…")

        src = _connect(
            account["src_host"], account["src_port"],
            bool(account["src_ssl"]),
            account["src_email"], account["src_password"]
        )

        if progress_cb:
            progress_cb(account_id, "", 0, 0, "Connecting to destination…")

        dst = _connect(
            account["dst_host"], account["dst_port"],
            bool(account["dst_ssl"]),
            account["dst_email"], account["dst_password"]
        )

        if stop_event.is_set():
            src.logout()
            dst.logout()
            return

        folders = _list_folders(src)
        if not folders:
            folders = ["INBOX"]

        if progress_cb:
            progress_cb(account_id, "", 0, len(folders),
                        f"Found {len(folders)} folder(s)")

        for folder in folders:
            if stop_event.is_set():
                break
            _sync_folder(src, dst, folder, account_id, progress_cb, stop_event)

        src.logout()
        dst.logout()

        if progress_cb:
            if stop_event.is_set():
                progress_cb(account_id, "", 0, 0, "Stopped")
            else:
                progress_cb(account_id, "", 0, 0, "Done ✓")

    except Exception as e:
        if progress_cb:
            progress_cb(account_id, "", 0, 0, f"Error: {e}")


class SyncManager:
    """Manages concurrent sync jobs, one thread per account."""

    def __init__(self):
        self._threads: dict[int, threading.Thread] = {}
        self._stops: dict[int, threading.Event] = {}

    def start(self, account: dict, progress_cb: ProgressCallback) -> None:
        account_id = account["id"]
        if account_id in self._threads and self._threads[account_id].is_alive():
            return  # Already running

        stop_event = threading.Event()
        self._stops[account_id] = stop_event

        t = threading.Thread(
            target=sync_account,
            args=(account, progress_cb, stop_event),
            daemon=True,
        )
        self._threads[account_id] = t
        t.start()

    def stop(self, account_id: int) -> None:
        if account_id in self._stops:
            self._stops[account_id].set()

    def stop_all(self) -> None:
        for ev in self._stops.values():
            ev.set()

    def is_running(self, account_id: int) -> bool:
        t = self._threads.get(account_id)
        return t is not None and t.is_alive()

    def running_count(self) -> int:
        self._prune_finished()
        return sum(1 for thread in self._threads.values() if thread.is_alive())

    def _prune_finished(self) -> None:
        finished_ids = [
            account_id
            for account_id, thread in self._threads.items()
            if not thread.is_alive()
        ]
        for account_id in finished_ids:
            self._threads.pop(account_id, None)
            self._stops.pop(account_id, None)
