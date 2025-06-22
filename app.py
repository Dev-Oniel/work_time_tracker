import tkinter as tk
from tkinter import ttk, messagebox
from ttkthemes import ThemedTk
import threading
import time
import psutil
import pygetwindow as gw
from pynput import mouse, keyboard as kb
import keyboard
import json
import os
from pystray import Icon, Menu as SysMenu, MenuItem as SysMenuItem
from PIL import Image, ImageDraw

# ------------------------------
# Configurações Globais
# ------------------------------
INATIVIDADE_TEMPO = 10
COMPACT_SIZE = (180, 40)
NORMAL_SIZE = (520, 320)
SAVE_FILE = "tempo_uso.json"

# ------------------------------
# Classe Principal
# ------------------------------
class AppTimer:
    def __init__(self, root):
        self.root = root
        self.root.title("Work Time Tracker")
        self.root.geometry(f"{NORMAL_SIZE[0]}x{NORMAL_SIZE[1]}")
        self.root.resizable(False, False)
        self.root.configure(bg='#222222')
        self.root.attributes('-topmost', True)

        self.app_name = None
        self.timer_running = False
        self.compact_mode = False

        self.seconds = 0
        self.last_activity_time = time.time()

        self.tray_icon = None
        self.menu_bar = None

        self.load_time()

        self.create_menu_bar()
        self.create_context_menu()
        self.create_widgets()
        self.setup_listeners()
        self.update_timer_display()

        self.monitor_thread = threading.Thread(target=self.monitor, daemon=True)
        self.monitor_thread.start()

    # --------------------------
    # Interface
    # --------------------------
    def create_widgets(self):
        self.timer_label = ttk.Label(self.root, text="00:00:00", font=("Segoe UI", 48), foreground="red", background='#222222')
        self.timer_label.pack(pady=10)

        self.app_label = ttk.Label(self.root, text="Nenhum aplicativo selecionado", font=("Segoe UI", 11), background='#222222', foreground='white')
        self.app_label.pack(pady=5)

        self.frame = ttk.Frame(self.root)
        self.frame.pack(pady=5)

        ttk.Button(self.frame, text="Iniciar", command=self.start_timer).grid(row=0, column=0, padx=5, pady=5)
        ttk.Button(self.frame, text="Parar", command=self.stop_timer).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(self.frame, text="Resetar", command=self.reset_timer).grid(row=0, column=2, padx=5, pady=5)

        self.root.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)
        self.root.attributes('-toolwindow', True)
        self.root.bind("<Button-3>", self.show_context_menu)

    def create_menu_bar(self):
        self.menu_bar = tk.Menu(self.root, bg='#333333', fg='white')

        app_menu = tk.Menu(self.menu_bar, tearoff=0, bg='#333333', fg='white')
        app_menu.add_command(label="Selecionar App", command=self.select_app)
        app_menu.add_command(label="Atalhos", command=self.show_shortcuts)
        app_menu.add_separator()
        self.always_on_top = tk.BooleanVar(value=True)
        app_menu.add_checkbutton(label="Sempre Visível", onvalue=True, offvalue=False, variable=self.always_on_top, command=self.toggle_always_on_top)
        app_menu.add_command(label="Modo Compacto", command=self.toggle_compact_mode)

        self.menu_bar.add_cascade(label="Menu", menu=app_menu)
        self.root.config(menu=self.menu_bar)

    def create_context_menu(self):
        self.context_menu = tk.Menu(self.root, tearoff=0, bg='#333333', fg='white')
        self.context_menu.add_command(label="Iniciar", command=self.start_timer)
        self.context_menu.add_command(label="Parar", command=self.stop_timer)
        self.context_menu.add_command(label="Resetar", command=self.reset_timer)
        self.context_menu.add_separator()
        self.context_menu.add_checkbutton(label="Sempre Visível", onvalue=True, offvalue=False, variable=self.always_on_top, command=self.toggle_always_on_top)
        self.context_menu.add_command(label="Modo Compacto", command=self.toggle_compact_mode)
        self.compact_menu_index = self.context_menu.index("end")

    def show_context_menu(self, event):
        self.context_menu.tk_popup(event.x_root, event.y_root)

    # --------------------------
    # System Tray
    # --------------------------
    def minimize_to_tray(self):
        self.root.withdraw()
        image = Image.new('RGB', (64, 64), color='#222222')
        d = ImageDraw.Draw(image)
        d.rectangle((16, 16, 48, 48), fill='cyan')
        menu = SysMenu(
            SysMenuItem('Mostrar', self.restore_window),
            SysMenuItem('Sair', self.on_close)
        )
        self.tray_icon = Icon("Work Time Tracker", image, "Work Time Tracker", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def restore_window(self, icon=None, item=None):
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.after(0, self.root.deiconify)

    # --------------------------
    # Atalhos
    # --------------------------
    def show_shortcuts(self):
        win = tk.Toplevel(self.root)
        win.title("Atalhos")
        win.geometry("350x200")
        win.configure(bg='#222222')

        shortcuts = [
            ("Iniciar", "Ctrl + Alt + E"),
            ("Parar", "Ctrl + Alt + D"),
            ("Resetar", "Ctrl + Alt + R"),
            ("Modo Compacto", "Ctrl + Alt + C")
        ]

        for idx, (action, keys) in enumerate(shortcuts):
            tk.Label(win, text=action, bg='#222222', fg='white', font=("Segoe UI", 10)).grid(row=idx, column=0, padx=10, pady=5, sticky='w')
            tk.Label(win, text=keys, bg='#222222', fg='cyan', font=("Segoe UI", 10, 'bold')).grid(row=idx, column=1, padx=10, pady=5, sticky='e')

    # --------------------------
    # Selecionar Aplicativo
    # --------------------------
    def select_app(self):
        windows = gw.getAllTitles()
        windows = [w for w in windows if w.strip()]

        if not windows:
            messagebox.showerror("Erro", "Nenhuma janela encontrada.")
            return

        win = tk.Toplevel(self.root)
        win.title("Selecionar App")
        win.geometry("300x400")
        win.configure(bg='#222222')

        lb = tk.Listbox(win, bg='#333333', fg='white')
        lb.pack(fill=tk.BOTH, expand=True)
        for w in windows:
            lb.insert(tk.END, w)

        def select():
            self.app_name = lb.get(lb.curselection())
            self.app_label.config(text=f"App Selecionado: {self.app_name}")
            win.destroy()

        ttk.Button(win, text="Selecionar", command=select).pack(pady=5)

    # --------------------------
    # Controle do Timer
    # --------------------------
    def start_timer(self):
        self.timer_running = True
        self.update_timer_color()

    def stop_timer(self):
        self.timer_running = False
        self.update_timer_color()

    def reset_timer(self):
        self.seconds = 0
        self.update_timer_display()
        self.update_timer_color()

    def update_timer_display(self):
        h = self.seconds // 3600
        m = (self.seconds % 3600) // 60
        s = self.seconds % 60
        self.timer_label.config(text=f"{h:02}:{m:02}:{s:02}")

    def update_timer_color(self):
        if self.timer_running:
            self.timer_label.config(foreground="green")
        else:
            self.timer_label.config(foreground="red")

    def toggle_always_on_top(self):
        self.root.attributes('-topmost', self.always_on_top.get())

    def toggle_compact_mode(self):
        self.compact_mode = not self.compact_mode
        if self.compact_mode:
            self.root.geometry(f"{COMPACT_SIZE[0]}x{COMPACT_SIZE[1]}")
            self.timer_label.pack_configure(pady=0)
            self.timer_label.config(font=("Segoe UI", 20))
            self.app_label.pack_forget()
            self.frame.pack_forget()
            self.root.config(menu="")
            self.context_menu.entryconfig(self.compact_menu_index, label="Expandir")
        else:
            self.root.geometry(f"{NORMAL_SIZE[0]}x{NORMAL_SIZE[1]}")
            self.timer_label.config(font=("Segoe UI", 48))
            self.timer_label.pack_configure(pady=10)
            self.app_label.pack(pady=5)
            self.frame.pack(pady=5)
            self.root.config(menu=self.menu_bar)
            self.context_menu.entryconfig(self.compact_menu_index, label="Modo Compacto")

    # --------------------------
    # Monitoramento
    # --------------------------
    def monitor(self):
        while True:
            active = gw.getActiveWindow()
            active_title = active.title if active else ""

            is_app_active = (self.app_name == active_title)
            is_user_active = (time.time() - self.last_activity_time) < INATIVIDADE_TEMPO

            if self.timer_running and is_app_active and is_user_active:
                self.seconds += 1
                self.update_timer_display()
                self.timer_label.config(foreground="green")
            else:
                self.timer_label.config(foreground="red")

            time.sleep(1)

    # --------------------------
    # Detecção de Inatividade
    # --------------------------
    def setup_listeners(self):
        mouse.Listener(on_move=self.on_activity, on_click=self.on_activity, on_scroll=self.on_activity).start()
        kb.Listener(on_press=self.on_activity).start()

        keyboard.add_hotkey('ctrl+alt+e', lambda: self.root.after(0, self.start_timer))
        keyboard.add_hotkey('ctrl+alt+d', lambda: self.root.after(0, self.stop_timer))
        keyboard.add_hotkey('ctrl+alt+r', lambda: self.root.after(0, self.reset_timer))
        keyboard.add_hotkey('ctrl+alt+c', lambda: self.root.after(0, self.toggle_compact_mode))

    def on_activity(self, *args):
        self.last_activity_time = time.time()

    def on_close(self, icon=None, item=None):
        self.save_time()
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.destroy()

    def save_time(self):
        data = {"app_name": self.app_name, "seconds": self.seconds}
        with open(SAVE_FILE, 'w') as f:
            json.dump(data, f)

    def load_time(self):
        if os.path.exists(SAVE_FILE):
            with open(SAVE_FILE, 'r') as f:
                data = json.load(f)
                if data.get("app_name") == self.app_name or data.get("app_name") is None:
                    self.seconds = data.get("seconds", 0)

# ------------------------------
# Inicialização
# ------------------------------
if __name__ == '__main__':
    root = ThemedTk(theme="black")
    app = AppTimer(root)
    root.mainloop()
