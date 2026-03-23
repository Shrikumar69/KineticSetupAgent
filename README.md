# EpicorSetupAgent

> **Automated Epicor Kinetic Local Development Environment Setup**  
> This project exists to solve one practical problem: **manual Epicor local setup wastes too much developer time**. It automates copying the required database/build files from the network and prepares the restore workflow so developers do not have to manually browse shares, copy huge files, and repeat the same steps every time.

---

## 🎯 Problem This Tool Solves

Before this tool, a developer had to do all of the following manually:

1. Open the network share paths by hand
2. Find the latest ERP backup
3. Find the Common DB backup
4. Find the latest Epicor build folder
5. Copy everything to the correct local folders
6. Wait for large files and ISO copies to finish
7. Repeat the same process again for every rebuild / refresh

That is slow, repetitive, and error-prone.

`EpicorSetupAgent` is intended to be the **problem solver** for that workflow by:

- using the **correct shared network paths**
- copying to the **correct local folders**
- automatically finding the **latest Epicor build folder**
- using **incremental fast sync** instead of delete-and-copy-everything
- reducing repeat run time dramatically once files are already present locally

---

## 📋 What This Tool Does

This tool replaces the manual setup process with a single command. It performs the following steps automatically:

| Step | Action |
|------|--------|
| **0** | Check system prerequisites (OS, RAM, disk, .NET, SQL Server tools, IIS, PowerShell) |
| **1** | Copy `E10QAGolden_full_dmp.7z` from network share → `C:\ErpCurrent\DB` |
| **1** | Copy `ICECommon_full_dmp.bak` from network share → `C:\ErpCurrent\CommonDB` |
| **1** | Copy the latest Epicor Kinetic build folder from network share → `C:\ErpCurrent\ISO` |
| **2** | Restore `E10QAGolden_full_dmp` into local SQL Server 2022 as database `E10QAGolden` |
| **3** | Restore `ICECommon_full_dmp` into local SQL Server 2022 as database `ICECommon` |

---

## ✅ What Has Been Verified On This Machine

The copy workflow was tested successfully on **2026-03-23**.

Verified successful outputs:

- ERP backup copied to: `C:\ErpCurrent\DB\E10QAGolden_full_dmp.7z`
- Common DB copied to: `C:\ErpCurrent\CommonDB\ICECommon_full_dmp.bak`
- Latest Epicor build copied to: `C:\ErpCurrent\ISO\20260322`
- Latest Epicor ISO found at: `C:\ErpCurrent\ISO\20260322\Build820\ERPCurrent.iso`

Verified copied file sizes from the successful run:

| Item | Destination | Size |
|------|-------------|------|
| ERP backup archive | `C:\ErpCurrent\DB\E10QAGolden_full_dmp.7z` | `1,650,558,962 bytes` |
| ICECommon backup | `C:\ErpCurrent\CommonDB\ICECommon_full_dmp.bak` | `34,459,648 bytes` |
| Epicor ISO | `C:\ErpCurrent\ISO\20260322\Build820\ERPCurrent.iso` | `5,058,557,952 bytes` |

Current restore status from testing:

- SQL connectivity from Python is working
- ERP restore was attempted successfully up to SQL execution
- ERP restore is currently blocked by an **existing SQL file-name collision** with database `ERP10Dev`
- That restore issue is a **database/file-placement problem**, not a copy problem

---

## 🗂 Project Structure

```
EpicorSetupAgent/
├── main.py                   # CLI entry point — run this
├── requirements.txt          # Python dependencies
├── .gitignore
├── README.md
│
├── config/
│   └── config.yaml           # All paths, SQL Server settings, options
│
├── agent/
│   ├── __init__.py
│   ├── prerequisites.py      # System prerequisite checks
│   ├── file_sync.py          # Network → local file copy logic
│   └── db_restore.py         # SQL Server database restore logic
│
└── logs/
    └── setup.log             # Generated at runtime
```

---

## ⚙️ Prerequisites

| Requirement | Details |
|------------|---------|
| **OS** | Windows 10 / Windows Server 2019 or later |
| **Python** | 3.10 or higher |
| **SQL Server 2022** | Local instance running (any edition) |
| **SSMS / sqlcmd** | SQL Server Management Studio or command-line tools |
| **Network access** | Must be able to reach `\\quicksilver` share |
| **RAM** | 16 GB minimum recommended |
| **Disk** | 100 GB free on C: recommended |

