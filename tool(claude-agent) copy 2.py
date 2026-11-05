import os
import sys
import struct
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import psutil
import ctypes
from datetime import datetime
import threading
import queue
import win32api
import win32con
import win32security
import shutil
import subprocess

class FileSignatures:
    """Enhanced file signatures with validation"""
    SIGNATURES = {
        'jpg': [
            {'sig': b'\xFF\xD8\xFF\xE0', 'ext': 'jpg', 'min_size': 100, 'max_size': 30*1024*1024},
            {'sig': b'\xFF\xD8\xFF\xE1', 'ext': 'jpg', 'min_size': 100, 'max_size': 30*1024*1024},
            {'sig': b'\xFF\xD8\xFF\xE8', 'ext': 'jpg', 'min_size': 100, 'max_size': 30*1024*1024}
        ],
        'png': [
            {'sig': b'\x89PNG\r\n\x1a\n', 'ext': 'png', 'min_size': 100, 'max_size': 50*1024*1024}
        ],
        'pdf': [
            {'sig': b'%PDF-', 'ext': 'pdf', 'min_size': 100, 'max_size': 100*1024*1024}
        ],
        'zip': [
            {'sig': b'PK\x03\x04', 'ext': 'zip', 'min_size': 100, 'max_size': 200*1024*1024},
            {'sig': b'PK\x05\x06', 'ext': 'zip', 'min_size': 100, 'max_size': 200*1024*1024}
        ],
        'mp3': [
            {'sig': b'\xFF\xFB', 'ext': 'mp3', 'min_size': 1024, 'max_size': 20*1024*1024},
            {'sig': b'\x49\x44\x33', 'ext': 'mp3', 'min_size': 1024, 'max_size': 20*1024*1024}
        ],
        'mp4': [
            {'sig': b'\x00\x00\x00\x20ftyp', 'ext': 'mp4', 'min_size': 1024, 'max_size': 500*1024*1024},
            {'sig': b'\x00\x00\x00\x18ftyp', 'ext': 'mp4', 'min_size': 1024, 'max_size': 500*1024*1024}
        ],
        'exe': [
            {'sig': b'MZ', 'ext': 'exe', 'min_size': 1024, 'max_size': 100*1024*1024}
        ],
        'bmp': [
            {'sig': b'BM', 'ext': 'bmp', 'min_size': 100, 'max_size': 50*1024*1024}
        ]
    }

