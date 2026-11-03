import customtkinter as ctk
from tkinter import messagebox
import time
import threading
import os
import json
import ctypes
import pygetwindow as gw
import pystray
from PIL import Image, ImageDraw, ImageFont
import sys

# === Native Windows Inactivity Detection ===
class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

# === Atalhos Globais Nativos do Windows (sem dependência do módulo 'keyboard' que causa falso positivo) ===
class NativeHotkeys:
    def __init__(self, root=None):
        self.root = root
        self.hotkeys = {}
        self.running = False
        self.thread = None
        self._next_id = 1

    def _parse_keys(self, shortcut_str):
        parts = [p.strip().lower() for p in shortcut_str.split('+')]
        mod = 0x4000  # MOD_NOREPEAT
        vk = 0
        for p in parts:
            if p in ('ctrl', 'control'):
                mod |= 0x0002
            elif p == 'alt':
                mod |= 0x0001
            elif p == 'shift':
                mod |= 0x0004
            elif len(p) == 1:
                vk = ord(p.upper())
            elif p.startswith('f') and p[1:].isdigit():
                vk = 0x70 + int(p[1:]) - 1
        return mod, vk

    def register(self, shortcut_str, callback):
        mod, vk = self._parse_keys(shortcut_str)
        if vk:
            hid = self._next_id
            self._next_id += 1
            self.hotkeys[hid] = (shortcut_str, mod, vk, callback)
            return hid
        return None

    def start(self):
        if self.running:
            self.stop()
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        registered_ids = []
        for hid, (s, mod, vk, cb) in list(self.hotkeys.items()):
            if ctypes.windll.user32.RegisterHotKey(None, hid, mod, vk):
                registered_ids.append(hid)
        from ctypes import wintypes
        msg = wintypes.MSG()
        while self.running:
            if ctypes.windll.user32.PeekMessageW(ctypes.byref(msg), None, 0x0312, 0x0312, 1):
                hid = msg.wParam
                if hid in self.hotkeys:
                    cb = self.hotkeys[hid][3]
                    if self.root:
                        self.root.after(0, cb)
                    else:
                        cb()
            time.sleep(0.05)
        for hid in registered_ids:
            ctypes.windll.user32.UnregisterHotKey(None, hid)

    def stop(self):
        self.running = False
        self.hotkeys.clear()
        self._next_id = 1

def get_idle_seconds():
    """Returns user idle time in seconds using Windows native API (GetLastInputInfo)."""
    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
        millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
        return max(0.0, millis / 1000.0)
    return 0.0

