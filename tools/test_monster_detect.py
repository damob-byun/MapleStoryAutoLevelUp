'''
test_monster_detect.py

스크린샷 한 장에 대해 monster/<name> 템플릿이 normal 모드 검출 파이프라인
(get_monsters_in_range 와 동일한 로직)으로 잡히는지 확인하는 진단 도구.

- 엔진과 똑같이 config_default + (macOS) + config_<cfg> 를 레이어링해서
  monster_detect 의 mode / diff_thres / template_scale 등 "내부 상수"를 그대로 사용한다.
- macOS 처럼 게임 창이 작아 화면 속 몹이 템플릿보다 작은 경우를 위해
  --scan 으로 template_scale 을 스윕하며 검출 수/최저 score 를 출력한다.
- --viz 로 검출 박스를 그린 결과 이미지를 screenshot/ 에 저장한다.

사용 예:
    # 현재 config(custom 포함) 상수로 한 장 검출 + 시각화 저장
    python -m tools.test_monster_detect screenshot/2026-05-31_06-18-24_img_frame.png

    # 특정 몹/맵으로 강제
    python -m tools.test_monster_detect <img> --monster coolie_zombie

    # template_scale 스윕(맥에서 적정 비율 찾기)
    python -m tools.test_monster_detect <img> --scan
'''
import os
import sys
import glob
import argparse
import functools

import cv2
import numpy as np

# 리다이렉트 시에도 진행 상황이 바로 보이도록 print 를 flush
print = functools.partial(print, flush=True)

from src.utils.common import get_mask, nms, load_yaml, override_cfg, is_mac


def load_cfg(cfg_name):
    '''엔진(src/engine/MapleStoryAutoLevelUp.py main)과 동일한 레이어링.'''
    cfg = load_yaml("config/config_default.yaml")
    if is_mac():
        cfg = override_cfg(cfg, load_yaml("config/config_macOS.yaml"))
    if cfg_name:
        cfg = override_cfg(cfg, load_yaml(f"config/config_{cfg_name}.yaml"))
    return cfg


def load_monster_templates(monster_name, template_scale):
    '''엔진 load_config 의 몬스터 로딩과 동일(원본 + 좌우반전, (0,255,0) 마스크).'''
    files = sorted(glob.glob(f"monster/{monster_name}/{monster_name}*.png"))
    if not files:
        raise FileNotFoundError(f"monster/{monster_name}/{monster_name}*.png 없음")
    imgs = []
    for f in files:
        img = cv2.imread(f)
        if template_scale != 1.0:
            img = cv2.resize(img, (0, 0), fx=template_scale, fy=template_scale,
                             interpolation=cv2.INTER_NEAREST)
        imgs.append((img, get_mask(img, (0, 255, 0))))
        flip = cv2.flip(img, 1)
        imgs.append((flip, get_mask(flip, (0, 255, 0))))
    return imgs


def detect(img_roi, templates, mode, diff_thres, contour_blur, monster_name):
    '''get_monsters_in_range 의 color/grayscale/contour_only 분기와 동일.'''
    monsters = []
    for img_monster, mask_monster in templates:
        h, w = img_monster.shape[:2]
        if mode == "contour_only":
            mask_pattern = np.all(img_monster == [0, 0, 0], axis=2).astype(np.uint8) * 255
            mask_roi = np.all(img_roi == [0, 0, 0], axis=2).astype(np.uint8) * 255
            a = cv2.GaussianBlur(mask_pattern, (contour_blur, contour_blur), 0)
            b = cv2.GaussianBlur(mask_roi, (contour_blur, contour_blur), 0)
            if a.shape[0] > b.shape[0] or a.shape[1] > b.shape[1]:
                continue
            res = cv2.matchTemplate(b, a, cv2.TM_SQDIFF_NORMED)
        elif mode == "grayscale":
            g1 = cv2.cvtColor(img_monster, cv2.COLOR_BGR2GRAY)
            g2 = cv2.cvtColor(img_roi, cv2.COLOR_BGR2GRAY)
            res = cv2.matchTemplate(g2, g1, cv2.TM_SQDIFF_NORMED, mask=mask_monster)
        elif mode == "color":
            res = cv2.matchTemplate(img_roi, img_monster, cv2.TM_SQDIFF_NORMED,
                                    mask=mask_monster)
        else:
            raise ValueError(f"지원하지 않는 mode: {mode}")
        # 마스크 매칭은 NaN/inf 가 생길 수 있어 정리
        res = np.nan_to_num(res, nan=1.0, posinf=1.0, neginf=1.0)
        locs = np.where(res <= diff_thres)
        pts = list(zip(*locs[::-1]))
        # 전체 프레임 + 느슨한 임계값이면 매칭점이 폭증해 nms 가 멈춤.
        # 점수 좋은 순 상위만 사용(템플릿당 200개 cap).
        if len(pts) > 200:
            pts = sorted(pts, key=lambda p: res[p[1], p[0]])[:200]
        for pt in pts:
            monsters.append({
                "name": monster_name,
                "position": (int(pt[0]), int(pt[1])),
                "size": (h, w),
                "score": float(res[pt[1], pt[0]]),
            })
    return nms(monsters, iou_threshold=0.4)


