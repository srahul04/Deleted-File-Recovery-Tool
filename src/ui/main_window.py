"""
Tkinter User Interface with Modern Controls, Drive Selector, Search & Sorting.
"""
import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import List, Dict, Optional

from src.core.models import RecoverableFile
from src.core.drive_reader import DriveReader
from src.core.recycle_bin import RecycleBinScanner
from src.core.carver_engine import DeepCarverEngine
from src.core.recovery_manager import RecoveryManager


class RecoveryToolUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Forensic Data Recovery Tool (Enterprise Edition)")
        self.root.geometry("1100x720")
        self.root.minsize(900, 600)

        # Application state
        self.all_files: Dict[str, RecoverableFile] = {}
        self.displayed_items: List[str] = []
        self.is_scanning = False
        self.active_carver: Optional[DeepCarverEngine] = None
        self.scan_thread: Optional[threading.Thread] = None

        self._check_admin_privileges()
        self._build_ui()
        self._load_drives()

    def _check_admin_privileges(self):
        self.has_admin = DriveReader.is_admin()

    def _build_ui(self):
        # 1. Admin Alert Banner (if not elevated)
        if not self.has_admin:
            banner = tk.Frame(self.root, bg="#FFD2D2", height=30)
            banner.pack(fill=tk.X, side=tk.TOP)
            lbl = tk.Label(
                banner,
                text="⚠️ Standard Privileges: Recycle Bin recovery active. Run as Administrator for Raw Physical Sector Recovery.",
                bg="#FFD2D2",
                fg="#900000",
                font=("Segoe UI", 9, "bold")
            )
            lbl.pack(pady=4)

        # 2. Main Top Controls Toolbar
        toolbar = ttk.Frame(self.root, padding=10)
        toolbar.pack(fill=tk.X, side=tk.TOP)

        # Target Selector Frame
        target_frame = ttk.LabelFrame(toolbar, text="Scan Target (Volume / Drive)", padding=5)
        target_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5)

        self.drive_combobox = ttk.Combobox(target_frame, width=38, state="readonly")
        self.drive_combobox.pack(side=tk.LEFT, padx=5, pady=2)

        ttk.Button(target_frame, text="↻ Refresh", command=self._load_drives, width=9).pack(side=tk.LEFT, padx=2)

        # Action Buttons Frame
        action_frame = ttk.LabelFrame(toolbar, text="Operations", padding=5)
        action_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5)

        self.start_btn = ttk.Button(action_frame, text="▶ Start Scan", command=self.start_scan)
        self.start_btn.pack(side=tk.LEFT, padx=4)

        self.stop_btn = ttk.Button(action_frame, text="⏹ Stop Scan", command=self.stop_scan, state="disabled")
        self.stop_btn.pack(side=tk.LEFT, padx=4)

        self.recover_btn = ttk.Button(action_frame, text="💾 Recover Selected", command=self.recover_selected)
        self.recover_btn.pack(side=tk.LEFT, padx=4)

        # Search Bar Frame
        search_frame = ttk.LabelFrame(toolbar, text="Filter Results", padding=5)
        search_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=5)

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._on_filter_changed)
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=22)
        search_entry.pack(side=tk.LEFT, padx=4)
        ttk.Button(search_frame, text="✕", width=3, command=lambda: self.search_var.set("")).pack(side=tk.LEFT)

        # 3. Metrics and Summary Bar
        metrics_bar = ttk.Frame(self.root, padding=(10, 2))
        metrics_bar.pack(fill=tk.X, side=tk.TOP)

        self.lbl_total = ttk.Label(metrics_bar, text="Total: 0", font=("Segoe UI", 9, "bold"))
        self.lbl_total.pack(side=tk.LEFT, padx=10)

        self.lbl_recycle = ttk.Label(metrics_bar, text="In Recycle Bin: 0", foreground="#005fb8")
        self.lbl_recycle.pack(side=tk.LEFT, padx=10)

        self.lbl_permanent = ttk.Label(metrics_bar, text="Permanently Deleted (Carved): 0", foreground="#b85f00")
        self.lbl_permanent.pack(side=tk.LEFT, padx=10)

        self.lbl_recovered = ttk.Label(metrics_bar, text="Restored: 0", foreground="#008000")
        self.lbl_recovered.pack(side=tk.LEFT, padx=10)

        # 4. Treeview Results Table
        table_frame = ttk.Frame(self.root, padding=10)
        table_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("name", "size", "source", "status", "timestamp", "location")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="extended")

        self.tree.heading("name", text="File Name", command=lambda: self._sort_by("name"))
        self.tree.heading("size", text="Size", command=lambda: self._sort_by("size"))
        self.tree.heading("source", text="Source", command=lambda: self._sort_by("source"))
        self.tree.heading("status", text="Status", command=lambda: self._sort_by("status"))
        self.tree.heading("timestamp", text="Timestamp", command=lambda: self._sort_by("timestamp"))
        self.tree.heading("location", text="Original / Sector Location", command=lambda: self._sort_by("location"))

        self.tree.column("name", width=220, anchor="w")
        self.tree.column("size", width=95, anchor="e")
        self.tree.column("source", width=110, anchor="center")
        self.tree.column("status", width=140, anchor="center")
        self.tree.column("timestamp", width=140, anchor="center")
        self.tree.column("location", width=340, anchor="w")

        v_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        h_scroll = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")

        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        # 5. Status & Progress Footer
        footer = ttk.Frame(self.root, padding=(10, 5))
        footer.pack(fill=tk.X, side=tk.BOTTOM)

        self.progress_bar = ttk.Progressbar(footer, orient="horizontal", mode="determinate")
        self.progress_bar.pack(fill=tk.X, side=tk.TOP, pady=2)

        self.status_label = ttk.Label(footer, text="Ready", relief=tk.SUNKEN, anchor="w")
        self.status_label.pack(fill=tk.X, side=tk.BOTTOM, pady=2)

    def _load_drives(self):
        """Populates targets dropdown with volumes and physical drives."""
        targets = DriveReader.list_available_targets()
        self.target_map = {t["name"]: t["id"] for t in targets}
        drive_names = list(self.target_map.keys())

        # Include an option for logical Recycle Bin only scan
        drive_names.insert(0, "All Disks: Recycle Bin Only (Fast)")

        self.drive_combobox["values"] = drive_names
        if drive_names:
            self.drive_combobox.current(0)

    def start_scan(self):
        if self.is_scanning:
            return

        selected_target_name = self.drive_combobox.get()
        target_id = self.target_map.get(selected_target_name)

        # Reset state
        self.all_files.clear()
        self.tree.delete(*self.tree.get_children())
        self._update_metrics(0, 0, 0, 0)
        self.progress_bar["value"] = 0

        self.is_scanning = True
        self.start_btn["state"] = "disabled"
        self.stop_btn["state"] = "normal"
        self.drive_combobox["state"] = "disabled"

        self.scan_thread = threading.Thread(
            target=self._scan_worker,
            args=(selected_target_name, target_id),
            daemon=True
        )
        self.scan_thread.start()

    def _scan_worker(self, target_name: str, target_id: Optional[str]):
        rb_count = 0
        perm_count = 0

        try:
            # Phase 1: Logical Scan (Recycle Bin)
            self._set_status("Scanning Recycle Bin across all volumes...")
            rb_files = RecycleBinScanner.scan_all_drives()
            for f in rb_files:
                self.all_files[f.file_id] = f
                if f.status == "In Recycle Bin":
                    rb_count += 1
                else:
                    perm_count += 1
                self.root.after(0, self._append_file_row, f)

            self.root.after(0, self._update_metrics, len(self.all_files), rb_count, perm_count, 0)

            # Phase 2: Physical / Volume Deep Sector Scan
            if target_id and not (self.active_carver and self.active_carver.is_cancelled):
                if not DriveReader.is_admin():
                    self._set_status("Notice: Administrative privileges needed for deep drive carving.")
                else:
                    self._set_status(f"Starting Deep File Carving on {target_name}...")
                    self.active_carver = DeepCarverEngine(target_id)

                    def on_progress(pct: float, msg: str):
                        self.root.after(0, self._update_progress, pct, msg)

                    def on_file_found(file_entry: RecoverableFile):
                        nonlocal perm_count
                        perm_count += 1
                        self.all_files[file_entry.file_id] = file_entry
                        self.root.after(0, self._append_file_row, file_entry)
                        self.root.after(0, self._update_metrics, len(self.all_files), rb_count, perm_count, 0)

                    self.active_carver.scan(progress_callback=on_progress, file_found_callback=on_file_found)

            self._set_status(f"Scan complete. Found {len(self.all_files)} recoverable item(s).")
            self.root.after(0, lambda: self.progress_bar.configure(value=100))

        except Exception as e:
            self._set_status(f"Scan stopped with error: {str(e)}")
            self.root.after(0, lambda: messagebox.showerror("Scan Error", str(e)))
        finally:
            self.is_scanning = False
            self.root.after(0, self._reset_controls)

    def _append_file_row(self, f: RecoverableFile):
        self.tree.insert("", "end", iid=f.file_id, values=(
            f.name,
            f.formatted_size,
            f.source_type,
            f.status,
            f.timestamp,
            f.location
        ))

    def _update_progress(self, pct: float, msg: str):
        self.progress_bar["value"] = pct
        self.status_label["text"] = msg

    def _set_status(self, text: str):
        self.root.after(0, lambda: self.status_label.configure(text=text))

    def _update_metrics(self, total: int, rb: int, permanent: int, recovered: int):
        self.lbl_total["text"] = f"Total: {total}"
        self.lbl_recycle["text"] = f"In Recycle Bin: {rb}"
        self.lbl_permanent["text"] = f"Permanently Deleted (Carved): {permanent}"
        self.lbl_recovered["text"] = f"Restored: {recovered}"

    def _reset_controls(self):
        self.start_btn["state"] = "normal"
        self.stop_btn["state"] = "disabled"
        self.drive_combobox["state"] = "readonly"

    def stop_scan(self):
        if self.active_carver:
            self.active_carver.is_cancelled = True
        self._set_status("Stopping scan...")

    def recover_selected(self):
        selected_ids = self.tree.selection()
        if not selected_ids:
            messagebox.showwarning("Selection Required", "Please select one or more files from the list to recover.")
            return

        dest_dir = filedialog.askdirectory(title="Select Destination Directory for Recovered Files")
        if not dest_dir:
            return

        success_count = 0
        error_count = 0

        self.progress_bar["value"] = 0
        total = len(selected_ids)

        for i, file_id in enumerate(selected_ids):
            rec_file = self.all_files.get(file_id)
            if not rec_file:
                continue

            try:
                self.status_label["text"] = f"Restoring {rec_file.name}..."
                RecoveryManager.recover_file(rec_file, dest_dir)
                success_count += 1
            except Exception as e:
                error_count += 1
                print(f"Failed to recover {rec_file.name}: {e}")

            self.progress_bar["value"] = ((i + 1) / total) * 100
            self.root.update_idletasks()

        self._update_metrics(len(self.all_files), 0, 0, success_count)
        messagebox.showinfo(
            "Recovery Summary",
            f"Extraction complete!\n\nSuccessfully saved: {success_count} file(s)\nFailed: {error_count}\nDestination: {dest_dir}"
        )
        self.status_label["text"] = f"Restoration finished: {success_count} recovered."

    def _on_filter_changed(self, *args):
        query = self.search_var.get().strip().lower()
        self.tree.delete(*self.tree.get_children())
        for f in self.all_files.values():
            if not query or query in f.name.lower() or query in f.location.lower() or query in f.status.lower():
                self._append_file_row(f)

    def _sort_by(self, col: str):
        # Sort current items
        items = list(self.all_files.values())
        if col == "size":
            items.sort(key=lambda x: x.size, reverse=True)
        elif col == "timestamp":
            items.sort(key=lambda x: x.timestamp, reverse=True)
        else:
            items.sort(key=lambda x: getattr(x, col, "").lower())

        self.tree.delete(*self.tree.get_children())
        for f in items:
            self._append_file_row(f)
