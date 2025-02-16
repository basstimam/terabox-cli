import tkinter as tk
from tkinter import ttk, messagebox, filedialog
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
import requests
from io import BytesIO
import webbrowser
import time
import subprocess
import aria2p
import multiprocessing
import sv_ttk
from PIL import Image, ImageTk
from concurrent.futures import ThreadPoolExecutor

class TeraboxGUI:
    """
    GUI implementation for TeraBox Downloader using tkinter and ttkthemes.
    
    This class provides a modern and user-friendly interface for downloading files from TeraBox,
    implementing all features from the CLI version with additional GUI conveniences.
    """
    
    def __init__(self):
        """Initialize the TeraBox GUI application."""
        # Cache untuk menyimpan data file yang sering diakses
        self._file_cache = {}
        self._last_file_check = 0
        self._cache_timeout = 300  # 5 menit
        
        # Queue untuk update UI
        self._ui_update_queue = queue.Queue()
        self._ui_update_running = False
        
        self.root = tk.Tk()  # Gunakan tk.Tk() untuk Sun Valley theme
        self.root.title("Trauso")
        
        # Setup logging first
        self.setup_logging()
        
        # Set window icon
        try:
            # Convert SVG to PNG using PIL
            svg_path = Path("icon/box.svg")
            if svg_path.exists():
                from cairosvg import svg2png
                png_data = svg2png(url=str(svg_path), output_width=64, output_height=64)
                icon_image = Image.open(BytesIO(png_data))
                icon_photo = ImageTk.PhotoImage(icon_image)
                self.root.iconphoto(True, icon_photo)
                self.logger.info("Berhasil mengatur ikon program")
        except Exception as e:
            self.logger.error(f"Error mengatur ikon: {str(e)}")
        
        self.root.geometry("1000x700")
        self.root.minsize(800, 600)

        # Apply Sun Valley theme
        sv_ttk.set_theme("light")
        
        # Initialize downloader dengan thread pool
        self.downloader = TeraboxDownloader()
        self.console = Console()
        self.download_queue = queue.Queue()
        self.current_downloads = {}
        
        # Setup thread pool untuk download
        self.download_pool = ThreadPoolExecutor(max_workers=min(32, multiprocessing.cpu_count() * 4))
        
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
        
        # Load download history
        self.history_file = Path("config/download_history.json")
        self.history_file.parent.mkdir(exist_ok=True)
        self.download_history = self.load_download_history()
        
        # Create main container dengan padding yang lebih kecil
        self.main_container = ttk.Frame(self.root)
        self.main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create and setup UI components
        self.create_header()
        self.create_url_input()
        self.create_file_list()
        self.create_download_progress()
        self.create_status_bar()
        
        # Initialize variables
        self.current_url = ""
        self.file_list_data = []
        
        # Bind events
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Cek pembaruan saat startup
        self.root.after(1000, self.check_updates_on_startup)  # Cek setelah 1 detik
        
    def setup_styles(self):
        """Setup custom styles for widgets."""
        style = ttk.Style()
        
        # Konfigurasi style untuk tombol accent
        style.configure("Accent.TButton",
            font=("Segoe UI", 9)
        )
        
        style.configure("TButton",
            font=("Segoe UI", 9)
        )
        
        style.configure("TLabel",
            font=("Segoe UI", 9)
        )
        
        style.configure("Header.TLabel",
            font=("Segoe UI", 16, "bold")
        )
        
        style.configure("Subheader.TLabel",
            font=("Segoe UI", 9)
        )
        
        style.configure("TEntry",
            font=("Segoe UI", 9)
        )
        
        style.configure("Treeview",
            font=("Segoe UI", 9),
            rowheight=25
        )
        
        style.configure("Treeview.Heading",
            font=("Segoe UI", 9, "bold")
        )
        
        style.configure("Horizontal.TProgressbar",
            thickness=20
        )
        
        style.configure("TLabelframe",
            padding=5
        )
        
        # Add theme toggle button
        self.theme_button = ttk.Button(
            self.main_container,
            text="🌓",
            command=self.toggle_theme,
            style="TButton",
            width=3
        )
        self.theme_button.pack(side=tk.RIGHT, padx=(0, 5), pady=(0, 10))
        
    def toggle_theme(self):
        """Toggle between light and dark theme."""
        if sv_ttk.get_theme() == "dark":
            sv_ttk.set_theme("light")
        else:
            sv_ttk.set_theme("dark")
            
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
            if not local_aria2.exists():
                local_aria2 = Path("_internal/aria2/aria2c.exe")
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
                
                # Gunakan CREATE_NO_WINDOW flag untuk mencegah munculnya console window
                startupinfo = None
                if os.name == 'nt':  # Windows
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    startupinfo.wShowWindow = subprocess.SW_HIDE
                
                subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    startupinfo=startupinfo,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                
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
            messagebox.showwarning("Warning", "aria2 tidak ditemukan, download mungkin akan lebih lambat")
            return False
            
        except Exception as e:
            self.logger.error(f"Error setting up aria2: {str(e)}")
            messagebox.showerror("Error", f"Gagal setup aria2: {str(e)}")
            return False
        
    def create_header(self):
        """Create the header section with logo and title."""
        header_frame = ttk.Frame(self.main_container)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        # Container untuk tombol donate di kiri
        donate_container = ttk.Frame(header_frame)
        donate_container.pack(side=tk.LEFT, padx=5)

        # Donate button
        donate_btn = ttk.Button(
            donate_container,
            text="☕ Donate",
            command=self.open_donate_link,
            style="TButton"
        )
        donate_btn.pack(side=tk.LEFT)
        
        # Container untuk logo dan judul
        title_container = ttk.Frame(header_frame)
        title_container.pack(expand=True)
        
        # Logo
        logo_label = ttk.Label(
            title_container,
            text="📦",
            style="Header.TLabel"
        )
        logo_label.pack(side=tk.LEFT, padx=5)
        
        # Title
        title_label = ttk.Label(
            title_container,
            text="Trauso",
            style="Header.TLabel"
        )
        title_label.pack(side=tk.LEFT)
        
        # Subtitle
        subtitle = ttk.Label(
            header_frame,
            text="A lightning fast terabox downloader",
            style="Subheader.TLabel"
        )
        subtitle.pack(pady=2)
        
    def create_url_input(self):
        """Create the URL input section."""
        url_frame = ttk.LabelFrame(
            self.main_container,
            text="TeraBox URL",
            padding=5
        )
        url_frame.pack(fill=tk.X, pady=(0, 10), padx=5)
        
        # URL Entry dengan padding
        self.url_var = tk.StringVar()
        url_entry = ttk.Entry(
            url_frame,
            textvariable=self.url_var,
            font=("Segoe UI", 9)
        )
        url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 10))
        
        # Process Button dengan style accent
        process_btn = ttk.Button(
            url_frame,
            text="Process URL",
            command=self.process_url,
            style="Accent.TButton"
        )
        process_btn.pack(side=tk.RIGHT)
        
    def create_file_list(self):
        """Create the file list section with Treeview."""
        list_frame = ttk.LabelFrame(
            self.main_container,
            text="File List",
            padding=5
        )
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10), padx=5)
        
        # Container untuk treeview dan tombol
        tree_container = ttk.Frame(list_frame)
        tree_container.pack(fill=tk.BOTH, expand=True)
        
        # Create Treeview dengan style modern
        columns = ("Name", "Type", "Size", "Status")
        self.tree = ttk.Treeview(
            tree_container,
            columns=columns,
            show="headings",
            style="Treeview"
        )
        
        # Setup columns dengan proporsi yang lebih baik
        self.tree.heading("Name", text="File Name")
        self.tree.heading("Type", text="Type")
        self.tree.heading("Size", text="Size")
        self.tree.heading("Status", text="Status")
        
        self.tree.column("Name", width=400)
        self.tree.column("Type", width=80)
        self.tree.column("Size", width=100)
        self.tree.column("Status", width=100)
        
        # Scrollbar yang menyatu dengan Treeview
        scrollbar = ttk.Scrollbar(tree_container, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack elements dengan padding
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Button frame dengan layout yang lebih rapi
        btn_frame = ttk.Frame(list_frame)
        btn_frame.pack(fill=tk.X, pady=(5, 0))
        
        # Container untuk tombol download di kiri
        download_container = ttk.Frame(btn_frame)
        download_container.pack(side=tk.LEFT)
        
        # Download buttons dengan style yang konsisten
        download_btn = ttk.Button(
            download_container,
            text="Download Selected",
            command=self.download_selected,
            style="Accent.TButton"
        )
        download_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        download_all_btn = ttk.Button(
            download_container,
            text="Download All",
            command=self.download_all,
            style="Accent.TButton"
        )
        download_all_btn.pack(side=tk.LEFT)
        
        # Container untuk tombol di kanan
        right_btn_container = ttk.Frame(btn_frame)
        right_btn_container.pack(side=tk.RIGHT)

        # Theme toggle button
        theme_btn = ttk.Button(
            right_btn_container,
            text="🌓",
            command=self.toggle_theme,
            style="TButton",
            width=3
        )
        theme_btn.pack(side=tk.LEFT, padx=(0, 5))

        # History button
        history_btn = ttk.Button(
            right_btn_container,
            text="📋 History",
            command=self.show_download_history,
            style="TButton"
        )
        history_btn.pack(side=tk.LEFT, padx=(0, 5))

        # Settings button
        settings_btn = ttk.Button(
            right_btn_container,
            text="⚙️ Settings",
            command=self.show_settings,
            style="TButton"
        )
        settings_btn.pack(side=tk.LEFT)
        
    def create_download_progress(self):
        """Create the download progress section."""
        progress_frame = ttk.LabelFrame(
            self.main_container,
            text="Download Progress",
            padding=5
        )
        progress_frame.pack(fill=tk.X, pady=(0, 10), padx=5)
        
        # Progress info frame dengan layout yang lebih baik
        info_frame = ttk.Frame(progress_frame)
        info_frame.pack(fill=tk.X, pady=(0, 5))
        
        # File name label dengan style yang konsisten
        self.current_file_label = ttk.Label(
            info_frame,
            text="",
            style="TLabel"
        )
        self.current_file_label.pack(side=tk.LEFT)
        
        # Speed and ETA frame
        stats_frame = ttk.Frame(info_frame)
        stats_frame.pack(side=tk.RIGHT)
        
        self.speed_label = ttk.Label(
            stats_frame,
            text="",
            style="TLabel"
        )
        self.speed_label.pack(side=tk.LEFT, padx=5)
        
        self.eta_label = ttk.Label(
            stats_frame,
            text="",
            style="TLabel"
        )
        self.eta_label.pack(side=tk.LEFT)
        
        # Progress bar frame dengan layout yang lebih baik
        bar_frame = ttk.Frame(progress_frame)
        bar_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Progress bar yang lebih tebal dan modern
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            bar_frame,
            variable=self.progress_var,
            mode='determinate',
            style="Horizontal.TProgressbar"
        )
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        # Cancel button dengan style yang konsisten
        self.cancel_btn = ttk.Button(
            bar_frame,
            text="❌ Cancel",
            command=self.cancel_download,
            state=tk.DISABLED
        )
        self.cancel_btn.pack(side=tk.RIGHT)
        
        # Progress details dengan layout yang lebih baik
        details_frame = ttk.Frame(progress_frame)
        details_frame.pack(fill=tk.X)
        
        self.progress_label = ttk.Label(
            details_frame,
            text="Ready to download...",
            style="TLabel"
        )
        self.progress_label.pack(side=tk.LEFT)
        
        self.size_label = ttk.Label(
            details_frame,
            text="",
            style="TLabel"
        )
        self.size_label.pack(side=tk.RIGHT)
        
        # Inisialisasi flag cancel
        self.cancel_flag = threading.Event()
        
    def create_status_bar(self):
        """Create the status bar."""
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        
        status_bar = ttk.Label(
            self.main_container,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            padding=5,
            style="TLabel"
        )
        status_bar.pack(fill=tk.X, side=tk.BOTTOM, padx=5)
        
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
        settings_window.title("Settings")
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
        ttk.Label(aria2_frame, text="Aria2 Configuration").pack(anchor=tk.W)
        
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

        # About Settings
        about_frame = ttk.Frame(notebook, padding=10)
        notebook.add(about_frame, text="About")

        # Add version and author info
        version_container = ttk.Frame(about_frame)
        version_container.pack(fill=tk.X, pady=5)
        
        version_label = ttk.Label(
            version_container,
            text=f"Version: {self.get_version()}",
            style="TLabel"
        )
        version_label.pack(side=tk.LEFT, pady=5)
        
        check_update_btn = ttk.Button(
            version_container,
            text="🔄 Check Update",
            command=self.check_for_updates,
            style="TButton"
        )
        check_update_btn.pack(side=tk.RIGHT, pady=5)

        author_label = ttk.Label(
            about_frame,
            text="Author: arumam",
            style="TLabel"
        )
        author_label.pack(pady=5)

        donate_label = ttk.Label(
            about_frame,
            text="Support development:",
            style="TLabel"
        )
        donate_label.pack(pady=5)

        donate_btn = ttk.Button(
            about_frame,
            text="☕ Donate on Saweria",
            command=self.open_donate_link,
            style="Accent.TButton"
        )
        donate_btn.pack(pady=5)
        
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
                
                messagebox.showinfo("Success", "Settings saved successfully!")
                settings_window.destroy()
                
            except Exception as e:
                messagebox.showerror("Error", f"Gagal menyimpan pengaturan: {str(e)}")
                
        save_btn = ttk.Button(
            settings_window,
            text="Save",
            command=save_settings,
            style="Accent.TButton"
        )
        save_btn.pack(pady=10)
        
    def process_url(self):
        """Process the TeraBox URL and display file list."""
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("Error", "URL cannot be empty!")
            return
            
        self.status_var.set("Processing URL...")
        self.tree.delete(*self.tree.get_children())
        
        def process():
            try:
                # Cek cache
                current_time = time.time()
                if url in self._file_cache and current_time - self._last_file_check < self._cache_timeout:
                    self.file_list_data = self._file_cache[url]
                    self.root.after(0, self.update_file_list)
                    self.status_var.set("URL processed successfully (cached)")
                    return
                    
                from terabox1 import TeraboxFile
                # Get file information
                tf = TeraboxFile()
                tf.search(url)
                
                if tf.result['status'] != 'success':
                    raise Exception("Failed to get file information!")
                    
                # Save important information for download
                self.current_uk = tf.result['uk']
                self.current_shareid = tf.result['shareid']
                self.current_timestamp = tf.result['timestamp']
                self.current_sign = tf.result['sign']
                self.current_js_token = tf.result['js_token']
                self.current_cookie = tf.result['cookie']
                
                # Update UI with file list
                self.file_list_data = self.downloader.flatten_files(tf.result['list'])
                
                # Update cache
                self._file_cache[url] = self.file_list_data
                self._last_file_check = current_time
                
                self.root.after(0, self.update_file_list)
                self.status_var.set("URL processed successfully")
                
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
                    "Ready"
                )
                self.tree.insert("", tk.END, values=values, tags=(file['fs_id'],))
                
    def download_selected(self):
        """Download selected files from the Treeview."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select files to download!")
            return
            
        for item in selected:
            file_data = self.get_file_data(item)
            if file_data:
                self.queue_download(file_data)
                
    def download_all(self):
        """Download all files in the list."""
        if not self.file_list_data:
            messagebox.showwarning("Warning", "No files to download!")
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
            self.logger.info(f"Getting download link for {file_data['name']}...")
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
            self.logger.info(f"Starting download {file_data['name']} ({self.downloader.format_size(filesize)})")
            
            # Update status in treeview
            for item in self.tree.get_children():
                if self.tree.item(item)['values'][0] == file_data['name']:
                    self.tree.set(item, "Status", "Downloading...")
                    break
            
            self.start_time = time.time()
            
            # Buat konfigurasi aria2 dengan trackers
            aria2_config = self.downloader._create_aria2_config()
            self.logger.info("Konfigurasi aria2 berhasil dibuat dengan trackers")
            
            # Tambahkan download ke aria2 dengan konfigurasi dari settings dan optimasi
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
                    "optimize-concurrent-downloads": "true",
                    "async-dns": "true",
                    "enable-mmap": "true",
                    "header": [
                        f"Cookie: {self.current_cookie}",
                        "Accept: */*",
                        "Accept-Language: en-US,en;q=0.9",
                        "Connection: keep-alive"
                    ]
                }
            )
            self.logger.info("Download berhasil ditambahkan ke aria2 dengan priority network")
            
            # Monitor progress dengan optimasi
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
                    
                    # Batasi update progress ke 4 kali per detik
                    if current_time - last_update_time >= 0.25:
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
                        
                        # Deteksi jika download stuck dengan optimasi
                        if downloaded == last_downloaded:
                            stall_time = current_time - last_progress_time
                            if stall_time > 30:  # Jika stuck lebih dari 30 detik
                                retry_count += 1
                                self.logger.warning(f"Download stuck selama {stall_time:.1f} detik")
                                
                                if retry_count >= max_retries:
                                    # Coba restart download dengan parameter berbeda dan optimasi
                                    self.logger.info("Download stuck, mencoba restart dengan parameter berbeda...")
                                    download.remove()
                                    
                                    # Coba dengan parameter yang berbeda dan optimasi
                                    download = self.aria2.add_uris(
                                        [download_url],
                                        options={
                                            "dir": str(download_dir),
                                            "out": file_data['name'],
                                            "continue": "true",
                                            "max-connection-per-server": "8",
                                            "split": "8",
                                            "min-split-size": "2M",
                                            "piece-length": "2M",
                                            "lowest-speed-limit": "1M",
                                            "stream-piece-selector": "random",
                                            "optimize-concurrent-downloads": "true",
                                            "async-dns": "true",
                                            "enable-mmap": "true",
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
                
            # Update final status in treeview
            for item in self.tree.get_children():
                if self.tree.item(item)['values'][0] == file_data['name']:
                    status = "Completed" if success else "Failed"
                    if self.cancel_flag.is_set():
                        status = "Cancelled"
                    self.tree.set(item, "Status", status)
                    break
            
            if success and not self.cancel_flag.is_set():
                self.status_var.set(f"Successfully downloaded: {file_data['name']}")
                self.add_to_history(file_data, "Completed")
            elif self.cancel_flag.is_set():
                self.status_var.set("Download cancelled")
                self.add_to_history(file_data, "Cancelled")
                if os.path.exists(filename):
                    os.remove(filename)
            else:
                self.status_var.set(f"Failed to download: {file_data['name']}")
                self.add_to_history(file_data, "Failed")
                if os.path.exists(filename):
                    os.remove(filename)
                
            # Reset progress UI
            self.root.after(0, lambda: [
                self.progress_var.set(0),
                self.current_file_label.config(text=""),
                self.speed_label.config(text=""),
                self.eta_label.config(text=""),
                self.progress_label.config(text="Ready to download..."),
                self.size_label.config(text=""),
                self.cancel_btn.config(state=tk.DISABLED)
            ])
                
        except Exception as e:
            self.logger.error(f"Error downloading {file_data['name']}: {str(e)}")
            self.status_var.set(f"Error: {str(e)}")
            self.add_to_history(file_data, "Error")
            # Update status error di treeview
            for item in self.tree.get_children():
                if self.tree.item(item)['values'][0] == file_data['name']:
                    status = "Cancelled"
                    if "dibatalkan" in str(e):
                        status = "Cancelled"
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
        if messagebox.askokcancel("Exit", "Are you sure you want to exit?"):
            # Kill proses aria2c.exe sebelum menutup aplikasi
            self.kill_aria2_process()
            self.root.quit()
            
    def run(self):
        """Start the GUI application."""
        self.root.mainloop()

    def update_progress_ui(self, file_name: str, downloaded: int, total: int, speed: float):
        """Update progress UI with download information."""
        try:
            # Batasi update UI ke maksimal 4 kali per detik untuk mengurangi beban
            current_time = time.time()
            if not hasattr(self, '_last_ui_update') or current_time - self._last_ui_update >= 0.25:
                self._last_ui_update = current_time
                
                # Calculate progress percentage
                progress = (downloaded / total) * 100
                
                # Calculate ETA
                if speed > 0:
                    eta_seconds = (total - downloaded) / speed
                    if eta_seconds < 60:
                        eta_text = f"ETA: {int(eta_seconds)} seconds"
                    elif eta_seconds < 3600:
                        eta_text = f"ETA: {int(eta_seconds/60)} minutes"
                    else:
                        eta_text = f"ETA: {int(eta_seconds/3600)} hours {int((eta_seconds%3600)/60)} minutes"
                else:
                    eta_text = "ETA: Calculating..."
                
                # Format sizes
                current_size = self.downloader.format_size(downloaded)
                total_size = self.downloader.format_size(total)
                speed_text = f"{self.downloader.format_size(speed)}/s"
                
                # Queue update UI untuk diproses di thread utama
                self._ui_update_queue.put({
                    'progress': progress,
                    'file_name': file_name,
                    'speed': speed_text,
                    'eta': eta_text,
                    'progress_text': f"{progress:.1f}%",
                    'size_text': f"{current_size} / {total_size}"
                })
                
                # Start UI update thread jika belum berjalan
                if not self._ui_update_running:
                    self._start_ui_update_thread()
                
        except Exception as e:
            self.logger.error(f"Error updating progress UI: {str(e)}")
            
    def _start_ui_update_thread(self):
        """Start thread untuk update UI."""
        def update_ui():
            self._ui_update_running = True
            while True:
                try:
                    # Get semua update yang tersedia
                    updates = []
                    while not self._ui_update_queue.empty():
                        updates.append(self._ui_update_queue.get_nowait())
                    
                    if not updates:
                        self._ui_update_running = False
                        break
                        
                    # Ambil update terakhir saja
                    update = updates[-1]
                    
                    # Update UI elements
                    self.root.after(0, lambda: [
                        self.progress_var.set(update['progress']),
                        self.current_file_label.config(text=update['file_name']),
                        self.speed_label.config(text=update['speed']),
                        self.eta_label.config(text=update['eta']),
                        self.progress_label.config(text=update['progress_text']),
                        self.size_label.config(text=update['size_text'])
                    ])
                    
                    time.sleep(0.25)  # Limit update rate
                    
                except queue.Empty:
                    self._ui_update_running = False
                    break
                except Exception as e:
                    self.logger.error(f"Error in UI update thread: {str(e)}")
                    self._ui_update_running = False
                    break
                    
        threading.Thread(target=update_ui, daemon=True).start()

    def cancel_download(self):
        """Cancel the current download."""
        if messagebox.askyesno("Cancel Download", "Are you sure you want to cancel the download?"):
            self.cancel_flag.set()
            self.status_var.set("Cancelling download...")
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

    def load_download_history(self) -> List[Dict[str, Any]]:
        """Load download history from JSON file."""
        try:
            if self.history_file.exists():
                with open(self.history_file, 'r') as f:
                    history = json.load(f)
                    self.logger.info("Successfully loaded download history")
                    return history
        except Exception as e:
            self.logger.error(f"Error loading download history: {str(e)}")
        return []

    def save_download_history(self):
        """Save download history to JSON file."""
        try:
            with open(self.history_file, 'w') as f:
                json.dump(self.download_history, f, indent=4)
            self.logger.info("Successfully saved download history")
        except Exception as e:
            self.logger.error(f"Error saving download history: {str(e)}")

    def add_to_history(self, file_data: Dict[str, Any], status: str):
        """Add a download to history."""
        download_dir = Path(self.settings.get("download_dir", "downloads"))
        file_path = str(download_dir / file_data['name'])
        
        history_entry = {
            "name": file_data['name'],
            "size": file_data['size'],
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": status,
            "location": file_path
        }
        self.download_history.insert(0, history_entry)  # Add to start of list
        if len(self.download_history) > 100:  # Keep only last 100 entries
            self.download_history = self.download_history[:100]
        self.save_download_history()

    def show_download_history(self):
        """Show download history window."""
        history_window = tk.Toplevel(self.root)
        history_window.title("Download History")
        history_window.geometry("1000x500")  # Perbesar window untuk menampung kolom lokasi
        history_window.transient(self.root)
        history_window.grab_set()

        # Create treeview for history
        columns = ("Name", "Size", "Date", "Status", "Location")
        tree = ttk.Treeview(
            history_window,
            columns=columns,
            show="headings",
            style="Treeview"
        )

        # Setup columns
        tree.heading("Name", text="File Name")
        tree.heading("Size", text="Size")
        tree.heading("Date", text="Date")
        tree.heading("Status", text="Status")
        tree.heading("Location", text="Location")

        tree.column("Name", width=200)
        tree.column("Size", width=100)
        tree.column("Date", width=150)
        tree.column("Status", width=100)
        tree.column("Location", width=400)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(history_window, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        # Pack elements
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)

        # Add clear history button
        btn_frame = ttk.Frame(history_window)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)

        clear_btn = ttk.Button(
            btn_frame,
            text="Clear History",
            command=lambda: self.clear_history(tree)
        )
        clear_btn.pack(side=tk.RIGHT)

        # Populate treeview
        for entry in self.download_history:
            tree.insert("", tk.END, values=(
                entry['name'],
                self.downloader.format_size(entry['size']),
                entry['date'],
                entry['status'],
                entry.get('location', 'N/A')  # Gunakan N/A jika lokasi tidak ada (untuk kompatibilitas dengan riwayat lama)
            ))

    def clear_history(self, tree: ttk.Treeview):
        """Clear download history."""
        if messagebox.askyesno("Clear History", "Are you sure you want to clear download history?"):
            self.download_history = []
            self.save_download_history()
            for item in tree.get_children():
                tree.delete(item)

    def open_donate_link(self):
        """Open donate link in browser."""
        webbrowser.open("https://saweria.co/arumam")

    def get_version(self):
        """Get application version."""
        return "1.0.0"  # Versi statis untuk saat ini

    def check_for_updates(self) -> None:
        """Cek pembaruan dari GitHub repository."""
        try:
            # URL API GitHub untuk mengecek rilis terbaru
            api_url = "https://api.github.com/repos/basstimam/terabox-cli/releases/latest"
            
            response = requests.get(api_url)
            response.raise_for_status()
            
            latest_release = response.json()
            latest_version = latest_release['tag_name'].lstrip('v')
            current_version = self.get_version()
            
            if latest_version > current_version:
                # Ada versi baru tersedia
                message = f"Versi baru tersedia!\n\nVersi saat ini: {current_version}\nVersi terbaru: {latest_version}\n\nApakah Anda ingin mengunduh versi terbaru?"
                if messagebox.askyesno("Update Tersedia", message):
                    webbrowser.open(latest_release['html_url'])
            else:
                messagebox.showinfo("Check Update", "Anda sudah menggunakan versi terbaru!")
            
        except Exception as e:
            self.logger.error(f"Error checking for updates: {str(e)}")
            messagebox.showerror("Error", "Gagal mengecek pembaruan. Silakan coba lagi nanti.")

    def check_updates_on_startup(self) -> None:
        """Cek pembaruan saat aplikasi pertama kali dijalankan."""
        try:
            # URL API GitHub untuk mengecek rilis terbaru
            api_url = "https://api.github.com/repos/arumam1/terabox-downloader-cli/releases/latest"
            
            response = requests.get(api_url)
            response.raise_for_status()
            
            latest_release = response.json()
            latest_version = latest_release['tag_name'].lstrip('v')
            current_version = self.get_version()
            
            if latest_version > current_version:
                # Ada versi baru tersedia
                message = f"Versi baru tersedia!\n\nVersi saat ini: {current_version}\nVersi terbaru: {latest_version}\n\nApakah Anda ingin mengunduh versi terbaru?"
                if messagebox.askyesno("Update Tersedia", message):
                    webbrowser.open(latest_release['html_url'])
            
        except Exception as e:
            self.logger.error(f"Error checking for updates on startup: {str(e)}")
            # Tidak perlu menampilkan pesan error ke user saat startup

    def kill_aria2_process(self):
        """Kill proses aria2c.exe saat program ditutup."""
        try:
            # Gunakan taskkill untuk mematikan proses aria2c.exe
            subprocess.run(['taskkill', '/F', '/IM', 'aria2c.exe'], 
                         stdout=subprocess.DEVNULL, 
                         stderr=subprocess.DEVNULL)
            self.logger.info("Berhasil mematikan proses aria2c.exe")
        except Exception as e:
            self.logger.error(f"Error saat mematikan proses aria2c.exe: {str(e)}")

def main():
    """Main entry point for the TeraBox GUI application."""
    app = TeraboxGUI()
    app.run()

if __name__ == "__main__":
    main() 