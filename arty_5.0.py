import tkinter as tk
from tkinter import ttk
import threading
import time
from pynput import mouse, keyboard
import pydirectinput
import sys, os, json, atexit
from tkinter import messagebox as mb

def get_settings_path():
    base_dir = None
    if getattr(sys, 'frozen', False):
        base_dir = os.path.join(os.environ.get("APPDATA", os.getcwd()), "ArtyKlicker")
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    if not os.path.exists(base_dir):
        os.makedirs(base_dir, exist_ok=True)
    return os.path.join(base_dir, "settings.json")

def resource_path(rel_path: str) -> str:
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, rel_path)

BG_MAIN   = "#1b4670"
PANEL_BG  = "#245b86"
BORDER_BG = "#163954"
TEXT_MAIN = "#e6edf3"
TEXT_MUT  = "#c7d3df"

ROLE_BG   = "#3a6ea5"
ROLE_HOV  = "#3f74ad"
ROLE_SEL  = "#5b95c2"

LOGI_BG   = "#5a87a7"
LOGI_HOV  = "#6393b4"
LOGI_SEL  = "#7aa8c4"

START_BG  = "#3a6ea5"; START_HOV = "#3f74ad"
STOP_BG   = "#214e76";  STOP_HOV  = "#275a88"

STATUS_GREEN  = "#7CFF7C"
STATUS_RED    = "#FF6B6B"
STATUS_AMBER  = "#FFD27F"

OK_MARK = "✓"
NO_MARK = "×"

ICON_EMBLEM_PATH = resource_path("UDC.png")
ICON_ARTA_PATH   = resource_path("Arta.png")
ICON_ZAVOD_PATH  = resource_path("Zavod.png")
SETTINGS_PATH = get_settings_path()

running = False
mode = None
recording = False
recorded_events = []
start_time = None
start_seq = 0

has_macro = False
last_macro_record_time = None

mouse_controller = mouse.Controller()
MODE_UI = {}
_img_cache = {}

_record_suppress_keys = set()
_record_suppress_until = 0.0

pydirectinput.PAUSE = 0
pydirectinput.FAILSAFE = False

DEFAULT_SETTINGS = {
    "hotkeys": {
        "start_stop": "f6",
        "record": "f7",
        "record_stop": "f8",
        "mode_select": {"1": None, "2": None, "3": None, "4": None, "5": None, "6": None}
    },
    "overlay": {
        "enabled": True,
        "alpha": 0.85,
        "dx": 14,
        "dy": 18
    }
}
SETTINGS = {}

def load_settings():
    global SETTINGS
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    def deep_merge_overwrite(base, inc):
        for k, v in inc.items():
            if isinstance(v, dict) and isinstance(base.get(k), dict):
                deep_merge_overwrite(base[k], v)
            else:
                base[k] = v
    SETTINGS = json.loads(json.dumps(DEFAULT_SETTINGS))
    deep_merge_overwrite(SETTINGS, data)

