#!/usr/bin/env python3
"""
E-DICE GUI APPLICATION (macOS Ready)
"""

import tkinter as tk
from tkinter import ttk
import serial
import serial.tools.list_ports
import threading
import re

GRAVITY_THRESHOLD = 700

FACE_MAP = {
    'Z+': 1,   'Z-': 6,
    'Y+': 2,   'Y-': 5,
    'X+': 3,   'X-': 4,
}

DEFAULT_BAUD_RATE = 115200
SERIAL_TIMEOUT = 0.1
GUI_UPDATE_MS = 50
GLOW_ANIM_MS = 80

COLORS = {
    'bg_primary':     '#0d1117',
    'bg_secondary':   '#151b23',
    'bg_tertiary':    '#212830',
    'bg_hover':       '#292f38',
    'border':         '#30363d',
    'border_focus':   '#1f6feb',
    'text_primary':   '#e6edf3',
    'text_secondary': '#9198a1',
    'text_muted':     '#545d68',
    'cyan':           '#00e5ff',
    'blue':           '#58a6ff',
    'green':          '#3fb950',
    'red':            '#f85149',
    'orange':         '#d29922',
    'purple':         '#bc8cff',
    'dice_body':      '#171d2a',
    'dice_border':    '#2a3350',
    'dice_shadow':    '#070a10',
    'dice_highlight': '#222840',
    'dot_white':      '#ffffff',
    'dot_inner':      '#e8f0ff',
    'dot_glow':       '#4fc3f7',
    'bar_pos':        '#3fb950',
    'bar_neg':        '#f85149',
    'bar_bg':         '#212830',
}

DICE_DOTS = {
    1: [(0.50, 0.50)],
    2: [(0.70, 0.30), (0.30, 0.70)],
    3: [(0.70, 0.30), (0.50, 0.50), (0.30, 0.70)],
    4: [(0.28, 0.28), (0.72, 0.28), (0.28, 0.72), (0.72, 0.72)],
    5: [(0.28, 0.28), (0.72, 0.28), (0.50, 0.50), (0.28, 0.72), (0.72, 0.72)],
    6: [(0.28, 0.26), (0.72, 0.26), (0.28, 0.50), (0.72, 0.50), (0.28, 0.74), (0.72, 0.74)],
}

def determine_face(x: int, y: int, z: int):
    abs_x, abs_y, abs_z = abs(x), abs(y), abs(z)
    dominant = max(abs_x, abs_y, abs_z)
    if dominant < GRAVITY_THRESHOLD:
        return None
    if dominant == abs_z:
        key = 'Z+' if z > 0 else 'Z-'
    elif dominant == abs_y:
        key = 'Y+' if y > 0 else 'Y-'
    else:
        key = 'X+' if x > 0 else 'X-'
    return FACE_MAP.get(key)

def parse_serial_line(line: str):
    match = re.match(r'X:\s*(-?\d+),\s*Y:\s*(-?\d+),\s*Z:\s*(-?\d+)', line.strip())
    if match:
        return int(match.group(1)), int(match.group(2)), int(match.group(3))
    return None

class EDiceApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("E-Dice — Electronic Dice")
        self.root.configure(bg=COLORS['bg_primary'])
        self.root.resizable(True, True)
        self.root.minsize(720, 860)

        self.serial_port = None
        self.serial_thread = None
        self.running = False
        self.current_face = None
        self.prev_face = None
        self.x_val = self.y_val = self.z_val = 0
        self.glow_phase = 0.0
        self.glow_dir = 1
        self.flash_count = 0
        self.last_raw_line = ""

        # UI BUILDING (Correct Order for packing)
        self._build_header()
        self._build_dice_area()
        self._build_sensor_panel()
        self._build_connection_panel()
        self._build_status_bar()

        # Init Ports AFTER status bar exists
        self._scan_ports()

        self._tick_glow()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_header(self):
        hdr = tk.Frame(self.root, bg=COLORS['bg_primary'])
        hdr.pack(fill='x', padx=32, pady=(22, 4))
        tk.Label(hdr, text="🎲  E-DICE", bg=COLORS['bg_primary'], fg=COLORS['text_primary'], font=('Segoe UI', 26, 'bold')).pack(side='left')
        self.ind_canvas = tk.Canvas(hdr, width=14, height=14, bg=COLORS['bg_primary'], highlightthickness=0)
        self.ind_canvas.pack(side='right', padx=(0, 6), pady=12)
        self.conn_text = tk.Label(hdr, text="Disconnected", bg=COLORS['bg_primary'], fg=COLORS['red'], font=('Segoe UI', 11))
        self.conn_text.pack(side='right', pady=12)
        self._paint_indicator(False)
        sub = tk.Frame(self.root, bg=COLORS['bg_primary'])
        sub.pack(fill='x', padx=32, pady=(0, 8))
        tk.Label(sub, text="STM32L476RG  ·  X-NUCLEO-IKS01A3  ·  Accelerometer Dice", bg=COLORS['bg_primary'], fg=COLORS['text_muted'], font=('Segoe UI', 9)).pack(side='left')
        tk.Canvas(self.root, height=1, bg=COLORS['border'], highlightthickness=0).pack(fill='x', padx=32, pady=(0, 6))

    def _paint_indicator(self, connected: bool):
        c = self.ind_canvas
        c.delete('all')
        clr = COLORS['green'] if connected else COLORS['red']
        c.create_oval(2, 2, 12, 12, fill=clr, outline=clr)

    def _build_dice_area(self):
        frame = tk.Frame(self.root, bg=COLORS['bg_primary'])
        frame.pack(fill='both', expand=True, padx=32, pady=(6, 4))
        self.dice_canvas = tk.Canvas(frame, bg=COLORS['bg_primary'], highlightthickness=0, width=360, height=360)
        self.dice_canvas.pack(pady=(10, 2))
        self.face_number = tk.Label(frame, text="—", bg=COLORS['bg_primary'], fg=COLORS['cyan'], font=('Segoe UI', 48, 'bold'))
        self.face_number.pack(pady=(0, 0))
        self.face_hint = tk.Label(frame, text="Waiting for data…", bg=COLORS['bg_primary'], fg=COLORS['text_muted'], font=('Segoe UI', 12))
        self.face_hint.pack(pady=(0, 6))
        self._draw_dice(None)

    def _rounded_rect(self, cvs, x1, y1, x2, y2, r, **kw):
        pts = [x1+r, y1, x2-r, y1, x2, y1, x2, y1+r, x2, y2-r, x2, y2, x2-r, y2, x1+r, y2, x1, y2, x1, y2-r, x1, y1+r, x1, y1]
        return cvs.create_polygon(pts, smooth=True, **kw)

    def _draw_dice(self, face, glow_extra=0, flash=False):
        c = self.dice_canvas
        c.delete('all')
        cw, ch = 360, 360
        size = 270
        x0 = (cw - size) // 2
        y0 = (ch - size) // 2
        rad = 28
        so = 10
        self._rounded_rect(c, x0+so, y0+so, x0+size+so, y0+size+so, rad, fill=COLORS['dice_shadow'], outline='')
        body_fill = '#222840' if flash else COLORS['dice_body']
        self._rounded_rect(c, x0, y0, x0+size, y0+size, rad, fill=body_fill, outline=COLORS['dice_border'], width=2)
        self._rounded_rect(c, x0+4, y0+4, x0+size-4, y0+8, rad-2, fill=COLORS['dice_highlight'], outline='')
        if face is not None and face in DICE_DOTS:
            dot_r = 19
            glow_r = dot_r + 7 + int(glow_extra)
            for dx, dy in DICE_DOTS[face]:
                cx = x0 + size * dx
                cy = y0 + size * dy
                c.create_oval(cx-glow_r, cy-glow_r, cx+glow_r, cy+glow_r, fill='', outline=COLORS['dot_glow'], width=2)
                c.create_oval(cx-dot_r, cy-dot_r, cx+dot_r, cy+dot_r, fill=COLORS['dot_white'], outline='')
                hr = dot_r * 0.45
                ho = -dot_r * 0.22
                c.create_oval(cx+ho-hr, cy+ho-hr, cx+ho+hr, cy+ho+hr, fill=COLORS['dot_inner'], outline='')
        else:
            c.create_text(cw//2, ch//2, text="?", fill=COLORS['text_muted'], font=('Segoe UI', 80, 'bold'))

    def _build_sensor_panel(self):
        border = tk.Frame(self.root, bg=COLORS['border'], padx=1, pady=1)
        border.pack(fill='x', padx=32, pady=(4, 8))
        panel = tk.Frame(border, bg=COLORS['bg_secondary'], padx=22, pady=5)
        panel.pack(fill='x')
        tk.Label(panel, text="ACCELEROMETER  DATA", bg=COLORS['bg_secondary'], fg=COLORS['text_muted'], font=('Segoe UI', 9, 'bold')).pack(anchor='w', pady=(0, 8))
        axis_clr = {'X': COLORS['red'], 'Y': COLORS['green'], 'Z': COLORS['blue']}
        self.axis_val_labels = {}
        self.axis_bars = {}
        for axis in ('X', 'Y', 'Z'):
            row = tk.Frame(panel, bg=COLORS['bg_secondary'])
            row.pack(fill='x', pady=3)
            tk.Label(row, text=f" {axis} ", bg=COLORS['bg_secondary'], fg=axis_clr[axis], font=('Consolas', 13, 'bold'), width=3).pack(side='left')
            vl = tk.Label(row, text="   0 mg", bg=COLORS['bg_secondary'], fg=COLORS['text_primary'], font=('Consolas', 12), width=10, anchor='e')
            vl.pack(side='left', padx=(4, 14))
            self.axis_val_labels[axis] = vl
            bar = tk.Canvas(row, height=18, bg=COLORS['bar_bg'], highlightthickness=0)
            bar.pack(side='left', fill='x', expand=True)
            self.axis_bars[axis] = bar
        self.raw_label = tk.Label(panel, text="", bg=COLORS['bg_secondary'], fg=COLORS['text_muted'], font=('Consolas', 9), anchor='w')
        self.raw_label.pack(anchor='w', pady=(8, 0))

    def _refresh_bars(self):
        vals = {'X': self.x_val, 'Y': self.y_val, 'Z': self.z_val}
        max_mg = 1200
        for axis, v in vals.items():
            cvs = self.axis_bars[axis]
            cvs.delete('all')
            w = cvs.winfo_width()
            h = cvs.winfo_height()
            if w < 2: continue
            mid = w // 2
            cvs.create_line(mid, 0, mid, h, fill=COLORS['border'], width=1)
            bar_px = int((v / max_mg) * (w / 2))
            bar_px = max(-w//2, min(w//2, bar_px))
            if bar_px > 0:
                cvs.create_rectangle(mid, 2, mid+bar_px, h-2, fill=COLORS['bar_pos'], outline='')
            elif bar_px < 0:
                cvs.create_rectangle(mid+bar_px, 2, mid, h-2, fill=COLORS['bar_neg'], outline='')
            self.axis_val_labels[axis].config(text=f"{v:+5d} mg")
        self.raw_label.config(text=f"RAW  {self.last_raw_line}")

    def _build_connection_panel(self):
        border = tk.Frame(self.root, bg=COLORS['border'], padx=1, pady=1)
        border.pack(fill='x', padx=32, pady=(0, 8))
        panel = tk.Frame(border, bg=COLORS['bg_secondary'], padx=22, pady=12)
        panel.pack(fill='x')
        tk.Label(panel, text="CONNECTION", bg=COLORS['bg_secondary'], fg=COLORS['text_muted'], font=('Segoe UI', 9, 'bold')).pack(anchor='w', pady=(0, 6))
        row = tk.Frame(panel, bg=COLORS['bg_secondary'])
        row.pack(fill='x')
        tk.Label(row, text="Port", bg=COLORS['bg_secondary'], fg=COLORS['text_secondary'], font=('Segoe UI', 10)).pack(side='left', padx=(0, 4))
        
        self.port_var = tk.StringVar()
        # Increased width to 28 for macOS long port names like /dev/cu.usbmodem...
        self.port_combo = ttk.Combobox(row, textvariable=self.port_var, width=28, state='readonly', font=('Consolas', 10))
        self.port_combo.pack(side='left', padx=(0, 6))
        
        tk.Button(row, text="⟳", command=self._scan_ports, font=('Segoe UI', 13)).pack(side='left', padx=(0, 14))
        
        tk.Label(row, text="Baud", bg=COLORS['bg_secondary'], fg=COLORS['text_secondary'], font=('Segoe UI', 10)).pack(side='left', padx=(0, 4))
        self.baud_var = tk.StringVar(value=str(DEFAULT_BAUD_RATE))
        ttk.Combobox(row, textvariable=self.baud_var, width=9, state='readonly', font=('Consolas', 10), values=('9600', '19200', '38400', '57600', '115200', '230400', '460800')).pack(side='left', padx=(0, 18))
        
        # Mac-compatible button without background colors
        self.btn_conn = tk.Button(row, text="⚡  Connect", command=self._toggle_connection, font=('Segoe UI', 15, 'bold'))
        self.btn_conn.pack(side='right')

    def _scan_ports(self):
        ports = sorted(p.device for p in serial.tools.list_ports.comports())
        self.port_combo['values'] = ports
        if ports:
            self.port_combo.current(0)
        self._set_status(f"Found {len(ports)} serial port(s)")

    def _build_status_bar(self):
        bar = tk.Frame(self.root, bg=COLORS['bg_tertiary'], height=28)
        bar.pack(fill='x', side='bottom')
        bar.pack_propagate(False)
        self.status_lbl = tk.Label(bar, text="  Ready — select a COM port and click Connect", bg=COLORS['bg_tertiary'], fg=COLORS['text_muted'], font=('Segoe UI', 9), anchor='w')
        self.status_lbl.pack(fill='x', padx=8, pady=4)

    def _set_status(self, msg: str):
        self.status_lbl.config(text=f"  {msg}")

    def _toggle_connection(self):
        if self.running:
            self._disconnect()
        else:
            self._connect()

    def _connect(self):
        port = self.port_var.get()
        baud = int(self.baud_var.get())
        if not port:
            self._set_status("⚠  No port selected")
            return
        try:
            self.serial_port = serial.Serial(port, baud, timeout=SERIAL_TIMEOUT)
            self.running = True
            self.btn_conn.config(text="⏹  Disconnect")
            self.conn_text.config(text=f"Connected  ({port})", fg=COLORS['green'])
            self._paint_indicator(True)
            self.port_combo.config(state='disabled')
            self._set_status(f"✓  Connected to {port} @ {baud} baud")
            self.serial_thread = threading.Thread(target=self._reader_loop, daemon=True)
            self.serial_thread.start()
            self._gui_poll()
        except serial.SerialException as exc:
            self._set_status(f"✗  Connection failed: {exc}")
            self.running = False

    def _disconnect(self):
        self.running = False
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.close()
            except Exception:
                pass
        self.btn_conn.config(text="⚡  Connect")
        self.conn_text.config(text="Disconnected", fg=COLORS['red'])
        self._paint_indicator(False)
        self.port_combo.config(state='readonly')
        self._set_status("Disconnected")

    def _reader_loop(self):
        while self.running:
            try:
                if self.serial_port and self.serial_port.is_open:
                    raw = self.serial_port.readline()
                    if raw:
                        line = raw.decode('utf-8', errors='ignore').strip()
                        self.last_raw_line = line
                        parsed = parse_serial_line(line)
                        if parsed:
                            self.x_val, self.y_val, self.z_val = parsed
                            self.current_face = determine_face(*parsed)
            except (serial.SerialException, OSError):
                self.running = False
                self.root.after(0, self._disconnect)
                break
            except Exception:
                pass

    def _gui_poll(self):
        if not self.running: return
        self._refresh_bars()
        face = self.current_face
        if face != self.prev_face:
            self.prev_face = face
            self.flash_count = 4
            if face is not None:
                self.face_number.config(text=str(face))
                self.face_hint.config(text=f"Face {face} is pointing UP", fg=COLORS['cyan'])
            else:
                self.face_number.config(text="—")
                self.face_hint.config(text="Cube is in motion…", fg=COLORS['orange'])
        self.root.after(GUI_UPDATE_MS, self._gui_poll)

    def _tick_glow(self):
        self.glow_phase += self.glow_dir * 0.6
        if self.glow_phase >= 5: self.glow_dir = -1
        elif self.glow_phase <= 0: self.glow_dir = 1
        flash = self.flash_count > 0
        if flash: self.flash_count -= 1
        self._draw_dice(self.current_face, glow_extra=self.glow_phase, flash=flash)
        self.root.after(GLOW_ANIM_MS, self._tick_glow)

    def _on_close(self):
        self.running = False
        if self.serial_port and self.serial_port.is_open:
            try: self.serial_port.close()
            except Exception: pass
        self.root.destroy()

def main():
    root = tk.Tk()
    root.geometry("740x920")
    root.update_idletasks()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"740x920+{(sw-740)//2}+{(sh-920)//2}")
    EDiceApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()