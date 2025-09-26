# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['isaac_savefile_editor.py'],
    pathex=[],
    binaries=[],
    datas=[('ui_completion_marks.csv', '.'), ('ui_secrets.csv', '.'), ('ui_items.csv', '.'), ('ui_challenges.csv', '.'), ('language', 'language'), ('i18n', 'i18n'), ('icons/items', 'icons/items'), ('icons/trinkets', 'icons/trinkets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='isaac_savefile_editor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='isaac_savefile_editor',
)
