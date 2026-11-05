# Data Recovery Tool - System Architecture

```mermaid
%%{init: {'theme': 'dark'}}%%
graph TD
    subgraph UI_Layer["User Interface Layer"]
        UI[GUI Window]
        Controls[Control Buttons]
        TreeView[File TreeView]
        Search[Search Box]
        Stats[Statistics Display]
        Progress[Progress Bar]
    end

    subgraph Core_Layer["Core Recovery Layer"]
        LogicalRecovery[Logical Recovery Module]
        PhysicalRecovery[Physical Recovery Module]
        FileSignatures[File Signatures DB]
        MetadataParser[Metadata Parser]
    end

    subgraph Storage_Layer["Storage Access Layer"]
        RecycleBin[Recycle Bin Access]
        PhysicalDrive[Physical Drive Access]
        FileSystem[File System Access]
    end

    subgraph Recovery_Types["Recovery Types"]
        RBRecovery[Recycle Bin Recovery]
        PhysicalScan[Deep Physical Scan]
        FileCarving[File Carving]
    end

    UI --> Controls;
    UI --> TreeView;
    UI --> Search;
    UI --> Stats;
    UI --> Progress;

    LogicalRecovery --> RecycleBin;
    PhysicalRecovery --> PhysicalDrive;
    PhysicalRecovery --> FileSignatures;
    LogicalRecovery --> MetadataParser;

    Controls --> RBRecovery;
    Controls --> PhysicalScan;
    RBRecovery --> LogicalRecovery;
    PhysicalScan --> PhysicalRecovery;
    PhysicalRecovery --> FileCarving;

    RecycleBin --> FileSystem;
    PhysicalDrive --> FileSystem;
    FileSystem --> TreeView;
    MetadataParser --> Stats;

    Search --> TreeView;

    classDef primary fill:#ff9999,stroke:#fff,stroke-width:2px,color:#fff;
    classDef secondary fill:#9999ff,stroke:#fff,stroke-width:2px,color:#fff;
    classDef storage fill:#99ff99,stroke:#fff,stroke-width:2px,color:#fff;
    
    class UI,Controls,TreeView,Search,Stats,Progress primary;
    class LogicalRecovery,PhysicalRecovery,FileSignatures,MetadataParser secondary;
    class RecycleBin,PhysicalDrive,FileSystem storage;
```

## Component Description

1. **User Interface Layer**
   - GUI Window: Main application window (tkinter)
   - Control Buttons: Start Scan, Stop Scan, Recover Selected
   - File TreeView: Displays found files and metadata
   - Search Box: Live file search functionality
   - Statistics Display: Shows recovery statistics
   - Progress Bar: Displays operation progress

2. **Core Recovery Layer**
   - Logical Recovery Module: Handles Recycle Bin recovery
   - Physical Recovery Module: Manages physical drive scanning
   - File Signatures DB: Stores file magic numbers
   - Metadata Parser: Processes file metadata

3. **Storage Access Layer**
   - Recycle Bin Access: Interfaces with Windows Recycle Bin
   - Physical Drive Access: Raw disk access
   - File System Access: File operations management

4. **Recovery Types**
   - Recycle Bin Recovery: Recovers from $Recycle.Bin
   - Deep Physical Scan: Raw drive scanning
   - File Carving: Signature-based file recovery

## Data Flow

1. **Recovery Process**
   - User initiates scan through UI
   - Logical Recovery checks Recycle Bin
   - Physical Recovery scans drives
   - Found files displayed in TreeView
   - Progress updated in real-time

2. **File Recovery**
   - User selects files in TreeView
   - System checks recovery type
   - Executes appropriate recovery method
   - Updates progress and statistics

## Security Features

- Administrator privilege checks
- Safe file handling
- Permission management
- Error handling and recovery

## Key Features

1. **File Detection**
   - Multiple file signature support
   - Metadata preservation
   - Directory structure recovery

2. **User Interface**
   - Real-time progress updates
   - Live search functionality
   - Sortable file list
   - Detailed file information

3. **Recovery Options**
   - Recycle Bin recovery
   - Physical drive scanning
   - Selective file recovery
   - Directory recovery support