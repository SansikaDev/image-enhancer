#!/usr/bin/env python3
import argparse
import os
import io
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np
from PIL import Image
from apng import APNG, PNG
import tempfile
import base64


def read_image_bgr(path: Path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"Could not read image: {path}")
    return img


def bgr_to_rgb(img_bgr: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)


def rgb_to_bgr(img_rgb: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)


def gray_world_white_balance(img_bgr: np.ndarray) -> np.ndarray:
    # Gray-world: scale each channel so their means are equal
    img = img_bgr.astype(np.float32)
    b_mean, g_mean, r_mean = [img[:, :, i].mean() for i in range(3)]
    mean_gray = (b_mean + g_mean + r_mean) / 3.0
    # Avoid division by zero
    scale_b = mean_gray / (b_mean + 1e-6)
    scale_g = mean_gray / (g_mean + 1e-6)
    scale_r = mean_gray / (r_mean + 1e-6)
    img[:, :, 0] *= scale_b
    img[:, :, 1] *= scale_g
    img[:, :, 2] *= scale_r
    img = np.clip(img, 0, 255).astype(np.uint8)
    return img


def clahe_l_channel(img_bgr: np.ndarray, clip_limit: float = 2.0, tile_grid_size: Tuple[int, int] = (8, 8)) -> np.ndarray:
    lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
    l2 = clahe.apply(l)
    lab2 = cv2.merge((l2, a, b))
    return cv2.cvtColor(lab2, cv2.COLOR_LAB2BGR)


def gentle_denoise(img_bgr: np.ndarray, h_luma: int = 5, h_color: int = 5) -> np.ndarray:
    return cv2.fastNlMeansDenoisingColored(img_bgr, None, h=h_luma, hColor=h_color, templateWindowSize=7, searchWindowSize=21)


def unsharp_mask(img_bgr: np.ndarray, amount: float = 0.6, sigma: float = 1.2) -> np.ndarray:
    # amount ~ [0.3, 1.0], sigma ~ [0.8, 1.8]
    blurred = cv2.GaussianBlur(img_bgr, (0, 0), sigma)
    sharpened = cv2.addWeighted(img_bgr, 1.0 + amount, blurred, -amount, 0)
    return sharpened


def adjust_saturation(img_bgr: np.ndarray, factor: float = 1.05) -> np.ndarray:
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    s = np.clip(s.astype(np.float32) * factor, 0, 255).astype(np.uint8)
    hsv2 = cv2.merge((h, s, v))
    return cv2.cvtColor(hsv2, cv2.COLOR_HSV2BGR)


def contrast_stretch_l_channel(img_bgr: np.ndarray, low_perc: float = 1.0, high_perc: float = 99.0) -> np.ndarray:
    # Percentile-based stretch on L channel in LAB
    lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    lo = np.percentile(l, low_perc)
    hi = np.percentile(l, high_perc)
    if hi <= lo:
        return img_bgr
    l_stretched = np.clip((l.astype(np.float32) - lo) * (255.0 / (hi - lo)), 0, 255).astype(np.uint8)
    lab2 = cv2.merge((l_stretched, a, b))
    return cv2.cvtColor(lab2, cv2.COLOR_LAB2BGR)


def upscale(img_bgr: np.ndarray, scale: Optional[float] = None, target_w: Optional[int] = None, target_h: Optional[int] = None) -> np.ndarray:
    h, w = img_bgr.shape[:2]
    if target_w is not None and target_h is not None:
        size = (int(target_w), int(target_h))
    elif target_w is not None:
        new_w = int(target_w)
        new_h = int(round(h * (new_w / w)))
        size = (new_w, new_h)
    elif target_h is not None:
        new_h = int(target_h)
        new_w = int(round(w * (new_h / h)))
        size = (new_w, new_h)
    else:
        s = scale if scale is not None else 2.0
        size = (int(round(w * s)), int(round(h * s)))
    return cv2.resize(img_bgr, size, interpolation=cv2.INTER_LANCZOS4)


