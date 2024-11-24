import os
import sys
import time
import requests
from typing import Optional, List, Dict, Any
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
    SpinnerColumn
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

console = Console()

class TeraboxDownloader:
    def __init__(self):
        self.chunk_size = 4 * 1024 * 1024  # 4MB chunks
        self.max_workers = min(64, multiprocessing.cpu_count() * 4)
        self.session = self._create_session()
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.fields[filename]}", justify="right"),
            BarColumn(bar_width=40),
            "[progress.percentage]{task.percentage:>3.0f}%",
            "•",
            DownloadColumn(),
            "•",
            TransferSpeedColumn(),
            "•",
            TimeRemainingColumn(),
            refresh_per_second=10,  # Update 10x per detik
            expand=True
        )
        self.download_lock = threading.Lock()
        self.total_downloaded = 0
        self.start_time = 0
        
    def _create_session(self) -> requests.Session:
        """Membuat session dengan optimasi"""
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=100,
            pool_maxsize=100,
            max_retries=3,
            pool_block=False
        )
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        session.headers.update({
            'Connection': 'keep-alive',
            'Keep-Alive': 'timeout=300',
            'Accept-Encoding': 'gzip, deflate',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
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
        """Download semua file dalam list dengan metode sederhana"""
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
                    
                # Dapatkan URL download terbaik
                download_urls = [
                    tl.result['download_link'].get('url_1', ''),
                    tl.result['download_link'].get('url_2', ''),
                    tl.result['download_link'].get('url_3', '')
                ]
                download_urls = [url for url in download_urls if url]
                
                if not download_urls:
                    failed_downloads.append((file['name'], "Tidak ada URL download yang valid"))
                    continue
                    
                # Test dan pilih URL terbaik
                with console.status("🔄 Testing kecepatan server...", spinner="dots"):
                    download_url = self.test_download_speed(download_urls)
                
                # Download file
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
        """Test kecepatan download dari beberapa URL dan pilih yang tercepat"""
        results = []
        
        def test_url(url):
            try:
                start_time = time.time()
                response = self.session.get(url, stream=True, timeout=5)
                response.raise_for_status()
                
                # Baca chunk pertama saja
                next(response.iter_content(chunk_size=sample_size))
                
                duration = time.time() - start_time
                latency = response.elapsed.total_seconds()
                
                # Hitung skor berdasarkan latency dan kecepatan
                speed_score = sample_size / duration if duration > 0 else 0
                latency_score = 1 / latency if latency > 0 else 0
                total_score = speed_score * 0.7 + latency_score * 0.3
                
                return (url, total_score)
                
            except Exception:
                return (url, 0)

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(urls)) as executor:
            futures = [executor.submit(test_url, url) for url in urls]
            for future in concurrent.futures.as_completed(futures):
                url, score = future.result()
                results.append((url, score))

        # Sort berdasarkan skor tertinggi
        results.sort(key=lambda x: x[1], reverse=True)
        return results[0][0] if results else urls[0]

    def download_file(self, url: str, filename: str, filesize: int, quiet: bool = False) -> bool:
        """Download file dengan metode sederhana dan progress realtime"""
        temp_filename = filename + ".part"
        mode = "wb"
        existing_size = 0

        try:
            filesize = int(filesize)
        except (ValueError, TypeError):
            console.print(Panel("[red]❌ Ukuran file tidak valid![/]", border_style="red"))
            return False

        # Cek file yang belum selesai
        if os.path.exists(temp_filename):
            existing_size = os.path.getsize(temp_filename)
            if existing_size < filesize:
                mode = "ab"  # Append mode untuk melanjutkan download
                console.print(Panel(
                    f"[yellow]💡 Melanjutkan download dari {self.format_size(existing_size)}[/]",
                    border_style="yellow"
                ))
            else:
                os.remove(temp_filename)
                existing_size = 0

        self.total_downloaded = existing_size
        self.start_time = time.time()

        # Setup headers untuk resume download
        headers = {}
        if existing_size > 0:
            headers['Range'] = f'bytes={existing_size}-'

        try:
            with self.progress as progress:
                task_id = progress.add_task(
                    "download",
                    filename=os.path.basename(filename),
                    total=filesize
                )
                progress.update(task_id, completed=existing_size)

                with self.session.get(url, headers=headers, stream=True, timeout=30) as response:
                    response.raise_for_status()
                    with open(temp_filename, mode) as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                progress.update(task_id, advance=len(chunk))
                                self.total_downloaded += len(chunk)

            # Verifikasi file
            if os.path.getsize(temp_filename) == filesize:
                os.rename(temp_filename, filename)
                if not quiet:
                    duration = time.time() - self.start_time
                    speed = filesize / duration if duration > 0 else 0
                    console.print(Panel(
                        f"[green]✅ Download selesai: {os.path.basename(filename)}\n"
                        f"⚡ Kecepatan rata-rata: {self.format_size(speed)}/s\n"
                        f"⏱️ Waktu: {int(duration)} detik[/]",
                        border_style="green"
                    ))
                return True
            else:
                if not quiet:
                    console.print(Panel(
                        "[red]❌ File tidak lengkap, silakan coba download ulang[/]",
                        border_style="red"
                    ))
                return False

        except Exception as e:
            if not quiet:
                console.print(Panel(f"[red]❌ Error saat download: {str(e)}[/]", border_style="red"))
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

    def process_url(self, url: str) -> None:
        """Memproses URL Terabox dan menangani download"""
        # Ekstrak path dari URL jika ada
        path = ''
        
        # Handle URL dengan format baru
        if 'path=' in url:
            parsed_url = urlparse(url)
            query_params = dict(param.split('=') for param in parsed_url.query.split('&'))
            
            # Ekstrak surl dan path
            surl = query_params.get('surl', '')
            path = query_params.get('path', '')
            
            # Buat URL baru tanpa path
            base_url = f"https://www.terabox.com/sharing/link?surl={surl}"
            url = base_url
            
            # Decode path
            path = requests.utils.unquote(path)
            
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
                    fs_id=str(selected_file['fs_id']),  # Pastikan dalam bentuk string
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

        # Dapatkan URL download terbaik
        try:
            download_urls = [
                tl.result['download_link'].get('url_1', ''),
                tl.result['download_link'].get('url_2', ''),
                tl.result['download_link'].get('url_3', '')
            ]
            download_urls = [url for url in download_urls if url]  # Filter URL kosong
            
            if not download_urls:
                console.print(Panel("[red]❌ Tidak ada URL download yang valid![/]", border_style="red"))
                return
            
            # Tampilkan semua URL download yang tersedia
            url_info = Table.grid(padding=1)
            url_info.add_row("[bold cyan]URL Download yang tersedia:[/]")
            for i, url in enumerate(download_urls, 1):
                url_info.add_row(f"[yellow]URL {i}:[/] {url}")
            console.print(Panel(url_info, border_style="blue"))
                
            # Pilih URL tercepat
            download_url = self.test_download_speed(download_urls)
            
            if not download_url:
                console.print(Panel("[yellow]⚠️ Gagal test kecepatan, menggunakan URL pertama[/]", border_style="yellow"))
                download_url = download_urls[0]
            
            console.print(Panel(
                f"[green]URL yang akan digunakan:[/]\n{download_url}",
                border_style="green"
            ))
            
        except Exception as e:
            console.print(Panel(f"[red]❌ Error saat memproses URL download: {str(e)}[/]", border_style="red"))
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
            
            if Confirm.ask("Mulai download?"):
                self.download_file(download_url, str(filename), filesize)
                
        except Exception as e:
            console.print(Panel(f"[red]❌ Error saat mempersiapkan download: {str(e)}[/]", border_style="red"))
            return

def main():
    try:
        downloader = TeraboxDownloader()
        downloader.show_banner()
        
        if len(sys.argv) != 2:
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