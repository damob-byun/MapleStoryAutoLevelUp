# macOS 지원 가이드

이 문서는 macOS에서 봇/도구를 돌릴 때의 차이점과, 작은 게임 창(저해상도 캡처)에 맞춘 대응을 정리합니다. Windows와 다른 부분만 다룹니다.

## 1. 실행 환경 — 반드시 `터미널.app` 에서

macOS의 입력/화면 권한은 **프로세스를 띄운 앱**에 귀속됩니다. IDE 통합 터미널(VS Code, Antigravity 등)에서 돌리면 IDE에 권한이 없어 **키 입력(pynput)·화면 캡처(mss)가 막힙니다.**

→ **기본 `터미널.app` 에서 실행**하고, 아래 권한을 모두 켜세요 (앱은 Cmd+Q 로 완전히 종료 후 재시작해야 권한이 적용됨):

- 시스템 설정 → 개인정보 보호 및 보안 →
  - **손쉬운 사용 (Accessibility)** — pynput 키 입력
  - **입력 모니터링 (Input Monitoring)** — pynput 키 입력
  - **화면 기록 (Screen Recording)** — mss 화면 캡처

권한이 없으면 증상:
- 캡처 프레임이 검정 → 미니맵/몹 인식 전부 실패
- F1~F4, 화살표 키 입력이 무시됨
- `This process is not trusted!` 로그

## 2. 캡처 백엔드

`src/input/GameWindowCapturorForMac.py` 가 사용됨:
- `Quartz.CGWindowListCopyWindowInfo` 로 "MapleStory Worlds" 창의 위치/크기 조회
- `mss` 로 해당 화면 영역 픽셀 캡처 → BGRA → BGR 변환
- `src/utils/common.py` 의 `is_mac()` 가 캡처/입력 백엔드를 분기

## 3. 해상도 / 타이틀바 (`config_macOS.yaml`)

macOS 창은 Windows보다 작게 캡처됩니다(예: 960×572). `config_macOS.yaml` 의 값을 **실제 캡처 크기에 맞춰** 설정해야 합니다:

```yaml
game_window:
  size: [541, 960]       # [높이, 너비] (타이틀바 제외). 실제 캡처에 맞게
  title_bar_height: 31   # 타이틀바 높이 (잘라낼 픽셀 수)
```

> 진단 도구: `python tools/test_minimap.py` 가 raw 캡처 크기·타이틀바 경계·미니맵 인식 여부를 출력하고 `screenshot/diag_*.png` 를 저장합니다.

작은 캡처를 `WINDOW_WORKING_SIZE(1296×700)` 로 **1.35배 확대**하기 때문에, 1px 선·작은 스프라이트가 왜곡됩니다. 아래 대응들이 여기서 나옵니다.

## 4. 미니맵 인식 완화

확대로 미니맵 흰 테두리가 깨지고, 지도 콘텐츠가 테두리에 닿아 검출이 실패합니다. `get_minimap_loc_size()` 에 완화 파라미터를 추가했고 macOS 경로에서만 사용:

```python
get_minimap_loc_size(img_frame,
    min_size=80,             # 최소 크기 완화 (기본 100)
    search_region_ratio=0.5, # 좌상단 1/4 영역만 탐색
    min_border_sides=3,      # 4면 중 3면만 흰색이면 통과
    border_ratio=0.8)        # 각 테두리 80% 이상 흰색
```

기본값(strict)은 Windows 동작과 동일 — Windows 무영향.

## 5. 플레이어(노란 점) 색 허용오차

캡처된 노란 점 색이 미세하게 흔들려 정확 매칭이 0개가 됩니다. `get_player_location_on_minimap(..., tol=15)` 로 ±15 허용오차를 둡니다. (`config_macOS.yaml` 의 `minimap.player_color` 사용)

## 6. HP / MP / EXP 바 — 고정 좌표

작은 창엔 바에 흰 테두리가 없어 자동 검출이 불가합니다. **고정 좌표 + 색상 기반 채움률**로 전환:

```yaml
health_monitor:
  use_fixed_bars: True
  hp_bar_rect:  [293, 62, 145, 21]   # [x, y, w, h]
  mp_bar_rect:  [439, 62, 145, 21]
  exp_bar_rect: [592, 62, 158, 21]
```

