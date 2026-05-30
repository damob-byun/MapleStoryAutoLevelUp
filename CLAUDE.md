# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

메이플스토리 Artale(글로벌/대만)에서 자동 사냥/레벨업을 수행하는 컴퓨터 비전 기반 봇입니다. 게임 메모리에 접근하지 않고, 게임 창을 캡처해 OpenCV 템플릿 매칭(몬스터/네임택/미니맵 스프라이트)으로 상태를 인식한 뒤 키보드 입력을 시뮬레이션합니다. **게임 메모리 접근 없음.** 대상 환경은 Python 3.12 + OpenCV 4.11 이며, 주 플랫폼은 Windows 11, macOS도 일부 지원(입력 캡처 경로가 다름).

## 자주 사용하는 명령어

```bash
# 초기 세팅 (venv 생성 + requirements 설치)
make setup

# PySide6 UI로 실행 (권장 진입점)
python -m src.main
# 또는: make run

# 헤드리스 엔진 직접 실행
python -m src.engine.MapleStoryAutoLevelUp
python -m src.engine.MapleStoryAutoLevelUp --cfg my_config       # config/config_my_config.yaml 사용
python -m src.engine.MapleStoryAutoLevelUp --disable_viz         # 디버그 창 끄기
python -m src.engine.MapleStoryAutoLevelUp --record              # 디버그 시각화를 video/에 녹화

# 레거시 엔진 (미니맵 대신 전체 맵 기반 위치 추정)
python -m src.legacy.mapleStoryAutoLevelUp_legacy --map <name> --monsters <a,b> --attack <directional|aoe_skill>

# 부가 도구
python -m tools.routeRecorder --new_map <map_dir>                # 새 루트 녹화
python tools/mob_maker.py                                        # maplestory.io에서 몬스터 스프라이트 다운로드
python -m tools.AutoDiceRoller --attribute 4,4,13,4              # 캐릭터 생성 주사위 자동화

# Windows 릴리스 빌드 (v* 태그 푸시 시 GitHub Actions에서도 실행됨)
build.bat   # build.bat / .github/workflows/build.yml 에서 pyinstaller 호출
```

런타임 단축키 (UI/헤드리스 공통): **F1** 시작/일시정지, **F2** `screenshot/` 폴더에 스크린샷, **F12** 종료. 테스트 스위트는 없음.

## 아키텍처

### 진입점
- `src/main.py` — `QApplication` 부팅, `AutoBotController`(오케스트레이터, `src/ui/`)와 `MainWindow`(`src/ui/ui.py`)를 연결.
- `src/engine/MapleStoryAutoLevelUp.py` — 헤드리스 엔진 클래스 `MapleStoryAutoBot`. 메인 `loop()` 스레드, 모든 프레임 단위 CV 파이프라인, FSM을 소유. UI 없이 `python -m` 으로 단독 실행 가능.

### 프레임 단위 루프 (엔진)
`MapleStoryAutoBot.loop` 한 사이클의 흐름:
1. `GameWindowCapturor` (Windows: `windows-capture`; macOS: `pyobjc-framework-Quartz`)가 게임 창을 `self.frame`으로 가져온 뒤, 타이틀바를 잘라내고 `WINDOW_WORKING_SIZE = (1296, 700)` (`src/utils/global_var.py`)로 리사이즈.
2. 플레이어 위치는 다음 중 하나로 결정: 네임택 템플릿 매칭(`get_player_location_by_nametag`), 파티 빨간바 HSV 검출(`get_player_location_by_party_red_bar`), 또는 — "normal" 모드에서 — 미니맵 기반 위치 추정(`get_minimap_loc_size` + `get_player_location_on_minimap`, 이후 `find_pattern_sqdiff`로 미니맵을 `minimaps/<map>/map.png`에 정렬).
3. 루트 가이드는 `minimaps/<map>/route*.png` 위에 색칠된 픽셀에서 옴. `get_nearest_color_code`가 플레이어와 가장 가까운 컬러 코드 픽셀을 찾아 `cfg["route"]["color_code"]` / `color_code_up_down` 매핑을 통해 이동 명령으로 변환.
4. 몬스터 검출은 `monster/<name>/`의 PNG에 대해 OpenCV 템플릿 매칭으로 수행되며, 네 가지 모드(`color`, `grayscale`, `contour_only`, `template_free`) 중 하나를 사용 (`cfg["monster_detect"]["mode"]`로 제어). NMS 적용, HP 바 색상 검출은 옵션 폴백.
5. `FiniteStateMachine` (`src/engine/FiniteStateMachine.py`)이 `state.on_frame()`을 호출 → 이동/공격 명령을 계산 → `kb.set_command("<x> <y> <action>")`로 `KeyBoardController`에 전달.
6. `HealthMonitor`는 별도 스레드에서 HP/MP/EXP 바를 감시하고, 임계값을 넘으면 포션 키를 누름.
7. `RuneSolver`는 룬 경고 텍스트를 감지하고, 트리거 시 화살표 미니게임을 풀어줌.

