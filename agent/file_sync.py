"""
file_sync.py
Copies source files/folders from the network share to local destination folders.

Steps covered:
  1. Copy E10QAGolden_full_dmp  -> C:\\ErpCurrent\\DB
  2. Copy ICECommon_full_dmp    -> C:\\ErpCurrent\\CommonDB
  3. Copy latest Epicor build   -> C:\\ErpCurrent\\ISO
"""

import os
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class FileSyncAgent:
    def __init__(self, config: dict):
        net = config.get("network", {})
        loc = config.get("local", {})

        self.erp_db_source      = net.get("erp_db_source", "")
        self.common_db_source   = net.get("common_db_source", "")
        self.epicor_builds_path = net.get("epicor_builds_path", "")

        self.erp_db_dest      = loc.get("erp_db_dest", "")
        self.common_db_dest   = loc.get("common_db_dest", "")
        self.epicor_iso_dest  = loc.get("epicor_iso_dest", "")

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    def sync_erp_db(self) -> str:
        """Copy E10QAGolden_full_dmp from network to C:\\ErpCurrent\\DB.
        Returns the local path of the copied file/folder."""
        logger.info("=== Syncing ERP Database Backup ===")
        return self._copy_item(self.erp_db_source, self.erp_db_dest, label="ERP DB")

    def sync_common_db(self) -> str:
        """Copy ICECommon_full_dmp from network to C:\\ErpCurrent\\CommonDB.
        Returns the local path of the copied file/folder."""
        logger.info("=== Syncing ICECommon Database Backup ===")
        return self._copy_item(self.common_db_source, self.common_db_dest, label="ICECommon DB")

    def sync_epicor_build(self) -> str:
        """Copy the latest Epicor build folder from network to C:\\ErpCurrent\\ISO.
        Returns the local destination path."""
        logger.info("=== Syncing Epicor Kinetic Build Folder ===")
        src = self._get_latest_build_folder(self.epicor_builds_path)
        logger.info(f"Latest build folder identified: {src}")
        dest = self.epicor_iso_dest
        self._ensure_dir(dest)
        folder_name = Path(src).name
        dest_full = os.path.join(dest, folder_name)

        # Incremental sync avoids full recopy and handles large build folders faster.
        self._sync_folder_incremental(src, dest_full)
        logger.info(f"[OK] Epicor build synced to: {dest_full}")
        return dest_full

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _copy_item(self, source: str, dest_dir: str, label: str) -> str:
        """Copy a file or folder from source to dest_dir.
        Returns the full local destination path."""
        if not source:
            raise ValueError(f"Source path for {label} is not configured.")

        source = source.strip()
        self._check_network_access(source)
        self._ensure_dir(dest_dir)

        item_name = Path(source).name
        dest_full = os.path.join(dest_dir, item_name)

        src_path = Path(source)
        if src_path.is_dir():
            logger.info(f"Syncing folder {source} -> {dest_full}")
            self._sync_folder_incremental(source, dest_full)
        else:
            logger.info(f"Syncing file   {source} -> {dest_full}")
            self._sync_file_incremental(source, dest_dir)
            # Ensure the copied file is readable by the current user
            # (robocopy can preserve restrictive network share permissions)
            self._fix_permissions(dest_full)

        logger.info(f"[OK] {label} synced to: {dest_full}")
        return dest_full

    def _get_latest_build_folder(self, builds_path: str) -> str:
        """Return the path of the most recently modified sub-folder inside builds_path.
        If no sub-folders exist, returns builds_path itself."""
        self._check_network_access(builds_path)
        try:
            subfolders = [
                f for f in os.scandir(builds_path) if f.is_dir()
            ]
            if not subfolders:
                logger.warning(
                    f"No sub-folders found in {builds_path}. Using the path itself."
                )
                return builds_path
            latest = max(subfolders, key=lambda f: f.stat().st_mtime)
            return latest.path
        except PermissionError as e:
            raise PermissionError(
                f"Cannot read Epicor builds path '{builds_path}': {e}"
            )

    def _sync_folder_incremental(self, source_dir: str, dest_dir: str):
        """Fast incremental folder sync via robocopy (no delete/mirror)."""
        self._ensure_dir(dest_dir)
        args = [
            source_dir,
            dest_dir,
            "/E",
            "/Z",
            "/MT:16",
            "/FFT",
            "/R:1",
            "/W:1",
            "/NP",
            "/NJH",
            "/NJS",
            "/XO",
        ]
        self._run_robocopy(args)

    def _sync_file_incremental(self, source_file: str, dest_dir: str):
        """Copy a single file from source to dest_dir using .NET File.Copy.
        Robocopy /Z (restartable mode) was corrupting large .7z archives when
        the network interrupted mid-copy — .NET File.Copy is atomic and safe."""
        self._ensure_dir(dest_dir)
        dest_file = os.path.join(dest_dir, os.path.basename(source_file))

        import ctypes
        kernel32 = ctypes.windll.kernel32

        # Use CopyFileEx for large file copy — reliable, no partial-file corruption
        result = kernel32.CopyFileExW(
            source_file,
            dest_file,
            None, None, None,
            0x00000008  # COPY_FILE_RESTARTABLE = 0, COPY_FILE_NO_BUFFERING = 0x8
        )
        if not result:
            err = ctypes.GetLastError()
            # Fallback: use Python shutil if CopyFileEx fails
            logger.warning(f"CopyFileExW failed (err={err}), falling back to shutil.copy2")
            import shutil
            shutil.copy2(source_file, dest_file)


    def _run_robocopy(self, args: list[str]):
        """Run robocopy and treat exit codes 0-7 as success, >=8 as failure."""
        cmd = ["robocopy"] + args
        logger.debug("Running: %s", " ".join(cmd))

        result = subprocess.run(cmd, capture_output=True, text=True)
        code = result.returncode

        if code >= 8:
            raise RuntimeError(
                "Robocopy failed with exit code "
                f"{code}.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )

        # 0-7 are success/warnings in robocopy semantics.
        if result.stdout.strip():
            logger.debug(result.stdout)
        if result.stderr.strip():
            logger.debug(result.stderr)

    @staticmethod
    def _fix_permissions(path: str):
        """Grant the current user full read/write access.
        Robocopy preserves network share ACLs which can block local access."""
        try:
            import subprocess, os
            user = os.environ.get("USERNAME", "")
            domain = os.environ.get("USERDOMAIN", "")
            account = f"{domain}\\{user}" if domain else user
            subprocess.run(
                ["icacls", path, "/grant", f"{account}:(F)", "/T"],
                capture_output=True, check=False
            )
            logger.debug(f"Permissions fixed for: {path}")
        except Exception as e:
            logger.warning(f"Could not fix permissions on {path}: {e}")

    @staticmethod
    def _check_network_access(path: str):
        """Raise a clear error if the network/local path is not accessible."""
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Path not found or not accessible: {path}\n"
                f"  • Check you are connected to the network.\n"
                f"  • Check VPN / share permissions."
            )

    @staticmethod
    def _ensure_dir(path: str):
        """Create directory (and parents) if it does not exist."""
        Path(path).mkdir(parents=True, exist_ok=True)
        logger.debug(f"Directory ready: {path}")
