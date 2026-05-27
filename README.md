# llama.cpp Windows Launcher

A lightweight, retro Windows 95 styled desktop launcher for `llama.cpp` builds. This GUI launcher is designed to easily configure, manage, and run both `llama-server` and `llama-cli` alongside your GGUF models.

![Windows 95 Style](https://img.shields.io/badge/Style-Windows_95-grey?style=flat-square)
![PyQt6](https://img.shields.io/badge/Built_with-PyQt6-blue?style=flat-square)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey?style=flat-square)

<p align="center">
<img width="391" height="361" alt="3" src="https://github.com/user-attachments/assets/6ed41805-56fa-49a6-ae5c-0f3408512003" />
<img width="392" height="556" alt="2" src="https://github.com/user-attachments/assets/df149107-ccc0-4034-9445-65c2e11f7959" />
<img width="392" height="361" alt="1" src="https://github.com/user-attachments/assets/d842e328-6dee-47a1-84c9-3aa3fbc880ed" />
</p>


---

## Key Features

- **Retro Win95 Aesthetic**: Built using a custom stylesheet mimicking the classic Windows 95 Tahoma-driven, bevel-bordered graphical layout.
- **Dynamic Window Resizing**: Automatically adapts window dimensions per active view—shrinking to an ultra-compact `380x310px` on the Home screen to eliminate dead vertical space, while expanding gracefully during detailed configuration.
- **Smart Autodetection Wizard**: Spawns an algorithmic helper that queries your hardware VRAM, executes `llama-cli --info` to extract model metadata, calculates quantization load weights, and proposes optimized parameters (NGL layers, context size, threads, temp, template) for your exact GPU capacity.
- **Modular Presets**: Presets are structured as independent JSON files stored in the `/presets` folder, allowing easy sharing, backing up, or manual editing.
- **Safe Scroll prevents Accidental Changes**: Standard Qt wheel scroll actions are ignored on dropdowns and numeric boxes to avoid accidental parameter changes while navigating the settings page.
- **Automatic Model Sync**: Changing your model on the home screen automatically saves the selection inside your active preset file. Switching presets automatically reloads the associated GGUF model.
- **Integrated Actions**: Built-in triggers to launch standard performance benchmarks (`llama-bench`) or open the `llama-server` web interface locally with a single click.

---

## File Structure

```text
├── presets/             # Directory containing saved preset JSON files
├── build.bat            # Compiles the Python script into a standalone .exe
├── launcher.bat         # Sets up local virtual environment, installs PyQt6 and runs run.py
├── run.py               # Core PyQt6 Python application
├── logo.svg             # Application window icon (Scalable vector format)
├── logo.ico             # Desktop binary executable icon resource (Windows native)
└── logo_full.png        # Graphical logo displayed inside the main home view
```

---

## How to Install and Run (Local Mode)

### Prerequisites
- [Python 3.8+](https://www.python.org/downloads/) installed and added to your system `PATH`.

### Execution Steps
1. Clone this repository into your desired directory:
   ```bash
   git clone https://github.com/Fictiverse/llama.cpp-Windows-Launcher.git
   cd llama.cpp-Windows-Launcher
   ```
2. Double-click the **`launcher.bat`** file.
   - On its first run, it will automatically instantiate a Python virtual environment (`env`), upgrade pip, install `PyQt6` and run the launcher.
   - Subsequent runs will bypass the installation checks and launch the GUI immediately in offline mode.

---

## How to Build a Standalone Executable (`.exe`)

If you prefer running a single standalone binary without having a local Python environment:

1. Double-click the **`build.bat`** file.
   - It will automatically install `PyInstaller` inside your local virtual environment if it is missing.
   - It compiles `run.py` into a single standalone `LlamaLauncher.exe` file inside a newly created `/dist` folder.
   - It embeds the native `logo.ico` file directly as the Windows binary resource icon.

### Troubleshooting: Executable Icon not showing up?
Windows Explorer heavily caches executable icons. If your compiled `LlamaLauncher.exe` still shows the default Windows program icon:
- Copy the file to another folder (e.g., your Desktop) or rename it to `LlamaLauncher_test.exe`. This forces Windows Explorer to clear its visual cache and display the retro custom icon.
- Ensure `logo.ico` is a real `.ico` file containing multiple layers (16x16, 32x32, 48x48, 256x256), and not just a renamed `.png` file.

---

## Quick Start Configuration

1. **Set Paths**: Upon opening the launcher, click **Options...** and browse to:
   - Your local compiled `llama.cpp` folder (the launcher automatically searches for `llama-server.exe`, `llama-cli.exe`, and `llama-bench.exe`).
   - Your GGUF models folder.
2. **Setup Autolaunch (Optional)**: Check *"Autolaunch last preset on startup"* if you want the launcher to immediately spin up your AI server as soon as the program starts.
3. **Use the Wizard**: Select your GGUF model on the home screen, click **Edit Preset**, then click the **Wizard (Autodetect)** button. The launcher will automatically find the best settings for your GPU and system RAM. Give your preset a name and click **Save**.
4. **Interact**: Click **Launch Server** to open the terminal, then click **Open Web UI** to start chatting in your default browser.

---

## License

This launcher is open-source. Feel free to modify and adapt it to your custom `llama.cpp` setups.
