"""
prerequisites.py
Checks system prerequisites before running the Epicor Kinetic setup.
"""

import os
import platform
import shutil
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class PrerequisiteChecker:
    def __init__(self, config: dict):
        self.cfg = config.get("prerequisites", {})
        self.required_ram_gb   = self.cfg.get("required_ram_gb", 16)
        self.required_disk_gb  = self.cfg.get("required_disk_gb", 100)
        self.required_dotnet   = self.cfg.get("required_dotnet_version", "4.8")
        self.results: list[dict] = []

    # ------------------------------------------------------------------
    def run_all(self) -> bool:
        """Run all checks. Returns True if all pass."""
        checks = [
            self._check_os,
            self._check_ram,
            self._check_disk,
            self._check_dotnet,
            self._check_sql_server_tools,
            self._check_iis,
            self._check_powershell,
        ]
        all_pass = True
        for fn in checks:
            ok = fn()
            if not ok:
                all_pass = False
        return all_pass

    # ------------------------------------------------------------------
    def _record(self, name: str, status: bool, detail: str):
        icon = "✅" if status else "❌"
        self.results.append({"name": name, "status": status, "detail": detail, "icon": icon})
        level = logging.INFO if status else logging.WARNING
        logger.log(level, f"[{icon}] {name}: {detail}")

    # ------------------------------------------------------------------
    def _check_os(self) -> bool:
        os_info = platform.platform()
        ok = platform.system() == "Windows"
        self._record("Operating System", ok, os_info)
        return ok

    def _check_ram(self) -> bool:
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            c_ulong = ctypes.c_ulong

            class MEMORYSTATUS(ctypes.Structure):
                _fields_ = [
                    ("dwLength", c_ulong),
                    ("dwMemoryLoad", c_ulong),
                    ("dwTotalPhys", ctypes.c_ulonglong),
                    ("dwAvailPhys", ctypes.c_ulonglong),
                    ("dwTotalPageFile", ctypes.c_ulonglong),
                    ("dwAvailPageFile", ctypes.c_ulonglong),
                    ("dwTotalVirtual", ctypes.c_ulonglong),
                    ("dwAvailVirtual", ctypes.c_ulonglong),
                ]

            memory_status = MEMORYSTATUS()
            memory_status.dwLength = ctypes.sizeof(MEMORYSTATUS)
            kernel32.GlobalMemoryStatusEx(ctypes.byref(memory_status))
            total_ram_gb = memory_status.dwTotalPhys / (1024 ** 3)
            ok = total_ram_gb >= self.required_ram_gb
            self._record("RAM", ok, f"{total_ram_gb:.1f} GB available (required: {self.required_ram_gb} GB)")
            return ok
        except Exception as e:
            self._record("RAM", False, f"Could not detect RAM: {e}")
            return False

    def _check_disk(self) -> bool:
        try:
            total, used, free = shutil.disk_usage("C:\\")
            free_gb = free / (1024 ** 3)
            ok = free_gb >= self.required_disk_gb
            self._record("Disk Space (C:)", ok,
                         f"{free_gb:.1f} GB free (required: {self.required_disk_gb} GB)")
            return ok
        except Exception as e:
            self._record("Disk Space", False, f"Error: {e}")
            return False

    def _check_dotnet(self) -> bool:
        try:
            result = subprocess.run(
                ["reg", "query",
                 r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full",
                 "/v", "Release"],
                capture_output=True, text=True
            )
            # .NET 4.8 release key >= 528040
            if "528040" in result.stdout or any(
                str(r) in result.stdout for r in range(528040, 600000)
            ):
                self._record(".NET Framework 4.8+", True, "Installed")
                return True
            # Try to find any release key
            lines = [l for l in result.stdout.splitlines() if "Release" in l]
            detail = lines[0].strip() if lines else result.stdout.strip() or "Not found"
            ok = False
            self._record(f".NET Framework {self.required_dotnet}", ok, detail)
            return ok
        except Exception as e:
            self._record(".NET Framework", False, f"Error: {e}")
            return False

    def _check_sql_server_tools(self) -> bool:
        sqlcmd = shutil.which("sqlcmd")
        ok = sqlcmd is not None
        self._record("SQL Server (sqlcmd)", ok,
                     sqlcmd if ok else "sqlcmd not found in PATH — install SQL Server or SSMS")
        return ok

    def _check_iis(self) -> bool:
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-WindowsOptionalFeature -Online -FeatureName IIS-WebServerRole | Select-Object -ExpandProperty State"],
                capture_output=True, text=True, timeout=30
            )
            ok = "Enabled" in result.stdout
            self._record("IIS (Web Server Role)", ok,
                         "Enabled" if ok else "Not enabled — run: Enable-WindowsOptionalFeature -Online -FeatureName IIS-WebServerRole")
            return ok
        except Exception as e:
            self._record("IIS", False, f"Could not check: {e}")
            return False

    def _check_powershell(self) -> bool:
        try:
            result = subprocess.run(
                ["powershell", "-Command", "$PSVersionTable.PSVersion.Major"],
                capture_output=True, text=True, timeout=10
            )
            version = result.stdout.strip()
            ok = int(version) >= 5 if version.isdigit() else False
            self._record("PowerShell 5+", ok, f"Version {version}" if version else "Not found")
            return ok
        except Exception as e:
            self._record("PowerShell", False, f"Error: {e}")
            return False

