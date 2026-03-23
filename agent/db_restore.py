"""
db_restore.py
Restores the ERP and ICECommon databases into the local SQL Server 2022 instance.

Restore order:
  1. E10QAGolden_full_dmp  -> database: E10QAGolden
  2. ICECommon_full_dmp    -> database: ICECommon

Strategy:
  - Uses pyodbc with Windows Authentication (default) or SQL auth.
  - Calls RESTORE FILELISTONLY to discover logical file names dynamically.
  - Queries SQL Server for its default Data/Log paths.
  - Falls back to sqlcmd if pyodbc ODBC driver is unavailable.
"""

import os
import logging
import subprocess
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


class DatabaseRestoreAgent:
    def __init__(self, config: dict):
        sql_cfg = config.get("sql_server", {})
        loc_cfg = config.get("local", {})

        self.instance     = sql_cfg.get("instance", "localhost")
        self.auth_mode    = sql_cfg.get("auth_mode", "windows")
        self.sql_user     = sql_cfg.get("sql_user", "")
        self.sql_password = sql_cfg.get("sql_password", "")
        self.erp_db_name  = sql_cfg.get("erp_db_name", "E10QAGolden")
        self.ice_db_name  = sql_cfg.get("common_db_name", "ICECommon")
        self.data_path    = sql_cfg.get("data_path", "").strip()
        self.log_path     = sql_cfg.get("log_path", "").strip()

        self.erp_db_local    = loc_cfg.get("erp_db_dest", r"C:\ErpCurrent\DB")
        self.common_db_local = loc_cfg.get("common_db_dest", r"C:\ErpCurrent\CommonDB")

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    def restore_erp_db(self):
        """Restore E10QAGolden_full_dmp -> SQL Server database E10QAGolden."""
        logger.info("=== Restoring ERP Database (E10QAGolden) ===")
        backup_path = self._find_backup_file(self.erp_db_local, "E10QAGolden_full_dmp")
        self._restore_database(self.erp_db_name, backup_path)

    def restore_common_db(self):
        """Restore ICECommon_full_dmp -> SQL Server database ICECommon."""
        logger.info("=== Restoring ICECommon Database ===")
        backup_path = self._find_backup_file(self.common_db_local, "ICECommon_full_dmp")
        self._restore_database(self.ice_db_name, backup_path)

    # ------------------------------------------------------------------
    # Core restore
    # ------------------------------------------------------------------

    def _restore_database(self, db_name: str, backup_path: str):
        logger.info(f"Target database : {db_name}")
        logger.info(f"Backup file     : {backup_path}")
        try:
            import pyodbc
            self._restore_via_pyodbc(db_name, backup_path)
        except ImportError:
            logger.warning("pyodbc not available - falling back to sqlcmd.")
            self._restore_via_sqlcmd(db_name, backup_path)

    # ------------------------------------------------------------------
    # pyodbc path
    # ------------------------------------------------------------------

    def _restore_via_pyodbc(self, db_name: str, backup_path: str):
        import pyodbc
        conn_str = self._build_connection_string()
        with pyodbc.connect(conn_str, autocommit=True, timeout=30) as conn:
            cursor = conn.cursor()
            data_dir, log_dir = self._get_default_sql_paths(cursor)
            file_list = self._get_file_list(cursor, backup_path)
            move_clauses = self._build_move_clauses(file_list, db_name, data_dir, log_dir)

            restore_sql = (
                f"RESTORE DATABASE [{db_name}]\n"
                f"FROM DISK = N'{backup_path}'\n"
                f"WITH\n"
                f"{move_clauses},\n"
                f"    REPLACE,\n"
                f"    STATS = 10"
            )
            logger.info("Executing RESTORE DATABASE ... (this may take several minutes)")
            logger.debug(restore_sql)
            cursor.execute(restore_sql)
            while cursor.nextset():
                pass

        logger.info(f"[OK] Database '{db_name}' restored successfully via pyodbc.")

    def _get_file_list(self, cursor, backup_path: str) -> list:
        cursor.execute(f"RESTORE FILELISTONLY FROM DISK = N'{backup_path}'")
        rows = cursor.fetchall()
        if not rows:
            raise RuntimeError(f"RESTORE FILELISTONLY returned no rows for: {backup_path}")
        cols = [desc[0] for desc in cursor.description]
        file_list = [dict(zip(cols, row)) for row in rows]
        logger.debug(f"Logical files in backup: {[f['LogicalName'] for f in file_list]}")
        return file_list

    def _get_default_sql_paths(self, cursor) -> tuple:
        if self.data_path and self.log_path:
            return self.data_path, self.log_path
        cursor.execute("""
            SELECT
                SERVERPROPERTY('InstanceDefaultDataPath') AS DataPath,
                SERVERPROPERTY('InstanceDefaultLogPath')  AS LogPath
        """)
        row = cursor.fetchone()
        data_dir = (row[0] or "").rstrip("\\")
        log_dir  = (row[1] or "").rstrip("\\")
        if not data_dir:
            data_dir = r"C:\Program Files\Microsoft SQL Server\MSSQL16.MSSQLSERVER\MSSQL\DATA"
        if not log_dir:
            log_dir = data_dir
        logger.debug(f"SQL data path: {data_dir}")
        logger.debug(f"SQL log  path: {log_dir}")
        return data_dir, log_dir

    @staticmethod
    def _build_move_clauses(file_list: list, db_name: str, data_dir: str, log_dir: str) -> str:
        parts = []
        data_counter = 0
        for f in file_list:
            logical = f["LogicalName"]
            ftype = (f.get("Type") or "D").upper()
            if ftype == "L":
                physical = os.path.join(log_dir, f"{db_name}_log.ldf")
            else:
                if data_counter == 0:
                    physical = os.path.join(data_dir, f"{db_name}.mdf")
                else:
                    physical = os.path.join(data_dir, f"{db_name}_{data_counter}.ndf")
                data_counter += 1
            parts.append(f"    MOVE N'{logical}' TO N'{physical}'")
        return ",\n".join(parts)

    # ------------------------------------------------------------------
    # sqlcmd fallback
    # ------------------------------------------------------------------

    def _restore_via_sqlcmd(self, db_name: str, backup_path: str):
        if not shutil.which("sqlcmd"):
            raise EnvironmentError(
                "sqlcmd not found in PATH.\n"
                "Install SQL Server Management Studio (SSMS) or SQL Server command-line tools."
            )
        sql = (
            f"RESTORE DATABASE [{db_name}] "
            f"FROM DISK = N'{backup_path}' "
            f"WITH REPLACE, STATS = 10;"
        )
        cmd = ["sqlcmd", "-S", self.instance, "-Q", sql]
        if self.auth_mode == "sql":
            cmd += ["-U", self.sql_user, "-P", self.sql_password]
        else:
            cmd += ["-E"]

        logger.info(f"Running sqlcmd restore for [{db_name}] ...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0 or "Error" in result.stdout:
            raise RuntimeError(
                f"sqlcmd restore failed for [{db_name}].\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            )
        logger.info(f"[OK] Database '{db_name}' restored successfully via sqlcmd.")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_connection_string(self) -> str:
        if self.auth_mode == "sql":
            return (
                f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                f"SERVER={self.instance};DATABASE=master;"
                f"UID={self.sql_user};PWD={self.sql_password};"
            )
        return (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={self.instance};DATABASE=master;"
            f"Trusted_Connection=yes;"
        )

    @staticmethod
    def _find_backup_file(local_dest_dir: str, expected_name: str) -> str:
        """Locate the backup file inside the local destination directory."""
        candidate = os.path.join(local_dest_dir, expected_name)
        if os.path.exists(candidate):
            if os.path.isdir(candidate):
                bak_files = list(Path(candidate).rglob("*.bak"))
                if bak_files:
                    return str(bak_files[0])
                all_files = [f for f in Path(candidate).iterdir() if f.is_file()]
                if all_files:
                    return str(sorted(all_files, key=lambda f: f.stat().st_size, reverse=True)[0])
            return candidate

        # Fallback: glob for any matching file
        local_dir = Path(local_dest_dir)
        if local_dir.exists():
            matches = list(local_dir.glob(f"{expected_name}*"))
            if matches:
                return str(matches[0])

        raise FileNotFoundError(
            f"Backup '{expected_name}' not found in '{local_dest_dir}'.\n"
            f"Run the sync step first (--sync or step 1)."
        )

