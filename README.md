# TeraBox Downloader CLI/GUI

A fast and easy-to-use TeraBox file downloader application. Available in both Command Line Interface (CLI) and Graphical User Interface (GUI) versions.

![TeraBox Downloader Screenshot](screenshots/app.png)

## ✨ Features

- 🚀 Aria2-based download manager for maximum speed
- 📂 Multiple file download support
- 🎯 Resume interrupted downloads
- 📊 Real-time progress bar
- 📋 Download history
- ⚙️ Flexible download configuration settings
- 🌙 Dark/Light mode (GUI version)
- 💻 Modern interface with Sun Valley theme (GUI version)

## 🔧 System Requirements

- Windows 10 or newer
- Python 3.8+
- Internet connection

## 📥 Installation

### Method 1: Download Executable (Recommended)

1. Download the latest version from [Releases](https://github.com/basstimam/terabox-cli/releases)
2. Extract the zip file to your desired folder
3. Run `Trauso.exe`


## 📚 Usage

### GUI Version

1. Run `Trauso.exe` 
2. Paste your TeraBox URL
3. Click "Process URL"
4. Select the files you want to download
5. Click "Download Selected" or "Download All"


## ⚙️ Configuration

Settings can be modified through:
- GUI: Settings Menu
- CLI: `config/settings.json` file

Available settings:
- Download directory
- Maximum connections
- Download splitting
- Minimum split size
- User agent

## 📋 Detailed Features

### Download Manager
- Aria2-based for maximum performance
- Multi-connection download
- Resume interrupted downloads
- Bandwidth management

### Interface (GUI)
- Modern Sun Valley theme
- Dark/Light mode
- Real-time progress bar
- Download history
- File browser

### Security
- No sensitive data storage
- File integrity verification
- Troubleshooting logs

## 🔍 Troubleshooting

### Download Failed
1. Ensure the TeraBox URL is valid and active
2. Check your internet connection
3. Try using a VPN if needed
4. Check the `logs` folder for detailed errors

### "Not a valid Win32 application" Error
1. Make sure you're using Windows 10 or newer
2. Reinstall the application
3. Run as Administrator

## 📝 Notes

- Files are downloaded to the `downloads` folder (default)
- Application logs are stored in the `logs` folder
- Settings are saved in the `config` folder
- The `aria2` folder contains aria2c.exe used for downloading

## 🤝 Contributing

Contributions are always welcome! Please feel free to submit Pull Requests or create Issues for bugs/suggestions.

## 📄 License

This project is licensed under the [MIT License](LICENSE)

## ☕ Support

If you find this application helpful, you can support the development through:

[![Saweria](https://img.shields.io/badge/Saweria-Support%20via%20Saweria-orange)](https://saweria.co/arumam)

## 📞 Contact

- GitHub: [@basstimam](https://github.com/basstimam)
- Email: [basstimam@gmail.com]

## 🙏 Credits

- Icon by [Author]
- Sun Valley theme by [rdbende](https://github.com/rdbende/Sun-Valley-ttk-theme) 