"""
extractor.py
Handles extraction of compressed ERP backup archives (.7z) before DB restore.

The ERP backup arrives as a compressed .7z archive from the network share.
This module extracts it into the same local folder so the .bak file is
available for SQL Server restore.
"""

import os
import logging
import subprocess
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


class ExtractorAgent:
    def __init__(self, config: dict):
        loc = config.get("local", {})
        self.erp_db_dest = loc.get("erp_db_dest", r"C:\ErpCurrent\DB")

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def extract_erp_backup(self) -> str:
        """Extract E10QAGolden_full_dmp.7z into the local DB folder.
        Returns the path of the extracted .bak file."""
        logger.info("=== Extracting ERP Backup Archive ===")

        archive = self._find_archive(self.erp_db_dest)
        dest_dir = str(Path(archive).parent)

        logger.info(f"Archive  : {archive}")
        logger.info(f"Dest dir : {dest_dir}")

        # Verify archive integrity before attempting extraction
        self._verify_archive(archive)

        # Try py7zr first (pure Python), fallback to 7z.exe
        try:
            import py7zr
            bak_path = self._extract_with_py7zr(archive, dest_dir)
        except ImportError:
            logger.warning("py7zr not available — trying 7z.exe")
            bak_path = self._extract_with_7zip_exe(archive, dest_dir)

        logger.info(f"[OK] Extracted backup file: {bak_path}")
        return bak_path

    # ------------------------------------------------------------------
    # Extraction methods
    # ------------------------------------------------------------------

    def _extract_with_py7zr(self, archive: str, dest_dir: str) -> str:
        import py7zr

        logger.info("Extracting with py7zr ...")
        with py7zr.SevenZipFile(archive, mode="r") as z:
            all_files = z.getnames()
            logger.debug(f"Files inside archive: {all_files}")
            z.extractall(path=dest_dir)

        return self._find_extracted_bak(dest_dir, archive)

    def _extract_with_7zip_exe(self, archive: str, dest_dir: str) -> str:
        exe = self._find_7zip_exe()
        if not exe:
            raise EnvironmentError(
                "7-Zip not found. Install py7zr (pip install py7zr) "
                "or install 7-Zip from https://www.7-zip.org/"
            )

        logger.info(f"Extracting with 7z.exe: {exe}")
        result = subprocess.run(
            [exe, "x", archive, f"-o{dest_dir}", "-y"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"7z.exe extraction failed (exit {result.returncode}).\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            )
        logger.debug(result.stdout)
        return self._find_extracted_bak(dest_dir, archive)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _find_extracted_bak(self, dest_dir: str, archive_path: str) -> str:
        """Locate the .bak file produced by extraction."""
        # Search in dest_dir and subdirectories
        bak_files = sorted(
            Path(dest_dir).rglob("*.bak"),
            key=lambda f: f.stat().st_size,
            reverse=True  # largest .bak first (most likely the main DB backup)
        )
        if bak_files:
            return str(bak_files[0])

        # Fallback: any file without .7z/.zip extension larger than 100 MB
        for f in Path(dest_dir).rglob("*"):
            if f.is_file() and f.suffix not in (".7z", ".zip", ".gz") and f.stat().st_size > 100_000_000:
                return str(f)

        raise FileNotFoundError(
            f"Could not find a .bak file after extraction in: {dest_dir}\n"
            f"Archive was: {archive_path}\n"
            "Check the archive contents manually."
        )

    @staticmethod
    def _verify_archive(archive_path: str):
        """Verify the archive has the correct 7z magic bytes.
        Raises a clear error with resync instructions if the file is corrupt."""
        SEVENZIP_MAGIC = bytes([0x37, 0x7A, 0xBC, 0xAF, 0x27, 0x1C])
        try:
            with open(archive_path, "rb") as f:
                header = f.read(6)
        except OSError as e:
            raise RuntimeError(f"Cannot read archive file: {archive_path}\n{e}")

        if header != SEVENZIP_MAGIC:
            raise RuntimeError(
                f"Archive is corrupt or invalid: {archive_path}\n"
                f"  Expected header : {SEVENZIP_MAGIC.hex(' ')}\n"
                f"  Found header    : {header.hex(' ')}\n\n"
                f"Fix: delete the local file and re-run sync to get a fresh copy:\n"
                f"  del \"{archive_path}\"\n"
                f"  python main.py --sync\n"
                f"  python main.py --extract"
            )
        logger.info("Archive integrity check passed.")

    @staticmethod
    def _find_archive(local_db_dir: str) -> str:
        """Find the .7z archive in the local DB folder."""
        base = Path(local_db_dir)
        if not base.exists():
            raise FileNotFoundError(
                f"Local DB folder does not exist: {local_db_dir}\n"
                "Run the sync step first (--sync)."
            )

        # Look for .7z files
        archives = list(base.glob("*.7z"))
        if archives:
            return str(sorted(archives, key=lambda f: f.stat().st_mtime, reverse=True)[0])

        # Fallback: .zip
        zips = list(base.glob("*.zip"))
        if zips:
            return str(sorted(zips, key=lambda f: f.stat().st_mtime, reverse=True)[0])

        raise FileNotFoundError(
            f"No .7z or .zip archive found in: {local_db_dir}\n"
            "Ensure the ERP backup was synced and is a compressed archive."
        )

    @staticmethod
    def _find_7zip_exe() -> str | None:
        """Look for 7z.exe in common install locations."""
        candidates = [
            r"C:\Program Files\7-Zip\7z.exe",
            r"C:\Program Files (x86)\7-Zip\7z.exe",
            shutil.which("7z"),
            shutil.which("7za"),
        ]
        for c in candidates:
            if c and Path(c).exists():
                return c
        return None



