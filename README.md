# EpicorSetupAgent

> **Automated Epicor Kinetic Local Development Environment Setup**  
> Automates the full process of syncing database backups and Epicor build files from the network share, then restoring both databases to a local SQL Server 2022 instance.

---

## 📋 What This Tool Does

This tool replaces the manual setup process with a single command. It performs the following steps automatically:

| Step | Action |
|------|--------|
| **0** | Check system prerequisites (OS, RAM, disk, .NET, SQL Server tools, IIS, PowerShell) |
| **1** | Copy `E10QAGolden_full_dmp` from network share → `C:\ErpCurrent\DB` |
| **1** | Copy `ICECommon_full_dmp` from network share → `C:\ErpCurrent\CommonDB` |
| **1** | Copy the latest Epicor Kinetic build folder from network share → `C:\ErpCurrent\ISO` |
| **2** | Restore `E10QAGolden_full_dmp` into local SQL Server 2022 as database `E10QAGolden` |
| **3** | Restore `ICECommon_full_dmp` into local SQL Server 2022 as database `ICECommon` |

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

---

## 📦 Network Source Paths

| File / Folder | Network Path |
|--------------|-------------|
| ERP DB Backup | `\\quicksilver\BLDesktop\ERPCurrent\QAGoldenMT\E10QAGolden_full_dmp` |
| ICECommon DB Backup | `\\quicksilver\BLDesktop\ERPCurrent\CommonDB\ICECommon_full_dmp` |
| Epicor Build Folder | `\\quicksilver\InstallExes\Epicor12\ERPCurrent` |

---

## 📁 Local Destination Paths

| File / Folder | Local Path |
|--------------|-----------|
| ERP DB Backup | `C:\ErpCurrent\DB\E10QAGolden_full_dmp` |
| ICECommon DB Backup | `C:\ErpCurrent\CommonDB\ICECommon_full_dmp` |
| Epicor Build Folder | `C:\ErpCurrent\ISO\<latest-build-folder>` |

> Local folders are created automatically if they do not exist.

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
  erp_db_source:      # UNC path to E10QAGolden_full_dmp on the network share
  common_db_source:   # UNC path to ICECommon_full_dmp on the network share
  epicor_builds_path: # UNC path to Epicor build folder root

local:
  erp_db_dest:        # Local folder where ERP backup is copied to
  common_db_dest:     # Local folder where ICECommon backup is copied to
  epicor_iso_dest:    # Local folder where Epicor build is copied to

sql_server:
  instance:           # SQL Server instance (e.g. "localhost")
  auth_mode:          # "windows" (Windows Auth) or "sql" (SQL Auth)
  sql_user:           # SQL login (only if auth_mode = "sql")
  sql_password:       # SQL password (only if auth_mode = "sql")
  erp_db_name:        # Target DB name for ERP restore (default: E10QAGolden)
  common_db_name:     # Target DB name for ICECommon restore (default: ICECommon)
  data_path:          # Override SQL data file path (blank = use SQL Server default)
  log_path:           # Override SQL log file path (blank = use SQL Server default)
```

---

## 🗄️ Database Details

### ERP Database — `E10QAGolden`

| Property | Value |
|---------|-------|
| Source file | `E10QAGolden_full_dmp` |
| Source type | SQL Server compressed full backup |
| Network path | `\\quicksilver\BLDesktop\ERPCurrent\QAGoldenMT\` |
| Local copy path | `C:\ErpCurrent\DB\` |
| Restored database name | `E10QAGolden` |
| SQL Server | Local SQL Server 2022 |

### Common Database — `ICECommon`

| Property | Value |
|---------|-------|
| Source file | `ICECommon_full_dmp` |
| Source type | SQL Server full backup (.bak) |
| Network path | `\\quicksilver\BLDesktop\ERPCurrent\CommonDB\` |
| Local copy path | `C:\ErpCurrent\CommonDB\` |
| Restored database name | `ICECommon` |
| SQL Server | Local SQL Server 2022 |

---

## 📝 Logging

All output is logged to `logs/setup.log` and printed to the console.  
Log format: `YYYY-MM-DD HH:MM:SS [LEVEL] module: message`

---

## ❓ Troubleshooting

| Problem | Solution |
|--------|---------|
| `Path not found or not accessible` | Ensure VPN is connected and you have access to `\\quicksilver` |
| `sqlcmd not found in PATH` | Install [SSMS](https://aka.ms/ssmsfullsetup) or [SQL Server command-line tools](https://learn.microsoft.com/en-us/sql/tools/sqlcmd/sqlcmd-utility) |
| `ODBC Driver not found` | Install [ODBC Driver 17 for SQL Server](https://aka.ms/odbc17) |
| `Restore failed: database in use` | Open SSMS, set the database to Single User mode, then retry |
| `Access denied on C:\ErpCurrent` | Run the script as Administrator |
| `Not enough disk space` | Free up space on C: (100 GB recommended) |

---

## 👨‍💻 Development Notes

- **Primary restore method**: `pyodbc` with ODBC Driver 17 for SQL Server
- **Fallback restore method**: `sqlcmd` command-line utility
- The agent automatically queries SQL Server for its default data/log file paths
- Logical file names inside the backup are auto-detected via `RESTORE FILELISTONLY`
- The latest Epicor build folder is identified by most-recent modification date

---

## 📄 License

Internal use only — Epicor Kinetic development team.

