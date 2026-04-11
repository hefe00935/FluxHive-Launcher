import sys
import uuid
import os
import json
import logging
import ctypes
import minecraft_launcher_lib
import subprocess
import shutil
import psutil
from utils import system_checks
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLineEdit, QPushButton, QComboBox, QLabel, QSlider, QStackedWidget,
                             QScrollArea, QFrame, QCheckBox, QGraphicsOpacityEffect,
                             QSizePolicy)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QThread, pyqtSignal
from PyQt6.QtGui import QIcon, QFont

logging.basicConfig(level=logging.INFO, format=" %(message)s")   

APP_VERSION = "1.0.2"
APP_TAGLINE = "Minecraft launcher that includes a free version of Minecraft with mods."
APP_SUMMARY = "Reliable modded Minecraft launcher tuned for FluxHive players."
MAX_OFFLINE_ACCOUNTS = 5
VERSION_OPTIONS = [
    {
        "label": "Fabric 1.21.11 (Recommended)",
        "display_label": "Fabric 1.21.11",
        "minecraft_version": "1.21.11",
        "loader": "fabric",
        "loader_version": "0.18.6",
        "recommended": True,
        "notes": "FluxHive default modpack"
    },
    {
        "label": "Vanilla 1.21.11",
        "display_label": "Vanilla 1.21.11",
        "minecraft_version": "1.21.11",
        "loader": "vanilla",
        "recommended": False,
        "notes": "Stock Minecraft build"
    }
]

def hide_windows_console():
    """Hide attached console window on Windows when possible."""
    if os.name != "nt":
        return
    try:
        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        console_window = kernel32.GetConsoleWindow()
        if console_window:
            user32.ShowWindow(console_window, 0)  # SW_HIDE
    except Exception:
        pass

def get_auto_ram_allocation():
    """Calculate automatic RAM allocation based on system memory"""
    try:
        total_ram_gb = psutil.virtual_memory().total / (1024 ** 3)
        if total_ram_gb >= 16:
            return 6
        elif total_ram_gb >= 8:
            return 3
        else:
            return 2
    except Exception:
        return 3  # Default to 3GB if detection fails

class DraggableWindow(QMainWindow):
    """Custom frameless window with draggable title bar"""
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.drag_position = None
        self.drag_region_height = 64

    def mousePressEvent(self, event):
        if event.pos().y() < self.drag_region_height:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.drag_position is not None:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.drag_position = None


class SidebarButton(QPushButton):
    """Animated sidebar button"""
    def __init__(self, icon_text, label):
        super().__init__()
        self.icon_text = icon_text
        self.label = label
        self.is_active = False
        self.setMinimumHeight(70)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_style()

    def apply_style(self):
        if self.is_active:
            self.setStyleSheet("""
                SidebarButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1f56b3, stop:1 #2f6fd1);
                    border: none;
                    border-left: 4px solid #5f9dff;
                    color: white;
                    font-weight: bold;
                    font-size: 14px;
                    padding: 10px;
                    text-align: left;
                    border-radius: 0px;
                }
            """)
        else:
            self.setStyleSheet("""
                SidebarButton {
                    background: #1a1a2e;
                    border: none;
                    color: #b0b0b0;
                    font-size: 14px;
                    padding: 10px;
                    text-align: left;
                }
                SidebarButton:hover {
                    background: #2d2d3d;
                    color: #ffffff;
                }
            """)

    def set_active(self, active):
        self.is_active = active
        self.apply_style()


