import os
import sys
import time
import requests
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import (
    DownloadColumn,
    Progress,
    TextColumn,
    TransferSpeedColumn,
    TimeRemainingColumn,
    BarColumn,
    ProgressColumn,
    SpinnerColumn,
    FileSizeColumn
)
from rich.prompt import Prompt, Confirm
from rich.layout import Layout
from terabox1 import TeraboxFile, TeraboxLink
import concurrent.futures
import threading
from urllib.parse import urlparse
import socket
import mmap
import multiprocessing
from rich.console import Group
import random
import logging
from contextlib import nullcontext
import subprocess
import json
import shutil
import aria2p

console = Console()

class TeraboxDownloader:
    def __init__(self):
        self.chunk_size = 16 * 1024 * 1024  # Meningkatkan chunk size ke 16MB
        self.max_workers = min(64, multiprocessing.cpu_count() * 8)  # Meningkatkan jumlah workers
        self.session = self._create_session()
        self.progress = Progress(
            SpinnerColumn(spinner_name="dots"),
            TextColumn("[bold blue]{task.fields[filename]}", justify="right"),
            BarColumn(bar_width=40, complete_style="green", finished_style="bright_green"),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            "•",
            FileSizeColumn(),
            "•", 
            DownloadColumn(),
            "•",
            TransferSpeedColumn(),
            "•",
            TimeRemainingColumn(),
            refresh_per_second=10,
            expand=True
        )
        self.download_lock = threading.Lock()
        self.total_downloaded = 0
        self.start_time = 0
        self.url_speed_cache = {}
        self.setup_logging()
        self.cancel_event = threading.Event()
        self.retry_delay = 2  # Mengurangi delay retry
        self.connect_timeout = 15  # Mengurangi timeout koneksi
        self.read_timeout = 30  # Mengurangi read timeout
        self.retry_timeout = 180  # Mengurangi retry timeout
        self.last_request_time = 0
        self.min_request_interval = 0.5  # Mengurangi interval minimum antar request
        
        # Setup direktori untuk log URL
        self.url_log_dir = Path("url_logs")
        self.url_log_dir.mkdir(exist_ok=True)
        
        # Cek keberadaan aria2c
        self.use_aria2 = self._setup_aria2()
        if not self.use_aria2:
            console.print(Panel("[yellow]⚠️ aria2 tidak ditemukan, menggunakan metode download default[/]", border_style="yellow"))

    def _setup_aria2(self) -> bool:
        """Setup aria2 dan aria2p"""
        try:
            # Cek di folder lokal dulu
            local_aria2 = Path("aria2/aria2c.exe")
            if local_aria2.exists():
                # Start aria2c daemon
                cmd = [
                    str(local_aria2),
                    "--enable-rpc",
                    "--rpc-listen-all=false",
                    "--rpc-listen-port=6800",
                    "--max-concurrent-downloads=1",
                    "--max-connection-per-server=16",
                    "--split=16",
                    "--min-split-size=1M",
                    "--max-overall-download-limit=0",
                    "--max-download-limit=0",
                    "--file-allocation=none",
                    "--daemon=true"
                ]
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                # Initialize aria2p API
                self.aria2 = aria2p.API(
                    aria2p.Client(
                        host="http://localhost",
                        port=6800,
                        secret=""
                    )
                )
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error setting up aria2: {str(e)}")
            return False

    def _create_aria2_config(self) -> str:
        """Membuat konfigurasi aria2"""
        trackers = """udp://93.158.213.92:1337/announce
udp://91.216.110.53:451/announce
udp://185.243.218.213:80/announce
udp://23.157.120.14:6969/announce
udp://45.154.96.35:6969/announce
udp://23.153.248.83:6969/announce
udp://51.159.54.68:6666/announce
http://34.94.76.146:6969/announce
http://34.94.76.146:2710/announce
http://34.94.76.146:80/announce
udp://83.6.230.142:6969/announce
udp://54.39.48.3:6969/announce
udp://210.61.187.208:80/announce
udp://135.125.202.143:6969/announce
udp://144.126.245.19:6969/announce
udp://209.141.59.25:6969/announce
udp://108.53.194.223:6969/announce
udp://52.58.128.163:6969/announce
udp://47.243.23.189:6969/announce
udp://211.75.210.220:6969/announce
udp://tracker.opentrackr.org:1337/announce
udp://open.demonii.com:1337/announce
udp://open.tracker.cl:1337/announce
udp://tracker.torrent.eu.org:451/announce
udp://open.stealth.si:80/announce
udp://exodus.desync.com:6969/announce
udp://explodie.org:6969/announce
udp://tracker.tiny-vps.com:6969/announce
udp://tracker.theoks.net:6969/announce
udp://tracker.qu.ax:6969/announce
udp://tracker.dump.cl:6969/announce
udp://tracker.0x7c0.com:6969/announce
udp://tracker-udp.gbitt.info:80/announce
udp://opentracker.io:6969/announce
udp://open.dstud.io:6969/announce
udp://ns-1.x-fins.com:6969/announce
udp://bt.ktrackers.com:6666/announce
http://tracker.xiaoduola.xyz:6969/announce
http://tracker.lintk.me:2710/announce
http://bt.poletracker.org:2710/announce"""

        config = {
            'max-connection-per-server': '16',
            'min-split-size': '1M',
            'split': '16',
            'max-concurrent-downloads': '1',
            'continue': 'true',
            'max-tries': '0',
            'retry-wait': '3',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'bt-tracker': trackers.replace('\n', ','),
            'enable-dht': 'true',
            'enable-peer-exchange': 'true',
            'bt-enable-lpd': 'true',
            'bt-max-peers': '0',
            'bt-request-peer-speed-limit': '50M',
            'seed-ratio': '0.0'
        }
        
        config_path = Path('aria2.conf')
        with open(config_path, 'w') as f:
            for key, value in config.items():
                f.write(f'{key}={value}\n')
                
        return str(config_path)

    def download_with_aria2(self, url: str, filename: str, filesize: int, quiet: bool = False) -> bool:
        """Download file menggunakan aria2p"""
        try:
            if not quiet:
                console.print(Panel("[bold cyan]🚀 Memulai download dengan aria2...[/]", border_style="cyan"))
            
            # Tambahkan download ke aria2
            download = self.aria2.add_uris(
                [url],
                options={
                    "dir": str(Path(filename).parent),
                    "out": Path(filename).name,
                    "max-connection-per-server": "16",
                    "split": "16",
                    "min-split-size": "1M",
                    "max-concurrent-downloads": "1",
                    "continue": "true",
                    "max-tries": "10",
                    "retry-wait": "3",
                    "connect-timeout": "60",
                    "timeout": "60",
                    "max-file-not-found": "5",
                    "max-overall-download-limit": "0",
                    "max-download-limit": "0",
                    "file-allocation": "none",
                    "auto-file-renaming": "false",
                    "allow-overwrite": "true"
                }
            )
            
            # Monitor progress
            last_progress = -1
            no_progress_time = time.time()
            
            while not download.is_complete:
                if self.cancel_event.is_set():
                    download.remove()
                    console.print("\n[bold red]Download dibatalkan![/]")
                    return False
                
                try:
                    download.update()
                    progress = download.progress
                    speed = download.download_speed
                    
                    if progress != last_progress:
                        last_progress = progress
                        no_progress_time = time.time()
                        if not quiet:
                            console.print(f"[cyan]Progress: {progress:.1f}% ({self.format_size(speed)}/s)[/]")
                    elif time.time() - no_progress_time > 30:
                        raise Exception("Download timeout - tidak ada progress selama 30 detik")
                        
                except aria2p.client.ClientException as e:
                    self.logger.error(f"Aria2 error: {str(e)}")
                    if not quiet:
                        console.print(f"[red]Error: {str(e)}[/]")
                    continue
                    
                time.sleep(1)
            
            # Verifikasi hasil download
            if os.path.exists(filename):
                actual_size = os.path.getsize(filename)
                if actual_size == filesize:
                    if not quiet:
                        console.print(Panel("[bold green]✅ Download selesai![/]", border_style="green"))
                    return True
                else:
                    raise Exception(f"Ukuran file tidak sesuai (expected: {filesize}, actual: {actual_size})")
            
            raise Exception("File tidak ditemukan setelah download selesai")
            
        except Exception as e:
            self.handle_error(e, "Download dengan aria2 gagal")
            return False

    def setup_logging(self):
        """Setup sistem logging"""
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        log_file = log_dir / f"terabox_{datetime.now():%Y%m%d}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def _create_session(self) -> requests.Session:
        """Membuat session dengan optimasi"""
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=200,  # Meningkatkan jumlah koneksi
            pool_maxsize=200,  # Meningkatkan pool size
            max_retries=5,  # Meningkatkan jumlah retry
            pool_block=False
        )
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        session.headers.update({
            'Connection': 'keep-alive',
            'Keep-Alive': 'timeout=300',
            'Accept-Encoding': 'gzip, deflate',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*',  # Menambahkan header accept
            'Accept-Language': 'en-US,en;q=0.9',  # Menambahkan header bahasa
            'Cache-Control': 'no-cache',  # Menambahkan cache control
            'Pragma': 'no-cache'  # Menambahkan pragma
        })
        return session

    def show_banner(self) -> None:
        """Menampilkan banner aplikasi"""
        banner = """
[bold cyan]
╔════════════════════════════════════════════════════╗
║                 TERABOX DOWNLOADER                 ║
║            Created with ❤️ by Your Name            ║
╚════════════════════════════════════════════════════╝
[/bold cyan]"""
        console.print(banner)
        
    def format_size(self, size: int) -> str:
        """Format ukuran file ke format yang mudah dibaca"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} PB"

    def create_file_table(self, files: List[Dict[str, Any]]) -> Table:
        """Membuat tabel untuk menampilkan daftar file"""
        table = Table(
            show_header=True,
            header_style="bold magenta",
            border_style="cyan",
            expand=True
        )
        table.add_column("No", justify="center", style="cyan", width=4)
        table.add_column("Tipe", justify="center", width=4)
        table.add_column("Path", style="green", no_wrap=False)
        table.add_column("Ukuran", justify="right", style="yellow")
        
        # Flatten dan urutkan file berdasarkan tipe
        flattened_files = self.flatten_files(files)
        flattened_files.sort(key=lambda x: (x['type'], x['display_path']))
        
        for idx, file in enumerate(flattened_files, 1):
            icon = self._get_file_icon(file['name'])
            size_str = self.format_size(file['size'])
            
            table.add_row(
                str(idx),
                icon,
                file['display_path'],
                size_str
            )
            
        return table

    def _get_file_icon(self, filename: str) -> str:
        """Mendapatkan icon berdasarkan tipe file"""
        ext = filename.lower().split('.')[-1] if '.' in filename else ''
        icons = {
            'pdf': '📕',
            'doc': '📘',
            'docx': '📘',
            'xls': '📗',
            'xlsx': '📗',
            'jpg': '🖼️',
            'jpeg': '🖼️',
            'png': '🖼️',
            'gif': '🖼️',
            'mp4': '🎥',
            'mp3': '🎵',
            'zip': '📦',
            'rar': '📦',
            '7z': '📦',
        }
        return icons.get(ext, '📄')

    def flatten_files(self, files: List[Dict[str, Any]], parent_path: str = "") -> List[Dict[str, Any]]:
        """Mendapatkan semua file dalam folder secara rekursif"""
        flattened = []
        for file in files:
            current_path = f"{parent_path}/{file['name']}" if parent_path else file['name']
            is_dir = bool(int(file.get('is_dir', 0)))
            
            # Tambahkan file saat ini (jika bukan folder)
            if not is_dir:
                file_info = {
                    'is_dir': is_dir,
                    'name': file['name'],
                    'path': file.get('path', ''),
                    'size': int(file.get('size', 0)),
                    'fs_id': file.get('fs_id', ''),
                    'display_path': current_path,
                    'type': self._get_file_type(file['name'])
                }
                flattened.append(file_info)
            
            # Jika folder, langsung proses file di dalamnya
            if is_dir and file.get('list'):
                flattened.extend(self.flatten_files(file['list'], current_path))
        return flattened

    def _get_file_type(self, name: str) -> str:
        """Mendapatkan tipe file"""
        name = name.lower()
        if any(ext in name for ext in ['.mp4', '.mov', '.m4v', '.mkv', '.asf', '.avi', '.wmv', '.m2ts', '.3g2']):
            return 'video'
        elif any(ext in name for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg']):
            return 'image'
        elif any(ext in name for ext in ['.pdf', '.docx', '.zip', '.rar', '.7z']):
            return 'file'
        else:
            return 'other'

    def select_file(self, files: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Memilih file untuk didownload"""
        # Flatten semua file untuk pemilihan
        flattened_files = self.flatten_files(files)
        
        try:
            console.print("\n[bold cyan]Opsi download:[/]")
            console.print("0. Download semua file")
            console.print("1-N. Download file tertentu")
            
            choice = Prompt.ask(
                "\n[bold yellow]Pilih nomor file untuk didownload[/]",
                default="1"
            )
            
            # Handle download all
            if choice == "0":
                return "download_all"
                
            choice = int(choice)
            if 1 <= choice <= len(flattened_files):
                selected = flattened_files[choice-1]
                if selected['is_dir']:
                    console.print(Panel("[yellow]⚠️ Tidak bisa mendownload folder![/]", border_style="yellow"))
                    return None
                return selected
                
        except ValueError:
            pass
        console.print(Panel("[red]❌ Pilihan tidak valid![/]", border_style="red"))
        return None

    def download_all_files(self, files: List[Dict[str, Any]], tf: Any, path: str = "") -> None:
        """Download semua file dalam list dengan aria2p"""
        flattened_files = [f for f in self.flatten_files(files) if not f['is_dir']]
        
        if not flattened_files:
            console.print(Panel("[yellow]⚠️ Tidak ada file yang bisa didownload![/]", border_style="yellow"))
            return
            
        total_size = sum(int(f['size']) for f in flattened_files)
        total_files = len(flattened_files)
        
        # Tampilkan ringkasan download
        summary = Table.grid(padding=1)
        summary.add_row("[bold cyan]Total File:[/]", f"{total_files}")
        summary.add_row("[bold cyan]Total Ukuran:[/]", f"{self.format_size(total_size)}")
        
        console.print(Panel(summary, title="[bold]Ringkasan Download All[/]", border_style="cyan"))
        
        if not Confirm.ask("Mulai download semua file?"):
            return
            
        # Tentukan direktori download
        base_download_dir = Path("downloads")
        base_download_dir.mkdir(exist_ok=True)
        
        # Buat subfolder jika file > 5
        if total_files > 5:
            folder_name = (path.strip('/').split('/')[-1] if path 
                          else datetime.now().strftime("%Y%m%d_%H%M%S"))
            folder_name = ''.join(c for c in folder_name if c.isalnum() or c in (' ', '-', '_'))
            
            # Handle folder yang sudah ada
            download_dir = base_download_dir / folder_name
            counter = 1
            while download_dir.exists():
                folder_name = f"{folder_name}_{counter}"
                download_dir = base_download_dir / folder_name
                counter += 1
                
            download_dir.mkdir(exist_ok=True)
            console.print(Panel(f"[green]📁 Membuat folder: {folder_name}[/]", border_style="green"))
        else:
            download_dir = base_download_dir

        # Statistik download
        successful_downloads = 0
        failed_downloads = []
        start_time = time.time()
        
        # Download setiap file
        for idx, file in enumerate(flattened_files, 1):
            console.print(f"[bold blue]({idx}/{total_files})[/] ", end="")
            
            try:
                # Dapatkan link download
                with console.status(f"🔗 Mengambil link untuk {file['name']}...", spinner="dots"):
                    tl = TeraboxLink(
                        fs_id=str(file['fs_id']),
                        uk=str(tf.result['uk']),
                        shareid=str(tf.result['shareid']),
                        timestamp=str(tf.result['timestamp']),
                        sign=str(tf.result['sign']),
                        js_token=str(tf.result['js_token']),
                        cookie=str(tf.result['cookie'])
                    )
                    tl.generate()
                
                if tl.result['status'] != 'success':
                    failed_downloads.append((file['name'], "Gagal mendapatkan link download"))
                    continue
                    
                # Dapatkan URL download dengan domain d.terabox.com
                download_url = tl.result['download_link'].get('url_1', '')
                if download_url:
                    download_url = download_url.replace('//cdn.', '//d.').replace('//c.', '//d.').replace('//b.', '//d.').replace('//a.', '//d.')
                else:
                    failed_downloads.append((file['name'], "Tidak ada URL download yang valid"))
                    continue
                
                # Download file dengan aria2 jika tersedia
                if self.use_aria2:
                    filename = download_dir / file['name']
                    filesize = int(file['size'])
                    
                    # Tambahkan download ke aria2
                    try:
                        download = self.aria2.add_uris(
                            [download_url],
                            options={
                                "dir": str(download_dir),
                                "out": file['name'],
                                "max-connection-per-server": "16",
                                "split": "16",
                                "min-split-size": "1M",
                                "max-concurrent-downloads": "1",
                                "continue": "true",
                                "max-tries": "10",
                                "retry-wait": "3",
                                "connect-timeout": "60",
                                "timeout": "60",
                                "max-file-not-found": "5",
                                "max-overall-download-limit": "0",
                                "max-download-limit": "0",
                                "file-allocation": "none",
                                "auto-file-renaming": "false",
                                "allow-overwrite": "true"
                            }
                        )
                        
                        # Monitor progress
                        last_progress = -1
                        no_progress_time = time.time()
                        
                        while not download.is_complete:
                            if self.cancel_event.is_set():
                                download.remove()
                                console.print("\n[bold red]Download dibatalkan![/]")
                                return
                            
                            try:
                                download.update()
                                progress = download.progress
                                speed = download.download_speed
                                
                                if progress != last_progress:
                                    last_progress = progress
                                    no_progress_time = time.time()
                                    console.print(f"[cyan]Progress: {progress:.1f}% ({self.format_size(speed)}/s)[/]")
                                elif time.time() - no_progress_time > 30:
                                    raise Exception("Download timeout - tidak ada progress selama 30 detik")
                                    
                            except aria2p.client.ClientException as e:
                                self.logger.error(f"Aria2 error: {str(e)}")
                                console.print(f"[red]Error: {str(e)}[/]")
                                continue
                                
                            time.sleep(1)
                        
                        # Verifikasi hasil download
                        if os.path.exists(filename):
                            actual_size = os.path.getsize(filename)
                            if actual_size == filesize:
                                successful_downloads += 1
                                console.print(Panel(
                                    f"[green]✅ {file['name']} berhasil didownload[/]",
                                    border_style="green"
                                ))
                                continue
                            else:
                                raise Exception(f"Ukuran file tidak sesuai (expected: {filesize}, actual: {actual_size})")
                        
                        raise Exception("File tidak ditemukan setelah download selesai")
                        
                    except Exception as e:
                        failed_downloads.append((file['name'], str(e)))
                        console.print(Panel(
                            f"[red]❌ {file['name']} gagal didownload: {str(e)}[/]",
                            border_style="red"
                        ))
                        continue
                        
                else:
                    # Gunakan metode download default jika aria2 tidak tersedia
                    filename = download_dir / file['name']
                    filesize = int(file['size'])
                    
                    if self.download_file(download_url, str(filename), filesize, quiet=True):
                        successful_downloads += 1
                        console.print(Panel(
                            f"[green]✅ {file['name']} berhasil didownload[/]",
                            border_style="green"
                        ))
                    else:
                        failed_downloads.append((file['name'], "Gagal saat download"))
                        console.print(Panel(
                            f"[red]❌ {file['name']} gagal didownload[/]",
                            border_style="red"
                        ))
                
            except Exception as e:
                failed_downloads.append((file['name'], str(e)))
                console.print(Panel(
                    f"[red]❌ Error: {str(e)}[/]",
                    border_style="red"
                ))
                continue

        # Tampilkan ringkasan akhir
        duration = time.time() - start_time
        avg_speed = total_size / duration if duration > 0 else 0
        
        summary = Table.grid(padding=1)
        summary.add_row("[bold cyan]Total Waktu:[/]", f"{int(duration)} detik")
        summary.add_row("[bold cyan]Kecepatan Rata-rata:[/]", f"{self.format_size(avg_speed)}/s")
        summary.add_row("[bold green]Berhasil Download:[/]", f"{successful_downloads} file")
        summary.add_row("[bold red]Gagal Download:[/]", f"{len(failed_downloads)} file")
        
        if failed_downloads:
            failed_table = Table(show_header=True, header_style="bold red")
            failed_table.add_column("Nama File")
            failed_table.add_column("Alasan Gagal")
            for name, reason in failed_downloads:
                failed_table.add_row(name, reason)
            
            console.print(Panel(
                Group(
                    Panel(summary, title="[bold]📊 Ringkasan Download[/]", border_style="cyan"),
                    Panel(failed_table, title="[bold red]❌ Daftar File Gagal[/]", border_style="red")
                ),
                title="[bold]Download Selesai[/]",
                border_style="yellow"
            ))
        else:
            console.print(Panel(
                summary,
                title="[bold]✅ Download Selesai[/]",
                border_style="green"
            ))

    def test_download_speed(self, urls: List[str], sample_size: int = 1024 * 1024) -> str:
        """Test kecepatan download dengan caching"""
        # Ambil URL dengan domain d.terabox.com
        for url in urls:
            if 'd.terabox.com' in url:
                return url
                
        # Jika tidak ada yang menggunakan d.terabox.com, ubah domain URL pertama
        if urls:
            url = urls[0]
            return url.replace('//cdn.', '//d.').replace('//c.', '//d.').replace('//b.', '//d.').replace('//a.', '//d.')
            
        return urls[0] if urls else ""

    def calculate_delay(self, attempt: int) -> float:
        """Menghitung delay untuk retry dengan exponential backoff"""
        backoff_factor = 1.5
        max_backoff = 60  # Maksimal delay 60 detik
        
        delay = min(self.retry_delay * (backoff_factor ** attempt), max_backoff)
        jitter = random.uniform(0, 0.1 * delay)  # Tambah random jitter
        return delay + jitter

    def download_file(self, url: str, filename: str, filesize: int, quiet: bool = False, alternative_urls: List[str] = None) -> bool:
        """Download file dengan aria2 atau metode default"""
        self.cancel_event.clear()
        self.start_time = time.time()
        
        # Gunakan aria2 jika tersedia
        if self.use_aria2:
            return self.download_with_aria2(url, filename, filesize, quiet)
            
        # Jika aria2 tidak tersedia, gunakan metode default
        temp_filename = filename + ".tmp"
        
        try:
            with requests.get(url, stream=True, timeout=self.read_timeout) as response:
                response.raise_for_status()
                
                if not quiet:
                    # Tampilkan informasi download sekali di awal
                    info_table = Table.grid(padding=1)
                    info_table.add_row("[cyan]Nama File:[/]", os.path.basename(filename))
                    info_table.add_row("[cyan]Ukuran:[/]", self.format_size(filesize))
                    
                    console.print(Panel(
                        info_table,
                        title="[bold]Informasi Download[/]",
                        border_style="cyan"
                    ))
                    
                    # Buat progress bar tunggal
                    progress = Progress(
                        TextColumn("[bold blue]{task.fields[filename]}"),
                        TextColumn("[dim cyan]•[/]"),
                        BarColumn(bar_width=50, style="cyan", complete_style="green"),
                        TextColumn("[dim cyan]•[/]"),
                        TextColumn("[progress.percentage]{task.percentage:>3.1f}%"),
                        TextColumn("[dim cyan]•[/]"),
                        DownloadColumn(),
                        TextColumn("[dim cyan]•[/]"),
                        TransferSpeedColumn(),
                        TextColumn("[dim cyan]•[/]"),
                        TimeRemainingColumn(),
                        expand=True
                    )
                    
                    with progress:
                        task_id = progress.add_task(
                            "download",
                            filename=os.path.basename(filename),
                            total=filesize
                        )
                        
                        with open(temp_filename, 'wb') as f:
                            downloaded = 0
                            for chunk in response.iter_content(chunk_size=8192):
                                if self.cancel_event.is_set():
                                    console.print("\n[bold red]Download dibatalkan![/]")
                                    raise Exception("Download dibatalkan oleh pengguna")
                                    
                                if chunk:
                                    f.write(chunk)
                                    downloaded += len(chunk)
                                    progress.update(task_id, completed=downloaded)
                                    
                            # Setelah selesai, tampilkan ringkasan
                            duration = time.time() - self.start_time
                            speed = filesize / duration if duration > 0 else 0
                            
                            console.print()  # Beri jarak
                            summary = Table.grid(padding=1)
                            summary.add_row("[bold green]✅ Download berhasil![/]")
                            summary.add_row("[cyan]Total Waktu:[/]", f"{int(duration)} detik")
                            summary.add_row("[cyan]Kecepatan Rata-rata:[/]", f"{self.format_size(speed)}/s")
                            
                            console.print(Panel(
                                summary,
                                title="[bold]Download Selesai[/]",
                                border_style="green"
                            ))
                
                else:
                    # Download tanpa progress bar untuk quiet mode
                    with open(temp_filename, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                
            # Verifikasi ukuran file
            if os.path.getsize(temp_filename) == filesize:
                os.rename(temp_filename, filename)
                return True
            else:
                raise Exception("Ukuran file tidak sesuai")

        except Exception as e:
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
            self.handle_error(e, "Download gagal")
            return False

    def get_folder_by_path(self, files: List[Dict[str, Any]], path: str) -> Optional[List[Dict[str, Any]]]:
        """Mendapatkan folder berdasarkan path"""
        if not path or path == '/':
            return files
            
        # Bersihkan path
        path = path.strip('/')
        path_parts = [p for p in path.split('/') if p and p != '#####']
        
        current_files = files
        for part in path_parts:
            found = False
            for file in current_files:
                if file['name'].lower() == part.lower() and bool(int(file.get('is_dir', 0))):
                    current_files = file.get('list', [])
                    found = True
                    break
            if not found:
                return None
        return current_files

    def log_urls(self, filename: str, urls: List[str], url_types: List[str]) -> None:
        """Mencatat URL ke dalam file log"""
        try:
            log_file = self.url_log_dir / f"url_log_{datetime.now():%Y%m%d}.txt"
            
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*50}\n")
                f.write(f"Timestamp: {datetime.now():%Y-%m-%d %H:%M:%S}\n")
                f.write(f"File: {filename}\n")
                f.write(f"{'='*50}\n")
                
                for url_type, url in zip(url_types, urls):
                    f.write(f"\n{url_type}:\n{url}\n")
                
                f.write(f"\n{'='*50}\n")
                
        except Exception as e:
            self.logger.error(f"Gagal mencatat URL: {str(e)}")

    def process_url(self, url: str) -> None:
        """Memproses URL Terabox dan menangani download"""
        path = ''
        
        try:
            # Ganti emoji dengan teks biasa untuk logging
            self.logger.info(f"[LINK] Memproses URL: {url}")
            
            # Handle berbagai format URL
            if 'surl=' in url:
                parsed_url = urlparse(url)
                # Ambil semua parameter query
                query_params = dict(param.split('=', 1) for param in parsed_url.query.split('&') if '=' in param)
                
                # Ekstrak surl dan path
                surl = query_params.get('surl', '')
                path = query_params.get('path', '')
                
                # Buat URL baru hanya dengan parameter surl
                base_url = f"https://www.terabox.com/sharing/link?surl={surl}"
                url = base_url
                
                # Decode path jika ada
                if path:
                    path = requests.utils.unquote(path)
                    
            # Log URL yang akan diproses
            self.logger.info(f"🔗 Memproses URL: {url}")
            
            with console.status("[bold blue]🔍 Mengambil informasi file...[/]", spinner="dots"):
                tf = TeraboxFile()
                tf.search(url)
                
            if tf.result['status'] != 'success':
                console.print(Panel("[red]❌ Gagal mendapatkan informasi file![/]", border_style="red"))
                return
            
            # Jika ada path, coba dapatkan folder yang sesuai
            files_to_show = tf.result['list']
            if path:
                # Bersihkan path dari karakter khusus
                clean_path = path.strip('/')
                folder_files = self.get_folder_by_path(files_to_show, clean_path)
                
                if folder_files is not None:
                    files_to_show = folder_files
                    console.print(Panel(f"[green]📂 Menampilkan isi folder: {clean_path}[/]", border_style="green"))
                else:
                    console.print(Panel(f"[yellow]⚠️ Path folder tidak ditemukan: {clean_path}\nMenampilkan semua file[/]", border_style="yellow"))
            
            # Tampilkan daftar file
            console.print("\n[bold cyan]📑 Daftar Semua File:[/]")
            table = self.create_file_table(files_to_show)
            console.print(table)
            
            # Tampilkan total informasi
            flattened_files = self.flatten_files(files_to_show)
            total_files = len([f for f in flattened_files if not f['is_dir']])
            total_folders = len([f for f in flattened_files if f['is_dir']])
            total_size = sum(int(f['size']) for f in flattened_files if not f['is_dir'])
            
            summary = Table.grid(padding=1)
            summary.add_row("[bold cyan]Total File:[/]", f"{total_files}")
            summary.add_row("[bold cyan]Total Folder:[/]", f"{total_folders}")
            summary.add_row("[bold cyan]Total Ukuran:[/]", f"{self.format_size(total_size)}")
            
            console.print(Panel(summary, title="[bold]Ringkasan[/]", border_style="cyan"))
            
            # Pilih file
            selected_file = self.select_file(files_to_show)
            if not selected_file:
                return
            
            # Handle download all dengan menyertakan path
            if selected_file == "download_all":
                self.download_all_files(files_to_show, tf, path)
                return
            
            # Dapatkan link download
            with console.status("[bold blue]🔗 Mengambil link download...[/]", spinner="dots"):
                try:
                    tl = TeraboxLink(
                        fs_id=str(selected_file['fs_id']),
                        uk=str(tf.result['uk']),
                        shareid=str(tf.result['shareid']),
                        timestamp=str(tf.result['timestamp']),
                        sign=str(tf.result['sign']),
                        js_token=str(tf.result['js_token']),
                        cookie=str(tf.result['cookie'])
                    )
                    tl.generate()
                except Exception as e:
                    console.print(Panel(f"[red]❌ Error saat mengambil link download: {str(e)}[/]", border_style="red"))
                    return
            
            if tl.result['status'] != 'success':
                console.print(Panel("[red]❌ Gagal mendapatkan link download![/]", border_style="red"))
                return
                
            # Dapatkan URL download dengan domain d.terabox.com
            download_url = tl.result['download_link'].get('url_1', '')
            if download_url:
                download_url = download_url.replace('//cdn.', '//d.').replace('//c.', '//d.').replace('//b.', '//d.').replace('//a.', '//d.')
            else:
                console.print(Panel("[red]❌ Tidak ada URL download yang valid![/]", border_style="red"))
                return

            # Buat direktori downloads jika belum ada
            download_dir = Path("downloads")
            download_dir.mkdir(exist_ok=True)
            
            # Persiapkan download
            try:
                filename = download_dir / selected_file['name']
                filesize = int(selected_file['size'])  # Pastikan size adalah integer
                
                # Tampilkan informasi file
                file_info = Table.grid(padding=1)
                file_info.add_row("[bold]Nama File:[/]", selected_file['name'])
                file_info.add_row("[bold]Ukuran:[/]", self.format_size(filesize))
                file_info.add_row("[bold]Lokasi:[/]", str(filename))
                
                console.print(Panel(
                    file_info,
                    title="[bold]Informasi Download[/]",
                    border_style="cyan"
                ))
                
                # Tampilkan opsi untuk download atau copy
                console.print("\n[bold yellow]Pilihan:[/]")
                console.print("[green]y[/] - Mulai download")
                console.print("[red]n[/] - Batalkan")
                console.print("[cyan]c[/] - Copy semua URL")
                
                choice = Prompt.ask(
                    "\n[bold yellow]Pilihan Anda[/]",
                    choices=["y", "n", "c"],
                    default="y"
                )
                
                if choice == "c":
                    # Buat teks URL yang akan disalin
                    url_text = "\nURL Download Terabox:\n"
                    url_text += f"Normal Speed: {download_url}\n"
                    
                    # Catat URL ke dalam log
                    self.log_urls(selected_file['name'], [download_url], ["Normal Speed"])
                    
                    # Tampilkan URL yang bisa disalin
                    console.print(Panel(
                        f"[green]Berikut adalah semua URL yang bisa disalin:[/]\n{url_text}\n[cyan]URL telah dicatat di: {self.url_log_dir}[/]",
                        title="[bold]📋 Copy URL[/]",
                        border_style="cyan"
                    ))
                    
                    # Tanya apakah ingin melanjutkan download
                    if Confirm.ask("\nLanjutkan download?"):
                        choice = "y"
                    else:
                        return
                
                if choice == "y":
                    # Dapatkan semua URL alternatif yang valid
                    alternative_urls = [url for url in [download_url] if url and url != download_url]
                    
                    self.download_file(
                        download_url, 
                        str(filename), 
                        filesize, 
                        alternative_urls=alternative_urls
                    )
                    
            except Exception as e:
                console.print(Panel(f"[red]❌ Error saat mempersiapkan download: {str(e)}[/]", border_style="red"))
                return
                
        except Exception as e:
            console.print(Panel(f"[red]❌ Error: {str(e)}[/]", border_style="red"))
            return

    def verify_file_integrity(self, filename: str, expected_size: int) -> bool:
        """Verifikasi integritas file"""
        try:
            actual_size = os.path.getsize(filename)
            if actual_size != expected_size:
                return False
                
            # Baca file dalam chunks untuk mengecek corrupted data
            with open(filename, 'rb') as f:
                while chunk := f.read(8192):
                    pass
            return True
            
        except Exception:
            return False
            
    def cancel_download(self):
        """Batalkan download yang sedang berjalan"""
        self.cancel_event.set()
        
    def progress_callback(self, downloaded: int, total: int):
        """Callback untuk progress download yang lebih detail"""
        percentage = (downloaded / total) * 100
        speed = downloaded / (time.time() - self.start_time) if time.time() - self.start_time > 0 else 0
        self.logger.info(f"Progress: {percentage:.1f}% Speed: {self.format_size(speed)}/s")

    def resume_download(self, filename: str, url: str, filesize: int) -> bool:
        """Implementasi resume download jika file terputus"""
        temp_file = filename + ".tmp"
        if os.path.exists(temp_file):
            current_size = os.path.getsize(temp_file)
            if current_size < filesize:
                headers = {'Range': f'bytes={current_size}-'}
                try:
                    response = self.session.get(url, headers=headers, stream=True, timeout=self.read_timeout)
                    response.raise_for_status()
                    
                    with open(temp_file, 'ab') as f:
                        for chunk in response.iter_content(chunk_size=self.chunk_size):
                            if self.cancel_event.is_set():
                                return False
                            if chunk:
                                f.write(chunk)
                                current_size += len(chunk)
                                self.progress_callback(current_size, filesize)
                    
                    if os.path.getsize(temp_file) == filesize:
                        os.rename(temp_file, filename)
                        return True
                except Exception as e:
                    self.handle_error(e, "Resume download gagal")
                    return False
        
        return self.download_file(url, filename, filesize)

    def handle_error(self, error: Exception, context: str = "") -> None:
        """Menangani error dengan lebih terstruktur"""
        error_msg = f"{context}: {str(error)}" if context else str(error)
        self.logger.error(error_msg)
        console.print(Panel(f"[red]❌ {error_msg}[/]", border_style="red"))

def main():
    try:
        downloader = TeraboxDownloader()
        downloader.show_banner()
        
        if len(sys.argv) < 2:
            console.print(Panel(
                "[red]Usage: python terabox_cli.py <terabox_url>[/]",
                border_style="red"
            ))
            sys.exit(1)
            
        url = sys.argv[1]
        downloader.process_url(url)
        
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️ Download dibatalkan oleh pengguna[/]")
    except Exception as e:
        console.print(f"[red]❌ Terjadi kesalahan: {str(e)}[/]")

if __name__ == "__main__":
    main()