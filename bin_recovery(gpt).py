import os
import struct
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, simpledialog
from datetime import datetime
import psutil  

def find_recycle_bins():
    """
    Finds all $Recycle.Bin folders on all drives.
    """
    drives = []
    for drive_letter in range(ord('C'), ord('Z')+1):
        drive = chr(drive_letter) + ':\\'
        if os.path.exists(drive):
            recycle_bin_path = os.path.join(drive, '$Recycle.Bin')
            if os.path.exists(recycle_bin_path):
                drives.append(recycle_bin_path)
    return drives

def get_physical_drives():
    
    physical_drives = []
    # Try to get actual physical drives using psutil
    try:
        for partition in psutil.disk_partitions(all=True):
            if partition.device:
                physical_drives.append(partition.device)
    except:
        pass
    
    # If psutil fails or doesn't find drives, use common physical drive paths
    if not physical_drives:
        physical_drives = [f"\\\\.\\PhysicalDrive{i}" for i in range(0, 4)]
    
    return physical_drives

def parse_i_file(i_file_path):
    """
    Parses the binary $I file to get metadata.
    Returns a dictionary with original path, name, size, and deletion time.
    """
    try:
        with open(i_file_path, 'rb') as f:
            header = f.read(8)
            file_size = struct.unpack('<Q', f.read(8))[0]
            deletion_time = struct.unpack('<Q', f.read(8))[0]
            raw_path = f.read()
            original_path = raw_path.decode('utf-16le').strip('\x00')
            original_name = os.path.basename(original_path)

            return {
                'original_path': original_path,
                'original_name': original_name,
                'size': file_size,
                'deletion_time': deletion_time,
                'r_file_path': i_file_path.replace('$I', '$R')
            }
    except Exception as e:
        print(f"Error parsing {i_file_path}: {e}")
        return None

def scan_recycle_bin():
    """
    Scans all Recycle Bin folders for $I files and parses them.
    Returns a list of file metadata dictionaries.
    """
    found_files = []
    recycle_bin_paths = find_recycle_bins()

    for bin_path in recycle_bin_paths:
        for root, dirs, files in os.walk(bin_path):
            for file in files:
                if file.startswith('$I'):
                    i_file_path = os.path.join(root, file)
                    file_info = parse_i_file(i_file_path)
                    if file_info:
                        found_files.append(file_info)
    return found_files

def recover_file(r_file_path, original_name, output_dir):
    """
    Tries to recover using the logical method first. If the $R file is missing (permanently deleted),
    it attempts a physical recovery via file carving.
    """
    if os.path.exists(r_file_path):
        try:
            os.makedirs(output_dir, exist_ok=True)
            destination_path = os.path.join(output_dir, original_name)
            counter = 1
            name, ext = os.path.splitext(original_name)
            while os.path.exists(destination_path):
                new_name = f"{name}_recovered_{counter}{ext}"
                destination_path = os.path.join(output_dir, new_name)
                counter += 1

            with open(r_file_path, 'rb') as source, open(destination_path, 'wb') as dest:
                dest.write(source.read())
            messagebox.showinfo("Success (Logical)", f"File '{original_name}' recovered successfully from Recycle Bin!")
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Logical recovery failed for {original_name}: {e}")
            return False
    else:
        answer = messagebox.askyesno("File Not Found",
                                    f"The data for '{original_name}' is not in the Recycle Bin.\n\n"
                                    "It may have been permanently deleted. How would you like to proceed?",
                                    detail="'Yes': Deep Scan this Drive\n'No': Raw Scan Entire Disk (for deleted partitions)")
        if answer:
            # Original Deep Scan on logical drive
            original_drive = os.path.splitdrive(r_file_path)[0]
            success = carve_file_by_signature(original_drive, original_name, output_dir)
            return success
        else:
            # NEW FEATURE: Raw Scan on Physical Drive for deleted partitions
            success = raw_scan_deleted_partitions(original_name, output_dir)
            return success

