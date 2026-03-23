"""
file_sync.py
Copies source files/folders from the network share to local destination folders.

Steps covered:
  1. Copy E10QAGolden_full_dmp  -> C:\ErpCurrent\DB
  2. Copy ICECommon_full_dmp    -> C:\ErpCurrent\CommonDB
  3. Copy latest Epicor build   -> C:\ErpCurrent\ISO
"""

import os
import shutil
import logging
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

        if os.path.exists(dest_full):
            logger.info(f"Removing existing folder: {dest_full}")
            shutil.rmtree(dest_full)

        logger.info(f"Copying  {src}")
        logger.info(f"      -> {dest_full}")
        shutil.copytree(src, dest_full)
        logger.info(f"[OK] Epicor build copied to: {dest_full}")
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
            # Source is a directory – copy the whole folder
            if os.path.exists(dest_full):
                logger.info(f"Removing existing folder: {dest_full}")
                shutil.rmtree(dest_full)
            logger.info(f"Copying folder {source} -> {dest_full}")
            shutil.copytree(source, dest_full)
        else:
            # Source is a file
            logger.info(f"Copying file  {source} -> {dest_full}")
            shutil.copy2(source, dest_full)

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

