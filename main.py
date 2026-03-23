"""
main.py
EpicorSetupAgent - Main CLI entry point

Usage:
    python main.py              # Run all steps interactively
    python main.py --sync       # Step 1: copy files from network
    python main.py --extract    # Step 2: extract ERP .7z archive -> .bak
    python main.py --restore    # Step 3: restore both databases
    python main.py --all        # Run all steps non-interactively
    python main.py --check      # Check prerequisites only
"""

import sys
import logging
import argparse
import yaml
from pathlib import Path
from datetime import datetime

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich import print as rprint
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

from agent.prerequisites import PrerequisiteChecker
from agent.file_sync import FileSyncAgent
from agent.extractor import ExtractorAgent
from agent.db_restore import DatabaseRestoreAgent
from agent.db_restore import DatabaseRestoreAgent

# ------------------------------------------------------------------
# Logging setup
# ------------------------------------------------------------------

def setup_logging(log_file: str, level: str = "INFO"):
    # When running as .exe, write log next to the executable
    if getattr(sys, "frozen", False):
        log_path = Path(sys.executable).parent / "EpicorSetupAgent.log"
    else:
        log_path = Path(log_file)

    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )

# ------------------------------------------------------------------
# Config loader
# ------------------------------------------------------------------

def load_config(config_path: str = "config/config.yaml") -> dict:
    import shutil

    # --- Running as a PyInstaller .exe ---
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        local_cfg = exe_dir / "config.yaml"

        if not local_cfg.exists():
            # First run: copy bundled config next to the .exe so user can edit it
            bundle_dir = Path(getattr(sys, "_MEIPASS", exe_dir))
            bundled = bundle_dir / "config" / "config.yaml"
            if bundled.exists():
                shutil.copy2(str(bundled), str(local_cfg))
                print(f"[INFO] Config created next to EpicorSetupAgent.exe: {local_cfg}")
                print("[INFO] Open config.yaml to review SQL Server settings before re-running.")

        cfg_file = local_cfg

    # --- Running as a normal Python script ---
    else:
        cfg_file = Path(config_path)

    if not cfg_file.exists():
        raise FileNotFoundError(
            f"Config file not found: {cfg_file.resolve()}\n"
            "Ensure config.yaml exists next to the .exe (or config/config.yaml for script mode)."
        )
    with open(cfg_file, "r") as f:
        return yaml.safe_load(f)

# ------------------------------------------------------------------
# Display helpers
# ------------------------------------------------------------------

console = Console() if HAS_RICH else None

def banner():
    if HAS_RICH:
        console.print(Panel.fit(
            "[bold cyan]EpicorSetupAgent[/bold cyan]\n"
            "[dim]Automated Epicor Kinetic Local Environment Setup[/dim]\n"
            f"[dim]{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/dim]",
            border_style="cyan"
        ))
    else:
        print("=" * 60)
        print("  EpicorSetupAgent")
        print("  Automated Epicor Kinetic Local Environment Setup")
        print("=" * 60)

def step_header(title: str):
    if HAS_RICH:
        console.rule(f"[bold green]{title}[/bold green]")
    else:
        print(f"\n{'='*60}\n  {title}\n{'='*60}")

def success(msg: str):
    if HAS_RICH:
        console.print(f"[bold green]✅ {msg}[/bold green]")
    else:
        print(f"[OK] {msg}")

def error(msg: str):
    if HAS_RICH:
        console.print(f"[bold red]❌ {msg}[/bold red]")
    else:
        print(f"[ERROR] {msg}")

def info(msg: str):
    if HAS_RICH:
        console.print(f"[cyan]ℹ  {msg}[/cyan]")
    else:
        print(f"[INFO] {msg}")

def print_prereq_table(results: list):
    if not HAS_RICH:
        for r in results:
            print(f"  {r['icon']} {r['name']}: {r['detail']}")
        return
    table = Table(title="Prerequisites Check", show_header=True, header_style="bold magenta")
    table.add_column("Check",  style="bold")
    table.add_column("Status", justify="center")
    table.add_column("Detail")
    for r in results:
        status_color = "green" if r["status"] else "red"
        table.add_row(r["name"], f"[{status_color}]{r['icon']}[/{status_color}]", r["detail"])
    console.print(table)