> ⚠️ **y 좌표는 `ui_coords.ui_y_start`(610) 를 뺀 값**. HealthMonitor 는 `img_frame[ui_y_start:]` 잘린 프레임을 받기 때문 (전체프레임 y=672 → 62).

좌표는 창 크기가 고정이라는 전제. 창 위치/크기가 바뀌면 재측정 필요. 측정은 F2 스크린샷(1296×700 프레임)에서 바 위치를 보고 조정.

## 7. 몬스터 검출 — 한계와 권장

작은 창 + 1.35배 확대로 화면 속 몹이 템플릿보다 작아집니다. `monster_detect.template_scale` 로 템플릿을 미리 축소(INTER_NEAREST, 마스크색 보존)할 수 있습니다.

```yaml
monster_detect:
  template_scale: 0.5   # 0.4~0.7 사이 조정
  max_templates: 10     # 매 프레임 매칭 템플릿 수 제한 (FPS 향상)
```

⚠️ **단, 배경이 몹과 비슷한 맵(눈/숲/바위 등)에서는 템플릿 매칭(color/grayscale/contour) 모두 오탐 위주가 되어 사실상 동작하지 않습니다.** 확대로 배경이 뭉개져 몹보다 템플릿에 더 잘 맞기 때문.

→ 이런 맵에서는 **patrol 모드**(몹 검출 없이 좌우 왕복 + 주기 공격)가 가장 안정적입니다. AOE 직업에 특히 적합:

```yaml
bot:
  mode: patrol
  attack: aoe_skill
patrol:
  range: [0.2, 0.8]
  patrol_attack_interval: 1.0
  patrol_attack_interval_random: 0.6   # 매크로 감지 회피용 랜덤
```

patrol 모드는 `get_monsters_in_range` 에서 템플릿 매칭을 건너뛰므로 빠릅니다.

## 8. 키 입력 — 모디파이어 기호 변환

UI가 모디파이어 키를 기호(`⇧⌥⌃⌘`)로 저장하지만 pyautogui 는 이름 문자열을 받습니다. `KeyBoardController` 의 `key_down`/`key_up` 에서 자동 변환:

| 기호 | pyautogui |
| --- | --- |
| `⇧` | `shift` |
| `⌥` | `option` |
| `⌃` | `ctrl` |
| `⌘` | `command` |
| `␣` | `space` |

> ⚠️ macOS는 pyautogui의 **모디파이어 키 시뮬레이션이 게임에 안 먹히는 경우**가 있습니다. AOE가 안 나가면 게임 키설정을 `q`/`w` 같은 **일반 문자 키**로 바꾸는 게 가장 확실합니다.

## 9. 매크로 감지 회피 — 랜덤 간격

정확히 N초 간격은 매크로로 감지될 수 있어 발사마다 랜덤 지터를 추가:

```yaml
patrol:
  patrol_attack_interval_random: 0.6   # 공격 간격 +0~0.6초 무작위
teleport:
  cooldown_random: 0.5                 # 텔레포트 간격 +0~0.5초 무작위
```

기본값 0 = 지터 없음(기존 동작).

## 10. 점프 구간 우선

`is_use_teleport_to_walk` 가 켜져 있어도, 루트가 **점프/등반(jump, up, down)** 을 지시하면 텔레포트로 덮어쓰지 않고 점프·올라가기를 수행합니다. `teleport.keep_route_jump: True`(기본) 로 제어.

## 11. macOS 전용 루트 레코더

`tools/routeRecorderForMac.py` — Windows용 `routeRecorder.py` 의 macOS 포팅:
- macOS 캡처러 사용
- 미니맵 검출 완화 + 플레이어 색 tol 적용
- 디버그 창 옵션: `--win_x`, `--win_y`(위치), `--win_scale`(크기, 기본 0.5), `--no_viz`(끄기)
- `cv2.namedWindow` 로 창 재사용(무한 생성 방지)

```bash
python -m tools.routeRecorderForMac --new_map <맵> --win_scale 0.5 --win_x 1920
```

## 진단 도구 모음

| 도구 | 용도 |
| --- | --- |
| `tools/test_key.py` | pynput 키 입력 감지 확인 (권한 진단) |
| `tools/test_minimap.py` | 캡처 크기·타이틀바·미니맵 인식 진단 |
| `tools/test_monster.py` | 여러 모드/스케일로 몹 검출 시도 + 시각화 |
