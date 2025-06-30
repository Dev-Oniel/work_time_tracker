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
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
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
        self.root.title("Work Time Tracker")
        self.root.geometry("425x500") # Aumentado para dar mais espaço
        self.root.resizable(True, True)  # Permitir redimensionar é melhor com lista dinâmica
        try:
            self.root.iconbitmap(resource_path("icone.ico"))
        except Exception as e:
            print(f"Could not load icon: {e}")
        self.root.attributes('-toolwindow', True)
        self.always_on_top = True
        self.resizable = True  # Ativado por padrão
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
        self.app_times = {}  # Novo: tempo individual de cada app
        
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
            from PIL import Image
            icon_pil_image = Image.open(resource_path("icone.ico"))
            self.icon_ctk_image = ctk.CTkImage(light_image=icon_pil_image, dark_image=icon_pil_image, size=(25, 25))
            icon_label = ctk.CTkLabel(self.title_bar, image=self.icon_ctk_image, text="", fg_color="#181e29")
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
                writer.writerow(["DATE", "TIME", "APP", "DURATION"])

    def load_settings(self):
        """Carrega configurações de um arquivo JSON."""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                    self.shortcuts.update(settings.get("shortcuts", {}))
                    self.always_on_top = settings.get("always_on_top", True)
                    self.resizable = settings.get("resizable", True) # Padrão para True
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

        # --- Seção de seleção de apps ---
        # Wrapper frame para garantir altura fixa da área rolável
        app_selector_wrapper = ctk.CTkFrame(self.page_main, fg_color="transparent", height=90)
        app_selector_wrapper.pack(fill="x", expand=False, padx=0, pady=0)
        app_selector_wrapper.pack_propagate(False) # Crucial: impede que o wrapper se redimensione para caber os filhos

        self.app_selector_container = ctk.CTkScrollableFrame(app_selector_wrapper, label_text="", fg_color="transparent")
        self.app_selector_container.pack(fill="both", expand=True) # Preenche o wrapper

        self.app_combos = []
        self.add_app_slot() # Adiciona o primeiro slot

        # Botão para adicionar mais apps
        add_app_button = ctk.CTkButton(self.page_main, text=t("add_app"), command=self.add_app_slot, width=130)
        add_app_button.pack(pady=(5, 10))
        # --- Fim da seção de seleção de apps ---

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

        # Página 2: Configurações
        self.page_history = ctk.CTkFrame(self.root, fg_color="#232B3B")
        self.page_settings = ctk.CTkFrame(self.root, fg_color="#232B3B")

        # --- Frame Rolável para Configurações ---
        settings_scroll_frame = ctk.CTkScrollableFrame(self.page_settings, fg_color="transparent", label_text="")
        settings_scroll_frame.pack(fill="both", expand=True, padx=10, pady=(32, 0))

        ctk.CTkLabel(settings_scroll_frame, text=t("settings"), font=("Arial", 20, "bold"), text_color="#22D3EE").pack(pady=(10, 10))

        # Combobox de idioma
        self.language_var = ctk.StringVar(value=self.language)
        lang_frame = ctk.CTkFrame(settings_scroll_frame, fg_color="#232B3B")
        lang_frame.pack(pady=5, padx=20, fill="x")
        ctk.CTkLabel(lang_frame, text=t("language"), text_color="#A1A7B3").pack(side="left", padx=5)
        self.language_combo = ctk.CTkComboBox(
            lang_frame,
            values=[LANGUAGES[k] for k in LANGUAGES],
            width=160,
            variable=self.language_var,
            command=self.on_language_change
        )
        self.language_combo.pack(side="left", padx=5)
        # Seleciona o idioma correto
        self.language_combo.set(LANGUAGES.get(self.language, "English"))

        close_to_tray_check = ctk.CTkCheckBox(
            settings_scroll_frame,
            text=t("minimize_to_tray"),
            variable=self.close_to_tray_var,
            fg_color="#323B4C",
            text_color="#A1A7B3"
        )
        close_to_tray_check.pack(pady=10, padx=20, anchor="w")
        
        # Novo: Checkbox para modo compacto automático
        auto_compact_check = ctk.CTkCheckBox(
            settings_scroll_frame,
            text=t("auto_compact"),
            variable=self.auto_compact_mode_var,
            fg_color="#323B4C",
            text_color="#A1A7B3"
        )
        auto_compact_check.pack(pady=10, padx=20, anchor="w")

        # Always On Top
        always_on_top_var = ctk.BooleanVar(value=self.always_on_top)
        always_on_top_check = ctk.CTkCheckBox(
            settings_scroll_frame,
            text=t("always_on_top"),
            variable=always_on_top_var,
            command=lambda: self.toggle_always_on_top(always_on_top_var.get()),
            fg_color="#323B4C", text_color="#A1A7B3"
        )
        always_on_top_check.pack(pady=10, padx=20, anchor="w")

        # Resizable
        resizable_var = ctk.BooleanVar(value=self.resizable)
        resizable_check = ctk.CTkCheckBox(
            settings_scroll_frame,
            text=t("allow_resizing"),
            variable=resizable_var,
            command=lambda: self.toggle_resizable(resizable_var.get()),
            fg_color="#323B4C", text_color="#A1A7B3"
        )
        resizable_check.pack(pady=10, padx=20, anchor="w")

        # Idle Threshold
        idle_frame = ctk.CTkFrame(settings_scroll_frame, fg_color="#232B3B")
        idle_frame.pack(pady=10, padx=20, fill="x")
        ctk.CTkLabel(idle_frame, text=t("idle_threshold"), text_color="#A1A7B3").pack(side="left", padx=5)
        ctk.CTkEntry(idle_frame, textvariable=self.idle_threshold_var, width=100, fg_color="#323B4C", text_color="#FFFFFF").pack(side="left", padx=5)

        # Check Interval
        interval_frame = ctk.CTkFrame(settings_scroll_frame, fg_color="#232B3B")
        interval_frame.pack(pady=10, padx=20, fill="x")
        ctk.CTkLabel(interval_frame, text=t("check_interval"), text_color="#A1A7B3").pack(side="left", padx=5)
        ctk.CTkEntry(interval_frame, textvariable=self.check_interval_var, width=100, fg_color="#323B4C", text_color="#FFFFFF").pack(side="left", padx=5)

        # Atalhos
        shortcuts_frame = ctk.CTkFrame(settings_scroll_frame, fg_color="#232B3B")
        shortcuts_frame.pack(pady=10, padx=20, fill="x")
        ctk.CTkLabel(shortcuts_frame, text=t("customize_shortcuts"), font=("Arial", 14, "bold"), text_color="#22D3EE").grid(row=0, column=0, columnspan=2, pady=(5, 10))
        shortcut_labels = [t("start_timer"), t("stop_timer"), t("reset_timer"), t("toggle_compact")]
        shortcut_vars = [self.start_shortcut_var, self.stop_shortcut_var, self.reset_shortcut_var, self.compact_shortcut_var]
        for i, label_text in enumerate(shortcut_labels):
            ctk.CTkLabel(shortcuts_frame, text=f"{label_text}:", text_color="#A1A7B3").grid(row=i+1, column=0, padx=10, pady=5, sticky="w")
            entry = ctk.CTkEntry(shortcuts_frame, textvariable=shortcut_vars[i], fg_color="#323B4C", text_color="#FFFFFF")
            entry.grid(row=i+1, column=1, padx=10, pady=5, sticky="ew")
        shortcuts_frame.grid_columnconfigure(1, weight=1)

        # Botões de ação da página de configurações
        settings_btn_frame = ctk.CTkFrame(settings_scroll_frame, fg_color="#232B3B")
        settings_btn_frame.pack(pady=20, padx=20, fill="x")
        ctk.CTkButton(settings_btn_frame, text=t("save_settings"), fg_color="#22D3EE", text_color="#181E29", hover_color="#06B6D4", command=self.save_settings).pack(side="right", padx=5)
        ctk.CTkButton(settings_btn_frame, text=t("back"), fg_color="#6B7280", text_color="#FFFFFF", hover_color="#374151", command=self.show_main_page).pack(side="right", padx=5)

        # Dicas para o usuário (Settings)
        tips_frame = ctk.CTkFrame(settings_scroll_frame, fg_color="#232B3B")
        tips_frame.pack(pady=(0, 10), padx=20, fill="x")
        ctk.CTkLabel(tips_frame, text=t("tip_title"), font=("Arial", 13, "bold"), text_color="#22D3EE").pack(anchor="w", pady=(0, 2))
        ctk.CTkLabel(tips_frame, text=t("tip_select_before"), font=("Arial", 11), text_color="#A1A7B3", wraplength=380, justify="left").pack(anchor="w", pady=(0, 2))
        ctk.CTkLabel(tips_frame, text=t("tip_blank_for_all"), font=("Arial", 11), text_color="#A1A7B3", wraplength=380, justify="left").pack(anchor="w")

        self.create_history_section(self.page_history)

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

    def create_history_section(self, parent_frame):
        history_frame = ctk.CTkFrame(parent_frame, corner_radius=10, fg_color="#232B3B")
        history_frame.pack(fill="both", expand=True, padx=10, pady=(32, 10))

        # --- Relatórios de uso diário, semanal e mensal + Filtros lado a lado ---
        top_frame = ctk.CTkFrame(history_frame, fg_color="#232b3b")
        top_frame.pack(fill="x", padx=5, pady=(10, 0))
        # Relatórios (lado esquerdo)
        self.usage_report_frame = ctk.CTkFrame(top_frame, fg_color="#232b3b")
        self.usage_report_frame.pack(side="left", fill="x", expand=True)
        self.usage_report_labels = []
        for _ in range(3):
            frame = ctk.CTkFrame(self.usage_report_frame, fg_color="#232b3b")
            frame.pack(fill="x", anchor="w")
            text_lbl = ctk.CTkLabel(frame, text="", font=("Arial", 10), text_color="#6b7280", anchor="w")
            text_lbl.pack(side="left")
            time_lbl = ctk.CTkLabel(frame, text="", font=("Arial", 10, "bold"), text_color="#22D3EE", anchor="w")
            time_lbl.pack(side="left", padx=(5,0))
            self.usage_report_labels.append((text_lbl, time_lbl))
        # Filtros (lado direito, campos alinhados na horizontal)
        filter_frame = ctk.CTkFrame(top_frame, fg_color="#232b3b")
        filter_frame.pack(side="right", padx=(10,0), pady=0)
        self.show_full_var = ctk.BooleanVar(value=self.show_full_history)
        ctk.CTkCheckBox(filter_frame, text=t("show_full_history"), variable=self.show_full_var,
                        command=self.toggle_history_display).pack(anchor="w", pady=2)
        # Linha: Filter by date | [campo] | [apply]
        date_row = ctk.CTkFrame(filter_frame, fg_color="#232b3b")
        date_row.pack(anchor="w", pady=2)
        ctk.CTkLabel(date_row, text=t("Date:")).pack(side="left", padx=(0,2))
        self.date_filter_var = ctk.StringVar()
        self.date_filter_entry = ctk.CTkEntry(date_row, width=100, textvariable=self.date_filter_var)
        self.date_filter_entry.pack(side="left", padx=(0,2))
        ctk.CTkButton(date_row, text=t("apply"), command=self.apply_date_filter, width=60).pack(side="left", padx=(0,0))
        # Linha: App: | [campo] | [Buscar]
        app_row = ctk.CTkFrame(filter_frame, fg_color="#232b3b")
        app_row.pack(anchor="w", pady=2)
        ctk.CTkLabel(app_row, text="App: ").pack(side="left", padx=(0,2))
        self.app_filter_var = ctk.StringVar()
        self.app_filter_entry = ctk.CTkEntry(app_row, width=100, textvariable=self.app_filter_var)
        self.app_filter_entry.pack(side="left", padx=(0,2))
        ctk.CTkButton(app_row, text=t("search"), command=self.apply_app_filter, width=60).pack(side="left", padx=(0,0))
        # --- Frame do Título e Botão Voltar ---
        # Frame do botão voltar, sem espaço extra
        title_bar_frame = ctk.CTkFrame(history_frame, fg_color="transparent")
        title_bar_frame.pack(fill="x", pady=(0, 0), padx=5)
        back_button = ctk.CTkButton(
            title_bar_frame,
            text=f"‹ {t('back')}",
            width=80,
            command=self.show_main_page,
            fg_color="#6B7280",
            hover_color="#374151"
        )
        back_button.pack(side="left", padx=0, pady=0)

        # Filtros movidos para o topo ao lado dos relatórios

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
        return [t("choose_app")] + [title for title in gw.getAllTitles() if title.strip()]

    def add_app_slot(self):
        """Adiciona uma nova linha para selecionar um aplicativo."""
        slot_frame = ctk.CTkFrame(self.app_selector_container, fg_color="transparent")
        
        combo = ctk.CTkComboBox(
            slot_frame,
            values=self.get_window_titles()
        )
        combo.pack(side="left", fill="x", expand=True, padx=(0, 5))
        combo.set(t('choose_app'))
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
        """Remove uma linha de seleção de aplicativo."""
        if len(self.app_combos) > 1:
            self.app_combos.remove(combo_to_remove)
            slot_frame.destroy()
        else:
            messagebox.showwarning(t("warning"), t("at_least_one_app"))

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
            # Novo: zera o tempo individual de cada app
            self.app_times = {app: 0.0 for app in self.target_windows}
            threading.Thread(target=self.track_time, daemon=True).start()

    def stop_tracking(self):
        """Para o tracking e salva a sessão"""
        if self.running:
            self.running = False
            self.start_btn.configure(fg_color="#22D3EE", text=t("start"))
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
            # Novo: identifica qual app está ativo
            app_found = None
            if current_window:
                for app in self.target_windows:
                    if app in current_window:
                        app_found = app
                        break
            if user_active and app_found:
                if not self.tracking_active:
                    self.tracking_active = True
                    self.timer_label.configure(text_color="#1ABC9C")
                    if hasattr(self, 'compact_timer_label'):
                        self.compact_timer_label.configure(text_color="#1ABC9C")
                    if not hasattr(self, '_compact_mode') or not self._compact_mode:
                        self.root.after(0, self.toggle_compact_mode)
                # Novo: incrementa só o app ativo
                self.app_times[app_found] += (self.check_interval / 60.0)
                self.elapsed_time = sum(self.app_times.values())
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
        # Novo: salva uma linha por app
        with open(resource_path(self.filename), mode="a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            for app, minutes in self.app_times.items():
                duration = self.format_duration(minutes)
                writer.writerow([date_str, time_str, app, duration])
                self.add_history_entry(date_str, time_str, app, duration)
        self.elapsed_time = 0
        self.update_timer_display()
        self.app_times = {}

    def format_duration(self, elapsed_minutes):
        """Formata a duração para HH:MM:SS"""
        total_seconds = int(elapsed_minutes * 60)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def load_history(self):
        self.clear_history_content()
        self.update_usage_reports(self.app_filter_var.get() if hasattr(self, 'app_filter_var') else None)
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

    def update_usage_reports(self, app_query=None):
        """Atualiza os relatórios de tempo de uso diário, semanal e mensal para o app filtrado (ou todos)."""
        import calendar
        from datetime import timedelta
        if not os.path.exists(resource_path(self.filename)):
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
        with open(resource_path(self.filename), mode="r", encoding="utf-8") as file:
            reader = csv.reader(file)
            next(reader)
            for row in reader:
                if len(row) < 4:
                    continue
                row_date = None
                try:
                    row_date = datetime.strptime(row[0], "%d/%m/%Y").date()
                except Exception:
                    continue
                app_name = row[2].lower()
                if app_query and app_query not in app_name:
                    continue
                try:
                    h, m, s = map(int, str(row[3]).split(':'))
                    minutes = h*60 + m + s/60
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
            s = int((mins*60) % 60)
            return f"{h:02d}:{m:02d}:{s:02d}"
        # Textos dos relatórios
        report_texts = [
            "⌚ Usage time today:",
            "⌛ Usage time week:",
            "📅 Usage time month:"
        ]
        times = [fmt(total_day), fmt(total_week), fmt(total_month)]
        for i, (text_lbl, time_lbl) in enumerate(self.usage_report_labels):
            text_lbl.configure(text=report_texts[i], font=("Arial", 10), text_color="#6b7280")
            time_lbl.configure(text=times[i], font=("Arial", 10, "bold"), text_color="#22D3EE")

    def apply_app_filter(self):
        """Filtra o histórico pelo nome do app (parcial ou completo) e atualiza relatórios."""
        app_query = self.app_filter_var.get().strip().lower()
        self.clear_history_content()
        self.update_usage_reports(app_query)
        if not app_query:
            self.load_history()
            return
        if os.path.exists(resource_path(self.filename)):
            with open(resource_path(self.filename), mode="r", encoding="utf-8") as file:
                reader = csv.reader(file)
                next(reader)
                for row in reader:
                    if len(row) >= 4 and app_query in row[2].lower():
                        self.add_history_entry(row[0], row[1], row[2], row[3])

    def clear_history_content(self):
        """Limpa o conteúdo do histórico"""
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
            if hasattr(self, 'title_bar'): # Garante que title_bar exista antes de tentar posicionar
                self.root.geometry("425x500") # Retorna à altura inicial fixa
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
                messagebox.showerror(t("invalid_shortcut"), t("invalid_shortcut_format", key=key))
                return

        # Validar idle_threshold
        try:
            idle_threshold = float(self.idle_threshold_var.get())
            if idle_threshold <= 0:
                raise ValueError(t("invalid_idle_threshold_msg"))
            self.idle_threshold = idle_threshold
        except (ValueError, TypeError):
            messagebox.showerror(t("invalid_idle_threshold"), t("invalid_idle_threshold_msg"))
            return

        # Validar check_interval
        try:
            check_interval = float(self.check_interval_var.get())
            if check_interval <= 0:
                raise ValueError(t("invalid_check_interval_msg"))
            self.check_interval = check_interval
        except (ValueError, ValueError):
            messagebox.showerror(t("invalid_check_interval"), t("invalid_check_interval_msg"))
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

            self.compact_frame.bind ("<Button-1>", start_move)
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
            self.page_main.pack(fill="both", expand=True, pady=(32, 0))
            self.root.geometry("425x500") # Retorna à altura original
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
        """Cria e exibe o dashboard de estatísticas com barra de rolagem, gráfico de pizza e filtro por app."""
        for widget in self.page_stats.winfo_children():
            widget.destroy()

        # Frame rolável
        scroll_frame = ctk.CTkScrollableFrame(self.page_stats, fg_color="transparent", label_text="")
        scroll_frame.pack(fill="both", expand=True, padx=0, pady=0)

        # Novo: Frame para título e botão voltar
        title_stats_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        title_stats_frame.pack(fill="x", pady=(35, 10), padx=0)
        back_btn = ctk.CTkButton(
            title_stats_frame,
            text=f"‹ {t('back')}",
            width=80,
            fg_color="#6b7280",
            hover_color="#374151",
            text_color="#FFFFFF",
            font=("Arial", 12, "bold"),
            command=self.show_main_page
        )
        back_btn.pack(side="left", padx=(0, 0), pady=0)
        # Label "Statistics" alinhado à esquerda, após o botão, com padding
        ctk.CTkLabel(title_stats_frame, text=t("statistics"), font=("Arial", 18, "bold"), text_color="#22d3ee").pack(side="left", padx=(90,0))


        # Variável para filtro múltiplo
        import tkinter as tk
        self.stats_app_filter_var = getattr(self, 'stats_app_filter_var', None)
        self.stats_app_filter_selected = getattr(self, 'stats_app_filter_selected', [])

        try:
            if not os.path.exists(resource_path(self.filename)) or os.path.getsize(resource_path(self.filename)) < 20:
                ctk.CTkLabel(scroll_frame, text=t("no_history")).pack(pady=20)
                ctk.CTkButton(scroll_frame, text=t("back"), command=self.show_main_page).pack(pady=10)
                return

            df = pd.read_csv(resource_path(self.filename), header=0, engine='python')
            if df.empty:
                ctk.CTkLabel(scroll_frame, text=t("no_history")).pack(pady=20)
                ctk.CTkButton(scroll_frame, text=t("back"), command=self.show_main_page).pack(pady=10)
                return

            def duration_to_minutes(duration_str):
                try:
                    h, m, s = map(int, str(duration_str).split(':'))
                    return (h * 60) + m + (s / 60)
                except (ValueError, AttributeError):
                    return 0

            df['MINUTES'] = df['DURATION'].apply(duration_to_minutes)
            df['DATE'] = pd.to_datetime(df['DATE'], format='%d/%m/%Y')


            # Listbox de filtro múltiplo de apps
            app_list = sorted(df['APP'].unique())

            # Frame com borda arredondada para filtro e Listbox
            filter_frame = ctk.CTkFrame(scroll_frame, corner_radius=5, fg_color="#323b4c")
            filter_frame.pack(fill="x", padx=20, pady=(0, 10), anchor="w")

            # Label acima do Listbox
            ctk.CTkLabel(filter_frame, text=t("total_time_by_app"), font=("Arial", 12, "bold"), text_color="white", fg_color="transparent").pack(side="top", anchor="w", padx=(5, 0), pady=(5, 0))

            # Listbox nativo do tkinter para múltipla seleção, com customização de cores
            listbox_frame = tk.Frame(filter_frame, bg="#323b4c")
            listbox_frame.pack(side="top", anchor="w", pady=(5, 5), padx=(5, 0))
            # Calcula largura dinâmica para Listbox (aproximação)
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
                # Seleciona apps previamente filtrados
                if app in self.stats_app_filter_selected:
                    app_listbox.selection_set(idx)
            app_listbox.pack(side="left", fill="x", expand=True)

            def apply_multi_app_filter():
                self.stats_app_filter_selected = [app_list[int(i)] for i in app_listbox.curselection()]
                self.update_stats_dashboard()

            apply_btn = ctk.CTkButton(filter_frame, text=t("apply"), width=60, command=apply_multi_app_filter)
            apply_btn.pack(side="left", padx=(10,0))

            # Filtrar DataFrame se apps selecionados
            selected_apps = self.stats_app_filter_selected
            if selected_apps:
                df = df[df['APP'].isin(selected_apps)]

            app_usage = df.groupby('APP')['MINUTES'].sum().sort_values(ascending=True)
            daily_avg = df.groupby(df['DATE'].dt.date)['MINUTES'].sum().mean()
            total_time = app_usage.to_dict()

            # Exibir estatísticas textuais
            stats_frame = ctk.CTkFrame(scroll_frame)
            stats_frame.pack(fill="x", padx=20, pady=10)
            # Formatar média diária para HH:MM:SS
            if pd.notnull(daily_avg):
                total_seconds = int(daily_avg * 60)
                h = total_seconds // 3600
                m = (total_seconds % 3600) // 60
                s = total_seconds % 60
                daily_avg_str = f"{h:02d}:{m:02d}:{s:02d}"
            else:
                daily_avg_str = "00:00:00"
            ctk.CTkLabel(stats_frame, text=t("daily_average", minutes=daily_avg_str), font=("Arial", 12)).pack(anchor="w", pady=5)
            # Lista de apps e tempos
            for app, minutes in total_time.items():
                ctk.CTkLabel(stats_frame, text=f"{app}: {minutes:.1f} minutes", font=("Arial", 12)).pack(anchor="w", padx=20)


            plt.style.use('dark_background')
            plt.rcParams.update({'font.size': 11})
            # Pie chart em primeiro, depois Line chart
            fig, axs = plt.subplots(2, 1, figsize=(10, 8), dpi=100, facecolor='#232b3b', gridspec_kw={'height_ratios': [1, 1]})
            ax1, ax2 = axs

            # Pie Chart (primeiro)
            if len(app_usage) > 0 and app_usage.sum() > 0:
                colors = plt.cm.Set3.colors if len(app_usage) <= 12 else None
                ax1.pie(app_usage, labels=app_usage.index, autopct='%1.1f%%', startangle=140, colors=colors, textprops={'color': 'white', 'fontsize': 11})
                ax1.set_title(t("pie_chart_title") if 'pie_chart_title' in TRANSLATIONS.get(TimeTrackerApp.current_language, {}) else "Usage Distribution (Pie)", color='white', fontsize=11)
                ax1.set_facecolor('#232b3b')
            else:
                ax1.axis('off')

            # Line Chart (segundo)
            for app in df['APP'].unique():
                app_data = df[df['APP'] == app]['MINUTES']
                ax2.plot(app_data.index, app_data.values, label=app)
            ax2.set_title(t("app_usage_over_time"), color='white', fontsize=11)
            ax2.set_xlabel('Date', color='white', fontsize=11)
            ax2.set_ylabel('Minutes', color='white', fontsize=11)
            ax2.tick_params(colors='white', labelsize=11, rotation=45)
            ax2.legend(loc='upper left', facecolor='#232b3b', edgecolor='white', labelcolor='white', fontsize=11)
            ax2.set_facecolor('#232b3b')

            fig.tight_layout(pad=2.0)
            canvas = FigureCanvasTkAgg(fig, master=scroll_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)

        except Exception as e:
            ctk.CTkLabel(scroll_frame, text=f"{t('error')} {e}").pack(pady=20)

        # Botão back removido do final da página (agora está no topo ao lado do título)

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
        elif hasattr(self, 'page_history') and self.page_history.winfo_ismapped():
            visible_page = 'history'
        # Destroi todos os frames principais
        for attr in ['page_main', 'page_settings', 'page_stats', 'page_history', 'nav_frame']:
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
        elif visible_page == 'history':
            self.show_history()

if __name__ == "__main__":
    root = ctk.CTk()
    app = TimeTrackerApp(root)
    root.mainloop()
