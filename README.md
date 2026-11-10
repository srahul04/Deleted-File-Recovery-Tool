**Author: Rahul S**

# 🛡️ Forensic File Recovery Suite

[![Python](https://img.shields.io/badge/Python-3.8+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?logo=windows&logoColor=white)](https://microsoft.com/windows)
[![Offline](https://img.shields.io/badge/API-100%25%20Offline%20%26%20Private-2ea44f)](#)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

An offline digital forensics desktop tool designed to locate and restore deleted data from Windows systems. Supports both **logical recovery** (Recycle Bin with original folder structures) and **deep raw sector carving** (recovering permanently deleted files by signature headers without file system tables).

---

## ⚡ Key Highlights

- **100% Offline & Private**: Zero external APIs, zero telemetry, zero cloud calls. Everything runs locally on your PC.
- **Dual-Engine Recovery**:
  - **Logical Scan**: Recovers Recycle Bin items with original names, paths, and deletion timestamps.
  - **Deep Sector Carving**: Recovers permanently deleted files (Shift+Delete / formatted drives) by scanning raw storage blocks.
- **Multi-Format Support**:
  - 📷 **Images**: JPG, PNG
  - 📄 **Documents**: PDF, DOCX, XLSX, ZIP
  - 🎬 **Media**: MP4, MKV
  - ⚙️ **Executables**: EXE, DLL
- **Target Selection**: Easily switch between specific disk partitions (`C:`, `D:`) or entire physical drives.
- **Search & Sort**: Filter recovered items in real-time by file name, size, or date.

---

## 🚀 Quick Start Guide

### 1. Requirements
* Windows 10 / 11
* Python 3.8 or newer
* **Administrator Privileges** (required only for raw sector carving)

### 2. Install Dependencies
Open PowerShell or Command Prompt in the project folder and run:
```bash
pip install -r requirements.txt
```

### 3. Launch the Application
Right-click your terminal and select **"Run as Administrator"**, then run:
```bash
python main.py
```

---

## 📖 How to Use (Step-by-Step)

```
[ 1. Select Target ] ➔ [ 2. Click Start Scan ] ➔ [ 3. Select Files ] ➔ [ 4. Recover ]
```

1. **Select Target Drive**:
   - Choose your drive partition from the dropdown menu (e.g., `Logical Volume C:`, `D:`, or `Recycle Bin Only`).
2. **Start Scanning**:
   - Click **▶ Start Scan**. The progress bar and live counters will track recovered items in real time.
3. **Filter Your Files**:
   - Type in the **Filter Results** search box to quickly locate documents, photos, or specific file extensions.
   - Click table headers to sort by **Name**, **Size**, or **Date**.
4. **Restore**:
   - Highlight the files you want to save.
   - Click **💾 Recover Selected** and pick a destination folder (select a different drive or external USB to prevent overwriting deleted sectors).

---

## 📁 Project Architecture

```
Deleted-File-Recovery-Tool/
│
├── src/
│   ├── core/              # Low-level sector reader, volume geometry & Recycle Bin logic
│   ├── carvers/           # Format-specific signature carvers (JPEG, PNG, PDF, ZIP, EXE)
│   └── ui/                # Tkinter desktop interface
│
├── tests/                 # Automated unit tests
├── main.py                # Application entry point
├── requirements.txt       # Minimal dependencies (psutil, pywin32)
└── README.md              # Project documentation
```

---

## 🧪 Testing

Run the automated test suite to verify carvers and binary parsers:
```bash
python -m unittest discover tests
```

---

## 📄 License
This project is open-source and distributed under the MIT License.