> Note: in real testing, the network share root was reachable, but the exact file names mattered. The working files were `E10QAGolden_full_dmp.7z` and `ICECommon_full_dmp.bak`.

---

## 📦 Network Source Paths

| File / Folder | Network Path |
|--------------|-------------|
| ERP DB Backup | `\\quicksilver\BLDesktop\ERPCurrent\QAGoldenMT\E10QAGolden_full_dmp.7z` |
| ICECommon DB Backup | `\\quicksilver\BLDesktop\ERPCurrent\CommonDB\ICECommon_full_dmp.bak` |
| Epicor Build Folder | `\\quicksilver\InstallExes\Epicor12\ERPCurrent` |

The latest Epicor build folder is selected automatically by **most recent modified time**.  
Example verified latest folder during testing: `20260322`

---

## 📁 Local Destination Paths

| File / Folder | Local Path |
|--------------|-----------|
| ERP DB Backup | `C:\ErpCurrent\DB\E10QAGolden_full_dmp.7z` |
| ICECommon DB Backup | `C:\ErpCurrent\CommonDB\ICECommon_full_dmp.bak` |
| Epicor Build Folder | `C:\ErpCurrent\ISO\<latest-build-folder>` |

> Local folders are created automatically if they do not exist.

Verified example from testing:

- `C:\ErpCurrent\ISO\20260322`
- `C:\ErpCurrent\ISO\20260322\Build820\ERPCurrent.iso`

---

## ⏱ Time Saved / Real Measured Results

The main value of this tool is **time saving on repeat setup runs**.

### Real measured copy timings from testing on 2026-03-23

#### Successful clean incremental sync run

| Step | Start | End | Approx Time |
|------|-------|-----|-------------|
| ERP backup sync | 14:54:53 | 14:54:59 | ~5 sec |
| ICECommon sync | 14:55:01 | 14:55:07 | ~5 sec |
| Latest Epicor build sync | 14:55:09 | 14:55:17 | ~8 sec |
| **Total sync run** | 14:54:49 | 14:55:17 | **~28 sec** |

#### First heavy Epicor ISO copy observed earlier

During earlier testing, the large Epicor ISO transfer copied about **4.7 GB** and took approximately:

- **~40 minutes 50 seconds**

This difference is exactly why the agent now uses **incremental sync**.

### Why later runs are much faster

The copy logic now uses `robocopy` incremental sync instead of deleting the destination and copying everything again.

That means:

- first large copy can still take time
- repeated runs skip unchanged files
- latest Epicor build checks become much faster
- developers do not lose time re-copying the same ISO/archive again and again

---

## 🚀 Getting Started

### 1. Clone the repository

```powershell
git clone <repo-url>
cd KneticSetupAgent
```

### 2. Create a Python virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

### 4. Review the configuration

Open `config/config.yaml` and verify:

- **`sql_server.instance`** — matches your local SQL Server instance name  
  (e.g. `localhost`, `.\SQLEXPRESS`, `localhost\MSSQLSERVER`)
- **`sql_server.auth_mode`** — `windows` (default) or `sql`
- All network and local paths are correct

### 5. Run the agent

```powershell
# Run everything (recommended)
python main.py --all

# Or step by step:
python main.py --check      # Prerequisites check only
python main.py --sync       # Copy files from network only
python main.py --restore    # Restore databases only
```

---

## 🛠 Configuration Reference (`config/config.yaml`)

```yaml
network:
  erp_db_source: "\\quicksilver\BLDesktop\ERPCurrent\QAGoldenMT\E10QAGolden_full_dmp.7z"
  common_db_source: "\\quicksilver\BLDesktop\ERPCurrent\CommonDB\ICECommon_full_dmp.bak"
  epicor_builds_path: "\\quicksilver\InstallExes\Epicor12\ERPCurrent"

local:
  erp_db_dest: "C:\ErpCurrent\DB"
  common_db_dest: "C:\ErpCurrent\CommonDB"
  epicor_iso_dest: "C:\ErpCurrent\ISO"

sql_server:
  instance: "localhost"
  auth_mode: "windows"
  erp_db_name: "E10QAGolden"
  common_db_name: "ICECommon"
```

