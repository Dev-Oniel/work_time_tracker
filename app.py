import customtkinter as ctk
from tkinter import messagebox
import time
import threading
import csv
import os
import json
from datetime import datetime
import pygetwindow as gw
import pyautogui
import keyboard
import pystray
from PIL import Image, ImageDraw, ImageFont
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import sys

def resource_path(relative_path):
    """Retorna o caminho absoluto para recursos, compatível com PyInstaller."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# === Tradução ===
TRANSLATIONS = {}
LANGUAGES = {'en': 'English', 'pt': 'Portuguese (BR)'}
def load_translations():
    global TRANSLATIONS
    try:
        with open(resource_path('translations.json'), 'r', encoding='utf-8') as f:
            TRANSLATIONS = json.load(f)
    except Exception as e:
        print(f"Could not load translations: {e}")
        TRANSLATIONS = {}

def t(key, **kwargs):
    lang = getattr(TimeTrackerApp, 'current_language', 'en')
    value = TRANSLATIONS.get(lang, {}).get(key, key)
    if kwargs:
        try:
            return value.format(**kwargs)
        except Exception:
            return value
    return value

load_translations()

# Configuração do tema
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme(resource_path("timetracker_theme.json"))

class TimeTrackerApp:
    current_language = 'en'  # Classe-level, para acesso global
    def __init__(self, root):
        self.root = root
        self.language = 'en'  # Inicializa antes de load_settings
        self.root.title("TimeTracker")
        self.root.geometry("425x855")
        self.root.resizable(False, False)  # Permite redimensionar: DESATIVADO por padrão
        try:
            self.root.iconbitmap(resource_path("icone.ico"))
        except Exception as e:
            print(f"Could not load icon: {e}")
        self.root.attributes('-toolwindow', True)
        self.always_on_top = True
        self.resizable = False  # Desativado por padrão
        self.close_to_tray = True  # Padrão: minimizar para bandeja, será usado na criação da interface
        
        # Variáveis
        self.target_windows = []
        self.elapsed_time = 0
        self.running = False
        self.tracking_active = False
        self.last_active_window = None
        self.last_activity_time = time.time()
        self.idle_threshold = 10  # Agora configurável
        self.check_interval = 1.0  # Intervalo de verificação configurável (em segundos)
        self.mouse_position = pyautogui.position()
        self.timer_var = ctk.StringVar(value="00:00:00")
        self.show_full_history = False  # Controla exibição do histórico completo
        
        # Arquivo de configurações e atalhos
        self.settings_file = "settings.json"
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
        self.auto_compact_mode_var = ctk.BooleanVar(value=True) # Novo: Padrão para ativar automaticamente

        # Arquivo CSV
        self.filename = "time_history.csv"
        self.initialize_csv()
        
        self.load_settings()
        self.create_interface()
        self.load_history()
        self.register_shortcuts()

        # Configurar monitoramento de teclado
        keyboard.hook(self.keyboard_activity)

        # Configurar bandeja do sistema
        self.root.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)
        self.tray_icon_update_running = False

        # Barra customizada
        self.root.overrideredirect(True)  # Remove a barra do sistema

        # Frame da barra
        self.title_bar = ctk.CTkFrame(self.root, fg_color="#181e29", height=32)
        self.title_bar.place(x=0, y=0, relwidth=1)

        # Ícone
        try:
            from PIL import Image, ImageTk
            icon_img = Image.open(resource_path("icone.ico")).resize((25, 25))
            self.icon_photo = ImageTk.PhotoImage(icon_img)
            icon_label = ctk.CTkLabel(self.title_bar, image=self.icon_photo, text="", fg_color="#181e29")
            icon_label.pack(side="left", padx=(8, 4), pady=4)
        except Exception as e:
            icon_label = ctk.CTkLabel(self.title_bar, text="", fg_color="#181e29")
            icon_label.pack(side="left", padx=(8, 4), pady=4)

        # Título
        title_label = ctk.CTkLabel(self.title_bar, text="Work Time Tracker", font=("Arial", 13, "bold"), text_color="#22D3EE", fg_color="#181e29")
        title_label.pack(side="left", padx=(0, 10), pady=4)

        # Botão fechar
        close_btn = ctk.CTkButton(
            self.title_bar, text="✕", width=32, height=24, fg_color="#EA697B", hover_color="#C53030",
            text_color="#FFFFFF", font=("Arial", 14, "bold"), corner_radius=8, command=self.handle_close
        )
        close_btn.pack(side="right", padx=8, pady=4)

        # Permitir arrastar a janela pela barra customizada
        def start_move(event):
            self._drag_start_x = event.x
            self._drag_start_y = event.y

        def do_move(event):
            x = self.root.winfo_x() + event.x - self._drag_start_x
            y = self.root.winfo_y() + event.y - self._drag_start_y
            self.root.geometry(f"+{x}+{y}")

        self.title_bar.bind("<Button-1>", start_move)
        self.title_bar.bind("<B1-Motion>", do_move)
        title_label.bind("<Button-1>", start_move)
        title_label.bind("<B1-Motion>", do_move)
        icon_label.bind("<Button-1>", start_move)
        icon_label.bind("<B1-Motion>", do_move)

    def keyboard_activity(self, event):
        """Registra atividade do teclado"""
        self.last_activity_time = time.time()

    def check_mouse_activity(self):
        """Verifica se o mouse se moveu"""
        current_position = pyautogui.position()
        if current_position != self.mouse_position:
            self.mouse_position = current_position
            self.last_activity_time = time.time()
        return self.last_activity_time

    def is_user_active(self):
        """Verifica se o usuário está ativo"""
        return (time.time() - self.last_activity_time) < self.idle_threshold

    def initialize_csv(self):
        if not os.path.exists(resource_path(self.filename)):
            with open(resource_path(self.filename), mode="w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(["DATE", "TIME", "APPS", "DURATION"])

    def load_settings(self):
        """Carrega configurações de um arquivo JSON."""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                    self.shortcuts.update(settings.get("shortcuts", {}))
                    self.always_on_top = settings.get("always_on_top", True)
                    self.resizable = settings.get("resizable", False)
                    self.idle_threshold = settings.get("idle_threshold", 10)
                    self.check_interval = settings.get("check_interval", 1.0)
                    self.close_to_tray = settings.get("close_to_tray", True)
                    self.auto_compact_mode_var.set(settings.get("auto_compact_mode", True))
                    self.language = settings.get("language", "en")  # Novo: idioma
        except (json.JSONDecodeError, FileNotFoundError):
            pass
        
        self.start_shortcut_var.set(self.shortcuts.get("start"))
        self.stop_shortcut_var.set(self.shortcuts.get("stop"))
        self.reset_shortcut_var.set(self.shortcuts.get("reset"))
        self.compact_shortcut_var.set(self.shortcuts.get("compact"))
        self.idle_threshold_var.set(str(self.idle_threshold))
        self.check_interval_var.set(str(self.check_interval))
        self.close_to_tray_var.set(self.close_to_tray)
        self.root.attributes('-topmost', self.always_on_top)
        self.root.resizable(self.resizable, self.resizable)
        TimeTrackerApp.current_language = self.language  # Atualiza idioma global

    def create_interface(self):
        # Fundo principal
        self.root.configure(bg="#181E29")
        self.page_main = ctk.CTkFrame(self.root, fg_color="#232B3B", corner_radius=12)
        self.page_main.pack(fill="both", expand=True, pady=(32, 0))  # 32px para baixo da barra customizada

        # Título
        ctk.CTkLabel(
            self.page_main, text=t("main_title"),
            font=("Arial", 28, "bold"), text_color="#22D3EE", fg_color="#232B3B"
        ).pack(pady=(5, 0))

        ctk.CTkLabel(
            self.page_main, text=t("main_subtitle"),
            font=("Arial", 14), text_color="#A1A7B3", fg_color="#232B3B"
        ).pack(pady=(0, 5))

        # Comboboxes
        combo_style = {"fg_color": "#323B4C", "text_color": "#FFFFFF", "button_color": "#565b5e"}
        self.app_combos = []
        for i in range(3):
            combo = ctk.CTkComboBox(
                self.page_main,
                values=self.get_window_titles(),
                width=340,
                fg_color="#323B4C",
                text_color="#FFFFFF",
                button_color="#565b5e",
                dropdown_fg_color="#323B4C"
            )
            combo.pack(pady=5)
            combo.set(f"{t('application')} {i+1}")
            self.app_combos.append(combo)

        # Timer
        timer_frame = ctk.CTkFrame(self.page_main, fg_color="#323b4c", corner_radius=50)
        timer_frame.pack(pady=5)
        self.timer_label = ctk.CTkLabel(
            timer_frame, textvariable=self.timer_var,
            font=("Arial", 45, "bold"), text_color="#22D3EE", fg_color="#323b4c"
        )
        self.timer_label.pack(padx=20, pady=10)

        # Botões grandes (Start, Stop)
        btn_frame1 = ctk.CTkFrame(self.page_main, fg_color="#232B3B")
        btn_frame1.pack(pady=(1, 0))
        btn_style1 = {"width": 130, "height": 40, "corner_radius": 12, "font": ("Arial", 15, "bold")}
        self.start_btn = ctk.CTkButton(btn_frame1, text=t("start"), fg_color="#22D3EE", text_color="#FFFFFF", hover_color="#06B6D4", **btn_style1, command=self.start_tracking)
        self.start_btn.grid(row=0, column=0, padx=5, pady=5)
        self.stop_btn = ctk.CTkButton(btn_frame1, text=t("stop"), fg_color="#F472B6", text_color="#FFFFFF", hover_color="#EC4899", **btn_style1, command=self.stop_tracking)
        self.stop_btn.grid(row=0, column=1, padx=5, pady=5)

        # Botões pequenos (Reset, Compact Mode)
        btn_frame2 = ctk.CTkFrame(self.page_main, fg_color="#232B3B")
        btn_frame2.pack(pady=(1, 5))
        btn_style2 = {"width": 130, "height": 40, "corner_radius": 12, "font": ("Arial", 15, "bold")}
        self.reset_btn = ctk.CTkButton(btn_frame2, text=t("reset"), fg_color="#6B7280", text_color="#FFFFFF", hover_color="#374151", **btn_style2, command=self.reset_timer)
        self.reset_btn.grid(row=0, column=0, padx=5, pady=5)
        self.compact_btn = ctk.CTkButton(btn_frame2, text=t("compact"), fg_color="#818CF8", text_color="#FFFFFF", hover_color="#323b4c", **btn_style2, command=self.toggle_compact_mode)
        self.compact_btn.grid(row=0, column=1, padx=5, pady=5)

        # Seção de histórico
        self.create_history_section()

        # Página 2: Configurações
        self.page_settings = ctk.CTkFrame(self.root, fg_color="#232B3B")
        ctk.CTkLabel(self.page_settings, text=t("settings"), font=("Arial", 20, "bold"), text_color="#22D3EE", fg_color="#232B3B").pack(pady=(40, 10))

        # Combobox de idioma
        self.language_var = ctk.StringVar(value=self.language)
        lang_frame = ctk.CTkFrame(self.page_settings, fg_color="#232B3B")
        lang_frame.pack(pady=5, padx=20, fill="x")
        ctk.CTkLabel(lang_frame, text=t("language"), text_color="#A1A7B3").pack(side="left", padx=5)
        self.language_combo = ctk.CTkComboBox(
            lang_frame,
            values=[LANGUAGES[k] for k in LANGUAGES],
            width=160,
            fg_color="#323B4C",
            text_color="#FFFFFF",
            button_color="#565b5e",
            variable=self.language_var,
            command=self.on_language_change
        )
        self.language_combo.pack(side="left", padx=5)
        # Seleciona o idioma correto
        self.language_combo.set(LANGUAGES.get(self.language, "English"))

        close_to_tray_check = ctk.CTkCheckBox(
            self.page_settings,
            text=t("minimize_to_tray"),
            variable=self.close_to_tray_var,
            fg_color="#323B4C",
            text_color="#A1A7B3"
        )
        close_to_tray_check.pack(pady=10, padx=20, anchor="w")
        
        # Novo: Checkbox para modo compacto automático
        auto_compact_check = ctk.CTkCheckBox(
            self.page_settings,
            text="Automatically enter compact mode when tracking starts",
            variable=self.auto_compact_mode_var,
            fg_color="#323B4C",
            text_color="#A1A7B3"
        )
        auto_compact_check.pack(pady=10, padx=20, anchor="w")

        # Always On Top
        always_on_top_var = ctk.BooleanVar(value=self.always_on_top)
        always_on_top_check = ctk.CTkCheckBox(
            self.page_settings,
            text="Always On Top",
            variable=always_on_top_var,
            command=lambda: self.toggle_always_on_top(always_on_top_var.get()),
            fg_color="#323B4C", text_color="#A1A7B3"
        )
        always_on_top_check.pack(pady=10, padx=20, anchor="w")

        # Resizable
        resizable_var = ctk.BooleanVar(value=self.resizable)
        resizable_check = ctk.CTkCheckBox(
            self.page_settings,
            text="Allow Resizing",
            variable=resizable_var,
            command=lambda: self.toggle_resizable(resizable_var.get()),
            fg_color="#323B4C", text_color="#A1A7B3"
        )
        resizable_check.pack(pady=10, padx=20, anchor="w")

        # Idle Threshold
        idle_frame = ctk.CTkFrame(self.page_settings, fg_color="#232B3B")
        idle_frame.pack(pady=10, padx=20, fill="x")
        ctk.CTkLabel(idle_frame, text="Idle Threshold (seconds):", text_color="#A1A7B3").pack(side="left", padx=5)
        ctk.CTkEntry(idle_frame, textvariable=self.idle_threshold_var, width=100, fg_color="#323B4C", text_color="#FFFFFF").pack(side="left", padx=5)

        # Check Interval
        interval_frame = ctk.CTkFrame(self.page_settings, fg_color="#232B3B")
        interval_frame.pack(pady=10, padx=20, fill="x")
        ctk.CTkLabel(interval_frame, text="Check Interval (seconds):", text_color="#A1A7B3").pack(side="left", padx=5)
        ctk.CTkEntry(interval_frame, textvariable=self.check_interval_var, width=100, fg_color="#323B4C", text_color="#FFFFFF").pack(side="left", padx=5)

        # Atalhos
        shortcuts_frame = ctk.CTkFrame(self.page_settings, fg_color="#232B3B")
        shortcuts_frame.pack(pady=10, padx=20, fill="x")
        ctk.CTkLabel(shortcuts_frame, text="Customize Keyboard Shortcuts", font=("Arial", 14, "bold"), text_color="#22D3EE").grid(row=0, column=0, columnspan=2, pady=(5, 10))
        shortcut_labels = ["Start Timer", "Stop Timer", "Reset Timer", "Toggle Compact"]
        shortcut_vars = [self.start_shortcut_var, self.stop_shortcut_var, self.reset_shortcut_var, self.compact_shortcut_var]
        for i, label_text in enumerate(shortcut_labels):
            ctk.CTkLabel(shortcuts_frame, text=f"{label_text}:", text_color="#A1A7B3").grid(row=i+1, column=0, padx=10, pady=5, sticky="w")
            entry = ctk.CTkEntry(shortcuts_frame, textvariable=shortcut_vars[i], fg_color="#323B4C", text_color="#FFFFFF")
            entry.grid(row=i+1, column=1, padx=10, pady=5, sticky="ew")
        shortcuts_frame.grid_columnconfigure(1, weight=1)

        # Botões de ação da página de configurações
        settings_btn_frame = ctk.CTkFrame(self.page_settings, fg_color="#232B3B")
        settings_btn_frame.pack(pady=20, padx=20, fill="x")
        ctk.CTkButton(settings_btn_frame, text="Save Settings", fg_color="#22D3EE", text_color="#181E29", hover_color="#06B6D4", command=self.save_settings).pack(side="right", padx=5)
        ctk.CTkButton(settings_btn_frame, text="Back", fg_color="#6B7280", text_color="#FFFFFF", hover_color="#374151", command=self.show_main_page).pack(side="right", padx=5)

        # Dicas para o usuário (Settings)
        tips_frame = ctk.CTkFrame(self.page_settings, fg_color="#232B3B")
        tips_frame.pack(pady=(0, 10), padx=20, fill="x")
        ctk.CTkLabel(tips_frame, text=t("tip_title"), font=("Arial", 13, "bold"), text_color="#22D3EE").pack(anchor="w", pady=(0, 2))
        ctk.CTkLabel(tips_frame, text=t("tip_select_before"), font=("Arial", 11), text_color="#A1A7B3", wraplength=380, justify="left").pack(anchor="w", pady=(0, 2))
        ctk.CTkLabel(tips_frame, text=t("tip_blank_for_all"), font=("Arial", 11), text_color="#A1A7B3", wraplength=380, justify="left").pack(anchor="w")

        # Página 3: Estatísticas
        self.page_stats = ctk.CTkFrame(self.root, fg_color="#232B3B")
        # O conteúdo será gerado dinamicamente

        # Frame de navegação fixo no rodapé
        self.nav_frame = ctk.CTkFrame(self.root, fg_color="#181e29")
        self.nav_frame.pack(side="bottom", fill="x", padx=20, pady=20)
        nav_btn_width = 120
        ctk.CTkButton(self.nav_frame, text=t("history"), font=("Arial", 10), fg_color="#181e29",
                     hover_color="#34495E", border_width=0, border_color="#7F8C8D",
                     text_color="#7F8C8D", command=self.show_history, width=nav_btn_width).pack(side="left", expand=True, padx=5)
        ctk.CTkButton(self.nav_frame, text=t("stats"), font=("Arial", 10), fg_color="#181e29",
                     hover_color="#34495E", border_width=0, border_color="#7F8C8D",
                     text_color="#7F8C8D", command=self.show_stats, width=nav_btn_width).pack(side="left", expand=True, padx=5)
        ctk.CTkButton(self.nav_frame, text=t("settings_nav"), font=("Arial", 10), fg_color="#181e29",
                     hover_color="#34495E", border_width=0, border_color="#7F8C8D",
                     text_color="#7F8C8D", command=self.show_settings_page, width=nav_btn_width).pack(side="left", expand=True, padx=5)

    def create_history_section(self):
        history_frame = ctk.CTkFrame(self.page_main, corner_radius=10, fg_color="#232B3B")
        history_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        ctk.CTkLabel(history_frame, text=t("usage_history"), text_color="#22D3EE", font=("Arial", 28, "bold")).pack(pady=(10, 5))
        
        # Filtros
        filter_frame = ctk.CTkFrame(history_frame, fg_color="#232B3B",)
        filter_frame.pack(fill="x", padx=5, pady=5)
        
        self.show_full_var = ctk.BooleanVar(value=self.show_full_history)
        ctk.CTkCheckBox(filter_frame, text=t("show_full_history"), variable=self.show_full_var,
                        command=self.toggle_history_display).pack(side="left", padx=5)
        
        ctk.CTkLabel(filter_frame, text=t("filter_by_date")).pack(side="left", padx=5)
        self.date_filter_var = ctk.StringVar()
        self.date_filter_entry = ctk.CTkEntry(filter_frame, width=60,textvariable=self.date_filter_var)
        self.date_filter_entry.pack(side="left", padx=0)
        ctk.CTkButton(filter_frame, text=t("apply"), command=self.apply_date_filter, width=60).pack(side="left", padx=5)
        
        # Container principal
        container = ctk.CTkFrame(history_frame, fg_color="#232B3B")
        container.pack(fill="both", expand=True, padx=0, pady=0)
        
        # Cabeçalhos
        headers_frame = ctk.CTkFrame(container, fg_color="#232b3b")
        headers_frame.pack(fill="x", padx=0, pady=(0, 0))
        
        headers = [t("date"), t("time"), t("apps"), t("duration")]
        for header in headers:
            ctk.CTkLabel(headers_frame, text=header, font=("Arial", 11, "bold"),
                        text_color="white").pack(side="left", expand=True, padx=2)
        
        # Área rolável
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

    def add_history_entry(self, date, time, apps, duration):
        """Adiciona entrada no histórico com texto ajustável"""
        entry_frame = ctk.CTkFrame(self.history_content, corner_radius=5, height=30, fg_color="#232b3b")
        entry_frame.pack(fill="x", pady=1, padx=1, expand=True)
        
        date_label = ctk.CTkLabel(entry_frame, text=date, font=("Arial", 9), anchor="w", text_color="white")
        date_label.pack(side="left", expand=True, padx=2)
        
        time_label = ctk.CTkLabel(entry_frame, text=time, font=("Arial", 9), anchor="w", text_color="white")
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
        """Obtém todos os títulos de janela disponíveis"""
        return ["Choose App"] + [title for title in gw.getAllTitles() if title.strip()]

    def start_tracking(self):
        """Inicia o tracking dos aplicativos selecionados"""
        # Filtra os placeholders e valores vazios
        self.target_windows = [
            combo.get() for combo in self.app_combos
            if combo.get() and "Application" not in combo.get() and "Choose App" not in combo.get()
        ]
        
        if not self.target_windows:
            messagebox.showwarning(t("warning"), t("please_select_app"))
            return
            
        if not self.running:
            self.running = True
            self.tracking_active = False
            self.last_activity_time = time.time()
            self.start_btn.configure(fg_color="#27AE60", text="▶ Tracking")
            self.update_timer_color()
            threading.Thread(target=self.track_time, daemon=True).start()

    def stop_tracking(self):
        """Para o tracking e salva a sessão"""
        if self.running:
            self.running = False
            self.start_btn.configure(fg_color="#3498DB", text="▶ Start")
            self.update_timer_color()
            
            if self.elapsed_time > 0:
                self.save_session()
            self.tracking_active = False
            self.elapsed_time = 0
            self.update_timer_display()

    def reset_timer(self):
        """Reseta o timer completamente"""
        if messagebox.askyesno(t("confirm"), t("reset_confirm")):
            self.elapsed_time = 0
            self.update_timer_display()
            self.tracking_active = False
            self.update_timer_color()

    def track_time(self):
        """Thread principal que monitora o tempo"""
        while self.running:
            self.check_mouse_activity()
            current_window = self.get_active_window()
            user_active = self.is_user_active()
            window_active = current_window and any(target in current_window for target in self.target_windows)
            if user_active and window_active:
                if not self.tracking_active:
                    self.tracking_active = True
                    self.timer_label.configure(text_color="#1ABC9C")
                    if hasattr(self, 'compact_timer_label'):
                        self.compact_timer_label.configure(text_color="#1ABC9C")
                    # Ativa o modo compacto automaticamente quando o contador começa a rodar
                    if not hasattr(self, '_compact_mode') or not self._compact_mode:
                        self.root.after(0, self.toggle_compact_mode)
                self.elapsed_time += (self.check_interval / 60.0)  # Incrementa com base no intervalo
                self.update_timer_display()
            else:
                if self.tracking_active:
                    self.tracking_active = False
                    self.timer_label.configure(text_color="#EA697B")
                    if hasattr(self, 'compact_timer_label'):
                        self.compact_timer_label.configure(text_color="#EA697B")
            time.sleep(self.check_interval)  # Dorme conforme intervalo configurado

    def get_active_window(self):
        """Obtém a janela ativa atual"""
        try:
            window = gw.getActiveWindow()
            return window and window.title
        except Exception as e:
            print(f"Window tracking error: {e}")
            return None

    def update_timer_display(self):
        """Atualiza o display do timer"""
        hours, remainder = divmod(int(self.elapsed_time * 60), 3600)
        minutes, seconds = divmod(remainder, 60)
        timer_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        self.timer_var.set(timer_str)
        self.update_timer_color()

    def save_session(self):
        """Salva a sessão atual no histórico"""
        now = datetime.now()
        date_str = now.strftime("%d/%m/%Y")
        time_str = now.strftime("%H:%M:%S")
        apps_str = ", ".join(self.target_windows)
        duration = self.format_duration(self.elapsed_time)
        
        with open(resource_path(self.filename), mode="a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow([date_str, time_str, apps_str, duration])
        
        self.add_history_entry(date_str, time_str, apps_str, duration)
        self.elapsed_time = 0
        self.update_timer_display()

    def format_duration(self, elapsed_minutes):
        """Formata a duração para HH:MM:SS"""
        total_seconds = int(elapsed_minutes * 60)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def load_history(self):
        """Carrega o histórico do arquivo CSV"""
        self.clear_history_content()
        if os.path.exists(resource_path(self.filename)):
            with open(resource_path(self.filename), mode="r", encoding="utf-8") as file:
                reader = csv.reader(file)
                next(reader) # Skip header
                rows = list(reader)
                if self.show_full_history:
                    rows_to_display = rows
                else:
                    rows_to_display = rows[-5:]
                for row in rows_to_display:
                    if len(row) >= 4:
                        self.add_history_entry(row[0], row[1], row[2], row[3])

    def toggle_history_display(self):
        """Alterna entre exibir todo o histórico ou as últimas 5 entradas"""
        self.show_full_history = self.show_full_var.get()
        self.load_history()

    def apply_date_filter(self):
        """Aplica filtro de data no histórico"""
        date_str = self.date_filter_var.get()
        self.clear_history_content()
        if not date_str:
            self.load_history()
            return
        try:
            filter_date = datetime.strptime(date_str, "%d/%m/%Y")
            with open(resource_path(self.filename), mode="r", encoding="utf-8") as file:
                reader = csv.reader(file)
                next(reader)
                for row in reader:
                    if len(row) >= 4:
                        row_date = datetime.strptime(row[0], "%d/%m/%Y")
                        if row_date.date() == filter_date.date():
                            self.add_history_entry(row[0], row[1], row[2], row[3])
        except ValueError:
            messagebox.showerror(t("invalid_date"), t("invalid_date_format"))

    def clear_history_content(self):
        """Limpa o conteúdo do histórico"""
        for widget in self.history_content.winfo_children():
            widget.destroy()

    def show_history(self):
        self.show_main_page()

    def show_stats(self):
        self.page_main.pack_forget()
        self.page_settings.pack_forget()
        self.page_stats.pack(fill="both", expand=True)
        self.update_stats_dashboard()

    def show_settings_page(self):
        self.page_main.pack_forget()
        self.page_stats.pack_forget()
        self.page_settings.pack(fill="both", expand=True)

    def show_main_page(self):
        self.page_settings.pack_forget()
        self.page_stats.pack_forget()
        self.page_main.pack(fill="both", expand=True, pady=(32, 0))  # <-- Corrija aqui!

    def toggle_always_on_top(self, state):
        """Ativa/desativa o modo Always On Top"""
        self.always_on_top = state
        self.root.attributes('-topmost', state)

    def toggle_resizable(self, state):
        """Ativa/desativa o redimensionamento e alterna barra customizada/barra do Windows"""
        self.resizable = state
        self.root.resizable(state, state)
        if state:
            # Restaurar barra padrão do Windows e ocultar barra customizada
            self.root.overrideredirect(False)
            if hasattr(self, 'title_bar'):
                self.title_bar.place_forget()
        else:
            # Ocultar barra padrão e mostrar barra customizada
            self.root.overrideredirect(True)
            if hasattr(self, 'title_bar'):
                self.title_bar.place(x=0, y=0, relwidth=1)

    def validate_shortcut(self, shortcut):
        """Valida o formato do atalho de teclado"""
        if not shortcut:
            return False
        try:
            # Verifica se o atalho contém apenas caracteres válidos
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
        """Salva as configurações atuais e as aplica."""
        # Validar atalhos
        new_shortcuts = {
            "start": self.start_shortcut_var.get().strip(),
            "stop": self.stop_shortcut_var.get().strip(),
            "reset": self.reset_shortcut_var.get().strip(),
            "compact": self.compact_shortcut_var.get().strip()
        }
        for key, shortcut in new_shortcuts.items():
            if shortcut and not self.validate_shortcut(shortcut):
                messagebox.showerror("Invalid Shortcut", f"Invalid format for {key} shortcut. Use format like 'ctrl+alt+e'.")
                return

        # Validar idle_threshold
        try:
            idle_threshold = float(self.idle_threshold_var.get())
            if idle_threshold <= 0:
                raise ValueError("Idle threshold must be positive")
            self.idle_threshold = idle_threshold
        except (ValueError, TypeError):
            messagebox.showerror("Invalid Idle Threshold", "Please enter a valid positive number for idle threshold.")
            return

        # Validar check_interval
        try:
            check_interval = float(self.check_interval_var.get())
            if check_interval <= 0:
                raise ValueError("Check interval must be positive")
            self.check_interval = check_interval
        except (ValueError, ValueError):
            messagebox.showerror("Invalid Check interval", "Please enter a valid positive number for check interval.")
            return

        # Desregistra atalhos antigos
        for shortcut in self.shortcuts.values():
            try:
                keyboard.remove_hotkey(shortcut)
            except (ValueError, KeyError, AttributeError):
                pass

        self.shortcuts = new_shortcuts
        self.register_shortcuts()

        settings_dict = {
            "shortcuts": self.shortcuts,
            "always_on_top": self.always_on_top,
            "resizable": self.resizable,
            "idle_threshold": self.idle_threshold,
            "check_interval": self.check_interval,
            "close_to_tray": self.close_to_tray_var.get(),
            "auto_compact_mode": self.auto_compact_mode_var.get(),
            "language": self.language  # Salva idioma
        }
        try:
            with open(resource_path(self.settings_file), 'w', encoding='utf-8') as f:
                json.dump(settings_dict, f, indent=4)
            messagebox.showinfo(t("settings_saved"), t("settings_saved_msg"))
        except Exception as e:
            messagebox.showerror(t("error"), f"{t('failed_save_settings')} {e}")

    def register_shortcuts(self):
        """Registra os atalhos de teclado com base nas configurações atuais."""
        try:
            for key, shortcut in self.shortcuts.items():
                if shortcut:
                    if key == "start":
                        keyboard.add_hotkey(shortcut, self.start_tracking)
                    elif key == "stop":
                        keyboard.add_hotkey(shortcut, self.stop_tracking)
                    elif key == "reset":
                        keyboard.add_hotkey(shortcut, self.reset_timer)
                    elif key == "compact":
                        keyboard.add_hotkey(shortcut, self.toggle_compact_mode)
        except (ValueError, KeyError) as e:
            messagebox.showerror("Invalid Shortcut", f"Could not register shortcut: {e}")

    def toggle_compact_mode(self):
        if not hasattr(self, '_compact_mode'):
            self._compact_mode = False
        self._compact_mode = not self._compact_mode  # Corrigido aqui!
        if self._compact_mode:
            self.root.geometry("185x40")
            self.page_main.pack_forget()
            if not hasattr(self, 'compact_frame'):
                self.compact_frame = ctk.CTkFrame(self.root)
                self.compact_inner = ctk.CTkFrame(self.compact_frame, fg_color="transparent")
                self.compact_inner.pack(expand=True)
                self.compact_timer_label = ctk.CTkLabel(
                    self.compact_inner, textvariable=self.timer_var,
                    font=("Arial", 28, "bold"), text_color="#1ABC9C"
                )
                self.compact_timer_label.pack(side="left", padx=(5, 2))
                self.compact_btn_compact = ctk.CTkButton(
                    self.compact_inner, text="💢", width=28, height=28,
                    font=("Arial", 16), command=self.toggle_compact_mode,
                    fg_color="#323b4c", hover_color="#818CF8", text_color="#FFFFFF"
                )
                self.compact_btn_compact.pack(side="left", padx=(2, 5))

            # Permitir mover o app clicando em qualquer lugar do frame compacto
            def start_move(event):
                self._drag_start_x = event.x
                self._drag_start_y = event.y

            def do_move(event):
                x = self.root.winfo_x() + event.x - self._drag_start_x
                y = self.root.winfo_y() + event.y - self._drag_start_y
                self.root.geometry(f"+{x}+{y}")

            self.compact_frame.bind("<Button-1>", start_move)
            self.compact_frame.bind("<B1-Motion>", do_move)
            self.compact_inner.bind("<Button-1>", start_move)
            self.compact_inner.bind("<B1-Motion>", do_move)
            self.compact_timer_label.bind("<Button-1>", start_move)
            self.compact_timer_label.bind("<B1-Motion>", do_move)
            self.compact_btn_compact.bind("<Button-1>", start_move)
            self.compact_btn_compact.bind("<B1-Motion>", do_move)
            self.compact_frame.pack(fill="both", expand=True)
            self.compact_inner.pack(expand=True)
            self.update_timer_color()
            self.nav_frame.pack_forget()
        else:
            if hasattr(self, 'compact_frame'):
                self.compact_frame.pack_forget()
            self.page_main.pack(fill="both", expand=True, pady=(32, 0))  # <-- Corrija aqui!
            self.root.geometry("425x855")
            self.nav_frame.pack(side="bottom", fill="x", padx=20, pady=20)
            self.update_timer_color()

        # Permitir arrastar a janela pela barra customizada
        def start_move(event):
            self._drag_start_x = event.x
            self._drag_start_y = event.y

        def do_move(event):
            x = self.root.winfo_x() + event.x - self._drag_start_x
            y = self.root.winfo_y() + event.y - self._drag_start_y
            self.root.geometry(f"+{x}+{y}")

        self.compact_frame.bind("<Button-1>", start_move)
        self.compact_frame.bind("<B1-Motion>", do_move)
        self.compact_inner.bind("<Button-1>", start_move)
        self.compact_inner.bind("<B1-Motion>", do_move)
        self.compact_timer_label.bind("<Button-1>", start_move)
        self.compact_timer_label.bind("<B1-Motion>", do_move)
        self.compact_btn_compact.bind("<Button-1>", start_move)
        self.compact_btn_compact.bind("<B1-Motion>", do_move)

    def update_timer_color(self):
        if self.running:
            self.timer_label.configure(text_color="#1ABC9C")
        else:
            self.timer_label.configure(text_color="#EA697B")
        
        if hasattr(self, 'compact_timer_label'):
            if self.running:
                self.compact_timer_label.configure(text_color="#1ABC9C")
            else:
                self.compact_timer_label.configure(text_color="#EA697B")

    def update_stats_dashboard(self):
        """Cria e exibe o dashboard de estatísticas."""
        for widget in self.page_stats.winfo_children():
            widget.destroy()

        ctk.CTkLabel(self.page_stats, text=t("statistics"), font=("Arial", 18, "bold")).pack(pady=(20, 10))

        try:
            if not os.path.exists(resource_path(self.filename)) or os.path.getsize(resource_path(self.filename)) < 20:
                ctk.CTkLabel(self.page_stats, text=t("no_history")).pack(pady=20)
                ctk.CTkButton(self.page_stats, text=t("back"), command=self.show_main_page).pack(pady=10)
                return

            df = pd.read_csv(resource_path(self.filename), names=[t("date"), t("time"), t("apps"), t("duration")], header=0, engine='python')
            if df.empty:
                ctk.CTkLabel(self.page_stats, text=t("no_history")).pack(pady=20)
                ctk.CTkButton(self.page_stats, text=t("back"), command=self.show_main_page).pack(pady=10)
                return

            def duration_to_minutes(duration_str):
                try:
                    h, m, s = map(int, str(duration_str).split(':'))
                    return (h * 60) + m + (s / 60)
                except (ValueError, AttributeError):
                    return 0

            df['MINUTES'] = df['DURATION'].apply(duration_to_minutes)
            app_usage = df.groupby('APPS')['MINUTES'].sum().sort_values(ascending=True)
            
            # Média diária
            df['DATE'] = pd.to_datetime(df['DATE'], format='%d/%m/%Y')
            daily_avg = df.groupby(df['DATE'].dt.date)['MINUTES'].sum().mean()
            
            # Tempo total por aplicativo
            total_time = app_usage.to_dict()

            # Exibir estatísticas textuais
            stats_frame = ctk.CTkFrame(self.page_stats)
            stats_frame.pack(fill="x", padx=20, pady=10)
            ctk.CTkLabel(stats_frame, text=t("daily_average", minutes=daily_avg), font=("Arial", 12)).pack(anchor="w", pady=5)
            ctk.CTkLabel(stats_frame, text=t("total_time_by_app"), font=("Arial", 12, "bold")).pack(anchor="w", pady=5)
            for app, minutes in total_time.items():
                ctk.CTkLabel(stats_frame, text=f"{app}: {minutes:.1f} minutes", font=("Arial", 12)).pack(anchor="w", padx=20)

            plt.style.use('dark_background')
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), dpi=100, facecolor='#2b2b2b')
            
            # Bar Chart
            app_usage.plot(kind='barh', ax=ax1, color='#1ABC9C')
            ax1.set_title(t("total_time_per_app"), color='white')
            ax1.set_xlabel('Total Minutes', color='white')
            ax1.set_ylabel('')
            ax1.tick_params(colors='white')
            ax1.set_facecolor('#3a3a3a')

            # Line Chart
            for app in df['APPS'].unique():
                app_data = df[df['APPS'] == app]['MINUTES']
                ax2.plot(app_data.index, app_data.values, label=app)
            ax2.set_title(t("app_usage_over_time"), color='white')
            ax2.set_xlabel('Date', color='white')
            ax2.set_ylabel('Minutes', color='white')
            ax2.tick_params(colors='white', rotation=45)
            ax2.legend(loc='upper left', facecolor='#3a3a3a', edgecolor='white', labelcolor='white')
            ax2.set_facecolor('#3a3a3a')

            fig.tight_layout(pad=2.0)
            canvas = FigureCanvasTkAgg(fig, master=self.page_stats)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)

        except Exception as e:
            ctk.CTkLabel(self.page_stats, text=f"{t('error')} {e}").pack(pady=20)

        ctk.CTkButton(self.page_stats, text=t("back"), command=self.show_main_page).pack(pady=10)

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
        self.tray_icon = pystray.Icon("TimeTracker", initial_image, "TimeTracker", menu)
        self.tray_icon_update_running = True
        threading.Thread(target=self._update_tray_icon_periodically, daemon=True).start()
        self.tray_icon.run()

    def _update_tray_icon_periodically(self):
        while self.tray_icon_update_running:
            if hasattr(self, 'tray_icon') and self.tray_icon.visible:
                new_image = self._generate_timer_icon_image()
                full_timer_str = self.timer_var.get()
                tooltip_text = f"TimeTracker\n{full_timer_str}"
                try:
                    self.tray_icon.icon = new_image
                    self.tray_icon.title = tooltip_text
                except Exception as e:
                    print(f"Error updating timer icon: {e}")
            time.sleep(1)

    def restore_from_tray(self, icon=None, item=None):
        self.tray_icon_update_running = False
        self.tray_icon.stop()
        self.root.after(0, self.root.deiconify)
        self.root.after(100, lambda: self.root.attributes('-topmost', self.always_on_top))

    def minimize_to_tray(self):
        self.root.withdraw()
        self.setup_tray_thread()

    def on_close(self, icon=None, item=None):
        self.tray_icon_update_running = False
        self.tray_icon.stop()
        self.running = False
        self.root.quit()

    def handle_close(self):
        if self.close_to_tray_var.get():
            self.minimize_to_tray()
        else:
            self.on_close()

    def _generate_timer_icon_image(self):
        timer_str = self.timer_var.get()
        is_running = self.running
        parts = timer_str.split(':')
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = int(parts[2])
        if hours > 0:
            display_text = f"{hours:02d}:{minutes:02d}"
        else:
            display_text = f"{minutes:02d}:{seconds:02d}"
        img_size = (64, 64)
        text_color = '#1ABC9C' if is_running else '#EA697B'
        image = Image.new('RGBA', img_size, (0, 0, 0, 0))
        d = ImageDraw.Draw(image)
        try:
            font_size = 24
            font = ImageFont.truetype("arial.ttf", font_size)
        except IOError:
            font = ImageFont.load_default()
        left, top, right, bottom = d.textbbox((0, 0), display_text, font=font)
        x_draw = (img_size[0] - (right - left)) / 2
        y_draw = (img_size[1] - (bottom - top)) / 2
        d.text((x_draw, y_draw), display_text, fill=text_color, font=font)
        return image

    def on_language_change(self, event=None):
        # Descobre a chave do idioma pelo valor
        selected = self.language_var.get()
        for k, v in LANGUAGES.items():
            if v == selected:
                self.language = k
                break
        TimeTrackerApp.current_language = self.language
        self.save_language_setting()
        self.refresh_ui_language()

    def save_language_setting(self):
        # Salva apenas o idioma no settings.json (mantendo os outros dados)
        try:
            if os.path.exists(resource_path(self.settings_file)):
                with open(resource_path(self.settings_file), 'r', encoding='utf-8') as f:
                    settings = json.load(f)
            else:
                settings = {}
            settings['language'] = self.language
            with open(resource_path(self.settings_file), 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            print(f"Failed to save language: {e}")

    def refresh_ui_language(self):
        # Descobre qual página está visível
        visible_page = None
        if hasattr(self, 'page_main') and self.page_main.winfo_ismapped():
            visible_page = 'main'
        elif hasattr(self, 'page_settings') and self.page_settings.winfo_ismapped():
            visible_page = 'settings'
        elif hasattr(self, 'page_stats') and self.page_stats.winfo_ismapped():
            visible_page = 'stats'
        # Destroi todos os frames principais
        for attr in ['page_main', 'page_settings', 'page_stats', 'nav_frame']:
            if hasattr(self, attr):
                try:
                    getattr(self, attr).destroy()
                except Exception:
                    pass
        self.create_interface()
        # Mostra a página que estava visível
        if visible_page == 'main':
            self.show_main_page()
        elif visible_page == 'settings':
            self.show_settings_page()
        elif visible_page == 'stats':
            self.show_stats()

if __name__ == "__main__":
    root = ctk.CTk()
    app = TimeTrackerApp(root)
    root.mainloop()