def resource_path(relative_path):
    """Returns absolute path to resource, compatible with PyInstaller and direct execution."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, relative_path)

# === Built-in Theme Configuration (no external files) ===
THEME_CONFIG = {
    "CTk": {
        "fg_color": ["#181E29", "#181E29"],
        "bg_color": "#181E29"
    },
    "CTkToplevel": {
        "fg_color": ["#181E29", "#181E29"]
    },
    "CTkFrame": {
        "fg_color": ["#232B3B", "#232B3B"],
        "border_color": ["#232B3B", "#232B3B"],
        "corner_radius": 10,
        "border_width": 0
    },
    "CTkLabel": {
        "fg_color": ["#232B3B", "#232B3B"],
        "text_color": ["#FFFFFF", "#FFFFFF"],
        "corner_radius": 0
    },
    "CTkButton": {
        "fg_color": ["#22D3EE", "#22D3EE"],
        "text_color": ["#FFFFFF", "#FFFFFF"],
        "text_color_disabled": ["#A1A7B3", "#A1A7B3"],
        "hover_color": ["#06B6D4", "#06B6D4"],
        "border_color": ["#22D3EE", "#22D3EE"],
        "corner_radius": 12,
        "border_width": 0
    },
    "CTkComboBox": {
        "fg_color": ["#323B4C", "#323B4C"],
        "text_color": ["#FFFFFF", "#FFFFFF"],
        "text_color_disabled": ["#A1A7B3", "#A1A7B3"],
        "button_color": ["#323B4C", "#323B4C"],
        "button_hover_color": ["#323B4C", "#323B4C"],
        "dropdown_fg_color": ["#323B4C", "#323B4C"],
        "corner_radius": 10,
        "border_width": 0,
        "border_color": ["#323B4C", "#323B4C"]
    },
    "CTkEntry": {
        "fg_color": ["#323B4C", "#323B4C"],
        "text_color": ["#FFFFFF", "#FFFFFF"],
        "placeholder_text_color": ["#A1A7B3", "#A1A7B3"],
        "border_color": ["#323B4C", "#323B4C"],
        "corner_radius": 10,
        "border_width": 0
    },
    "CTkCheckBox": {
        "fg_color": ["#323B4C", "#323B4C"],
        "text_color": ["#FFFFFF", "#FFFFFF"],
        "text_color_disabled": ["#A1A7B3", "#A1A7B3"],
        "hover_color": ["#444B5A", "#444B5A"],
        "border_color": ["#323B4C", "#323B4C"],
        "border_width": 2,
        "corner_radius": 10,
        "checkmark_color": ["#22D3EE", "#22D3EE"]
    },
    "CTkScrollbar": {
        "fg_color": ["#232B3B", "#232B3B"],
        "button_color": ["#323B4C", "#323B4C"],
        "button_hover_color": ["#444B5A", "#444B5A"],
        "border_color": ["#232B3B", "#232B3B"],
        "border_width": 0,
        "corner_radius": 10,
        "border_spacing": 2
    },
    "CTkScrollableFrame": {
        "label_fg_color": ["#232B3B", "#232B3B"]
    },
    "CTkFont": {
        "family": "Arial",
        "size": 13,
        "weight": "normal"
    },
    "DropdownMenu": {
        "fg_color": ["#323B4C", "#323B4C"],
        "hover_color": ["#444B5A", "#444B5A"],
        "text_color": ["#FFFFFF", "#FFFFFF"],
        "border_color": ["#323B4C", "#323B4C"],
        "border_width": 0,
        "corner_radius": 10
    }
}

ctk.set_appearance_mode("Dark")
for widget_key, widget_values in THEME_CONFIG.items():
    if widget_key in ctk.ThemeManager.theme and isinstance(widget_values, dict):
        ctk.ThemeManager.theme[widget_key].update(widget_values)
    else:
        ctk.ThemeManager.theme[widget_key] = widget_values


class TimeTrackerLiteApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Work Time Tracker (Lite)")
        self.root.geometry("425x470")
        self.root.resizable(True, True)
        try:
            self.root.iconbitmap(resource_path("icone.ico"))
        except Exception:
            pass

        self.root.attributes('-toolwindow', True)
        self.always_on_top = True
        self.resizable = True
        self.close_to_tray = True

        # Real-time tracking state
        self.target_windows = []
        self.elapsed_time = 0
        self.running = False
        self.tracking_active = False
        self.idle_threshold = 10
        self.check_interval = 1.0
        self.timer_var = ctk.StringVar(value="00:00:00")
        self.app_times = {}

        # Events for responsive thread shutdown
        self.stop_tracking_event = threading.Event()
        self.tray_stop_event = threading.Event()

        # Cache tray font
        try:
            self.tray_font = ImageFont.truetype("arial.ttf", 24)
        except Exception:
            self.tray_font = ImageFont.load_default()

        # Settings and shortcuts file
        self.settings_file = resource_path("settings.json")
        self.native_hotkeys = NativeHotkeys(root=self.root)
        self.shortcuts = {
            "start": "ctrl+alt+e",
            "stop": "ctrl+alt+d",
            "reset": "ctrl+alt+r",
            "compact": "ctrl+alt+c"
        }
        self.start_shortcut_var = ctk.StringVar()
        self.stop_shortcut_var = ctk.StringVar()
        self.reset_shortcut_var = ctk.StringVar()
        self.compact_shortcut_var = ctk.StringVar()
        self.idle_threshold_var = ctk.StringVar(value=str(self.idle_threshold))
        self.check_interval_var = ctk.StringVar(value=str(self.check_interval))
        self.close_to_tray_var = ctk.BooleanVar(value=self.close_to_tray)
        self.auto_compact_mode_var = ctk.BooleanVar(value=True)

        self.load_settings()
        self.create_interface()
        self.register_shortcuts()

        # Tray & close configuration
        self.root.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)
        self.tray_icon_update_running = False

        # Custom title bar
        self.root.overrideredirect(True)
        self.title_bar = ctk.CTkFrame(self.root, fg_color="#181e29", height=32)
        self.title_bar.place(x=0, y=0, relwidth=1)

        try:
            icon_pil_image = Image.open(resource_path("icone.ico"))
            self.icon_ctk_image = ctk.CTkImage(light_image=icon_pil_image, dark_image=icon_pil_image, size=(25, 25))
            icon_label = ctk.CTkLabel(self.title_bar, image=self.icon_ctk_image, text="", fg_color="#181e29")
            icon_label.pack(side="left", padx=(8, 4), pady=4)
        except Exception:
            icon_label = ctk.CTkLabel(self.title_bar, text="", fg_color="#181e29")
            icon_label.pack(side="left", padx=(8, 4), pady=4)

        title_label = ctk.CTkLabel(
            self.title_bar, text="Work Time Tracker (Lite)",
            font=("Arial", 13, "bold"), text_color="#22D3EE", fg_color="#181e29"
        )
        title_label.pack(side="left", padx=(0, 10), pady=4)

        close_btn = ctk.CTkButton(
            self.title_bar, text="✕", width=32, height=24, fg_color="#EA697B", hover_color="#C53030",
            text_color="#FFFFFF", font=("Arial", 14, "bold"), corner_radius=8, command=self.handle_close
        )
        close_btn.pack(side="right", padx=8, pady=4)

        def start_move(event):
            self._drag_start_x = event.x
            self._drag_start_y = event.y

        def do_move(event):
            x = self.root.winfo_x() + event.x - self._drag_start_x
            y = self.root.winfo_y() + event.y - self._drag_start_y
            self.root.geometry(f"+{x}+{y}")

        for widget in (self.title_bar, title_label, icon_label):
            widget.bind("<Button-1>", start_move)
            widget.bind("<B1-Motion>", do_move)

    def is_user_active(self):
        """Checks if the user is active using Windows native API (no hooks or pyautogui)."""
        return get_idle_seconds() < self.idle_threshold

    def load_settings(self):
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    self.shortcuts.update(settings.get("shortcuts", {}))
                    self.always_on_top = settings.get("always_on_top", True)
                    self.resizable = settings.get("resizable", True)
                    self.idle_threshold = settings.get("idle_threshold", 10)
                    self.check_interval = settings.get("check_interval", 1.0)
                    self.close_to_tray = settings.get("close_to_tray", True)
                    self.auto_compact_mode_var.set(settings.get("auto_compact_mode", True))
        except Exception:
            pass

        self.start_shortcut_var.set(self.shortcuts.get("start", "ctrl+alt+e"))
        self.stop_shortcut_var.set(self.shortcuts.get("stop", "ctrl+alt+d"))
        self.reset_shortcut_var.set(self.shortcuts.get("reset", "ctrl+alt+r"))
        self.compact_shortcut_var.set(self.shortcuts.get("compact", "ctrl+alt+c"))
        self.idle_threshold_var.set(str(self.idle_threshold))
        self.check_interval_var.set(str(self.check_interval))
        self.close_to_tray_var.set(self.close_to_tray)
        self.root.attributes('-topmost', self.always_on_top)
        self.root.resizable(self.resizable, self.resizable)

    def create_interface(self):
        self.root.configure(bg="#181E29")

        # Main Page
        self.page_main = ctk.CTkFrame(self.root, fg_color="#232B3B", corner_radius=12)
        self.page_main.pack(fill="both", expand=True, pady=(32, 0))

        ctk.CTkLabel(
            self.page_main, text="Focus Mode",
            font=("Arial", 28, "bold"), text_color="#22D3EE", fg_color="#232B3B"
        ).pack(pady=(8, 0))

        ctk.CTkLabel(
            self.page_main, text="Select apps to track your focus time.",
            font=("Arial", 13), text_color="#A1A7B3", fg_color="#232B3B"
        ).pack(pady=(0, 6))

        # App selector section
        app_selector_wrapper = ctk.CTkFrame(self.page_main, fg_color="transparent", height=90)
        app_selector_wrapper.pack(fill="x", expand=False, padx=0, pady=0)
        app_selector_wrapper.pack_propagate(False)

        self.app_selector_container = ctk.CTkScrollableFrame(app_selector_wrapper, label_text="", fg_color="transparent")
        self.app_selector_container.pack(fill="both", expand=True)

        self.app_combos = []
        self.add_app_slot()

        add_app_button = ctk.CTkButton(self.page_main, text="+ Add App", command=self.add_app_slot, width=130)
        add_app_button.pack(pady=(4, 8))

        # Timer
        timer_frame = ctk.CTkFrame(self.page_main, fg_color="#323b4c", corner_radius=50)
        timer_frame.pack(pady=5)
        self.timer_label = ctk.CTkLabel(
            timer_frame, textvariable=self.timer_var,
            font=("Arial", 45, "bold"), text_color="#22D3EE", fg_color="#323b4c"
        )
        self.timer_label.pack(padx=24, pady=10)

        # Control buttons
        btn_frame1 = ctk.CTkFrame(self.page_main, fg_color="#232B3B")
        btn_frame1.pack(pady=(2, 0))
        btn_style1 = {"width": 130, "height": 40, "corner_radius": 12, "font": ("Arial", 15, "bold")}
        self.start_btn = ctk.CTkButton(btn_frame1, text="▶ Start", fg_color="#22D3EE", text_color="#FFFFFF", hover_color="#06B6D4", **btn_style1, command=self.start_tracking)
        self.start_btn.grid(row=0, column=0, padx=5, pady=4)
        self.stop_btn = ctk.CTkButton(btn_frame1, text="⏸ Pause", fg_color="#F472B6", text_color="#FFFFFF", hover_color="#EC4899", **btn_style1, command=self.pause_tracking)
        self.stop_btn.grid(row=0, column=1, padx=5, pady=4)

        btn_frame2 = ctk.CTkFrame(self.page_main, fg_color="#232B3B")
        btn_frame2.pack(pady=(2, 8))
        btn_style2 = {"width": 130, "height": 40, "corner_radius": 12, "font": ("Arial", 15, "bold")}
        self.reset_btn = ctk.CTkButton(btn_frame2, text="⟳ Reset", fg_color="#6B7280", text_color="#FFFFFF", hover_color="#374151", **btn_style2, command=self.reset_timer)
        self.reset_btn.grid(row=0, column=0, padx=5, pady=4)
        self.compact_btn = ctk.CTkButton(btn_frame2, text="💢 Compact", fg_color="#818CF8", text_color="#FFFFFF", hover_color="#323b4c", **btn_style2, command=self.toggle_compact_mode)
        self.compact_btn.grid(row=0, column=1, padx=5, pady=4)

        # Settings Page
        self.page_settings = ctk.CTkFrame(self.root, fg_color="#232B3B")

        settings_scroll = ctk.CTkScrollableFrame(self.page_settings, fg_color="transparent", label_text="")
        settings_scroll.pack(fill="both", expand=True, padx=10, pady=(32, 0))

        ctk.CTkLabel(settings_scroll, text="Settings", font=("Arial", 20, "bold"), text_color="#22D3EE").pack(pady=(10, 10))

        close_to_tray_check = ctk.CTkCheckBox(
            settings_scroll,
            text="Minimize to tray when closing (recommended)",
            variable=self.close_to_tray_var,
            fg_color="#323B4C", text_color="#A1A7B3"
        )
        close_to_tray_check.pack(pady=8, padx=20, anchor="w")

        auto_compact_check = ctk.CTkCheckBox(
            settings_scroll,
            text="Automatically enter compact mode when tracking starts",
            variable=self.auto_compact_mode_var,
            fg_color="#323B4C", text_color="#A1A7B3"
        )
        auto_compact_check.pack(pady=8, padx=20, anchor="w")

        always_on_top_var = ctk.BooleanVar(value=self.always_on_top)
        always_on_top_check = ctk.CTkCheckBox(
            settings_scroll,
            text="Always On Top",
            variable=always_on_top_var,
            command=lambda: self.toggle_always_on_top(always_on_top_var.get()),
            fg_color="#323B4C", text_color="#A1A7B3"
        )
        always_on_top_check.pack(pady=8, padx=20, anchor="w")

        resizable_var = ctk.BooleanVar(value=self.resizable)
        resizable_check = ctk.CTkCheckBox(
            settings_scroll,
            text="Allow Resizing",
            variable=resizable_var,
            command=lambda: self.toggle_resizable(resizable_var.get()),
            fg_color="#323B4C", text_color="#A1A7B3"
        )
        resizable_check.pack(pady=8, padx=20, anchor="w")

        idle_frame = ctk.CTkFrame(settings_scroll, fg_color="#232B3B")
        idle_frame.pack(pady=8, padx=20, fill="x")
        ctk.CTkLabel(idle_frame, text="Idle Threshold (seconds):", text_color="#A1A7B3").pack(side="left", padx=5)
        ctk.CTkEntry(idle_frame, textvariable=self.idle_threshold_var, width=100, fg_color="#323B4C", text_color="#FFFFFF").pack(side="left", padx=5)

        interval_frame = ctk.CTkFrame(settings_scroll, fg_color="#232B3B")
        interval_frame.pack(pady=8, padx=20, fill="x")
        ctk.CTkLabel(interval_frame, text="Check Interval (seconds):", text_color="#A1A7B3").pack(side="left", padx=5)
        ctk.CTkEntry(interval_frame, textvariable=self.check_interval_var, width=100, fg_color="#323B4C", text_color="#FFFFFF").pack(side="left", padx=5)

        shortcuts_frame = ctk.CTkFrame(settings_scroll, fg_color="#232B3B")
        shortcuts_frame.pack(pady=8, padx=20, fill="x")
        ctk.CTkLabel(shortcuts_frame, text="Customize Keyboard Shortcuts", font=("Arial", 14, "bold"), text_color="#22D3EE").grid(row=0, column=0, columnspan=2, pady=(5, 8))
        shortcut_labels = ["Start / Resume", "Pause Timer", "Reset Timer", "Toggle Compact"]
        shortcut_vars = [self.start_shortcut_var, self.stop_shortcut_var, self.reset_shortcut_var, self.compact_shortcut_var]
        for i, label_text in enumerate(shortcut_labels):
            ctk.CTkLabel(shortcuts_frame, text=f"{label_text}:", text_color="#A1A7B3").grid(row=i+1, column=0, padx=10, pady=4, sticky="w")
            entry = ctk.CTkEntry(shortcuts_frame, textvariable=shortcut_vars[i], fg_color="#323B4C", text_color="#FFFFFF")
            entry.grid(row=i+1, column=1, padx=10, pady=4, sticky="ew")
        shortcuts_frame.grid_columnconfigure(1, weight=1)

        settings_btn_frame = ctk.CTkFrame(settings_scroll, fg_color="#232B3B")
        settings_btn_frame.pack(pady=15, padx=20, fill="x")
        ctk.CTkButton(settings_btn_frame, text="Save Settings", fg_color="#22D3EE", text_color="#181E29", hover_color="#06B6D4", command=self.save_settings).pack(side="right", padx=5)
        ctk.CTkButton(settings_btn_frame, text="Back", fg_color="#6B7280", text_color="#FFFFFF", hover_color="#374151", command=self.show_main_page).pack(side="right", padx=5)

        # Simple Settings bottom button
        self.nav_frame = ctk.CTkFrame(self.root, fg_color="#181e29")
        self.nav_frame.pack(side="bottom", fill="x", padx=20, pady=12)
        ctk.CTkButton(
            self.nav_frame, text="⚙️ Settings", font=("Arial", 11, "bold"), fg_color="#181e29",
            hover_color="#34495E", text_color="#22D3EE", command=self.show_settings_page
        ).pack(fill="x", expand=True)

    def get_window_titles(self):
        return ["Choose App"] + [title for title in gw.getAllTitles() if title.strip()]

    def add_app_slot(self):
        slot_frame = ctk.CTkFrame(self.app_selector_container, fg_color="transparent")
        combo = ctk.CTkComboBox(slot_frame, values=self.get_window_titles())
        combo.pack(side="left", fill="x", expand=True, padx=(0, 5))
        combo.set("Choose App")
        self.app_combos.append(combo)

        remove_btn = ctk.CTkButton(
            slot_frame,
            text="-",
            width=28,
            height=28,
            fg_color="#6B7280",
            hover_color="#C53030",
            command=lambda f=slot_frame, c=combo: self.remove_app_slot(f, c)
        )
        remove_btn.pack(side="left")
        slot_frame.pack(fill="x", expand=True, pady=2, padx=5)

    def remove_app_slot(self, slot_frame, combo_to_remove):
        if len(self.app_combos) > 1:
            self.app_combos.remove(combo_to_remove)
            slot_frame.destroy()
        else:
            messagebox.showwarning("Warning", "Keep at least one application slot.")

    def start_tracking(self):
        self.target_windows = [
            combo.get() for combo in self.app_combos
            if combo.get() and combo.get() != "Choose App" and combo.get() != "Escolha o App"
        ]
        if not self.target_windows:
            messagebox.showwarning("Warning", "Please select at least one application!")
            return
        if not self.running:
            self.running = True
            self.stop_tracking_event.clear()
            self.tracking_active = False
            self.start_btn.configure(fg_color="#27AE60", text="▶ Tracking")
            self.update_timer_color()
            # Preserve accumulated time on resume
            for app in self.target_windows:
                if app not in self.app_times:
                    self.app_times[app] = 0.0
            threading.Thread(target=self.track_time, daemon=True).start()

    def pause_tracking(self):
        if self.running:
            self.running = False
            self.tracking_active = False
            self.stop_tracking_event.set()
            self.start_btn.configure(fg_color="#22D3EE", text="▶ Resume" if self.elapsed_time > 0 else "▶ Start")
            self.update_timer_color()
            # Keeps elapsed_time intact (pause without resetting)
            self.update_timer_display()

    # Alias for compatibility
    stop_tracking = pause_tracking

    def reset_timer(self):
        if messagebox.askyesno("Confirm", "Reset timer?"):
            self.elapsed_time = 0
            self.app_times = {app: 0.0 for app in self.target_windows}
            self.update_timer_display()
            self.tracking_active = False
            self.start_btn.configure(fg_color="#22D3EE", text="▶ Start")
            self.update_timer_color()

    def track_time(self):
        while self.running and not self.stop_tracking_event.is_set():
            current_window = self.get_active_window()
            user_active = self.is_user_active()
            app_found = None
            if current_window:
                for app in self.target_windows:
                    if app in current_window:
                        app_found = app
                        break
            if user_active and app_found:
                if not self.tracking_active:
                    self.tracking_active = True
                    self.root.after(0, self.update_timer_color)
                    if self.auto_compact_mode_var.get() and (not hasattr(self, '_compact_mode') or not self._compact_mode):
                        self.root.after(0, self.toggle_compact_mode)
                self.app_times[app_found] += (self.check_interval / 60.0)
                self.elapsed_time = sum(self.app_times.values())
                self.root.after(0, self.update_timer_display)
            else:
                if self.tracking_active:
                    self.tracking_active = False
                    self.root.after(0, self.update_timer_color)
            if self.stop_tracking_event.wait(self.check_interval):
                break

    def get_active_window(self):
        try:
            window = gw.getActiveWindow()
            return window and window.title
        except Exception:
            return None

    def update_timer_display(self):
        hours, remainder = divmod(int(self.elapsed_time * 60), 3600)
        minutes, seconds = divmod(remainder, 60)
        timer_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        self.timer_var.set(timer_str)
        self.update_timer_color()

    def show_settings_page(self):
        self.page_main.pack_forget()
        self.page_settings.pack(fill="both", expand=True)

    def show_main_page(self):
        self.page_settings.pack_forget()
        self.page_main.pack(fill="both", expand=True, pady=(32, 0))

    def toggle_always_on_top(self, state):
        self.always_on_top = state
        self.root.attributes('-topmost', state)

    def toggle_resizable(self, state):
        self.resizable = state
        self.root.resizable(state, state)
        if state:
            self.root.overrideredirect(False)
            if hasattr(self, 'title_bar'):
                self.title_bar.place_forget()
        else:
            self.root.overrideredirect(True)
            if hasattr(self, 'title_bar'):
                self.root.geometry("425x470")
                self.title_bar.place(x=0, y=0, relwidth=1)

    def validate_shortcut(self, shortcut):
        if not shortcut:
            return False
        try:
            parts = shortcut.lower().split('+')
            valid_keys = set('abcdefghijklmnopqrstuvwxyz0123456789')
            valid_modifiers = {'ctrl', 'alt', 'shift'}
            for part in parts:
                if part in valid_modifiers:
                    continue
                if len(part) == 1 and part in valid_keys:
                    continue
                return False
            return True
        except Exception:
            return False

    def save_settings(self):
        new_shortcuts = {
            "start": self.start_shortcut_var.get().strip(),
            "stop": self.stop_shortcut_var.get().strip(),
            "reset": self.reset_shortcut_var.get().strip(),
            "compact": self.compact_shortcut_var.get().strip()
        }
        for key, shortcut in new_shortcuts.items():
            if shortcut and not self.validate_shortcut(shortcut):
                messagebox.showerror("Invalid Shortcut", f"Invalid format for '{key}' shortcut. Use format like 'ctrl+alt+e'.")
                return

        try:
            idle_threshold = float(self.idle_threshold_var.get())
            if idle_threshold <= 0:
                raise ValueError()
            self.idle_threshold = idle_threshold
        except (ValueError, TypeError):
            messagebox.showerror("Invalid Idle Threshold", "Please enter a valid positive number for idle threshold.")
            return

        try:
            check_interval = float(self.check_interval_var.get())
            if check_interval <= 0:
                raise ValueError()
            self.check_interval = check_interval
        except (ValueError, TypeError):
            messagebox.showerror("Invalid Check Interval", "Please enter a valid positive number for check interval.")
            return

        if hasattr(self, "native_hotkeys"):
            self.native_hotkeys.stop()

        self.shortcuts = new_shortcuts
        self.register_shortcuts()

        settings_dict = {
            "shortcuts": self.shortcuts,
            "always_on_top": self.always_on_top,
            "resizable": self.resizable,
            "idle_threshold": self.idle_threshold,
            "check_interval": self.check_interval,
            "close_to_tray": self.close_to_tray_var.get(),
            "auto_compact_mode": self.auto_compact_mode_var.get()
        }
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings_dict, f, indent=4)
            messagebox.showinfo("Settings Saved", "Your settings have been saved and applied.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")

    def register_shortcuts(self):
        try:
            if hasattr(self, 'native_hotkeys'):
                self.native_hotkeys.stop()
                for key, shortcut in self.shortcuts.items():
                    if shortcut:
                        if key == "start":
                            self.native_hotkeys.register(shortcut, self.start_tracking)
                        elif key == "stop":
                            self.native_hotkeys.register(shortcut, self.stop_tracking)
                        elif key == "reset":
                            self.native_hotkeys.register(shortcut, self.reset_timer)
                        elif key == "compact":
                            self.native_hotkeys.register(shortcut, self.toggle_compact_mode)
                self.native_hotkeys.start()
        except Exception as e:
            print(f"Erro ao registrar atalhos nativos: {e}")
    def toggle_compact_mode(self):
        if not hasattr(self, '_compact_mode'):
            self._compact_mode = False
        self._compact_mode = not self._compact_mode
        if self._compact_mode:
            self.root.geometry("185x40")
            self.page_main.pack_forget()
            if not hasattr(self, 'compact_frame'):
                self.compact_frame = ctk.CTkFrame(self.root)
                self.compact_inner = ctk.CTkFrame(self.compact_frame, fg_color="transparent")
                self.compact_inner.pack(expand=True)
                self.compact_timer_label = ctk.CTkLabel(
                    self.compact_inner, textvariable=self.timer_var,
                    font=("Arial", 28, "bold"), text_color="#EA697B"
                )
                self.compact_timer_label.pack(side="left", padx=(5, 2))
                self.compact_btn_compact = ctk.CTkButton(
                    self.compact_inner, text="💢", width=28, height=28,
                    font=("Arial", 16), command=self.toggle_compact_mode,
                    fg_color="#323b4c", hover_color="#818CF8", text_color="#FFFFFF"
                )
                self.compact_btn_compact.pack(side="left", padx=(2, 5))

                def start_move(event):
                    self._drag_start_x = event.x
                    self._drag_start_y = event.y

                def do_move(event):
                    x = self.root.winfo_x() + event.x - self._drag_start_x
                    y = self.root.winfo_y() + event.y - self._drag_start_y
                    self.root.geometry(f"+{x}+{y}")

                for w in (self.compact_frame, self.compact_inner, self.compact_timer_label, self.compact_btn_compact):
                    w.bind("<Button-1>", start_move)
                    w.bind("<B1-Motion>", do_move)

            self.compact_frame.pack(fill="both", expand=True)
            self.update_timer_color()
            self.nav_frame.pack_forget()
        else:
            if hasattr(self, 'compact_frame'):
                self.compact_frame.pack_forget()
            self.page_main.pack(fill="both", expand=True, pady=(32, 0))
            self.root.geometry("425x470")
            self.nav_frame.pack(side="bottom", fill="x", padx=20, pady=12)
            self.update_timer_color()

    def update_timer_color(self):
        is_active = self.running and getattr(self, 'tracking_active', False)
        color = "#1ABC9C" if is_active else "#EA697B"
        if hasattr(self, 'timer_label'):
            self.timer_label.configure(text_color=color)
        if hasattr(self, 'compact_timer_label'):
            self.compact_timer_label.configure(text_color=color)

    def setup_tray_thread(self):
        if not hasattr(self, 'tray_thread') or not self.tray_thread.is_alive():
            self.tray_thread = threading.Thread(target=self.setup_tray, daemon=True)
            self.tray_thread.start()

    def setup_tray(self):
        initial_image = self._generate_timer_icon_image()
        menu = (
            pystray.MenuItem("Show", self.restore_from_tray, default=True),
            pystray.MenuItem("Exit", self.on_close)
        )
        self.tray_icon = pystray.Icon("TimeTrackerLite", initial_image, "TimeTracker (Lite)", menu)
        self.tray_icon_update_running = True
        self.tray_stop_event.clear()
        threading.Thread(target=self._update_tray_icon_periodically, daemon=True).start()
        self.tray_icon.run()

    def _update_tray_icon_periodically(self):
        while self.tray_icon_update_running and not self.tray_stop_event.is_set():
            if hasattr(self, 'tray_icon') and self.tray_icon.visible:
                new_image = self._generate_timer_icon_image()
                full_timer_str = self.timer_var.get()
                tooltip_text = f"TimeTracker (Lite)\n{full_timer_str}"
                try:
                    self.tray_icon.icon = new_image
                    self.tray_icon.title = tooltip_text
                except Exception:
                    pass
            if self.tray_stop_event.wait(1.0):
                break

    def restore_from_tray(self, icon=None, item=None):
        self.tray_icon_update_running = False
        self.tray_stop_event.set()
        if hasattr(self, 'tray_icon'):
            self.tray_icon.stop()
        self.root.after(0, self.root.deiconify)
        self.root.after(100, lambda: self.root.attributes('-topmost', self.always_on_top))

    def minimize_to_tray(self):
        self.root.withdraw()
        self.setup_tray_thread()

    def on_close(self, icon=None, item=None):
        self.tray_icon_update_running = False
        self.tray_stop_event.set()
        self.stop_tracking_event.set()
        if hasattr(self, 'tray_icon'):
            self.tray_icon.stop()
        if hasattr(self, "native_hotkeys"):
            self.native_hotkeys.stop()
        self.running = False
        self.root.quit()

    def handle_close(self):
        if self.close_to_tray_var.get():
            self.minimize_to_tray()
        else:
            self.on_close()

    def _generate_timer_icon_image(self):
        timer_str = self.timer_var.get()
        is_active = self.running and getattr(self, 'tracking_active', False)
        parts = timer_str.split(':')
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = int(parts[2])
        if hours > 0:
            display_text = f"{hours:02d}:{minutes:02d}"
        else:
            display_text = f"{minutes:02d}:{seconds:02d}"
        img_size = (64, 64)
        text_color = '#1ABC9C' if is_active else '#EA697B'
        image = Image.new('RGBA', img_size, (0, 0, 0, 0))
        d = ImageDraw.Draw(image)
        # Reuse cached font to avoid reading disk every second
        font = getattr(self, 'tray_font', None) or ImageFont.load_default()
        left, top, right, bottom = d.textbbox((0, 0), display_text, font=font)
        x_draw = (img_size[0] - (right - left)) / 2
        y_draw = (img_size[1] - (bottom - top)) / 2
        d.text((x_draw, y_draw), display_text, fill=text_color, font=font)
        return image


if __name__ == "__main__":
    root = ctk.CTk()
    app = TimeTrackerLiteApp(root)
    root.mainloop()

