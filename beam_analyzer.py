


# ===================== Mechanical Beam Analyzer — Fixed & Enhanced =====================
# PART 1/4: Imports, utilities, materials (full), Beam model

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import matplotlib.pyplot as plt
import numpy as np
import csv, os, json
from matplotlib.backends.backend_pdf import PdfPages

# Materials Project API client (optional)
try:
    from mp_api.client import MPRester  # pip install mp-api
    HAVE_MP = True
except Exception:
    HAVE_MP = False

# --- Default Materials Project API Key (user can change in UI) ---
DEFAULT_MP_API_KEY = "k63ZJgHvzrbGVRFbFvXOIRCiY253eiLP"


# ==================== Tooltip Helper ====================
class Tooltip:
    def __init__(self, widget, text, delay_ms=350):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self.tip = None
        self._after = None
        widget.bind("<Enter>", self._schedule)
        widget.bind("<Leave>", self._hide)
        widget.bind("<ButtonPress>", self._hide)

    def _schedule(self, _e):
        self._after = self.widget.after(self.delay_ms, self._show)

    def _show(self):
        if self.tip or not self.text:
            return
        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self.tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        dark = getattr(self.widget, "_dark_mode", False)
        bg = "#111827" if dark else "#ffffe0"
        fg = "#e5e7eb" if dark else "#000000"
        lbl = tk.Label(
            tw, text=self.text, justify="left",
            background=bg, foreground=fg,
            relief="solid", borderwidth=1,
            font=("Segoe UI", 9), padx=6, pady=3
        )
        lbl.pack()

    def _hide(self, _e=None):
        if self._after:
            self.widget.after_cancel(self._after)
            self._after = None
        if self.tip:
            self.tip.destroy()
            self.tip = None


# ==================== Scrollable Frame (content area) ====================
class ScrollableFrame(ttk.Frame):
    """Scroll container that hosts a 'body' frame."""
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        self.canvas = tk.Canvas(self, highlightthickness=0, bd=0)
        self.vbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vbar.set)

        self.vbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.body = ttk.Frame(self.canvas)
        self._body_id = self.canvas.create_window((0, 0), window=self.body, anchor="nw")

        self.body.bind("<Configure>", self._on_body_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # mouse wheel
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)      # Win/mac
        self.canvas.bind_all("<Button-4>", self._on_mousewheel_linux)  # Linux up
        self.canvas.bind_all("<Button-5>", self._on_mousewheel_linux)  # Linux down

    def _on_body_configure(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self._body_id, width=event.width)

    def _on_mousewheel(self, event):
        step = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(step, "units")

    def _on_mousewheel_linux(self, event):
        step = -1 if event.num == 4 else 1
        self.canvas.yview_scroll(step, "units")


# ==================== Utilities ====================
def sci_notation(val):
    """Format numbers like 2.50*10^8 instead of 2.5e8."""
    try:
        f = float(val)
        if f == 0:
            return "0"
        exp = int(np.floor(np.log10(abs(f))))
        base = f / (10 ** exp)
        return f"{base:.3f}*10^{exp}"
    except Exception:
        return str(val)

def pad_limits(values, frac=0.12):
    vmin = float(np.nanmin(values)) if np.size(values) else 0.0
    vmax = float(np.nanmax(values)) if np.size(values) else 0.0
    if vmin == vmax == 0.0:
        return (-1.0, 1.0)
    span = vmax - vmin
    if span == 0:
        pad = max(abs(vmax), 1.0) * frac
        return (vmin - pad, vmax + pad)
    pad = span * frac
    if vmin < 0 < vmax:
        m = max(abs(vmin), abs(vmax))
        return (-m - pad, m + pad)
    return (vmin - pad, vmax + pad)


# ==================== Built-in Materials (100+ common) ====================
BUILTIN_MATERIALS = {
    # --- Steels (carbon, alloy, structural) ---
    "Carbon Steel 1018": (2.05e11, 3.70e8),
    "Carbon Steel 1020": (2.05e11, 3.50e8),
    "Carbon Steel 1040": (2.05e11, 4.50e8),
    "Carbon Steel 1045": (2.05e11, 5.30e8),
    "Carbon Steel 1060": (2.05e11, 6.20e8),
    "Carbon Steel 1095 (Spring)": (2.05e11, 8.00e8),
    "Carbon Steel A36": (2.00e11, 2.50e8),
    "Carbon Steel AISI 4140 (QT)": (2.10e11, 6.55e8),
    "Alloy Steel 4340 (QT)": (2.10e11, 1.00e9),
    "Alloy Steel 8620": (2.05e11, 6.20e8),
    "HSLA Steel A572-50": (2.00e11, 3.45e8),
    "HSLA Steel A992": (2.00e11, 3.45e8),
    "Tool Steel D2": (2.10e11, 5.50e8),
    "Tool Steel O1": (2.10e11, 5.00e8),
    "Tool Steel H13": (2.10e11, 1.40e9),

    # --- Stainless steels ---
    "Stainless Steel 301": (1.93e11, 2.75e8),
    "Stainless Steel 302": (1.93e11, 2.75e8),
    "Stainless Steel 303": (1.93e11, 2.15e8),
    "Stainless Steel 304": (1.93e11, 2.15e8),
    "Stainless Steel 304L": (1.93e11, 1.70e8),
    "Stainless Steel 316": (1.93e11, 2.90e8),
    "Stainless Steel 316L": (1.93e11, 1.70e8),
    "Stainless Steel 321": (1.93e11, 2.05e8),
    "Stainless Steel 347": (1.93e11, 2.05e8),
    "Stainless Steel 409": (2.00e11, 2.00e8),
    "Stainless Steel 410": (2.00e11, 2.75e8),
    "Stainless Steel 420": (2.00e11, 5.00e8),
    "Stainless Steel 430": (2.00e11, 2.75e8),
    "Stainless Steel 17-4PH": (1.96e11, 1.10e9),

    # --- Aluminum alloys ---
    "Aluminum 1100-O": (6.90e10, 3.40e7),
    "Aluminum 2024-T3": (7.30e10, 3.20e8),
    "Aluminum 3003-H14": (6.90e10, 1.45e8),
    "Aluminum 5052-H32": (7.00e10, 1.93e8),
    "Aluminum 5083-H116": (7.00e10, 2.15e8),
    "Aluminum 6061-T4": (6.90e10, 1.45e8),
    "Aluminum 6061-T6": (6.90e10, 2.70e8),
    "Aluminum 6063-T5": (6.90e10, 1.45e8),
    "Aluminum 6063-T6": (6.90e10, 2.40e8),
    "Aluminum 7075-T6": (7.20e10, 5.00e8),
    "Aluminum 7075-T73": (7.20e10, 4.30e8),

    # --- Titanium ---
    "Titanium Grade 2": (1.05e11, 3.40e8),
    "Titanium Grade 4": (1.05e11, 4.80e8),
    "Titanium Ti-6Al-4V (Grade 5)": (1.14e11, 8.80e8),
    "Titanium Ti-6Al-4V ELI (Gr 23)": (1.14e11, 7.60e8),

    # --- Nickel / Cobalt / Superalloys ---
    "Inconel 625": (2.05e11, 7.60e8),
    "Inconel 718": (2.10e11, 1.00e9),
    "Hastelloy C-276": (2.06e11, 3.50e8),
    "Monel 400": (1.79e11, 1.70e8),
    "Nickel 200": (2.06e11, 1.48e8),
    "Cobalt-Chrome (CoCr)": (2.30e11, 6.00e8),

    # --- Copper & friends ---
    "Copper C11000": (1.10e11, 7.00e7),
    "Copper C10100 (OFHC)": (1.10e11, 6.90e7),
    "Brass 260 (Cartridge)": (1.00e11, 2.00e8),
    "Brass 360 (Free-Cutting)": (1.00e11, 2.10e8),
    "Bronze (Phosphor)": (1.10e11, 2.40e8),

    # --- Magnesium / Zinc / Lead / Others ---
    "Magnesium AZ31B": (4.50e10, 2.00e8),
    "Magnesium AZ91D": (4.50e10, 1.60e8),
    "Zinc": (1.08e11, 5.50e7),
    "Lead": (1.60e10, 1.20e7),
    "Molybdenum": (3.30e11, 5.50e8),
    "Tungsten": (4.00e11, 5.50e8),
    "Beryllium": (2.87e11, 2.40e8),

    # --- Structural (common specs) ---
    "ASTM A500 Gr B (Tube)": (2.00e11, 3.17e8),
    "ASTM A500 Gr C (Tube)": (2.00e11, 3.45e8),
    "ASTM A53 Gr B (Pipe)": (2.00e11, 2.40e8),

    # --- Polymers (engineering plastics) ---
    "ABS": (2.00e9, 3.50e7),
    "Acetal (POM, Delrin)": (3.00e9, 6.90e7),
    "Acrylic (PMMA)": (3.20e9, 6.00e7),
    "Nylon 6": (2.50e9, 6.50e7),
    "Nylon 6/6": (2.80e9, 7.00e7),
    "Nylon 12": (1.60e9, 4.50e7),
    "Polycarbonate": (2.30e9, 7.00e7),
    "PEEK": (3.60e9, 9.00e7),
    "UHMW-PE": (0.80e9, 2.00e7),
    "HDPE": (1.00e9, 2.50e7),
    "LDPE": (2.00e9, 2.00e7),
    "PP (Polypropylene)": (1.50e9, 3.00e7),
    "PET": (2.70e9, 6.00e7),
    "PTFE (Teflon)": (0.50e9, 2.00e7),
    "PVC (Rigid)": (2.90e9, 5.50e7),
    "PS (Polystyrene)": (3.00e9, 4.00e7),
    "SAN": (2.20e9, 5.00e7),
    "PC-ABS (Blend)": (2.50e9, 5.50e7),
    "PEI (Ultem)": (3.20e9, 1.10e8),
    "PBT": (2.40e9, 5.50e7),
    "PPS": (3.00e9, 1.00e8),

    # --- Composites / Fibers / Laminates ---
    "Carbon Fiber/Epoxy (UD)": (1.45e11, 6.00e8),
    "Carbon Fiber/Epoxy (Woven)": (7.00e10, 4.00e8),
    "Glass Fiber/Epoxy (E-glass)": (4.00e10, 3.50e8),
    "Kevlar/Epoxy": (7.00e10, 3.60e8),
    "G10/FR4": (2.40e10, 3.10e8),

    # --- Ceramics / Glass ---
    "Alumina (Al2O3, 95%)": (3.00e11, 2.50e8),
    "Zirconia (Y-TZP)": (2.10e11, 1.20e9),
    "Silicon Carbide (SiC)": (4.50e11, 4.00e8),
    "Silicon Nitride (Si3N4)": (3.05e11, 8.00e8),
    "Glass (Soda-lime)": (7.00e10, 1.00e8),
    "Glass (Borosilicate)": (6.40e10, 1.20e8),
    "Fused Silica": (7.20e10, 5.00e7),
    "Silicon (single-crystal)": (1.30e11, 7.00e9),

    # --- Concrete / Masonry ---
    "Concrete (Normal Strength)": (3.00e10, 3.00e7),
    "Concrete (High Strength)": (4.00e10, 6.00e7),
    "Mortar": (1.50e10, 1.50e7),

    # --- Woods (typical along grain) ---
    "Wood (Pine)": (8.00e9, 4.00e7),
    "Wood (Douglas Fir)": (1.20e10, 5.00e7),
    "Wood (Oak)": (1.10e10, 6.00e7),
    "Wood (Maple)": (1.10e10, 6.00e7),
    "Wood (Birch)": (1.05e10, 5.50e7),
    "Wood (Teak)": (1.20e10, 6.00e7),
    "Bamboo": (1.10e10, 1.60e8),

    "Custom / Add New…": (None, None),
}
def sort_material_keys(d):
    keys = [k for k in d.keys() if k != "Custom / Add New…"]
    keys.sort(key=lambda s: s.lower())
    keys.append("Custom / Add New…")
    return keys


