import customtkinter as ctk
from tkinter import messagebox
import tkinter as tk
import time
import threading
import csv
import os
import json
import ctypes
from datetime import datetime, timedelta
import pygetwindow as gw
import pystray
from PIL import Image, ImageDraw, ImageFont
import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import sys
import re
import warnings

# Suprime avisos do Matplotlib sobre glifos/emojis ausentes
warnings.filterwarnings('ignore', category=UserWarning, module='matplotlib')
warnings.filterwarnings('ignore', message='.*missing from font.*')

# === Estrutura Nativa do Windows para Detecção de Inatividade ===
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
    """Retorna o tempo de inatividade do usuário em segundos usando a API nativa do Windows (GetLastInputInfo)."""
    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
        millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
        return max(0.0, millis / 1000.0)
    return 0.0

def resource_path(relative_path):
    """Retorna o caminho absoluto para recursos, compatível com PyInstaller e execução direta."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, relative_path)

# === Configuração de Tema Integrado (sem arquivos externos) ===
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


class TimeTrackerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Rastreador de Tempo de Trabalho")
        self.root.geometry("425x500")
        self.root.resizable(True, True)
        try:
            self.root.iconbitmap(resource_path("icone.ico"))
        except Exception as e:
            print(f"Não foi possível carregar o ícone: {e}")

        self.root.attributes('-toolwindow', True)
        self.always_on_top = True
        self.resizable = True
        self.close_to_tray = True

        # Variáveis de controle
        self.target_windows = []
        self.elapsed_time = 0
        self.running = False
        self.tracking_active = False
        self.last_active_window = None
        self.idle_threshold = 10
        self.check_interval = 1.0
        self.timer_var = ctk.StringVar(value="00:00:00")
        self.show_full_history = False
        self.app_times = {}

        # Eventos para encerramento responsivo de threads
        self.stop_tracking_event = threading.Event()
        self.tray_stop_event = threading.Event()

        # Cache de fonte para ícone da bandeja
        try:
            self.tray_font = ImageFont.truetype("arial.ttf", 24)
        except Exception:
            self.tray_font = ImageFont.load_default()

        # Arquivo de configurações e atalhos
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

        # Arquivo CSV
        self.filename = resource_path("time_history.csv")
        self.initialize_csv()

        self.load_settings()
        self.create_interface()
        self.load_history()
        self.register_shortcuts()

        # Configurar fechamento e bandeja
        self.root.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)
        self.tray_icon_update_running = False

        # Barra de título customizada
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
            self.title_bar, text="Rastreador de Tempo de Trabalho",
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
        """Verifica se o usuário está ativo usando a API nativa do Windows (sem hooks de teclado ou pyautogui)."""
        return get_idle_seconds() < self.idle_threshold

    def initialize_csv(self):
        csv_path = getattr(self, 'filename', 'time_history.csv')
        expected_header = ["DATE", "TIME", "APP", "DURATION"]
        if not os.path.exists(csv_path):
            with open(csv_path, mode="w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(expected_header)
        else:
            try:
                with open(csv_path, mode="r", encoding="utf-8", errors="replace") as file:
                    lines = file.readlines()
                if lines:
                    header = [h.strip() for h in lines[0].strip().split(",")]
                    if "DURATION" not in header:
                        lines[0] = ",".join(expected_header) + "\n"
                        with open(csv_path, mode="w", newline="", encoding="utf-8") as file:
                            file.writelines(lines)
            except Exception as e:
                print(f"Error checking/repairing CSV header: {e}")

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
        except (json.JSONDecodeError, FileNotFoundError):
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
        self.page_main = ctk.CTkFrame(self.root, fg_color="#232B3B", corner_radius=12)
        self.page_main.pack(fill="both", expand=True, pady=(32, 0))

        # Título
        ctk.CTkLabel(
            self.page_main, text="Modo Foco",
            font=("Arial", 28, "bold"), text_color="#22D3EE", fg_color="#232B3B"
        ).pack(pady=(5, 0))

        ctk.CTkLabel(
            self.page_main, text="Selecione até 3 aplicativos para monitorar seu tempo.",
            font=("Arial", 14), text_color="#A1A7B3", fg_color="#232B3B"
        ).pack(pady=(0, 5))

        # Seção de seleção de apps
        app_selector_wrapper = ctk.CTkFrame(self.page_main, fg_color="transparent", height=90)
        app_selector_wrapper.pack(fill="x", expand=False, padx=0, pady=0)
        app_selector_wrapper.pack_propagate(False)

        self.app_selector_container = ctk.CTkScrollableFrame(app_selector_wrapper, label_text="", fg_color="transparent")
        self.app_selector_container.pack(fill="both", expand=True)

        self.app_combos = []
        self.add_app_slot()

        add_app_button = ctk.CTkButton(self.page_main, text="+ Adicionar App", command=self.add_app_slot, width=130)
        add_app_button.pack(pady=(5, 10))

        # Timer
        timer_frame = ctk.CTkFrame(self.page_main, fg_color="#323b4c", corner_radius=50)
        timer_frame.pack(pady=5)
        self.timer_label = ctk.CTkLabel(
            timer_frame, textvariable=self.timer_var,
            font=("Arial", 45, "bold"), text_color="#22D3EE", fg_color="#323b4c"
        )
        self.timer_label.pack(padx=20, pady=10)

        # Botões principais
        btn_frame1 = ctk.CTkFrame(self.page_main, fg_color="#232B3B")
        btn_frame1.pack(pady=(1, 0))
        btn_style1 = {"width": 130, "height": 40, "corner_radius": 12, "font": ("Arial", 15, "bold")}
        self.start_btn = ctk.CTkButton(btn_frame1, text="▶ Iniciar", fg_color="#22D3EE", text_color="#FFFFFF", hover_color="#06B6D4", **btn_style1, command=self.start_tracking)
        self.start_btn.grid(row=0, column=0, padx=5, pady=5)
        self.stop_btn = ctk.CTkButton(btn_frame1, text="■ Parar", fg_color="#F472B6", text_color="#FFFFFF", hover_color="#EC4899", **btn_style1, command=self.stop_tracking)
        self.stop_btn.grid(row=0, column=1, padx=5, pady=5)

        btn_frame2 = ctk.CTkFrame(self.page_main, fg_color="#232B3B")
        btn_frame2.pack(pady=(1, 5))
        btn_style2 = {"width": 130, "height": 40, "corner_radius": 12, "font": ("Arial", 15, "bold")}
        self.reset_btn = ctk.CTkButton(btn_frame2, text="⟳ Resetar", fg_color="#6B7280", text_color="#FFFFFF", hover_color="#374151", **btn_style2, command=self.reset_timer)
        self.reset_btn.grid(row=0, column=0, padx=5, pady=5)
        self.compact_btn = ctk.CTkButton(btn_frame2, text="💢 Compacto", fg_color="#818CF8", text_color="#FFFFFF", hover_color="#323b4c", **btn_style2, command=self.toggle_compact_mode)
        self.compact_btn.grid(row=0, column=1, padx=5, pady=5)

        # Página de Configurações
        self.page_history = ctk.CTkFrame(self.root, fg_color="#232B3B")
        self.page_settings = ctk.CTkFrame(self.root, fg_color="#232B3B")

        settings_scroll_frame = ctk.CTkScrollableFrame(self.page_settings, fg_color="transparent", label_text="")
        settings_scroll_frame.pack(fill="both", expand=True, padx=10, pady=(32, 0))

        ctk.CTkLabel(settings_scroll_frame, text="Configurações", font=("Arial", 20, "bold"), text_color="#22D3EE").pack(pady=(10, 10))

        close_to_tray_check = ctk.CTkCheckBox(
            settings_scroll_frame,
            text="Minimizar para bandeja ao fechar (recomendado)",
            variable=self.close_to_tray_var,
            fg_color="#323B4C",
            text_color="#A1A7B3"
        )
        close_to_tray_check.pack(pady=10, padx=20, anchor="w")

        auto_compact_check = ctk.CTkCheckBox(
            settings_scroll_frame,
            text="Entrar em modo compacto automaticamente ao iniciar monitoramento",
            variable=self.auto_compact_mode_var,
            fg_color="#323B4C",
            text_color="#A1A7B3"
        )
        auto_compact_check.pack(pady=10, padx=20, anchor="w")

        always_on_top_var = ctk.BooleanVar(value=self.always_on_top)
        always_on_top_check = ctk.CTkCheckBox(
            settings_scroll_frame,
            text="Sempre no Topo",
            variable=always_on_top_var,
            command=lambda: self.toggle_always_on_top(always_on_top_var.get()),
            fg_color="#323B4C", text_color="#A1A7B3"
        )
        always_on_top_check.pack(pady=10, padx=20, anchor="w")

        resizable_var = ctk.BooleanVar(value=self.resizable)
        resizable_check = ctk.CTkCheckBox(
            settings_scroll_frame,
            text="Permitir Redimensionamento",
            variable=resizable_var,
            command=lambda: self.toggle_resizable(resizable_var.get()),
            fg_color="#323B4C", text_color="#A1A7B3"
        )
        resizable_check.pack(pady=10, padx=20, anchor="w")

        idle_frame = ctk.CTkFrame(settings_scroll_frame, fg_color="#232B3B")
        idle_frame.pack(pady=10, padx=20, fill="x")
        ctk.CTkLabel(idle_frame, text="Tempo de Inatividade (segundos):", text_color="#A1A7B3").pack(side="left", padx=5)
        ctk.CTkEntry(idle_frame, textvariable=self.idle_threshold_var, width=100, fg_color="#323B4C", text_color="#FFFFFF").pack(side="left", padx=5)

        interval_frame = ctk.CTkFrame(settings_scroll_frame, fg_color="#232B3B")
        interval_frame.pack(pady=10, padx=20, fill="x")
        ctk.CTkLabel(interval_frame, text="Intervalo de Verificação (segundos):", text_color="#A1A7B3").pack(side="left", padx=5)
        ctk.CTkEntry(interval_frame, textvariable=self.check_interval_var, width=100, fg_color="#323B4C", text_color="#FFFFFF").pack(side="left", padx=5)

        shortcuts_frame = ctk.CTkFrame(settings_scroll_frame, fg_color="#232B3B")
        shortcuts_frame.pack(pady=10, padx=20, fill="x")
        ctk.CTkLabel(shortcuts_frame, text="Personalizar Atalhos de Teclado", font=("Arial", 14, "bold"), text_color="#22D3EE").grid(row=0, column=0, columnspan=2, pady=(5, 10))
        shortcut_labels = ["Iniciar Temporizador", "Parar Temporizador", "Resetar Temporizador", "Alternar Compacto"]
        shortcut_vars = [self.start_shortcut_var, self.stop_shortcut_var, self.reset_shortcut_var, self.compact_shortcut_var]
        for i, label_text in enumerate(shortcut_labels):
            ctk.CTkLabel(shortcuts_frame, text=f"{label_text}:", text_color="#A1A7B3").grid(row=i+1, column=0, padx=10, pady=5, sticky="w")
            entry = ctk.CTkEntry(shortcuts_frame, textvariable=shortcut_vars[i], fg_color="#323B4C", text_color="#FFFFFF")
            entry.grid(row=i+1, column=1, padx=10, pady=5, sticky="ew")
        shortcuts_frame.grid_columnconfigure(1, weight=1)

        settings_btn_frame = ctk.CTkFrame(settings_scroll_frame, fg_color="#232B3B")
        settings_btn_frame.pack(pady=20, padx=20, fill="x")
        ctk.CTkButton(settings_btn_frame, text="Salvar Configurações", fg_color="#22D3EE", text_color="#181E29", hover_color="#06B6D4", command=self.save_settings).pack(side="right", padx=5)
        ctk.CTkButton(settings_btn_frame, text="Voltar", fg_color="#6B7280", text_color="#FFFFFF", hover_color="#374151", command=self.show_main_page).pack(side="right", padx=5)

        tips_frame = ctk.CTkFrame(settings_scroll_frame, fg_color="#232B3B")
        tips_frame.pack(pady=(0, 10), padx=20, fill="x")
        ctk.CTkLabel(tips_frame, text="Dicas:", font=("Arial", 13, "bold"), text_color="#22D3EE").pack(anchor="w", pady=(0, 2))
        ctk.CTkLabel(tips_frame, text="Dica 1: Selecione todos os programas que deseja monitorar antes de iniciar o cronômetro. Não é possível alterar a seleção depois de iniciar.", font=("Arial", 11), text_color="#A1A7B3", wraplength=380, justify="left").pack(anchor="w", pady=(0, 2))
        ctk.CTkLabel(tips_frame, text="Dica 2: Você pode apagar o nome da janela no campo para que o programa rastreie o aplicativo inteiro, e não apenas a janela selecionada.", font=("Arial", 11), text_color="#A1A7B3", wraplength=380, justify="left").pack(anchor="w")

        self.create_history_section(self.page_history)
        self.page_stats = ctk.CTkFrame(self.root, fg_color="#232B3B")

        # Barra de navegação inferior
        self.nav_frame = ctk.CTkFrame(self.root, fg_color="#181e29")
        self.nav_frame.pack(side="bottom", fill="x", padx=20, pady=20)
        nav_btn_width = 120
        ctk.CTkButton(self.nav_frame, text="🕐 Histórico", font=("Arial", 10), fg_color="#181e29",
                     hover_color="#34495E", border_width=0, border_color="#7F8C8D",
                     text_color="#7F8C8D", command=self.show_history, width=nav_btn_width).pack(side="left", expand=True, padx=5)
        ctk.CTkButton(self.nav_frame, text="📊 Estatísticas", font=("Arial", 10), fg_color="#181e29",
                     hover_color="#34495E", border_width=0, border_color="#7F8C8D",
                     text_color="#7F8C8D", command=self.show_stats, width=nav_btn_width).pack(side="left", expand=True, padx=5)
        ctk.CTkButton(self.nav_frame, text="⚙️ Configurações", font=("Arial", 10), fg_color="#181e29",
                     hover_color="#34495E", border_width=0, border_color="#7F8C8D",
                     text_color="#7F8C8D", command=self.show_settings_page, width=nav_btn_width).pack(side="left", expand=True, padx=5)

    def create_history_section(self, parent_frame):
        history_frame = ctk.CTkFrame(parent_frame, corner_radius=10, fg_color="#232B3B")
        history_frame.pack(fill="both", expand=True, padx=10, pady=(32, 10))

        top_frame = ctk.CTkFrame(history_frame, fg_color="#232b3b")
        top_frame.pack(fill="x", padx=5, pady=(10, 0))

        self.usage_report_frame = ctk.CTkFrame(top_frame, fg_color="#232b3b")
        self.usage_report_frame.pack(side="left", fill="x", expand=True)
        self.usage_report_labels = []
        for _ in range(3):
            frame = ctk.CTkFrame(self.usage_report_frame, fg_color="#232b3b")
            frame.pack(fill="x", anchor="w")
            text_lbl = ctk.CTkLabel(frame, text="", font=("Arial", 10), text_color="#6b7280", anchor="w")
            text_lbl.pack(side="left")
            time_lbl = ctk.CTkLabel(frame, text="", font=("Arial", 10, "bold"), text_color="#22D3EE", anchor="w")
            time_lbl.pack(side="left", padx=(5, 0))
            self.usage_report_labels.append((text_lbl, time_lbl))

        filter_frame = ctk.CTkFrame(top_frame, fg_color="#232b3b")
        filter_frame.pack(side="right", padx=(10, 0), pady=0)
        self.show_full_var = ctk.BooleanVar(value=self.show_full_history)
        ctk.CTkCheckBox(filter_frame, text="Histórico Completo", variable=self.show_full_var,
                        command=self.toggle_history_display).pack(anchor="w", pady=2)

        date_row = ctk.CTkFrame(filter_frame, fg_color="#232b3b")
        date_row.pack(anchor="w", pady=2)
        ctk.CTkLabel(date_row, text="Data:").pack(side="left", padx=(0, 2))
        self.date_filter_var = ctk.StringVar()
        self.date_filter_entry = ctk.CTkEntry(date_row, width=100, textvariable=self.date_filter_var)
        self.date_filter_entry.pack(side="left", padx=(0, 2))
        ctk.CTkButton(date_row, text="Aplicar", command=self.apply_date_filter, width=60).pack(side="left", padx=(0, 0))

        app_row = ctk.CTkFrame(filter_frame, fg_color="#232b3b")
        app_row.pack(anchor="w", pady=2)
        ctk.CTkLabel(app_row, text="App: ").pack(side="left", padx=(0, 2))
        self.app_filter_var = ctk.StringVar()
        self.app_filter_entry = ctk.CTkEntry(app_row, width=100, textvariable=self.app_filter_var)
        self.app_filter_entry.pack(side="left", padx=(0, 2))
        ctk.CTkButton(app_row, text="Buscar", command=self.apply_app_filter, width=60).pack(side="left", padx=(0, 0))

        title_bar_frame = ctk.CTkFrame(history_frame, fg_color="transparent")
        title_bar_frame.pack(fill="x", pady=(0, 0), padx=5)
        back_button = ctk.CTkButton(
            title_bar_frame,
            text="‹ Voltar",
            width=80,
            command=self.show_main_page,
            fg_color="#6B7280",
            hover_color="#374151"
        )
        back_button.pack(side="left", padx=0, pady=0)

        container = ctk.CTkFrame(history_frame, fg_color="#232B3B")
        container.pack(fill="both", expand=True, padx=0, pady=0)

        headers_frame = ctk.CTkFrame(container, fg_color="#232b3b")
        headers_frame.pack(fill="x", padx=0, pady=(0, 0))

        headers = ["DATA", "HORA", "APPS", "DURAÇÃO"]
        for header in headers:
            ctk.CTkLabel(headers_frame, text=header, font=("Arial", 11, "bold"),
                        text_color="white").pack(side="left", expand=True, padx=2)

        self.history_canvas = ctk.CTkCanvas(container, highlightthickness=0, bg="#232B3B")
        scrollbar = ctk.CTkScrollbar(container, orientation="vertical", command=self.history_canvas.yview)
        self.history_content = ctk.CTkFrame(self.history_canvas, fg_color="#232B3B")

        self.history_content.bind(
            "<Configure>",
            lambda e: self.history_canvas.configure(scrollregion=self.history_canvas.bbox("all")))

        self.history_canvas.create_window((0, 0), window=self.history_content, anchor="nw", width=380)
        self.history_canvas.configure(yscrollcommand=scrollbar.set)
        self.history_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def add_history_entry(self, date, time_val, apps, duration):
        entry_frame = ctk.CTkFrame(self.history_content, corner_radius=5, height=30, fg_color="#232b3b")
        entry_frame.pack(fill="x", pady=1, padx=1, expand=True)

        date_label = ctk.CTkLabel(entry_frame, text=date, font=("Arial", 9), anchor="w", text_color="white")
        date_label.pack(side="left", expand=True, padx=2)

        time_label = ctk.CTkLabel(entry_frame, text=time_val, font=("Arial", 9), anchor="w", text_color="white")
        time_label.pack(side="left", expand=True, padx=2)

        apps_label = ctk.CTkLabel(entry_frame, text=apps, font=("Arial", 9), anchor="w", text_color="white")
        apps_label.pack(side="left", expand=True, padx=2)

        def show_full_text(e):
            apps_label.configure(text=apps)
        def show_short_text(e):
            apps_label.configure(text=(apps[:15] + "...") if len(apps) > 15 else apps)

        apps_label.bind("<Enter>", show_full_text)
        apps_label.bind("<Leave>", show_short_text)
        show_short_text(None)

        duration_label = ctk.CTkLabel(entry_frame, text=duration, font=("Arial", 9), anchor="e", text_color="white")
        duration_label.pack(side="left", expand=True, padx=2)

    def get_window_titles(self):
        return ["Escolha o App"] + [title for title in gw.getAllTitles() if title.strip()]

    def add_app_slot(self):
        slot_frame = ctk.CTkFrame(self.app_selector_container, fg_color="transparent")
        combo = ctk.CTkComboBox(slot_frame, values=self.get_window_titles())
        combo.pack(side="left", fill="x", expand=True, padx=(0, 5))
        combo.set("Escolha o App")
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
            messagebox.showwarning("Aviso", "Mantenha pelo menos um campo de aplicativo.")

    def start_tracking(self):
        self.target_windows = [
            combo.get() for combo in self.app_combos
            if combo.get() and combo.get() != "Escolha o App" and combo.get() != "Choose App"
        ]
        if not self.target_windows:
            messagebox.showwarning("Aviso", "Selecione pelo menos um aplicativo!")
            return
        if not self.running:
            self.running = True
            self.stop_tracking_event.clear()
            self.tracking_active = False
            self.start_btn.configure(fg_color="#27AE60", text="▶ Monitorando")
            self.update_timer_color()
            self.app_times = {app: 0.0 for app in self.target_windows}
            threading.Thread(target=self.track_time, daemon=True).start()

    def stop_tracking(self):
        if self.running:
            self.running = False
            self.tracking_active = False
            self.stop_tracking_event.set()
            self.start_btn.configure(fg_color="#22D3EE", text="▶ Iniciar")
            self.update_timer_color()

            if self.elapsed_time > 0:
                self.save_session()
            self.elapsed_time = 0
            self.update_timer_display()

    def reset_timer(self):
        if messagebox.askyesno("Confirmar", "Resetar temporizador e descartar sessão atual?"):
            self.elapsed_time = 0
            self.update_timer_display()
            self.tracking_active = False
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

    def save_session(self):
        now = datetime.now()
        date_str = now.strftime("%d/%m/%Y")
        time_str = now.strftime("%H:%M:%S")
        with open(self.filename, mode="a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            for app, minutes in self.app_times.items():
                duration = self.format_duration(minutes)
                writer.writerow([date_str, time_str, app, duration])
                self.add_history_entry(date_str, time_str, app, duration)
        self.elapsed_time = 0
        self.update_timer_display()
        self.app_times = {}

    def format_duration(self, elapsed_minutes):
        total_seconds = int(elapsed_minutes * 60)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def load_history(self):
        self.clear_history_content()
        self.update_usage_reports(self.app_filter_var.get() if hasattr(self, 'app_filter_var') else None)
        if os.path.exists(self.filename):
            with open(self.filename, mode="r", encoding="utf-8") as file:
                reader = csv.reader(file)
                try:
                    next(reader)
                except StopIteration:
                    return
                rows = list(reader)
                rows_to_display = rows if self.show_full_history else rows[-5:]
                for row in rows_to_display:
                    if len(row) >= 4:
                        self.add_history_entry(row[0], row[1], row[2], row[3])

    def toggle_history_display(self):
        self.show_full_history = self.show_full_var.get()
        self.load_history()

    def apply_date_filter(self):
        date_str = self.date_filter_var.get()
        self.clear_history_content()
        if not date_str:
            self.load_history()
            return
        try:
            filter_date = datetime.strptime(date_str, "%d/%m/%Y")
            with open(self.filename, mode="r", encoding="utf-8") as file:
                reader = csv.reader(file)
                next(reader)
                for row in reader:
                    if len(row) >= 4:
                        row_date = datetime.strptime(row[0], "%d/%m/%Y")
                        if row_date.date() == filter_date.date():
                            self.add_history_entry(row[0], row[1], row[2], row[3])
        except ValueError:
            messagebox.showerror("Data Inválida", "Use o formato DD/MM/AAAA")

    def update_usage_reports(self, app_query=None):
        if not os.path.exists(self.filename):
            for text_lbl, time_lbl in self.usage_report_labels:
                text_lbl.configure(text="")
                time_lbl.configure(text="")
            return
        now = datetime.now()
        today = now.date()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        total_day = 0
        total_week = 0
        total_month = 0
        app_query = (app_query or '').strip().lower()
        with open(self.filename, mode="r", encoding="utf-8") as file:
            reader = csv.reader(file)
            try:
                next(reader)
            except StopIteration:
                return
            for row in reader:
                if len(row) < 4:
                    continue
                try:
                    row_date = datetime.strptime(row[0], "%d/%m/%Y").date()
                except Exception:
                    continue
                app_name = row[2].lower()
                if app_query and app_query not in app_name:
                    continue
                try:
                    h, m, s = map(int, str(row[3]).split(':'))
                    minutes = h * 60 + m + s / 60
                except Exception:
                    minutes = 0
                if row_date == today:
                    total_day += minutes
                if week_start <= row_date <= today:
                    total_week += minutes
                if month_start <= row_date <= today:
                    total_month += minutes

        def fmt(mins):
            h = int(mins // 60)
            m = int(mins % 60)
            s = int((mins * 60) % 60)
            return f"{h:02d}:{m:02d}:{s:02d}"

        report_texts = [
            "⌚ Tempo de uso hoje:",
            "⌛ Tempo de uso na semana:",
            "📅 Tempo de uso no mês:"
        ]
        times = [fmt(total_day), fmt(total_week), fmt(total_month)]
        for i, (text_lbl, time_lbl) in enumerate(self.usage_report_labels):
            text_lbl.configure(text=report_texts[i], font=("Arial", 10), text_color="#6b7280")
            time_lbl.configure(text=times[i], font=("Arial", 10, "bold"), text_color="#22D3EE")

    def apply_app_filter(self):
        app_query = self.app_filter_var.get().strip().lower()
        self.clear_history_content()
        self.update_usage_reports(app_query)
        if not app_query:
            self.load_history()
            return
        if os.path.exists(self.filename):
            with open(self.filename, mode="r", encoding="utf-8") as file:
                reader = csv.reader(file)
                try:
                    next(reader)
                except StopIteration:
                    return
                for row in reader:
                    if len(row) >= 4 and app_query in row[2].lower():
                        self.add_history_entry(row[0], row[1], row[2], row[3])

    def clear_history_content(self):
        for widget in self.history_content.winfo_children():
            widget.destroy()

    def show_history(self):
        self.page_main.pack_forget()
        self.page_settings.pack_forget()
        self.page_stats.pack_forget()
        self.page_history.pack(fill="both", expand=True)

    def show_stats(self):
        self.page_main.pack_forget()
        self.page_settings.pack_forget()
        self.page_history.pack_forget()
        self.page_stats.pack(fill="both", expand=True)
        self.update_stats_dashboard()

    def show_settings_page(self):
        self.page_main.pack_forget()
        self.page_stats.pack_forget()
        self.page_history.pack_forget()
        self.page_settings.pack(fill="both", expand=True)

    def show_main_page(self):
        self.page_settings.pack_forget()
        self.page_stats.pack_forget()
        self.page_history.pack_forget()
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
                self.root.geometry("425x500")
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
                messagebox.showerror("Atalho Inválido", f"Formato inválido para o atalho '{key}'. Use o formato 'ctrl+alt+e'.")
                return

        try:
            idle_threshold = float(self.idle_threshold_var.get())
            if idle_threshold <= 0:
                raise ValueError()
            self.idle_threshold = idle_threshold
        except (ValueError, TypeError):
            messagebox.showerror("Tempo de Inatividade Inválido", "Digite um número positivo válido para o tempo de inatividade.")
            return

        try:
            check_interval = float(self.check_interval_var.get())
            if check_interval <= 0:
                raise ValueError()
            self.check_interval = check_interval
        except (ValueError, TypeError):
            messagebox.showerror("Intervalo de Verificação Inválido", "Digite um número positivo válido para o intervalo de verificação.")
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
            messagebox.showinfo("Configurações Salvas", "Suas configurações foram salvas e aplicadas.")
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao salvar configurações: {e}")

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
            self.root.geometry("425x500")
            self.nav_frame.pack(side="bottom", fill="x", padx=20, pady=20)
            self.update_timer_color()

    def update_timer_color(self):
        is_active = self.running and getattr(self, 'tracking_active', False)
        color = "#1ABC9C" if is_active else "#EA697B"
        if hasattr(self, 'timer_label'):
            self.timer_label.configure(text_color=color)
        if hasattr(self, 'compact_timer_label'):
            self.compact_timer_label.configure(text_color=color)

    def update_stats_dashboard(self):
        for widget in self.page_stats.winfo_children():
            widget.destroy()

        scroll_frame = ctk.CTkScrollableFrame(self.page_stats, fg_color="transparent", label_text="")
        scroll_frame.pack(fill="both", expand=True, padx=0, pady=0)

        title_stats_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        title_stats_frame.pack(fill="x", pady=(35, 10), padx=0)
        back_btn = ctk.CTkButton(
            title_stats_frame,
            text="‹ Voltar",
            width=80,
            fg_color="#6b7280",
            hover_color="#374151",
            text_color="#FFFFFF",
            font=("Arial", 12, "bold"),
            command=self.show_main_page
        )
        back_btn.pack(side="left", padx=(0, 0), pady=0)
        ctk.CTkLabel(title_stats_frame, text="Estatísticas", font=("Arial", 18, "bold"), text_color="#22d3ee").pack(side="left", padx=(90, 0))

        self.stats_app_filter_var = getattr(self, 'stats_app_filter_var', None)
        self.stats_app_filter_selected = getattr(self, 'stats_app_filter_selected', [])

        try:
            if not os.path.exists(self.filename) or os.path.getsize(self.filename) < 20:
                ctk.CTkLabel(scroll_frame, text="Sem dados de histórico para gerar estatísticas.").pack(pady=20)
                ctk.CTkButton(scroll_frame, text="Voltar", command=self.show_main_page).pack(pady=10)
                return

            df = pd.read_csv(self.filename, header=0, engine='python')
            if df.empty:
                ctk.CTkLabel(scroll_frame, text="Sem dados de histórico para gerar estatísticas.").pack(pady=20)
                ctk.CTkButton(scroll_frame, text="Voltar", command=self.show_main_page).pack(pady=10)
                return

            if 'DURATION' not in df.columns:
                if len(df.columns) == 3:
                    df = df.reset_index()
                df.columns = ['DATE', 'TIME', 'APP', 'DURATION'][:len(df.columns)]

            def duration_to_minutes(duration_str):
                try:
                    h, m, s = map(int, str(duration_str).split(':'))
                    return (h * 60) + m + (s / 60)
                except Exception:
                    return 0

            def sanitize_label(text, max_len=32):
                cleaned = re.sub(r'[𐀀-􏿿☀-➿︀-️]', '', str(text)).strip()
                if not cleaned:
                    cleaned = str(text).encode('ascii', 'ignore').decode('ascii').strip() or 'App'
                if len(cleaned) > max_len:
                    return cleaned[:max_len-3] + '...'
                return cleaned

            df['MINUTES'] = df['DURATION'].apply(duration_to_minutes)
            df['DATE'] = pd.to_datetime(df['DATE'], format='%d/%m/%Y')

            app_list = sorted(df['APP'].unique())

            filter_frame = ctk.CTkFrame(scroll_frame, corner_radius=5, fg_color="#323b4c")
            filter_frame.pack(fill="x", padx=20, pady=(0, 10), anchor="w")

            ctk.CTkLabel(filter_frame, text="Tempo Total por App:", font=("Arial", 12, "bold"), text_color="white", fg_color="transparent").pack(side="top", anchor="w", padx=(5, 0), pady=(5, 0))

            listbox_frame = tk.Frame(filter_frame, bg="#323b4c")
            listbox_frame.pack(side="top", anchor="w", pady=(5, 5), padx=(5, 0))
            listbox_width = max(28, min(60, int(self.page_stats.winfo_width() / 8)))
            app_listbox = tk.Listbox(
                listbox_frame,
                selectmode="multiple",
                exportselection=False,
                height=min(8, len(app_list)),
                width=listbox_width,
                bg="#323b4c",
                fg="white",
                selectbackground="#444b5a",
                selectforeground="white",
                highlightthickness=0,
                relief="flat",
                borderwidth=0,
                font=("Arial", 11)
            )
            for idx, app in enumerate(app_list):
                app_listbox.insert(tk.END, app)
                if app in self.stats_app_filter_selected:
                    app_listbox.selection_set(idx)
            app_listbox.pack(side="left", fill="x", expand=True)

            def apply_multi_app_filter():
                self.stats_app_filter_selected = [app_list[int(i)] for i in app_listbox.curselection()]
                self.update_stats_dashboard()

            apply_btn = ctk.CTkButton(filter_frame, text="Aplicar", width=60, command=apply_multi_app_filter)
            apply_btn.pack(side="left", padx=(10, 0))

            if self.stats_app_filter_selected:
                df = df[df['APP'].isin(self.stats_app_filter_selected)]

            app_usage = df.groupby('APP')['MINUTES'].sum().sort_values(ascending=True)
            daily_avg = df.groupby(df['DATE'].dt.date)['MINUTES'].sum().mean()
            total_time = app_usage.to_dict()

            stats_frame = ctk.CTkFrame(scroll_frame)
            stats_frame.pack(fill="x", padx=20, pady=10)

            if pd.notnull(daily_avg):
                total_seconds = int(daily_avg * 60)
                h = total_seconds // 3600
                m = (total_seconds % 3600) // 60
                s = total_seconds % 60
                daily_avg_str = f"{h:02d}:{m:02d}:{s:02d}"
            else:
                daily_avg_str = "00:00:00"

            ctk.CTkLabel(stats_frame, text=f"Média Diária: {daily_avg_str}", font=("Arial", 12)).pack(anchor="w", pady=5)
            for app, minutes in total_time.items():
                ctk.CTkLabel(stats_frame, text=f"{app}: {minutes:.1f} minutos", font=("Arial", 12)).pack(anchor="w", padx=20)

            plt.style.use('dark_background')
            plt.rcParams.update({'font.size': 11, 'font.sans-serif': ['Segoe UI', 'DejaVu Sans', 'Arial']})
            fig, axs = plt.subplots(2, 1, figsize=(10, 8), dpi=100, facecolor='#232b3b', gridspec_kw={'height_ratios': [1, 1]})
            ax1, ax2 = axs

            if len(app_usage) > 0 and app_usage.sum() > 0:
                colors = plt.cm.Set3.colors if len(app_usage) <= 12 else None
                pie_labels = [sanitize_label(a) for a in app_usage.index]
                ax1.pie(app_usage, labels=pie_labels, autopct='%1.1f%%', startangle=140, colors=colors, textprops={'color': 'white', 'fontsize': 11})
                ax1.set_title("Distribuição de Uso (Pizza)", color='white', fontsize=11)
                ax1.set_facecolor('#232b3b')
            else:
                ax1.axis('off')

            for app in df['APP'].unique():
                app_data = df[df['APP'] == app]['MINUTES']
                ax2.plot(app_data.index, app_data.values, label=sanitize_label(app))

            ax2.set_title("Uso dos Aplicativos ao Longo do Tempo", color='white', fontsize=11)
            ax2.set_xlabel('Data', color='white', fontsize=11)
            ax2.set_ylabel('Minutos', color='white', fontsize=11)
            ax2.tick_params(colors='white', labelsize=11, rotation=45)
            ax2.legend(loc='upper left', facecolor='#232b3b', edgecolor='white', labelcolor='white', fontsize=11)
            ax2.set_facecolor('#232b3b')

            fig.tight_layout(pad=2.0)
            canvas = FigureCanvasTkAgg(fig, master=scroll_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)

        except Exception as e:
            ctk.CTkLabel(scroll_frame, text=f"Erro: {e}").pack(pady=20)

    def setup_tray_thread(self):
        if not hasattr(self, 'tray_thread') or not self.tray_thread.is_alive():
            self.tray_thread = threading.Thread(target=self.setup_tray, daemon=True)
            self.tray_thread.start()

    def setup_tray(self):
        initial_image = self._generate_timer_icon_image()
        menu = (
            pystray.MenuItem("Mostrar", self.restore_from_tray, default=True),
            pystray.MenuItem("Sair", self.on_close)
        )
        self.tray_icon = pystray.Icon("TimeTracker", initial_image, "Rastreador de Tempo", menu)
        self.tray_icon_update_running = True
        self.tray_stop_event.clear()
        threading.Thread(target=self._update_tray_icon_periodically, daemon=True).start()
        self.tray_icon.run()

    def _update_tray_icon_periodically(self):
        while self.tray_icon_update_running and not self.tray_stop_event.is_set():
            if hasattr(self, 'tray_icon') and self.tray_icon.visible:
                new_image = self._generate_timer_icon_image()
                full_timer_str = self.timer_var.get()
                tooltip_text = f"Rastreador de Tempo\n{full_timer_str}"
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
        # Reutiliza a fonte em cache para evitar leituras repetidas de disco
        font = getattr(self, 'tray_font', None) or ImageFont.load_default()
        left, top, right, bottom = d.textbbox((0, 0), display_text, font=font)
        x_draw = (img_size[0] - (right - left)) / 2
        y_draw = (img_size[1] - (bottom - top)) / 2
        d.text((x_draw, y_draw), display_text, fill=text_color, font=font)
        return image


if __name__ == "__main__":
    root = ctk.CTk()
    app = TimeTrackerApp(root)
    root.mainloop()

