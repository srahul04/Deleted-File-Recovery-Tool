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

class FileSignatures:
    """File signatures (magic numbers) for various file types"""
    SIGNATURES = {
        'jpg': [b'\xFF\xD8\xFF\xE0', b'\xFF\xD8\xFF\xE1'],
        'png': [b'\x89PNG\r\n\x1a\n'],
        'pdf': [b'%PDF-'],
        'zip': [b'PK\x03\x04'],  # Also works for docx, xlsx
        'mp4': [b'\x00\x00\x00\x20ftyp', b'\x00\x00\x00\x18ftyp'],
        'mkv': [b'\x1A\x45\xDF\xA3'],
        'exe': [b'MZ']
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
        self.all_files = []  # List to store all file entries
        
        # Check for admin privileges
        if not self.is_admin():
            messagebox.showerror("Admin Rights Required", 
                "This tool requires administrator privileges for physical recovery operations.")
            self.request_admin_privileges()
        
        self.setup_ui()
        self.file_queue = queue.Queue()
        self.scan_thread = None
        self.is_scanning = False
        
        # Initialize scanning flags
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
        
        # Search frame
        search_frame = ttk.LabelFrame(top_frame, text="Search")
        search_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Search entry and button
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.on_search_change)  # Live search as you type
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        
        ttk.Button(search_frame, text="Clear Search", command=self.clear_search).pack(side=tk.LEFT, padx=5, pady=5)
        
        # Stats frame
        stats_frame = ttk.LabelFrame(top_frame, text="Statistics")
        stats_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Statistics labels
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
        columns = ("Name", "Size", "Original Path", "Status", "Last Modified")
        self.tree = ttk.Treeview(self.root, columns=columns, show="headings")
        
        # Configure columns
        column_widths = {
            "Name": 200,
            "Size": 100,
            "Original Path": 300,
            "Status": 150,
            "Last Modified": 150
        }
        
        for col, width in column_widths.items():
            # For Last Modified column, default sort in reverse order (newest first)
            if col == "Last Modified":
                self.tree.heading(col, text=col + " ▼", command=lambda c=col: self.sort_treeview(c))
            else:
                self.tree.heading(col, text=col, command=lambda c=col: self.sort_treeview(c))
            self.tree.column(col, width=width)
        
        # Add scrollbars
        y_scrollbar = ttk.Scrollbar(self.root, orient=tk.VERTICAL, command=self.tree.yview)
        x_scrollbar = ttk.Scrollbar(self.root, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)
        
        # Pack the Treeview and scrollbars
        self.tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5)
        y_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        x_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

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
                sys.exit(1)

    def start_scan(self):
        """Initiate the scanning process"""
        if self.is_scanning:
            messagebox.showwarning("Scan in Progress", "A scan is already running.")
            return
        
        self.tree.delete(*self.tree.get_children())
        self.all_files.clear()  # Clear the stored files list
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
            # Special handling for date/time column
            if col == "Last Modified":
                try:
                    # Convert date string to datetime object for proper sorting
                    val = datetime.strptime(val, "%Y-%m-%d %H:%M:%S")
                except:
                    val = datetime.min  # Use minimum date for invalid dates
            items.append((val, item))
        
        # Sort in reverse order for dates (newest first) and normal order for other columns
        items.sort(reverse=(col == "Last Modified"))
        
        for index, (val, item) in enumerate(items):
            self.tree.move(item, '', index)
    
    def on_search_change(self, *args):
        """Handle search as user types"""
        search_term = self.search_var.get().lower()
        self.perform_search(search_term)
    
    def clear_search(self):
        """Clear the search and show all files"""
        self.search_var.set("")  # This will trigger on_search_change
    
    def perform_search(self, search_term):
        """Perform the search and update the display"""
        # Clear current display
        self.tree.delete(*self.tree.get_children())
        
        if not search_term:
            # If search is empty, show all files
            for file_entry in self.all_files:
                self.tree.insert('', 'end', values=(
                    file_entry['name'],
                    file_entry['size'],
                    file_entry['path'],
                    file_entry['status'],
                    file_entry['timestamp']
                ), tags=(file_entry['metadata'],))
        else:
            # Show only matching files
            for file_entry in self.all_files:
                if search_term in file_entry['name'].lower() or search_term in file_entry['path'].lower():
                    self.tree.insert('', 'end', values=(
                        file_entry['name'],
                        file_entry['size'],
                        file_entry['path'],
                        file_entry['status'],
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
            # Reset counters and clear tree
            self.tree.delete(*self.tree.get_children())
            self.all_files.clear()  # Clear stored files
            self.total_files = 0
            self.recycle_bin_files = 0
            self.permanent_deleted_files = 0
            self.recovered_files = 0
            self.stop_scan = False
            self.update_stats()  # Initialize stats display
            
            # Phase 1: Logical Recovery (Recycle Bin)
            self.status_var.set("Scanning Recycle Bin...")
            self.progress_var.set(0)
            self.scan_recycle_bin()
            
            if not self.stop_scan:
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
            # Sort files by deletion time after scan completes
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
                                    
                                    # Store both formatted timestamp and raw datetime for sorting
                                    deletion_time = metadata['deletion_time']
                                    timestamp = deletion_time.strftime("%Y-%m-%d %H:%M:%S")
                                    
                                    # Create comprehensive metadata dictionary with timestamp
                                    metadata_dict = {
                                        'i_path': i_path,
                                        'r_path': r_path,
                                        'metadata': {
                                            'original_name': metadata['original_name'],
                                            'original_path': metadata['original_path'],
                                            'size': metadata['size'],
                                            'deletion_time': timestamp
                                        },
                                        'timestamp': deletion_time.timestamp()  # Store raw timestamp for sorting
                                    }
                                    
                                    self.add_file_to_list(
                                        metadata['original_name'],
                                        metadata['size'],
                                        metadata['original_path'],
                                        "In Recycle Bin" if os.path.exists(r_path) else "Permanently Deleted",
                                        timestamp,
                                        metadata_dict
                                    )
                                    
                                    self.add_file_to_list(
                                        metadata['original_name'],
                                        metadata['size'],
                                        metadata['original_path'],
                                        "In Recycle Bin" if os.path.exists(r_path) else "Permanently Deleted",
                                        timestamp,
                                        metadata_dict
                                    )
                                    
                                    self.update_stats()
                                    
                            except Exception as e:
                                print(f"Error processing {i_path}: {str(e)}")
                                
            except PermissionError:
                error_msg = f"Access denied to Recycle Bin on {drive}. Try running as administrator."
                print(error_msg)
                messagebox.showwarning("Permission Error", error_msg)
                continue
                
        return found_files

    def parse_recyclebin_metadata(self, i_file_path):
        """Parse the $I metadata file from Recycle Bin"""
        try:
            with open(i_file_path, 'rb') as f:
                # Skip header (8 bytes)
                f.seek(8)
                
                # Read file size (8 bytes)
                size = struct.unpack('Q', f.read(8))[0]
                
                # Read deletion time (8 bytes, Windows FILETIME format)
                filetime = struct.unpack('Q', f.read(8))[0]
                deletion_time = self.filetime_to_datetime(filetime)
                
                # Read file name length (4 bytes)
                name_length = struct.unpack('I', f.read(4))[0]
                
                # Read original file path (Unicode string)
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
        EPOCH_AS_FILETIME = 116444736000000000  # January 1, 1970
        return datetime.fromtimestamp((filetime - EPOCH_AS_FILETIME) // 10000000)

    def scan_physical_drives(self):
        """Scan physical drives for deleted files using file signatures"""
        physical_drives = self.get_physical_drives()
        
        for drive in physical_drives:
            try:
                self.status_var.set(f"Scanning {drive}...")
                self.deep_scan_drive(drive)
            except Exception as e:
                print(f"Error scanning {drive}: {str(e)}")

    def get_physical_drives(self):
        """Get list of physical drives"""
        drives = []
        try:
            for i in range(10):  # Check first 10 potential physical drives
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

    def deep_scan_drive(self, drive_path, chunk_size=10*1024*1024):
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
                        
                        found_files = self.analyze_chunk(buffer[:bytes_read], offset, drive_path)
                        offset += bytes_read
                        
                        # Update progress every 1%
                        progress = (offset / drive_size) * 100
                        if int(progress) > last_update:
                            self.progress_var.set(progress)
                            self.status_var.set(
                                f"Scanning {drive_path}: {progress:.1f}% - "
                                f"Found {self.permanent_deleted_files} deleted files"
                            )
                            last_update = int(progress)
                            self.update_stats()  # Update statistics display
                            self.tree.yview_moveto(1)  # Auto-scroll to bottom
                            self.root.update_idletasks()
                            
                    except Exception as chunk_error:
                        print(f"Error processing chunk at offset {offset}: {str(chunk_error)}")
                        offset += chunk_size  # Skip problematic chunk
                    
            finally:
                win32api.CloseHandle(handle)
                
        except Exception as e:
            error_msg = f"Error scanning {drive_path}: {str(e)}"
            print(error_msg)
            self.status_var.set(error_msg)
            messagebox.showerror("Scan Error", error_msg)

    def analyze_chunk(self, chunk, offset, drive_path):
        """Analyze a chunk of data for file signatures"""
        found_files = 0
        
        for file_type, signatures in FileSignatures.SIGNATURES.items():
            for signature in signatures:
                sig_pos = 0
                while True:
                    sig_pos = chunk.find(signature, sig_pos)
                    if sig_pos == -1:
                        break
                    
                    if file_type == 'exe':
                        # Special handling for EXE files
                        file_size = self.get_exe_size(chunk[sig_pos:])
                    else:
                        # For other files, use enhanced file carving
                        file_size = self.get_file_size(chunk[sig_pos:], file_type)
                    
                    if file_size and file_size > len(signature) and file_size < 1024*1024*1024:  # Max 1GB
                        abs_offset = offset + sig_pos
                        self.permanent_deleted_files += 1  # Increment permanent deleted count
                        self.total_files += 1  # Increment total files count
                        found_files += 1
                        
                        # Use current time for physically recovered files
                        current_time = datetime.now()
                        timestamp = current_time.strftime("%Y-%m-%d %H:%M:%S")
                        
                        # Create unique identifier for the file
                        file_id = f"{drive_path}_{abs_offset}_{file_type}"
                        
                        # Check if this file has already been found
                        if not any(entry['name'] == f"recovered_{file_type}_{abs_offset}.{file_type}" for entry in self.all_files):
                            metadata_dict = {
                                'drive': drive_path,
                                'offset': abs_offset,
                                'size': file_size,
                                'type': file_type,
                                'timestamp': current_time.timestamp(),  # Store timestamp for sorting
                                'file_id': file_id  # Add unique identifier
                            }
                            
                            self.add_file_to_list(
                                f"recovered_{file_type}_{abs_offset}.{file_type}",
                                file_size,
                                drive_path,
                                "Permanently Deleted",
                                timestamp,
                                metadata_dict
                            )
                    
                    sig_pos += len(signature)

    def get_exe_size(self, data):
        """Get the size of an EXE file by parsing its PE header"""
        try:
            if len(data) < 64:
                return None
                
            # Check for MZ signature
            if data[:2] != b'MZ':
                return None
                
            # Get PE header offset
            pe_offset = struct.unpack('<I', data[0x3C:0x40])[0]
            if pe_offset + 24 > len(data):
                return None
                
            # Verify PE signature
            if data[pe_offset:pe_offset+4] != b'PE\x00\x00':
                return None
                
            # Get SizeOfImage from Optional Header
            size_of_image = struct.unpack('<I', data[pe_offset+0x50:pe_offset+0x54])[0]
            return size_of_image
            
        except Exception:
            return None

    def get_file_size(self, data, file_type):
        """Determine file size based on file format"""
        try:
            if file_type == 'jpg':
                # Look for JPEG end marker (FF D9)
                end_pos = data.find(b'\xFF\xD9')
                if end_pos != -1:
                    return end_pos + 2
                    
            elif file_type == 'png':
                # Parse PNG chunks until IEND
                pos = 8  # Skip signature
                while pos < len(data):
                    if pos + 8 > len(data):
                        break
                    chunk_size = struct.unpack('>I', data[pos:pos+4])[0]
                    chunk_type = data[pos+4:pos+8]
                    if chunk_type == b'IEND':
                        return pos + chunk_size + 12
                    pos += chunk_size + 12
                    
            elif file_type == 'pdf':
                # Look for %%EOF marker
                end_pos = data.find(b'%%EOF')
                if end_pos != -1:
                    return end_pos + 5
                    
            elif file_type in ['zip', 'docx', 'xlsx']:
                # Look for end of central directory
                for i in range(len(data)-22, 0, -1):
                    if data[i:i+4] == b'PK\x05\x06':
                        return struct.unpack('<I', data[i+16:i+20])[0] + i + 22
                        
            elif file_type in ['mp4', 'mkv']:
                # For container formats, check first atom/cluster size
                if len(data) >= 8:
                    size = struct.unpack('>I', data[0:4])[0]
                    if size > 0:
                        return size
                        
        except Exception as e:
            print(f"Error determining file size for {file_type}: {str(e)}")
            
        # Default to a reasonable chunk size if format-specific detection fails
        return min(len(data), 10*1024*1024)  # Max 10MB for unknown formats

    def add_file_to_list(self, name, size, original_path, status, timestamp, metadata):
        """Add a file to the UI list"""
        # Convert metadata to dict if it's not already
        if isinstance(metadata, dict):
            metadata_dict = metadata
        else:
            metadata_dict = {'data': metadata}
            
        # Check if file already exists in the list (using name as unique identifier)
        existing_entries = [entry for entry in self.all_files if entry['name'] == name]
        if existing_entries:
            # Skip if already exists
            return
            
        # Create file entry
        file_entry = {
            'name': name,
            'size': f"{size:,} bytes",
            'path': original_path,
            'status': status,
            'timestamp': timestamp,
            'metadata': str(metadata_dict)
        }
        
        # Add to all files list
        self.all_files.append(file_entry)
        
        # Add to treeview
        self.tree.insert('', 'end', values=(
            name,
            f"{size:,} bytes",
            original_path,
            status,
            timestamp
        ), tags=(str(metadata_dict),))
        
        # Update UI immediately
        self.root.update_idletasks()

    def recover_selected(self):
        """Recover selected files and folders"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select files or folders to recover")
            return
            
        save_dir = filedialog.askdirectory(title="Select Recovery Location")
        if not save_dir:
            return
        
        # Ensure the recovery directory exists
        os.makedirs(save_dir, exist_ok=True)
            
        total_selected = len(selected)
        successful = 0
        failed = 0
        
        self.progress_var.set(0)
        
        for index, item in enumerate(selected):
            values = self.tree.item(item)['values']
            metadata_str = self.tree.item(item)['tags'][0]
            # Convert string representation of dict back to dict
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
                else:
                    raise ValueError("Recovery failed: file not found after recovery")
                
            except Exception as e:
                failed += 1
                error_msg = f"Failed to recover {values[0]}: {str(e)}"
                print(error_msg)
                messagebox.showerror("Recovery Error", error_msg)
            
            # Update progress
            progress = ((index + 1) / total_selected) * 100
            self.progress_var.set(progress)
            self.root.update_idletasks()
        
        # Show summary
        self.status_var.set(f"Recovery completed: {successful} successful, {failed} failed")
        if successful > 0:
            messagebox.showinfo("Recovery Complete", 
                              f"Successfully recovered {successful} file(s)\n"
                              f"Failed to recover {failed} file(s)\n"
                              f"Files saved to: {save_dir}")
            
        # Reset progress bar
        self.progress_var.set(0)

    def recover_from_recycle_bin(self, metadata, save_dir):
        """Recover a file or folder from the Recycle Bin"""
        try:
            # Check for admin privileges and take ownership first
            if not self.is_admin():
                messagebox.showerror("Permission Error", 
                    "Administrator privileges are required to recover files from the Recycle Bin")
                self.request_admin_privileges()
                return None
            
            # Take ownership and set permissions using Windows commands
            try:
                import subprocess
                r_path = metadata.get('r_path', '').strip('\x00')
                
                # Take ownership
                subprocess.run(f'takeown /F "{r_path}" /R /D Y', 
                             shell=True, capture_output=True, check=True)
                
                # Grant permissions
                subprocess.run(f'icacls "{r_path}" /grant "%USERNAME%":F /T', 
                             shell=True, capture_output=True, check=True)
                
            except Exception as e:
                print(f"Permission adjustment failed: {str(e)}")
            
            # Debug print to inspect metadata
            print("Debug - Metadata received:", metadata)
            
            # Clean up metadata paths
            if isinstance(metadata.get('r_path'), str):
                metadata['r_path'] = metadata['r_path'].strip('\x00')
            if isinstance(metadata.get('metadata', {}).get('original_path'), str):
                metadata['metadata']['original_path'] = metadata['metadata']['original_path'].strip('\x00')
            if isinstance(metadata.get('metadata', {}).get('original_name'), str):
                metadata['metadata']['original_name'] = metadata['metadata']['original_name'].strip('\x00')
            
            # Handle directory recovery
            if metadata.get('is_directory', False) or (
                metadata.get('metadata', {}).get('original_path', '').endswith('\\')):
                return self.recover_directory_from_recycle_bin(metadata, save_dir)
            
            # Ensure metadata is a dictionary
            if not isinstance(metadata, dict):
                try:
                    if isinstance(metadata, str):
                        metadata = eval(metadata)
                    else:
                        raise ValueError("Metadata must be a dictionary or string representation of a dictionary")
                except:
                    raise ValueError("Failed to parse metadata")

            # Extract required paths
            r_path = metadata.get('r_path')
            metadata_info = metadata.get('metadata', {})
            
            # Ensure metadata_info is a dictionary
            if not isinstance(metadata_info, dict):
                try:
                    if isinstance(metadata_info, str):
                        metadata_info = eval(metadata_info)
                    else:
                        raise ValueError("Invalid metadata_info format")
                except:
                    raise ValueError("Failed to parse metadata_info")

            # Get original name with fallbacks
            original_name = metadata_info.get('original_name')
            if not original_name and isinstance(r_path, str):
                # Fallback to extracting name from r_path
                original_name = os.path.basename(r_path.replace('$R', ''))
            
            if not r_path or not original_name:
                print("Debug - r_path:", r_path)
                print("Debug - original_name:", original_name)
                print("Debug - metadata_info:", metadata_info)
                raise ValueError("Missing required metadata for recovery")
            
            if not os.path.exists(r_path):
                raise FileNotFoundError(f"Source file not found: {r_path}")
            
            # Create a safe filename from the original name
            safe_name = ''.join(c for c in original_name if c.isalnum() or c in (' ', '-', '_', '.'))
            if not safe_name:
                safe_name = "recovered_file"
            
            # Ensure unique filename
            base_name = os.path.splitext(safe_name)[0]
            extension = os.path.splitext(safe_name)[1]
            counter = 1
            destination = os.path.join(save_dir, safe_name)
            
            while os.path.exists(destination):
                destination = os.path.join(save_dir, f"{base_name}_{counter}{extension}")
                counter += 1
            
            # Create destination directory if it doesn't exist
            os.makedirs(save_dir, exist_ok=True)
            
            # Copy file in chunks with progress update
            file_size = os.path.getsize(r_path)
            copied_size = 0
            
            with open(r_path, 'rb') as src, open(destination, 'wb') as dst:
                while True:
                    chunk = src.read(1024*1024)  # 1MB chunks
                    if not chunk:
                        break
                    dst.write(chunk)
                    copied_size += len(chunk)
                    progress = (copied_size / file_size) * 100
                    self.progress_var.set(progress)
                    self.root.update_idletasks()
            
            # Verify the recovered file
            if os.path.getsize(destination) == 0:
                os.remove(destination)
                raise ValueError("Recovery failed: recovered file is empty")
            
            return destination
            
        except Exception as e:
            if 'destination' in locals() and os.path.exists(destination):
                try:
                    os.remove(destination)
                except:
                    pass
            raise Exception(f"Recovery failed: {str(e)}")

    def recover_directory_from_recycle_bin(self, metadata, save_dir):
        """Recover a directory and its contents from the Recycle Bin"""
        try:
            # Check for admin privileges first
            if not self.is_admin():
                messagebox.showerror("Permission Error", 
                    "Administrator privileges are required to recover files from the Recycle Bin")
                self.request_admin_privileges()
                return None
                
            # Extract required paths
            r_path = metadata.get('r_path')
            metadata_info = metadata.get('metadata', {})
            
            # Check administrator privileges
            if not self.is_admin():
                messagebox.showerror("Permission Error", 
                    "Administrator privileges are required to recover files from the Recycle Bin")
                self.request_admin_privileges()
                return None
            
            # Clean up path and verify it exists
            if isinstance(r_path, str):
                r_path = r_path.strip('\x00')
            
            if not r_path or not os.path.exists(r_path):
                raise ValueError("Invalid directory path or directory not found")
            
            # Get original name
            original_name = metadata_info.get('original_name')
            if not original_name:
                original_name = os.path.basename(metadata_info.get('original_path', ''))
            if not original_name:
                original_name = "recovered_folder"
            
            # Create a safe directory name
            safe_name = ''.join(c for c in original_name if c.isalnum() or c in (' ', '-', '_'))
            if not safe_name:
                safe_name = "recovered_folder"
            
            # Ensure unique directory name
            counter = 1
            destination = os.path.join(save_dir, safe_name)
            while os.path.exists(destination):
                destination = os.path.join(save_dir, f"{safe_name}_{counter}")
                counter += 1
            
            # Create destination directory
            os.makedirs(destination, exist_ok=True)
            
            try:
                # Try using win32api for the copy operation first
                import win32file
                import win32con
                import shutil
                
                # Set backup privilege for the current process
                priv_flags = win32security.TOKEN_ADJUST_PRIVILEGES | win32security.TOKEN_QUERY
                h_token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), priv_flags)
                priv_id = win32security.LookupPrivilegeValue(None, "SeBackupPrivilege")
                win32security.AdjustTokenPrivileges(h_token, 0, [(priv_id, win32security.SE_PRIVILEGE_ENABLED)])
                
                # Try robocopy first (better for folders)
                try:
                    import subprocess
                    robocopy_cmd = f'robocopy "{r_path}" "{destination}" /E /ZB /R:1 /W:1'
                    result = subprocess.run(robocopy_cmd, shell=True, capture_output=True, text=True)
                    if result.returncode <= 8:  # Robocopy success codes are 0-8
                        return destination
                except Exception as robocopy_error:
                    print(f"Robocopy failed, trying shutil: {str(robocopy_error)}")
                
                # Try shutil as backup
                shutil.copytree(r_path, destination, dirs_exist_ok=True)
                return destination
                
            except Exception as shell_error:
                print(f"Automated copy methods failed, falling back to manual copy: {str(shell_error)}")
                
                # Manual copy as final fallback
                total_items = sum([len(files) + len(dirs) for _, dirs, files in os.walk(r_path)])
                copied_items = 0
                
                for root, dirs, files in os.walk(r_path):
                    # Create relative path
                    rel_path = os.path.relpath(root, r_path)
                    if rel_path == '.':
                        rel_path = ''                # Create directories
                for dir_name in dirs:
                    src_dir = os.path.join(root, dir_name)
                    dst_dir = os.path.join(destination, rel_path, dir_name)
                    os.makedirs(dst_dir, exist_ok=True)
                    copied_items += 1
                    self.progress_var.set((copied_items / total_items) * 100)
                    self.root.update_idletasks()
                
                # Copy files
                for file_name in files:
                    src_file = os.path.join(root, file_name)
                    dst_file = os.path.join(destination, rel_path, file_name)
                    
                    # Copy file in chunks
                    with open(src_file, 'rb') as src, open(dst_file, 'wb') as dst:
                        while True:
                            chunk = src.read(1024*1024)  # 1MB chunks
                            if not chunk:
                                break
                            dst.write(chunk)
                    
                    copied_items += 1
                    self.progress_var.set((copied_items / total_items) * 100)
                    self.root.update_idletasks()
            
            return destination
            
        except Exception as e:
            if 'destination' in locals() and os.path.exists(destination):
                try:
                    import shutil
                    shutil.rmtree(destination)
                except:
                    pass
            raise Exception(f"Directory recovery failed: {str(e)}")

    def recover_from_physical(self, metadata, save_dir):
        """Recover a file from physical scan"""
        try:
            drive_path = metadata.get('drive')
            offset = metadata.get('offset')
            size = metadata.get('size')
            file_type = metadata.get('type', 'unknown')
            
            if not all([drive_path, offset is not None, size]):
                raise ValueError("Missing required metadata for recovery")
            
            # Create a safe filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"recovered_{file_type}_{timestamp}"
            counter = 1
            
            while os.path.exists(os.path.join(save_dir, f"{filename}_{counter}.{file_type}")):
                counter += 1
                
            destination = os.path.join(save_dir, f"{filename}_{counter}.{file_type}")
            
            # Create destination directory if it doesn't exist
            os.makedirs(save_dir, exist_ok=True)
            
            # Open the physical drive
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
                # Seek to the file offset
                win32api.SetFilePointer(handle, offset, 0)
                
                with open(destination, 'wb') as dst:
                    bytes_remaining = size
                    bytes_written = 0
                    
                    while bytes_remaining > 0:
                        chunk_size = min(1024*1024, bytes_remaining)  # 1MB chunks
                        try:
                            data = win32api.ReadFile(handle, chunk_size, None)[1]
                            if not data:
                                break
                                
                            dst.write(data)
                            bytes_written += len(data)
                            bytes_remaining -= len(data)
                            
                            # Update progress
                            progress = (bytes_written / size) * 100
                            self.progress_var.set(progress)
                            self.status_var.set(f"Recovering file: {progress:.1f}%")
                            self.root.update_idletasks()
                            
                        except Exception as chunk_error:
                            print(f"Error reading chunk: {str(chunk_error)}")
                            break
                
                # Verify the recovered file
                if os.path.getsize(destination) == 0:
                    os.remove(destination)
                    raise ValueError("Recovery failed: recovered file is empty")
                
                if os.path.getsize(destination) < len(FileSignatures.SIGNATURES[file_type][0]):
                    os.remove(destination)
                    raise ValueError("Recovery failed: file too small to be valid")
                
                return destination
                
            finally:
                win32api.CloseHandle(handle)
                
        except Exception as e:
            if 'destination' in locals() and os.path.exists(destination):
                try:
                    os.remove(destination)
                except:
                    pass
            raise Exception(f"Recovery failed: {str(e)}")

def main():
    root = tk.Tk()
    app = RecoveryTool(root)
    root.mainloop()

if __name__ == "__main__":
    main()
