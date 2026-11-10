# 🖼️ HEIC Batch Processor Studio

> A high-throughput, dual-interface (Desktop GUI & Web App) image conversion engine engineered for zero-loss batch processing of Apple HEIC/HEIF containers to JPEG/PNG. Built with concurrent pipeline architecture, metadata (EXIF) preservation, and cryptographic SHA-256 integrity auditing.

[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Framework: Streamlit](https://img.shields.io/badge/Web-Streamlit-FF4B4B.svg)](https://streamlit.io/)
[![GUI: Tkinter](https://img.shields.io/badge/Desktop-Tkinter-brightgreen.svg)]()

---

## ⚡ Highlights

* **Dual Deployment Paradigms:** Run natively as a standalone desktop GUI (`Converter_v1.py`) with zero server dependency, or launch as a cloud-hosted web app (`app.py`) via Streamlit.
* **Concurrent Bitstream Execution:** Leverages CPU-bound multi-worker threads (`ThreadPoolExecutor`) to saturate multi-core processors during batch decoding.
* **Lossless Color & EXIF Mapping:** Preserves full camera EXIF payloads (orientation, timestamp, lens profiles) while maintaining maximum chroma sampling (`subsampling=0`, `quality=100`).
* **Cryptographic Verification:** Automatically hashes every converted asset with `SHA-256` and generates an audit manifest file (`manifest_sha256.txt`).
* **In-App Architecture Visualizer:** Features an educational pipeline simulator demonstrating the transition from ISO base media file bitstreams down to DCT/DEFLATE encoding.
* **Zero Disk Spooling (Web):** Processes uploads and outputs entirely in-memory using byte buffers (`io.BytesIO`), bundling output downloads directly into a `.zip` archive.

---

## 🏗️ Architecture & Pipeline Flow

```text
  [Input File / Stream]
           │
           ▼
┌─────────────────────────┐
│ 1. Header Verification  │ ──> Inspects 'ftypheic' / 'mif1' container signature
└─────────────────────────┘
           │
           ▼
┌─────────────────────────┐
│ 2. libheif Decompress   │ ──> Unpacks HEVC (H.265) intra-frame macroblocks
└─────────────────────────┘
           │
           ▼
┌─────────────────────────┐
│ 3. Buffer Normalization │ ──> Translates planar YCbCr (4:2:0) to RGB bitmap
└─────────────────────────┘
           │
           ▼
┌─────────────────────────┐
│ 4. Encode & EXIF Inject │ ──> Re-encodes via DCT (JPEG) or DEFLATE (PNG) + EXIF
└─────────────────────────┘
           │
           ▼
┌─────────────────────────┐
│ 5. SHA-256 Verification │ ──> Computes checksum & appends to audit manifest
└─────────────────────────┘