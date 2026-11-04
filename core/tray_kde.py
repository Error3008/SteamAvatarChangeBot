import json
import os
import sys
import threading
from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

class TrayBridge(QObject):
    update_icon = Signal(str)
    update_tooltip = Signal(str)
    request_quit = Signal()

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    bridge = TrayBridge()
    tray = QSystemTrayIcon()

    initial_icon = sys.argv[1] if len(sys.argv) > 1 and os.path.exists(sys.argv[1]) else ""
    if initial_icon:
        tray.setIcon(QIcon(initial_icon))

    tray.setToolTip("Steam Avatar Manager")

    menu = QMenu()

    action_show = QAction("Show Window", menu)
    action_show.triggered.connect(lambda: print(json.dumps({"event": "show"}), flush=True))
    menu.addAction(action_show)

    action_toggle = QAction("Toggle Rotation", menu)
    action_toggle.triggered.connect(lambda: print(json.dumps({"event": "toggle_rotation"}), flush=True))
    menu.addAction(action_toggle)

    menu.addSeparator()

    action_quit = QAction("Quit", menu)
    action_quit.triggered.connect(lambda: (print(json.dumps({"event": "quit"}), flush=True), app.quit()))
    menu.addAction(action_quit)

    tray.setContextMenu(menu)

    def on_activated(reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            print(json.dumps({"event": "show"}), flush=True)

    tray.activated.connect(on_activated)

    bridge.update_icon.connect(lambda path: tray.setIcon(QIcon(path)) if os.path.exists(path) else None)
    bridge.update_tooltip.connect(lambda text: tray.setToolTip(f"Steam Avatar Manager\n{text}"))
    bridge.request_quit.connect(app.quit)

    def listen_stdin():
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
                    bridge.request_quit.emit()
                    break
            except Exception:
                pass

    threading.Thread(target=listen_stdin, daemon=True).start()

    tray.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