def enhance(img_bgr: np.ndarray,
            scale: Optional[float] = None,
            target_w: Optional[int] = None,
            target_h: Optional[int] = None,
            denoise_luma: int = 5,
            denoise_color: int = 5,
            clahe_clip: float = 2.0,
            sharpen_amount: float = 0.6,
            sharpen_sigma: float = 1.2,
            sat_factor: float = 1.05) -> np.ndarray:
    # Pipeline: denoise -> white balance -> local contrast -> contrast-stretch -> upscale -> unsharp -> mild saturation
    out = img_bgr.copy()
    out = gentle_denoise(out, h_luma=denoise_luma, h_color=denoise_color)
    out = gray_world_white_balance(out)
    out = clahe_l_channel(out, clip_limit=clahe_clip)
    out = contrast_stretch_l_channel(out, 1.0, 99.0)
    out = upscale(out, scale=scale, target_w=target_w, target_h=target_h)
    out = unsharp_mask(out, amount=sharpen_amount, sigma=sharpen_sigma)
    out = adjust_saturation(out, factor=sat_factor)
    return out


def save_outputs(img_rgb: np.ndarray, out_dir: Path, base_name: str):
    out_dir.mkdir(parents=True, exist_ok=True)
    pil_img = Image.fromarray(img_rgb)

    # PNG (master)
    png_path = out_dir / f"{base_name}_enhanced.png"
    pil_img.save(png_path, format="PNG", optimize=True)

    # JPG
    jpg_path = out_dir / f"{base_name}_enhanced.jpg"
    pil_img.save(jpg_path, format="JPEG", quality=90, subsampling=0, optimize=True)

    # WEBP
    webp_path = out_dir / f"{base_name}_enhanced.webp"
    pil_img.save(webp_path, format="WEBP", quality=90, method=6)

    # APNG (single frame)
    apng_path = out_dir / f"{base_name}_enhanced.apng"
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    png_bytes = buf.getvalue()
    png_frame = PNG.from_bytes(png_bytes)
    ap = APNG()
    ap.append(png_frame, delay=100)  # 1-frame APNG
    ap.save(apng_path)

    return {
        "png": str(png_path),
        "jpg": str(jpg_path),
        "webp": str(webp_path),
        "apng": str(apng_path),
    }


def parse_args():
    p = argparse.ArgumentParser(description="Enhance an image (denoise, balance, contrast, sharpen, upscale) and export in multiple formats.")
    p.add_argument("--in", dest="input_path", required=True, help="Path to input image")
    p.add_argument("--out", dest="out_dir", default="outputs", help="Output directory (default: outputs)")
    scale_group = p.add_mutually_exclusive_group()
    scale_group.add_argument("--scale", type=float, default=2.0, help="Upscale factor (default: 2.0)")
    scale_group.add_argument("--width", type=int, help="Target width (maintains aspect)")
    scale_group.add_argument("--height", type=int, help="Target height (maintains aspect)")

    p.add_argument("--denoise-luma", type=int, default=5, help="Denoise strength for luma (default: 5)")
    p.add_argument("--denoise-color", type=int, default=5, help="Denoise strength for color (default: 5)")
    p.add_argument("--clahe-clip", type=float, default=2.0, help="CLAHE clip limit (default: 2.0)")
    p.add_argument("--sharpen-amount", type=float, default=0.6, help="Unsharp mask amount (default: 0.6)")
    p.add_argument("--sharpen-sigma", type=float, default=1.2, help="Unsharp mask sigma (default: 1.2)")
    p.add_argument("--saturation", type=float, default=1.05, help="Saturation factor (default: 1.05)")

    return p.parse_args()


def main():
    args = parse_args()
    in_path = Path(args.input_path).expanduser()
    out_dir = Path(args.out_dir).expanduser()

    if not in_path.exists():
        raise SystemExit(f"Input image not found: {in_path}")

    img_bgr = read_image_bgr(in_path)

    img_enh_bgr = enhance(
        img_bgr,
        scale=args.scale if (args.width is None and args.height is None) else None,
        target_w=args.width,
        target_h=args.height,
        denoise_luma=args.denoise_luma,
        denoise_color=args.denoise_color,
        clahe_clip=args.clahe_clip,
        sharpen_amount=args.sharpen_amount,
        sharpen_sigma=args.sharpen_sigma,
        sat_factor=args.saturation,
    )

    img_enh_rgb = bgr_to_rgb(img_enh_bgr)

    base_name = Path(in_path).stem
    outputs = save_outputs(img_enh_rgb, out_dir, base_name)

    print("Saved:")
    for k, v in outputs.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
