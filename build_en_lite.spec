# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

a = Analysis(
    ['app_en_lite.py'],
    pathex=[],
    binaries=[],
    datas=[('icone.ico', '.')] + collect_data_files('customtkinter'),
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'keyboard', 'matplotlib', 'pandas', 'numpy', 'scipy', 'IPython',
        'pyautogui', 'pyscreeze', 'mouseinfo', 'pymsgbox', 'pytweening'
    ],
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='WorkTimeTracker_EN_Lite',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='icone.ico',
    disable_windowed_traceback=False,
)