# ==================== Beam Model ====================
class Beam:
    def __init__(self, beam_type, load_type, length, load, E, I, c,
                 material="Custom", yield_strength=None, a=None):
        self.beam_type = beam_type
        self.load_type = load_type
        self.length = length
        self.load = load
        self.E = E
        self.I = I
        self.c = c
        self.material = material
        self.yield_strength = yield_strength
        self.a = a

    def diagrams(self, n=601):
        L = self.length
        x = np.linspace(0.0, L, n)
        P_or_w = self.load
        b = self.beam_type
        case = self.load_type
        V = np.zeros_like(x)
        M = np.zeros_like(x)

        if b == "Simply Supported":
            if case == "Point Load (Center)":
                P = P_or_w; R = P/2
                V = np.where(x < L/2, R, R - P)
                M = np.where(x <= L/2, R*x, R*x - P*(x - L/2))
            elif case == "Point Load (Any Position)":
                P = P_or_w; a = self.a if self.a is not None else L/2
                R1 = P * (L - a) / L
                V = np.where(x < a, R1, R1 - P)
                M = np.where(x < a, R1*x, R1*x - P*(x - a))
            elif case == "UDL (Uniformly Distributed Load)":
                w = P_or_w; R = w*L/2
                V = R - w*x
                M = R*x - 0.5*w*x**2
            elif case == "Applied Moment (Center)":
                M0 = P_or_w
                V = np.zeros_like(x)
                M = np.where(x < L/2, 0.0, M0)

        elif b == "Cantilever":
            if case == "Point Load (End)":
                P = P_or_w
                V = -P * np.ones_like(x)
                M = -P * (L - x)
            elif case == "UDL (Uniformly Distributed Load)":
                w = P_or_w
                V = -w*(L - x)
                M = -0.5*w*(L - x)**2
            elif case == "Applied Moment (End)":
                M0 = P_or_w
                V = np.zeros_like(x)
                M = np.full_like(x, M0)

        elif b == "Fixed-Fixed":
            if case == "UDL (Uniformly Distributed Load)":
                w = P_or_w
                R = w*L/2
                M_A = -w*L**2/12.0
                V = R - w*x
                M = R*x - 0.5*w*x**2 + M_A
            elif case == "Point Load (Center)":
                P = P_or_w
                R = P/2
                M_A = -P*L/8.0
                M = np.where(x <= L/2, R*x + M_A, R*x - P*(x - L/2) + M_A)
                V = np.where(x < L/2, R, R - P)

        return x, V, M

    def deflection(self, x, M):
        EI = self.E * self.I
        if EI == 0:
            return np.zeros_like(x)
        k = M / EI
        I1 = np.cumsum(np.concatenate([[0.0], 0.5*(k[1:] + k[:-1]) * np.diff(x)]))
        I2 = np.cumsum(np.concatenate([[0.0], 0.5*(I1[1:] + I1[:-1]) * np.diff(x)]))

        # boundary conditions
        if self.beam_type == "Cantilever":
            C1, C2 = 0.0, 0.0
        elif self.beam_type == "Simply Supported":
            C2 = 0.0
            C1 = -I2[-1] / (x[-1] if x[-1] != 0 else 1.0)
        elif self.beam_type == "Fixed-Fixed":
            # approximate by enforcing zero deflection at both ends
            C2 = 0.0
            C1 = -I2[-1] / (x[-1] if x[-1] != 0 else 1.0)
        else:
            C1 = 0.0; C2 = 0.0
        return I2 + C1*x + C2

    def reactions(self):
        L = self.length; case = self.load_type; b = self.beam_type; d = {}
        if b == "Simply Supported":
            if case == "Point Load (Center)":
                P = self.load; d["RA"] = P/2; d["RB"] = P/2
            elif case == "Point Load (Any Position)":
                P = self.load; a = self.a if self.a is not None else L/2
                d["RA"] = P*(L - a)/L; d["RB"] = P*a/L
            elif case == "UDL (Uniformly Distributed Load)":
                w = self.load; W = w*L; d["RA"] = W/2; d["RB"] = W/2
            elif case == "Applied Moment (Center)":
                M0 = self.load; d["MA@A"] = M0/2; d["MB@B"] = -M0/2
        elif b == "Cantilever":
            if case == "Point Load (End)":
                P = self.load; d["V@fix"] = P; d["M@fix"] = P*L
            elif case == "UDL (Uniformly Distributed Load)":
                w = self.load; d["V@fix"] = w*L; d["M@fix"] = w*L**2/2
            elif case == "Applied Moment (End)":
                M0 = self.load; d["V@fix"] = 0.0; d["M@fix"] = M0
        elif b == "Fixed-Fixed":
            if case == "UDL (Uniformly Distributed Load)":
                w = self.load
                d["RA"] = w*L/2; d["RB"] = w*L/2
                d["MA@A"] = w*L**2/12; d["MB@B"] = -w*L**2/12
            elif case == "Point Load (Center)":
                P = self.load
                d["RA"] = P/2; d["RB"] = P/2
                d["MA@A"] = P*L/8; d["MB@B"] = -P*L/8
        return d

    def bending_stress(self):
        x, _, M = self.diagrams()
        Mabs = np.max(np.abs(M))
        if self.I == 0 or self.c is None:
            return None
        return (Mabs * self.c) / self.I

    def safety_factor(self):
        s = self.bending_stress()
        if self.yield_strength and s not in (None, 0):
            return self.yield_strength / s
        return None

    def plot_all(self):
        x, V, M = self.diagrams()
        y = self.deflection(x, M)

        c_shear = "#5B8DEF"    # soft blue
        c_moment = "#F2694E"   # warm amber
        c_defl = "#66C2A5"     # gentle green

        fig = plt.figure(figsize=(10, 11))
        fig.suptitle(f"{self.beam_type} – {self.load_type}", fontsize=14)

        ax1 = fig.add_subplot(3, 1, 1)
        ax1.plot(x, V, linewidth=2.2, linestyle="-", color=c_shear, label="Shear Force V(x) [N]")
        ax1.set_title("Shear Force", fontsize=12); ax1.set_ylabel("V (N)")
        ax1.grid(True, alpha=0.3); ax1.legend(loc="best"); ax1.axhline(0, linewidth=0.8)
        ax1.set_ylim(*pad_limits(V))

        ax2 = fig.add_subplot(3, 1, 2)
        ax2.plot(x, M, linewidth=2.2, linestyle="-", color=c_moment, label="Bending Moment M(x) [Nm]")
        ax2.set_title("Bending Moment", fontsize=12); ax2.set_ylabel("M (Nm)")
        ax2.grid(True, alpha=0.3); ax2.legend(loc="best"); ax2.axhline(0, linewidth=0.8)
        ax2.set_ylim(*pad_limits(M))

        ax3 = fig.add_subplot(3, 1, 3)
        ax3.plot(x, y, linewidth=2.2, linestyle="-", color=c_defl, label="Deflection δ(x) [m]")
        ax3.set_title("Deflection", fontsize=12); ax3.set_xlabel("Position x (m)"); ax3.set_ylabel("δ (m)")
        ax3.grid(True, alpha=0.3); ax3.legend(loc="best"); ax3.axhline(0, linewidth=0.8)
        ax3.set_ylim(*pad_limits(y))

        plt.tight_layout(rect=[0, 0, 1, 0.96])
        plt.show()