def carve_file_by_signature(drive, original_name, output_dir):
    """
    Enhanced file carving function with improved recovery capabilities for permanently deleted files.
    Supports multiple file signatures and advanced PE file handling for executables.
    """
    try:
        # Enhanced signature map with more detailed signatures and end markers
        signature_map = {
            '.jpg': {'start': [b'\xFF\xD8\xFF\xE0', b'\xFF\xD8\xFF\xE1'], 'end': [b'\xFF\xD9'], 'max_size': 100 * 1024 * 1024},
            '.jpeg': {'start': [b'\xFF\xD8\xFF\xE0', b'\xFF\xD8\xFF\xE1'], 'end': [b'\xFF\xD9'], 'max_size': 100 * 1024 * 1024},
            '.png': {'start': [b'\x89PNG\r\n\x1a\n'], 'end': [b'IEND\xaeB`\x82'], 'max_size': 50 * 1024 * 1024},
            '.pdf': {'start': [b'%PDF-'], 'end': [b'%%EOF'], 'max_size': 200 * 1024 * 1024},
            '.docx': {'start': [b'PK\x03\x04'], 'end': [b'PK\x05\x06'], 'max_size': 200 * 1024 * 1024},
            '.xlsx': {'start': [b'PK\x03\x04'], 'end': [b'PK\x05\x06'], 'max_size': 200 * 1024 * 1024},
            '.pptx': {'start': [b'PK\x03\x04'], 'end': [b'PK\x05\x06'], 'max_size': 200 * 1024 * 1024},
            '.zip': {'start': [b'PK\x03\x04'], 'end': [b'PK\x05\x06'], 'max_size': 500 * 1024 * 1024},
            '.mp4': {'start': [b'\x00\x00\x00\x20ftyp', b'\x00\x00\x00\x18ftyp'], 'end': None, 'max_size': 2 * 1024 * 1024 * 1024},
            '.avi': {'start': [b'RIFF'], 'end': None, 'max_size': 2 * 1024 * 1024 * 1024},
            '.mkv': {'start': [b'\x1A\x45\xDF\xA3'], 'end': None, 'max_size': 2 * 1024 * 1024 * 1024},
            '.exe': {'start': [b'MZ'], 'end': None, 'max_size': 2 * 1024 * 1024 * 1024},
        }

        file_extension = os.path.splitext(original_name)[1].lower()
        file_info = signature_map.get(file_extension)

        if not file_info:
            messagebox.showwarning("Cannot Carve", f"Deep scan is not supported for '{file_extension}' files yet.")
            return False

        # Use larger chunk size for faster scanning
        chunk_size = 1024 * 1024  # 1MB chunks for faster scanning
        found = False
        messagebox.showinfo("Deep Scan Started", 
                          f"Now deeply scanning drive {drive} for '{original_name}'.\n"
                          "This process might take several minutes...")

        with open(f'\\\\.\\{drive}', 'rb') as disk:
            chunk_number = 0
            while True:
                chunk = disk.read(chunk_size)
                if not chunk:
                    break

                # Check for file signatures
                for sig in file_info['start']:
                    offset = chunk.find(sig)
                    if offset != -1:
                        absolute_position = (chunk_number * chunk_size) + offset
                        print(f"Found potential {file_extension} file at position: {absolute_position}")

                        base_name = os.path.splitext(original_name)[0]
                        # Create unique filename for multiple potential matches
                        counter = 1
                        while os.path.exists(os.path.join(output_dir, f"RECOVERED_{counter}_{original_name}")):
                            counter += 1
                        destination_path = os.path.join(output_dir, f"RECOVERED_{counter}_{original_name}")
                        
                        try:
                            disk.seek(absolute_position)
                            file_size_to_read = 0
                            
                            # Special handling for EXE files
                            if file_extension == '.exe':
                                header_data = disk.read(4096)  # Read larger header for better analysis
                                try:
                                    # Parse PE header more thoroughly
                                    if len(header_data) >= 64:
                                        pe_offset = struct.unpack('<I', header_data[60:64])[0]
                                        if len(header_data) >= pe_offset + 24:
                                            # Verify PE signature
                                            if header_data[pe_offset:pe_offset+4] == b'PE\x00\x00':
                                                # Try to get size from multiple PE header fields
                                                if len(header_data) >= pe_offset + 84:
                                                    size_of_image = struct.unpack('<I', header_data[pe_offset+80:pe_offset+84])[0]
                                                    if 0 < size_of_image <= file_info['max_size']:
                                                        file_size_to_read = size_of_image
                                                        print(f"Valid PE header found. Size: {size_of_image:,} bytes")
                                except:
                                    pass
                                
                                # Fallback if PE parsing fails
                                if file_size_to_read == 0:
                                    file_size_to_read = 500 * 1024 * 1024  # Increased default size for executables
                            
                            # For other files, try to find end marker or use max size
                            else:
                                # If we have an end marker for this file type, try to find it
                                end_marker = file_info.get('end')
                                if end_marker:
                                    # Read in larger chunks to search for end marker
                                    search_buffer = bytearray()
                                    max_search = min(50 * 1024 * 1024, file_info['max_size'])  # 50MB search buffer
                                    
                                    while len(search_buffer) < max_search:
                                        data = disk.read(1024 * 1024)  # 1MB chunks
                                        if not data:
                                            break
                                        search_buffer.extend(data)
                                        
                                        # Try each potential end marker
                                        for end_sig in end_marker:
                                            end_pos = search_buffer.find(end_sig)
                                            if end_pos != -1:
                                                file_size_to_read = end_pos + len(end_sig)
                                                break
                                        if file_size_to_read:
                                            break
                                
                                # If no end marker found, use default size
                                if not file_size_to_read:
                                    file_size_to_read = file_info['max_size']

                            # Improved streaming recovery with validation
                            disk.seek(absolute_position)
                            bytes_recovered = 0
                            valid_file = True
                            
                            with open(destination_path, 'wb') as carved_file:
                                while bytes_recovered < file_size_to_read:
                                    bytes_to_read = min(4 * 1024 * 1024, file_size_to_read - bytes_recovered)  # 4MB chunks
                                    data_chunk = disk.read(bytes_to_read)
                                    if not data_chunk:
                                        break
                                        
                                    carved_file.write(data_chunk)
                                    bytes_recovered += len(data_chunk)
                                    
                                    # Show progress for large files
                                    if bytes_recovered > 10 * 1024 * 1024:  # 10MB
                                        print(f"Recovering: {bytes_recovered/(1024*1024):.1f}MB / {file_size_to_read/(1024*1024):.1f}MB")

                            print(f"Finished carving. Total bytes recovered: {bytes_recovered:,} bytes")
                            
                            # Validate recovered file
                            if bytes_recovered > 0:
                                valid_file = True
                                
                                # For EXE files, verify PE header
                                if file_extension == '.exe':
                                    try:
                                        with open(destination_path, 'rb') as f:
                                            header = f.read(2)
                                            if header != b'MZ':
                                                valid_file = False
                                    except:
                                        valid_file = False
                                
                                # For other files, check minimum size and signature
                                elif bytes_recovered < len(file_info['start'][0]):
                                    valid_file = False
                                
                                if valid_file:
                                    messagebox.showinfo("Success (Carved!)", 
                                                      f"Recovered file via deep scan!\n"
                                                      f"Saved as: {destination_path}\n"
                                                      f"Size: {bytes_recovered:,} bytes")
                                    found = True
                                    return True
                                else:
                                    print("Recovered file failed validation checks")
                            
                            # Clean up invalid files
                            if not valid_file and os.path.exists(destination_path):
                                try:
                                    os.remove(destination_path)
                                except:
                                    pass
                                
                        except Exception as carve_error:
                            print(f"Carving failed at {absolute_position}: {carve_error}")
                            if os.path.exists(destination_path):
                                try:
                                    os.remove(destination_path)
                                except:
                                    pass
                            continue

                chunk_number += 1

        if not found:
            messagebox.showinfo("Deep Scan Complete", "The deep scan could not find the file. It has likely been overwritten.")
        return found

    except PermissionError:
        messagebox.showerror("Admin Rights Required", "Deep scanning requires running the program as Administrator.")
        return False
    except Exception as e:
        messagebox.showerror("Deep Scan Error", f"An error occurred during the deep scan: {e}")
        return False

