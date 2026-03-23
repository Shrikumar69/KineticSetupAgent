"""
prerequisites.py
Checks system prerequisites before running the Epicor Kinetic setup.
"""

import os
import re
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
            import psutil
            total_ram_gb = psutil.virtual_memory().total / (1024 ** 3)
            ok = total_ram_gb >= self.required_ram_gb
            self._record("RAM", ok,
                         f"{total_ram_gb:.1f} GB total (required: {self.required_ram_gb} GB)")
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
            # Registry returns hex value e.g. "0x82405" — parse it numerically
            match = re.search(r'0x([0-9a-fA-F]+)', result.stdout)
            if match:
                release = int(match.group(1), 16)
                # .NET 4.8 = 528040, .NET 4.8.1 = 533320, .NET 4.8.2+ = higher
                if release >= 528040:
                    self._record(f".NET Framework {self.required_dotnet}", True,
                                 f"Installed (release key: {release} / 0x{release:X})")
                    return True
                else:
                    self._record(f".NET Framework {self.required_dotnet}", False,
                                 f"Release key {release} is below required 528040 (.NET 4.8)")
                    return False
            # Fallback: not found
            self._record(f".NET Framework {self.required_dotnet}", False,
                         "Registry key not found — .NET 4.8 may not be installed")
            return False
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
        # Method 1: registry key (works without elevation, fastest)
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\InetStp"
            )
            install_path, _ = winreg.QueryValueEx(key, "InstallPath")
            winreg.CloseKey(key)
            if install_path:
                self._record("IIS (Web Server Role)", True,
                             f"Installed at: {install_path}")
                return True
        except FileNotFoundError:
            pass  # Registry key absent → not installed
        except Exception:
            pass  # Fall through to next method

        # Method 2: W3SVC service exists
        try:
            result = subprocess.run(
                ["sc", "query", "W3SVC"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                self._record("IIS (Web Server Role)", True, "W3SVC service found")
                return True
        except Exception:
            pass

        # Method 3: PowerShell Get-WindowsOptionalFeature (may need elevation)
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command",
                 "(Get-WindowsOptionalFeature -Online -FeatureName IIS-WebServerRole).State"],
                capture_output=True, text=True, timeout=30
            )
            if "Enabled" in result.stdout:
                self._record("IIS (Web Server Role)", True, "Enabled")
                return True
        except Exception:
            pass

        self._record("IIS (Web Server Role)", False,
                     "Not detected — run: Enable-WindowsOptionalFeature -Online -FeatureName IIS-WebServerRole")
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

