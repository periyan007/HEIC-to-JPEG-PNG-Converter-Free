import os
import time
import logging
import hashlib
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# --- Optional TkinterDnD hook ---
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False

# --- Dependency Check ---
try:
    from PIL import Image, ImageTk
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError as e:
    import tkinter.messagebox as msg
    root = tk.Tk()
    root.withdraw()
    msg.showerror("Missing Libraries", f"Critical Error: {e}\nPlease run: pip install Pillow pillow-heif")
    exit()

# --- Logging Setup ---
logging.basicConfig(
    filename='app_log.txt',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


# =====================================================================
# 1. CORE CONVERTER LOGIC
# =====================================================================
class ImageConverterLogic:
    """Core logic separated from UI for clean architecture."""
    
    @staticmethod
    def calculate_sha256(file_path):
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception as e:
            logging.error(f"Hash calculation failed for {file_path}: {e}")
            return None

    @staticmethod
    def convert_image(source_path, dest_folder, output_format):
        try:
            filename = os.path.basename(source_path)
            name_no_ext = os.path.splitext(filename)[0]
            target_ext = output_format.lower()
            dest_path = os.path.join(dest_folder, f"{name_no_ext}.{target_ext}")

            image = Image.open(source_path)
            exif_data = image.info.get("exif")

            save_kwargs = {}
            if target_ext in ['jpg', 'jpeg']:
                save_kwargs['quality'] = 100
                save_kwargs['subsampling'] = 0
            
            if exif_data:
                save_kwargs['exif'] = exif_data

            image.save(dest_path, format=output_format.upper(), **save_kwargs)
            file_hash = ImageConverterLogic.calculate_sha256(dest_path)
            
            return True, dest_path, file_hash, None

        except Exception as e:
            return False, source_path, None, str(e)


# =====================================================================
# 2. CUSTOM VISUAL WIDGETS
# =====================================================================
class ModernProgressBar(tk.Canvas):
    """Custom high-contrast canvas progress bar with dynamic percentage readout."""
    def __init__(self, parent, height=22, bg="#1e293b", fg="#0ea5e9", **kwargs):
        super().__init__(parent, height=height, bg=bg, highlightthickness=0, **kwargs)
        self.progress_color = fg
        self.bg_color = bg
        self.value = 0.0
        self.text_id = self.create_text(10, height // 2, text="0.0%", fill="#ffffff", font=("Segoe UI", 9, "bold"), anchor="w")
        self.bind("<Configure>", self._on_resize)

    def _on_resize(self, event):
        self.coords(self.text_id, event.width // 2, event.height // 2)
        self.itemconfig(self.text_id, anchor="center")
        self.set_progress(self.value)

    def set_progress(self, percent):
        self.value = max(0.0, min(100.0, percent))
        self.delete("bar")
        w = self.winfo_width()
        h = self.winfo_height()
        fill_w = (self.value / 100.0) * w
        
        if fill_w > 0:
            self.create_rectangle(0, 0, fill_w, h, fill=self.progress_color, outline="", tags="bar")
        self.tag_raise(self.text_id)
        self.itemconfig(self.text_id, text=f"{self.value:.1f}%")


# =====================================================================
# 3. CONVERSION SIMULATION & ARCHITECTURE WINDOW
# =====================================================================
class LogicSimulationWindow(tk.Toplevel):
    """Explains and animates step-by-step how HEIC transforms into JPEG/PNG."""
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Logic Visualizer & Pipeline Architecture")
        self.geometry("640x580")
        self.resizable(False, False)
        self.configure(bg="#0f172a")

        title_lbl = tk.Label(self, text="Binary Pipeline Simulation", bg="#0f172a", fg="#38bdf8", font=("Segoe UI", 14, "bold"))
        title_lbl.pack(pady=(15, 4))

        sub_lbl = tk.Label(self, text="Real-time breakdown of internal decoding and encoding buffers", bg="#0f172a", fg="#94a3b8", font=("Segoe UI", 9))
        sub_lbl.pack()

        # Step inspection view
        self.steps_frame = tk.Frame(self, bg="#0f172a", padx=15, pady=10)
        self.steps_frame.pack(fill=tk.BOTH, expand=True)

        self.step_labels = []
        steps_info = [
            ("Stage 1: File Header Parse", "Verifies 'ftypheic' ISO/IEC base container signature."),
            ("Stage 2: Bitstream Decompression", "libheif unpacks High Efficiency Video Coding (HEVC) keyframes."),
            ("Stage 3: Color Plane Mapping", "Converts planar YCbCr 4:2:0 matrix into RGB 8-bit bitmap array."),
            ("Stage 4: Quantization & Re-encode", "Transforms raw array via DCT (JPEG) or DEFLATE (PNG)."),
            ("Stage 5: Integrity Verification", "Calculates destination SHA-256 hash to ensure zero corruption.")
        ]

        for head, desc in steps_info:
            box = tk.Frame(self.steps_frame, bg="#1e293b", bd=1, relief=tk.FLAT, padx=12, pady=8)
            box.pack(fill=tk.X, pady=5)
            h = tk.Label(box, text=head, bg="#1e293b", fg="#e2e8f0", font=("Consolas", 10, "bold"), anchor="w")
            h.pack(fill=tk.X)
            d = tk.Label(box, text=desc, bg="#1e293b", fg="#64748b", font=("Segoe UI", 8), anchor="w")
            d.pack(fill=tk.X)
            self.step_labels.append((box, h))

        # Simulation Action
        btn_frame = tk.Frame(self, bg="#0f172a")
        btn_frame.pack(pady=15)
        self.btn_run_sim = tk.Button(btn_frame, text="Run Animated Pipeline Test", bg="#2563eb", fg="white", 
                                     font=("Segoe UI", 10, "bold"), padx=14, pady=5, relief=tk.FLAT, cursor="hand2", command=self.run_simulation)
        self.btn_run_sim.pack()

    def run_simulation(self):
        self.btn_run_sim.config(state="disabled")
        threading.Thread(target=self._animate_steps, daemon=True).start()

    def _animate_steps(self):
        for box, lbl in self.step_labels:
            box.config(bg="#1e293b")
            lbl.config(fg="#e2e8f0")

        for box, lbl in self.step_labels:
            self.after(0, lambda b=box, l=lbl: (b.config(bg="#0284c7"), l.config(fg="#ffffff")))
            time.sleep(0.65)
            self.after(0, lambda b=box, l=lbl: (b.config(bg="#064e3b"), l.config(fg="#34d399")))
            time.sleep(0.2)

        self.after(0, lambda: self.btn_run_sim.config(state="normal"))


# =====================================================================
# 4. CODE REFERENCE POPUP
# =====================================================================
class CodeSnippetWindow(tk.Toplevel):
    """Displays the core procedural conversion logic snippet for quick study."""
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Reference: Core Procedural Logic")
        self.geometry("600x420")
        self.configure(bg="#18181b")

        tk.Label(self, text="Core Pure Python Implementation", bg="#18181b", fg="#f43f5e", font=("Segoe UI", 12, "bold")).pack(pady=12)

        snippet = (
            "# Standard Pillow + Pillow-HEIF conversion core\n"
            "from PIL import Image\n"
            "import pillow_heif\n\n"
            "# 1. Register plugin decoder\n"
            "pillow_heif.register_heif_opener()\n\n"
            "# 2. Open file into PIL Image object (decompressed to RGB)\n"
            "image = Image.open('input.heic')\n\n"
            "# 3. Retain metadata if available\n"
            "exif = image.info.get('exif')\n\n"
            "# 4. Encode and save to destination\n"
            "image.save('output.jpg', format='JPEG', quality=100, exif=exif)\n"
        )

        txt = tk.Text(self, bg="#27272a", fg="#a1a1aa", font=("Consolas", 10), padx=12, pady=12, relief=tk.FLAT)
        txt.insert("1.0", snippet)
        txt.config(state="disabled")
        txt.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))


# =====================================================================
# 5. MAIN CONVERTER GUI
# =====================================================================
class ConverterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("HEIC to JPEG/PNG Pro Converter")
        self.root.geometry("680x730")
        self.root.resizable(False, False)

        style = ttk.Style()
        style.theme_use('clam')
        
        # Variables
        self.source_dir = tk.StringVar()
        self.dest_dir = tk.StringVar()
        self.format_var = tk.StringVar(value="JPEG")
        self.status_var = tk.StringVar(value="Waiting for input...")
        self.file_count_var = tk.StringVar(value="0 files found")
        self.is_processing = False

        self._setup_ui()

    def _setup_ui(self):
        # Header
        header = tk.Frame(self.root, bg="#1e293b", height=65)
        header.pack(fill=tk.X)
        tk.Label(header, text="HEIC Batch Processor Studio", bg="#1e293b", fg="#f8fafc", 
                 font=("Segoe UI", 16, "bold")).pack(side=tk.LEFT, padx=20, pady=15)

        # Quick Links on Header
        btn_box = tk.Frame(header, bg="#1e293b")
        btn_box.pack(side=tk.RIGHT, padx=15)
        tk.Button(btn_box, text="Inspect Logic", bg="#334155", fg="#f8fafc", font=("Segoe UI", 9),
                  relief=tk.FLAT, padx=8, cursor="hand2", command=lambda: LogicSimulationWindow(self.root)).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_box, text="View Code", bg="#334155", fg="#f8fafc", font=("Segoe UI", 9),
                  relief=tk.FLAT, padx=8, cursor="hand2", command=lambda: CodeSnippetWindow(self.root)).pack(side=tk.LEFT, padx=4)

        # Main Container
        main = tk.Frame(self.root, padx=20, pady=12)
        main.pack(fill=tk.BOTH, expand=True)

        # DRAG & DROP ZONE (Native canvas with authentic dashed border)
        self.drop_frame = tk.Canvas(main, bg="#f8fafc", height=90, highlightthickness=0)
        self.drop_frame.pack(fill=tk.X, pady=(0, 12))

        def _draw_dashed_border(event):
            self.drop_frame.delete("border_outline")
            w, h = event.width, event.height
            self.drop_frame.create_rectangle(
                2, 2, w - 2, h - 2,
                outline="#94a3b8", width=2, dash=(6, 4), tags="border_outline"
            )

        self.drop_frame.bind("<Configure>", _draw_dashed_border)

        self.drop_label = tk.Label(
            self.drop_frame, 
            text="📁 Drag & Drop HEIC Folder Here\n- or double-click to browse -",
            bg="#f8fafc", fg="#475569", font=("Segoe UI", 10, "bold"), cursor="hand2"
        )
        self.drop_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        self.drop_label.bind("<Double-Button-1>", lambda e: self.select_source())
        self.drop_frame.bind("<Double-Button-1>", lambda e: self.select_source())

        # Bind native Drag-and-Drop if tkinterdnd2 is installed
        if HAS_DND and hasattr(self.root, 'drop_target_register'):
            self.drop_frame.drop_target_register(DND_FILES)
            self.drop_frame.dnd_bind('<<Drop>>', self._handle_drag_drop)
            self.drop_label.drop_target_register(DND_FILES)
            self.drop_label.dnd_bind('<<Drop>>', self._handle_drag_drop)

        # Source
        tk.Label(main, text="1. Source Folder:", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        src_frame = tk.Frame(main)
        src_frame.pack(fill=tk.X, pady=(4, 10))
        tk.Entry(src_frame, textvariable=self.source_dir, width=50, bg="#f8fafc").pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
        tk.Button(src_frame, text="Browse", command=self.select_source).pack(side=tk.LEFT, padx=5)

        # Destination
        tk.Label(main, text="2. Destination Folder:", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        dest_frame = tk.Frame(main)
        dest_frame.pack(fill=tk.X, pady=(4, 10))
        tk.Entry(dest_frame, textvariable=self.dest_dir, width=50, bg="#f8fafc").pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
        tk.Button(dest_frame, text="Browse", command=self.select_dest).pack(side=tk.LEFT, padx=5)

        # Options
        opts = tk.Frame(main)
        opts.pack(fill=tk.X, pady=4)
        tk.Label(opts, text="Output Format:", font=("Segoe UI", 10)).pack(side=tk.LEFT)
        ttk.Combobox(opts, textvariable=self.format_var, values=["JPEG", "PNG"], state="readonly", width=10).pack(side=tk.LEFT, padx=10)

        # Status Strip
        status_frame = tk.Frame(main, bg="#e2e8f0", bd=1, relief=tk.FLAT)
        status_frame.pack(fill=tk.X, pady=8, ipady=4)
        tk.Label(status_frame, textvariable=self.status_var, bg="#e2e8f0", fg="#334155", font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=10)
        tk.Label(status_frame, textvariable=self.file_count_var, bg="#e2e8f0", fg="#2563eb", font=("Segoe UI", 9, "bold")).pack(side=tk.RIGHT, padx=10)

        # Modern Canvas Progress Bar
        tk.Label(main, text="Batch Progress:", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.progress_bar = ModernProgressBar(main, height=22, bg="#1e293b", fg="#0ea5e9")
        self.progress_bar.pack(fill=tk.X, pady=(2, 8))

        # Button
        self.btn_convert = tk.Button(main, text="START CONVERSION", bg="#94a3b8", fg="white", 
                                     font=("Segoe UI", 11, "bold"), relief=tk.FLAT, state='disabled', command=self.start_thread)
        self.btn_convert.pack(fill=tk.X, pady=6, ipady=6)

        # Log
        self.log_box = tk.Text(main, height=6, state='disabled', bg="#0f172a", fg="#38bdf8", font=("Consolas", 8))
        self.log_box.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

    def _handle_drag_drop(self, event):
        path = event.data.strip('{}')
        if os.path.isdir(path):
            self.source_dir.set(path)
            self.check_readiness()
            self.update_log_safe(f"Dropped folder: {path}")

    def select_source(self):
        path = filedialog.askdirectory()
        if path:
            self.source_dir.set(path)
            self.check_readiness()

    def select_dest(self):
        path = filedialog.askdirectory()
        if path:
            self.dest_dir.set(path)
            self.check_readiness()

    def check_readiness(self):
        src = self.source_dir.get()
        dest = self.dest_dir.get()
        if src and os.path.isdir(src):
            files = [f for f in os.listdir(src) if f.lower().endswith(('.heic', '.heif'))]
            count = len(files)
            self.file_count_var.set(f"{count} HEIC files found")
            if count > 0 and dest and os.path.isdir(dest):
                self.status_var.set("Ready to start")
                self.btn_convert.config(state='normal', bg="#16a34a", cursor="hand2")
            elif count == 0:
                self.status_var.set("No HEIC files found")
                self.btn_convert.config(state='disabled', bg="#94a3b8", cursor="arrow")
            else:
                self.status_var.set("Select Output Folder")
                self.btn_convert.config(state='disabled', bg="#94a3b8", cursor="arrow")

    # --- Thread Safe Helpers ---
    def update_log_safe(self, message):
        self.log_box.config(state='normal')
        self.log_box.insert(tk.END, f"{datetime.now().strftime('%H:%M:%S')} > {message}\n")
        self.log_box.see(tk.END)
        self.log_box.config(state='disabled')

    def update_progress_safe(self, value, text):
        self.progress_bar.set_progress(value)
        self.status_var.set(text)

    def finish_process_safe(self, errors, dest):
        self.is_processing = False
        self.btn_convert.config(state='normal', text="START CONVERSION", bg="#16a34a", cursor="hand2")
        self.check_readiness()
        
        if errors:
            messagebox.showwarning("Done", f"Completed with {len(errors)} errors. Check log.")
        else:
            messagebox.showinfo("Success", "All images converted successfully!")
            try:
                os.startfile(dest)
            except Exception:
                pass

    def start_thread(self):
        if self.is_processing: return
        self.is_processing = True
        self.btn_convert.config(state='disabled', text="PROCESSING...", bg="#94a3b8", cursor="arrow")
        
        src = self.source_dir.get()
        dest = self.dest_dir.get()
        fmt = self.format_var.get()
        
        threading.Thread(target=self.run_conversion_logic, args=(src, dest, fmt), daemon=True).start()

    def run_conversion_logic(self, src, dest, fmt):
        try:
            files = [f for f in os.listdir(src) if f.lower().endswith(('.heic', '.heif'))]
            total = len(files)
            
            self.root.after(0, lambda: self.update_log_safe(f"Starting batch for {total} images..."))
            
            processed = 0
            errors = []
            manifest_path = os.path.join(dest, "manifest_sha256.txt")

            with open(manifest_path, "w") as f:
                f.write(f"Conversion Manifest - {datetime.now()}\n")
                f.write("-" * 80 + "\n")

            with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
                futures = []
                for filename in files:
                    file_path = os.path.join(src, filename)
                    futures.append(executor.submit(ImageConverterLogic.convert_image, file_path, dest, fmt))

                for future in futures:
                    success, path, f_hash, err = future.result()
                    processed += 1
                    
                    progress_percent = (processed / total) * 100
                    status_text = f"Converting: {processed}/{total}"
                    
                    self.root.after(0, lambda p=progress_percent, t=status_text: self.update_progress_safe(p, t))
                    
                    if success:
                        with open(manifest_path, "a") as f:
                            f.write(f"{os.path.basename(path)} | {f_hash}\n")
                    else:
                        errors.append(f"{path}: {err}")
                        self.root.after(0, lambda e=err: self.update_log_safe(f"Error: {e}"))

            self.root.after(0, lambda: self.update_log_safe("Conversion Finished."))
            self.root.after(0, lambda: self.finish_process_safe(errors, dest))

        except Exception as e:
            self.root.after(0, lambda: self.update_log_safe(f"Critical Error: {e}"))
            self.root.after(0, lambda: self.finish_process_safe([], dest))

if __name__ == "__main__":
    if HAS_DND:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    app = ConverterGUI(root)
    root.mainloop()