# ------------------------------------------------------------------
# Steps
# ------------------------------------------------------------------

def run_prerequisites(config: dict) -> bool:
    step_header("Step 0 — Prerequisites Check")
    checker = PrerequisiteChecker(config)
    all_ok = checker.run_all()
    print_prereq_table(checker.results)
    if all_ok:
        success("All prerequisites passed.")
    else:
        error("Some prerequisites failed. Review the table above.")
    return all_ok

def run_sync(config: dict):
    step_header("Step 1 — Copy Files from Network Share")
    agent = FileSyncAgent(config)

    info(f"Copying ERP DB backup from network ...")
    erp_path = agent.sync_erp_db()
    success(f"ERP DB backup copied to: {erp_path}")

    info(f"Copying ICECommon DB backup from network ...")
    ice_path = agent.sync_common_db()
    success(f"ICECommon DB backup copied to: {ice_path}")

    info(f"Copying latest Epicor build folder from network ...")
    iso_path = agent.sync_epicor_build()
    success(f"Epicor build folder copied to: {iso_path}")

def run_extract(config: dict):
    step_header("Step 2 — Extract ERP Backup Archive (.7z → .bak)")
    agent = ExtractorAgent(config)
    info("Extracting E10QAGolden_full_dmp.7z ...")
    bak_path = agent.extract_erp_backup()
    success(f"ERP backup extracted to: {bak_path}")

def run_restore(config: dict):
    step_header("Step 3 — Restore ERP Database (E10QAGolden)")
    agent = DatabaseRestoreAgent(config)

    info("Restoring E10QAGolden to SQL Server 2022 ...")
    agent.restore_erp_db()
    success("E10QAGolden database restored successfully.")

    step_header("Step 4 — Restore ICECommon Database")
    info("Restoring ICECommon to SQL Server 2022 ...")
    agent.restore_common_db()
    success("ICECommon database restored successfully.")

# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="EpicorSetupAgent - Automate Epicor Kinetic local environment setup"
    )
    parser.add_argument("--all",     action="store_true", help="Run all steps (sync + extract + restore)")
    parser.add_argument("--sync",    action="store_true", help="Step 1: Copy files from network share")
    parser.add_argument("--extract", action="store_true", help="Step 2: Extract ERP .7z archive to .bak")
    parser.add_argument("--restore", action="store_true", help="Steps 3-4: Restore both databases")
    parser.add_argument("--check",   action="store_true", help="Check prerequisites only")
    parser.add_argument("--config",  default="config/config.yaml", help="Path to config file")
    args = parser.parse_args()

    config = load_config(args.config)
    log_cfg = config.get("logging", {})
    setup_logging(log_cfg.get("log_file", "logs/setup.log"), log_cfg.get("level", "INFO"))

    banner()

    # Default: interactive mode if no flags given
    run_all = args.all or (not args.sync and not args.extract and not args.restore and not args.check)

    try:
        if args.check or run_all:
            ok = run_prerequisites(config)
            if not ok and not run_all:
                sys.exit(1)

        if args.sync or run_all:
            run_sync(config)

        if args.extract or run_all:
            run_extract(config)

        if args.restore or run_all:
            run_restore(config)

        if run_all or args.sync or args.extract or args.restore:
            print()
            success("EpicorSetupAgent completed all steps successfully!")
            info(f"Check the log file for details: {log_cfg.get('log_file', 'logs/setup.log')}")

    except FileNotFoundError as e:
        error(str(e))
        logging.error(str(e))
        sys.exit(1)
    except PermissionError as e:
        error(str(e))
        logging.error(str(e))
        sys.exit(1)
    except RuntimeError as e:
        error(str(e))
        logging.error(str(e))
        sys.exit(1)
    except Exception as e:
        error(f"Unexpected error: {e}")
        logging.exception("Unexpected error")
        sys.exit(1)


if __name__ == "__main__":
    main()

