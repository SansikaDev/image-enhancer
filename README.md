# Image Enhancer

A simple, realistic image enhancement toolkit and web UI.

Features
- Gentle, natural pipeline: denoise → white balance → local contrast (CLAHE) → contrast stretch → upscale (Lanczos4) → unsharp → mild saturation
- CLI tool to process local files
- FastAPI backend API that returns PNG/JPG/WEBP/APNG as data URLs
- React + Vite frontend for upload, options, preview, and downloads

Project structure
- scripts/enhance.py: CLI and core enhancement pipeline
- backend/app.py: FastAPI service exposing POST /api/enhance
- web/: React app (Vite + TypeScript)

Requirements
- Python 3.9+ (CI uses 3.11)
- Node.js 18+ (CI uses 20)

Quick start (local)
1) Backend
- Create a virtualenv and install deps:
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
- Run the API:
  uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
- Health check: http://localhost:8000/api/health

2) Frontend (web)
- Start the dev server:
  npm --prefix web install
  npm --prefix web run dev
- Open http://localhost:5173

CLI usage
- Enhance a single image and export to outputs/: 
  python scripts/enhance.py --in /path/to/image.jpg --scale 2 --out outputs
- Options:
  --scale <float>            Upscale factor (default 2.0). Ignored if width/height supplied
  --width <int>              Target width, keeps aspect
  --height <int>             Target height, keeps aspect
  --denoise-luma <int>       Default 5
  --denoise-color <int>      Default 5
  --clahe-clip <float>       Default 2.0
  --sharpen-amount <float>   Default 0.6
  --sharpen-sigma <float>    Default 1.2
  --saturation <float>       Default 1.05

API reference
- POST /api/enhance (multipart/form-data)
  - file: image/*
  - scale: float (optional, ignored if width/height provided)
  - width: int (optional)
  - height: int (optional)
  - denoise_luma: int (default 5)
  - denoise_color: int (default 5)
  - clahe_clip: float (default 2.0)
  - sharpen_amount: float (default 0.6)
  - sharpen_sigma: float (default 1.2)
  - saturation: float (default 1.05)
  - Response JSON: { png, jpg, webp, apng } as data URLs

Development tips
- Backend logs: backend.log (when started via nohup)
- Frontend logs: web/dev.log
- Stop background processes (if started via prior scripts):
  kill $(cat backend.pid) || true
  kill $(cat web/dev.pid) || true

CI
- A GitHub Actions workflow (.github/workflows/ci.yml) builds the frontend and verifies the backend health endpoint.

License
- MIT (update if needed)
