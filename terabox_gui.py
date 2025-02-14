import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from ttkthemes import ThemedTk
from typing import Optional, Dict, Any, List
import threading
import queue
import json
import os
from pathlib import Path
from datetime import datetime
from terabox_cli import TeraboxDownloader
import logging
from rich.console import Console
import sys
import re
from PIL import Image, ImageTk
import requests
from io import BytesIO
import webbrowser
import time
import subprocess
import aria2p
import multiprocessing

class TeraboxGUI:
    """
    GUI implementation for TeraBox Downloader using tkinter and ttkthemes.
    
    This class provides a modern and user-friendly interface for downloading files from TeraBox,
    implementing all features from the CLI version with additional GUI conveniences.
    """
    
    def __init__(self):
        """Initialize the TeraBox GUI application."""
        self.root = ThemedTk(theme="yaru")  # Modern theme
        self.root.title("TeraBox Downloader")
        self.root.geometry("1000x700")
        self.root.minsize(800, 600)
        
        # Setup logging first
        self.setup_logging()
        
        # Initialize downloader
        self.downloader = TeraboxDownloader()
        self.console = Console()
        self.download_queue = queue.Queue()
        self.current_downloads: Dict[str, Dict[str, Any]] = {}
        
        # Setup chunk size dan workers
        self.chunk_size = 16 * 1024 * 1024  # 16MB chunk size
        self.max_workers = min(64, multiprocessing.cpu_count() * 8)
        
        # Load saved settings
        self.config_file = Path("config/settings.json")
        self.config_file.parent.mkdir(exist_ok=True)
        self.settings = self.load_settings()
        
        # Update trackers
        self.update_trackers()
        
        # Setup aria2
        self._setup_aria2()
        
        # Create main container
        self.main_container = ttk.Frame(self.root)
        self.main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create and setup UI components
        self.create_header()
        self.create_url_input()
        self.create_file_list()
        self.create_download_progress()
        self.create_status_bar()
        self.create_settings_button()
        
        # Initialize variables
        self.current_url = ""
        self.file_list_data = []
        
        # Bind events
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def setup_logging(self):
        """Setup logging configuration for the GUI application."""
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        log_file = log_dir / f"terabox_gui_{datetime.now():%Y%m%d}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def _setup_aria2(self) -> bool:
        """Setup aria2 dan aria2p"""
        try:
            # Cek di folder lokal dulu
            local_aria2 = Path("aria2/aria2c.exe")
            if local_aria2.exists():
                # Start aria2c daemon dengan konfigurasi yang sama dengan CLI
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
                    "--daemon=true",
                    f"--disk-cache={self.chunk_size}",  # Set disk cache sama dengan chunk size
                    "--async-dns=true",
                    "--enable-mmap=true",
                    "--optimize-concurrent-downloads=true",
                    "--http-accept-gzip=true",
                    "--reuse-uri=true",
                    "--enable-http-keep-alive=true",
                    "--enable-http-pipelining=true",
                    "--stream-piece-selector=inorder",
                    "--uri-selector=inorder",
                    "--min-tls-version=TLSv1.2"
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
                self.logger.info("Aria2 berhasil disetup dengan konfigurasi CLI")
                return True
            
            self.logger.warning("aria2 tidak ditemukan, menggunakan metode download default")
            messagebox.showwarning("Peringatan", "aria2 tidak ditemukan, download mungkin akan lebih lambat")
            return False
            
        except Exception as e:
            self.logger.error(f"Error setting up aria2: {str(e)}")
            messagebox.showerror("Error", f"Gagal setup aria2: {str(e)}")
            return False
        
    def create_header(self):
        """Create the header section with logo and title."""
        header_frame = ttk.Frame(self.main_container)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Logo (placeholder - you should add your own logo)
        logo_label = ttk.Label(header_frame, text="📦", font=("Segoe UI", 24))
        logo_label.pack(side=tk.LEFT, padx=5)
        
        # Title
        title_label = ttk.Label(
            header_frame, 
            text="TeraBox Downloader",
            font=("Segoe UI", 18, "bold")
        )
        title_label.pack(side=tk.LEFT, padx=5)
        
    def create_url_input(self):
        """Create the URL input section."""
        url_frame = ttk.LabelFrame(self.main_container, text="URL TeraBox", padding=10)
        url_frame.pack(fill=tk.X, pady=(0, 10))
        
        # URL Entry
        self.url_var = tk.StringVar()
        url_entry = ttk.Entry(url_frame, textvariable=self.url_var)
        url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        # Process Button
        process_btn = ttk.Button(
            url_frame,
            text="Proses URL",
            command=self.process_url,
            style="Accent.TButton"
        )
        process_btn.pack(side=tk.RIGHT)
        
    def create_file_list(self):
        """Create the file list section with Treeview."""
        list_frame = ttk.LabelFrame(self.main_container, text="Daftar File", padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Create Treeview
        columns = ("Nama", "Tipe", "Ukuran", "Status")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings")
        
        # Setup columns
        self.tree.heading("Nama", text="Nama File")
        self.tree.heading("Tipe", text="Tipe")
        self.tree.heading("Ukuran", text="Ukuran")
        self.tree.heading("Status", text="Status")
        
        # Column widths
        self.tree.column("Nama", width=300)
        self.tree.column("Tipe", width=100)
        self.tree.column("Ukuran", width=100)
        self.tree.column("Status", width=100)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack elements
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Buttons frame
        btn_frame = ttk.Frame(list_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Download buttons
        download_btn = ttk.Button(
            btn_frame,
            text="Download Terpilih",
            command=self.download_selected,
            style="Accent.TButton"
        )
        download_btn.pack(side=tk.LEFT, padx=5)
        
        download_all_btn = ttk.Button(
            btn_frame,
            text="Download Semua",
            command=self.download_all,
            style="Accent.TButton"
        )
        download_all_btn.pack(side=tk.LEFT, padx=5)
        
    def create_download_progress(self):
        """Create the download progress section."""
        progress_frame = ttk.LabelFrame(
            self.main_container,
            text="Progress Download",
            padding=10
        )
        progress_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Progress info frame
        info_frame = ttk.Frame(progress_frame)
        info_frame.pack(fill=tk.X, pady=(0, 5))
        
        # File name label
        self.current_file_label = ttk.Label(info_frame, text="")
        self.current_file_label.pack(side=tk.LEFT)
        
        # Speed and ETA frame
        stats_frame = ttk.Frame(info_frame)
        stats_frame.pack(side=tk.RIGHT)
        
        self.speed_label = ttk.Label(stats_frame, text="")
        self.speed_label.pack(side=tk.LEFT, padx=5)
        
        self.eta_label = ttk.Label(stats_frame, text="")
        self.eta_label.pack(side=tk.LEFT, padx=5)
        
        # Progress bar frame
        bar_frame = ttk.Frame(progress_frame)
        bar_frame.pack(fill=tk.X)
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            bar_frame,
            variable=self.progress_var,
            mode='determinate',
            length=400
        )
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=(0, 5))
        
        # Cancel button
        self.cancel_btn = ttk.Button(
            bar_frame,
            text="❌ Cancel",
            command=self.cancel_download,
            state=tk.DISABLED
        )
        self.cancel_btn.pack(side=tk.RIGHT, padx=(5, 0))
        
        # Progress details
        details_frame = ttk.Frame(progress_frame)
        details_frame.pack(fill=tk.X)
        
        self.progress_label = ttk.Label(details_frame, text="Siap untuk download...")
        self.progress_label.pack(side=tk.LEFT)
        
        self.size_label = ttk.Label(details_frame, text="")
        self.size_label.pack(side=tk.RIGHT)
        
        # Inisialisasi flag cancel
        self.cancel_flag = threading.Event()
        
    def create_status_bar(self):
        """Create the status bar."""
        self.status_var = tk.StringVar()
        self.status_var.set("Siap")
        
        status_bar = ttk.Label(
            self.main_container,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            padding=5
        )
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        
    def create_settings_button(self):
        """Create the settings button and dialog."""
        settings_btn = ttk.Button(
            self.main_container,
            text="⚙️ Pengaturan",
            command=self.show_settings,
            style="Accent.TButton"
        )
        settings_btn.pack(side=tk.RIGHT, pady=(0, 10))
        
    def load_settings(self) -> Dict[str, Any]:
        """Load settings from JSON file."""
        default_settings = {
            "download_dir": str(Path("downloads").absolute()),
            "max_connections": 16,
            "split": 16,
            "min_split_size": "1M",
            "disk_cache": "64M",
            "last_url": "",
            "theme": "arc",
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    saved_settings = json.load(f)
                    # Update default settings with saved ones
                    default_settings.update(saved_settings)
                    self.logger.info("Berhasil memuat konfigurasi")
        except Exception as e:
            self.logger.error(f"Error loading settings: {str(e)}")
            
        return default_settings

    def save_settings(self):
        """Save current settings to JSON file."""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.settings, f, indent=4)
            self.logger.info("Berhasil menyimpan konfigurasi")
        except Exception as e:
            self.logger.error(f"Error saving settings: {str(e)}")

    def show_settings(self):
        """Show the settings dialog."""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Pengaturan")
        settings_window.geometry("500x500")  # Perbesar window untuk menampung user agent
        settings_window.transient(self.root)
        settings_window.grab_set()
        
        # Create notebook for settings categories
        notebook = ttk.Notebook(settings_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Aria2 Settings
        aria2_frame = ttk.Frame(notebook, padding=10)
        notebook.add(aria2_frame, text="Aria2")
        
        # Aria2 settings
        ttk.Label(aria2_frame, text="Konfigurasi Aria2").pack(anchor=tk.W)
        
        # Max connections
        ttk.Label(aria2_frame, text="Max Connections:").pack(anchor=tk.W)
        max_conn = ttk.Entry(aria2_frame)
        max_conn.insert(0, str(self.settings.get("max_connections", 16)))
        max_conn.pack(fill=tk.X, pady=5)
        
        # Split
        ttk.Label(aria2_frame, text="Split:").pack(anchor=tk.W)
        split = ttk.Entry(aria2_frame)
        split.insert(0, str(self.settings.get("split", 16)))
        split.pack(fill=tk.X, pady=5)
        
        # Min split size
        ttk.Label(aria2_frame, text="Min Split Size:").pack(anchor=tk.W)
        min_split = ttk.Entry(aria2_frame)
        min_split.insert(0, self.settings.get("min_split_size", "1M"))
        min_split.pack(fill=tk.X, pady=5)
        
        # User Agent
        ttk.Label(aria2_frame, text="User Agent:").pack(anchor=tk.W)
        user_agent = ttk.Entry(aria2_frame)
        user_agent.insert(0, self.settings.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"))
        user_agent.pack(fill=tk.X, pady=5)
        
        # Tombol reset User Agent
        def reset_user_agent():
            default_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            user_agent.delete(0, tk.END)
            user_agent.insert(0, default_ua)
            
        reset_ua_btn = ttk.Button(
            aria2_frame,
            text="Reset User Agent",
            command=reset_user_agent
        )
        reset_ua_btn.pack(pady=5)
        
        # Download Settings
        download_frame = ttk.Frame(notebook, padding=10)
        notebook.add(download_frame, text="Download")
        
        # Download directory
        ttk.Label(download_frame, text="Download Directory:").pack(anchor=tk.W)
        dir_frame = ttk.Frame(download_frame)
        dir_frame.pack(fill=tk.X, pady=5)
        
        dir_entry = ttk.Entry(dir_frame)
        dir_entry.insert(0, self.settings.get("download_dir", str(Path("downloads").absolute())))
        dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        def choose_dir():
            dir_path = filedialog.askdirectory(initialdir=dir_entry.get())
            if dir_path:
                dir_entry.delete(0, tk.END)
                dir_entry.insert(0, dir_path)
                
        browse_btn = ttk.Button(dir_frame, text="Browse", command=choose_dir)
        browse_btn.pack(side=tk.RIGHT, padx=5)
        
        # Save button
        def save_settings():
            try:
                # Update settings
                self.settings.update({
                    "download_dir": dir_entry.get(),
                    "max_connections": int(max_conn.get()),
                    "split": int(split.get()),
                    "min_split_size": min_split.get(),
                    "user_agent": user_agent.get()
                })
                
                # Save to file
                self.save_settings()
                
                messagebox.showinfo("Sukses", "Pengaturan berhasil disimpan!")
                settings_window.destroy()
                
            except Exception as e:
                messagebox.showerror("Error", f"Gagal menyimpan pengaturan: {str(e)}")
                
        save_btn = ttk.Button(
            settings_window,
            text="Simpan",
            command=save_settings,
            style="Accent.TButton"
        )
        save_btn.pack(pady=10)
        
    def process_url(self):
        """Process the TeraBox URL and display file list."""
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("Error", "URL tidak boleh kosong!")
            return
            
        self.status_var.set("Memproses URL...")
        self.tree.delete(*self.tree.get_children())
        
        def process():
            try:
                from terabox1 import TeraboxFile
                # Get file information
                tf = TeraboxFile()
                tf.search(url)
                
                if tf.result['status'] != 'success':
                    raise Exception("Gagal mendapatkan informasi file!")
                    
                # Simpan informasi penting untuk download
                self.current_uk = tf.result['uk']
                self.current_shareid = tf.result['shareid']
                self.current_timestamp = tf.result['timestamp']
                self.current_sign = tf.result['sign']
                self.current_js_token = tf.result['js_token']
                self.current_cookie = tf.result['cookie']
                
                # Update UI with file list
                self.file_list_data = self.downloader.flatten_files(tf.result['list'])
                
                self.root.after(0, self.update_file_list)
                self.status_var.set("URL berhasil diproses")
                
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
                self.status_var.set("Error: " + str(e))
                self.logger.error(f"Error processing URL: {str(e)}")
                
        threading.Thread(target=process, daemon=True).start()
        
    def update_file_list(self):
        """Update the file list in Treeview."""
        self.tree.delete(*self.tree.get_children())
        
        for file in self.file_list_data:
            if not file['is_dir']:
                values = (
                    file['name'],
                    self.downloader._get_file_type(file['name']),
                    self.downloader.format_size(file['size']),
                    "Siap"
                )
                self.tree.insert("", tk.END, values=values, tags=(file['fs_id'],))
                
    def download_selected(self):
        """Download selected files from the Treeview."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Peringatan", "Pilih file terlebih dahulu!")
            return
            
        for item in selected:
            file_data = self.get_file_data(item)
            if file_data:
                self.queue_download(file_data)
                
    def download_all(self):
        """Download all files in the list."""
        if not self.file_list_data:
            messagebox.showwarning("Peringatan", "Tidak ada file untuk didownload!")
            return
            
        for file in self.file_list_data:
            if not file['is_dir']:
                self.queue_download(file)
                
    def queue_download(self, file_data: Dict[str, Any]):
        """Add a file to the download queue."""
        self.download_queue.put(file_data)
        
        if not hasattr(self, 'download_thread') or not self.download_thread.is_alive():
            self.download_thread = threading.Thread(target=self.process_download_queue)
            self.download_thread.daemon = True
            self.download_thread.start()
            
    def process_download_queue(self):
        """Process the download queue."""
        while True:
            try:
                file_data = self.download_queue.get(timeout=1)
            except queue.Empty:
                break
                
            try:
                self.download_file(file_data)
            except Exception as e:
                self.logger.error(f"Error downloading {file_data['name']}: {str(e)}")
                self.status_var.set(f"Error: {str(e)}")
                
            self.download_queue.task_done()
            
    def download_file(self, file_data: Dict[str, Any]):
        """Download a single file."""
        filename = None
        try:
            # Reset cancel flag
            self.cancel_flag.clear()
            # Enable cancel button
            self.root.after(0, lambda: self.cancel_btn.config(state=tk.NORMAL))
            
            # Get download link
            self.logger.info(f"Mengambil link download untuk {file_data['name']}...")
            from terabox1 import TeraboxLink
            tl = TeraboxLink(
                fs_id=str(file_data['fs_id']),
                uk=str(self.current_uk),
                shareid=str(self.current_shareid),
                timestamp=str(self.current_timestamp),
                sign=str(self.current_sign),
                js_token=str(self.current_js_token),
                cookie=str(self.current_cookie)
            )
            tl.generate()
            
            if tl.result['status'] != 'success':
                error_msg = f"Gagal mendapatkan link download: {tl.result.get('message', 'Unknown error')}"
                self.logger.error(error_msg)
                raise Exception(error_msg)
                
            # Get download URL and force d.terabox.com domain
            download_url = tl.result['download_link'].get('url_1', '')
            if not download_url:
                raise Exception("Tidak ada URL download yang valid!")
                
            # Pastikan menggunakan d.terabox.com
            download_url = download_url.replace('//cdn.', '//d.').replace('//c.', '//d.').replace('//b.', '//d.').replace('//a.', '//d.')
            self.logger.info(f"URL download: {download_url}")
                
            # Prepare download - gunakan direktori dari settings
            download_dir = Path(self.settings.get("download_dir", "downloads"))
            download_dir.mkdir(exist_ok=True)
            
            filename = download_dir / file_data['name']
            filesize = int(file_data['size'])
            
            # Start download
            self.status_var.set(f"Downloading: {file_data['name']}")
            self.logger.info(f"Memulai download {file_data['name']} ({self.downloader.format_size(filesize)})")
            
            # Update status di treeview
            for item in self.tree.get_children():
                if self.tree.item(item)['values'][0] == file_data['name']:
                    self.tree.set(item, "Status", "Downloading...")
                    break
            
            self.start_time = time.time()
            
            # Buat konfigurasi aria2 dengan trackers
            aria2_config = self.downloader._create_aria2_config()
            self.logger.info("Konfigurasi aria2 berhasil dibuat dengan trackers")
            
            # Tambahkan download ke aria2 dengan konfigurasi dari settings
            download = self.aria2.add_uris(
                [download_url],
                options={
                    "dir": str(download_dir),
                    "out": file_data['name'],
                    "max-connection-per-server": str(self.settings.get("max_connections", 16)),
                    "split": str(self.settings.get("split", 16)),
                    "min-split-size": self.settings.get("min_split_size", "1M"),
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
                    "allow-overwrite": "true",
                    "conf-path": aria2_config,
                    "check-integrity": "true",
                    "disk-cache": "64M",
                    "piece-length": "1M",
                    "enable-http-pipelining": "true",
                    "stream-piece-selector": "inorder",
                    "header": [
                        f"Cookie: {self.current_cookie}",
                        "Accept: */*",
                        "Accept-Language: en-US,en;q=0.9",
                        "Connection: keep-alive"
                    ]
                }
            )
            self.logger.info("Download berhasil ditambahkan ke aria2 dengan priority network")
            
            # Monitor progress
            last_update_time = time.time()
            last_downloaded = 0
            retry_count = 0
            max_retries = 3
            stall_time = 0
            last_progress_time = time.time()
            
            while not download.is_complete:
                if self.cancel_flag.is_set():
                    download.remove()
                    raise Exception("Download dibatalkan oleh pengguna")
                    
                try:
                    download.update()
                    current_time = time.time()
                    
                    if current_time - last_update_time >= 0.5:
                        downloaded = download.completed_length
                        speed = download.download_speed
                        
                        # Log progress lebih detail
                        progress = (downloaded / filesize) * 100
                        self.logger.info(f"Progress: {progress:.1f}% Speed: {self.downloader.format_size(speed)}/s Downloaded: {self.downloader.format_size(downloaded)} / {self.downloader.format_size(filesize)}")
                        
                        # Update UI
                        self.update_progress_ui(
                            file_data['name'],
                            downloaded,
                            filesize,
                            speed
                        )
                        
                        # Deteksi jika download stuck
                        if downloaded == last_downloaded:
                            stall_time = current_time - last_progress_time
                            if stall_time > 30:  # Jika stuck lebih dari 30 detik
                                retry_count += 1
                                self.logger.warning(f"Download stuck selama {stall_time:.1f} detik")
                                
                                if retry_count >= max_retries:
                                    # Coba restart download dengan parameter berbeda
                                    self.logger.info("Download stuck, mencoba restart dengan parameter berbeda...")
                                    download.remove()
                                    
                                    # Coba dengan parameter yang berbeda
                                    download = self.aria2.add_uris(
                                        [download_url],
                                        options={
                                            "dir": str(download_dir),
                                            "out": file_data['name'],
                                            "continue": "true",
                                            "max-connection-per-server": "8",  # Kurangi koneksi
                                            "split": "8",
                                            "min-split-size": "2M",  # Naikkan ukuran split
                                            "piece-length": "2M",
                                            "lowest-speed-limit": "1M",
                                            "stream-piece-selector": "random",  # Ganti ke random untuk mencoba
                                            "conf-path": aria2_config
                                        }
                                    )
                                    retry_count = 0
                                    stall_time = 0
                        else:
                            stall_time = 0
                            last_progress_time = current_time
                            retry_count = 0
                        
                        last_update_time = current_time
                        last_downloaded = downloaded
                        
                except Exception as e:
                    self.logger.error(f"Aria2 error: {str(e)}")
                    continue
                    
                time.sleep(0.1)
            
            # Verifikasi hasil download dengan lebih ketat
            if os.path.exists(filename):
                actual_size = os.path.getsize(filename)
                if actual_size == filesize:
                    # Coba baca file untuk memastikan integritas
                    try:
                        with open(filename, 'rb') as f:
                            # Baca file dalam chunks untuk verifikasi
                            chunk_size = 8192
                            while chunk := f.read(chunk_size):
                                pass
                        success = True
                        self.logger.info(f"File {file_data['name']} berhasil diverifikasi")
                    except Exception as e:
                        success = False
                        self.logger.error(f"File corrupt: {str(e)}")
                else:
                    success = False
                    self.logger.error(f"Ukuran file tidak sesuai. Expected: {filesize}, Actual: {actual_size}")
            else:
                success = False
                self.logger.error("File tidak ditemukan setelah download")
                
            # Update status akhir di treeview
            for item in self.tree.get_children():
                if self.tree.item(item)['values'][0] == file_data['name']:
                    status = "Selesai" if success else "Gagal"
                    if self.cancel_flag.is_set():
                        status = "Dibatalkan"
                    self.tree.set(item, "Status", status)
                    break
            
            if success and not self.cancel_flag.is_set():
                self.status_var.set(f"Berhasil download: {file_data['name']}")
            elif self.cancel_flag.is_set():
                self.status_var.set("Download dibatalkan")
                if os.path.exists(filename):
                    os.remove(filename)
            else:
                self.status_var.set(f"Gagal download: {file_data['name']}")
                if os.path.exists(filename):
                    os.remove(filename)
                
            # Reset progress UI
            self.root.after(0, lambda: [
                self.progress_var.set(0),
                self.current_file_label.config(text=""),
                self.speed_label.config(text=""),
                self.eta_label.config(text=""),
                self.progress_label.config(text="Siap untuk download..."),
                self.size_label.config(text=""),
                self.cancel_btn.config(state=tk.DISABLED)
            ])
                
        except Exception as e:
            self.logger.error(f"Error downloading {file_data['name']}: {str(e)}")
            self.status_var.set(f"Error: {str(e)}")
            # Update status error di treeview
            for item in self.tree.get_children():
                if self.tree.item(item)['values'][0] == file_data['name']:
                    status = "Error"
                    if "dibatalkan" in str(e):
                        status = "Dibatalkan"
                    self.tree.set(item, "Status", status)
                    break
            # Hapus file yang gagal
            if filename and os.path.exists(filename):
                os.remove(filename)
            # Disable cancel button
            self.root.after(0, lambda: self.cancel_btn.config(state=tk.DISABLED))
            
    def get_file_data(self, item: str) -> Optional[Dict[str, Any]]:
        """Get file data from Treeview item."""
        values = self.tree.item(item)['values']
        if not values:
            return None
            
        for file in self.file_list_data:
            if file['name'] == values[0]:
                return file
        return None
        
    def on_closing(self):
        """Handle application closing."""
        if messagebox.askokcancel("Keluar", "Yakin ingin keluar?"):
            self.root.quit()
            
    def run(self):
        """Start the GUI application."""
        self.root.mainloop()

    def update_progress_ui(self, file_name: str, downloaded: int, total: int, speed: float):
        """Update progress UI with download information."""
        try:
            # Calculate progress percentage
            progress = (downloaded / total) * 100
            
            # Calculate ETA
            if speed > 0:
                eta_seconds = (total - downloaded) / speed
                if eta_seconds < 60:
                    eta_text = f"ETA: {int(eta_seconds)} detik"
                elif eta_seconds < 3600:
                    eta_text = f"ETA: {int(eta_seconds/60)} menit"
                else:
                    eta_text = f"ETA: {int(eta_seconds/3600)} jam {int((eta_seconds%3600)/60)} menit"
            else:
                eta_text = "ETA: Menghitung..."
            
            # Format sizes
            current_size = self.downloader.format_size(downloaded)
            total_size = self.downloader.format_size(total)
            speed_text = f"{self.downloader.format_size(speed)}/s"
            
            # Update UI elements
            self.root.after(0, lambda: [
                self.progress_var.set(progress),
                self.current_file_label.config(text=file_name),
                self.speed_label.config(text=speed_text),
                self.eta_label.config(text=eta_text),
                self.progress_label.config(text=f"{progress:.1f}%"),
                self.size_label.config(text=f"{current_size} / {total_size}")
            ])
            
        except Exception as e:
            self.logger.error(f"Error updating progress UI: {str(e)}")

    def cancel_download(self):
        """Cancel the current download."""
        if messagebox.askyesno("Cancel Download", "Yakin ingin membatalkan download?"):
            self.cancel_flag.set()
            self.status_var.set("Membatalkan download...")
            self.cancel_btn.config(state=tk.DISABLED)

    def update_trackers(self):
        """Download dan update trackers dari GitHub."""
        try:
            # URL trackers dari dua sumber
            trackers_urls = [
                "https://raw.githubusercontent.com/ngosang/trackerslist/master/trackers_all.txt",
                "https://raw.githubusercontent.com/ngosang/trackerslist/master/trackers_best_ip.txt"
            ]
            
            # Path untuk file trackers
            trackers_file = Path("config/trackers.txt")
            
            # Hapus file lama jika ada
            if trackers_file.exists():
                trackers_file.unlink()
            
            # Download dan gabungkan trackers dari kedua sumber
            combined_trackers = set()  # Gunakan set untuk menghindari duplikat
            
            for url in trackers_urls:
                try:
                    response = requests.get(url)
                    response.raise_for_status()
                    # Tambahkan trackers ke set, hilangkan baris kosong
                    trackers = set(line.strip() for line in response.text.split('\n') if line.strip())
                    combined_trackers.update(trackers)
                    self.logger.info(f"Berhasil mengambil trackers dari {url}")
                except Exception as e:
                    self.logger.error(f"Error mengambil trackers dari {url}: {str(e)}")
            
            if combined_trackers:
                # Simpan trackers yang sudah digabung
                trackers_file.write_text('\n'.join(sorted(combined_trackers)))
                self.logger.info(f"Berhasil menyimpan {len(combined_trackers)} trackers unik")
            else:
                # Jika kedua sumber gagal, gunakan trackers default
                trackers_file.write_text(self.downloader._get_default_trackers())
                self.logger.info("Menggunakan trackers default karena gagal mengambil dari sumber online")
            
        except Exception as e:
            self.logger.error(f"Error updating trackers: {str(e)}")
            # Jika gagal total, gunakan trackers default
            if not trackers_file.exists():
                trackers_file.write_text(self.downloader._get_default_trackers())
                self.logger.info("Menggunakan trackers default")

    def _create_aria2_config(self) -> str:
        """Membuat konfigurasi aria2 dengan trackers dari file."""
        try:
            # Baca trackers dari file
            trackers_file = Path("config/trackers.txt")
            if not trackers_file.exists():
                self.update_trackers()
            
            trackers = trackers_file.read_text().strip()
            
            # Buat konfigurasi
            config = {
                'max-connection-per-server': str(self.settings.get("max_connections", 16)),
                'min-split-size': self.settings.get("min_split_size", "1M"),
                'split': str(self.settings.get("split", 16)),
                'max-concurrent-downloads': "1",
                'continue': 'true',
                'max-tries': '0',
                'retry-wait': '3',
                'user-agent': self.settings.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"),
                'bt-tracker': trackers.replace('\n', ','),
                'enable-dht': 'true',
                'enable-peer-exchange': 'true',
                'bt-enable-lpd': 'true',
                'bt-max-peers': '0',
                'bt-request-peer-speed-limit': '50M',
                'seed-ratio': '0.0'
            }
            
            # Simpan konfigurasi
            config_path = Path('aria2.conf')
            with open(config_path, 'w') as f:
                for key, value in config.items():
                    f.write(f'{key}={value}\n')
                
            return str(config_path)
            
        except Exception as e:
            self.logger.error(f"Error creating aria2 config: {str(e)}")
            # Gunakan konfigurasi dari CLI jika gagal
            return self.downloader._create_aria2_config()

def main():
    """Main entry point for the TeraBox GUI application."""
    app = TeraboxGUI()
    app.run()

if __name__ == "__main__":
    main() 