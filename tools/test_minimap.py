'''
미니맵 인식 진단 스크립트 (macOS)

게임 창을 1프레임 캡처해서:
  - 실제 캡처 이미지를 screenshot/ 에 저장 (눈으로 확인용)
  - 순수 흰색(255,255,255) 픽셀이 몇 개인지
  - get_minimap_loc_size() 가 미니맵을 찾는지
  - 흰색에 "가까운" 픽셀(>=250)은 몇 개인지 (안티앨리어싱 의심용)
을 출력합니다.

실행 (터미널.app 에서):
    source venv/bin/activate
    python tools/test_minimap.py
'''
import os
import sys

# 레포 루트를 import 경로에 추가 (python tools/test_minimap.py 로 직접 실행해도 동작)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cv2
import numpy as np

from src.utils.global_var import WINDOW_WORKING_SIZE
from src.utils.logger import logger
from src.utils.common import (
    load_yaml, override_cfg, is_mac, get_minimap_loc_size,
)
from src.input.GameWindowCapturorForMac import GameWindowCapturor

def main():
    # config 로드 (default + macOS)
    cfg = load_yaml("config/config_default.yaml")
    cfg = override_cfg(cfg, load_yaml("config/config_macOS.yaml"))

    logger.info("게임 창 캡처 시작... 게임을 포그라운드로 두세요.")
    capture = GameWindowCapturor(cfg)

    # 프레임 한 장 가져오기
    frame = None
    for _ in range(30):
        frame = capture.get_frame()
        if frame is not None:
            break
    if frame is None:
        logger.error("프레임 캡처 실패 (None). 화면 기록 권한 확인.")
        return

    os.makedirs("screenshot", exist_ok=True)

    # 1) raw 프레임 저장
    cv2.imwrite("screenshot/diag_raw.png", frame)
    logger.info(f"raw 프레임 저장: screenshot/diag_raw.png  shape={frame.shape}")
    logger.info(f"raw 평균 픽셀값: {float(frame.mean()):.2f} (5 미만이면 검정=권한문제)")

    # 2) 타이틀바 자르기
    title_h = cfg["game_window"]["title_bar_height"]
    frame_no_title = frame[title_h:, :]
    logger.info(f"타이틀바 제거 후 shape={frame_no_title.shape} "
                f"(config game_window.size={cfg['game_window']['size']})")

    if cfg["game_window"]["size"] != list(frame_no_title.shape[:2]) and \
       cfg["game_window"]["size"] != frame_no_title.shape[:2]:
        logger.warning("⚠️ 캡처 해상도가 config game_window.size 와 다릅니다. "
                       "config_macOS.yaml 의 game_window.size / title_bar_height 를 "
                       "실제 캡처 크기에 맞게 조정해야 합니다.")

    # 3) WINDOW_WORKING_SIZE 로 리사이즈 (엔진과 동일)
    img_frame = cv2.resize(frame_no_title, WINDOW_WORKING_SIZE,
                           interpolation=cv2.INTER_NEAREST)
    cv2.imwrite("screenshot/diag_resized.png", img_frame)
    logger.info(f"리사이즈 후 저장: screenshot/diag_resized.png  shape={img_frame.shape}")

    # 4) 순수 흰색 픽셀 개수
    white = np.array([255, 255, 255])
    mask_pure = cv2.inRange(img_frame, white, white)
    n_pure = int(np.count_nonzero(mask_pure))
    logger.info(f"순수 흰색(255,255,255) 픽셀 수: {n_pure}")

    # 5) 흰색에 가까운 픽셀 (>=250 모든 채널) — 안티앨리어싱 의심
    near = np.all(img_frame >= 250, axis=2)
    n_near = int(np.count_nonzero(near))
    logger.info(f"흰색 근접(>=250) 픽셀 수: {n_near}")
    if n_pure < 400 and n_near > n_pure * 2:
        logger.warning("⚠️ 순수 흰색은 적은데 근접 흰색이 많습니다 → "
                       "캡처 흰색이 254/253 으로 어긋났을 가능성 (안티앨리어싱/색프로파일). "
                       "get_minimap_loc_size 의 흰색 임계값을 낮춰야 할 수 있습니다.")

    # 6) 미니맵 인식 시도 (macOS 완화 파라미터)
    result = get_minimap_loc_size(
        img_frame,
        min_size=80,
        search_region_ratio=0.5,
        min_border_sides=3,
        border_ratio=0.8,
    )
    if result is None:
        logger.error("❌ get_minimap_loc_size: 미니맵을 찾지 못함")
        logger.info("→ screenshot/diag_resized.png 를 열어 좌상단에 미니맵이 "
                    "흰 테두리와 함께 또렷이 보이는지 확인하세요.")
    else:
        x, y, w, h = result
        logger.info(f"✅ 미니맵 발견: x={x}, y={y}, w={w}, h={h}")
        viz = img_frame.copy()
        cv2.rectangle(viz, (x, y), (x+w, y+h), (0, 0, 255), 2)
        cv2.imwrite("screenshot/diag_minimap.png", viz)
        logger.info("미니맵 박스 표시 저장: screenshot/diag_minimap.png")

    capture.stop()

if __name__ == "__main__":
    if not is_mac():
        logger.warning("이 진단 스크립트는 macOS 전용입니다.")
    main()