# ===================== PART 2/4: App GUI (layout, inputs, sticky bottom bar) =====================

class BeamApp:
    def __init__(self, root):
        self.root = root
        root.title("Mechanical Beam Analyzer")
        root.geometry("1060x880")
        self.root.minsize(860, 540)

        # Theme colors (eye-soothing)
        self._light_bg = "#f6f8fb"; self._light_card = "#eef4fb"
        self._dark_bg  = "#0f172a"; self._dark_card  = "#111827"
        self._light_text = "#1f2937"; self._dark_text = "#e5e7eb"
        self._accent = "#93c5fd"; self._dark_mode = False

        style = ttk.Style()
        try: style.theme_use("clam")
        except tk.TclError: pass

        root.configure(bg=self._light_bg)
        style.configure("TFrame", background=self._light_bg)
        style.configure("Card.TFrame", background=self._light_card)
        style.configure("TLabel", background=self._light_bg, foreground=self._light_text, font=("Segoe UI", 10))
        style.configure("Card.TLabel", background=self._light_card, foreground=self._light_text, font=("Segoe UI", 10))
        style.configure("Section.TLabel", background=self._light_bg, foreground="#203040", font=("Segoe UI Semibold", 13))
        style.configure("Hint.TLabel", background=self._light_card, foreground="#586174", font=("Segoe UI", 9))
        style.configure("TButton", font=("Segoe UI", 10, "bold"), padding=6)
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"), padding=6)
        style.configure("TCombobox", fieldbackground="white", font=("Segoe UI", 10))
        style.configure("TEntry", fieldbackground="white", font=("Consolas", 11))

        # ----- Layout: scrollable content + sticky bottom bar -----
        self.container = ttk.Frame(root, style="TFrame"); self.container.pack(fill="both", expand=True)
        # Grid with two rows: scrollable (row 0) and sticky bottom (row 1)
        self.container.rowconfigure(0, weight=1)
        self.container.columnconfigure(0, weight=1)

        # Scrollable host (row 0)
        self.scroller = ScrollableFrame(self.container)
        self.scroller.grid(row=0, column=0, sticky="nsew")
        host = self.scroller.body

        # Sticky bottom action bar (row 1) — always visible even when window is tiny
        self.bottom_bar = ttk.Frame(self.container, style="Card.TFrame", padding=(10, 8))
        self.bottom_bar.grid(row=1, column=0, sticky="ew")
        self.container.bind("<Configure>", self._refresh_scrollregion)

        # ----- Menu -----
        menubar = tk.Menu(root)
        mat_menu = tk.Menu(menubar, tearoff=0)
        mat_menu.add_command(label="Fetch E from Materials Project…", command=self.fetch_E_from_mp)
        mat_menu.add_command(label="Suggest Common Formulas…", command=self.suggest_formulas)
        mat_menu.add_separator()
        mat_menu.add_command(label="Set/Change MP API Key…", command=self.set_mp_key)
        menubar.add_cascade(label="Materials (API)", menu=mat_menu)
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Toggle Dark Mode", command=self.toggle_dark)
        menubar.add_cascade(label="View", menu=view_menu)
        root.config(menu=menubar)
        self.mp_api_key = DEFAULT_MP_API_KEY

        # Materials store (merge CSV if exists)
        self.materials = dict(BUILTIN_MATERIALS)
        self.default_csv = "materials_db.csv"
        if os.path.exists(self.default_csv):
            self._import_materials(self.default_csv, silent=True)

        # ---------- Beam Setup ----------
        ttk.Label(host, text="Beam Setup", style="Section.TLabel").pack(anchor="w", padx=14, pady=(12, 4))
        frame_setup = ttk.Frame(host, style="Card.TFrame", padding=14); frame_setup.pack(fill="x", padx=12)
        r = 0
        ttk.Label(frame_setup, text="Select Beam Type", style="Card.TLabel").grid(row=r, column=0, sticky="w", pady=(0,2))
        self.beam_type_var = tk.StringVar(value="Simply Supported")
        self.cmb_beam = ttk.Combobox(frame_setup, textvariable=self.beam_type_var, width=34,
                                     values=["Simply Supported", "Cantilever", "Fixed-Fixed"], state="readonly")
        self.cmb_beam.grid(row=r, column=1, sticky="ew", padx=(0,8))

        r += 1
        ttk.Label(frame_setup, text="Select Load Type", style="Card.TLabel").grid(row=r, column=0, sticky="w", pady=(6,2))
        self.load_type_var = tk.StringVar(value="Point Load (Center)")
        self.cmb_load = ttk.Combobox(frame_setup, textvariable=self.load_type_var, width=34, values=[
            "Point Load (Center)","Point Load (Any Position)","UDL (Uniformly Distributed Load)",
            "Point Load (End)","Applied Moment (Center)","Applied Moment (End)",
            "Point Load (Center) [Fixed-Fixed]"
        ], state="readonly")
        self.cmb_load.grid(row=r, column=1, sticky="ew", padx=(0,8), pady=(6,2))
        self.cmb_load.bind("<<ComboboxSelected>>", self._on_load_change)
        self.cmb_beam.bind("<<ComboboxSelected>>", self._on_load_change)
        frame_setup.columnconfigure(1, weight=1)

        # ---------- Loading ----------
        ttk.Label(host, text="Loading", style="Section.TLabel").pack(anchor="w", padx=14, pady=(14, 4))
        frame_load = ttk.Frame(host, style="Card.TFrame", padding=14); frame_load.pack(fill="x", padx=12)
        r = 0
        ttk.Label(frame_load, text="Beam Length L (m)", style="Card.TLabel").grid(row=r, column=0, sticky="w")
        self.entry_length = ttk.Entry(frame_load); self.entry_length.grid(row=r, column=1, sticky="ew")
        ttk.Label(frame_load, text="(e.g., 2.5)", style="Hint.TLabel").grid(row=r, column=2, sticky="w")
        r += 1
        ttk.Label(frame_load, text="Load Value", style="Card.TLabel").grid(row=r, column=0, sticky="w", pady=(6,2))
        self.entry_load = ttk.Entry(frame_load); self.entry_load.grid(row=r, column=1, sticky="ew")
        self.load_unit_var = tk.StringVar(value="N")
        self.cmb_unit = ttk.Combobox(frame_load, textvariable=self.load_unit_var, width=12, values=["N","N/m","Nm"], state="readonly")
        self.cmb_unit.grid(row=r, column=2, sticky="w", padx=6)
        ttk.Label(frame_load, text="Choose correct unit for your load case", style="Hint.TLabel").grid(row=r, column=3, sticky="w")
        r += 1
        ttk.Label(frame_load, text="Point Load Position a (m)", style="Card.TLabel").grid(row=r, column=0, sticky="w", pady=(6,2))
        self.entry_a = ttk.Entry(frame_load); self.entry_a.grid(row=r, column=1, sticky="ew")
        ttk.Label(frame_load, text="(Only for ‘Any Position’ case)", style="Hint.TLabel").grid(row=r, column=2, sticky="w")
        frame_load.columnconfigure(1, weight=1)

        # ---------- Material ----------
        ttk.Label(host, text="Material", style="Section.TLabel").pack(anchor="w", padx=14, pady=(14, 4))
        frame_mat = ttk.Frame(host, style="Card.TFrame", padding=14); frame_mat.pack(fill="x", padx=12)
        r = 0
        ttk.Label(frame_mat, text="Select / Type Material", style="Card.TLabel").grid(row=r, column=0, sticky="w")
        self.material_var = tk.StringVar(value="Carbon Steel A36")
        self.cmb_material = ttk.Combobox(frame_mat, textvariable=self.material_var, width=42,
                                         values=sort_material_keys(self.materials))
        self.cmb_material.grid(row=r, column=1, sticky="ew")
        self.cmb_material.bind("<<ComboboxSelected>>", self._on_material_select)
        self.cmb_material.bind("<KeyRelease>", self._filter_materials)
        self.btn_add_mat = ttk.Button(frame_mat, text="Add / Edit Material…", style="Accent.TButton", command=self._add_material)
        self.btn_add_mat.grid(row=r, column=2, padx=8)
        self.btn_import = ttk.Button(frame_mat, text="Import Materials CSV…", style="Accent.TButton", command=self._import_materials_dialog)
        self.btn_import.grid(row=r, column=3, padx=8)
        self.btn_export = ttk.Button(frame_mat, text="Export Materials CSV…", style="Accent.TButton", command=self._export_materials_dialog)
        self.btn_export.grid(row=r, column=4, padx=8)
        btn_suggest = ttk.Button(frame_mat, text="Suggest Formulas…", style="Accent.TButton", command=self.suggest_formulas)
        btn_suggest.grid(row=r, column=5, padx=8)

        r += 1
        ttk.Label(frame_mat, text="Young’s Modulus E (Pa)", style="Card.TLabel").grid(row=r, column=0, sticky="w", pady=(6,2))
        self.entry_E = ttk.Entry(frame_mat); self.entry_E.grid(row=r, column=1, sticky="ew")
        ttk.Label(frame_mat, text="(e.g., 2.1e11)", style="Hint.TLabel").grid(row=r, column=2, sticky="w")
        r += 1
        ttk.Label(frame_mat, text="Yield Strength Sy (Pa) [Optional]", style="Card.TLabel").grid(row=r, column=0, sticky="w", pady=(6,2))
        self.entry_sy = ttk.Entry(frame_mat); self.entry_sy.grid(row=r, column=1, sticky="ew")
        ttk.Label(frame_mat, text="(e.g., 2.5e8)", style="Hint.TLabel").grid(row=r, column=2, sticky="w")
        frame_mat.columnconfigure(1, weight=1)

        # ---------- Section Library (auto I & c) ----------
        ttk.Label(host, text="Section Library (auto I & c)", style="Section.TLabel").pack(anchor="w", padx=14, pady=(14, 4))
        sec_frame = ttk.Frame(host, style="Card.TFrame", padding=14); sec_frame.pack(fill="x", padx=12)
        ttk.Label(sec_frame, text="Shape", style="Card.TLabel").grid(row=0, column=0, sticky="w")
        self.section_shape = tk.StringVar(value="(none)")
        self.cmb_shape = ttk.Combobox(sec_frame, textvariable=self.section_shape, width=26, values=[
            "(none)","Rectangle (b,h)","Square (b)","Solid Circle (D)","Thin-Wall Tube (Do,t)",
            "Hollow Circle (Do,Di)","Rectangular Tube (b,h,t)","Solid Ellipse (a,b)","I-Beam (bf,tf,tw,h)"
        ])
        self.cmb_shape.grid(row=0, column=1, sticky="w", padx=(0,12))
        self.cmb_shape.bind("<<ComboboxSelected>>", self._on_shape_change)

        self.shape_help = ttk.Label(sec_frame,
            text="Pick a cross-section to auto-calc I (stiffness) and c (outer fiber distance).",
            style="Hint.TLabel", padding=(6,2))
        self.shape_help.grid(row=0, column=2, columnspan=3, sticky="w")

        self.dim1_lab = ttk.Label(sec_frame, text="Dim1 (m)", style="Hint.TLabel"); self.dim1_lab.grid(row=1, column=0, sticky="w")
        self.dim2_lab = ttk.Label(sec_frame, text="Dim2 (m)", style="Hint.TLabel"); self.dim2_lab.grid(row=1, column=1, sticky="w")
        self.dim3_lab = ttk.Label(sec_frame, text="Dim3 (m)", style="Hint.TLabel"); self.dim3_lab.grid(row=1, column=2, sticky="w")
        self.dim4_lab = ttk.Label(sec_frame, text="Dim4 (m)", style="Hint.TLabel"); self.dim4_lab.grid(row=1, column=3, sticky="w")

        self.sec_dim1 = ttk.Entry(sec_frame, width=12); self.sec_dim1.grid(row=2, column=0, sticky="we", padx=(0,8))
        self.sec_dim2 = ttk.Entry(sec_frame, width=12); self.sec_dim2.grid(row=2, column=1, sticky="we", padx=(0,8))
        self.sec_dim3 = ttk.Entry(sec_frame, width=12); self.sec_dim3.grid(row=2, column=2, sticky="we", padx=(0,8))
        self.sec_dim4 = ttk.Entry(sec_frame, width=12); self.sec_dim4.grid(row=2, column=3, sticky="we", padx=(0,8))
        self.btn_calc_section = ttk.Button(sec_frame, text="Compute I & c from shape", command=self.compute_Ic, style="Accent.TButton")
        self.btn_calc_section.grid(row=2, column=4, padx=8)

        ttk.Label(sec_frame,
            text="Reminder: I = stiffness against bending (higher I → less deflection).  "
                 "c = distance to extreme fiber (used in σ = M·c/I).",
            style="Hint.TLabel").grid(row=3, column=0, columnspan=5, sticky="w", pady=(8,0))
        sec_frame.columnconfigure(1, weight=1)

        # ---------- Section & Strength (manual) ----------
        ttk.Label(host, text="Section & Strength (manual entry)", style="Section.TLabel").pack(anchor="w", padx=14, pady=(14, 4))
        frame_sec = ttk.Frame(host, style="Card.TFrame", padding=14); frame_sec.pack(fill="x", padx=12)
        r = 0
        ttk.Label(frame_sec, text="I — Second Moment of Area (m⁴)", style="Card.TLabel").grid(row=r, column=0, sticky="w")
        self.entry_I = ttk.Entry(frame_sec); self.entry_I.grid(row=r, column=1, sticky="ew")
        ttk.Label(frame_sec, text="(e.g., 2.2e-11)", style="Hint.TLabel").grid(row=r, column=2, sticky="w")
        r += 1
        ttk.Label(frame_sec, text="c — Distance to Extreme Fiber (m)", style="Card.TLabel").grid(row=r, column=0, sticky="w", pady=(6,2))
        self.entry_c = ttk.Entry(frame_sec); self.entry_c.grid(row=r, column=1, sticky="ew")
        ttk.Label(frame_sec, text="(e.g., 0.02)", style="Hint.TLabel").grid(row=r, column=2, sticky="w")
        ttk.Label(frame_sec, text="ℹ I: resistance to bending. ℹ c: distance from neutral axis to farthest fiber (σ = M·c/I).",
                  style="Hint.TLabel").grid(row=r+1, column=0, columnspan=3, sticky="w", pady=(10,2))
        frame_sec.columnconfigure(1, weight=1)

        # ---------- Bottom Buttons (sticky) ----------
        self.btn_calc = ttk.Button(self.bottom_bar, text="Calculate", command=self.calculate)
        self.btn_plot = ttk.Button(self.bottom_bar, text="Plot Diagrams (V, M, δ)", command=self.plot_diagrams, state="disabled")
        self.btn_export_csv = ttk.Button(self.bottom_bar, text="Export CSV", command=self.export_csv)
        self.btn_export_pdf = ttk.Button(self.bottom_bar, text="Export PDF Report", command=self.export_pdf)
        self.btn_save = ttk.Button(self.bottom_bar, text="Save Project", command=self.save_project)
        self.btn_load = ttk.Button(self.bottom_bar, text="Load Project", command=self.load_project)

        for b in (self.btn_calc, self.btn_plot, self.btn_export_csv, self.btn_export_pdf, self.btn_save, self.btn_load):
            b.pack(side="left", padx=6)

        # Results handles
        self.result_win = None; self.result_text = None

        # Enter→next focus
        for w in (self.cmb_beam, self.cmb_load, self.entry_length, self.entry_load, self.cmb_unit, self.entry_a,
                  self.cmb_material, self.entry_E, self.entry_sy, self.entry_I, self.entry_c,
                  self.cmb_shape, self.sec_dim1, self.sec_dim2, self.sec_dim3, self.sec_dim4):
            w.bind("<Return>", self._focus_next)

        # Tooltips
        self._add_tip(self.btn_calc, "Compute reactions, diagrams, stress and safety factor, then show results.")
        self._add_tip(self.btn_plot, "Plot shear force (V), bending moment (M), and deflection (δ).")
        self._add_tip(self.btn_export_csv, "Export x, V(x), M(x), δ(x) as CSV.")
        self._add_tip(self.btn_export_pdf, "Create a PDF report with inputs and plots.")
        self._add_tip(self.btn_save, "Save current inputs to a project file.")
        self._add_tip(self.btn_load, "Load a saved project file.")
        self._add_tip(self.btn_add_mat, "Add or edit a material (E, Sy).")
        self._add_tip(self.btn_import, "Import materials from CSV: name,E_Pa,Sy_Pa.")
        self._add_tip(self.btn_export, "Export current materials to CSV.")
        self._add_tip(self.btn_calc_section, "Compute I and c for the selected shape & dimensions.")
        self._add_tip(self.cmb_shape, "Select a shape; labels below tell you which dimensions to enter.")

        # Initialize defaults
        self._on_material_select()



