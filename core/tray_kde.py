import json
import os
import signal
import sys
import threading
from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtGui import QAction, QIcon, QPixmap, QPainter, QColor
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

# On Linux, ensure that if parent process dies abruptly, the kernel immediately sends SIGTERM
if sys.platform.startswith("linux"):
    try:
        import ctypes
        libc = ctypes.CDLL("libc.so.6")
        PR_SET_PDEATHSIG = 1
        libc.prctl(PR_SET_PDEATHSIG, signal.SIGTERM)
    except Exception:
        pass

class TrayBridge(QObject):
    update_icon = Signal(str)
    update_tooltip = Signal(str)
    request_quit = Signal()

def create_default_icon() -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(59, 142, 208))
    painter.setPen(QColor(30, 35, 45))
    painter.drawEllipse(4, 4, 56, 56)
    painter.end()
    return QIcon(pixmap)

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    bridge = TrayBridge()
    tray = QSystemTrayIcon()

    initial_icon = sys.argv[1] if len(sys.argv) > 1 and os.path.exists(sys.argv[1]) else ""
    if initial_icon and os.path.exists(initial_icon):
        tray.setIcon(QIcon(initial_icon))
    else:
        tray.setIcon(create_default_icon())

    tray.setToolTip("Steam Avatar Manager")

    def clean_exit(code=0):
        try:
            tray.hide()
        except Exception:
            pass
        try:
            app.quit()
        except Exception:
            pass
        os._exit(code)

    # Signal handlers (executed on MainThread in Python)
    def sig_handler(signum=None, frame=None):
        clean_exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, sig_handler)

    # Periodic timer so Python signal handlers can execute while in Qt C++ loop
    sig_timer = QTimer()
    sig_timer.timeout.connect(lambda: None)
    sig_timer.start(250)

    def safe_send_event(event_name: str):
        try:
            sys.stdout.write(json.dumps({"event": event_name}) + "\n")
            sys.stdout.flush()
        except (BrokenPipeError, IOError, OSError):
            clean_exit(0)

    menu = QMenu()

    action_show = QAction("Show Window", menu)
    action_show.triggered.connect(lambda: safe_send_event("show"))
    menu.addAction(action_show)

    action_toggle = QAction("Toggle Rotation", menu)
    action_toggle.triggered.connect(lambda: safe_send_event("toggle_rotation"))
    menu.addAction(action_toggle)

    menu.addSeparator()

    action_quit = QAction("Quit", menu)
    def on_quit_action():
        safe_send_event("quit")
        clean_exit(0)
    action_quit.triggered.connect(on_quit_action)
    menu.addAction(action_quit)

    tray.setContextMenu(menu)

    def on_activated(reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            safe_send_event("show")

    tray.activated.connect(on_activated)

    bridge.update_icon.connect(lambda path: tray.setIcon(QIcon(path)) if os.path.exists(path) else None)
    bridge.update_tooltip.connect(lambda text: tray.setToolTip(f"Steam Avatar Manager\n{text}"))
    bridge.request_quit.connect(lambda: clean_exit(0))

    def listen_stdin():
        try:
            for line in sys.stdin:
                line = line.strip()
                if not line:
                    continue
                try:
                    cmd = json.loads(line)
                    action = cmd.get("action")
                    if action == "set_icon":
                        bridge.update_icon.emit(cmd.get("path", ""))
                    elif action == "set_tooltip":
                        bridge.update_tooltip.emit(cmd.get("text", ""))
                    elif action == "quit":
                        break
                except Exception:
                    pass
        except Exception:
            pass
        # Signal main thread via QueuedConnection
        bridge.request_quit.emit()
        # Watchdog: if main thread is blocked, force exit
        import time
        time.sleep(0.5)
        os._exit(0)

    threading.Thread(target=listen_stdin, daemon=True).start()

    tray.show()
    app.aboutToQuit.connect(lambda: tray.hide())
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
