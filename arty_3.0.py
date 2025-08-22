import tkinter as tk
import threading
import time
from pynput import mouse, keyboard
import pydirectinput  # ✅ використовується для натискання клавіш у іграх

# --- Глобальні змінні ---
running = False          # чи працює автоклікер
mode = None              # обраний режим
recording = False        # чи йде запис макросу
recorded_events = []     # список подій для макро [(key, 'press'/'release', timestamp)]
start_time = None        # час початку запису

# Контролери (pynput для миші та клавіатури)
mouse_controller = mouse.Controller()
keyboard_controller = keyboard.Controller()

# --- Режим 1: Утримання ПКМ ---
def autoclick_mode1():
    mouse_controller.press(mouse.Button.right)  # затискаємо ПКМ
    while running:
        time.sleep(0.1)
    mouse_controller.release(mouse.Button.right)  # відпускаємо ПКМ при зупинці

# --- Режим 2: ЛКМ + R ---
def autoclick_mode2():
    while running:
        # натискаємо R через pydirectinput і утримуємо 50 мс
        pydirectinput.keyDown('r')
        time.sleep(0.05)   # утримання R 50 мс
        pydirectinput.keyUp('r')

        # клікаємо ЛКМ
        mouse_controller.click(mouse.Button.left)

        time.sleep(0.1)  # затримка 100 мс між циклами

# --- Режим 3: Макрорекордер (тільки клавіатура) ---
def record_key_event(key, event_type):
    """Записує натискання/відпускання клавіш у список recorded_events"""
    global recorded_events, start_time
    if recording:
        now = time.time()
        timestamp = now - start_time
        recorded_events.append((key, event_type, timestamp))

def start_recording():
    """Запуск запису макросу"""
    global recording, recorded_events, start_time
    if not recording:
        recorded_events = []
        start_time = time.time()
        recording = True
        status_var.set("Йде запис")
        status_label.config(fg="orange")
        threading.Thread(target=record_keyboard_listener, daemon=True).start()
        threading.Thread(target=record_mouse_stop_listener, daemon=True).start()

def stop_recording_mouse(x=None, y=None, button=None, pressed=None):
    """Зупинка запису при кліку ЛКМ"""
    global recording
    if recording and pressed and button == mouse.Button.left:
        recording = False
        status_var.set("Запис завершено")
        status_label.config(fg="blue")
        return False  # зупиняємо listener

def record_keyboard_listener():
    """Слухає клавіатуру під час запису макросу"""
    with keyboard.Listener(on_press=lambda k: record_key_event(k, 'press'),
                           on_release=lambda k: record_key_event(k, 'release')) as listener:
        while recording:
            time.sleep(0.01)
        listener.stop()

def record_mouse_stop_listener():
    """Слухає мишу для зупинки запису (по ЛКМ)"""
    with mouse.Listener(on_click=stop_recording_mouse) as listener:
        listener.join()

def play_recording():
    """Відтворення записаного макросу"""
    global running
    if not recorded_events:
        return
    while running:
        start_play = time.time()
        for key, event_type, timestamp in recorded_events:
            if not running:
                break
            now = time.time()
            wait_time = (start_play + timestamp) - now
            if wait_time > 0:
                time.sleep(wait_time)
            try:
                if event_type == 'press':
                    keyboard_controller.press(key.char if hasattr(key, 'char') and key.char else key)
                elif event_type == 'release':
                    keyboard_controller.release(key.char if hasattr(key, 'char') and key.char else key)
            except Exception:
                pass

# --- Управління режимами ---
def start_autoclick():
    """Запускає обраний режим"""
    if mode == 1:
        autoclick_mode1()
    elif mode == 2:
        autoclick_mode2()
    elif mode == 3:
        threading.Thread(target=play_recording, daemon=True).start()  # макро у окремому потоці

def toggle():
    """Перемикання старт/стоп"""
    if running:
        stop()
    else:
        start()