# ===================== PART 3/4: BeamApp methods =====================

    # ---------- View / Theme ----------
    def toggle_dark(self):
        self._apply_style_palette(not self._dark_mode)

    def _apply_style_palette(self, dark: bool):
        style = ttk.Style()

        # Force a tiny theme hop to refresh colors on some Tk builds
        cur = style.theme_use()
        try:
            style.theme_use("alt")
        except tk.TclError:
            pass
        style.theme_use(cur)

        if dark:
            bg_w, bg_c = self._dark_bg, self._dark_card
            txt, sub, sel = self._dark_text, "#0b1220", "#1f2937"
            self.root.configure(bg=bg_w)
            style.configure("TFrame", background=bg_w)
            style.configure("Card.TFrame", background=bg_c)
            style.configure("TLabel", background=bg_w, foreground=txt)
            style.configure("Card.TLabel", background=bg_c, foreground=txt)
            style.configure("Section.TLabel", background=bg_w, foreground=self._accent)

            # Entry
            style.configure("TEntry", fieldbackground=sub, foreground=txt, insertcolor=txt)
            style.map("TEntry",
                      fieldbackground=[("readonly", sub), ("disabled", "#374151"), ("!disabled", sub)],
                      foreground=[("disabled", "#9ca3af"), ("!disabled", txt)],
                      selectbackground=[("!disabled", "#374151")],
                      selectforeground=[("!disabled", txt)])

            # Combobox
            style.configure("TCombobox", fieldbackground=sub, background=sub, foreground=txt)
            style.map("TCombobox",
                      fieldbackground=[("readonly", sub), ("!disabled", sub)],
                      foreground=[("readonly", txt), ("!disabled", txt)],
                      selectbackground=[("!disabled", "#374151")],
                      selectforeground=[("!disabled", txt)],
                      arrowcolor=[("!disabled", txt)])

            # Buttons
            style.configure("TButton", background=sel, foreground=txt)
            style.map("TButton", background=[("active", "#374151")])
            style.configure("Accent.TButton", background="#0e7490", foreground="#e5e7eb")
            style.map("Accent.TButton", background=[("active", "#155e75")])
        else:
            bg_w, bg_c, txt = self._light_bg, self._light_card, self._light_text
            self.root.configure(bg=bg_w)
            style.configure("TFrame", background=bg_w)
            style.configure("Card.TFrame", background=bg_c)
            style.configure("TLabel", background=bg_w, foreground=txt)
            style.configure("Card.TLabel", background=bg_c, foreground=txt)
            style.configure("Section.TLabel", background=bg_w, foreground="#203040")

            # Entry
            style.configure("TEntry", fieldbackground="white", foreground="#111", insertcolor="#111")
            style.map("TEntry",
                      fieldbackground=[("readonly", "white"), ("disabled", "#f0f0f0"), ("!disabled", "white")],
                      foreground=[("disabled", "#666"), ("!disabled", "#111")],
                      selectbackground=[("!disabled", "#cde2ff")],
                      selectforeground=[("!disabled", "#000")])

            # Combobox
            style.configure("TCombobox", fieldbackground="white", background="white", foreground="#111")
            style.map("TCombobox",
                      fieldbackground=[("readonly", "white"), ("!disabled", "white")],
                      foreground=[("readonly", "#111"), ("!disabled", "#111")],
                      selectbackground=[("!disabled", "#cde2ff")],
                      selectforeground=[("!disabled", "#000")],
                      arrowcolor=[("!disabled", "#111")])

            # Buttons
            style.configure("TButton", background="#dbeafe", foreground="#102a43")
            style.map("TButton", background=[("active", "#c7e0ff")])
            style.configure("Accent.TButton", background="#e6fffa", foreground="#0f766e")
            style.map("Accent.TButton", background=[("active", "#ccfbf1")])

        # Results window colors
        if self.result_win and self.result_win.winfo_exists():
            self.result_win.configure(bg=bg_c if dark else bg_c)
            if self.result_text:
                self.result_text.configure(
                    bg=("#0b1220" if dark else "#f8fafc"),
                    fg=("#e5e7eb" if dark else "#111827"),
                    insertbackground=("#e5e7eb" if dark else "#111827"),
                    selectbackground=("#374151" if dark else "#cde2ff"),
                    selectforeground=("#e5e7eb" if dark else "#000"),
                )

        # Update scroll canvas + sticky bar backdrop
        try:
            self.scroller.canvas.configure(bg=self.root.cget("bg"))
            self.bottom_bar.configure(style="Card.TFrame")
        except Exception:
            pass

        # Mark widgets for tooltips palette awareness
        for w in (
            getattr(self, "btn_calc", None), getattr(self, "btn_plot", None),
            getattr(self, "btn_export_csv", None), getattr(self, "btn_export_pdf", None),
            getattr(self, "btn_save", None), getattr(self, "btn_load", None),
            getattr(self, "btn_add_mat", None), getattr(self, "btn_import", None),
            getattr(self, "btn_export", None), getattr(self, "btn_calc_section", None),
            getattr(self, "cmb_material", None), getattr(self, "cmb_load", None),
            getattr(self, "cmb_beam", None), getattr(self, "cmb_shape", None),
            getattr(self, "entry_length", None), getattr(self, "entry_load", None),
            getattr(self, "entry_a", None), getattr(self, "entry_E", None),
            getattr(self, "entry_sy", None), getattr(self, "entry_I", None),
            getattr(self, "entry_c", None), getattr(self, "sec_dim1", None),
            getattr(self, "sec_dim2", None), getattr(self, "sec_dim3", None),
            getattr(self, "sec_dim4", None),
        ):
            if w is not None:
                try:
                    w._dark_mode = dark
                except Exception:
                    pass

        self._dark_mode = dark

    # ---------- Section Library helpers ----------
    def _shape_specs(self):
        return {
            "Rectangle (b,h)": ( [("b (width)","m"),("h (height)","m")],
                "Rectangle: I = b·h³/12, c = h/2 (about strong axis)."),
            "Square (b)": ( [("b (side)","m")], "Square: I = b⁴/12, c = b/2."),
            "Solid Circle (D)": ( [("D (diameter)","m")], "Solid circle: I = π·D⁴/64, c = D/2."),
            "Thin-Wall Tube (Do,t)": ( [("Do (outer Ø)","m"),("t (wall)","m")],
                "Thin-wall tube (Do ≫ t): I ≈ (π/8)·Do³·t, c = Do/2."),
            "Hollow Circle (Do,Di)": ( [("Do (outer Ø)","m"),("Di (inner Ø)","m")],
                "Hollow circle: I = (π/64)(Do⁴ − Di⁴), c = Do/2."),
            "Rectangular Tube (b,h,t)": ( [("b (outer width)","m"),("h (outer height)","m"),("t (wall)","m")],
                "Rectangular tube: I = [b·h³ − (b−2t)(h−2t)³]/12, c = h/2."),
            "Solid Ellipse (a,b)": ( [("a (semi-width)","m"),("b (semi-height)","m")],
                "Solid ellipse about horizontal axis: I = (π/4)·a·b³, c = b."),
            "I-Beam (bf,tf,tw,h)": ( [("bf (flange width)","m"),("tf (flange thick.)","m"),("tw (web)","m"),("h (overall)","m")],
                "I-beam: c = h/2; hw = h−2tf; I = 2[bf·tf³/12 + bf·tf(h/2 − tf/2)²] + (tw·hw³)/12."),
        }

    def _on_shape_change(self, _e=None):
        name = self.section_shape.get()
        dims, help_txt = self._shape_specs().get(name, ([], "Pick a shape to see required dimensions."))
        for i, lab in enumerate([self.dim1_lab, self.dim2_lab, self.dim3_lab, self.dim4_lab]):
            if i < len(dims):
                label, unit = dims[i]
                lab.configure(text=f"{label} ({unit})")
            else:
                lab.configure(text=f"Dim{i+1} (m)")
        self.shape_help.configure(text=help_txt)
        for i, e in enumerate([self.sec_dim1, self.sec_dim2, self.sec_dim3, self.sec_dim4]):
            if i >= len(dims):
                e.delete(0, tk.END)

    def compute_Ic(self):
        name = self.section_shape.get()
        try:
            if name == "Rectangle (b,h)":
                b = float(self.sec_dim1.get()); h = float(self.sec_dim2.get()); I = b*h**3/12.0; c = h/2.0
            elif name == "Square (b)":
                b = float(self.sec_dim1.get()); I = b**4/12.0; c = b/2.0
            elif name == "Solid Circle (D)":
                D = float(self.sec_dim1.get()); I = (np.pi*D**4)/64.0; c = D/2.0
            elif name == "Thin-Wall Tube (Do,t)":
                Do = float(self.sec_dim1.get()); t = float(self.sec_dim2.get())
                if t <= 0 or Do <= 2*t: raise ValueError("Require Do > 2t and t > 0.")
                I = (np.pi/8.0) * (Do**3) * t; c = Do/2.0
            elif name == "Hollow Circle (Do,Di)":
                Do = float(self.sec_dim1.get()); Di = float(self.sec_dim2.get())
                if Di >= Do: raise ValueError("Inner diameter must be smaller than outer diameter.")
                I = (np.pi*(Do**4 - Di**4))/64.0; c = Do/2.0
            elif name == "Rectangular Tube (b,h,t)":
                b = float(self.sec_dim1.get()); h = float(self.sec_dim2.get()); t = float(self.sec_dim3.get())
                if t <= 0 or b <= 2*t or h <= 2*t: raise ValueError("Need b>2t and h>2t.")
                I = (b*h**3 - (b-2*t)*(h-2*t)**3)/12.0; c = h/2.0
            elif name == "Solid Ellipse (a,b)":
                a = float(self.sec_dim1.get()); b = float(self.sec_dim2.get())
                if a <= 0 or b <= 0: raise ValueError("a and b must be positive.")
                I = (np.pi/4.0) * a * b**3; c = b
            elif name == "I-Beam (bf,tf,tw,h)":
                bf = float(self.sec_dim1.get()); tf = float(self.sec_dim2.get())
                tw = float(self.sec_dim3.get()); h  = float(self.sec_dim4.get())
                hw = h - 2*tf
                if hw <= 0 or tw <= 0: raise ValueError("Require h > 2tf and tw > 0.")
                Ifl = (bf*tf**3)/12.0 + bf*tf*((h/2 - tf/2)**2)
                Ifr = (bf*tf**3)/12.0 + bf*tf*((h/2 - tf/2)**2)
                Iw  = (tw*hw**3)/12.0
                I = Ifl + Ifr + Iw; c = h/2.0
            else:
                messagebox.showinfo("Section", "Choose a shape first."); return
            self.entry_I.delete(0, tk.END); self.entry_I.insert(0, f"{I:.6e}")
            self.entry_c.delete(0, tk.END); self.entry_c.insert(0, f"{c:.6e}")
        except Exception as ex:
            messagebox.showerror("Section", f"Could not compute I,c: {ex}")

    # ---------- Materials Import / Export / Add ----------
    def _import_materials(self, path, silent=False):
        try:
            count = 0
            with open(path, "r", newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                if header and len(header) != 3:
                    f.seek(0); reader = csv.reader(f)
                for row in reader:
                    if len(row) != 3: continue
                    name = row[0].strip()
                    if not name: continue
                    try:
                        E = float(row[1]) if row[1] != "" else None
                        Sy = float(row[2]) if row[2] != "" else None
                    except ValueError:
                        continue
                    self.materials[name] = (E, Sy); count += 1
            self.cmb_material['values'] = sort_material_keys(self.materials)
            if not silent: messagebox.showinfo("Import Complete", f"Imported {count} materials.")
        except Exception as e:
            if not silent: messagebox.showerror("Import Failed", str(e))

    def _import_materials_dialog(self):
        path = filedialog.askopenfilename(title="Import Materials CSV",
            filetypes=[("CSV files","*.csv"),("All files","*.*")])
        if path: self._import_materials(path)

    def _export_materials_dialog(self):
        path = filedialog.asksaveasfilename(title="Export Materials CSV", defaultextension=".csv",
            filetypes=[("CSV files","*.csv")])
        if not path: return
        try:
            with open(path,"w",newline="",encoding="utf-8") as f:
                w = csv.writer(f); w.writerow(["name","E_Pa","Sy_Pa"])
                for name in sort_material_keys(self.materials):
                    E,Sy = self.materials[name]
                    w.writerow([name, "" if E is None else f"{E:.6e}",
                                     "" if Sy is None else f"{Sy:.6e}"])
            messagebox.showinfo("Export Complete","Materials exported.")
        except Exception as e:
            messagebox.showerror("Export Failed", str(e))

    def _add_material(self):
        try:
            name = simpledialog.askstring("Add / Edit Material","Material name:")
            if not name: return
            E_str = simpledialog.askstring("Add / Edit Material","Young’s Modulus E (Pa)\n(e.g., 2.1e11):")
            Sy_str = simpledialog.askstring("Add / Edit Material","Yield Strength Sy (Pa) [optional]\n(e.g., 2.5e8):")
            E_val = float(E_str) if E_str not in (None,"") else None
            Sy_val = float(Sy_str) if Sy_str not in (None,"") else None
            self.materials[name] = (E_val, Sy_val)
            self.cmb_material['values'] = sort_material_keys(self.materials)
            self.material_var.set(name)
            if E_val is not None: self.entry_E.delete(0, tk.END); self.entry_E.insert(0, f"{E_val:.6e}")
            if Sy_val is not None: self.entry_sy.delete(0, tk.END); self.entry_sy.insert(0, f"{Sy_val:.6e}")
            messagebox.showinfo("Material Saved", f"“{name}” saved.")
        except ValueError:
            messagebox.showerror("Invalid Input","Use numbers like 2.1e11 (E) and 2.5e8 (Sy).")

    # ---------- Materials Project API ----------
    def set_mp_key(self):
        key = simpledialog.askstring("Materials Project", "Enter your MP API key:")
        if key:
            self.mp_api_key = key
            messagebox.showinfo("Materials Project","API key saved for this session.")

    def _fetch_E_for_formula(self, formula: str):
        """Robust fetch: find material IDs by formula via Summary, then get elasticity (K,G) and compute E."""
        if not HAVE_MP:
            messagebox.showwarning("Materials Project","Install the client:\n\npip install mp-api\n\nThen try again.")
            return
        if not self.mp_api_key:
            self.set_mp_key()
            if not self.mp_api_key: return
        try:
            with MPRester(self.mp_api_key) as mpr:
                # 1) Find candidate materials by formula (API keyword compatibility dance)
                sdocs = None
                try:
                    sdocs = mpr.materials.summary.search(formula=formula)
                except TypeError:
                    try:
                        sdocs = mpr.materials.summary.search(chemical_formula=formula)
                    except Exception:
                        sdocs = mpr.materials.summary.search(composition=formula)

                if not sdocs:
                    messagebox.showinfo("Materials Project", f"No matches for “{formula}”.")
                    return

                # Gather material_ids
                mids = []
                for d in sdocs:
                    mid = getattr(d, "material_id", None)
                    if not mid:
                        # sometimes summaries may include material_ids list
                        mids.extend(getattr(d, "material_ids", []) or [])
                    else:
                        mids.append(mid)
                mids = list(dict.fromkeys(mids))  # dedupe
                if not mids:
                    messagebox.showinfo("Materials Project", f"No material IDs for “{formula}”.")
                    return

                # 2) Fetch elasticity docs by material_ids
                edocs = mpr.materials.elasticity.search(material_ids=mids)
                if not edocs:
                    messagebox.showinfo("Materials Project", f"No elasticity data for “{formula}”.")
                    return

                picked = None
                for d in edocs:
                    if getattr(d, "k_vrh", None) and getattr(d, "g_vrh", None):
                        picked = d
                        break
                if picked is None:
                    picked = edocs[0]

                K = float(picked.k_vrh)  # in GPa
                G = float(picked.g_vrh)  # in GPa
                E_GPa = 9*K*G/(3*K + G)
                E_Pa = E_GPa * 1e9

                self.entry_E.delete(0, tk.END)
                self.entry_E.insert(0, f"{E_Pa:.6e}")
                self.material_var.set(f"{formula} (MP)")
                messagebox.showinfo("Materials Project", f"Set E = {E_GPa:.2f} GPa for {formula}")
        except Exception as ex:
            messagebox.showerror("Materials Project", f"Error: {ex}")

    def fetch_E_from_mp(self):
        formula = simpledialog.askstring("Materials Project","Enter a chemical formula (e.g., SiO2, Al2O3, Fe, Ti-6Al-4V):")
        if formula:
            self._fetch_E_for_formula(formula.strip())

    def suggest_formulas(self):
        win = tk.Toplevel(self.root)
        win.title("Try a Formula")
        win.configure(bg=self._dark_card if self._dark_mode else self._light_card)
        frm = ttk.Frame(win, style="Card.TFrame", padding=10); frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="Click a common material formula to fetch E (from Materials Project):",
                  style="Card.TLabel").grid(row=0, column=0, columnspan=4, sticky="w", pady=(0,8))
        groups = {
            "Metals": ["Fe","Cu","Al","Ti","Ni","Mg","Mo","W"],
            "Alloys (nominal)": ["Ti-6Al-4V","Inconel-718","Inconel-625"],
            "Oxides": ["Al2O3","SiO2","ZrO2","TiO2","Fe2O3","MgO"],
            "Carbides/Nitrides": ["SiC","B4C","WC","Si3N4","AlN","TiN"],
            "Semiconductors": ["Si","Ge","GaAs","GaN","InP"],
            "Others": ["C (diamond)","C (graphite)"],
        }
        r = 1
        for title, items in groups.items():
            ttk.Label(frm, text=title, style="Card.TLabel").grid(row=r, column=0, sticky="w", pady=(8,2)); r += 1
            c = 0
            for f in items:
                b = ttk.Button(frm, text=f, command=lambda ff=f: (win.destroy(), self._fetch_E_for_formula(ff)))
                b.grid(row=r, column=c, padx=4, pady=3, sticky="w")
                self._add_tip(b, f"Fetch E for {f} via Materials Project"); c += 1
                if c >= 4: c = 0; r += 1
            r += 1
        ttk.Label(frm, text="Or type a formula:", style="Card.TLabel").grid(row=r, column=0, sticky="w", pady=(8,2))
        ent = ttk.Entry(frm, width=22); ent.grid(row=r, column=1, sticky="w", padx=(4,8))
        go = ttk.Button(frm, text="Fetch", command=lambda: (win.destroy(), self._fetch_E_for_formula(ent.get().strip())))
        go.grid(row=r, column=2, sticky="w"); ent.bind("<Return>", lambda _e: (win.destroy(), self._fetch_E_for_formula(ent.get().strip())))

    # ---------- Results window ----------
    def _show_results_window(self):
        if self.result_win is None or not self.result_win.winfo_exists():
            self.result_win = tk.Toplevel(self.root)
            self.result_win.title("Results")
            self.result_win.geometry("760x600")
            self.result_win.configure(bg=self._dark_card if self._dark_mode else self._light_card)

            header = ttk.Frame(self.result_win, style="Card.TFrame", padding=0); header.pack(fill="x")
            hdr_bg = "#0b1220" if self._dark_mode else "#eaf1ff"
            hdr_fg = "#e2e8f0" if self._dark_mode else "#1f2937"
            strip = tk.Canvas(header, height=40, highlightthickness=0, bd=0, bg=hdr_bg); strip.pack(fill="x")
            strip.create_text(14, 22, anchor="w", text="Beam Analysis Results", fill=hdr_fg, font=("Segoe UI Semibold", 15))

            topbar = ttk.Frame(self.result_win, style="Card.TFrame", padding=(10,8)); topbar.pack(fill="x")
            self.btn_copy = ttk.Button(topbar, text="Copy", command=self._copy_results); self.btn_copy.pack(side="left", padx=(0,6))
            self.btn_save_txt = ttk.Button(topbar, text="Save as TXT", command=self._save_results_txt); self.btn_save_txt.pack(side="left", padx=6)
            self._add_tip(self.btn_copy, "Copy results to clipboard.")
            self._add_tip(self.btn_save_txt, "Save results to a text file.")

            legend = ttk.Label(self.result_win, style="Card.TLabel", padding=(12,4),
                text=("Legend:  V = Shear Force (N)   M = Bending Moment (Nm)   δ = Deflection (m)   "
                      "σ = Bending Stress (Pa)   Sy = Yield Strength (Pa)   n = Safety Factor (Sy/σ)"))
            legend.pack(fill="x", padx=8, pady=(4,0))

            frame = ttk.Frame(self.result_win, style="Card.TFrame", padding=10); frame.pack(fill="both", expand=True, padx=10, pady=(6,12))
            self.result_text = tk.Text(frame, height=22, state='disabled', wrap="word",
                bg=("#0b1220" if self._dark_mode else "#f8fafc"),
                fg=("#e5e7eb" if self._dark_mode else "#111827"),
                insertbackground=("#e5e7eb" if self._dark_mode else "#111827"),
                font=("Segoe UI", 10), relief="flat", padx=10, pady=8)
            self.result_text.pack(fill="both", expand=True)
        return self.result_text

    def _copy_results(self):
        if not self.result_text: return
        self.result_text.config(state="normal")
        txt = self.result_text.get("1.0","end-1c")
        self.result_text.config(state="disabled")
        self.result_win.clipboard_clear(); self.result_win.clipboard_append(txt)
        messagebox.showinfo("Copied","Results copied to clipboard.")

    def _save_results_txt(self):
        if not self.result_text: return
        path = filedialog.asksaveasfilename(title="Save Results as TXT", defaultextension=".txt", filetypes=[("Text file","*.txt")])
        if not path: return
        self.result_text.config(state="normal")
        txt = self.result_text.get("1.0","end-1c")
        self.result_text.config(state="disabled")
        with open(path,"w",encoding="utf-8") as f: f.write(txt)
        messagebox.showinfo("Saved","Results saved as TXT.")

    # ---------- Calculation / Export / Plot ----------
    def _collect_inputs(self):
        return {"beam_type": self.beam_type_var.get(), "load_type": self.load_type_var.get(),
                "L": self.entry_length.get(), "Load": self.entry_load.get(), "unit": self.load_unit_var.get(),
                "a": self.entry_a.get(), "material": self.material_var.get(),
                "E": self.entry_E.get(), "Sy": self.entry_sy.get(), "I": self.entry_I.get(), "c": self.entry_c.get()}

    def _apply_inputs(self, data):
        self.beam_type_var.set(data.get("beam_type","Simply Supported"))
        self.load_type_var.set(data.get("load_type","Point Load (Center)"))
        self.entry_length.delete(0,tk.END); self.entry_length.insert(0, data.get("L",""))
        self.entry_load.delete(0,tk.END); self.entry_load.insert(0, data.get("Load",""))
        self.load_unit_var.set(data.get("unit","N"))
        self.entry_a.delete(0,tk.END); self.entry_a.insert(0, data.get("a",""))
        self.material_var.set(data.get("material","Carbon Steel A36"))
        self.entry_E.delete(0,tk.END); self.entry_E.insert(0, data.get("E",""))
        self.entry_sy.delete(0,tk.END); self.entry_sy.insert(0, data.get("Sy",""))
        self.entry_I.delete(0,tk.END); self.entry_I.insert(0, data.get("I",""))
        self.entry_c.delete(0,tk.END); self.entry_c.insert(0, data.get("c",""))
        self._on_material_select()

    def _show_and_fill_results(self, beam, x, V, M, y, stress, sf):
        rtext = self._show_results_window()
        lines = []
        lines.append("INPUT SUMMARY")
        lines.append(f"  Beam Type: {beam.beam_type}")
        lines.append(f"  Load Type: {beam.load_type}")
        if 'Any Position' in beam.load_type and beam.a is not None:
            lines.append(f"  Point Load Position (a): {beam.a:.4f} m")
        lines.append(f"  Length (L): {beam.length:.4f} m")
        lines.append(f"  Load Value: {sci_notation(beam.load)}  (unit depends on case)")
        lines.append(f"  Material: {beam.material}")
        lines.append(f"  Young’s Modulus (E): {sci_notation(beam.E)} Pa")
        if beam.yield_strength: lines.append(f"  Yield Strength (Sy): {sci_notation(beam.yield_strength)} Pa")
        lines.append(f"  Area Moment of Inertia (I): {sci_notation(beam.I)} m^4")
        lines.append(f"  Outer Fiber Distance (c): {sci_notation(beam.c)} m")

        lines.append("\nRESULTS")
        lines.append(f"  Max |V| (Shear Force):  {sci_notation(np.max(np.abs(V)))} N")
        lines.append(f"  Max |M| (Bending Moment):  {sci_notation(np.max(np.abs(M)))} Nm")
        lines.append(f"  Max |δ| (Deflection):  {sci_notation(np.max(np.abs(y)))} m")
        lines.append(f"  Max σ (from max |M|):  {sci_notation(stress) if stress is not None else 'N/A'} Pa")
        sfv = sf
        if sfv: lines.append(f"  n (Safety Factor = Sy/σ):  {sfv:.2f}")

        r = beam.reactions()
        if r:
            lines.append("\nSUPPORT REACTIONS")
            for k, v in r.items(): lines.append(f"  {k}: {sci_notation(v)}")

        if sfv and sfv < 1.5:
            lines.append("\nNOTE")
            lines.append("  Safety factor is low (<1.5). Consider increasing I, reducing load, shortening span,")
            lines.append("  or choosing a stronger material (higher Sy).")

        txt = "\n".join(lines)
        rtext.config(state='normal'); rtext.delete("1.0","end"); rtext.insert("1.0", txt); rtext.config(state='disabled')

    def calculate(self):
        try:
            beam_type = self.beam_type_var.get(); load_type = self.load_type_var.get()
            L = float(self.entry_length.get()); Load = float(self.entry_load.get()); unit = self.load_unit_var.get()
            if "Moment" in load_type and unit != "Nm": messagebox.showwarning("Unit","Moment case expects Nm.")
            if "UDL" in load_type and unit != "N/m": messagebox.showwarning("Unit","UDL case expects N/m.")
            if "Moment" not in load_type and "UDL" not in load_type and unit != "N": messagebox.showwarning("Unit","Point load case expects N.")

            E = float(self.entry_E.get()); I = float(self.entry_I.get()); c = float(self.entry_c.get())
            Sy = self.entry_sy.get(); Sy = float(Sy) if Sy else None; mat = self.material_var.get()
            a = None
            if "Any Position" in load_type:
                a_txt = self.entry_a.get().strip()
                if not a_txt: raise ValueError("Enter the position ‘a’ (m) for the point load.")
                a = float(a_txt)
                if not (0 <= a <= L): raise ValueError("Position ‘a’ must be between 0 and L.")
            if load_type == "Point Load (Center) [Fixed-Fixed]":
                beam_type = "Fixed-Fixed"; load_type = "Point Load (Center)"

            beam = Beam(beam_type, load_type, L, Load, E, I, c, mat, Sy, a=a)
            x, V, M = beam.diagrams(); y = beam.deflection(x, M)
            stress = beam.bending_stress(); sf = beam.safety_factor()
            self._show_and_fill_results(beam, x, V, M, y, stress, sf)
            self.btn_plot.config(state='normal'); self.root.beam_obj = beam
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def plot_diagrams(self):
        if hasattr(self.root, 'beam_obj'):
            self.root.beam_obj.plot_all()
        else:
            messagebox.showwarning("Warning", "Calculate first before plotting!")

    # ---------- Save/Load & Export ----------
    def save_project(self):
        path = filedialog.asksaveasfilename(title="Save Project", defaultextension=".json", filetypes=[("JSON","*.json")])
        if not path: return
        with open(path,"w",encoding="utf-8") as f: json.dump(self._collect_inputs(), f, indent=2)
        messagebox.showinfo("Saved","Project saved.")

    def load_project(self):
        path = filedialog.askopenfilename(title="Load Project", filetypes=[("JSON","*.json")])
        if not path: return
        with open(path,"r",encoding="utf-8") as f: data = json.load(f)
        self._apply_inputs(data); messagebox.showinfo("Loaded","Project loaded.")

    def export_csv(self):
        if not hasattr(self.root, "beam_obj"): messagebox.showwarning("Export CSV","Calculate first."); return
        path = filedialog.asksaveasfilename(title="Export CSV", defaultextension=".csv", filetypes=[("CSV","*.csv")])
        if not path: return
        x,V,M = self.root.beam_obj.diagrams(); y = self.root.beam_obj.deflection(x,M)
        with open(path,"w",newline="",encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(["x_m","V_N","M_Nm","delta_m"])
            for xi,Vi,Mi,yi in zip(x,V,M,y): w.writerow([f"{xi:.6e}",f"{Vi:.6e}",f"{Mi:.6e}",f"{yi:.6e}"])
        messagebox.showinfo("Export CSV","CSV exported.")

    def export_pdf(self):
        if not hasattr(self.root, "beam_obj"): messagebox.showwarning("Export PDF","Calculate first."); return
        path = filedialog.asksaveasfilename(title="Export PDF Report", defaultextension=".pdf", filetypes=[("PDF","*.pdf")])
        if not path: return
        beam = self.root.beam_obj; x,V,M = beam.diagrams(); y = beam.deflection(x,M)
        with PdfPages(path) as pdf:
            # page 1: text summary
            fig = plt.figure(figsize=(8.5,11))
            fig.text(0.1,0.92,"Beam Analysis Report", fontsize=18)
            fig.text(0.1,0.88,f"Beam: {beam.beam_type} | Load: {beam.load_type} | L = {beam.length:.3f} m")
            fig.text(0.1,0.85,f"Material: {beam.material} | E = {sci_notation(beam.E)} Pa | Sy = {(sci_notation(beam.yield_strength) if beam.yield_strength else '—')}")
            fig.text(0.1,0.82,f"I = {sci_notation(beam.I)} m^4 | c = {sci_notation(beam.c)} m")
            r = beam.reactions(); yabs = np.max(np.abs(y)); Mabs = np.max(np.abs(M)); Vabs = np.max(np.abs(V))
            fig.text(0.1,0.78,f"Max |V| = {sci_notation(Vabs)} N | Max |M| = {sci_notation(Mabs)} Nm | Max |δ| = {sci_notation(yabs)} m")
            ry = 0.74
            if r:
                fig.text(0.1,ry,"Reactions:", fontsize=12); ry -= 0.02
                for k,v in r.items(): fig.text(0.12,ry,f"{k}: {sci_notation(v)}"); ry -= 0.018
            pdf.savefig(fig); plt.close(fig)

            # page 2: diagrams (no plt.show)
            x,V,M = beam.diagrams()
            y = beam.deflection(x,M)
            c_shear = "#5B8DEF"; c_moment = "#F2C14E"; c_defl = "#66C2A5"
            fig2 = plt.figure(figsize=(10, 11))
            fig2.suptitle(f"{beam.beam_type} – {beam.load_type}", fontsize=14)

            ax1 = fig2.add_subplot(3, 1, 1)
            ax1.plot(x, V, linewidth=2.2, linestyle="--", color=c_shear, label="Shear V(x) [N]")
            ax1.set_title("Shear Force"); ax1.set_ylabel("V (N)"); ax1.grid(True, alpha=0.3); ax1.legend(); ax1.axhline(0, linewidth=0.8)
            ax1.set_ylim(*pad_limits(V))

            ax2 = fig2.add_subplot(3, 1, 2)
            ax2.plot(x, M, linewidth=2.2, linestyle="-.", color=c_moment, label="Moment M(x) [Nm]")
            ax2.set_title("Bending Moment"); ax2.set_ylabel("M (Nm)"); ax2.grid(True, alpha=0.3); ax2.legend(); ax2.axhline(0, linewidth=0.8)
            ax2.set_ylim(*pad_limits(M))

            ax3 = fig2.add_subplot(3, 1, 3)
            ax3.plot(x, y, linewidth=2.2, linestyle=":", color=c_defl, label="Deflection δ(x) [m]")
            ax3.set_title("Deflection"); ax3.set_xlabel("x (m)"); ax3.set_ylabel("δ (m)")
            ax3.grid(True, alpha=0.3); ax3.legend(); ax3.axhline(0, linewidth=0.8)
            ax3.set_ylim(*pad_limits(y))

            plt.tight_layout(rect=[0, 0, 1, 0.96])
            pdf.savefig(fig2); plt.close(fig2)

        messagebox.showinfo("Export PDF","Report exported.")

    # ---------- Misc helpers ----------
    def _add_tip(self, widget, text):
        try:
            Tooltip(widget, text)
            widget._dark_mode = self._dark_mode  # so Tooltip picks palette
        except Exception:
            pass

    def _focus_next(self, event):
        event.widget.tk_focusNext().focus()
        return "break"

    def _refresh_scrollregion(self, _e=None):
        try:
            self.scroller._on_body_configure()
        except Exception:
            pass

    def _on_load_change(self, _e=None):
        """Adjust unit hinting and enable/disable 'a' position based on case."""
        beam = self.beam_type_var.get()
        case = self.load_type_var.get()

        # Suggested unit
        if "UDL" in case:
            self.load_unit_var.set("N/m")
        elif "Moment" in case:
            self.load_unit_var.set("Nm")
        else:
            self.load_unit_var.set("N")

        # a-position only for 'Any Position'
        needs_a = ("Any Position" in case)
        try:
            self.entry_a.configure(state=("normal" if needs_a else "disabled"))
        except Exception:
            pass

        # Keep case list sensible per beam type (UX)
        if beam == "Cantilever":
            valid = {"Point Load (End)", "UDL (Uniformly Distributed Load)", "Applied Moment (End)"}
            if case not in valid:
                self.load_type_var.set("Point Load (End)")
        elif beam == "Fixed-Fixed":
            valid = {"UDL (Uniformly Distributed Load)", "Point Load (Center)", "Point Load (Center) [Fixed-Fixed]"}
            if case not in valid:
                self.load_type_var.set("UDL (Uniformly Distributed Load)")

    def _filter_materials(self, _e=None):
        """Type-to-filter dropdown for materials."""
        text = self.cmb_material.get().strip().lower()
        keys = sort_material_keys(self.materials)
        if text:
            keys = [k for k in keys if text in k.lower()]
        self.cmb_material["values"] = keys

    def _on_material_select(self, _e=None):
        """Fill E/Sy when a known material is chosen."""
        name = self.material_var.get()
        if name in self.materials:
            E, Sy = self.materials[name]
            if E is not None:
                self.entry_E.delete(0, tk.END); self.entry_E.insert(0, f"{E:.6e}")
            if Sy is not None:
                self.entry_sy.delete(0, tk.END); self.entry_sy.insert(0, f"{Sy:.6e}")



# ===================== PART 4/4: Main =====================
if __name__ == "__main__":
    root = tk.Tk()
    app = BeamApp(root)
    # Start in light mode with soothing palette; user can toggle dark mode from View menu
    app._apply_style_palette(False)
    root.mainloop()