def best_score(img_roi, templates, mode, contour_blur):
    '''임계값 없이, 이 scale 에서 도달 가능한 "최저(최적) score" 만 반환.
    전체 프레임을 임계값으로 긁으면 매칭점이 폭증(nms 가 O(n^2))하므로,
    scale 적정값을 찾는 단계에선 res.min() 만 본다.'''
    best = 1.0
    for img_monster, mask_monster in templates:
        if mode == "contour_only":
            mask_pattern = np.all(img_monster == [0, 0, 0], axis=2).astype(np.uint8) * 255
            mask_roi = np.all(img_roi == [0, 0, 0], axis=2).astype(np.uint8) * 255
            a = cv2.GaussianBlur(mask_pattern, (contour_blur, contour_blur), 0)
            b = cv2.GaussianBlur(mask_roi, (contour_blur, contour_blur), 0)
            if a.shape[0] > b.shape[0] or a.shape[1] > b.shape[1]:
                continue
            res = cv2.matchTemplate(b, a, cv2.TM_SQDIFF_NORMED)
        elif mode == "grayscale":
            g1 = cv2.cvtColor(img_monster, cv2.COLOR_BGR2GRAY)
            g2 = cv2.cvtColor(img_roi, cv2.COLOR_BGR2GRAY)
            res = cv2.matchTemplate(g2, g1, cv2.TM_SQDIFF_NORMED, mask=mask_monster)
        else:  # color
            res = cv2.matchTemplate(img_roi, img_monster, cv2.TM_SQDIFF_NORMED,
                                    mask=mask_monster)
        res = np.nan_to_num(res, nan=1.0, posinf=1.0, neginf=1.0)
        m = float(res.min())
        if m < best:
            best = m
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image", help="검사할 스크린샷 (img_frame, 1296x700)")
    ap.add_argument("--cfg", default="custom", help="config/config_<cfg>.yaml (기본: custom)")
    ap.add_argument("--monster", default=None,
                    help="몹 이름. 미지정 시 config_data.yaml 의 map_mobs_mapping[bot.map] 사용")
    ap.add_argument("--mode", default=None,
                    help="검출 모드 override (color/grayscale/contour_only). 미지정 시 config 값")
    ap.add_argument("--diff_thres", type=float, default=None,
                    help="diff_thres override (시각화 시 더 엄격하게 보고 싶을 때)")
    ap.add_argument("--scale", type=float, default=None,
                    help="template_scale override")
    ap.add_argument("--scan", action="store_true",
                    help="template_scale 와 mode 를 스윕하며 검출 수/score 출력")
    ap.add_argument("--viz", action="store_true", help="검출 박스 시각화 이미지 저장")
    args = ap.parse_args()

    cfg = load_cfg(args.cfg)
    md = cfg["monster_detect"]
    mode = args.mode or md["mode"]
    diff_thres = args.diff_thres if args.diff_thres is not None else md["diff_thres"]
    contour_blur = md["contour_blur"]
    base_scale = args.scale if args.scale is not None else md.get("template_scale", 1.0)

    # 몹 이름 결정
    if args.monster:
        monster_name = args.monster
    else:
        data = load_yaml("config/config_data.yaml")
        mobs = data["map_mobs_mapping"][cfg["bot"]["map"]]
        monster_name = mobs[0]

    img = cv2.imread(args.image)
    if img is None:
        raise FileNotFoundError(args.image)

    print(f"[cfg] mode={mode} diff_thres={diff_thres} contour_blur={contour_blur} "
          f"template_scale={base_scale}")
    print(f"[입력] {args.image} {img.shape[1]}x{img.shape[0]} / 몹={monster_name}")
    t0 = cv2.imread(sorted(glob.glob(f'monster/{monster_name}/{monster_name}*.png'))[0])
    print(f"[템플릿] 원본 첫 프레임 {t0.shape[1]}x{t0.shape[0]} (h={t0.shape[0]})")

    if args.scan:
        print("\n=== scale x mode 스윕 (도달 가능한 최저 score; 낮을수록 좋음) ===")
        print(f"    (diff_thres={diff_thres} 보다 낮아야 검출됨)")
        modes = [args.mode] if args.mode else ["contour_only", "grayscale", "color"]
        scales = [1.0, 0.85, 0.75, 0.65, 0.6, 0.55, 0.5, 0.45, 0.4]
        for m in modes:
            print(f"\n[{m}]")
            for s in scales:
                tpls = load_monster_templates(monster_name, s)
                b = best_score(img, tpls, m, contour_blur)
                hit = "  <= 검출" if b <= diff_thres else ""
                print(f"  scale={s:<4} -> best={b:.3f}{hit}")
        return

    # 단일 검출
    tpls = load_monster_templates(monster_name, base_scale)
    monsters = detect(img, tpls, mode, diff_thres, contour_blur, monster_name)
    print(f"\n검출 {len(monsters)}개")
    for mm in sorted(monsters, key=lambda x: x["score"])[:20]:
        print(f"  pos={mm['position']} size={mm['size']} score={mm['score']:.3f}")

    if args.viz:
        out = img.copy()
        for mm in monsters:
            x, y = mm["position"]
            h, w = mm["size"]
            cv2.rectangle(out, (x, y), (x + w, y + h), (0, 0, 255), 2)
            cv2.putText(out, f"{mm['score']:.2f}", (x, y - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
        base = os.path.splitext(os.path.basename(args.image))[0]
        out_path = f"screenshot/{base}_detect_{mode}_s{base_scale}.png"
        cv2.imwrite(out_path, out)
        print(f"\n시각화 저장: {out_path}")


if __name__ == "__main__":
    main()