class TitleBar(QWidget):
    """Custom title bar with close and minimize buttons"""
    def __init__(self, parent):
        super().__init__(parent)
        self.parent_window = parent
        self.setFixedHeight(56)
        self.setStyleSheet("""
            background: rgba(8, 12, 18, 0.94);
            border-bottom: 1px solid #1f2f46;
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 12, 8)
        layout.setSpacing(12)
        
        title_group = QVBoxLayout()
        title_group.setSpacing(2)
        title = QLabel("FluxHive Launcher")
        title.setStyleSheet("color: #7FB3FF; font-size: 18px; font-weight: 800; font-family: 'Segoe UI';")
        title_group.addWidget(title)
        layout.addLayout(title_group)
        layout.addStretch()

        self.account_chip = QFrame()
        self.account_chip.setObjectName("AccountChip")
        self.account_chip.setMinimumHeight(40)
        self.account_chip.setStyleSheet("""
            #AccountChip {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                            stop:0 #162739, stop:1 #1b2f44);
                border: 1px solid #2f4867;
                border-radius: 11px;
            }
        """)
        chip_layout = QHBoxLayout(self.account_chip)
        chip_layout.setContentsMargins(10, 8, 12, 8)
        chip_layout.setSpacing(7)
        avatar = QFrame()
        avatar.setFixedSize(10, 10)
        avatar.setStyleSheet("background: #6FB0FF; border: 1px solid #4a7fc4; border-radius: 5px;")
        self.account_name = QLabel("No Profile")
        self.account_name.setStyleSheet(
            "color: #F0F6FF; font-size: 13px; font-weight: 500; "
            "font-family: 'Segoe UI'; background: transparent;"
        )
        chip_layout.addWidget(avatar)
        chip_layout.addWidget(self.account_name)
        layout.addWidget(self.account_chip)
        
        settings_btn = QPushButton("⚙")
        settings_btn.setFixedSize(30, 30)
        settings_btn.setStyleSheet("""
            QPushButton {
                background: #101926;
                color: #5f9dff;
                border: 1px solid #25364d;
                border-radius: 7px;
                font-size: 16px;
            }
            QPushButton:hover {
                background: #1a2a3f;
                border: 1px solid #5f9dff;
            }
        """)
        settings_btn.clicked.connect(self.open_settings)
        layout.addWidget(settings_btn)
        
        min_btn = QPushButton("−")
        min_btn.setFixedSize(30, 30)
        min_btn.setStyleSheet("""
            QPushButton {
                background: #101926;
                color: #dce9fb;
                border: 1px solid #25364d;
                border-radius: 7px;
                font-size: 16px;
            }
            QPushButton:hover {
                background: #1a2a3f;
            }
        """)
        min_btn.clicked.connect(self.parent_window.showMinimized)
        layout.addWidget(min_btn)
        
        close_btn = QPushButton("×")
        close_btn.setFixedSize(30, 30)
        close_btn.setStyleSheet("""
            QPushButton {
                background: #101926;
                color: #dce9fb;
                border: 1px solid #25364d;
                border-radius: 7px;
                font-size: 18px;
            }
            QPushButton:hover {
                background: #3a1a1f;
                border: 1px solid #6a2a32;
            }
        """)
        close_btn.clicked.connect(self.parent_window.close)
        layout.addWidget(close_btn)

    def set_account_name(self, username):
        username = username.strip()
        self.account_name.setText(username if username else "No Profile")

    def open_settings(self):
        if hasattr(self.parent_window, 'switch_to_settings'):
            self.parent_window.switch_to_settings()


class InstallManager:
    """Handles installation checks and launch command creation."""
    def __init__(self, launcher_config, version_profile=None):
        self.config = launcher_config
        self.minecraft_version = "1.21.11"
        self.preferred_loader = "0.18.6"
        self.loader_type = "fabric"
        self.version_display = "Fabric 1.21.11"
        profile = version_profile or (VERSION_OPTIONS[0] if VERSION_OPTIONS else None)
        if profile:
            self.set_version_profile(profile)

    def set_version_profile(self, profile):
        if not isinstance(profile, dict):
            return
        self.version_profile = profile
        self.minecraft_version = profile.get("minecraft_version", self.minecraft_version)
        loader_version = profile.get("loader_version")
        if loader_version:
            self.preferred_loader = loader_version
        self.loader_type = profile.get("loader", self.loader_type or "fabric")
        self.version_display = profile.get("label", self.minecraft_version)

    def _emit_status(self, callback, message):
        logging.info(message)
        if callback:
            callback(message)

    def _make_install_callback(self, callback, prefix):
        state = {"max": 0}
        def set_status(text):
            if callback and text: callback(f"{prefix}: {text}")
        def set_max(value):
            try: state["max"] = max(0, int(value))
            except Exception: state["max"] = 0
        def set_progress(value):
            if not callback: return
            try: value = int(value)
            except Exception: return
            max_value = state["max"]
            if max_value > 0:
                percentage = int((value / max_value) * 100)
                callback(f"{prefix}: {percentage}%")
        return {
            "setStatus": set_status,
            "setMax": set_max,
            "setProgress": set_progress
        }

    def _get_installed_version_ids(self):
        installed = minecraft_launcher_lib.utils.get_installed_versions(self.config.minecraft_directory)
        return {entry.get("id") for entry in installed if isinstance(entry, dict) and entry.get("id")}

    def _is_version_installed(self, version_id):
        return version_id in self._get_installed_version_ids()

    def ensure_minecraft_installed(self, status_callback=None):
        if self._is_version_installed(self.minecraft_version):
            self._emit_status(status_callback, f"Minecraft {self.minecraft_version} already installed.")
            return
        self._emit_status(status_callback, f"Installing Minecraft {self.minecraft_version}...")
        callback = self._make_install_callback(status_callback, "Installing Minecraft")
        minecraft_launcher_lib.install.install_minecraft_version(
            self.minecraft_version,
            self.config.minecraft_directory,
            callback=callback
        )
        if not self._is_version_installed(self.minecraft_version):
            raise RuntimeError(f"Minecraft {self.minecraft_version} installation did not complete.")

    def _resolve_loader_version(self, status_callback=None):
        if self.preferred_loader:
            return self.preferred_loader
        self._emit_status(status_callback, "Resolving latest Fabric loader...")
        return minecraft_launcher_lib.fabric.get_latest_loader_version()

    def _resolve_java_executable(self, status_callback=None):
        """Logic to find Java: Portable Folder -> System Path -> Auto-Install"""
        
        # 1. Look for the portable jdk-21 folder you added
        # We calculate the path relative to where main.py is located
        project_dir = os.path.dirname(os.path.abspath(__file__))
        portable_jdk_bin = os.path.join(project_dir, "jdk-21", "bin")
        portable_java = os.path.join(portable_jdk_bin, "java.exe" if os.name == 'nt' else "java")

        if os.path.exists(portable_java):
            selected_java = self._prefer_javaw_on_windows(portable_java)
            self._emit_status(status_callback, f"✓ Using portable Java: {selected_java}")
            return selected_java

        # 2. If portable folder is missing, check the system PATH
        system_java = shutil.which("java")
        if system_java:
            # Quick check: does it run?
            try:
                # We use your utils to check if the version is high enough (21+)
                ver, _ = system_checks.get_java_version(system_java)
                if ver and ver >= 21:
                    selected_java = self._prefer_javaw_on_windows(system_java)
                    self._emit_status(status_callback, f"✓ Using system Java {ver}")
                    return selected_java
            except:
                pass

        # 3. If still nothing, CALL the auto-install function from utils.py
        self._emit_status(status_callback, "Java not found. Attempting auto-install via Winget...")
        
        # Calling the function defined in utils.py
        ok, msg = system_checks.ensure_java_21()
        
        if ok:
            # If install worked, system PATH should now have it
            new_system_java = shutil.which("java")
            if new_system_java:
                self._emit_status(status_callback, "✓ Auto-install successful!")
                return self._prefer_javaw_on_windows(new_system_java)
        
        # 4. Total Failure
        error_msg = f"Java 21 is required. {msg}"
        self._emit_status(status_callback, f"ERROR: {error_msg}", is_error=True)
        return None

    def _prefer_javaw_on_windows(self, java_path):
        """Use javaw.exe on Windows to avoid console window popups."""
        if os.name != "nt":
            return java_path
        if not java_path:
            return java_path
        java_dir = os.path.dirname(java_path)
        javaw_path = os.path.join(java_dir, "javaw.exe")
        if os.path.exists(javaw_path):
            return javaw_path
        return java_path

    def ensure_fabric_installed(self, status_callback=None):
        if self.loader_type != "fabric":
            return self.minecraft_version
        loader_version = self._resolve_loader_version(status_callback)
        target_fabric_id = f"fabric-loader-{loader_version}-{self.minecraft_version}"
        if self._is_version_installed(target_fabric_id):
            self._emit_status(status_callback, f"Fabric {loader_version} already installed.")
            return target_fabric_id

        self._emit_status(status_callback, f"Installing Fabric loader {loader_version}...")
        minecraft_launcher_lib.fabric.install_fabric(
            self.minecraft_version,
            self.config.minecraft_directory,
            loader_version=loader_version
        )

        installed_ids = self._get_installed_version_ids()
        if target_fabric_id in installed_ids:
            return target_fabric_id

        prefix = "fabric-loader-"
        suffix = f"-{self.minecraft_version}"
        compatible = sorted([v for v in installed_ids if v.startswith(prefix) and v.endswith(suffix)], reverse=True)
        if compatible:
            self._emit_status(status_callback, f"Using detected Fabric version {compatible[0]}.")
            return compatible[0]
        raise RuntimeError("Fabric installation failed or no compatible Fabric version found.")

    def build_launch_command(self, username, ram_gb, status_callback=None):
        self.ensure_minecraft_installed(status_callback)
        version_id = self.ensure_fabric_installed(status_callback)
        self._emit_status(status_callback, "Preparing launch command...")

        options = {
            "username": username,
            "uuid": str(uuid.uuid4()),
            "token": "0",
            "gameDirectory": self.config.custom_game_dir,
            "jvmArguments": [
                f"-Xmx{ram_gb}G", 
                f"-Xms{ram_gb}G", # Synced Start RAM with Max RAM
                "-Djava.net.preferIPv4Stack=true",
                "-XX:+UnlockExperimentalVMOptions",
                "-XX:+UseG1GC"
            ],
            "launcherName": "FluxHive Launcher",
            #"server": "FluxHive.play.hosting",
            #"port": "25565"
        }

        java_path = self._resolve_java_executable(status_callback)
        if java_path:
            options["executablePath"] = java_path
        else:
            self._emit_status(status_callback, "Java not found in PATH, using launcher defaults.")

        command = minecraft_launcher_lib.command.get_minecraft_command(
            version_id,
            self.config.minecraft_directory,
            options
        )
        return command, version_id


class LaunchWorker(QThread):
    status_changed = pyqtSignal(str)
    launch_started = pyqtSignal()
    launch_finished = pyqtSignal(bool, str)

    def __init__(self, install_manager, username, ram_gb):
        super().__init__()
        self.install_manager = install_manager
        self.username = username
        self.ram_gb = ram_gb

    def run(self):
        try:
            command, version_id = self.install_manager.build_launch_command(
                self.username,
                self.ram_gb,
                status_callback=self.status_changed.emit
            )
            self.status_changed.emit(f"Launching {version_id}...")
            self.launch_started.emit()
            launch_kwargs = {}
            if os.name == "nt":
                startup_info = subprocess.STARTUPINFO()
                startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startup_info.wShowWindow = 0  # SW_HIDE
                launch_kwargs["startupinfo"] = startup_info
                launch_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
                launch_kwargs["stdin"] = None
                launch_kwargs["stdout"] = None
                launch_kwargs["stderr"] = None
            return_code = subprocess.call(command, **launch_kwargs)
            if return_code != 0:
                raise RuntimeError(f"Minecraft exited with code {return_code}.")
            self.launch_finished.emit(True, "Game session ended.")
        except Exception as exc:
            logging.exception("Launch failed")
            self.launch_finished.emit(False, str(exc))


class HomePage(QWidget):
    """Home page with Play button and version info"""
    def __init__(self, launcher_config, version_options, version_change_callback=None):
        super().__init__()
        self.launcher = launcher_config
        self.version_options = version_options or []
        self._version_change_callback = version_change_callback
        self.version_selector = None
        self.accounts_file = os.path.join(self.launcher.custom_game_dir, "offline_accounts.json")
        self.offline_accounts = []
        self.last_used_account = ""
        self._loading_account_ui = False
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(24)
        layout.setContentsMargins(34, 24, 34, 24)

        mods_dir = os.path.join(self.launcher.custom_game_dir, "mods")
        mod_count = 0
        if os.path.exists(mods_dir):
            mod_count = len([f for f in os.listdir(mods_dir) if f.endswith(('.jar', '.zip'))])
        
        # ===== HERO CARD =====
        hero = QFrame()
        hero.setObjectName("HeroCard")
        hero.setMinimumHeight(160)
        hero.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        hero.setStyleSheet("""
            #HeroCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                            stop:0 rgba(10, 15, 24, 0.96), stop:1 rgba(18, 24, 35, 0.96));
                border: 1px solid #23354e;
                border-radius: 14px;
            }
        """)
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(26, 20, 26, 20)
        hero_layout.setSpacing(10)

        hero_version = QLabel(f"Version {APP_VERSION}")
        hero_version.setStyleSheet("""
            color: #7FB3FF;
            font-size: 12px;
            font-weight: 600;
            background: rgba(17, 33, 54, 0.85);
            border: 1px solid #345982;
            border-radius: 8px;
            padding: 4px 10px;
        """)
        hero_layout.addWidget(hero_version, alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        hero_title = QLabel("FluxHive Launcher")
        hero_title.setStyleSheet("color: #F4F8FF; font-size: 30px; font-weight: 700;")
        hero_layout.addWidget(hero_title)

        hero_desc = QLabel(APP_TAGLINE)
        hero_desc.setWordWrap(True)
        hero_desc.setStyleSheet("color: #C6D4EE; font-size: 13px; line-height: 1.4;")
        hero_layout.addWidget(hero_desc)
        
        layout.addWidget(hero)

        layout.addSpacing(28)

        # ===== VERSION SELECTOR SECTION =====
        version_section = QVBoxLayout()
        version_section.setSpacing(8)

        versions_label = QLabel("VERSIONS")
        versions_label.setStyleSheet("color: #93ADD1; font-size: 11px; font-weight: bold; letter-spacing: 1.5px;")
        version_section.addWidget(versions_label)

        version_box = QFrame()
        version_box.setObjectName("VersionBox")
        version_box.setMinimumWidth(700)
        version_box.setMinimumHeight(96)
        version_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        version_box.setStyleSheet("""
            #VersionBox {
                background: rgba(22, 34, 51, 0.96);
                border: 1px solid #2a3f5b;
                border-radius: 10px;
            }
        """)
        version_box_layout = QVBoxLayout(version_box)
        version_box_layout.setContentsMargins(12, 8, 12, 8)
        version_box_layout.setSpacing(4)

        self.version_selector = QComboBox()
        self.version_selector.setObjectName("VersionSelector")
        self.version_selector.setMinimumHeight(36)
        self.version_selector.setMinimumWidth(640)
        self.version_selector.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.version_selector.setCursor(Qt.CursorShape.PointingHandCursor)
        self.version_selector.setStyleSheet("""
            QComboBox#VersionSelector {
                background: #111a28;
                border: 1px solid #2d4361;
                border-radius: 6px;
                color: #E9F2FF;
                padding: 6px 12px;
                font-weight: 700;
                font-size: 13px;
            }
            QComboBox#VersionSelector::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox#VersionSelector QAbstractItemView {
                background: #111a28;
                color: #E9F2FF;
                selection-background-color: #2f5f9b;
                border: 1px solid #2a3f5b;
                border-radius: 6px;
            }
        """)
        selector_labels = [opt["label"] for opt in self.version_options]
        if selector_labels:
            self.version_selector.addItems(selector_labels)
            self.version_selector.currentIndexChanged.connect(self._on_version_selector_changed)
        else:
            self.version_selector.addItem("No builds configured")
            self.version_selector.setEnabled(False)
        version_box_layout.addWidget(self.version_selector)

        version_box_layout.addSpacing(10)

        mods_indicator = QLabel(f"{mod_count} Mods ready")
        mods_indicator.setStyleSheet("color: #7FB3FF; font-weight: bold; font-size: 12px;")
        mods_indicator.setAlignment(Qt.AlignmentFlag.AlignLeft)
        version_box_layout.addWidget(mods_indicator)
        
        version_section.addWidget(version_box)
        layout.addLayout(version_section)
        layout.addSpacing(8)
        
        # ===== ACCOUNT MANAGER SECTION =====
        account_section = QVBoxLayout()
        account_section.setSpacing(8)

        player_label = QLabel("ACCOUNT MANAGER")
        player_label.setStyleSheet("color: #93ADD1; font-size: 11px; font-weight: bold; letter-spacing: 1.5px;")
        account_section.addWidget(player_label)

        player_frame = QFrame()
        player_frame.setObjectName("PlayerCard")
        player_frame.setMinimumHeight(130)
        player_frame.setStyleSheet("""
            #PlayerCard {
                background: rgba(22, 34, 51, 0.96);
                border: 1px solid #2a3f5b;
                border-radius: 10px;
            }
        """)
        player_layout = QVBoxLayout(player_frame)
        player_layout.setContentsMargins(16, 16, 16, 16)
        player_layout.setSpacing(12)

        # Row 1: Saved Account Dropdown & Remove Button
        row1 = QHBoxLayout()
        row1.setSpacing(12)
        
        self.account_selector = QComboBox()
        self.account_selector.setMinimumHeight(40)
        self.account_selector.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.account_selector.setStyleSheet("""
            QComboBox {
                background: #111a28;
                border: 1px solid #2d4361;
                border-radius: 6px;
                color: #E9F2FF;
                padding: 8px 14px;
                font-size: 14px;
                font-weight: bold;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox QAbstractItemView {
                background: #111a28;
                color: #E9F2FF;
                selection-background-color: #2f5f9b;
                border: 1px solid #2a3f5b;
            }
        """)
        
        self.remove_account_btn = QPushButton("Remove Selected")
        self.remove_account_btn.setMinimumHeight(40)
        self.remove_account_btn.setMinimumWidth(130)
        self.remove_account_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.remove_account_btn.setStyleSheet(self.get_small_button_style())

        row1.addWidget(self.account_selector)
        row1.addWidget(self.remove_account_btn)
        player_layout.addLayout(row1)

        # Row 2: Username Input & Save Button
        row2 = QHBoxLayout()
        row2.setSpacing(12)
        
        self.username = QLineEdit()
        self.username.setPlaceholderText("Enter your Account name...")
        self.username.setMaxLength(24)
        self.username.setMinimumHeight(40)
        self.username.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.username.setStyleSheet("""
            QLineEdit {
                background: #0f1826;
                border: 1px solid #335079;
                color: #FFFFFF;
                padding: 10px 12px;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }
            QLineEdit:focus {
                border: 1px solid #5e8dc8;
                background: #121f31;
            }
            QLineEdit::placeholder {
                color: #9A9A9A;
            }
        """)

        self.save_account_btn = QPushButton("Save Player")
        self.save_account_btn.setMinimumHeight(40)
        self.save_account_btn.setMinimumWidth(130)
        self.save_account_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_account_btn.setStyleSheet(self.get_small_button_style())

        row2.addWidget(self.username)
        row2.addWidget(self.save_account_btn)
        player_layout.addLayout(row2)

        account_section.addWidget(player_frame)
        layout.addLayout(account_section)
        
        # ===== LAUNCH STATUS (READY Text Removed) =====
        self.launch_status = QLabel("") 
        self.launch_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.launch_status.setStyleSheet("color: #8FB2DE; font-size: 12px; font-weight: 600; padding-top: 8px;")
        layout.addWidget(self.launch_status)
        
        self.play_btn = QPushButton("Launch Game")
        self.play_btn.hide()

        layout.addStretch(1)

        self.refresh_account_selector()
        self.account_selector.currentTextChanged.connect(self.on_account_selected)
        self.save_account_btn.clicked.connect(self.add_current_account)
        self.remove_account_btn.clicked.connect(self.remove_selected_account)
        self.username.textChanged.connect(self.update_account_actions)

    def get_small_button_style(self):
        return """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                            stop:0 #1f56b3, stop:1 #2f6fd1);
                border: 1px solid #5f9dff;
                color: white;
                padding: 0 14px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                            stop:0 #2f6fd1, stop:1 #5f9dff);
            }
            QPushButton:pressed {
                background: #1f56b3;
            }
            QPushButton:disabled {
                background: #1a2a3f;
                border: 1px solid #2a3f5b;
                color: #556b87;
            }
        """

    def load_accounts(self):
        if not os.path.exists(self.accounts_file):
            self.offline_accounts = []
            self.last_used_account = ""
            return
        try:
            with open(self.accounts_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            accounts = data.get("accounts", [])
            accounts = [str(a).strip() for a in accounts if str(a).strip()]
            self.offline_accounts = list(dict.fromkeys(accounts))[:MAX_OFFLINE_ACCOUNTS]
            self.last_used_account = self._normalize_username(data.get("last_used", ""))
            if self.last_used_account and self.last_used_account not in self.offline_accounts:
                self.offline_accounts.insert(0, self.last_used_account)
                self.offline_accounts = self.offline_accounts[:MAX_OFFLINE_ACCOUNTS]
        except Exception as exc:
            print(f" Failed to read local accounts: {exc}")
            self.offline_accounts = []
            self.last_used_account = ""

    def save_accounts(self, last_used=None):
        if last_used is None:
            last_used = self.last_used_account
        payload = {
            "accounts": self.offline_accounts,
            "last_used": last_used
        }
        try:
            os.makedirs(os.path.dirname(self.accounts_file), exist_ok=True)
            with open(self.accounts_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception as exc:
            print(f" Failed to save local accounts: {exc}")

    def refresh_account_selector(self):
        self._loading_account_ui = True
        self.account_selector.clear()
        self.load_accounts()
        if self.offline_accounts:
            self.account_selector.setEnabled(True)
            self.account_selector.addItems(self.offline_accounts)
            selected = self.last_used_account if self.last_used_account in self.offline_accounts else self.offline_accounts[0]
            self.account_selector.setCurrentText(selected)
            self.username.setText(selected)
        else:
            self.account_selector.addItem("No saved accounts")
            self.account_selector.setEnabled(False)
            self.username.clear()
        self._loading_account_ui = False
        self.update_account_actions()

    def add_current_account(self):
        username = self._normalize_username(self.username.text())
        if not username:
            return
        self.username.setText(username)
        if not self.account_selector.isEnabled():
            self.account_selector.setEnabled(True)
            self.account_selector.clear()
        if username in self.offline_accounts:
            self.offline_accounts.remove(username)
        self.offline_accounts.insert(0, username)
        self.offline_accounts = self.offline_accounts[:MAX_OFFLINE_ACCOUNTS]
        self.last_used_account = username
        self.save_accounts(username)
        self.refresh_account_selector()

    def remove_selected_account(self):
        if not self.account_selector.isEnabled():
            return
        current = self.account_selector.currentText().strip()
        if not current:
            return
        if current in self.offline_accounts:
            self.offline_accounts.remove(current)
        self.last_used_account = self.offline_accounts[0] if self.offline_accounts else ""
        self.save_accounts(self.last_used_account)
        self.refresh_account_selector()

    def on_account_selected(self, account_name):
        if self._loading_account_ui:
            return
        account_name = self._normalize_username(account_name)
        if not account_name:
            return
        self.username.setText(account_name)
        self.last_used_account = account_name
        self.save_accounts(account_name)

    def sync_current_username(self):
        username = self._normalize_username(self.username.text())
        if not username:
            return
        self.username.setText(username)
        if username in self.offline_accounts:
            self.offline_accounts.remove(username)
        self.offline_accounts.insert(0, username)
        self.offline_accounts = self.offline_accounts[:MAX_OFFLINE_ACCOUNTS]
        self.last_used_account = username
        self.save_accounts(username)

    def update_account_actions(self):
        has_name = bool(self.username.text().strip())
        has_accounts = bool(self.offline_accounts)
        self.save_account_btn.setEnabled(has_name)
        self.remove_account_btn.setEnabled(has_accounts and self.account_selector.isEnabled())

    def set_selected_version(self, index, emit_signal=False):
        if not self.version_options or self.version_selector is None:
            return
        index = max(0, min(index, len(self.version_options) - 1))
        if emit_signal:
            self.version_selector.setCurrentIndex(index)
        else:
            self.version_selector.blockSignals(True)
            self.version_selector.setCurrentIndex(index)
            self.version_selector.blockSignals(False)

    def _on_version_selector_changed(self, index):
        if not self.version_options:
            return
        if index < 0 or index >= len(self.version_options):
            return
        if callable(self._version_change_callback):
            self._version_change_callback(self.version_options[index])

    def _normalize_username(self, value):
        username = str(value).strip()
        if not username:
            return ""
        filtered = "".join(ch for ch in username if ch.isalnum() or ch in ("_", "-"))
        return filtered

    def set_launch_status(self, text, is_error=False):
        color = "#FF8A8A" if is_error else "#8FB2DE"
        self.launch_status.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: 600; padding-top: 8px;")
        self.launch_status.setText(text)


class ModsPage(QWidget):
    """Mods management page"""
    def __init__(self, launcher_config):
        super().__init__()
        self.launcher = launcher_config
        self.mods_dir = os.path.join(launcher_config.custom_game_dir, "mods")
        os.makedirs(self.mods_dir, exist_ok=True)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)
        
        title = QLabel("MODS")
        title_font = QFont("Segoe UI", 32)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #5f9dff;")
        layout.addWidget(title)
        
        scroll = QScrollArea()
        scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #1f56b3;
                background: rgba(31, 86, 179, 0.05);
                border-radius: 8px;
            }
            QScrollBar:vertical {
                background: #1a1a2e;
                width: 8px;
            }
            QScrollBar::handle:vertical {
                background: #2f6fd1;
                border-radius: 4px;
            }
        """)
        scroll.setWidgetResizable(True)
        
        content = QWidget()
        scroll_layout = QVBoxLayout(content)
        scroll_layout.setSpacing(10)
        
        mods_found = False
        if os.path.exists(self.mods_dir):
            for mod_file in os.listdir(self.mods_dir):
                if mod_file.endswith(('.jar', '.zip')):
                    mod_frame = self.create_mod_item(mod_file)
                    scroll_layout.addWidget(mod_frame)
                    mods_found = True
        
        if not mods_found:
            no_mods = QLabel("No mods installed. Click 'Open Mods Folder' to add mods.")
            no_mods.setStyleSheet("color: #b0b0b0; padding: 20px;")
            no_mods.setAlignment(Qt.AlignmentFlag.AlignCenter)
            scroll_layout.addWidget(no_mods)
        
        scroll_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        
        button_layout = QHBoxLayout()
        
        open_folder_btn = QPushButton("Open Mods Folder")
        open_folder_btn.setMinimumHeight(45)
        open_folder_btn.setStyleSheet(self.get_button_style())
        open_folder_btn.clicked.connect(self.open_mods_folder)
        button_layout.addWidget(open_folder_btn)
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setMinimumHeight(45)
        refresh_btn.setStyleSheet(self.get_button_style())
        refresh_btn.clicked.connect(self.refresh_mods)
        button_layout.addWidget(refresh_btn)
        
        layout.addLayout(button_layout)

    def create_mod_item(self, mod_name):
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background: rgba(31, 86, 179, 0.1);
                border: 1px solid #1f56b3;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        frame_layout = QHBoxLayout(frame)
        frame_layout.setContentsMargins(10, 10, 10, 10)
        
        checkbox = QCheckBox(mod_name)
        checkbox.setCheckState(Qt.CheckState.Checked)
        checkbox.setStyleSheet("""
            QCheckBox {
                color: #5f9dff;
                spacing: 8px;
                font-weight: bold;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox::indicator:unchecked {
                background: #2d2d3d;
                border: 2px solid #1f56b3;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                background: #2f6fd1;
                border: 2px solid #1f56b3;
                border-radius: 3px;
            }
        """)
        frame_layout.addWidget(checkbox)
        frame_layout.addStretch()
        
        return frame

    def refresh_mods(self):
        print(f" Mods refreshed from: {self.mods_dir}")

    def open_mods_folder(self):
        try:
            os.startfile(self.mods_dir)
        except Exception as exc:
            print(f" Could not open mods folder: {exc}")

    def get_button_style(self):
        return """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                            stop:0 #1f56b3, stop:1 #2f6fd1);
                border: none;
                color: white;
                padding: 10px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                            stop:0 #2f6fd1, stop:1 #5f9dff);
            }
        """


