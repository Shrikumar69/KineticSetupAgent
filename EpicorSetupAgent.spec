# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for EpicorSetupAgent
# Run:  pyinstaller EpicorSetupAgent.spec

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        # Bundle config template so first-run copies it next to the .exe
        ('config/config.yaml', 'config'),
    ],
    hiddenimports=[
        'py7zr',
        'py7zr.archiveinfo',
        'py7zr.compressor',
        'py7zr.helpers',
        'pyodbc',
        'yaml',
        'rich',
        'rich.console',
        'rich.panel',
        'rich.table',
        'colorama',
        'psutil',
        'agent.prerequisites',
        'agent.file_sync',
        'agent.extractor',
        'agent.db_restore',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='EpicorSetupAgent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,          # Keep console window so progress is visible
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