### 유한 상태 머신 (FSM)
상태 클래스는 `src/states/`에 있으며 모두 `State` (`base_state.py`)를 상속. 전이는 `MapleStoryAutoBot.__init__`에서 등록됨:
- `hunting` ⇄ `finding_rune` → `near_rune` → `solving_rune` → `hunting`
- 독립 모드: `aux` (버프 자동화만, 맵 불필요)와 `patrol` (템플릿 기반 몹 검출 미사용 — `get_monsters_in_range`의 `mode == "patrol"` 분기 참고)

각 상태의 `check_transitions()`는 다음 상태 이름이나 `None`을 반환; `FiniteStateMachine.transit_to`는 전이를 1초당 1회로 제한.

### 스레딩
Qt 메인 스레드 외에 최소 3개 스레드를 띄움: 봇 메인 `loop`, `GameWindowCapturor` 캡처 스레드, `HealthMonitor`. `KeyBoardController`도 자체 입력 루프를 가짐. UI 시그널(`image_debug_signal`, `route_map_viz_signal`)을 통해 엔진이 Qt UI를 막지 않고 프레임을 전달.

### 설정
- `config/config_default.yaml` — 주석 포함 전체 스키마. **직접 수정 금지**; 값을 복사해 `config_custom.yaml` (gitignore됨)에 작성하면 `override_cfg` (`src/utils/common.py`)로 레이어링됨.
- `config/config_data.yaml` — 정적 데이터: 영어↔중국어 이름 번역과 `map_mobs_mapping` (어떤 맵에서 어떤 몬스터를 찾을지).
- `config/config_cleric.yaml`, `config/config_macOS.yaml` — 오버라이드 예시.
- `--cfg <name>` 플래그는 `config/config_<name>.yaml`을 선택.

### 에셋 디렉터리 (로드 경로는 CWD 기준 하드코딩)
- `minimaps/<map>/map.png` + `route*.png` — 미니맵 배경 + 컬러 코드가 칠해진 1개 이상의 루트 맵. 루트는 순환됨(`idx_routes`). `route_rest.png`는 순환에서 제외.
- `monster/<name>/*.png` — 템플릿 매칭용 스프라이트. 엔진이 좌우 반전을 자동 생성하고 `(0,255,0)`을 투명 마스크 색으로 사용. 새 몬스터는 `tools/mob_maker.py`로 추가.
- `nametag/<name>.png`, `misc/`, `rune/`, `numbers/` — 네임택/파티/로그인 버튼/룬 화살표 인식용 UI 템플릿.
- `maps/` — `src/legacy/`에서 쓰는 레거시 전체 창 맵 이미지.

이러한 상대 경로 때문에 **항상 레포 루트에서 실행해야 함.**

### 플랫폼 분기
`src/utils/common.py`의 `is_mac()`이 캡처 백엔드를 분기:
- Windows: `src/input/GameWindowCapturor.py` (`windows-capture` + `pywin32`로 창 리사이즈/클릭).
- macOS: `src/input/GameWindowCapturorForMac.py` (`pyobjc-framework-Quartz`). `requirements.txt`에 macOS는 WIP로 표시되어 있음.

### 레거시
`src/legacy/mapleStoryAutoLevelUp_legacy.py`는 미니맵 도입 전 구현으로, 전체 화면 맵 매칭으로 위치를 추정. 작동은 유지되지만, 신규 개발은 미니맵 기반 엔진을 대상으로 함.

## 새 콘텐츠 추가

- **새 맵**: `python -m tools.routeRecorder --new_map <name>`으로 루트 녹화 (F1 일시정지, F3 저장 후 새 루트 시작, F4 현재 맵 덤프) → `config/config_data.yaml`의 `map_mobs_mapping`에 몬스터 등록. 원본 녹화 루트는 이미지 편집기로 다듬어야 잘 동작함.
- **새 몬스터**: `python tools/mob_maker.py`가 `maplestory.io`에서 스프라이트를 `monster/<name>/`로 다운로드. 죽은 몹은 재인식할 필요가 없으므로 사망 애니메이션 프레임은 의도적으로 제외됨.