---

## 🗄️ Database Details

### ERP Database — `E10QAGolden`

| Property | Value |
|---------|-------|
| Source file | `E10QAGolden_full_dmp.7z` |
| Source type | Archive containing ERP backup |
| Network path | `\\quicksilver\BLDesktop\ERPCurrent\QAGoldenMT\` |
| Local copy path | `C:\ErpCurrent\DB\` |
| Restored database name | `E10QAGolden` |
| SQL Server | Local SQL Server 2022 |

> Important: the ERP source currently arrives as `.7z`, so extraction to `.bak` is still part of the overall restore workflow design.

### Common Database — `ICECommon`

| Property | Value |
|---------|-------|
| Source file | `ICECommon_full_dmp.bak` |
| Source type | SQL Server full backup (.bak) |
| Network path | `\\quicksilver\BLDesktop\ERPCurrent\CommonDB\` |
| Local copy path | `C:\ErpCurrent\CommonDB\` |
| Restored database name | `ICECommon` |
| SQL Server | Local SQL Server 2022 |

---

## 🚀 Why This Saves Team Time

This README should make it clear to every developer why this project matters.

### Without the agent

- manually browse multiple network paths
- manually identify the newest Epicor build folder
- manually copy large files to the correct local folders
- wait through long transfers with no repeat-run optimization
- repeat the same process for every refresh

### With the agent

- one command: `python main.py --sync`
- correct source and destination paths are already defined
- latest Epicor build folder is auto-detected
- repeat runs are much faster because unchanged files are skipped
- reduces mistakes and setup time for everyone on the team

---

## 📝 Logging

All output is logged to `logs/setup.log` and printed to the console.  
Log format: `YYYY-MM-DD HH:MM:SS [LEVEL] module: message`

Useful log examples already captured:

- `[OK] ERP DB synced to: C:\ErpCurrent\DB\E10QAGolden_full_dmp.7z`
- `[OK] ICECommon DB synced to: C:\ErpCurrent\CommonDB\ICECommon_full_dmp.bak`
- `Latest build folder identified: \\quicksilver\InstallExes\Epicor12\ERPCurrent\20260322`
- `[OK] Epicor build synced to: C:\ErpCurrent\ISO\20260322`

---

## ❓ Troubleshooting

| Problem | Solution |
|--------|---------|
| `Path not found or not accessible` | Ensure VPN is connected and you have access to `\\quicksilver` |
| Wrong ERP/Common filename | Use the exact reachable filenames: `E10QAGolden_full_dmp.7z` and `ICECommon_full_dmp.bak` |
| First Epicor copy is slow | This is expected for the first large ISO transfer; later runs are incremental and much faster |
| Existing file is locked | Close mounted ISO, Explorer preview, or setup processes before re-syncing |
| `sqlcmd not found in PATH` | Install [SSMS](https://aka.ms/ssmsfullsetup) or [SQL Server command-line tools](https://learn.microsoft.com/en-us/sql/tools/sqlcmd/sqlcmd-utility) |
| `ODBC Driver not found` | Install [ODBC Driver 17 for SQL Server](https://aka.ms/odbc17) |
| `Restore failed: database in use / file already in use` | Current tested blocker: ERP restore conflicts with existing SQL files used by `ERP10Dev`; fix file naming or restore target before retrying |
| `Access denied on C:\ErpCurrent` | Run the script as Administrator |
| `Not enough disk space` | Free up space on C: (100 GB recommended) |

---

## 👨‍💻 Development Notes

- **Primary restore method**: `pyodbc` with ODBC Driver 17 for SQL Server
- **Fallback restore method**: `sqlcmd` command-line utility
- The agent automatically queries SQL Server for its default data/log file paths
- Logical file names inside the backup are auto-detected via `RESTORE FILELISTONLY`
- The latest Epicor build folder is identified by most-recent modification date
- File sync now uses **incremental `robocopy`-based fast sync** instead of delete-and-full-copy
- Incremental sync is the main reason repeat copy runs dropped to about **28 seconds** in tested scenarios

---

## 📄 License

Internal use only — Epicor Kinetic development team.

