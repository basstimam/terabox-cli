import os
import shutil
import subprocess
from pathlib import Path
import sys
import zipfile
from io import BytesIO

def create_standalone():
    """Create standalone executable distribution."""
    print("Memulai pembuatan versi standalone...")
    
    # Install PyInstaller jika belum ada
    subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
    
    # Buat folder dist jika belum ada
    dist_dir = Path("dist")
    dist_dir.mkdir(exist_ok=True)
    
    # Buat folder untuk standalone
    standalone_dir = dist_dir / "Trauso"
    if standalone_dir.exists():
        shutil.rmtree(standalone_dir)
    standalone_dir.mkdir()
    
    # Copy folder aria2 terlebih dahulu
    aria2_source = Path("aria2")
    if aria2_source.exists():
        print("Menyalin folder aria2...")
        shutil.copytree(aria2_source, standalone_dir / "aria2")
    else:
        print("Warning: Folder aria2 tidak ditemukan!")
    
    # Siapkan file spec untuk PyInstaller dengan tambahan data files
    spec_content = """# -*- mode: python ; coding: utf-8 -*-

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
"""
    
    # Tulis file spec
    with open("TeraBox-Downloader.spec", "w") as f:
        f.write(spec_content)
    
    # Konversi SVG ke ICO untuk icon
    try:
        from cairosvg import svg2png
        from PIL import Image
        svg_path = Path("icon/box.svg")
        if svg_path.exists():
            # Konversi SVG ke PNG dengan berbagai ukuran
            sizes = [16, 32, 48, 64, 128, 256]
            images = []
            for size in sizes:
                png_data = svg2png(url=str(svg_path), output_width=size, output_height=size)
                img = Image.open(BytesIO(png_data))
                images.append(img)
            
            # Simpan sebagai ICO
            images[0].save(
                "icon/box.ico",
                format="ICO",
                sizes=[(size, size) for size in sizes],
                append_images=images[1:]
            )
            print("Icon berhasil dikonversi ke ICO")
    except Exception as e:
        print(f"Warning: Gagal membuat icon: {e}")
    
    # Jalankan PyInstaller
    print("Menjalankan PyInstaller...")
    subprocess.run(["pyinstaller", "TeraBox-Downloader.spec", "--clean"], check=True)
    
    # Buat folder downloads dan logs
    (standalone_dir / "downloads").mkdir(exist_ok=True)
    (standalone_dir / "logs").mkdir(exist_ok=True)
    (standalone_dir / "config").mkdir(exist_ok=True)
    
    # Buat README
    with open(standalone_dir / "README.txt", "w", encoding="utf-8") as f:
        f.write("""TeraBox Downloader (Standalone Version)

Aplikasi untuk mendownload file dari TeraBox dengan mudah dan cepat.

Cara Penggunaan:
1. Jalankan Trauso.exe
2. Paste URL TeraBox yang ingin didownload
3. Klik Process URL
4. Pilih file yang ingin didownload
5. Klik Download Selected atau Download All

Fitur:
- Interface modern dengan Sun Valley theme
- Download manager berbasis aria2 untuk kecepatan maksimal
- Mendukung download multiple file
- Riwayat download
- Pengaturan konfigurasi download
- Mode gelap/terang

Catatan:
- File akan didownload ke folder 'downloads'
- Log aplikasi tersimpan di folder 'logs'
- Pengaturan tersimpan di folder 'config'
- Pengaturan bisa diubah melalui menu Settings
- Folder 'aria2' berisi aria2c.exe yang digunakan untuk download

Persyaratan Sistem:
- Windows 10 atau lebih baru
- Koneksi internet

Kredit:
Icon oleh [Autor]
""")
    
    # Buat zip file
    zip_name = f"TeraBox-Downloader-Standalone-v{get_version()}.zip"
    with zipfile.ZipFile(dist_dir / zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(standalone_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, standalone_dir)
                zipf.write(file_path, arcname)
    
    print(f"Standalone distribution created at: {dist_dir / zip_name}")
    
    # Cleanup
    cleanup_files = ["TeraBox-Downloader.spec", "build"]
    for item in cleanup_files:
        if os.path.isfile(item):
            os.remove(item)
        elif os.path.isdir(item):
            shutil.rmtree(item)
    
    print("Build process completed!")

def create_portable():
    """Create portable distribution of TeraBox Downloader."""
    # Buat folder dist jika belum ada
    dist_dir = Path("dist")
    dist_dir.mkdir(exist_ok=True)
    
    # Buat folder untuk portable
    portable_dir = dist_dir / "TeraBox-Downloader-Portable"
    portable_dir.mkdir(exist_ok=True)
    
    # Copy file utama
    main_files = ["terabox_gui.py", "terabox_cli.py", "terabox1.py"]
    for file in main_files:
        shutil.copy2(file, portable_dir)
    
    # Copy folder aria2
    aria2_dir = portable_dir / "aria2"
    if Path("aria2").exists():
        shutil.copytree("aria2", aria2_dir, dirs_exist_ok=True)
    
    # Copy folder icon
    icon_dir = portable_dir / "icon"
    if Path("icon").exists():
        shutil.copytree("icon", icon_dir, dirs_exist_ok=True)
    
    # Buat folder config
    config_dir = portable_dir / "config"
    config_dir.mkdir(exist_ok=True)
    
    # Copy settings.json jika ada
    settings_file = Path("config/settings.json")
    if settings_file.exists():
        shutil.copy2(settings_file, config_dir)
    
    # Buat folder logs dan downloads
    (portable_dir / "logs").mkdir(exist_ok=True)
    (portable_dir / "downloads").mkdir(exist_ok=True)
    
    # Buat file requirements.txt
    requirements = [
        "sv-ttk==2.6.0",
        "cairosvg==2.7.1",
        "requests==2.31.0",
        "aria2p==0.11.3",
        "rich==13.7.0",
        "pillow==10.2.0"
    ]
    
    with open(portable_dir / "requirements.txt", "w") as f:
        f.write("\n".join(requirements))
    
    # Buat launcher script
    with open(portable_dir / "TeraBox-Downloader.bat", "w") as f:
        f.write('@echo off\n')
        f.write('echo Installing/Updating dependencies...\n')
        f.write('python -m pip install -r requirements.txt\n')
        f.write('echo Starting TeraBox Downloader...\n')
        f.write('python terabox_gui.py\n')
        f.write('pause\n')
    
    # Buat README
    with open(portable_dir / "README.md", "w") as f:
        f.write("""# TeraBox Downloader

Aplikasi untuk mendownload file dari TeraBox dengan mudah dan cepat.

## Cara Penggunaan

1. Pastikan Python 3.8 atau lebih baru sudah terinstall
2. Jalankan file `TeraBox-Downloader.bat`
3. Program akan menginstall dependencies yang dibutuhkan
4. Setelah itu program akan berjalan otomatis

## Fitur

- Interface modern dengan Sun Valley theme
- Download manager berbasis aria2 untuk kecepatan maksimal
- Mendukung download multiple file
- Riwayat download
- Pengaturan konfigurasi download
- Mode gelap/terang

## Catatan

- Folder `downloads` adalah lokasi default untuk menyimpan file
- Folder `logs` berisi log aplikasi
- Folder `config` menyimpan pengaturan dan trackers
- File konfigurasi bisa diubah di menu Settings

## Persyaratan Sistem

- Windows 10 atau lebih baru
- Python 3.8+
- Koneksi internet

## Kredit

Icon oleh [Autor]
""")
    
    # Buat zip file
    zip_name = f"TeraBox-Downloader-Portable-v{get_version()}.zip"
    with zipfile.ZipFile(dist_dir / zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(portable_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, portable_dir)
                zipf.write(file_path, arcname)
    
    print(f"Portable distribution created at: {dist_dir / zip_name}")

def get_version():
    """Get version from terabox_gui.py."""
    try:
        with open("terabox_gui.py", "r") as f:
            content = f.read()
            # Cari versi dalam komentar atau variabel
            # TODO: Implementasikan cara mendapatkan versi yang sesuai
            return "1.0.0"
    except:
        return "1.0.0"

if __name__ == "__main__":
    # Tanya user mau build versi apa
    print("Pilih jenis distribusi yang ingin dibuat:")
    print("1. Portable (Membutuhkan Python)")
    print("2. Standalone (Tidak membutuhkan Python)")
    
    choice = input("Pilihan (1/2): ").strip()
    
    if choice == "1":
        create_portable()
    elif choice == "2":
        create_standalone()
    else:
        print("Pilihan tidak valid!") 