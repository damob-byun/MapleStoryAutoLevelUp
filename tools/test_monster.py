'''
몬스터 검출 테스트 (정적 스크린샷에 실제 검출 로직 적용)

스크린샷 한 장에 대해 여러 (mode, template_scale, diff_thres) 조합으로
몬스터 템플릿 매칭을 돌리고, 검출 박스를 그려 저장합니다.

실행:
    python -m tools.test_monster --img screenshot/2026-05-31_02-59-07_screenshot.png --mob coolie_zombie
'''
import os
import sys
import glob
import argparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cv2
import numpy as np

from src.utils.common import get_mask, nms
from src.utils.logger import logger


def load_templates(mob, scale):
    imgs = []
    for f in sorted(glob.glob(f"monster/{mob}/{mob}*.png")):
        img = cv2.imread(f)
        if img is None:
            continue
        if scale != 1.0:
            img = cv2.resize(img, (0, 0), fx=scale, fy=scale,
                             interpolation=cv2.INTER_NEAREST)
        imgs.append((img, get_mask(img, (0, 255, 0))))
        flip = cv2.flip(img, 1)
        imgs.append((flip, get_mask(flip, (0, 255, 0))))
    return imgs


def detect(img_roi, templates, mode, diff_thres, contour_blur=5):
    '''엔진 get_monsters_in_range 의 핵심 매칭 로직을 단순 복제'''
    monsters = []
    for img_monster, mask_monster in templates:
        h, w = img_monster.shape[:2]
        if img_monster.shape[0] >= img_roi.shape[0] or \
           img_monster.shape[1] >= img_roi.shape[1]:
            continue

        if mode == "contour_only":
            mask_pat = np.all(img_monster == [0, 0, 0], axis=2).astype(np.uint8) * 255
            mask_roi = np.all(img_roi == [0, 0, 0], axis=2).astype(np.uint8) * 255
            mp = cv2.GaussianBlur(mask_pat, (contour_blur, contour_blur), 0)
            mr = cv2.GaussianBlur(mask_roi, (contour_blur, contour_blur), 0)
            if mp.shape[0] >= mr.shape[0] or mp.shape[1] >= mr.shape[1]:
                continue
            res = cv2.matchTemplate(mr, mp, cv2.TM_SQDIFF_NORMED)
        elif mode == "grayscale":
            gm = cv2.cvtColor(img_monster, cv2.COLOR_BGR2GRAY)
            gr = cv2.cvtColor(img_roi, cv2.COLOR_BGR2GRAY)
            res = cv2.matchTemplate(gr, gm, cv2.TM_SQDIFF_NORMED, mask=mask_monster)
        elif mode == "color":
            res = cv2.matchTemplate(img_roi, img_monster, cv2.TM_SQDIFF_NORMED, mask=mask_monster)
        else:
            continue

        res = np.nan_to_num(res, nan=1.0, posinf=1.0)
        locs = np.where(res <= diff_thres)
        for pt in zip(*locs[::-1]):
            monsters.append({
                "name": "mob",
                "position": (int(pt[0]), int(pt[1])),
                "size": (h, w),
                "score": float(res[pt[1], pt[0]]),
            })
    return nms(monsters, iou_threshold=0.4)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--img", default="screenshot/2026-05-31_02-59-07_screenshot.png")
    ap.add_argument("--mob", default="coolie_zombie")
    args = ap.parse_args()

    frame = cv2.imread(args.img)
    if frame is None:
        logger.error(f"이미지 로드 실패: {args.img}")
        return
    logger.info(f"frame: {frame.shape}")

    # 게임 영역 ROI (UI/채팅창 제외). 채팅창이 좌측이라 x>=400 부터.
    x0, y0, x1, y1 = 400, 90, 1296, 600
    roi = frame[y0:y1, x0:x1]

    os.makedirs("screenshot", exist_ok=True)

    # 여러 조합 시도
    combos = []
    for mode in ["contour_only", "grayscale", "color"]:
        for scale in [0.4, 0.5, 0.6, 0.7, 1.0]:
            # mode 별 적당한 임계값
            thres = 0.5 if mode == "contour_only" else 0.4
            combos.append((mode, scale, thres))

    best = None
    for mode, scale, thres in combos:
        templates = load_templates(args.mob, scale)
        if not templates:
            logger.error(f"템플릿 없음: monster/{args.mob}/")
            return
        dets = detect(roi, templates, mode, thres)
        n = len(dets)
        avg = (sum(d["score"] for d in dets) / n) if n else 1.0
        logger.info(f"mode={mode:13s} scale={scale} thres={thres}: 검출 {n}개, 평균score={avg:.3f}")
        if n and (best is None or n > best[0]):
            best = (n, mode, scale, thres, dets, templates)

    # 가장 많이 검출된 조합 시각화
    if best:
        n, mode, scale, thres, dets, templates = best
        viz = frame.copy()
        for d in dets:
            px, py = d["position"]
            mh, mw = d["size"]
            cv2.rectangle(viz, (x0+px, y0+py), (x0+px+mw, y0+py+mh), (0, 255, 0), 2)
            cv2.putText(viz, f"{d['score']:.2f}", (x0+px, y0+py-3),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
        out = "screenshot/diag_monster_detect.png"
        cv2.imwrite(out, viz)
        logger.info(f"최다 검출: mode={mode} scale={scale} thres={thres} → {n}개")
        logger.info(f"시각화 저장: {out}")
    else:
        logger.warning("어떤 조합으로도 검출 0개")


if __name__ == "__main__":
    main()
