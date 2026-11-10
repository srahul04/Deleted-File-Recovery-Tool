"""
Forensic Data Recovery Tool - Main Entry Point.
"""
import sys
import os
import tkinter as tk

# Ensure src package is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.ui.main_window import RecoveryToolUI


def main():
    root = tk.Tk()
    app = RecoveryToolUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
