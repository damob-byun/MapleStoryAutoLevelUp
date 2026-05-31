'''
test_hp_bar.py

몬스터 HP 바(초록색 가로 바) 검출 진단 도구.

엔진 get_monsters_in_range 의 with_enemy_hp_bar 는 config 의 hp_bar_color 정확색
(inRange(img, color, color))으로만 잡는다. macOS 캡처에선 리사이즈/색 드리프트로
그 정확색이 0픽셀이 되어 검출이 안 된다.

이 스크립트는 "관계형 초록"(G 채널이 R·B 보다 확실히 우세)으로 마스크를 만든 뒤,
HP 바 모양(가로로 길고 얇은 바)만 connectedComponents 로 골라 개수/위치를 출력하고
시각화 이미지를 저장한다.

사용 예:
    python -m tools.test_hp_bar screenshot/2026-05-31_04-34-46_frame.png
    python -m tools.test_hp_bar <img> --gmin 150 --gdiff 40 --no-resize
'''
import os
import sys
import argparse
import functools

import cv2
import numpy as np

print = functools.partial(print, flush=True)


def engine_preprocess(img, title_bar_height):
    '''엔진과 동일: 타이틀바 크롭 후 WINDOW_WORKING_SIZE(1296x700)로 리사이즈.'''
    if title_bar_height > 0:
        img = img[title_bar_height:, :]
    return cv2.resize(img, (1296, 700), interpolation=cv2.INTER_NEAREST)


def green_mask(img, gmin, gdiff):
    '''관계형 초록 마스크: G 가 충분히 밝고, R·B 보다 gdiff 이상 큰 픽셀.'''
    b, g, r = img[:, :, 0].astype(int), img[:, :, 1].astype(int), img[:, :, 2].astype(int)
    rel = (g > gmin) & (g > r + gdiff) & (g > b + gdiff)
    return rel.astype(np.uint8) * 255


def find_bars(mask, min_w, max_h, min_aspect):
    '''가로로 길고 얇은(바 모양) 연결 성분만 추린다.'''
    num, labels, stats, cents = cv2.connectedComponentsWithStats(mask, connectivity=8)
    bars = []
    for i in range(1, num):  # 0 = 배경
        x, y, w, h, area = stats[i]
        if w < min_w:
            continue
        if not (1 <= h <= max_h):
            continue
        if w / max(h, 1) < min_aspect:
            continue
        bars.append({"x": int(x), "y": int(y), "w": int(w), "h": int(h),
                     "area": int(area)})
    return bars


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image", help="검사할 이미지 (raw frame 또는 img_frame)")
    ap.add_argument("--gmin", type=int, default=150, help="G 채널 최소 밝기")
    ap.add_argument("--gdiff", type=int, default=40, help="G 가 R·B 보다 커야 하는 차이")
    ap.add_argument("--min_w", type=int, default=12, help="바 최소 너비(px)")
    ap.add_argument("--max_h", type=int, default=8, help="바 최대 높이(px)")
    ap.add_argument("--min_aspect", type=float, default=3.0, help="바 최소 가로/세로 비")
    ap.add_argument("--title_bar", type=int, default=31,
                    help="raw frame 일 때 크롭할 타이틀바 높이(px)")
    ap.add_argument("--no-resize", action="store_true",
                    help="엔진 전처리(크롭+1296x700 리사이즈) 생략하고 원본 그대로 검사")
    args = ap.parse_args()

    img = cv2.imread(args.image)
    if img is None:
        raise FileNotFoundError(args.image)
    print(f"[입력] {args.image} {img.shape[1]}x{img.shape[0]}")

    if not args.no_resize and img.shape[1] != 1296:
        img = engine_preprocess(img, args.title_bar)
        print(f"[전처리] 타이틀바 {args.title_bar}px 크롭 + 1296x700 리사이즈 적용")
    else:
        print("[전처리] 생략(원본 그대로)")

    mask = green_mask(img, args.gmin, args.gdiff)
    print(f"[마스크] gmin={args.gmin} gdiff={args.gdiff} -> 초록 픽셀 {int((mask>0).sum())}개")

    bars = find_bars(mask, args.min_w, args.max_h, args.min_aspect)
    print(f"\n바 모양(min_w={args.min_w} max_h={args.max_h} min_aspect={args.min_aspect}) "
          f"검출 {len(bars)}개")
    for b in sorted(bars, key=lambda b: b["x"]):
        print(f"  x={b['x']:4} y={b['y']:4} w={b['w']:3} h={b['h']:2} area={b['area']}")

    out = img.copy()
    for b in bars:
        cv2.rectangle(out, (b["x"], b["y"]), (b["x"] + b["w"], b["y"] + b["h"]),
                      (0, 255, 255), 1)
        cv2.putText(out, f"{b['w']}x{b['h']}", (b["x"], b["y"] - 3),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 255), 1)
    base = os.path.splitext(os.path.basename(args.image))[0]
    out_path = f"screenshot/{base}_hpbar.png"
    cv2.imwrite(out_path, out)
    mask_path = f"screenshot/{base}_hpbar_mask.png"
    cv2.imwrite(mask_path, mask)
    print(f"\n시각화 저장: {out_path}")
    print(f"마스크 저장: {mask_path}")


if __name__ == "__main__":
    main()
