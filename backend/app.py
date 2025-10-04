from __future__ import annotations
import base64
import io
import sys
import pathlib
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import numpy as np
import cv2

# Make project root importable so we can import from scripts.enhance
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))
from scripts.enhance import (
    enhance,
    bgr_to_rgb,
)

app = FastAPI(title="Image Enhancer API", version="1.0.0")

# CORS for local frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


def _decode_image_to_bgr(data: bytes) -> np.ndarray:
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Unable to decode image bytes")
    return img


def _pil_to_bytes(pil_img, format: str) -> bytes:
    buf = io.BytesIO()
    pil_img.save(buf, format=format)
    return buf.getvalue()


@app.post("/api/enhance")
async def enhance_endpoint(
    file: UploadFile = File(...),
    scale: Optional[float] = Form(None),
    width: Optional[int] = Form(None),
    height: Optional[int] = Form(None),
    denoise_luma: int = Form(5),
    denoise_color: int = Form(5),
    clahe_clip: float = Form(2.0),
    sharpen_amount: float = Form(0.6),
    sharpen_sigma: float = Form(1.2),
    saturation: float = Form(1.05),
):
    data = await file.read()
    img_bgr = _decode_image_to_bgr(data)

    img_enh_bgr = enhance(
        img_bgr,
        scale=scale if (width is None and height is None) else None,
        target_w=width,
        target_h=height,
        denoise_luma=denoise_luma,
        denoise_color=denoise_color,
        clahe_clip=clahe_clip,
        sharpen_amount=sharpen_amount,
        sharpen_sigma=sharpen_sigma,
        sat_factor=saturation,
    )

    from PIL import Image

    img_rgb = bgr_to_rgb(img_enh_bgr)
    pil_img = Image.fromarray(img_rgb)

    # Encode PNG
    png_bytes = _pil_to_bytes(pil_img, "PNG")
    # JPG
    jpg_buf = io.BytesIO()
    pil_img.save(jpg_buf, format="JPEG", quality=90, subsampling=0, optimize=True)
    jpg_bytes = jpg_buf.getvalue()
    # WEBP
    webp_buf = io.BytesIO()
    pil_img.save(webp_buf, format="WEBP", quality=90, method=6)
    webp_bytes = webp_buf.getvalue()

    # APNG (single frame) using apng library
    from apng import APNG, PNG
    png_frame = PNG.from_bytes(png_bytes)
    ap = APNG()
    ap.append(png_frame, delay=100)
    apng_io = io.BytesIO()
    # apng library does not expose direct write to BytesIO in all versions, so write to temp and read back
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".apng", delete=True) as tf:
        ap.save(tf.name)
        tf.seek(0)
        apng_bytes = tf.read()

    def to_data_url(mime: str, data: bytes) -> str:
        return f"data:{mime};base64," + base64.b64encode(data).decode("ascii")

    return JSONResponse(
        {
            "png": to_data_url("image/png", png_bytes),
            "jpg": to_data_url("image/jpeg", jpg_bytes),
            "webp": to_data_url("image/webp", webp_bytes),
            "apng": to_data_url("image/apng", apng_bytes),
        }
    )