def save_settings():
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(SETTINGS, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

load_settings()

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
    if target_h <= 0: return img
    h = img.height()
    if h == 0: return img
    if h > target_h:
        k = max(1, round(h / target_h)); img = img.subsample(k)
    elif h < target_h:
        k = max(1, round(target_h / h)); img = img.zoom(k)
    if img.height() > target_h:
        k = max(1, round(img.height() / target_h)); img = img.subsample(k)
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

VK_TO_NAME = {
    0x10: "shift", 0x11: "ctrl", 0x12: "alt",
    0x20: "space", 0x0D: "enter", 0x1B: "esc", 0x09: "tab", 0x08: "backspace", 0x2E: "delete",
    0x24: "home", 0x23: "end", 0x21: "pageup", 0x22: "pagedown", 0x2D: "insert",
    0x26: "up", 0x28: "down", 0x25: "left", 0x27: "right",
    0x70: "f1", 0x71: "f2", 0x72: "f3", 0x73: "f4", 0x74: "f5", 0x75: "f6",
    0x76: "f7", 0x77: "f8", 0x78: "f9", 0x79: "f10", 0x7A: "f11", 0x7B: "f12",
    0x14: "capslock",
}
def _vk_to_name(vk):
    if 0x30 <= vk <= 0x39: return chr(vk)
    if 0x41 <= vk <= 0x5A: return chr(vk).lower()
    return VK_TO_NAME.get(vk)

def _normalize_key_for_directinput(key):
    vk = getattr(key, "vk", None)
    if isinstance(vk, int):
        name = _vk_to_name(vk)
        if name:
            is_char = name.isalpha() or name.isdigit()
            return name, is_char, False
    try:
        if hasattr(key, "char") and key.char:
            ch = key.char
            return ch.lower(), True, ch.isupper()
    except Exception:
        pass
    try:
        name = getattr(key, "name", None) or str(key).replace("Key.", "")
    except Exception:
        name = None
    if not name: return None, False, False
    if name.startswith("shift"): return "shift", False, False
    if name.startswith("ctrl"):  return "ctrl",  False, False
    if name.startswith("alt"):   return "alt",   False, False
    if name.startswith("f") and name[1:].isdigit(): return name, False, False
    mapping = {
        "space":"space","enter":"enter","esc":"esc","tab":"tab",
        "backspace":"backspace","delete":"delete",
        "up":"up","down":"down","left":"left","right":"right",
        "caps_lock":"capslock","home":"home","end":"end",
        "page_up":"pageup","page_down":"pagedown","insert":"insert",
    }
    if name in mapping: return mapping[name], False, False
    return None, False, False

MODE_NAME = {
    1: "Споттер: Утримання ПКМ",
    2: "Стрілець: ЛКМ + R кожні 100мс",
    3: "Заряджаючий: Макрорекордер (клавіатура)",
    4: "Логістика: Утримання S",
    5: "Логістика: Утримання W",
    6: "Логістика: Повторення Shift + ЛКМ",
}

play_stop_evt = threading.Event()
play_thread = None
_play_held_keys = set()
_play_held_mods = set()

_is_windows = sys.platform.startswith("win")
if _is_windows:
    import ctypes
    _GetAsyncKeyState = ctypes.windll.user32.GetAsyncKeyState
    _NAME_TO_VK = {
        "shift":0x10,"ctrl":0x11,"alt":0x12,"space":0x20,"enter":0x0D,"esc":0x1B,"tab":0x09,
        "backspace":0x08,"delete":0x2E,"home":0x24,"end":0x23,"pageup":0x21,"pagedown":0x22,"insert":0x2D,
        "up":0x26,"down":0x28,"left":0x25,"right":0x27,
        "capslock":0x14,"f1":0x70,"f2":0x71,"f3":0x72,"f4":0x73,"f5":0x74,"f6":0x75,
        "f7":0x76,"f8":0x77,"f9":0x78,"f10":0x79,"f11":0x7A,"f12":0x7B,
    }
    def _vk_for_name(name: str):
        n = name.lower()
        if n in _NAME_TO_VK: return _NAME_TO_VK[n]
        if len(n) == 1 and n.isalnum():
            ch = n.upper()
            return ord(ch)
        return None
    def _combo_names(combo_str: str):
        if not combo_str: return []
        parts = [p.strip().lower() for p in combo_str.split("+") if p.strip()]
        mods = [m for m in ["ctrl","alt","shift"] if m in parts]
        rest = [p for p in parts if p not in ("ctrl","alt","shift")]
        if rest: rest = rest[:1]
        return mods + rest
    def is_combo_down_async(combo_str: str) -> bool:
        if not combo_str: return False
        names = _combo_names(combo_str)
        if not names: return False
        for n in names:
            vk = _vk_for_name(n)
            if vk is None: return False
            state = _GetAsyncKeyState(vk)
            if (state & 0x8000) == 0:
                return False
        return True
else:
    def is_combo_down_async(combo_str: str) -> bool:
        return False

_async_stop_prev_down = False
_async_stop_guard_until = 0.0

def _async_hard_stop():
    play_stop_evt.set()
    _release_playback_keys()
    try:
        root.after(0, stop)
    except Exception:
        stop()

def _emergency_poll_stop():
    global _async_stop_prev_down, _async_stop_guard_until
    stop_combo = SETTINGS["hotkeys"].get("start_stop")
    if not stop_combo:
        return False
    now = time.time()
    down_now = is_combo_down_async(stop_combo)
    if now < _async_stop_guard_until:
        _async_stop_prev_down = down_now
        return False
    if down_now and not _async_stop_prev_down:
        _async_hard_stop()
        _async_stop_prev_down = down_now
        return True
    _async_stop_prev_down = down_now
    return False

def _tiny_sleep(): time.sleep(0.008)

def autoclick_mode1():
    mouse_controller.press(mouse.Button.right)
    try:
        while running and not play_stop_evt.is_set():
            _emergency_poll_stop()
            time.sleep(0.05)
    finally:
        mouse_controller.release(mouse.Button.right)

def autoclick_mode2():
    while running and not play_stop_evt.is_set():
        _emergency_poll_stop()
        pydirectinput.keyDown('r'); time.sleep(0.05); pydirectinput.keyUp('r')
        time.sleep(0.05)
        mouse_controller.click(mouse.Button.left)
        time.sleep(0.05)

def _release_playback_keys():
    for k in list(_play_held_keys):
        try: pydirectinput.keyUp(k)
        except: pass
    _play_held_keys.clear()
    for m in list(_play_held_mods):
        try: pydirectinput.keyUp(m)
        except: pass
    _play_held_mods.clear()
    for m in ("shift","ctrl","alt"):
        try: pydirectinput.keyUp(m)
        except: pass

def _interruptible_wait(seconds: float):
    end = time.time() + seconds
    while time.time() < end:
        if play_stop_evt.is_set() or _emergency_poll_stop() or not running:
            return True
        time.sleep(0.005)
    return False

def play_recording():
    if not recorded_events:
        return
    global running, _play_held_keys, _play_held_mods
    while running and not play_stop_evt.is_set():
        start_play = time.time()
        _play_held_keys.clear()
        _play_held_mods.clear()
        for key, event_type, ts in recorded_events:
            if not running or play_stop_evt.is_set():
                break
            wait = (start_play + ts) - time.time()
            if wait > 0:
                if _interruptible_wait(wait):
                    break
            kname, is_char, is_upper = _normalize_key_for_directinput(key)
            if not kname:
                continue
            try:
                if event_type == "press":
                    if kname in ("shift","ctrl","alt"):
                        if kname not in _play_held_mods:
                            pydirectinput.keyDown(kname); _tiny_sleep()
                            _play_held_mods.add(kname); _play_held_keys.add(kname)
                        continue
                    if is_char and is_upper and "shift" not in _play_held_mods:
                        pydirectinput.keyDown("shift"); _tiny_sleep()
                        _play_held_mods.add("shift"); _play_held_keys.add("shift")
                    if kname not in _play_held_keys:
                        pydirectinput.keyDown(kname); _tiny_sleep()
                        _play_held_keys.add(kname)
                elif event_type == "release":
                    if kname in _play_held_keys:
                        pydirectinput.keyUp(kname); _tiny_sleep()
                        _play_held_keys.discard(kname)
                    if kname in ("shift","ctrl","alt") and kname in _play_held_mods:
                        _play_held_mods.discard(kname)
            except Exception:
                pass
            if _emergency_poll_stop():
                break
        _release_playback_keys()

def autoclick_mode4():
    pydirectinput.keyDown('s')
    try:
        while running and not play_stop_evt.is_set():
            _emergency_poll_stop(); time.sleep(0.02)
    finally:
        pydirectinput.keyUp('s')

def autoclick_mode5():
    pydirectinput.keyDown('w')
    try:
        while running and not play_stop_evt.is_set():
            _emergency_poll_stop(); time.sleep(0.02)
    finally:
        pydirectinput.keyUp('w')

def autoclick_mode6():
    while running and not play_stop_evt.is_set():
        _emergency_poll_stop()
        pydirectinput.keyDown('shift'); _tiny_sleep()
        mouse_controller.click(mouse.Button.left); _tiny_sleep()
        pydirectinput.keyUp('shift'); time.sleep(0.05)

def record_key_event(key, event_type):
    global recorded_events
    if not recording: return
    name, *_ = _normalize_key_for_directinput(key)
    if name and time.time() < _record_suppress_until and name in _record_suppress_keys:
        return
    ts = time.time() - start_time
    recorded_events.append((key, event_type, ts))

def start_recording():
    global recording, recorded_events, start_time, has_macro, last_macro_record_time
    global _record_suppress_keys, _record_suppress_until
    if recording: return
    recorded_events = []
    start_time = time.time()
    recording = True
    has_macro = False
    last_macro_record_time = None
    _record_suppress_keys = set()
    _record_suppress_until = 0.0
    set_status_state("Працює", STATUS_GREEN)
    update_macro_status_ui(); overlay_update_now()
    threading.Thread(target=record_keyboard_listener, daemon=True).start()
    threading.Thread(target=record_mouse_stop_listener, daemon=True).start()

def _finish_recording():
    global recording, has_macro, last_macro_record_time
    if not recording: return
    recording = False
    has_macro = len(recorded_events) > 0
    last_macro_record_time = time.time() if has_macro else None
    set_status_state("Не працює", STATUS_RED)
    update_macro_status_ui(); overlay_update_now()

def stop_recording_mouse(x=None, y=None, button=None, pressed=None):
    if recording and pressed and button == mouse.Button.left:
        _finish_recording(); return False

def stop_recording_keyboard():
    _finish_recording()

def record_keyboard_listener():
    with keyboard.Listener(on_press=lambda k: record_key_event(k, 'press'),
                           on_release=lambda k: record_key_event(k, 'release')) as listener:
        while recording: time.sleep(0.01)
        listener.stop()

def record_mouse_stop_listener():
    with mouse.Listener(on_click=stop_recording_mouse) as listener:
        listener.join()

def start_autoclick():
    global play_thread
    if mode == 1: autoclick_mode1()
    elif mode == 2: autoclick_mode2()
    elif mode == 3:
        play_thread = threading.Thread(target=play_recording, daemon=True)
        play_thread.start()
    elif mode == 4: autoclick_mode4()
    elif mode == 5: autoclick_mode5()
    elif mode == 6: autoclick_mode6()

def start(delay_s: float = 1.0):
    global running, start_seq, _async_stop_guard_until, _async_stop_prev_down
    if mode == 3 and not has_macro:
        mb.showinfo("Немає макросу",
                    "Немає записаного макросу для відтворення.\n"
                    "Спочатку зробіть запис (кнопка «Запис макро» або гаряча клавіша).")
        return
    if not running and mode in [1,2,3,4,5,6]:
        play_stop_evt.clear()
        running = True
        start_seq += 1
        local_seq = start_seq
        stop_combo = SETTINGS["hotkeys"].get("start_stop")
        _async_stop_guard_until = time.time() + 0.35
        _async_stop_prev_down = bool(is_combo_down_async(stop_combo)) if stop_combo else False
        set_status_state(
            "Підготовка... 1 секунда" if abs(delay_s-1.0)<1e-6 else f"Підготовка... {delay_s:.1f} секунди",
            STATUS_AMBER
        )
        overlay_update_now()
        threading.Thread(target=delayed_start, args=(local_seq, delay_s), daemon=True).start()

def delayed_start(local_seq, delay_s: float):
    if _interruptible_wait(delay_s):
        return
    if not running or local_seq != start_seq: return
    set_status_state("Працює", STATUS_GREEN)
    overlay_update_now()
    threading.Thread(target=start_autoclick, daemon=True).start()

def stop():
    global running, start_seq
    if running:
        running = False
        start_seq += 1
        play_stop_evt.set()
        _release_playback_keys()
        set_status_state("Не працює", STATUS_RED)
        overlay_update_now()

def select_mode(m):
    global mode
    stop(); mode = m
    status_var.set(MODE_NAME.get(m, "Режим не обрано"))
    update_mode_highlight(m)
    update_macro_status_ui(); overlay_update_now()

def _key_name_from_pynput(k):
    n, *_ = _normalize_key_for_directinput(k)
    return n

MOD_ORDER = ["ctrl","alt","shift"]
def _canonize_combo_list(names):
    mods = [k for k in MOD_ORDER if k in names]
    rest = sorted([k for k in names if k not in MOD_ORDER])
    return mods + rest

def str_to_combo(s):
    if not s: return []
    parts = [p.strip().lower() for p in s.split("+") if p.strip()]
    ordered = _canonize_combo_list(parts)
    return ordered[:2]

def _combo_match(pressed_set, combo_str):
    if not combo_str: return False
    need = set(str_to_combo(combo_str))
    return need and (pressed_set == need)

def iter_all_combo_slots():
    yield ("hotkeys.start_stop", lambda: SETTINGS["hotkeys"]["start_stop"])
    yield ("hotkeys.record",     lambda: SETTINGS["hotkeys"]["record"])
    yield ("hotkeys.record_stop",lambda: SETTINGS["hotkeys"]["record_stop"])
    for mid in ("1","2","3","4","5","6"):
        yield (f"hotkeys.mode_select.{mid}", lambda m=mid: SETTINGS["hotkeys"]["mode_select"].get(m))

def slot_path_label(path: str) -> str:
    if path == "hotkeys.start_stop":   return "Старт/Стоп"
    if path == "hotkeys.record":       return "Почати запис макро"
    if path == "hotkeys.record_stop":  return "Зупинити запис макро"
    if path.startswith("hotkeys.mode_select."):
        mid = path.split(".")[-1]
        try:
            mid_int = int(mid)
            return f"Швидкий вибір режиму: {MODE_NAME.get(mid_int, mid)}"
        except:
            return "Швидкий вибір режиму"
    return path

def find_conflict(target_path: str, combo_str: str | None) -> str | None:
    if not combo_str: return None
    new_norm = combo_str.lower()
    for path, getter in iter_all_combo_slots():
        if path == target_path: continue
        v = getter()
        if v and v.lower() == new_norm:
            return path
    return None

def global_keyboard_listener():
    global _record_suppress_keys, _record_suppress_until
    pressed = set()
    last_trigger = {}
    COOLDOWN = 0.35
    COOLDOWN_STARTSTOP = 0.0
    def maybe_trigger(tag, fn, cooldown):
        now = time.time()
        if now - last_trigger.get(tag, 0) > cooldown:
            last_trigger[tag] = now
            try: fn()
            except: pass
    def hard_stop_from_hotkey():
        _async_hard_stop()
    def on_press(key):
        name = _key_name_from_pynput(key)
        if not name: return
        hk  = SETTINGS["hotkeys"]
        sel = hk["mode_select"]
        pressed.add(name)
        if len(pressed) > 2:
            ordered = _canonize_combo_list(list(pressed))
            pressed.clear(); pressed.update(ordered[:2])
        if _combo_match(pressed, hk.get("start_stop")):
            if running:
                maybe_trigger("start_stop", hard_stop_from_hotkey, COOLDOWN_STARTSTOP)
            else:
                maybe_trigger("start_stop", lambda: start(delay_s=0.1), COOLDOWN_STARTSTOP)
            return
        if _combo_match(pressed, hk.get("record")) and not recording:
            maybe_trigger("record", start_recording, COOLDOWN); return
        if recording and _combo_match(pressed, hk.get("record_stop")):
            _record_suppress_keys  = set(pressed)
            _record_suppress_until = time.time() + 0.5
            maybe_trigger("record_stop", stop_recording_keyboard, COOLDOWN_STARTSTOP); return
        for mid, assigned in sel.items():
            if assigned and _combo_match(pressed, assigned):
                maybe_trigger(f"mode_{mid}", lambda m=int(mid): select_mode(m), COOLDOWN)
                return
    def on_release(key):
        name = _key_name_from_pynput(key)
        if name and name in pressed:
            pressed.discard(name)
    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()

def minutes_ago(ts):
    if not ts: return "—"
    delta = max(0, int(time.time() - ts))
    if delta < 60: return f"{delta} с тому"
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
    if macro_label_rec is None: return
    rec_text = "Є" if has_macro else "Немає"
    macro_label_rec.config(text=f"Запис макро: {rec_text}")
    macro_label_time.config(text=f"Запис зроблено: {minutes_ago(last_macro_record_time)}")

def macro_timer_tick():
    update_macro_status_ui()
    overlay_update_now()
    root.after(1000, macro_timer_tick)

overlay_win = None
overlay_line1 = None
ov_mark = None
ov_text = None
ov_sep  = None
ov_mode = None
overlay_line2 = None

def build_overlay():
    global overlay_win, overlay_line1, ov_mark, ov_text, ov_sep, ov_mode, overlay_line2
    if overlay_win is not None: return
    overlay_win = tk.Toplevel(root)
    overlay_win.overrideredirect(True)
    try:
        overlay_win.attributes("-topmost", True)
        overlay_win.attributes("-alpha", SETTINGS["overlay"]["alpha"])
    except Exception:
        pass
    overlay_win.configure(bg="#000000")
    overlay_line1 = tk.Frame(overlay_win, bg="#000000")
    overlay_line1.pack(padx=0, pady=(0,0), anchor="w")
    ov_mark = tk.Label(overlay_line1, text="", bg="#000000", fg=STATUS_GREEN,
                       font=("{Segoe UI}", 13, "bold"), padx=4, pady=1, anchor="w")
    ov_text = tk.Label(overlay_line1, text="", bg="#000000", fg=STATUS_GREEN,
                       font=("{Segoe UI}", 10, "bold"), padx=6, pady=2, anchor="w")
    ov_sep  = tk.Label(overlay_line1, text="   |   ", bg="#000000", fg="#ffffff",
                       font=("{Segoe UI}", 9, "bold"), padx=0, pady=3, anchor="w")
    ov_mode = tk.Label(overlay_line1, text="", bg="#000000", fg="#ffffff",
                       font=("{Segoe UI}", 9, "bold"), padx=6, pady=3, anchor="w")
    ov_mark.pack(side="left"); ov_text.pack(side="left"); ov_sep.pack(side="left"); ov_mode.pack(side="left")
    overlay_line2 = tk.Label(overlay_win, text="", bg="#000000", fg="#d9e1ff",
                             font=("{Segoe UI}", 8, "bold"),
                             padx=12, pady=2, anchor="w", justify="left")
    overlay_line2.pack(anchor="w")
    overlay_update_now()
    if not SETTINGS["overlay"]["enabled"]:
        overlay_win.withdraw()

def overlay_update_now():
    if overlay_win is None: return
    if running:
        ov_mark.config(text=OK_MARK, fg=STATUS_GREEN)
        ov_text.config(text="Працює", fg=STATUS_GREEN)
    else:
        ov_mark.config(text=NO_MARK, fg=STATUS_RED)
        ov_text.config(text="Не працює", fg=STATUS_RED)
    ov_mode.config(text=MODE_NAME.get(mode, "—"))
    if mode == 3:
        rec_icon = OK_MARK if recording else NO_MARK
        has_icon = "Є" if has_macro else "Немає"
        when_txt = minutes_ago(last_macro_record_time)
        overlay_line2.config(text=f"Запис: {rec_icon}   |   Запис макро: {has_icon}   |   Запис зроблено: {when_txt}")
        overlay_line2.pack(anchor="w")
    else:
        overlay_line2.config(text="")
        overlay_line2.pack_forget()

def overlay_tick():
    try:
        if SETTINGS["overlay"]["enabled"]:
            if overlay_win.state() == "withdrawn": overlay_win.deiconify()
            x, y = mouse_controller.position
            dx = SETTINGS["overlay"]["dx"]; dy = SETTINGS["overlay"]["dy"]
            overlay_win.geometry(f"+{int(x+dx)}+{int(y+dy)}")
        else:
            overlay_win.withdraw()
    except Exception:
        pass
    root.after(40, overlay_tick)

def key_capture_combo(callback):
    pressed = set()
    best_set = set()
    def _canon(names):
        mods = [k for k in MOD_ORDER if k in names]
        rest = sorted([k for k in names if k not in MOD_ORDER])
        return mods + rest
    def consider_update():
        nonlocal best_set
        limited = set(_canon(list(pressed))[:2])
        def rank(s):
            ordered = _canon(list(s))
            return (len(ordered), ordered)
        if rank(limited) > rank(best_set):
            best_set = set(limited)
    def on_press(k):
        name = _key_name_from_pynput(k)
        if not name: return
        pressed.add(name)
        if len(pressed) > 2:
            ordered = _canon(list(pressed))
            pressed.clear(); pressed.update(ordered[:2])
        consider_update()
    def on_release(k):
        name = _key_name_from_pynput(k)
        if name and name in pressed: pressed.discard(name)
        if not pressed:
            combo = "+".join(_canon(list(best_set))).upper() if best_set else None
            try: callback(combo)
            except: pass
            return False
    threading.Thread(target=lambda: keyboard.Listener(on_press=on_press, on_release=on_release).run(),
                     daemon=True).start()

root = tk.Tk()
root.title("Автоклікер для артилерії")

sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
win_w = 820
desired_h = 1080
max_h = max(480, sh - 80)
win_h = min(desired_h, max_h)
pos_x = (sw - win_w) // 2
pos_y = 0
root.geometry(f"{win_w}x{win_h}+{pos_x}+{pos_y}")
make_style(root)

icon_img = load_photo_image(ICON_EMBLEM_PATH)
if icon_img:
    try: root.iconphoto(True, icon_img)
    except: pass

container = tk.Frame(root, bg=BG_MAIN); container.pack(fill="both", expand=True)
canvas = tk.Canvas(container, bg=BG_MAIN, highlightthickness=0)
vbar   = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
canvas.configure(yscrollcommand=vbar.set)
vbar.pack(side="right", fill="y"); canvas.pack(side="left", fill="both", expand=True)
scroll_frame = ttk.Frame(canvas, style="BG.TFrame")
window_id = canvas.create_window((0,0), window=scroll_frame, anchor="nw")

def on_frame_configure(_=None): canvas.configure(scrollregion=canvas.bbox("all"))
def on_canvas_configure(event): canvas.itemconfigure(window_id, width=event.width)

def _on_mousewheel(event):
    if getattr(event, "delta", 0) != 0:
        steps = -int(event.delta / 120)
        if steps != 0: canvas.yview_scroll(steps, "units")
        return
    if getattr(event, "num", None) == 4: canvas.yview_scroll(-1, "units")
    elif getattr(event, "num", None) == 5: canvas.yview_scroll(1, "units")

scroll_frame.bind("<Configure>", on_frame_configure)
canvas.bind("<Configure>", on_canvas_configure)
root.bind_all("<MouseWheel>", _on_mousewheel)
canvas.bind_all("<Button-4>", _on_mousewheel)
canvas.bind_all("<Button-5>", _on_mousewheel)

emblem_panel = add_panel(scroll_frame, "", draw_line=False, top_pad=0)
emblem_img = load_photo_image(ICON_EMBLEM_PATH, size=(128, 128))
if emblem_img:
    _img_cache["emblem"] = emblem_img
    tk.Label(emblem_panel, image=emblem_img, bg=PANEL_BG).pack(pady=(0,0))
tk.Label(emblem_panel, text="За Барсіка та Імперію Варденів!",
         bg=PANEL_BG, fg="#eaf3ff", font=("{Segoe UI}", 12, "bold"),
         anchor="center", justify="center").pack(anchor="center", pady=(1,14))

status_panel = add_panel(scroll_frame, "СТАТУС")
status_columns = tk.Frame(status_panel, bg=PANEL_BG); status_columns.pack(fill="x")
status_columns.grid_columnconfigure(0, weight=1, uniform="statuscol")
status_columns.grid_columnconfigure(1, weight=1, uniform="statuscol")

left_status_col = tk.Frame(status_columns, bg=PANEL_BG)
left_status_col.grid(row=0, column=0, sticky="nsew")

status_var = tk.StringVar(value="Режим не обрано")
status_state_var = tk.StringVar(value="Не працює")
status_state_label = tk.Label(left_status_col, textvariable=status_state_var,
                              bg=PANEL_BG, fg=STATUS_RED,
                              font=("{Segoe UI}", 12, "bold"), anchor="w")
tk.Label(left_status_col, textvariable=status_var, bg=PANEL_BG, fg=TEXT_MAIN,
         font=("{Segoe UI}", 12, "bold"), anchor="w").pack(anchor="w", padx=12, pady=(4,0))
status_state_label.pack(anchor="w", padx=12, pady=(0,6))

def set_status_state(text: str, color: str):
    status_state_var.set(text)
    try:
        status_state_label.config(fg=color)
    except Exception:
        pass

build_macro_right_col(status_columns)
update_macro_status_ui()

ctrl_panel = add_panel(scroll_frame, "КЕРУВАННЯ (гарячі клавіші)")
make_button(ctrl_panel, "▶ Старт", lambda: start(delay_s=1.0), "Start.TButton")
make_button(ctrl_panel, "■ Стоп",  stop,  "Stop.TButton")

cols = ttk.Frame(scroll_frame, style="BG.TFrame"); cols.pack(fill="x")
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

macro_panel = add_panel(scroll_frame, "РЕКОРДЕР МАКРО")
tk.Button(macro_panel, text="Запис макро", command=start_recording,
          relief="flat", bd=2, bg=ROLE_BG, fg=TEXT_MAIN,
          activebackground=ROLE_HOV, activeforeground=TEXT_MAIN,
          padx=10, pady=6, highlightthickness=0, anchor="w")\
    .pack(pady=6, padx=12, fill="x")
tk.Label(macro_panel, text="Зупинити запис: ЛКМ або ваша гаряча клавіша", bg=PANEL_BG, fg=TEXT_MUT,
         anchor="w").pack(anchor="w", padx=14, pady=(0,8))

settings_panel = add_panel(scroll_frame, "НАЛАШТУВАННЯ КЛАВІШ")

def group_header(parent, text):
    f = tk.Frame(parent, bg=PANEL_BG); f.pack(fill="x", padx=12, pady=(8,4))
    tk.Label(f, text=text, bg=PANEL_BG, fg=TEXT_MAIN, font=("{Segoe UI}", 10, "bold"), anchor="w").pack(side="left")
    return f

help_text = (
    "Натисніть «Змінити», утримуйте 1–2 клавіші одночасно (CTRL+A тощо), відпустіть — зафіксується.\n"
    "Комбінацію не можна використовувати в декількох місцях одночасно."
)
tk.Label(settings_panel, text=help_text, bg=PANEL_BG, fg=TEXT_MUT, anchor="w", justify="left")\
    .pack(anchor="w", padx=12, pady=(6,6))

SETTINGS_VALUE_LABELS = {}

def settings_row_combo(parent, label_text, slot_path, get_value, set_value):
    row = tk.Frame(parent, bg=PANEL_BG); row.pack(fill="x", padx=12, pady=4)
    lab = tk.Label(row, text=label_text, bg=PANEL_BG, fg=TEXT_MAIN, width=38, anchor="w")
    current = (get_value() or "—").upper()
    val = tk.Label(row, text=current, bg=PANEL_BG, fg=TEXT_MUT, anchor="w")
    SETTINGS_VALUE_LABELS[slot_path] = val
    def do_change():
        val.config(text="…")
        def _set(combo_str):
            conflict_path = find_conflict(slot_path, combo_str) if combo_str else None
            if conflict_path:
                val.config(text=(get_value() or "—").upper())
                mb.showwarning("Комбінація зайнята",
                               f"Комбінація «{(combo_str or '').upper()}» вже використовується у "
                               f"«{slot_path_label(conflict_path)}». Оберіть іншу.")
                return
            set_value(combo_str); save_settings()
            val.config(text=(combo_str or "—").upper())
        key_capture_combo(_set)
    btn = tk.Button(row, text="Змінити", command=do_change,
                    relief="flat", bd=2, bg=ROLE_BG, fg=TEXT_MAIN,
                    activebackground=ROLE_HOV, activeforeground=TEXT_MAIN, padx=8, pady=3)
    lab.pack(side="left"); val.pack(side="left", padx=8); btn.pack(side="right")
    return val

group_header(settings_panel, "Старт/Стоп")
settings_row_combo(settings_panel, "Старт/Стоп",
                   "hotkeys.start_stop",
                   lambda: SETTINGS["hotkeys"]["start_stop"],
                   lambda v: SETTINGS["hotkeys"].__setitem__("start_stop", v))

group_header(settings_panel, "АРТА")
for mid in ("1","2","3"):
    settings_row_combo(settings_panel, MODE_NAME[int(mid)],
                       f"hotkeys.mode_select.{mid}",
                       lambda m=mid: SETTINGS["hotkeys"]["mode_select"].get(m),
                       lambda v, m=mid: SETTINGS["hotkeys"]["mode_select"].__setitem__(m, v))

group_header(settings_panel, "ЛОГІСТИКА")
for mid in ("4","5","6"):
    settings_row_combo(settings_panel, MODE_NAME[int(mid)],
                       f"hotkeys.mode_select.{mid}",
                       lambda m=mid: SETTINGS["hotkeys"]["mode_select"].get(m),
                       lambda v, m=mid: SETTINGS["hotkeys"]["mode_select"].__setitem__(m, v))

group_header(settings_panel, "Запис / Зупинка макро")
settings_row_combo(settings_panel, "Почати запис макро",
                   "hotkeys.record",
                   lambda: SETTINGS["hotkeys"]["record"],
                   lambda v: SETTINGS["hotkeys"].__setitem__("record", v))
settings_row_combo(settings_panel, "Зупинити запис макро",
                   "hotkeys.record_stop",
                   lambda: SETTINGS["hotkeys"]["record_stop"],
                   lambda v: SETTINGS["hotkeys"].__setitem__("record_stop", v))

overlay_panel = add_panel(scroll_frame, "ПОКАЗНИК БІЛЯ КУРСОРА (оверлей)")
ov_var = tk.BooleanVar(value=SETTINGS["overlay"]["enabled"])
def on_tgl():
    SETTINGS["overlay"]["enabled"] = bool(ov_var.get())
    save_settings(); overlay_update_now()
tk.Checkbutton(overlay_panel, text="Показувати стан біля курсора",
               variable=ov_var, command=on_tgl, bg=PANEL_BG, fg=TEXT_MAIN,
               activebackground=PANEL_BG, activeforeground=TEXT_MAIN,
               selectcolor=PANEL_BG).pack(anchor="w", padx=12, pady=6)

def get_value_for_slot(path: str):
    if path == "hotkeys.start_stop":   return SETTINGS["hotkeys"]["start_stop"]
    if path == "hotkeys.record":       return SETTINGS["hotkeys"]["record"]
    if path == "hotkeys.record_stop":  return SETTINGS["hotkeys"]["record_stop"]
    if path.startswith("hotkeys.mode_select."):
        mid = path.split(".")[-1]
        return SETTINGS["hotkeys"]["mode_select"].get(mid)
    return None

def reset_settings():
    if not mb.askyesno("Скинути налаштування", "Повернути всі налаштування до значень за замовчуванням?"):
        return
    SETTINGS.clear()
    SETTINGS.update(json.loads(json.dumps(DEFAULT_SETTINGS)))
    save_settings()
    for path, lbl in SETTINGS_VALUE_LABELS.items():
        val = get_value_for_slot(path)
        lbl.config(text=(val or "—").upper())
    ov_var.set(SETTINGS["overlay"]["enabled"])
    overlay_update_now()
    mb.showinfo("Готово", "Налаштування скинуто.")

actions_panel = add_panel(scroll_frame, "ДІЇ")
tk.Button(actions_panel, text="Скинути налаштування",
          command=reset_settings, relief="flat", bd=2,
          bg=STOP_BG, fg=TEXT_MAIN,
          activebackground=STOP_HOV, activeforeground=TEXT_MAIN,
          padx=12, pady=6).pack(anchor="w", padx=12, pady=(6,6))

info_panel = add_panel(scroll_frame, "ІНФО")
info_text = (
    "Затримка до початку виконання обраного режиму:\n"
    "• зі кнопки «Старт» — 1.0 с\n"
    "• гарячою клавішею — 0.1 с (за вашим налаштуванням)\n"
    "Рекордер макро записує лише клавіатуру"
)
tk.Label(info_panel, text=info_text, bg=PANEL_BG, fg=TEXT_MUT,
         anchor="w", justify="left").pack(anchor="w", padx=12, pady=(6,8))

tk.Frame(scroll_frame, bg=BG_MAIN, height=32).pack(fill="x")

def force_update_scrollregion(*_):
    root.update_idletasks()
    canvas.configure(scrollregion=canvas.bbox("all"))
root.after_idle(force_update_scrollregion)
root.after(50,  force_update_scrollregion)
root.after(200, force_update_scrollregion)
root.after(800, force_update_scrollregion)
root.bind("<Configure>", force_update_scrollregion)

threading.Thread(target=global_keyboard_listener, daemon=True).start()
root.after(1000, macro_timer_tick)

build_overlay()
root.after(40, overlay_tick)

def _shutdown_save_settings():
    try: stop()
    except: pass
    try: save_settings()
    except: pass

def on_close():
    _shutdown_save_settings()
    try:
        if 'overlay_win' in globals() and overlay_win is not None:
            overlay_win.destroy()
    except Exception:
        pass
    root.destroy()

atexit.register(_shutdown_save_settings)
root.protocol("WM_DELETE_WINDOW", on_close)

root.mainloop()
