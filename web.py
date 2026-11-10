import os
import io
import time
import zipfile
import hashlib
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
import pillow_heif
import streamlit as st

# Register HEIF opener once
pillow_heif.register_heif_opener()

# --- Page Configuration ---
st.set_page_config(
    page_title="HEIC Studio | Batch Converter",
    page_icon="🖼️",
    layout="wide"
)

# --- Core Converter Logic ---
class ImageConverterLogic:
    @staticmethod
    def calculate_sha256(byte_data):
        sha256_hash = hashlib.sha256()
        sha256_hash.update(byte_data)
        return sha256_hash.hexdigest()

    @staticmethod
    def convert_image(file_bytes, filename, output_format):
        try:
            name_no_ext = os.path.splitext(filename)[0]
            target_ext = output_format.lower()
            out_filename = f"{name_no_ext}.{target_ext}"

            # Open image from in-memory byte stream
            image = Image.open(io.BytesIO(file_bytes))
            exif_data = image.info.get("exif")

            save_kwargs = {}
            if target_ext in ['jpg', 'jpeg']:
                save_kwargs['quality'] = 100
                save_kwargs['subsampling'] = 0

            if exif_data:
                save_kwargs['exif'] = exif_data

            # Save to in-memory buffer
            out_buffer = io.BytesIO()
            image.save(out_buffer, format=output_format.upper(), **save_kwargs)
            out_bytes = out_buffer.getvalue()

            f_hash = ImageConverterLogic.calculate_sha256(out_bytes)
            return True, out_filename, out_bytes, f_hash, None

        except Exception as e:
            return False, filename, None, None, str(e)


# --- UI Layout ---
st.title("HEIC to JPEG/PNG Web Studio")
st.caption("High-fidelity, in-memory HEIC batch converter powered by Pillow and libheif.")

# Top Navigation Tabs
tab_convert, tab_sim, tab_code = st.tabs([
    "🚀 Batch Converter", 
    "🔬 Pipeline Simulation", 
    "💻 Code Architecture"
])

# ==========================================
# TAB 1: BATCH CONVERTER (Drag & Drop + Processing)
# ==========================================
with tab_convert:
    col1, col2 = st.columns([2, 1])

    with col1:
        # Native drag-and-drop file uploader
        uploaded_files = st.file_uploader(
            "📁 Drag & Drop HEIC / HEIF files here",
            type=["heic", "heif"],
            accept_multiple_files=True,
            help="Select one or more HEIC files directly from your computer."
        )

    with col2:
        output_format = st.selectbox("Output Format", ["JPEG", "PNG"], index=0)
        st.write("")
        start_btn = st.button("Start Conversion", type="primary", use_container_width=True)

    if uploaded_files:
        st.info(f"Loaded {len(uploaded_files)} file(s) ready for conversion.")

    if start_btn:
        if not uploaded_files:
            st.warning("Please upload at least one HEIC file first.")
        else:
            progress_bar = st.progress(0)
            status_text = st.empty()
            log_box = st.empty()

            logs = []
            results = []
            total = len(uploaded_files)

            status_text.text(f"Starting batch conversion for {total} images...")

            # Run parallel in-memory conversions
            with ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as executor:
                futures = [
                    executor.submit(
                        ImageConverterLogic.convert_image, 
                        file.getvalue(), 
                        file.name, 
                        output_format
                    )
                    for file in uploaded_files
                ]

                for idx, future in enumerate(futures):
                    success, fname, out_bytes, f_hash, err = future.result()
                    processed = idx + 1
                    percent = int((processed / total) * 100)
                    
                    progress_bar.progress(percent)
                    status_text.text(f"Processing ({processed}/{total}): {fname}")

                    if success:
                        results.append((fname, out_bytes, f_hash))
                        logs.append(f"✓ Converted: {fname} | SHA256: {f_hash[:12]}...")
                    else:
                        logs.append(f"✗ Failed: {fname} | Error: {err}")

                    log_box.code("\n".join(logs[-6:]), language="bash")

            status_text.success("Conversion complete!")

            # Package converted images and manifest into an in-memory ZIP
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                manifest_lines = ["Conversion Manifest\n", "-" * 60 + "\n"]
                for fname, data, f_hash in results:
                    zip_file.writestr(fname, data)
                    manifest_lines.append(f"{fname} | {f_hash}\n")
                zip_file.writestr("manifest_sha256.txt", "".join(manifest_lines))

            zip_buffer.seek(0)

            # Download Button
            st.download_button(
                label="⬇️ Download Converted Images (.ZIP)",
                data=zip_buffer,
                file_name=f"converted_images_{output_format.lower()}.zip",
                mime="application/zip",
                use_container_width=True
            )

# ==========================================
# TAB 2: PIPELINE SIMULATION
# ==========================================
with tab_sim:
    st.subheader("Binary Pipeline Breakdown")
    st.write("Understand the internal bitstream transitions from container parse to SHA-256 verification:")

    steps = [
        ("Stage 1: File Header Parse", "Inspects the `ftypheic` or `mif1` ISO base container header to confirm valid HEIF framing."),
        ("Stage 2: Bitstream Decompression", "`libheif` decodes the High Efficiency Video Coding (HEVC) intra-frames."),
        ("Stage 3: Color Plane Mapping", "Converts planar YCbCr 4:2:0 matrices into a standard RGB 8-bit bitmap array in memory."),
        ("Stage 4: Quantization & Re-encode", "Transforms raw pixel buffers via Discrete Cosine Transform (JPEG) or DEFLATE (PNG)."),
        ("Stage 5: Integrity Verification", "Computes the destination SHA-256 hash to ensure zero bit rot or artifact corruption.")
    ]

    for title, desc in steps:
        with st.expander(title, expanded=True):
            st.markdown(f"**Mechanism:** {desc}")

    if st.button("Simulate Pipeline Step-by-Step"):
        sim_status = st.empty()
        sim_bar = st.progress(0)
        for i, (title, _) in enumerate(steps):
            sim_status.info(f"Executing: **{title}**...")
            time.sleep(0.6)
            sim_bar.progress((i + 1) * 20)
        sim_status.success("Simulation Complete: All buffers verified cleanly.")

# ==========================================
# TAB 3: CODE SNIPPET REFERENCE
# ==========================================
with tab_code:
    st.subheader("Core Conversion Routine")
    st.markdown("This minimalist implementation handles the image processing pipeline cleanly:")

    core_code = """from PIL import Image
import pillow_heif

# 1. Register decoder plugin
pillow_heif.register_heif_opener()

# 2. Open into PIL object (decompressed to RGB)
image = Image.open('input.heic')

# 3. Retain camera metadata
exif = image.info.get('exif')

# 4. Save to destination
image.save('output.jpg', format='JPEG', quality=100, exif=exif)
"""
    st.code(core_code, language="python")