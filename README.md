# Steam Avatar Manager 🔄🎮

A simple, modern desktop application to automatically rotate and switch your Steam profile avatars without re-uploading images every time.

Choose your favorite avatars from your Steam history, pick a rotation interval (e.g., every 15 minutes), choose a mode (Sequential, Random, or Shuffle), and let the app handle the rest in the background.

> [!IMPORTANT]
> **How does this app work?**
> Steam allows instant switching between avatars that you have **previously uploaded to your Steam account**.
> This app does **not** upload local image files directly to Steam. Instead, you upload your avatars to your Steam profile **once**, and this app pulls your history and automates switching and rotation between them!

---

## ✨ Features

- 🔄 **Automatic Avatar Rotation**: Cycles through your selected avatars at any interval you set (e.g., every 5, 15, or 60 minutes).
- 🎲 **3 Rotation Modes**:
  - **Sequential**: Rotates in order, one by one.
  - **Random**: Picks a random avatar every time.
  - **Shuffle**: Shuffles all avatars like a deck of cards and goes through all of them before reshuffling (no immediate repeats!).
- 🖼️ **One-Click Manual Switch**: Browse all your avatars with visual previews and apply any of them instantly.
- 📥 **Fetch Avatar History**: Downloads your previously uploaded Steam avatars directly from Steam's servers.
- 🛡️ **Secure Local Storage**: Supports Steam Guard (email codes & Steam Mobile 2FA approval). Your session is stored locally on your machine—never sent to third parties.
- 🗔 **System Tray Support**: Minimize to system tray so it stays out of your way while gaming. (Works on Windows and Linux, including KDE Plasma and GNOME).
- 🔒 **Single Instance Protection**: Opening the launcher again simply brings the existing window to the front instead of spawning duplicate processes.
- 🖥️ **CLI Scripts Included**: Headless scripts (`change_avatar.py`, `fetch_avatars.py`) for command-line power users or automation.

---

## 📋 Requirements

- **Python 3.10** or higher (Recommended: Python 3.12 or 3.14).
  - *Windows users*: Make sure to check **"Add python.exe to PATH"** when installing Python!
  - *Ubuntu / Debian Linux users*: Make sure `python3-tk` and `python3-venv` are installed (`sudo apt install python3-tk python3-venv`).

---

## 🚀 Quick Start & Installation

Clone this repository or download it as a ZIP and extract it to a folder.

```bash
git clone https://github.com/Error3008/SteamAvatarChangeBot.git
cd SteamAvatarChangeBot
```

### 🪟 Windows Setup & Launch

We included a dedicated one-click launcher for Windows:

1. Simply double-click **`start_windows.bat`**.
2. The script will automatically:
   - Check your Python version.
   - Create a virtual environment (`venv`).
   - Install all required libraries (`requirements.txt`).
   - Launch the application!

---

### 🐧 Linux Setup & Launch

We included a dedicated launcher for Linux:

1. Open your terminal in the project directory.
2. Make sure the script has execute permissions:
   ```bash
   chmod +x start_linux.sh
   ```
3. Run the launcher:
   ```bash
   ./start_linux.sh
   ```
4. The script will automatically create the virtual environment, install dependencies, and launch the GUI.

---

## 📖 How to Use

1. **Log In**:
   - Open the app and stay on the **Login** tab.
   - Enter your Steam Account Name and Password.
   - If you use Steam Guard code, enter it in the code field. If you use the Steam Mobile App, leave it empty, click **Log In**, and approve the prompt on your phone.
   - Once logged in, your session is saved locally for future launches.
2. **Fetch Avatars**:
   - Switch to the **Avatars** tab.
   - Click the **Fetch from Steam** button. The app will pull your past avatar history from Steam and download previews.

   > [!TIP]
   > **How to add avatars to the app (If your list is empty):**
   > Since the app switches between avatars already stored in Steam's cloud history:
   > 1. Open the Steam app or website -> Go to **Profile** -> **Edit Profile** -> **Avatar**.
   > 2. Upload the images you want to rotate through (upload them one after another so Steam saves them into your "Your Avatars" history).
   > 3. Return to this app and click **"Fetch from Steam"**. All of them will appear immediately with checkboxes and previews!
3. **Configure Rotation**:
   - Check the boxes next to the avatars you want to include in the rotation (or click **Select All**).
   - Set the rotation **Interval** in minutes.
   - Select the **Mode** (`Sequential`, `Random`, or `Shuffle`).
   - Enable **"Minimize to tray on [X]"** if you want the window to hide to the system tray when closed.
4. **Start & Enjoy**:
   - Click **Start Rotation** to begin automated avatar rotation.
   - Or click the **Apply** button next to any avatar to set it immediately.
   - Click **Save Configuration** so your preferences are remembered the next time you open the app.

---

## ⚠️ Troubleshooting: What to do if the app doesn't open?

If the app closes immediately or doesn't start when you double-click the launcher, **run it from a terminal**. When you launch through a terminal, you will see the exact error message instead of the window vanishing instantly.

### On Windows:
1. Open the folder containing the project.
2. Click in the file explorer's address bar at the top, type `cmd`, and press **Enter**. A Command Prompt window will open in that folder.
3. Run the launcher in console mode:
   ```cmd
   start_windows.bat --console
   ```
   *(Or run directly: `venv\Scripts\python.exe gui.py`)*
4. Read the error output:
   - **"Python is not recognized"**: You need to install Python from [python.org](https://www.python.org/downloads/) and ensure you tick **"Add python.exe to PATH"**.
   - **"Session invalid / expired"**: Your Steam token expired. Delete `*.session.json` and `.env` files, then log in again.

### On Linux:
1. Open a terminal in the project folder.
2. Run:
   ```bash
   ./start_linux.sh
   ```
   *(Or run directly: `./venv/bin/python gui.py`)*
3. Read the terminal output:
   - **`No module named '_tkinter'`**: Install Tkinter by running:
     ```bash
     sudo apt install python3-tk    # Ubuntu / Debian / Mint
     sudo pacman -S tk              # Arch Linux
     sudo dnf install python3-tkinter # Fedora
     ```

---

## 📁 Project Structure

```text
SteamAvatarChangeAuto/
├── start_windows.bat      # One-click launcher for Windows
├── start_linux.sh         # One-click launcher for Linux
├── gui.py                 # Main CustomTkinter desktop interface
├── config.json            # Saved user settings (interval, mode, selected hashes)
├── avatar_state.txt       # Tracks current rotation index
├── requirements.txt       # Python dependencies
├── core/
│   ├── auth.py            # Steam login, session management & token refresh
│   ├── avatar.py          # Avatar fetching, history and Steam API apply requests
│   └── tray_kde.py        # Dedicated Qt tray handler for Linux/KDE
├── avatars/               # Downloaded avatar images (.jpg)
├── change_avatar.py       # Headless CLI: Switch to next avatar
├── fetch_avatars.py       # Headless CLI: Download avatar history
└── login.py               # Headless CLI: Login to Steam
```

---

## 🔒 Security & Privacy

- **Direct Communication**: All requests are sent directly to official Steam Community endpoints (`steamcommunity.com` and `api.steampowered.com`).
- **No Remote Telemetry**: Your credentials, cookies, and session tokens are strictly stored on your own local drive (`*.session.json` and `.env`).
- **Open Source**: The code is fully open-source Python, so you can inspect every line.

---

## 📄 License

This project is licensed under the MIT License. Feel free to use, modify, and distribute!
