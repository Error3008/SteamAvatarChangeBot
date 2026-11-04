import asyncio
import atexit
import json
import os
import random
import signal
import socket
import subprocess
import sys
import threading
from pathlib import Path
import customtkinter as ctk
from PIL import Image, ImageDraw

from core.auth import login, validate_session
from core.avatar import apply_avatar, fetch_recent_avatars, AVATARS_DIR, CONFIG_FILE

BASE_DIR = Path(__file__).resolve().parent

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class SingleInstance:
    def __init__(self, on_show_callback):
        self.on_show_callback = on_show_callback
        self.sock = None
        base_port = 49280
        uid_offset = (os.getuid() % 1000) if hasattr(os, "getuid") else 1
        self.port = base_port + uid_offset

    def check_and_start(self) -> bool:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        try:
            s.connect(("127.0.0.1", self.port))
            s.sendall(b"show\n")
            s.close()
            return False
        except (ConnectionRefusedError, OSError):
            s.close()

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind(("127.0.0.1", self.port))
            self.sock.listen(1)
            threading.Thread(target=self._listener_loop, daemon=True).start()
            return True
        except OSError:
            return False

    def _listener_loop(self):
        while self.sock:
            try:
                conn, _ = self.sock.accept()
            except Exception:
                break
            try:
                data = conn.recv(16).strip()
                if data == b"show" and self.on_show_callback:
                    self.on_show_callback()
            except Exception:
                pass
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

    def cleanup(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

class SteamAvatarApp(ctk.CTk):
    def __init__(self, single_instance_mgr=None):
        super().__init__()
        self.single_instance_mgr = single_instance_mgr
        self.title("Steam Avatar Manager")
        self.geometry("720x840")
        self.minsize(600, 700)

        self.is_authenticated = False
        self.checkbox_vars = {}
        self.image_references = []
        self.config_data = self.load_config()
        self.min_to_tray_var = ctk.BooleanVar(value=self.config_data.get("minimize_to_tray", False))

        self.is_rotating = False
        self.rotation_timer_id = None
        self.sequential_idx = 0
        self.shuffle_deck = []
        self.tray_proc = None
        self.pystray_icon = None

        atexit.register(self._cleanup_on_exit)
        try:
            signal.signal(signal.SIGINT, lambda *_: self.quit_app())
            signal.signal(signal.SIGTERM, lambda *_: self.quit_app())
        except Exception:
            pass

        self.create_layout()
        self.tabview.set("Login")
        self.protocol("WM_DELETE_WINDOW", self.on_close_window)

        self.setup_tray()
        self.check_session()

    def load_config(self) -> dict:
        default_cfg = {
            "interval_minutes": 15,
            "mode": "Sequential",
            "selected_hashes": [],
            "minimize_to_tray": False
        }
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                default_cfg.update(data)
                return default_cfg
            except Exception:
                pass
        return default_cfg

    def get_tray_image(self, sha: str = "") -> Image.Image:
        if sha:
            img_path = AVATARS_DIR / f"{sha}.jpg"
            if img_path.exists():
                try:
                    return Image.open(img_path).convert("RGBA").resize((64, 64), Image.Resampling.LANCZOS)
                except Exception:
                    pass

        if AVATARS_DIR.exists():
            for p in AVATARS_DIR.glob("*.jpg"):
                try:
                    return Image.open(p).convert("RGBA").resize((64, 64), Image.Resampling.LANCZOS)
                except Exception:
                    pass

        img = Image.new("RGBA", (64, 64), color=(30, 35, 45, 255))
        draw = ImageDraw.Draw(img)
        draw.ellipse([8, 8, 56, 56], fill=(59, 142, 208, 255))
        return img

    def setup_tray(self):
        if sys.platform.startswith("linux"):
            try:
                import PySide6
                tray_script = BASE_DIR / "core" / "tray_kde.py"
                if tray_script.exists():
                    try:
                        # Clean up any leftover orphaned tray processes from previous runs
                        subprocess.run(
                            ["pkill", "-u", str(os.getuid()), "-f", "core/tray_kde.py"],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL
                        )
                    except Exception:
                        pass

                    initial_icon = ""
                    if AVATARS_DIR.exists():
                        for p in AVATARS_DIR.glob("*.jpg"):
                            initial_icon = str(p)
                            break
                    self.tray_proc = subprocess.Popen(
                        [sys.executable, str(tray_script), initial_icon],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        text=True,
                        bufsize=1
                    )
                    threading.Thread(target=self._listen_kde_tray, daemon=True).start()
                    return
            except Exception:
                pass

        try:
            import pystray
            menu = pystray.Menu(
                pystray.MenuItem("Show Window", self.show_from_tray, default=True),
                pystray.MenuItem("Toggle Rotation", self.toggle_rotation_from_tray),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit", self.quit_app)
            )
            self.pystray_icon = pystray.Icon(
                "SteamAvatarManager",
                icon=self.get_tray_image(),
                title="Steam Avatar Manager",
                menu=menu
            )
            threading.Thread(target=self.pystray_icon.run, daemon=True).start()
        except Exception:
            pass

    def _listen_kde_tray(self):
        if not self.tray_proc or not self.tray_proc.stdout:
            return
        for line in self.tray_proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                evt = data.get("event")
                if evt == "show":
                    self.after(0, self._restore_window)
                elif evt == "toggle_rotation":
                    self.after(0, self.toggle_rotation)
                elif evt == "quit":
                    self.after(0, self.quit_app)
            except Exception:
                pass

    def send_tray_cmd(self, cmd: dict):
        if self.tray_proc and self.tray_proc.poll() is None and self.tray_proc.stdin:
            try:
                self.tray_proc.stdin.write(json.dumps(cmd) + "\n")
                self.tray_proc.stdin.flush()
            except Exception:
                pass

    def update_tray_image(self, sha: str):
        img_path = AVATARS_DIR / f"{sha}.jpg"
        if self.tray_proc and img_path.exists():
            self.send_tray_cmd({"action": "set_icon", "path": str(img_path)})
        elif self.pystray_icon:
            try:
                self.pystray_icon.icon = self.get_tray_image(sha)
            except Exception:
                pass

    def on_close_window(self):
        if self.is_authenticated and self.min_to_tray_var.get() and ((self.tray_proc and self.tray_proc.poll() is None) or self.pystray_icon):
            self.withdraw()
        else:
            self.quit_app()

    def hide_to_tray(self):
        if (self.tray_proc and self.tray_proc.poll() is None) or self.pystray_icon:
            self.withdraw()

    def show_from_tray(self, icon=None, item=None):
        self.after(0, self._restore_window)

    def _restore_window(self):
        self.deiconify()
        self.state("normal")
        self.lift()
        try:
            self.attributes("-topmost", True)
            self.after_idle(lambda: self.attributes("-topmost", False))
        except Exception:
            pass
        self.focus_force()

    def toggle_rotation_from_tray(self, icon=None, item=None):
        self.after(0, self.toggle_rotation)

    def quit_app(self, icon=None, item=None):
        self.after(0, self._do_quit)

    def _do_quit(self):
        self._cleanup_on_exit()
        try:
            self.destroy()
        except Exception:
            pass
        sys.exit(0)

    def _cleanup_on_exit(self):
        if getattr(self, "_cleaned_up", False):
            return
        self._cleaned_up = True

        try:
            self.stop_rotation()
        except Exception:
            pass
        if self.tray_proc and self.tray_proc.poll() is None:
            try:
                self.send_tray_cmd({"action": "quit"})
                self.tray_proc.terminate()
                self.tray_proc.wait(timeout=1.0)
            except Exception:
                try:
                    self.tray_proc.kill()
                except Exception:
                    pass
            self.tray_proc = None
        if self.pystray_icon:
            try:
                self.pystray_icon.stop()
            except Exception:
                pass
            self.pystray_icon = None
        if hasattr(self, "single_instance_mgr") and self.single_instance_mgr:
            self.single_instance_mgr.cleanup()
            self.single_instance_mgr = None

    def set_authenticated(self, is_auth: bool, account_name: str = ""):
        self.is_authenticated = is_auth

        button_state = "normal" if is_auth else "disabled"
        if hasattr(self, "tabview") and "Avatars" in self.tabview._segmented_button._buttons_dict:
            self.tabview._segmented_button._buttons_dict["Avatars"].configure(state=button_state)

        if is_auth:
            self.account_status_label.configure(
                text=f"Active Session: {account_name}",
                text_color="#55ff55"
            )
        else:
            if self.is_rotating:
                self.stop_rotation()
            self.account_status_label.configure(
                text="Active Session: None (Session closed or expired)",
                text_color="#ff5555"
            )
            self.tabview.set("Login")

    def check_session(self):
        def task():
            try:
                valid, info = asyncio.run(validate_session())
                self.after(0, lambda: self._on_session_checked(valid, info))
            except Exception as e:
                self.after(0, lambda: self._on_session_checked(False, str(e)))

        threading.Thread(target=task, daemon=True).start()

    def _on_session_checked(self, is_valid: bool, info: str):
        if is_valid:
            self.set_authenticated(True, info)
            self.login_status.configure(
                text="Session verified and active.",
                text_color="#55ff55"
            )
        else:
            self.set_authenticated(False)
            self.login_status.configure(
                text=f"Session closed: {info}. Please log in.",
                text_color="#ffaa00"
            )

    def _on_tab_switch(self):
        if not self.is_authenticated and self.tabview.get() == "Avatars":
            self.tabview.set("Login")

    def create_layout(self):
        self.tabview = ctk.CTkTabview(self, command=self._on_tab_switch)
        self.tabview.pack(fill="both", expand=True, padx=16, pady=16)

        self.tab_login = self.tabview.add("Login")
        self.tab_avatars = self.tabview.add("Avatars")

        self.setup_login_tab()
        self.setup_avatars_tab()

    def setup_login_tab(self):
        card = ctk.CTkFrame(self.tab_login, corner_radius=12)
        card.pack(expand=True, padx=40, pady=20)

        ctk.CTkLabel(
            card,
            text="Steam Account Login",
            font=ctk.CTkFont(size=22, weight="bold")
        ).pack(padx=24, pady=(24, 6))

        self.account_status_label = ctk.CTkLabel(
            card,
            text="Active Session: Checking...",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#55ccff"
        )
        self.account_status_label.pack(padx=24, pady=(0, 20))

        ctk.CTkLabel(card, text="Account Name", font=ctk.CTkFont(size=13)).pack(pady=(4, 2))
        self.username_entry = ctk.CTkEntry(
            card,
            width=440,
            height=42,
            placeholder_text="Enter Steam account name",
            font=ctk.CTkFont(size=14),
            justify="center"
        )
        self.username_entry.pack(padx=30, pady=(0, 12))

        ctk.CTkLabel(card, text="Password", font=ctk.CTkFont(size=13)).pack(pady=(4, 2))
        self.password_entry = ctk.CTkEntry(
            card,
            width=440,
            height=42,
            show="*",
            placeholder_text="Enter Steam password",
            font=ctk.CTkFont(size=14),
            justify="center"
        )
        self.password_entry.pack(padx=30, pady=(0, 12))

        ctk.CTkLabel(card, text="Steam Guard Code", font=ctk.CTkFont(size=13)).pack(pady=(4, 2))
        self.guard_entry = ctk.CTkEntry(
            card,
            width=440,
            height=42,
            placeholder_text="5-digit code or leave empty for mobile approval",
            font=ctk.CTkFont(size=14),
            justify="center"
        )
        self.guard_entry.pack(padx=30, pady=(0, 20))

        self.login_btn = ctk.CTkButton(
            card,
            text="Log In",
            font=ctk.CTkFont(size=15, weight="bold"),
            width=240,
            height=44,
            command=self.start_login
        )
        self.login_btn.pack(pady=(0, 14))

        self.login_status = ctk.CTkLabel(
            card,
            text="",
            font=ctk.CTkFont(size=13),
            wraplength=420,
            justify="center"
        )
        self.login_status.pack(padx=24, pady=(0, 22))

    def setup_avatars_tab(self):
        header = ctk.CTkFrame(self.tab_avatars)
        header.pack(fill="x", padx=10, pady=(6, 8))

        top_header = ctk.CTkFrame(header, fg_color="transparent")
        top_header.pack(fill="x", padx=12, pady=(10, 4))

        ctk.CTkLabel(
            top_header,
            text="Avatar Rotation & Management",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(side="left")

        ctk.CTkButton(
            top_header,
            text="Exit App",
            fg_color="#d9534f",
            hover_color="#c9302c",
            width=90,
            height=28,
            command=self.quit_app
        ).pack(side="right", padx=(8, 0))

        ctk.CTkButton(
            top_header,
            text="Minimize to Tray",
            width=120,
            height=28,
            command=self.hide_to_tray
        ).pack(side="right")

        settings_row = ctk.CTkFrame(header, fg_color="transparent")
        settings_row.pack(fill="x", padx=12, pady=4)

        ctk.CTkLabel(
            settings_row,
            text="Interval (min):",
            font=ctk.CTkFont(size=14)
        ).pack(side="left")

        default_interval = str(self.config_data.get("interval_minutes", 15))
        self.interval_entry = ctk.CTkEntry(settings_row, width=70)
        self.interval_entry.insert(0, default_interval)
        self.interval_entry.pack(side="left", padx=(8, 16))

        ctk.CTkLabel(
            settings_row,
            text="Mode:",
            font=ctk.CTkFont(size=14)
        ).pack(side="left")

        default_mode = self.config_data.get("mode", "Sequential")
        self.mode_menu = ctk.CTkOptionMenu(
            settings_row,
            values=["Sequential", "Random", "Shuffle"],
            width=120
        )
        self.mode_menu.set(default_mode)
        self.mode_menu.pack(side="left", padx=(8, 16))

        self.min_to_tray_cb = ctk.CTkCheckBox(
            settings_row,
            text="Minimize to tray on [X]",
            variable=self.min_to_tray_var,
            font=ctk.CTkFont(size=13)
        )
        self.min_to_tray_cb.pack(side="left", padx=(8, 0))

        rotation_row = ctk.CTkFrame(header, fg_color="transparent")
        rotation_row.pack(fill="x", padx=12, pady=4)

        self.rotate_toggle_btn = ctk.CTkButton(
            rotation_row,
            text="Start Rotation",
            font=ctk.CTkFont(size=13, weight="bold"),
            width=140,
            height=32,
            command=self.toggle_rotation
        )
        self.rotate_toggle_btn.pack(side="left", padx=(0, 12))

        self.rotation_info_label = ctk.CTkLabel(
            rotation_row,
            text="Rotation: Stopped",
            font=ctk.CTkFont(size=13),
            text_color="#aaaaaa"
        )
        self.rotation_info_label.pack(side="left")

        actions_row = ctk.CTkFrame(header, fg_color="transparent")
        actions_row.pack(fill="x", padx=12, pady=(4, 10))

        ctk.CTkButton(
            actions_row,
            text="Select All",
            width=90,
            command=self.select_all
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            actions_row,
            text="Deselect All",
            width=90,
            command=self.deselect_all
        ).pack(side="left", padx=(0, 6))

        self.fetch_btn = ctk.CTkButton(
            actions_row,
            text="Fetch from Steam",
            width=130,
            command=self.start_fetch_avatars
        )
        self.fetch_btn.pack(side="left")

        self.scroll_frame = ctk.CTkScrollableFrame(self.tab_avatars, label_text="Available Avatars")
        self.scroll_frame.pack(fill="both", expand=True, padx=10, pady=6)

        self.populate_avatars()

        footer = ctk.CTkFrame(self.tab_avatars)
        footer.pack(fill="x", padx=10, pady=(8, 10))

        self.save_button = ctk.CTkButton(
            footer,
            text="Save Configuration",
            font=ctk.CTkFont(size=15, weight="bold"),
            height=38,
            command=self.save_config
        )
        self.save_button.pack(fill="x", padx=12, pady=(10, 6))

        self.avatar_status = ctk.CTkLabel(footer, text="", font=ctk.CTkFont(size=13))
        self.avatar_status.pack(padx=12, pady=(0, 8))

    def populate_avatars(self):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        self.checkbox_vars.clear()
        self.image_references.clear()

        saved_hashes = set(self.config_data.get("selected_hashes", []))
        avatar_files = sorted(AVATARS_DIR.glob("*.jpg")) if AVATARS_DIR.exists() else []

        if not avatar_files:
            ctk.CTkLabel(
                self.scroll_frame,
                text="No avatars found yet!\n\n1. Upload your avatars on Steam (Profile -> Edit Profile -> Avatar)\n2. Click 'Fetch from Steam' above to load them here.",
                font=ctk.CTkFont(size=14),
                justify="center"
            ).pack(pady=40)
            return

        for img_path in avatar_files:
            sha = img_path.stem
            is_checked = sha in saved_hashes or not saved_hashes

            row = ctk.CTkFrame(self.scroll_frame)
            row.pack(fill="x", padx=6, pady=4)

            try:
                pil_img = Image.open(img_path).resize((64, 64), Image.Resampling.LANCZOS)
                ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(64, 64))
                self.image_references.append(ctk_img)

                img_label = ctk.CTkLabel(row, image=ctk_img, text="")
                img_label.pack(side="left", padx=8, pady=6)
            except Exception:
                pass

            var = ctk.BooleanVar(value=is_checked)
            self.checkbox_vars[sha] = var

            short_sha = f"{sha[:8]}...{sha[-8:]}"
            cb = ctk.CTkCheckBox(
                row,
                text=short_sha,
                variable=var,
                font=ctk.CTkFont(family="monospace", size=13)
            )
            cb.pack(side="left", padx=10, pady=6)

            apply_btn = ctk.CTkButton(
                row,
                text="Apply",
                width=75,
                height=28,
                command=lambda s=sha: self.apply_specific_avatar(s)
            )
            apply_btn.pack(side="right", padx=12, pady=6)

    def apply_specific_avatar(self, sha: str):
        self.avatar_status.configure(
            text=f"Applying avatar {sha[:8]}...",
            text_color="#aaaaaa"
        )

        def task():
            try:
                success, msg = asyncio.run(apply_avatar(sha))
                self.after(0, lambda: self._on_apply_result(success, msg, sha))
            except Exception as e:
                self.after(0, lambda: self._on_apply_result(False, str(e), sha))

        threading.Thread(target=task, daemon=True).start()

    def _on_apply_result(self, success: bool, msg: str, sha: str):
        if success:
            self.update_tray_image(sha)
            self.avatar_status.configure(
                text=f"Avatar successfully switched to {sha[:8]}...!",
                text_color="#55ff55"
            )
        else:
            self.avatar_status.configure(
                text=f"Failed to switch avatar: {msg}",
                text_color="#ff5555"
            )
            self.check_session()

    def get_selected_hashes(self) -> list[str]:
        return [sha for sha, var in self.checkbox_vars.items() if var.get()]

    def toggle_rotation(self):
        if self.is_rotating:
            self.stop_rotation()
        else:
            self.start_rotation()

    def start_rotation(self):
        selected = self.get_selected_hashes()
        if not selected:
            self.avatar_status.configure(
                text="Warning: Select at least one avatar for rotation!",
                text_color="#ffaa00"
            )
            return

        raw_interval = self.interval_entry.get().strip()
        try:
            interval = int(raw_interval)
            if interval <= 0:
                raise ValueError
        except ValueError:
            self.avatar_status.configure(
                text="Error: Interval must be a positive integer!",
                text_color="#ff5555"
            )
            return

        self.is_rotating = True
        self.rotate_toggle_btn.configure(
            text="Stop Rotation",
            fg_color="#d9534f",
            hover_color="#c9302c"
        )

        mode = self.mode_menu.get()
        self.rotation_info_label.configure(
            text=f"Rotation: Active ({mode}, every {interval}m)",
            text_color="#55ff55"
        )

        self.sequential_idx = 0
        self.shuffle_deck = []
        self._rotation_tick()

    def stop_rotation(self):
        self.is_rotating = False
        if self.rotation_timer_id:
            self.after_cancel(self.rotation_timer_id)
            self.rotation_timer_id = None

        self.rotate_toggle_btn.configure(
            text="Start Rotation",
            fg_color=["#3B8ED0", "#1F6AA5"],
            hover_color=["#36719F", "#144870"]
        )
        self.rotation_info_label.configure(
            text="Rotation: Stopped",
            text_color="#aaaaaa"
        )

    def _get_next_rotation_sha(self, pool: list[str]) -> str:
        mode = self.mode_menu.get()
        if mode == "Random":
            return random.choice(pool)
        elif mode == "Shuffle":
            if not self.shuffle_deck:
                self.shuffle_deck = pool.copy()
                random.shuffle(self.shuffle_deck)
            return self.shuffle_deck.pop(0)
        else:
            sha = pool[self.sequential_idx % len(pool)]
            self.sequential_idx = (self.sequential_idx + 1) % len(pool)
            return sha

    def _rotation_tick(self):
        if not self.is_rotating:
            return

        selected = self.get_selected_hashes()
        if not selected:
            self.stop_rotation()
            self.avatar_status.configure(
                text="Rotation stopped: No avatars selected.",
                text_color="#ffaa00"
            )
            return

        sha = self._get_next_rotation_sha(selected)

        def task():
            try:
                success, msg = asyncio.run(apply_avatar(sha))
                self.after(0, lambda: self._on_rotation_step_done(success, msg, sha))
            except Exception as e:
                self.after(0, lambda: self._on_rotation_step_done(False, str(e), sha))

        threading.Thread(target=task, daemon=True).start()

    def _on_rotation_step_done(self, success: bool, msg: str, sha: str):
        if not self.is_rotating:
            return

        if success:
            self.update_tray_image(sha)
            mode = self.mode_menu.get()
            self.avatar_status.configure(
                text=f"Rotation: Applied {sha[:8]}... ({mode})",
                text_color="#55ff55"
            )
        else:
            self.avatar_status.configure(
                text=f"Rotation error: {msg}",
                text_color="#ff5555"
            )
            self.check_session()
            if not self.is_authenticated:
                self.stop_rotation()
                return

        try:
            interval = int(self.interval_entry.get().strip())
        except ValueError:
            interval = 15

        delay_ms = max(interval, 1) * 60 * 1000
        self.rotation_timer_id = self.after(delay_ms, self._rotation_tick)

    def select_all(self):
        for var in self.checkbox_vars.values():
            var.set(True)

    def deselect_all(self):
        for var in self.checkbox_vars.values():
            var.set(False)

    def start_fetch_avatars(self):
        self.fetch_btn.configure(state="disabled")
        self.avatar_status.configure(text="Fetching avatars from Steam...", text_color="#aaaaaa")

        def task():
            try:
                hashes = asyncio.run(fetch_recent_avatars())
                self.after(0, lambda: self._on_fetch_done(hashes))
            except Exception as e:
                self.after(0, lambda: self._on_fetch_fail(str(e)))

        threading.Thread(target=task, daemon=True).start()

    def _on_fetch_done(self, hashes: list[str]):
        self.fetch_btn.configure(state="normal")
        if hashes:
            self.populate_avatars()
            self.avatar_status.configure(
                text=f"Fetched {len(hashes)} avatar(s) successfully.",
                text_color="#55ff55"
            )
        else:
            self.avatar_status.configure(
                text="No avatar history found on Steam! Please upload avatars to your Steam profile first.",
                text_color="#ffaa00"
            )
            self.check_session()

    def _on_fetch_fail(self, err: str):
        self.fetch_btn.configure(state="normal")
        self.avatar_status.configure(
            text=f"Fetch failed: {err}",
            text_color="#ff5555"
        )
        self.check_session()

    def save_config(self):
        raw_interval = self.interval_entry.get().strip()
        try:
            interval = int(raw_interval)
            if interval <= 0:
                raise ValueError
        except ValueError:
            self.avatar_status.configure(
                text="Error: Interval must be a positive integer!",
                text_color="#ff5555"
            )
            return

        selected = self.get_selected_hashes()
        if not selected:
            self.avatar_status.configure(
                text="Warning: No avatars selected!",
                text_color="#ffaa00"
            )
            return

        mode = self.mode_menu.get()
        data = {
            "interval_minutes": interval,
            "mode": mode,
            "selected_hashes": selected,
            "minimize_to_tray": self.min_to_tray_var.get()
        }

        try:
            CONFIG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
            self.config_data = data
            self.avatar_status.configure(
                text=f"Saved {len(selected)} avatar(s), mode '{mode}', {interval}m interval to config.json",
                text_color="#55ff55"
            )
        except Exception as e:
            self.avatar_status.configure(
                text=f"Error saving config: {e}",
                text_color="#ff5555"
            )

    def start_login(self):
        user = self.username_entry.get().strip()
        pwd = self.password_entry.get()
        code = self.guard_entry.get().strip()

        if not user or not pwd:
            self.login_status.configure(
                text="Error: Account Name and Password cannot be empty!",
                text_color="#ff5555"
            )
            return

        self.login_btn.configure(state="disabled")
        self.login_status.configure(
            text="Authenticating with Steam... (Confirm on phone if prompted)",
            text_color="#aaaaaa"
        )

        def task():
            try:
                success, msg = asyncio.run(login(user, pwd, code))
                self.after(0, lambda: self._on_login_done(success, msg, user))
            except Exception as e:
                self.after(0, lambda: self._on_login_done(False, str(e), user))

        threading.Thread(target=task, daemon=True).start()

    def _on_login_done(self, success: bool, msg: str, user: str):
        self.login_btn.configure(state="normal")
        if success:
            self.set_authenticated(True, user)
            self.login_status.configure(text=msg, text_color="#55ff55")
            self.password_entry.delete(0, "end")
            self.guard_entry.delete(0, "end")
        else:
            self.set_authenticated(False)
            self.login_status.configure(text=msg, text_color="#ff5555")

if __name__ == "__main__":
    app = None

    def on_show():
        if app:
            app.after(0, app._restore_window)

    mgr = SingleInstance(on_show)
    if not mgr.check_and_start():
        print("[INFO] Steam Avatar Manager is already running. Showing active window.")
        sys.exit(0)

    app = SteamAvatarApp(single_instance_mgr=mgr)
    app.mainloop()
