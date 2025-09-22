import os
import re
import shutil
import subprocess
from pathlib import Path
import sys
import zipfile
from io import BytesIO

def create_standalone():
    """Create standalone executable distribution."""
    print("Memulai pembuatan versi standalone...")
    
    # Ensure pip is available
    print("Memastikan pip tersedia...")
    subprocess.run([sys.executable, "-m", "ensurepip", "--upgrade"], check=True)

    # Uninstall obsolete 'typing' package if it exists
    print("Menghapus paket 'typing' yang usang jika ada...")
    subprocess.run([sys.executable, "-m", "pip", "uninstall", "typing", "-y"], check=False)

    # Uninstall obsolete 'pathlib' package if it exists
    print("Menghapus paket 'pathlib' yang usang jika ada...")
    subprocess.run([sys.executable, "-m", "pip", "uninstall", "pathlib", "-y"], check=False)

    # Define and install build dependencies
    build_deps = [
        "pyinstaller>=5.13.0", "sv-ttk>=2.6.0", "cairosvg>=2.7.0", 
        "pillow>=10.0.0", "rich>=13.0.0", "aria2p>=0.12.0", "requests>=2.28.0"
    ]
    print("Menginstall/memperbarui dependensi untuk build...")
    subprocess.run([sys.executable, "-m", "pip", "install", *build_deps], check=True)
    
    # Buat folder dist jika belum ada
    dist_dir = Path("dist")
    dist_dir.mkdir(exist_ok=True)
    
    # Buat folder untuk standalone
    standalone_dir = dist_dir / "TeraBox-Downloader"
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
    
    # Siapkan file spec untuk PyInstaller dengan optimasi maksimal
    spec_content = """# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['terabox_gui.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('icon', 'icon'),
        ('aria2', 'aria2'),
    ],
    hiddenimports=[
        'sv_ttk',
        'cairosvg',
        'PIL._tkinter_finder',
        'PIL.Image',
        'PIL.ImageTk', 
        'rich.console',
        'rich.progress',
        'aria2p.api',
        'aria2p.client',
        'requests.adapters',
        'requests.packages.urllib3',
        'workers',
        'terabox_cli',
        'concurrent.futures',
        'queue',
        'threading',
        'json',
        'pathlib',
        'tkinter.ttk',
        'tkinter.messagebox',
        'tkinter.filedialog'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'numpy', 'scipy', 'pandas', 'pytest', 'IPython',
        'jupyter', 'notebook', 'qtpy', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6',
        'tornado', 'zmq', 'sqlalchemy', 'django', 'flask', 'fastapi',
        'tensorflow', 'torch', 'sklearn', 'cv2', 'selenium'
    ],
    cipher=block_cipher,
    noarchive=False,
)

# Remove unnecessary modules to reduce size
a.binaries = [x for x in a.binaries if not any(excluded in x[0].lower() for excluded in [
    'qt', 'tcl', 'tk8', '_ssl', 'libssl', 'libcrypto'
])]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TeraBox-Downloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon/box.ico'
)

# Create the COLLECT bundle with UPX compression
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=True,
    upx=True,
    upx_exclude=['aria2c.exe', 'vcruntime140.dll'],
    name='TeraBox-Downloader'
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
    
    # Jalankan PyInstaller dengan optimasi maksimal
    print("Menjalankan PyInstaller dengan optimasi maksimal...")
    pyinstaller_cmd = [
        "pyinstaller", 
        "TeraBox-Downloader.spec", 
        "--clean",
        "--optimize=2",  # Maximum optimization
        "--strip",       # Strip debug symbols
        "--noupx" if os.name != 'nt' else "--upx-dir=upx"  # Conditional UPX usage
    ]
    
    # Remove --noupx if on Windows and UPX is available
    if os.name == 'nt':
        pyinstaller_cmd = [cmd for cmd in pyinstaller_cmd if cmd != "--noupx"]
    
    subprocess.run(pyinstaller_cmd, check=True)
    
    # Buat folder downloads dan logs
    (standalone_dir / "downloads").mkdir(exist_ok=True)
    (standalone_dir / "logs").mkdir(exist_ok=True)
    (standalone_dir / "config").mkdir(exist_ok=True)
    
    # Buat README dengan informasi yang lebih lengkap
    with open(standalone_dir / "README.txt", "w", encoding="utf-8") as f:
        f.write(f"""TeraBox Downloader v{get_version()} (Standalone Version)

Aplikasi untuk mendownload file dari TeraBox dengan mudah dan cepat.
Menggunakan workers.dev API dengan endpoint prioritas: terabox.hnn.workers.dev