def raw_scan_deleted_partitions(original_name, output_dir):
    """
    NEW FEATURE: Scans physical drives for files, useful for recovering data from deleted partitions.
    """
    try:
        # Get list of physical drives
        physical_drives = get_physical_drives()
        if not physical_drives:
            messagebox.showerror("Error", "Could not find any physical drives to scan.")
            return False

        # Let the user choose which physical drive to scan
        drive_list = "\n".join([f"{i}. {drive}" for i, drive in enumerate(physical_drives)])
        choice = simpledialog.askstring("Raw Scan", 
                                       "Enter the number of physical drive to scan:\n" + drive_list)
        if not choice:
            return False

        try:
            drive_index = int(choice)
            if 0 <= drive_index < len(physical_drives):
                selected_drive = physical_drives[drive_index]
                # Use the same carving function but on the physical drive
                return carve_file_by_signature(selected_drive, original_name, output_dir)
            else:
                messagebox.showerror("Error", "Invalid drive selection.")
                return False
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid number.")
            return False

    except Exception as e:
        messagebox.showerror("Raw Scan Error", f"An error occurred during the raw scan: {e}")
        return False

# GUI Code
class RecoveryApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Advanced Data Recovery Tool")
        self.root.geometry("1000x700")
        
        # Initialize counters
        self.total_files = 0
        self.recycle_bin_files = 0
        self.permanent_deleted_files = 0
        self.recovered_files = 0
        self.found_files = []
        
        # Initialize scanning flags
        self.stop_scan = False
        self.is_scanning = False
        self.current_scan_progress = 0
        
        self.setup_ui()

    def setup_ui(self):
        """Initialize the user interface"""
        # Top frame for controls and stats
        top_frame = ttk.Frame(self.root)
        top_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Control frame
        control_frame = ttk.LabelFrame(top_frame, text="Controls")
        control_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        ttk.Button(control_frame, text="Start Scan", command=self.scan).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(control_frame, text="Stop Scan", command=self.stop_scanning).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(control_frame, text="Recover Selected", command=self.recover_selected).pack(side=tk.LEFT, padx=5, pady=5)
        
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
        
    def stop_scanning(self):
        """Stop the scanning process"""
        if self.is_scanning:
            self.stop_scan = True
            self.status_var.set("Stopping scan...")
    
    def sort_treeview(self, col):
        """Sort treeview by column"""
        items = [(self.tree.set(item, col), item) for item in self.tree.get_children('')]
        items.sort()
        for index, (val, item) in enumerate(items):
            self.tree.move(item, '', index)
    
    def update_stats(self):
        """Update statistics display"""
        self.stats_var['total'].set(f"Total Files: {self.total_files}")
        self.stats_var['recycle'].set(f"In Recycle Bin: {self.recycle_bin_files}")
        self.stats_var['permanent'].set(f"Permanently Deleted: {self.permanent_deleted_files}")
        self.stats_var['recovered'].set(f"Recovered: {self.recovered_files}")
        self.root.update_idletasks()

    def scan(self):
        """Initiate the scanning process"""
        if self.is_scanning:
            messagebox.showwarning("Scan in Progress", "A scan is already running.")
            return
        
        # Reset counters and flags
        self.total_files = 0
        self.recycle_bin_files = 0
        self.permanent_deleted_files = 0
        self.recovered_files = 0
        self.stop_scan = False
        
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.found_files = []
        
        self.is_scanning = True
        self.status_var.set("Scanning Recycle Bin...")
        self.progress_var.set(0)
        self.root.update()

        try:
            # Scan Recycle Bin
            self.found_files = scan_recycle_bin()
            self.recycle_bin_files = len(self.found_files)
            self.total_files = self.recycle_bin_files

            # Add files to treeview
            for file_info in self.found_files:
                size_str = f"{file_info['size']:,} bytes"
                # Convert Windows FILETIME to readable format
                deleted_time = datetime.fromtimestamp(file_info['deletion_time'] / 10000000 - 11644473600)
                time_str = deleted_time.strftime("%Y-%m-%d %H:%M:%S")
                
                status = "In Recycle Bin" if os.path.exists(file_info['r_file_path']) else "Permanently Deleted"
                if status == "Permanently Deleted":
                    self.permanent_deleted_files += 1
                    self.recycle_bin_files -= 1
                
                self.tree.insert('', 'end', values=(
                    file_info['original_name'],
                    size_str,
                    file_info['original_path'],
                    status,
                    time_str
                ), tags=(file_info,))

            # Update statistics
            self.update_stats()
            
            if not self.stop_scan:
                self.status_var.set(f"Scan complete. Found {self.total_files} files "
                                  f"({self.recycle_bin_files} in Recycle Bin, "
                                  f"{self.permanent_deleted_files} permanently deleted)")
            else:
                self.status_var.set("Scan stopped by user")
                
        except Exception as e:
            self.status_var.set(f"Error during scan: {str(e)}")
            messagebox.showerror("Error", f"An error occurred during scanning: {str(e)}")
            
        finally:
            self.is_scanning = False
            self.progress_var.set(100)

    def recover_selected(self):
        """Recover selected files"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select files to recover")
            return
            
        save_dir = filedialog.askdirectory(title="Select Recovery Location")
        if not save_dir:
            return
            
        total_selected = len(selected)
        successful = 0
        failed = 0
        
        self.progress_var.set(0)
        
        for index, item in enumerate(selected):
            values = self.tree.item(item)['values']
            try:
                file_index = self.tree.index(item)
                if not hasattr(self, 'found_files') or not self.found_files or file_index >= len(self.found_files):
                    raise ValueError("File information not found in recovery data")
                    
                file_info = self.found_files[file_index]
                if not isinstance(file_info, dict):
                    raise ValueError("Invalid file information format")
                file_name = values[0]
                
                self.status_var.set(f"Recovering {file_name}...")
                self.root.update_idletasks()
                
                # Create safe filename
                safe_name = ''.join(c for c in file_name if c.isalnum() or c in (' ', '-', '_', '.'))
                if not safe_name:
                    safe_name = "recovered_file"
                
                # Ensure unique filename
                base_name = os.path.splitext(safe_name)[0]
                extension = os.path.splitext(safe_name)[1]
                destination = os.path.join(save_dir, safe_name)
                counter = 1
                
                while os.path.exists(destination):
                    destination = os.path.join(save_dir, f"{base_name}_{counter}{extension}")
                    counter += 1
                
                # Ensure directory exists
                os.makedirs(save_dir, exist_ok=True)
                
                # Check file status and get recovery path
                if values[3] == "Permanently Deleted":
                    # Handle permanently deleted files
                    drive = os.path.splitdrive(file_info.get('original_path', ''))[0]
                    if drive and carve_file_by_signature(drive, values[0], save_dir):
                        successful += 1
                        self.recovered_files += 1
                        continue
                    else:
                        raise ValueError("Physical recovery failed - file may be overwritten")
                
                # Handle files still in Recycle Bin
                r_file_path = file_info.get('r_file_path')
                if not r_file_path:
                    raise ValueError("Missing required recovery path")
                
                if not os.path.exists(r_file_path):
                    raise FileNotFoundError(f"Source file not found: {r_file_path}")
                
                # Verify file size before recovery
                file_size = os.path.getsize(r_file_path)
                if file_size == 0:
                    raise ValueError("Source file is empty")
                copied_size = 0
                
                # Copy file with progress tracking
                with open(r_file_path, 'rb') as src, open(destination, 'wb') as dst:
                    while True:
                        chunk = src.read(1024*1024)  # 1MB chunks
                        if not chunk:
                            break
                        dst.write(chunk)
                        copied_size += len(chunk)
                        recovery_progress = (copied_size / file_size) * 100
                        self.status_var.set(f"Recovering {file_name}: {recovery_progress:.1f}%")
                        self.root.update_idletasks()
                
                if os.path.exists(destination) and os.path.getsize(destination) > 0:
                    successful += 1
                    self.recovered_files += 1
                else:
                    raise ValueError("Recovery failed: recovered file is empty")
                
                self.update_stats()
                
            except Exception as e:
                failed += 1
                error_msg = f"Failed to recover {values[0]}: {str(e)}"
                print(error_msg)
                messagebox.showerror("Recovery Error", error_msg)
                if os.path.exists(destination):
                    try:
                        os.remove(destination)
                    except:
                        pass
            
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

if __name__ == "__main__":
    # Install required libraries if not found
    # try:
    #     import psutil
    # except ModuleNotFoundError:
    #     print("Installing required library: psutil")
    #     import subprocess
    #     subprocess.check_call(["python", "-m", "pip", "install", "psutil"])
    #     import psutil

    # Check if running as admin (for deep scan features)
    try:
        import ctypes
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
        if not is_admin:
            print("Warning: For full functionality including deep scan, run as Administrator.")
    except:
        pass

    root = tk.Tk()
    app = RecoveryApp(root)
    root.mainloop()