import os
import sys
import argparse
from collections import deque

import numpy as np
import cv2
from PIL import Image

def load_image_keep_alpha(path):
    # cv2.IMREAD_UNCHANGED로 알파 보존
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise RuntimeError(f"이미지를 불러올 수 없음: {path}")
    return img

def save_image_preserve(path, cv_img):
    # cv2는 BGR, Pillow는 RGB라 변환해 저장 (알파 있으면 RGBA)
    if cv_img.ndim == 2:
        mode = "L"
        pil_img = Image.fromarray(cv_img, mode)
    elif cv_img.shape[2] == 4:
        # BGRA -> RGBA
        pil_img = Image.fromarray(cv2.cvtColor(cv_img, cv2.COLOR_BGRA2RGBA))
    else:
        # BGR -> RGB
        pil_img = Image.fromarray(cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB))
    pil_img.save(path)

def crop_by_alpha(img, alpha_threshold=0):
    """알파 채널 기준 트림"""
    h, w = img.shape[:2]
    alpha = img[:, :, 3]
    if alpha_threshold > 0:
        mask = (alpha > alpha_threshold).astype(np.uint8)
    else:
        mask = (alpha > 0).astype(np.uint8)
    if not np.any(mask):
        return img  # 전부 투명하면 패스
    pts = cv2.findNonZero(mask)
    x, y, bw, bh = cv2.boundingRect(pts)
    return img[y:y+bh, x:x+bw]

def flood_fill_background_mask(img_bgr, tol=12, seed_step=10):
    """
    테두리에서 시작하는 flood fill로 '배경'만 마스크로 선정.
    tol: 색 허용오차(0~255). 값이 클수록 느슨.
    seed_step: 테두리 씨앗 점 간격(px)
    반환: background_mask (H x W, bool)
    """
    h, w = img_bgr.shape[:2]
    # floodFill용 마스크는 (h+2, w+2)
    mask = np.zeros((h + 2, w + 2), np.uint8)

    # 여러 시드 생성(4변 + 모서리)
    seeds = []
    for x in range(0, w, seed_step):
        seeds.append((x, 0))
        seeds.append((x, h - 1))
    for y in range(0, h, seed_step):
        seeds.append((0, y))
        seeds.append((w - 1, y))
    seeds = list(set(seeds))  # 중복 제거

    # floodFill 옵션
    flags = cv2.FLOODFILL_MASK_ONLY | (255 << 8)  # 마스크에만 채우기, fill value=255
    lo = (tol, tol, tol)
    up = (tol, tol, tol)

    # 마스크는 누적(여러 씨앗으로 배경 확장)
    for sx, sy in seeds:
        # 이미 채워진 곳이면 넘어감
        if mask[sy + 1, sx + 1] != 0:
            continue
        # 시드 픽셀 색이 이미지 내일 때만 시도
        if 0 <= sx < w and 0 <= sy < h:
            try:
                cv2.floodFill(img_bgr, mask, (sx, sy), 0, lo, up, flags)
            except cv2.error:
                # 드물게 색공간/모드 문제 시 패스
                continue

    # 가장자리에서 채운 값은 마스크에서 1, 내부는 0
    bg_mask = (mask[1:h+1, 1:w+1] > 0)
    return bg_mask

def crop_by_border_floodfill(img, tol=12, seed_step=10):
    """
    알파가 없을 때(예: JPG/RGB) 테두리 flood fill로 배경 제거 후 트림
    """
    # BGR만 사용
    if img.ndim == 2:
        bgr = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    elif img.shape[2] == 4:
        bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    else:
        bgr = img.copy()

    bg_mask = flood_fill_background_mask(bgr, tol=tol, seed_step=seed_step)
    fg_mask = ~bg_mask

    if not np.any(fg_mask):
        # 전부 배경으로 인식되면 자르지 않음 (tol이 너무 큰 경우)
        return img

    pts = cv2.findNonZero(fg_mask.astype(np.uint8))
    x, y, bw, bh = cv2.boundingRect(pts)
    return img[y:y+bh, x:x+bw]

def process_one(path, out_path, alpha_threshold=0, tol=12, seed_step=10):
    img = load_image_keep_alpha(path)
    has_alpha = (img.ndim == 3 and img.shape[2] == 4)

    if has_alpha:
        trimmed = crop_by_alpha(img, alpha_threshold=alpha_threshold)
    else:
        trimmed = crop_by_border_floodfill(img, tol=tol, seed_step=seed_step)

    # 0 크기 방지
    if trimmed.size == 0:
        trimmed = img
    save_image_preserve(out_path, trimmed)

def is_image_file(name):
    n = name.lower()
    return n.endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"))

def main():
    ap = argparse.ArgumentParser(description="흰 여백/배경을 테두리 기준으로 안전하게 제거(대량 처리)")
    ap.add_argument("folder", nargs="?", default=".", help="입력 폴더 (기본: 현재 폴더)")
    ap.add_argument("--alpha-threshold", type=int, default=0, help="RGBA 알파 임계값(0~255), 기본 0")
    ap.add_argument("--tolerance", type=int, default=12, help="RGB 허용오차(0~255), 기본 12")
    ap.add_argument("--seed-step", type=int, default=10, help="테두리 씨앗 간격(px), 기본 10")
    ap.add_argument("--out", default="trimmed", help="출력 폴더명 (기본 trimmed)")
    args = ap.parse_args()

    in_dir = os.path.abspath(args.folder)
    out_dir = os.path.join(in_dir, args.out)
    os.makedirs(out_dir, exist_ok=True)

    count = 0
    for fn in os.listdir(in_dir):
        if not is_image_file(fn):
            continue
        src = os.path.join(in_dir, fn)
        dst = os.path.join(out_dir, fn)
        try:
            process_one(
                src, dst,
                alpha_threshold=args.alpha_threshold,
                tol=args.tolerance,
                seed_step=args.seed_step,
            )
            count += 1
        except Exception as e:
            print(f"[WARN] 처리 실패: {fn} -> {e}")

    print(f"✅ 작업 완료! {count}개 처리, 결과: {out_dir}")

if __name__ == "__main__":
    main()