# --- Старт/стоп з затримкою 1 секунда ---
def start():
    """Запуск з 1 секундною затримкою"""
    global running
    if not running and mode in [1, 2, 3]:
        running = True
        status_var.set("Підготовка... 1 секунда")
        status_label.config(fg="orange")
        threading.Thread(target=delayed_start, daemon=True).start()

def delayed_start():
    """Виконується через 1 секунду після натискання старт"""
    time.sleep(1)
    status_var.set("Працює")
    status_label.config(fg="green")
    threading.Thread(target=start_autoclick, daemon=True).start()

def stop():
    """Зупинка роботи"""
    global running
    if running:
        running = False
        status_var.set("Зупинено")
        status_label.config(fg="red")

def select_mode(m):
    """Вибір режиму з автоматичною зупинкою роботи"""
    global mode
    stop()  # ✅ зупиняємо роботу при переключенні режиму
    mode = m
    if m == 1:
        mode_var.set("Споттер: Утримання ПКМ")
        hide_macro_buttons()
    elif m == 2:
        mode_var.set("Стрілець: ЛКМ + R кожні 100мс")
        hide_macro_buttons()
    elif m == 3:
        mode_var.set("Заряджаючий: Макрорекордер (клавіатура)")
        show_macro_buttons()
    mode_label.config(fg="blue")

def show_macro_buttons():
    """Показати кнопки для макросу"""
    btn_record.pack(pady=5)
    lbl_record_info.pack(pady=2)

def hide_macro_buttons():
    """Сховати кнопки для макросу"""
    btn_record.pack_forget()
    lbl_record_info.pack_forget()

# --- Глобальний слухач клавіатури (F6/F7) ---
def global_keyboard_listener():
    """Слухає натискання F6/F7 глобально"""
    def on_press(key):
        global running
        try:
            if key == keyboard.Key.f6:
                toggle()  # старт/стоп
            elif key == keyboard.Key.f7 and mode == 3 and not recording:
                start_recording()
        except:
            pass

    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()

# --- GUI ---
root = tk.Tk()
root.title("Автоклікер для артилерії")

# напис про затримку
delay_label = tk.Label(root, text="Виконання почнеться через 1 секунду після натискання кнопки Старт", font=("Arial", 10), fg="gray")
delay_label.pack(pady=5)

# кнопки вибору режиму
btn_mode1 = tk.Button(root, text="Споттер: Утримання ПКМ", width=30, command=lambda: select_mode(1))
btn_mode1.pack(pady=5)

btn_mode2 = tk.Button(root, text="Стрілець: ЛКМ + R кожні 100мс", width=30, command=lambda: select_mode(2))
btn_mode2.pack(pady=5)

btn_mode3 = tk.Button(root, text="Заряджаючий: Макро (клавіатура)", width=30, command=lambda: select_mode(3))
btn_mode3.pack(pady=5)

# керування
btn_start = tk.Button(root, text="Старт (F6)", width=20, command=start)
btn_start.pack(pady=5)

btn_stop = tk.Button(root, text="Стоп (F6)", width=20, command=stop)
btn_stop.pack(pady=5)

# для режиму 3 (макро)
btn_record = tk.Button(root, text="Запис макро (F7)", width=20, command=start_recording)
lbl_record_info = tk.Label(root, text="Зупинити запис: ЛКМ", font=("Arial", 10), fg="gray")

# статус режиму
mode_var = tk.StringVar(value="Режим не обрано")
mode_label = tk.Label(root, textvariable=mode_var, font=("Arial", 12), fg="gray")
mode_label.pack(pady=5)

# статус роботи
status_var = tk.StringVar(value="Зупинено")
status_label = tk.Label(root, textvariable=status_var, font=("Arial", 12), fg="red")
status_label.pack(pady=10)

# вихід
exit_btn = tk.Button(root, text="Вихід", width=20, command=root.destroy)
exit_btn.pack(pady=10)

# --- Запуск глобального слухача клавіатури одразу ---
threading.Thread(target=global_keyboard_listener, daemon=True).start()

root.mainloop()
