# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['terabox_gui.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('icon', 'icon'),
        ('aria2', 'aria2'),  # Sertakan folder aria2
    ],
    hiddenimports=[
        'sv_ttk',
        'cairosvg',
        'PIL',
        'rich',
        'aria2p',
        'requests',
        'json',
        'threading',
        'queue',
        'subprocess'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

# Tambahkan file aria2c.exe ke binaries jika ada
if os.path.exists('aria2/aria2c.exe'):
    a.binaries += [('aria2/aria2c.exe', 'aria2/aria2c.exe', 'BINARY')]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Trauso',
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
    icon='icon/box.ico'
)

# Create the COLLECT bundle
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=['aria2c.exe'],
    name='Trauso'
)
