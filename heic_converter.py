import os
import time
import logging
import hashlib
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

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

class ConverterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("HEIC to JPEG/PNG Pro Converter")
        self.root.geometry("650x550")
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
        header = tk.Frame(self.root, bg="#2c3e50", height=70)
        header.pack(fill=tk.X)
        tk.Label(header, text="HEIC Batch Processor", bg="#2c3e50", fg="white", 
                 font=("Segoe UI", 18, "bold")).pack(pady=15)

        # Main Container
        main = tk.Frame(self.root, padx=25, pady=20)
        main.pack(fill=tk.BOTH, expand=True)

        # Source
        tk.Label(main, text="1. Source Folder:", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        src_frame = tk.Frame(main)
        src_frame.pack(fill=tk.X, pady=(5, 15))
        tk.Entry(src_frame, textvariable=self.source_dir, width=50, bg="#f0f0f0").pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
        tk.Button(src_frame, text="Browse", command=self.select_source).pack(side=tk.LEFT, padx=5)

        # Destination
        tk.Label(main, text="2. Destination Folder:", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        dest_frame = tk.Frame(main)
        dest_frame.pack(fill=tk.X, pady=(5, 15))
        tk.Entry(dest_frame, textvariable=self.dest_dir, width=50, bg="#f0f0f0").pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
        tk.Button(dest_frame, text="Browse", command=self.select_dest).pack(side=tk.LEFT, padx=5)

        # Options
        opts = tk.Frame(main)
        opts.pack(fill=tk.X, pady=5)
        tk.Label(opts, text="Output Format:", font=("Segoe UI", 10)).pack(side=tk.LEFT)
        ttk.Combobox(opts, textvariable=self.format_var, values=["JPEG", "PNG"], state="readonly", width=10).pack(side=tk.LEFT, padx=10)

        # Status
        status_frame = tk.Frame(main, bg="#ecf0f1", bd=1, relief=tk.SUNKEN)
        status_frame.pack(fill=tk.X, pady=15, ipady=5)
        tk.Label(status_frame, textvariable=self.status_var, bg="#ecf0f1", fg="#7f8c8d").pack(side=tk.LEFT, padx=10)
        tk.Label(status_frame, textvariable=self.file_count_var, bg="#ecf0f1", fg="blue", font=("Segoe UI", 10, "bold")).pack(side=tk.RIGHT, padx=10)

        # Progress
        self.progress_bar = ttk.Progressbar(main, orient=tk.HORIZONTAL, length=100, mode='determinate')
        self.progress_bar.pack(fill=tk.X, pady=5)

        # Button
        self.btn_convert = tk.Button(main, text="START CONVERSION", bg="#95a5a6", fg="white", 
                                     font=("Segoe UI", 12, "bold"), state='disabled', command=self.start_thread)
        self.btn_convert.pack(fill=tk.X, pady=10, ipady=5)

        # Log
        self.log_box = tk.Text(main, height=6, state='disabled', bg="#f8f9fa", font=("Consolas", 8))
        self.log_box.pack(fill=tk.BOTH, expand=True)

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
                self.btn_convert.config(state='normal', bg="#27ae60")
            elif count == 0:
                self.status_var.set("No HEIC files found")
                self.btn_convert.config(state='disabled', bg="#95a5a6")
            else:
                self.status_var.set("Select Output Folder")
                self.btn_convert.config(state='disabled', bg="#95a5a6")

    # --- Thread Safe Helpers ---
    def update_log_safe(self, message):
        """Thread-safe UI update for logs"""
        self.log_box.config(state='normal')
        self.log_box.insert(tk.END, f"{datetime.now().strftime('%H:%M:%S')} > {message}\n")
        self.log_box.see(tk.END)
        self.log_box.config(state='disabled')

    def update_progress_safe(self, value, text):
        """Thread-safe UI update for progress bar"""
        self.progress_bar['value'] = value
        self.status_var.set(text)

    def finish_process_safe(self, errors, dest):
        """Thread-safe completion handler"""
        self.is_processing = False
        self.btn_convert.config(state='normal', text="START CONVERSION", bg="#27ae60")
        self.check_readiness()
        
        if errors:
            messagebox.showwarning("Done", f"Completed with {len(errors)} errors. Check log.")
        else:
            messagebox.showinfo("Success", "All images converted successfully!")
            try:
                os.startfile(dest)
            except Exception:
                pass # Ignore if OS cannot open folder

    def start_thread(self):
        if self.is_processing: return
        self.is_processing = True
        self.btn_convert.config(state='disabled', text="PROCESSING...")
        
        src = self.source_dir.get()
        dest = self.dest_dir.get()
        fmt = self.format_var.get()
        
        # Start the heavy lifting in a background thread
        threading.Thread(target=self.run_conversion_logic, args=(src, dest, fmt), daemon=True).start()

    def run_conversion_logic(self, src, dest, fmt):
        try:
            files = [f for f in os.listdir(src) if f.lower().endswith(('.heic', '.heif'))]
            total = len(files)
            
            # Use root.after to safely talk to UI
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
                    
                    # Calculate progress
                    progress_percent = (processed / total) * 100
                    status_text = f"Converting: {processed}/{total}"
                    
                    # SCHEDULE UI UPDATE ON MAIN THREAD
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
    root = tk.Tk()
    app = ConverterGUI(root)
    root.mainloop()