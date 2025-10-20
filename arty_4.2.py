import tkinter as tk
from tkinter import ttk
import threading
import time
from pynput import mouse, keyboard
import pydirectinput
import sys, os

def resource_path(rel_path: str) -> str:
    """Повертає шлях до ресурсу і для .py, і для зібраного .exe (PyInstaller)."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        base = sys._MEIPASS  # тимчасова папка, куди PyInstaller розпаковує дані
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, rel_path)
# ===== Кольорова схема інтерфейсу =====
BG_MAIN   = "#1b4670"
PANEL_BG  = "#245b86"
BORDER_BG = "#163954"
TEXT_MAIN = "#e6edf3"
TEXT_MUT  = "#c7d3df"

ROLE_BG   = "#3a6ea5"   # кнопки «Арта»
ROLE_HOV  = "#3f74ad"
ROLE_SEL  = "#5b95c2"

LOGI_BG   = "#5a87a7"   # кнопки «Логістика»
LOGI_HOV  = "#6393b4"
LOGI_SEL  = "#7aa8c4"

START_BG  = "#3a6ea5"; START_HOV = "#3f74ad"
STOP_BG   = "#214e76";  STOP_HOV  = "#275a88"

# ===== Файли з емблемами/іконками =====
ICON_EMBLEM_PATH = resource_path("UDC.png")
ICON_ARTA_PATH   = resource_path("Arta.png")
ICON_ZAVOD_PATH  = resource_path("Zavod.png")

# ===== Глобальні стани =====
running = False
mode = None
recording = False
recorded_events = []
start_time = None
start_seq = 0

has_macro = False
last_macro_record_time = None

mouse_controller = mouse.Controller()
keyboard_controller = keyboard.Controller()

MODE_UI = {}
_img_cache = {}   # щоб PhotoImage не збирався GC

# ===== ВАЖЛИВО для ігор: вимикаємо паузи/фейлсейф у pydirectinput =====
pydirectinput.PAUSE = 0
pydirectinput.FAILSAFE = False

# ===== Утиліти =====
def load_photo_image(path, size=None):
    try:
        img = tk.PhotoImage(file=path)
        if size:
            w, h = img.width(), img.height()
            sw = max(1, int(w / max(1, size[0])))
            sh = max(1, int(h / max(1, size[1])))
            img = img.subsample(sw, sh)
        return img
    except Exception:
        return None

def load_icon_fixed_height(path, target_h: int):
    try:
        img = tk.PhotoImage(file=path)
    except Exception:
        return None
    if target_h <= 0:
        return img
    h = img.height()
    if h == 0:
        return img
    if h > target_h:
        k = max(1, round(h / target_h))
        img = img.subsample(k)
    elif h < target_h:
        k = max(1, round(target_h / h))
        img = img.zoom(k)
    if img.height() > target_h:
        k = max(1, round(img.height() / target_h))
        img = img.subsample(k)
    return img

def make_style(root):
    root.configure(bg=BG_MAIN)
    style = ttk.Style()
    try: style.theme_use("clam")
    except: pass
    style.configure("BG.TFrame", background=BG_MAIN)
    style.configure("PanelBorder.TFrame", background=BORDER_BG)
    style.configure("Panel.TFrame", background=PANEL_BG)
    style.configure("Start.TButton",
                    background=START_BG, foreground=TEXT_MAIN,
                    font=("{Segoe UI}", 12, "bold"), padding=(14,10), borderwidth=2)
    style.map("Start.TButton", background=[("active", START_HOV)])
    style.configure("Stop.TButton",
                    background=STOP_BG, foreground=TEXT_MAIN,
                    font=("{Segoe UI}", 12, "bold"), padding=(14,10), borderwidth=2)
    style.map("Stop.TButton", background=[("active", STOP_HOV)])

def add_panel(master, title_text, hp: int = 8, draw_line: bool = True, top_pad: int = 8, title_icon=None):
    """
    Створити панель з заголовком (опційно з іконкою).
    hp — горизонтальні поля; draw_line — лінія під заголовком; top_pad — верхній внутр. відступ.
    """
    wrap = ttk.Frame(master, style="BG.TFrame")
    wrap.pack(fill="x", padx=hp, pady=(8,0))
    border = ttk.Frame(wrap, style="PanelBorder.TFrame"); border.pack(fill="x")
    panel = ttk.Frame(border, style="Panel.TFrame"); panel.pack(fill="x", padx=1, pady=1)

    if title_icon is not None:
        lbl = tk.Label(panel, text=title_text, image=title_icon, compound="left",
                       bg=PANEL_BG, fg=TEXT_MUT, anchor="w", padx=6)
        lbl.image = title_icon
        lbl.pack(anchor="w", padx=12, pady=(top_pad,4))
    else:
        tk.Label(panel, text=title_text, bg=PANEL_BG, fg=TEXT_MUT, anchor="w")\
            .pack(anchor="w", padx=12, pady=(top_pad,4))

    if draw_line:
        tk.Frame(panel, bg=BORDER_BG, height=1).pack(fill="x", padx=12, pady=(0,4))
    return panel

RIVET_ON  = "◆ "
RIVET_OFF = "  "

def make_mode_button(master, text, cmd, kind, mode_id):
    base_bg   = ROLE_BG if kind == "role" else LOGI_BG
    hover_bg  = ROLE_HOV if kind == "role" else LOGI_HOV
    active_bg = ROLE_SEL if kind == "role" else LOGI_SEL

    holder = tk.Frame(master, bg=PANEL_BG); holder.pack(fill="x", padx=12, pady=6)
    btn = tk.Button(holder, text=RIVET_OFF + text, command=cmd, relief="flat", bd=2,
                    bg=base_bg, fg=TEXT_MAIN, activebackground=hover_bg,
                    activeforeground=TEXT_MAIN, padx=10, pady=6, highlightthickness=0,
                    anchor="w")
    btn.pack(fill="x")

    def on_enter(_):
        if mode != mode_id: btn.configure(bg=hover_bg)
    def on_leave(_):
        if mode != mode_id: btn.configure(bg=base_bg)
    btn.bind("<Enter>", on_enter); btn.bind("<Leave>", on_leave)

    MODE_UI[mode_id] = {"btn": btn, "kind": kind, "base": base_bg,
                        "hover": hover_bg, "sel": active_bg, "text": text}
    return btn

def update_mode_highlight(selected_mode):
    for mid, info in MODE_UI.items():
        info["btn"].configure(bg=info["base"], text=RIVET_OFF + info["text"])
    if selected_mode in MODE_UI:
        info = MODE_UI[selected_mode]
        info["btn"].configure(bg=info["sel"], text=RIVET_ON + info["text"])

def make_button(master, text, cmd, style_name):
    holder = ttk.Frame(master, style="Panel.TFrame"); holder.pack(fill="x", padx=12, pady=6)
    btn = ttk.Button(holder, text=text, command=cmd, style=style_name); btn.pack(fill="x")
    return btn

# ===== Мапи Virtual-Key -> US key name (для ігор/DirectInput) =====
# Основні діапазони: A..Z (0x41..0x5A), 0..9 (0x30..0x39), модифікатори, стрілки, керуючі.
VK_TO_NAME = {
    # модифікатори
    0x10: "shift", 0x11: "ctrl", 0x12: "alt",
    # керуючі
    0x20: "space", 0x0D: "enter", 0x1B: "esc", 0x09: "tab", 0x08: "backspace", 0x2E: "delete",
    0x24: "home", 0x23: "end", 0x21: "pageup", 0x22: "pagedown", 0x2D: "insert",
    # стрілки
    0x26: "up", 0x28: "down", 0x25: "left", 0x27: "right",
    # F-клавіші
    0x70: "f1", 0x71: "f2", 0x72: "f3", 0x73: "f4", 0x74: "f5", 0x75: "f6",
    0x76: "f7", 0x77: "f8", 0x78: "f9", 0x79: "f10", 0x7A: "f11", 0x7B: "f12",
    # CapsLock
    0x14: "capslock",
}

def _vk_to_name(vk):
    # Цифри 0..9
    if 0x30 <= vk <= 0x39:
        return chr(vk)
    # Літери A..Z (вертаємо у нижньому регістрі)
    if 0x41 <= vk <= 0x5A:
        return chr(vk).lower()
    # Інші з мапи
    return VK_TO_NAME.get(vk)

# ===== Нормалізація клавіш для pydirectinput з урахуванням vk та name/char =====
def _normalize_key_for_directinput(key):
    """
    Перетворює pynput Key/KeyCode у (name, is_char, is_upper).
    1) Спочатку по VK (фізична клавіша US) — працює незалежно від розкладки.
    2) Потім по char/name (fallback).
    """
    # 1) Пробуємо VK
    vk = getattr(key, "vk", None)
    if isinstance(vk, int):
        name = _vk_to_name(vk)
        if name:
            # для A..Z з vk — це фізична літера; is_char=True; is_upper неважливий (гру ловить по фізичній)
            is_char = name.isalpha() or name.isdigit()
            return name, is_char, False

    # 2) Fallback: char / name
    try:
        if hasattr(key, "char") and key.char:
            ch = key.char
            return ch.lower(), True, ch.isupper()
    except Exception:
        pass

    try:
        name = getattr(key, "name", None)
        if not name:
            name = str(key).replace("Key.", "")
    except Exception:
        name = None

    if not name:
        return None, False, False

    # уніфікуємо модифікатори
    if name.startswith("shift"):
        return "shift", False, False
    if name.startswith("ctrl"):
        return "ctrl", False, False
    if name.startswith("alt"):
        return "alt", False, False

    # функціональні (на випадок, якщо vk не спрацював)
    if name.startswith("f") and name[1:].isdigit():
        return name, False, False

    mapping = {
        "space": "space", "enter": "enter", "esc": "esc", "tab": "tab",
        "backspace": "backspace", "delete": "delete",
        "up": "up", "down": "down", "left": "left", "right": "right",
        "caps_lock": "capslock", "home": "home", "end": "end",
        "page_up": "pageup", "page_down": "pagedown", "insert": "insert",
    }
    if name in mapping:
        return mapping[name], False, False
    return None, False, False

# ===== Режими =====
def autoclick_mode1():
    mouse_controller.press(mouse.Button.right)
    try:
        while running: time.sleep(0.1)
    finally:
        mouse_controller.release(mouse.Button.right)

def autoclick_mode2():
    while running:
        pydirectinput.keyDown('r'); time.sleep(0.05); pydirectinput.keyUp('r')
        _tiny_sleep()
        mouse_controller.click(mouse.Button.left)
        time.sleep(0.1)

def record_key_event(key, event_type):
    global recorded_events, start_time
    if recording:
        ts = time.time() - start_time
        recorded_events.append((key, event_type, ts))

def start_recording():
    global recording, recorded_events, start_time, has_macro, last_macro_record_time
    if not recording:
        recorded_events = []
        start_time = time.time()
        recording = True
        has_macro = False
        last_macro_record_time = None
        status_state_var.set("Працює")
        update_macro_status_ui()
        threading.Thread(target=record_keyboard_listener, daemon=True).start()
        threading.Thread(target=record_mouse_stop_listener, daemon=True).start()

def stop_recording_mouse(x=None, y=None, button=None, pressed=None):
    global recording, has_macro, last_macro_record_time
    if recording and pressed and button == mouse.Button.left:
        recording = False
        has_macro = len(recorded_events) > 0
        last_macro_record_time = time.time() if has_macro else None
        status_state_var.set("Зупинено")
        update_macro_status_ui()
        return False

def record_keyboard_listener():
    with keyboard.Listener(on_press=lambda k: record_key_event(k, 'press'),
                           on_release=lambda k: record_key_event(k, 'release')) as listener:
        while recording: time.sleep(0.01)
        listener.stop()

def record_mouse_stop_listener():
    with mouse.Listener(on_click=stop_recording_mouse) as listener:
        listener.join()

def _tiny_sleep():
    time.sleep(0.008)  # деяким іграм потрібен невеликий інтервал

# ===== Відтворення макро в грі (DirectInput, коректні модифікатори + VK) =====
def play_recording():
    """Відтворення записаного макросу клавіатури через pydirectinput із мапою VK -> US key."""
    if not recorded_events:
        return
    global running
    while running:
        start_play = time.time()
        held = set()       # зажаті клавіші (імена)
        held_mods = set()  # 'shift','ctrl','alt'

        for key, event_type, ts in recorded_events:
            if not running:
                break
            wait = (start_play + ts) - time.time()
            if wait > 0:
                time.sleep(wait)

            kname, is_char, is_upper = _normalize_key_for_directinput(key)
            if not kname:
                continue

            try:
                if event_type == "press":
                    if kname in ("shift", "ctrl", "alt"):
                        if kname not in held_mods:
                            pydirectinput.keyDown(kname); _tiny_sleep()
                            held_mods.add(kname); held.add(kname)
                        continue

                    # якщо символ і верхній регістр, а Shift ще не зажатий — тимчасово додамо
                    temp_shift = False
                    if is_char and is_upper and "shift" not in held_mods:
                        pydirectinput.keyDown("shift"); _tiny_sleep()
                        held_mods.add("shift")
                        temp_shift = True  # відпустимо на release цієї ж клавіші

                    if kname not in held:
                        pydirectinput.keyDown(kname); _tiny_sleep()
                        held.add(kname)

                    # якщо ми підняли тимчасовий шифт для цієї букви — відпустимо його вже на release
                    if temp_shift:
                        # помітку не зберігаємо — просто далі release зніме Shift або цикл в кінці
                        pass

                elif event_type == "release":
                    if kname in held:
                        pydirectinput.keyUp(kname); _tiny_sleep()
                        held.discard(kname)
                    if kname in ("shift", "ctrl", "alt") and kname in held_mods:
                        held_mods.discard(kname)

            except Exception:
                pass

        # в кінці прогону — відпускаємо все, що могло лишитись
        for k in list(held):
            try:
                pydirectinput.keyUp(k); _tiny_sleep()
            except Exception:
                pass
        held.clear()
        for m in list(held_mods):
            try:
                pydirectinput.keyUp(m); _tiny_sleep()
            except Exception:
                pass
        held_mods.clear()

def autoclick_mode4():
    pydirectinput.keyDown('s');  _loop_hold('s')

def autoclick_mode5():
    pydirectinput.keyDown('w');  _loop_hold('w')

def autoclick_mode6():
    while running:
        pydirectinput.keyDown('shift'); _tiny_sleep()
        mouse_controller.click(mouse.Button.left); _tiny_sleep()
        pydirectinput.keyUp('shift'); time.sleep(0.1)

def _loop_hold(keyname):
    try:
        while running: time.sleep(0.1)
    finally:
        pydirectinput.keyUp(keyname)

# ===== Керування =====
def start_autoclick():
    if mode == 1: autoclick_mode1()
    elif mode == 2: autoclick_mode2()
    elif mode == 3: threading.Thread(target=play_recording, daemon=True).start()
    elif mode == 4: autoclick_mode4()
    elif mode == 5: autoclick_mode5()
    elif mode == 6: autoclick_mode6()

def format_delay_text(delay_s: float) -> str:
    if abs(delay_s - 1.0) < 1e-6: return "Підготовка... 1 секунда"
    return f"Підготовка... {delay_s:.1f} секунди"

def start(delay_s: float = 1.0):
    global running, start_seq
    if not running and mode in [1,2,3,4,5,6]:
        running = True
        start_seq += 1
        local_seq = start_seq
        status_state_var.set(format_delay_text(delay_s))
        threading.Thread(target=delayed_start, args=(local_seq, delay_s), daemon=True).start()

def delayed_start(local_seq, delay_s: float):
    time.sleep(delay_s)
    if not running or local_seq != start_seq: return
    status_state_var.set("Працює")
    threading.Thread(target=start_autoclick, daemon=True).start()

def stop():
    global running, start_seq
    if running:
        running = False
        start_seq += 1
        status_state_var.set("Зупинено")

def select_mode(m):
    global mode
    stop(); mode = m
    if m == 1:
        status_var.set("Споттер: Утримання ПКМ")
    elif m == 2:
        status_var.set("Стрілець: ЛКМ + R кожні 100мс")
    elif m == 3:
        status_var.set("Заряджаючий: Макрорекордер (клавіатура)")
    elif m == 4:
        status_var.set("Логістика: Утримання S")
    elif m == 5:
        status_var.set("Логістика: Утримання W")
    elif m == 6:
        status_var.set("Логістика: Повторення Shift + ЛКМ")
    update_mode_highlight(m)
    update_macro_status_ui()

def global_keyboard_listener():
    def on_press(key):
        try:
            if key == keyboard.Key.f6:
                if running: stop()
                else: start(delay_s=0.1)
            elif key == keyboard.Key.f7 and not recording:
                start_recording()
        except: pass
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()

# ===== Статус макро (права колонка) =====
def minutes_ago(ts):
    """Повертає час від останнього запису: спочатку секунди, далі хвилини."""
    if not ts:
        return "—"
    delta = max(0, int(time.time() - ts))
    if delta < 60:
        return f"{delta} с тому"
    mins = delta // 60
    return f"{mins} хв тому"

macro_label_rec = None
macro_label_time = None

def build_macro_right_col(parent):
    global macro_label_rec, macro_label_time
    right = tk.Frame(parent, bg=PANEL_BG)
    right.grid(row=0, column=1, sticky="nsew")
    parent.grid_columnconfigure(1, weight=1, uniform="statuscol")
    macro_label_rec  = tk.Label(right, bg=PANEL_BG, fg=TEXT_MAIN,
                                font=("{Segoe UI}", 10, "bold"),
                                anchor="w")
    macro_label_time = tk.Label(right, bg=PANEL_BG, fg=TEXT_MUT,
                                font=("{Segoe UI}", 10),
                                anchor="w")
    macro_label_rec.pack(anchor="w", padx=12, pady=(2,0))
    macro_label_time.pack(anchor="w", padx=12, pady=(0,8))

def update_macro_status_ui():
    """Оновити праву частину статусу: лише 'Є' або 'Немає' + час останнього запису."""
    if macro_label_rec is None:
        return
    rec_text = "Є" if has_macro else "Немає"
    macro_label_rec.config(text=f"Запис макро: {rec_text}")
    macro_label_time.config(text=f"Запис зроблено: {minutes_ago(last_macro_record_time)}")

def macro_timer_tick():
    update_macro_status_ui()
    root.after(1000, macro_timer_tick)

# ===== Інтерфейс =====
root = tk.Tk()
root.title("Автоклікер для артилерії")

# розмір/позиція
win_w, win_h = 820, 980
sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
center_x = (sw - win_w) // 2
center_y = (sh - win_h) // 2
pos_y = max(0, center_y - sh // 10)
root.geometry(f"{win_w}x{win_h}+{center_x}+{pos_y}")
make_style(root)

# іконка вікна
icon_img = load_photo_image(ICON_EMBLEM_PATH)
if icon_img:
    try: root.iconphoto(True, icon_img)
    except: pass

# === Прокручувана область ===
container = tk.Frame(root, bg=BG_MAIN)
container.pack(fill="both", expand=True)

canvas = tk.Canvas(container, bg=BG_MAIN, highlightthickness=0)
vbar   = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
canvas.configure(yscrollcommand=vbar.set)

vbar.pack(side="right", fill="y")
canvas.pack(side="left", fill="both", expand=True)

scroll_frame = ttk.Frame(canvas, style="BG.TFrame")
window_id = canvas.create_window((0,0), window=scroll_frame, anchor="nw")

def on_frame_configure(_=None):
    canvas.configure(scrollregion=canvas.bbox("all"))
def on_canvas_configure(event):
    canvas.itemconfigure(window_id, width=event.width)
def _on_mousewheel(event):
    canvas.yview_scroll(-int(event.delta/120), "units")

scroll_frame.bind("<Configure>", on_frame_configure)
canvas.bind("<Configure>", on_canvas_configure)
root.bind_all("<MouseWheel>", _on_mousewheel)

# ===== Содержимое (всё строим ВНУТРИ scroll_frame) =====

# шапка максимально «піджата» догори
emblem_panel = add_panel(scroll_frame, "", draw_line=False, top_pad=0)
emblem_img = load_photo_image(ICON_EMBLEM_PATH, size=(128, 128))
if emblem_img:
    _img_cache["emblem"] = emblem_img
    tk.Label(emblem_panel, image=emblem_img, bg=PANEL_BG).pack(pady=(0,0))
tk.Label(emblem_panel, text="За Барсіка та Імперію Варденів!",
         bg=PANEL_BG, fg="#eaf3ff", font=("{Segoe UI}", 12, "bold"),
         anchor="center", justify="center")\
    .pack(anchor="center", pady=(1,14))

# статус (дві колонки)
status_panel = add_panel(scroll_frame, "СТАТУС")
status_columns = tk.Frame(status_panel, bg=PANEL_BG); status_columns.pack(fill="x")
status_columns.grid_columnconfigure(0, weight=1, uniform="statuscol")
status_columns.grid_columnconfigure(1, weight=1, uniform="statuscol")

left_status_col = tk.Frame(status_columns, bg=PANEL_BG)
left_status_col.grid(row=0, column=0, sticky="nsew")

status_var = tk.StringVar(value="Режим не обрано")
status_state_var = tk.StringVar(value="Зупинено")
tk.Label(left_status_col, textvariable=status_var, bg=PANEL_BG, fg=TEXT_MAIN,
         font=("{Segoe UI}", 12, "bold"), anchor="w")\
    .pack(anchor="w", padx=12, pady=(4,0))
tk.Label(left_status_col, textvariable=status_state_var, bg=PANEL_BG, fg="#f0817b",
         font=("{Segoe UI}", 12, "bold"), anchor="w")\
    .pack(anchor="w", padx=12, pady=(0,6))

build_macro_right_col(status_columns)
update_macro_status_ui()

# керування
ctrl_panel = add_panel(scroll_frame, "КЕРУВАННЯ (F6 / F7)")
make_button(ctrl_panel, "▶ Старт (F6)", lambda: start(delay_s=1.0), "Start.TButton")
make_button(ctrl_panel, "■ Стоп (F6)",  stop,  "Stop.TButton")

# дві колонки 50/50: Арта / Логістика
cols = ttk.Frame(scroll_frame, style="BG.TFrame")
cols.pack(fill="x")
cols.grid_columnconfigure(0, weight=1, uniform="cols")
cols.grid_columnconfigure(1, weight=1, uniform="cols")

left_col  = ttk.Frame(cols, style="BG.TFrame");  left_col.grid(row=0, column=0, sticky="nsew")
right_col = ttk.Frame(cols, style="BG.TFrame"); right_col.grid(row=0, column=1, sticky="nsew")

ICON_H = 20
icon_arta  = load_icon_fixed_height(ICON_ARTA_PATH,  ICON_H)
icon_zavod = load_icon_fixed_height(ICON_ZAVOD_PATH, ICON_H)
if icon_arta:  _img_cache["arta"]  = icon_arta
if icon_zavod: _img_cache["zavod"] = icon_zavod

modes_panel = add_panel(left_col,  "АРТА",      hp=4, title_icon=icon_arta)
make_mode_button(modes_panel, "Споттер: Утримання ПКМ",          lambda: select_mode(1), "role", 1)
make_mode_button(modes_panel, "Стрілець: ЛКМ + R кожні 100мс",   lambda: select_mode(2), "role", 2)
make_mode_button(modes_panel, "Заряджаючий: Макро (клавіатура)", lambda: select_mode(3), "role", 3)

logi_panel  = add_panel(right_col, "ЛОГІСТИКА", hp=4, title_icon=icon_zavod)
make_mode_button(logi_panel, "Утримання S",            lambda: select_mode(4), "logi", 4)
make_mode_button(logi_panel, "Утримання W",            lambda: select_mode(5), "logi", 5)
make_mode_button(logi_panel, "Повторення Shift + ЛКМ", lambda: select_mode(6), "logi", 6)

# рекордер макро
macro_panel = add_panel(scroll_frame, "РЕКОРДЕР МАКРО")
tk.Button(macro_panel, text="Запис макро (F7)", command=start_recording,
          relief="flat", bd=2, bg=ROLE_BG, fg=TEXT_MAIN,
          activebackground=ROLE_HOV, activeforeground=TEXT_MAIN,
          padx=10, pady=6, highlightthickness=0, anchor="w")\
    .pack(pady=6, padx=12, fill="x")
tk.Label(macro_panel, text="Зупинити запис: ЛКМ", bg=PANEL_BG, fg=TEXT_MUT, anchor="w")\
    .pack(anchor="w", padx=14, pady=(0,8))

# ІНФО
info_panel = add_panel(scroll_frame, "ІНФО")
info_text = (
    "Затримка до початку виконання обраного режиму:\n"
    "• зі кнопки «Старт» — 1.0 с\n"
    "• гарячою клавішею F6 — 0.1 с\n"
    "Рекордер макро записує лише клавіатуру"
)
tk.Label(info_panel, text=info_text, bg=PANEL_BG, fg=TEXT_MUT,
         anchor="w", justify="left")\
    .pack(anchor="w", padx=12, pady=(6,8))

# нижній внутрішній відступ у скролюваній області
tk.Frame(scroll_frame, bg=BG_MAIN, height=8).pack(fill="x")

# ===== Системні ниті/таймери =====
threading.Thread(target=global_keyboard_listener, daemon=True).start()
root.after(1000, macro_timer_tick)

root.mainloop()
