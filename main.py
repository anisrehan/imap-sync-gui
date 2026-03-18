"""
IMAP Sync GUI - Plesk to cPanel Email Migration Tool
Entry point.
"""
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import init_db
from app.ui.main_window import MainWindow


def main():
    init_db()
    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