Cara Penggunaan:
1. Jalankan TeraBox-Downloader.exe
2. Paste URL TeraBox yang ingin didownload (format: https://terabox.com/s/XXXXX)
3. Klik Process URL
4. Pilih file yang ingin didownload
5. Klik Download Selected atau Download All

Fitur:
- Interface modern dengan Sun Valley theme
- Download manager berbasis aria2 untuk kecepatan maksimal
- Mendukung download multiple file secara bersamaan
- Riwayat download dengan tracking status
- Pengaturan konfigurasi download yang fleksibel
- Mode gelap/terang dengan toggle otomatis
- Automatic retry mechanism untuk failed downloads
- Compression handling untuk response yang optimal

Konfigurasi:
- File akan didownload ke folder 'downloads'
- Log aplikasi tersimpan di folder 'logs' 
- Pengaturan tersimpan di folder 'config'
- Trackers aria2 akan diupdate otomatis
- Folder 'aria2' berisi aria2c.exe untuk download engine

Persyaratan Sistem:
- Windows 10 atau lebih baru (64-bit)
- Minimal 4GB RAM
- Koneksi internet stabil
- 100MB ruang disk kosong

Performa:
- Executable size dioptimasi dengan UPX compression
- Startup time < 3 detik pada hardware standar
- Memory usage < 150MB saat idle
- Mendukung download hingga 16 koneksi paralel

Troubleshooting:
- Jika download gagal, coba refresh URL dan ulangi
- Untuk error KVTOKENS, tunggu beberapa menit lalu coba lagi
- Pastikan firewall tidak memblokir aplikasi
- Check log files di folder 'logs' untuk detail error

Kredit:
- Developed by Team
- Icon design by [Author]
- Built with PyInstaller {subprocess.check_output(['pyinstaller', '--version'], text=True).strip()}
""")
    
    # Buat zip file dengan kompresi maksimal
    zip_name = f"TeraBox-Downloader-Standalone-v{get_version()}.zip"
    print(f"Membuat arsip: {zip_name}...")
    with zipfile.ZipFile(dist_dir / zip_name, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zipf:
        for root, dirs, files in os.walk(standalone_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, standalone_dir)
                zipf.write(file_path, arcname)
                
    # Calculate and display file sizes
    zip_size = (dist_dir / zip_name).stat().st_size
    print(f"\n📦 Build Summary:")
    print(f"   Zip file: {zip_name}")
    print(f"   Size: {zip_size / (1024*1024):.1f} MB")
    print(f"   Location: {dist_dir / zip_name}")
    
    # Cleanup with better error handling
    cleanup_files = ["TeraBox-Downloader.spec", "build"]
    for item in cleanup_files:
        try:
            if os.path.isfile(item):
                os.remove(item)
                print(f"Cleaned up: {item}")
            elif os.path.isdir(item):
                shutil.rmtree(item)
                print(f"Cleaned up directory: {item}")
        except Exception as e:
            print(f"Warning: Could not clean up {item}: {e}")
    
    print("\n✅ Build process completed successfully!")
    print(f"\n🚀 Ready to distribute: {dist_dir / zip_name}")

def create_portable():
    """Create portable distribution of TeraBox Downloader."""
    # Buat folder dist jika belum ada
    dist_dir = Path("dist")
    dist_dir.mkdir(exist_ok=True)
    
    # Buat folder untuk portable
    portable_dir = dist_dir / "TeraBox-Downloader-Portable"
    portable_dir.mkdir(exist_ok=True)
    
    # Copy file utama
    main_files = ["terabox_gui.py", "terabox_cli.py", "terabox1.py", "build.py", "workers.py"]
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
        
    # Copy creds.json jika ada
    creds_file = Path("config/creds.json")
    if creds_file.exists():
        shutil.copy2(creds_file, config_dir)
    
    # Buat folder logs dan downloads
    (portable_dir / "logs").mkdir(exist_ok=True)
    (portable_dir / "downloads").mkdir(exist_ok=True)
    (portable_dir / "url_logs").mkdir(exist_ok=True)
    
    # Buat requirements.txt dengan versi yang lebih spesifik
    requirements = [
        "sv-ttk>=2.6.0,<3.0.0",
        "cairosvg>=2.7.0,<3.0.0", 
        "requests>=2.28.0,<3.0.0",
        "aria2p>=0.12.0,<1.0.0",
        "rich>=13.0.0,<14.0.0",
        "pillow>=10.0.0,<11.0.0"
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
    with open(portable_dir / "README.md", "w", encoding="utf-8") as f:
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
        with open("terabox_gui.py", "r", encoding="utf-8") as f:
            content = f.read()
            match = re.search(r"def get_version\s*\(self\):\s*.*?return\s+[\"'](.*?)[\"']", content, re.DOTALL)
            if match:
                return match.group(1)
    except Exception as e:
        print(f"Gagal mendapatkan versi: {e}")
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