class SettingsPage(QWidget):
    """Settings page"""
    def __init__(self, launcher_config):
        super().__init__()
        self.launcher = launcher_config
        self.settings_path = os.path.join(self.launcher.custom_game_dir, "launcher_settings.json")
        self.settings = self.load_settings()
        self.init_ui()

    def load_settings(self):
        defaults = {
            "ram_gb": get_auto_ram_allocation()
        }
        if not os.path.exists(self.settings_path):
            return defaults
        try:
            with open(self.settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                defaults.update(data)
        except Exception as exc:
            print(f" Failed to load launcher settings: {exc}")
        return defaults

    def save_settings(self):
        try:
            os.makedirs(os.path.dirname(self.settings_path), exist_ok=True)
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2)
        except Exception as exc:
            print(f" Failed to save launcher settings: {exc}")

    def _on_ram_changed(self, value):
        self.ram_settings_label.setText(f"{value}/16 RAM")
        self.settings["ram_gb"] = int(value)
        self.save_settings()

    def init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setStyleSheet("QScrollArea { background: transparent; }")
        root_layout.addWidget(scroll_area)

        content_widget = QWidget()
        scroll_area.setWidget(content_widget)

        layout = QVBoxLayout(content_widget)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 10, 20, 30)
        
        title = QLabel("SETTINGS")
        title_font = QFont("Segoe UI", 34); title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #5f9dff;")
        layout.addWidget(title)
        
        ram_label = QLabel("MEMORY ALLOCATION (RAM)")
        ram_label.setStyleSheet("color: #bcd3ff; font-size: 13px; font-weight: 900; letter-spacing: 1.5px; margin-bottom: 6px;")
        layout.addWidget(ram_label)
        
        ram_frame = QFrame()
        ram_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                            stop:0 rgba(31, 86, 179, 0.15), stop:1 rgba(31, 86, 179, 0.05));
                border: 3px solid #1f56b3;
                border-radius: 15px;
                padding: 30px;
            }
        """)
        ram_frame.setMinimumHeight(140)
        ram_layout = QVBoxLayout(ram_frame)
        ram_layout.setSpacing(15)
        ram_layout.setContentsMargins(20, 20, 20, 20)
        
        ram_desc = QLabel("Choose how much system RAM Minecraft can use (2GB - 16GB).")
        ram_desc.setStyleSheet("color: #c8d6f0; font-size: 14px; font-weight: 500;")
        ram_layout.addWidget(ram_desc)
        
        ram_slider_layout = QHBoxLayout()
        ram_slider_layout.setSpacing(15)
        
        self.ram_settings_slider = QSlider(Qt.Orientation.Horizontal)
        self.ram_settings_slider.setRange(2, 16)
        saved_ram = int(self.settings.get("ram_gb", get_auto_ram_allocation()))
        saved_ram = max(2, min(16, saved_ram))
        self.ram_settings_slider.setValue(saved_ram)
        self.ram_settings_slider.setMinimumHeight(40)
        self.ram_settings_slider.setStyleSheet(self.get_slider_style())
        
        self.ram_settings_label = QLabel(f"{saved_ram}/16 RAM")
        self.ram_settings_label.setStyleSheet("color: #2f6fd1; font-weight: bold; font-size: 18px; min-width: 70px;")
        self.ram_settings_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.ram_settings_slider.valueChanged.connect(self._on_ram_changed)
        self.ram_settings_slider.setTickPosition(QSlider.TickPosition.NoTicks)
        
        ram_slider_layout.addWidget(self.ram_settings_slider)
        ram_slider_layout.addWidget(self.ram_settings_label)
        ram_layout.addLayout(ram_slider_layout)
        
        layout.addWidget(ram_frame)

        layout.addStretch()

    def get_slider_style(self):
        return """
            QSlider {
                background: transparent;
            }
            QSlider::groove:horizontal {
                background: rgba(255, 255, 255, 0.08);
                height: 6px;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                            stop:0 #1f56b3, stop:1 #2f6fd1);
                height: 6px;
                border-radius: 3px;
            }
            QSlider::add-page:horizontal {
                background: rgba(255, 255, 255, 0.04);
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                            stop:0 #2b66c8, stop:1 #4a85ff);
                width: 24px;
                margin: -10px 0;
                border-radius: 12px;
                border: 2px solid #76b0ff;
            }
            QSlider::handle:horizontal:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                            stop:0 #4a85ff, stop:1 #76b0ff);
            }
        """


class LauncherConfig:
    """Configuration holder"""
    def __init__(self):
        try:
            self.minecraft_directory = minecraft_launcher_lib.utils.get_minecraft_directory()
        except Exception:
            self.minecraft_directory = os.path.expanduser("~/.minecraft")
        
        self.current_project_dir = os.path.dirname(os.path.abspath(__file__))
        self.custom_game_dir = os.path.join(self.current_project_dir, "game_data")
        os.makedirs(os.path.join(self.custom_game_dir, "mods"), exist_ok=True)


class WaterLauncher(DraggableWindow):
    """Main application window"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FluxHive Launcher - Fabric 1.21.1")
        self.setMinimumSize(1050, 720)
        self.resize(1200, 720) # Fixed window height bug
        self.setWindowIcon(QIcon())
        self._window_fade_anim = None
        self._page_fade_anim = None
        self._did_show_animation = False
        self.nav_buttons = []
        self.launch_worker = None
        self._launch_controls_ready = True
        
        # Config
        self.config = LauncherConfig()
        self.version_options = VERSION_OPTIONS or []
        default_profile = self.version_options[0] if self.version_options else None
        self.install_manager = InstallManager(self.config, default_profile)
        
        self.apply_global_style()
        self.init_ui()

    def apply_global_style(self):
        self.setStyleSheet("""
            QMainWindow { background: #070c14; }
            QWidget { background-color: #070c14; }
            QLabel { color: #ffffff; font-family: 'Segoe UI'; background: transparent; }
        """)

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        self.title_bar = TitleBar(self)
        main_layout.addWidget(self.title_bar)
        
        content_widget = QWidget()
        content_widget.setObjectName("ContentRoot")
        content_widget.setStyleSheet("""
            #ContentRoot {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                            stop:0 #070c14, stop:1 #0b1220);
            }
        """)
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(20, 18, 20, 16)
        content_layout.setSpacing(14)
        
        self.pages = QStackedWidget()
        self.pages.setObjectName("MainPages")
        
        self.home_page = HomePage(self.config, self.version_options, self._on_version_option_selected)
        self.mods_page = ModsPage(self.config)
        self.settings_page = SettingsPage(self.config)
        
        self.pages.addWidget(self.home_page)
        self.pages.addWidget(self.mods_page)
        self.pages.addWidget(self.settings_page)
        
        self.pages.setStyleSheet("""
            #MainPages {
                background: transparent;
                border: 1px solid #1e2f46;
                border-radius: 12px;
            }
        """)
        content_layout.addWidget(self.pages, 1)

        bottom_nav = QFrame()
        bottom_nav.setFixedHeight(68)
        bottom_nav.setStyleSheet("""
            QFrame {
                background: rgba(10, 15, 24, 0.96);
                border: 1px solid #20324a;
                border-radius: 12px;
            }
        """)
        nav_layout = QHBoxLayout(bottom_nav)
        nav_layout.setContentsMargins(16, 10, 16, 10)
        nav_layout.setSpacing(14)

        self.home_tab_btn = QPushButton("Home")
        self.home_tab_btn.setMinimumHeight(42)
        self.home_tab_btn.setStyleSheet(self.get_nav_button_style(active=False))
        self.home_tab_btn.clicked.connect(lambda: self.switch_page(0))
        nav_layout.addWidget(self.home_tab_btn, 1)

        self.bottom_play_btn = QPushButton("PLAY")
        self.bottom_play_btn.setMinimumHeight(48)
        font = QFont("Segoe UI", 17); font.setBold(True); self.bottom_play_btn.setFont(font)
        self.bottom_play_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1f56b3, stop:1 #2f6fd1);
                border: 2px solid #88b5ff;
                border-radius: 10px;
                color: white;
            }
            QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2b66c8, stop:1 #3b7fe3); }
            QPushButton:disabled { background: #1a2a3f; border: 2px solid #2a3f5b; color: #556b87; }
        """)
        self.bottom_play_btn.clicked.connect(self.launch_game)
        nav_layout.addWidget(self.bottom_play_btn, 1)

        self.mods_tab_btn = QPushButton("Mod Manager")
        self.mods_tab_btn.setMinimumHeight(42)
        self.mods_tab_btn.setStyleSheet(self.get_nav_button_style(active=False))
        self.mods_tab_btn.clicked.connect(lambda: self.switch_page(1))
        nav_layout.addWidget(self.mods_tab_btn, 1)

        content_layout.addWidget(bottom_nav)
        main_layout.addWidget(content_widget)
        
        self.home_page.play_btn.clicked.connect(self.launch_game)
        self.home_page.username.textChanged.connect(self.title_bar.set_account_name)
        self.home_page.username.textChanged.connect(self._handle_username_change)
        
        if self.version_options:
            self.home_page.set_selected_version(0, emit_signal=True)
            
        self.title_bar.set_account_name(self.home_page.username.text())
        self.animate_page_transition(0)
        self.update_bottom_nav(0)
        self._apply_launch_button_state()

    def get_nav_button_style(self, active=False):
        if active:
            return """
                QPushButton {
                    background: #1f56b3;
                    border: 1px solid #7fb1ff;
                    border-radius: 10px;
                    color: white;
                    font-size: 15px;
                    font-weight: 700;
                }
            """
        return """
            QPushButton {
                background: #162435;
                border: 1px solid #2b405d;
                border-radius: 10px;
                color: #d6e5fa;
                font-size: 15px;
                font-weight: 600;
            }
            QPushButton:hover:!disabled { background: #1e3249; border: 1px solid #416390; }
            QPushButton:disabled { background: #101926; border: 1px solid #1a2a3f; color: #4a5c73; }
        """

    def showEvent(self, event):
        super().showEvent(event)
        if self._did_show_animation: return
        self._did_show_animation = True
        self.setWindowOpacity(0.0)
        self._window_fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self._window_fade_anim.setDuration(220)
        self._window_fade_anim.setStartValue(0.0)
        self._window_fade_anim.setEndValue(1.0)
        self._window_fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._window_fade_anim.start()

    def animate_page_transition(self, index):
        self.pages.setCurrentIndex(index)
        current_page = self.pages.currentWidget()
        if not current_page: return
        opacity_effect = QGraphicsOpacityEffect(current_page)
        current_page.setGraphicsEffect(opacity_effect)
        self._page_fade_anim = QPropertyAnimation(opacity_effect, b"opacity")
        self._page_fade_anim.setDuration(180)
        self._page_fade_anim.setStartValue(0.70)
        self._page_fade_anim.setEndValue(1.0)
        self._page_fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._page_fade_anim.finished.connect(lambda: current_page.setGraphicsEffect(None))
        self._page_fade_anim.start()

    def switch_page(self, index):
        if self.pages.currentIndex() == index: return
        self.animate_page_transition(index)
        self.update_bottom_nav(index)

    def update_bottom_nav(self, index):
        self.home_tab_btn.setStyleSheet(self.get_nav_button_style(active=index == 0))
        self.mods_tab_btn.setStyleSheet(self.get_nav_button_style(active=index == 1))

    def switch_to_settings(self):
        self.animate_page_transition(2)
        self.update_bottom_nav(2)

    def _handle_username_change(self, _text):
        self._apply_launch_button_state()

    def _apply_launch_button_state(self):
        has_name = bool(self.home_page._normalize_username(self.home_page.username.text()))
        play_enabled = self._launch_controls_ready and has_name
        self.bottom_play_btn.setEnabled(play_enabled)
        self.home_page.save_account_btn.setEnabled(self._launch_controls_ready and has_name)

    def _set_launch_controls_enabled(self, enabled):
        self._launch_controls_ready = enabled
        self._apply_launch_button_state()
    
    def _on_version_option_selected(self, profile):
        if not profile: return
        self.install_manager.set_version_profile(profile)
        # Disable/Grey out Mod Manager for Vanilla
        is_vanilla = profile.get("loader", "").lower() == "vanilla"
        self.mods_tab_btn.setEnabled(not is_vanilla)
        # If user is on mods page and selects vanilla, boot them home
        if is_vanilla and self.pages.currentIndex() == 1:
            self.switch_page(0)

    def _on_launch_status(self, message):
        self.home_page.set_launch_status(message)

    def _on_launch_started(self):
        self.home_page.set_launch_status("Launching...")
        self.hide()

    def _on_launch_finished(self, success, message):
        self._set_launch_controls_enabled(True)
        if self.launch_worker:
            self.launch_worker.deleteLater()
        if success:
                self.home_page.set_launch_status("Game closed.")
                self.show()
                return
        self.home_page.set_launch_status(f"Launch failed: {message}", is_error=True)
        self.show()

    def launch_game(self):
        if self.launch_worker is not None and self.launch_worker.isRunning(): return
        self.home_page.sync_current_username()
        username = self.home_page._normalize_username(self.home_page.username.text())
        if not username:
            self.home_page.set_launch_status("Enter a player name.", is_error=True)
            return
        ram = self.settings_page.ram_settings_slider.value()
        self._set_launch_controls_enabled(False)
        self.launch_worker = LaunchWorker(self.install_manager, username, ram)
        self.launch_worker.status_changed.connect(self._on_launch_status)
        self.launch_worker.launch_started.connect(self._on_launch_started)
        self.launch_worker.launch_finished.connect(self._on_launch_finished)
        self.launch_worker.start()


if __name__ == "__main__":
    hide_windows_console()
    app = QApplication(sys.argv)
    window = WaterLauncher()
    window.show()
    sys.exit(app.exec())