class RecoveryTool:
    def __init__(self, root):
        self.root = root
        self.root.title("Advanced Data Recovery Tool")
        self.root.geometry("1000x700")
        
        # Initialize counters
        self.total_files = 0
        self.recycle_bin_files = 0
        self.permanent_deleted_files = 0
        self.recovered_files = 0
        
        # Store all files for searching
        self.all_files = []
        
        # Check for admin privileges
        if not self.is_admin():
            messagebox.showwarning("Admin Rights Recommended", 
                "For best results, especially for physical recovery, run as Administrator.")
        
        self.setup_ui()
        self.file_queue = queue.Queue()
        self.scan_thread = None
        self.is_scanning = False
        self.stop_scan = False
        self.current_scan_progress = 0
        
    def setup_ui(self):
        """Initialize the user interface"""
        # Top frame for controls and stats
        top_frame = ttk.Frame(self.root)
        top_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Control frame
        control_frame = ttk.LabelFrame(top_frame, text="Controls")
        control_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        ttk.Button(control_frame, text="Start Scan", command=self.start_scan).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(control_frame, text="Stop Scan", command=self.stop_scanning).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(control_frame, text="Recover Selected", command=self.recover_selected).pack(side=tk.LEFT, padx=5, pady=5)
        
        # Scan options
        self.deep_scan_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(control_frame, text="Deep Scan", variable=self.deep_scan_var).pack(side=tk.LEFT, padx=5, pady=5)
        
        # Validation option - disabled by default to show all files initially
        self.validate_files_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(control_frame, text="Validate Files", 
                       variable=self.validate_files_var).pack(side=tk.LEFT, padx=5, pady=5)
        
        # Search frame
        search_frame = ttk.LabelFrame(top_frame, text="Search")
        search_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.on_search_change)
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        
        ttk.Button(search_frame, text="Clear Search", command=self.clear_search).pack(side=tk.LEFT, padx=5, pady=5)
        
        # Stats frame
        stats_frame = ttk.LabelFrame(top_frame, text="Statistics")
        stats_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        self.stats_var = {
            'total': tk.StringVar(value="Total Files: 0"),
            'recycle': tk.StringVar(value="In Recycle Bin: 0"),
            'permanent': tk.StringVar(value="Permanently Deleted: 0"),
            'recovered': tk.StringVar(value="Recovered: 0")
        }
        
        for var in self.stats_var.values():
            ttk.Label(stats_frame, textvariable=var).pack(side=tk.LEFT, padx=10, pady=5)
        
        # Progress bar
        self.progress_var = tk.DoubleVar(value=0)
        self.progress = ttk.Progressbar(self.root, orient=tk.HORIZONTAL, 
                                      length=100, mode='determinate', 
                                      variable=self.progress_var)
        self.progress.pack(fill=tk.X, padx=5, pady=2)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN)
        status_label.pack(fill=tk.X, padx=5, pady=2)
        
        # Treeview for file list
        columns = ("Name", "Size", "Original Path", "Status", "Type", "Last Modified")
        
        # Create a frame to hold the Treeview and scrollbars
        tree_frame = ttk.Frame(self.root)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5)
        
        # Create vertical scrollbar
        y_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        y_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Create horizontal scrollbar
        x_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)
        x_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Configure Treeview with scrollbars
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                yscrollcommand=y_scrollbar.set,
                                xscrollcommand=x_scrollbar.set)
        
        # Configure scrollbar commands
        y_scrollbar.config(command=self.tree.yview)
        x_scrollbar.config(command=self.tree.xview)
        
        # Pack the Treeview
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Configure column widths and headings
        column_widths = {
            "Name": 200,
            "Size": 100,
            "Original Path": 250,
            "Status": 120,
            "Type": 80,
            "Last Modified": 150
        }
        
        for col, width in column_widths.items():
            if col == "Last Modified":
                self.tree.heading(col, text=col + " ▼", command=lambda c=col: self.sort_treeview(c))
            else:
                self.tree.heading(col, text=col, command=lambda c=col: self.sort_treeview(c))
            self.tree.column(col, width=width, minwidth=50)  # Add minwidth for better horizontal scrolling

        # Enable mouse wheel scrolling when hovering over treeview
        self.tree.bind('<MouseWheel>', lambda e: self.tree.yview_scroll(-1*(e.delta//120), "units"))
        self.tree.bind('<Shift-MouseWheel>', lambda e: self.tree.xview_scroll(-1*(e.delta//120), "units"))

    def is_admin(self):
        """Check if the script is running with administrator privileges"""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False

    def request_admin_privileges(self):
        """Request elevation of privileges"""
        if sys.argv[0].endswith('.py'):
            script = os.path.abspath(sys.argv[0])
            params = ' '.join([script] + sys.argv[1:])
            try:
                ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
                sys.exit()
            except:
                messagebox.showerror("Error", "Failed to obtain administrator privileges.")

    def start_scan(self):
        """Initiate the scanning process"""
        if self.is_scanning:
            messagebox.showwarning("Scan in Progress", "A scan is already running.")
            return
        
        self.tree.delete(*self.tree.get_children())
        self.all_files.clear()
        self.is_scanning = True
        self.status_var.set("Scanning...")
        
        self.scan_thread = threading.Thread(target=self.scan_process)
        self.scan_thread.daemon = True
        self.scan_thread.start()

    def stop_scanning(self):
        """Stop the scanning process"""
        if self.is_scanning:
            self.stop_scan = True
            self.status_var.set("Stopping scan...")
    
    def sort_treeview(self, col):
        """Sort treeview by column"""
        items = []
        for item in self.tree.get_children(''):
            val = self.tree.set(item, col)
            if col == "Last Modified":
                try:
                    val = datetime.strptime(val, "%Y-%m-%d %H:%M:%S")
                except:
                    val = datetime.min
            elif col == "Size":
                try:
                    if 'bytes' in val:
                        val = int(val.replace(' bytes', '').replace(',', ''))
                    else:
                        val = 0
                except:
                    val = 0
            items.append((val, item))
        
        items.sort(reverse=(col == "Last Modified"))
        
        for index, (val, item) in enumerate(items):
            self.tree.move(item, '', index)
    
    def on_search_change(self, *args):
        """Handle search as user types"""
        search_term = self.search_var.get().lower()
        self.perform_search(search_term)
    
    def clear_search(self):
        """Clear the search and show all files"""
        self.search_var.set("")
    
    def perform_search(self, search_term):
        """Perform the search and update the display"""
        self.tree.delete(*self.tree.get_children())
        
        if not search_term:
            for file_entry in self.all_files:
                self.tree.insert('', 'end', values=(
                    file_entry['name'],
                    file_entry['size'],
                    file_entry['path'],
                    file_entry['status'],
                    file_entry['file_type'],
                    file_entry['timestamp']
                ), tags=(file_entry['metadata'],))
        else:
            for file_entry in self.all_files:
                if (search_term in file_entry['name'].lower() or 
                    search_term in file_entry['path'].lower() or
                    search_term in file_entry['file_type'].lower()):
                    self.tree.insert('', 'end', values=(
                        file_entry['name'],
                        file_entry['size'],
                        file_entry['path'],
                        file_entry['status'],
                        file_entry['file_type'],
                        file_entry['timestamp']
                    ), tags=(file_entry['metadata'],))
    
    def update_stats(self):
        """Update statistics display"""
        self.stats_var['total'].set(f"Total Files: {self.total_files}")
        self.stats_var['recycle'].set(f"In Recycle Bin: {self.recycle_bin_files}")
        self.stats_var['permanent'].set(f"Permanently Deleted: {self.permanent_deleted_files}")
        self.stats_var['recovered'].set(f"Recovered: {self.recovered_files}")
        
    def scan_process(self):
        """Main scanning process"""
        try:
            self.tree.delete(*self.tree.get_children())
            self.all_files.clear()
            self.total_files = 0
            self.recycle_bin_files = 0
            self.permanent_deleted_files = 0
            self.recovered_files = 0
            self.stop_scan = False
            self.update_stats()
            
            # Phase 1: Logical Recovery (Recycle Bin)
            self.status_var.set("Scanning Recycle Bin...")
            self.progress_var.set(0)
            recycle_bin_files = self.scan_recycle_bin()
            
            if not self.stop_scan and self.deep_scan_var.get():
                # Phase 2: Physical Recovery
                self.status_var.set("Starting deep scan for permanently deleted files...")
                self.scan_physical_drives()
            
        except Exception as e:
            self.status_var.set(f"Error during scan: {str(e)}")
            messagebox.showerror("Error", f"An error occurred during scanning: {str(e)}")
        finally:
            self.is_scanning = False
            if self.stop_scan:
                self.status_var.set("Scan stopped by user")
            else:
                self.status_var.set(f"Scan completed. Found {self.total_files} files total")
            self.progress_var.set(100)
            self.update_stats()
            self.sort_treeview("Last Modified")

    def scan_recycle_bin(self):
        """Scan Windows Recycle Bin for recoverable files"""
        drives = [d.device for d in psutil.disk_partitions() if 'fixed' in d.opts]
        found_files = 0
        
        for drive in drives:
            if self.stop_scan:
                break
                
            recycle_path = os.path.join(drive, '$Recycle.Bin')
            if not os.path.exists(recycle_path):
                continue
            
            self.status_var.set(f"Scanning Recycle Bin on {drive}...")
                
            try:
                for sid in os.listdir(recycle_path):
                    sid_path = os.path.join(recycle_path, sid)
                    if not os.path.isdir(sid_path):
                        continue
                        
                    for file in os.listdir(sid_path):
                        if self.stop_scan:
                            break
                            
                        if file.startswith('$I'):
                            i_path = os.path.join(sid_path, file)
                            r_path = os.path.join(sid_path, '$R' + file[2:])
                            
                            try:
                                metadata = self.parse_recyclebin_metadata(i_path)
                                if metadata:
                                    found_files += 1
                                    self.recycle_bin_files += 1
                                    self.total_files += 1
                                    
                                    deletion_time = metadata['deletion_time']
                                    timestamp = deletion_time.strftime("%Y-%m-%d %H:%M:%S")
                                    
                                    # Determine file type from extension
                                    file_ext = os.path.splitext(metadata['original_name'])[1].lower().replace('.', '')
                                    if not file_ext:
                                        file_ext = 'unknown'
                                    
                                    metadata_dict = {
                                        'i_path': i_path,
                                        'r_path': r_path,
                                        'metadata': {
                                            'original_name': metadata['original_name'],
                                            'original_path': metadata['original_path'],
                                            'size': metadata['size'],
                                            'deletion_time': timestamp
                                        },
                                        'timestamp': deletion_time.timestamp(),
                                        'file_type': file_ext
                                    }
                                    
                                    self.add_file_to_list(
                                        metadata['original_name'],
                                        metadata['size'],
                                        metadata['original_path'],
                                        "In Recycle Bin" if os.path.exists(r_path) else "Permanently Deleted",
                                        file_ext,
                                        timestamp,
                                        metadata_dict
                                    )
                                    
                                    self.update_stats()
                                    
                            except Exception as e:
                                print(f"Error processing {i_path}: {str(e)}")
                                
            except PermissionError:
                error_msg = f"Access denied to Recycle Bin on {drive}. Try running as administrator."
                print(error_msg)
                continue
                
        return found_files

    def parse_recyclebin_metadata(self, i_file_path):
        """Parse the $I metadata file from Recycle Bin"""
        try:
            with open(i_file_path, 'rb') as f:
                f.seek(8)
                size = struct.unpack('Q', f.read(8))[0]
                filetime = struct.unpack('Q', f.read(8))[0]
                deletion_time = self.filetime_to_datetime(filetime)
                name_length = struct.unpack('I', f.read(4))[0]
                original_path = f.read(name_length * 2).decode('utf-16')
                original_name = os.path.basename(original_path)
                
                return {
                    'original_name': original_name,
                    'original_path': original_path,
                    'size': size,
                    'deletion_time': deletion_time
                }
        except Exception as e:
            print(f"Error parsing metadata from {i_file_path}: {str(e)}")
            return None

    def filetime_to_datetime(self, filetime):
        """Convert Windows FILETIME to Python datetime"""
        EPOCH_AS_FILETIME = 116444736000000000
        return datetime.fromtimestamp((filetime - EPOCH_AS_FILETIME) // 10000000)

    def scan_physical_drives(self):
        """Scan physical drives for deleted files using file signatures"""
        # First try logical drives
        logical_drives = [d.device for d in psutil.disk_partitions() if 'fixed' in d.opts]
        
        for drive in logical_drives:
            if self.stop_scan:
                break
            try:
                self.status_var.set(f"Scanning {drive} for deleted files...")
                self.deep_scan_logical_drive(drive)
            except Exception as e:
                print(f"Error scanning {drive}: {str(e)}")
        
        # Then try physical drives if admin privileges
        if self.is_admin() and not self.stop_scan:
            physical_drives = self.get_physical_drives()
            for drive in physical_drives:
                if self.stop_scan:
                    break
                try:
                    self.status_var.set(f"Scanning physical drive {drive}...")
                    self.deep_scan_physical_drive(drive)
                except Exception as e:
                    print(f"Error scanning {drive}: {str(e)}")

    def get_physical_drives(self):
        """Get list of physical drives"""
        drives = []
        try:
            for i in range(10):
                drive_path = f"\\\\.\\PhysicalDrive{i}"
                try:
                    handle = win32api.CreateFile(
                        drive_path,
                        win32con.GENERIC_READ,
                        win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE,
                        None,
                        win32con.OPEN_EXISTING,
                        0,
                        None
                    )
                    win32api.CloseHandle(handle)
                    drives.append(drive_path)
                except:
                    continue
        except Exception as e:
            print(f"Error enumerating physical drives: {str(e)}")
        return drives

    def deep_scan_logical_drive(self, drive_path, chunk_size=64*1024*1024):
        """Perform deep scan on a logical drive"""
        try:
            # Get drive size
            total_size = psutil.disk_usage(drive_path).total
            scanned_size = 0
            
            with open(f"\\\\.\\{drive_path[:-1]}", 'rb') as drive:
                buffer = bytearray(chunk_size)
                last_update = 0
                
                while scanned_size < total_size and not self.stop_scan:
                    try:
                        # Read chunk
                        bytes_read = drive.readinto(buffer)
                        if bytes_read == 0:
                            break
                        
                        # Analyze chunk for file signatures
                        self.analyze_chunk_for_files(buffer[:bytes_read], scanned_size, drive_path)
                        
                        scanned_size += bytes_read
                        progress = (scanned_size / total_size) * 100
                        
                        if int(progress) > last_update:
                            self.progress_var.set(progress)
                            self.status_var.set(
                                f"Scanning {drive_path}: {progress:.1f}% - "
                                f"Found {self.permanent_deleted_files} deleted files"
                            )
                            last_update = int(progress)
                            self.update_stats()
                            self.root.update_idletasks()
                            
                    except Exception as chunk_error:
                        print(f"Error processing chunk at offset {scanned_size}: {str(chunk_error)}")
                        scanned_size += chunk_size
                    
        except Exception as e:
            error_msg = f"Error scanning {drive_path}: {str(e)}"
            print(error_msg)
            self.status_var.set(error_msg)

    def deep_scan_physical_drive(self, drive_path, chunk_size=64*1024*1024):
        """Perform deep scan on a physical drive"""
        try:
            handle = win32api.CreateFile(
                drive_path,
                win32con.GENERIC_READ,
                win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE,
                None,
                win32con.OPEN_EXISTING,
                0,
                None
            )
            
            try:
                drive_size = win32api.GetFileSizeEx(handle)
                buffer = bytearray(chunk_size)
                offset = 0
                last_update = 0
                
                while offset < drive_size and not self.stop_scan:
                    try:
                        bytes_read = win32api.ReadFile(handle, buffer, None)[1]
                        if bytes_read == 0:
                            break
                        
                        self.analyze_chunk_for_files(buffer[:bytes_read], offset, drive_path)
                        offset += bytes_read
                        
                        progress = (offset / drive_size) * 100
                        if int(progress) > last_update:
                            self.progress_var.set(progress)
                            self.status_var.set(
                                f"Scanning {drive_path}: {progress:.1f}% - "
                                f"Found {self.permanent_deleted_files} deleted files"
                            )
                            last_update = int(progress)
                            self.update_stats()
                            self.root.update_idletasks()
                            
                    except Exception as chunk_error:
                        print(f"Error processing chunk at offset {offset}: {str(chunk_error)}")
                        offset += chunk_size
                    
            finally:
                win32api.CloseHandle(handle)
                
        except Exception as e:
            error_msg = f"Error scanning {drive_path}: {str(e)}"
            print(error_msg)
            self.status_var.set(error_msg)

    def analyze_chunk_for_files(self, chunk, offset, drive_path):
        """Enhanced file carving with validation and better size detection"""
        found_files = 0
        
        for file_type, signatures in FileSignatures.SIGNATURES.items():
            for signature_info in signatures:
                signature = signature_info['sig']
                extension = signature_info['ext']
                min_size = signature_info['min_size']
                max_size = signature_info['max_size']
                
                sig_pos = 0
                while True:
                    sig_pos = chunk.find(signature, sig_pos)
                    if sig_pos == -1:
                        break
                    
                    # Calculate absolute position
                    abs_offset = offset + sig_pos
                    
                    # Get file size based on type with validation
                    file_size = self.calculate_file_size(chunk[sig_pos:], file_type, extension, min_size, max_size)
                    
                    if file_size and min_size <= file_size <= max_size:
                        # Only validate if the option is enabled
                        should_add = True
                        if self.validate_files_var.get():
                            should_add = self.simple_validate_file(chunk[sig_pos:sig_pos + min(file_size, 8192)], file_type)
                        
                        if should_add:
                            # Create unique file ID to avoid duplicates
                            file_id = f"{drive_path}_{abs_offset}_{file_size}"
                            
                            # Check if we already found this file
                            if not any(f['metadata'].get('file_id') == file_id for f in self.all_files):
                                self.permanent_deleted_files += 1
                                self.total_files += 1
                                found_files += 1
                                
                                current_time = datetime.now()
                                timestamp = current_time.strftime("%Y-%m-%d %H:%M:%S")
                                
                                metadata_dict = {
                                    'drive': drive_path,
                                    'offset': abs_offset,
                                    'size': file_size,
                                    'type': extension,
                                    'timestamp': current_time.timestamp(),
                                    'file_id': file_id,
                                    'signature': signature.hex(),
                                    'validated': self.validate_files_var.get()
                                }
                                
                                filename = f"recovered_{extension}_{abs_offset:08x}.{extension}"
                                
                                self.add_file_to_list(
                                    filename,
                                    file_size,
                                    f"Physical Drive - Offset: 0x{abs_offset:08x}",
                                    "Permanently Deleted",
                                    extension,
                                    timestamp,
                                    metadata_dict
                                )
                    
                    sig_pos += len(signature)

    def calculate_file_size(self, data, file_type, extension, min_size, max_size):
        """Calculate file size with basic validation"""
        try:
            if file_type == 'jpg':
                # Look for JPEG end marker
                end_pos = data.find(b'\xFF\xD9')
                if end_pos != -1:
                    return end_pos + 2
                return min(len(data), max_size)
                    
            elif file_type == 'png':
                # Parse PNG structure
                pos = 8
                while pos + 8 <= len(data):
                    chunk_length = struct.unpack('>I', data[pos:pos+4])[0]
                    chunk_type = data[pos+4:pos+8]
                    
                    if chunk_type == b'IEND':
                        return pos + chunk_length + 12
                    
                    if pos + chunk_length + 12 > len(data):
                        break
                    
                    pos += chunk_length + 12
                return min(len(data), max_size)
                    
            elif file_type == 'pdf':
                # Look for %%EOF
                eof_pos = data.find(b'%%EOF')
                if eof_pos != -1:
                    return eof_pos + 5
                return min(len(data), max_size)
                    
            elif file_type in ['zip', 'docx', 'xlsx']:
                # Look for end of central directory
                eocd_pos = data.rfind(b'PK\x05\x06')
                if eocd_pos != -1 and eocd_pos + 22 <= len(data):
                    try:
                        central_dir_size = struct.unpack('<I', data[eocd_pos+12:eocd_pos+16])[0]
                        central_dir_offset = struct.unpack('<I', data[eocd_pos+16:eocd_pos+20])[0]
                        total_size = central_dir_offset + central_dir_size + 22
                        return total_size if total_size <= len(data) else min(len(data), max_size)
                    except:
                        pass
                return min(len(data), max_size)
                        
            elif file_type in ['mp4', 'mkv']:
                # Parse container structure
                if len(data) >= 8:
                    try:
                        first_size = struct.unpack('>I', data[0:4])[0]
                        if first_size > 0 and first_size <= len(data):
                            return first_size
                    except:
                        pass
                return min(len(data), max_size)
                        
            elif file_type == 'exe':
                # Parse PE header
                if len(data) >= 64:
                    try:
                        if data[:2] == b'MZ':
                            pe_offset = struct.unpack('<I', data[0x3C:0x40])[0]
                            if pe_offset + 24 <= len(data) and data[pe_offset:pe_offset+4] == b'PE\x00\x00':
                                size_of_image = struct.unpack('<I', data[pe_offset+0x50:pe_offset+0x54])[0]
                                return size_of_image
                    except:
                        pass
                return min(len(data), max_size)
                
            elif file_type == 'mp3':
                # For MP3, use reasonable size limits
                return min(len(data), 10 * 1024 * 1024)  # Max 10MB for MP3
                
            elif file_type == 'bmp':
                # Parse BMP header
                if len(data) >= 14 and data[:2] == b'BM':
                    try:
                        file_size = struct.unpack('<I', data[2:6])[0]
                        if file_size >= 14:
                            return file_size
                    except:
                        pass
                return min(len(data), max_size)
                
            else:
                return min(len(data), max_size)
                        
        except Exception as e:
            print(f"Error determining file size for {file_type}: {str(e)}")
            return min(len(data), max_size)

    def simple_validate_file(self, data, file_type):
        """Simple file validation to reduce false positives"""
        if len(data) < 100:
            return False
            
        try:
            if file_type == 'jpg':
                # Check for valid JPEG structure
                return data.find(b'\xFF\xD8') != -1 and data.find(b'\xFF\xD9') != -1
                
            elif file_type == 'png':
                # Check PNG signature and IEND
                return data.startswith(b'\x89PNG\r\n\x1a\n') and b'IEND' in data
                
            elif file_type == 'pdf':
                # Check PDF signature
                return data.startswith(b'%PDF-') and b'%%EOF' in data
                
            elif file_type == 'mp3':
                # Check for MP3 markers or ID3
                return (data.startswith(b'ID3') or 
                       (len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0))
                
            elif file_type == 'bmp':
                # Check BMP signature
                return data.startswith(b'BM') and len(data) >= 14
                
            elif file_type == 'exe':
                # Check MZ signature
                return data.startswith(b'MZ')
                
            elif file_type in ['zip', 'docx', 'xlsx']:
                # Check ZIP signature
                return data.startswith(b'PK') and len(data) >= 4
                
            elif file_type == 'mp4':
                # Check for MP4 signature
                return b'ftyp' in data[:12]
                
        except Exception:
            return False
            
        return True

    def add_file_to_list(self, name, size, original_path, status, file_type, timestamp, metadata):
        """Add a file to the UI list"""
        # Check for duplicates using file_id if available
        file_id = metadata.get('file_id')
        if file_id and any(entry['metadata'].get('file_id') == file_id for entry in self.all_files):
            return
            
        file_entry = {
            'name': name,
            'size': f"{size:,} bytes",
            'path': original_path,
            'status': status,
            'file_type': file_type,
            'timestamp': timestamp,
            'metadata': metadata
        }
        
        self.all_files.append(file_entry)
        
        self.tree.insert('', 'end', values=(
            name,
            f"{size:,} bytes",
            original_path,
            status,
            file_type,
            timestamp
        ), tags=(str(metadata),))
        
        self.root.update_idletasks()

    def recover_selected(self):
        """Recover selected files with improved error handling"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select files to recover")
            return
            
        save_dir = filedialog.askdirectory(title="Select Recovery Location")
        if not save_dir:
            return
        
        os.makedirs(save_dir, exist_ok=True)
            
        total_selected = len(selected)
        successful = 0
        failed = 0
        
        self.progress_var.set(0)
        
        for index, item in enumerate(selected):
            values = self.tree.item(item)['values']
            metadata_str = self.tree.item(item)['tags'][0]
            
            try:
                metadata = eval(metadata_str)
            except:
                metadata = {'data': metadata_str}
            
            try:
                self.status_var.set(f"Recovering {values[0]}...")
                
                recovered_path = None
                if values[3] == "In Recycle Bin":
                    recovered_path = self.recover_from_recycle_bin(metadata, save_dir)
                else:
                    recovered_path = self.recover_from_physical(metadata, save_dir)
                
                if recovered_path and os.path.exists(recovered_path):
                    successful += 1
                    self.recovered_files += 1
                    self.update_stats()
                    self.status_var.set(f"Successfully recovered: {os.path.basename(recovered_path)}")
                    
                    # Verify the recovered file is not empty
                    file_size = os.path.getsize(recovered_path)
                    if file_size == 0:
                        os.remove(recovered_path)
                        raise ValueError("Recovered file is empty")
                        
                else:
                    raise ValueError("Recovery failed: file not found after recovery")
                
            except Exception as e:
                failed += 1
                error_msg = f"Failed to recover {values[0]}: {str(e)}"
                print(f"Recovery error details: {error_msg}")
                print(f"Metadata: {metadata}")
                messagebox.showerror("Recovery Error", error_msg)
            
            progress = ((index + 1) / total_selected) * 100
            self.progress_var.set(progress)
            self.root.update_idletasks()
        
        self.status_var.set(f"Recovery completed: {successful} successful, {failed} failed")
        if successful > 0:
            messagebox.showinfo("Recovery Complete", 
                              f"Successfully recovered {successful} file(s)\n"
                              f"Failed to recover {failed} file(s)\n"
                              f"Files saved to: {save_dir}")
            
        self.progress_var.set(0)

    def recover_from_recycle_bin(self, metadata, save_dir):
        """Recover a file from the Recycle Bin"""
        try:
            r_path = metadata.get('r_path', '').strip('\x00')
            
            if not r_path or not os.path.exists(r_path):
                raise FileNotFoundError(f"Source file not found: {r_path}")
            
            # Get original name
            original_name = None
            metadata_info = metadata.get('metadata', {})
            if isinstance(metadata_info, dict):
                original_name = metadata_info.get('original_name', '')
            elif isinstance(metadata_info, str):
                try:
                    metadata_info = eval(metadata_info)
                    original_name = metadata_info.get('original_name', '')
                except:
                    pass
            
            if not original_name:
                original_name = os.path.basename(r_path.replace('$R', ''))
            
            # Create safe filename
            safe_name = ''.join(c for c in original_name if c.isalnum() or c in (' ', '-', '_', '.'))
            if not safe_name:
                safe_name = "recovered_file"
            
            # Ensure unique filename
            base_name, extension = os.path.splitext(safe_name)
            if not extension:
                # Try to determine extension from file type in metadata
                file_type = metadata.get('file_type')
                if file_type and file_type != 'unknown':
                    extension = f".{file_type}"
            
            counter = 1
            destination = os.path.join(save_dir, safe_name)
            
            while os.path.exists(destination):
                destination = os.path.join(save_dir, f"{base_name}_{counter}{extension}")
                counter += 1
            
            # Copy file
            shutil.copy2(r_path, destination)
            
            return destination
            
        except Exception as e:
            raise Exception(f"Recycle bin recovery failed: {str(e)}")

    def recover_from_physical(self, metadata, save_dir):
        """Recover a file from physical scan with improved error handling"""
        try:
            drive_path = metadata.get('drive')
            offset = metadata.get('offset')
            size = metadata.get('size')
            file_type = metadata.get('type', 'bin')
            
            if not all([drive_path, offset is not None, size]):
                raise ValueError("Missing required metadata for recovery")
            
            # Validate parameters
            if offset < 0:
                raise ValueError(f"Invalid offset: {offset}")
            if size <= 0 or size > 500 * 1024 * 1024:  # Max 500MB
                raise ValueError(f"Invalid file size: {size}")
            
            # Create filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"recovered_{file_type}_{timestamp}"
            counter = 1
            
            while os.path.exists(os.path.join(save_dir, f"{filename}_{counter}.{file_type}")):
                counter += 1
                
            destination = os.path.join(save_dir, f"{filename}_{counter}.{file_type}")
            os.makedirs(save_dir, exist_ok=True)
            
            # Determine if it's a physical or logical drive and use appropriate method
            if drive_path.startswith('\\\\.\\PhysicalDrive'):
                return self.recover_from_physical_drive(drive_path, offset, size, destination)
            else:
                return self.recover_from_logical_drive_improved(drive_path, offset, size, destination)
                
        except Exception as e:
            if 'destination' in locals() and os.path.exists(destination):
                try:
                    os.remove(destination)
                except:
                    pass
            raise Exception(f"Physical recovery failed: {str(e)}")

    def recover_from_physical_drive(self, drive_path, offset, size, destination):
        """Recover from physical drive with improved error handling"""
        handle = None
        try:
            handle = win32api.CreateFile(
                drive_path,
                win32con.GENERIC_READ,
                win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE,
                None,
                win32con.OPEN_EXISTING,
                0,
                None
            )
            
            if handle == win32api.INVALID_HANDLE_VALUE:
                raise Exception("Failed to open physical drive")
            
            # Set file pointer
            win32api.SetFilePointer(handle, offset, 0)
            
            with open(destination, 'wb') as dst:
                bytes_remaining = size
                chunk_size = 64 * 1024  # 64KB chunks for better reliability
                
                while bytes_remaining > 0:
                    current_chunk_size = min(chunk_size, bytes_remaining)
                    try:
                        data = win32api.ReadFile(handle, current_chunk_size, None)[1]
                        if not data:
                            print(f"Warning: No data read at offset {offset}, expected {current_chunk_size} bytes")
                            break
                            
                        dst.write(data)
                        bytes_remaining -= len(data)
                        
                        progress = ((size - bytes_remaining) / size) * 100
                        self.progress_var.set(progress)
                        self.status_var.set(f"Recovering... {progress:.1f}%")
                        self.root.update_idletasks()
                        
                    except Exception as chunk_error:
                        print(f"Error reading chunk: {str(chunk_error)}")
                        # Try to continue with smaller chunk
                        if chunk_size > 1024:
                            chunk_size = chunk_size // 2
                            continue
                        else:
                            break
                        
            # Verify recovery
            if os.path.exists(destination):
                actual_size = os.path.getsize(destination)
                if actual_size == 0:
                    os.remove(destination)
                    raise ValueError("Recovered file is empty")
                elif actual_size < size:
                    print(f"Warning: Recovered file size {actual_size} is less than expected {size}")
            
            return destination
            
        except Exception as e:
            if handle and handle != win32api.INVALID_HANDLE_VALUE:
                win32api.CloseHandle(handle)
            raise e
        finally:
            if handle and handle != win32api.INVALID_HANDLE_VALUE:
                win32api.CloseHandle(handle)

    def recover_from_logical_drive_improved(self, drive_path, offset, size, destination):
        """Improved logical drive recovery with better error handling"""
        try:
            # Extract drive letter from path
            drive_letter = None
            if ':' in drive_path:
                drive_letter = drive_path[0]
                physical_path = f"\\\\.\\{drive_letter}:"
            else:
                physical_path = drive_path
            
            # Get drive size to validate offset
            try:
                drive_size = psutil.disk_usage(f"{drive_letter}:\\").total if drive_letter else 0
                if offset + size > drive_size:
                    raise ValueError(f"Offset {offset} + size {size} exceeds drive capacity {drive_size}")
            except:
                pass  # Skip size validation if we can't get drive info
            
            with open(physical_path, 'rb') as src:
                # Validate that we can seek to the offset
                try:
                    src.seek(offset)
                    current_pos = src.tell()
                    if current_pos != offset:
                        raise ValueError(f"Failed to seek to offset {offset}, got {current_pos}")
                except Exception as e:
                    raise ValueError(f"Invalid offset {offset}: {str(e)}")
                
                with open(destination, 'wb') as dst:
                    bytes_remaining = size
                    chunk_size = 64 * 1024  # 64KB chunks
                    total_written = 0
                    
                    while bytes_remaining > 0 and total_written < size:
                        current_chunk_size = min(chunk_size, bytes_remaining)
                        
                        try:
                            data = src.read(current_chunk_size)
                            if not data:
                                print(f"Warning: No data read at offset {offset + total_written}")
                                break
                            
                            dst.write(data)
                            bytes_written = len(data)
                            total_written += bytes_written
                            bytes_remaining -= bytes_written
                            
                            progress = (total_written / size) * 100
                            self.progress_var.set(progress)
                            self.status_var.set(f"Recovering... {progress:.1f}%")
                            self.root.update_idletasks()
                            
                        except Exception as read_error:
                            print(f"Read error at offset {offset + total_written}: {str(read_error)}")
                            # Try smaller chunk size
                            if chunk_size > 1024:
                                chunk_size = chunk_size // 2
                                continue
                            else:
                                break
                    
                    print(f"Recovery completed: wrote {total_written} of {size} bytes")
                    
            # Verify the recovered file
            if os.path.exists(destination):
                actual_size = os.path.getsize(destination)
                if actual_size == 0:
                    os.remove(destination)
                    raise ValueError("Recovered file is empty")
                return destination
            else:
                raise ValueError("Recovery failed: destination file not created")
                        
        except Exception as e:
            raise Exception(f"Logical drive recovery failed: {str(e)}")

def main():
    """Main function to run the application"""
    try:
        root = tk.Tk()
        app = RecoveryTool(root)
        root.mainloop()
    except Exception as e:
        messagebox.showerror("Fatal Error", f"Application failed to start: {str(e)}")
        print(f"Fatal error: {str(e)}")

if __name__ == "__main__":
    main()