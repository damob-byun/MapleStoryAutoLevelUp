# 도구 사용 가이드

`tools/` 디렉터리에 있는 두 가지 핵심 보조 스크립트의 사용법입니다.

- [`tools/routeRecorder.py`](#routerecorderpy--루트-레코더) — 새 맵의 `map.png` / `route*.png`를 직접 녹화해 만드는 도구
- [`tools/mob_maker.py`](#mob_makerpy--몬스터-스프라이트-다운로더) — `maplestory.io`에서 몬스터 스프라이트를 자동 다운로드하는 도구

> 두 스크립트 모두 **반드시 레포 루트(`MapleStoryAutoLevelUp/`)에서 실행**해야 합니다. 내부 경로(`config/`, `minimaps/`, `monster/`)가 CWD 기준으로 하드코딩되어 있습니다.

---

## `routeRecorder.py` — 루트 레코더

캐릭터를 직접 조작하면서 미니맵 위에 이동 경로를 그려 `minimaps/<map>/map.png` 와 `minimaps/<map>/route*.png` 를 자동으로 생성하는 도구입니다. 봇은 이 두 파일을 보고 맵에서 어디로 이동해야 할지 판단합니다.

### 동작 원리 (개요)

1. 게임 창을 캡처해 좌상단 미니맵 영역을 추출합니다.
2. 미니맵을 누적해 가며 전역 맵(`img_map`)을 점점 넓혀 갑니다 (캐릭터가 가본 영역만 채워짐).
3. 키 입력(←/→/↑/↓/Space/E)을 읽어, 그 시점의 캐릭터 글로벌 위치 위에 `config/config_default.yaml`의 `route.color_code` 색상을 따라 선/점을 그립니다.
4. `F3` 을 누르면 현재까지 그려진 루트 이미지를 `route<N>.png` 로 저장하고 다음 루트를 새로 시작합니다.
5. `F4` 를 누르면 누적된 전역 맵을 `map.png` 로 저장합니다.

### 사전 준비

- 게임은 **창모드 + 최소 해상도** 로 실행해야 합니다 (`config/config_default.yaml`의 `game_window.size` 와 일치).
- 좌상단 **미니맵을 켜야** 합니다.
- 큰 맵일수록 루트를 그리기 전에 캐릭터로 맵 구석구석을 먼저 돌아다녀 전역 맵을 충분히 누적시켜 두는 것이 좋습니다.

### 실행 명령

```bash
# 기본 사용법: 새 맵 디렉터리를 생성하면서 시작
python -m tools.routeRecorder --new_map <map_directory_name>

# 예시
python -m tools.routeRecorder --new_map garden_of_red_2
```

`--new_map` 으로 지정한 이름의 폴더가 `minimaps/` 아래 새로 생성됩니다. 이미 같은 이름이 있으면 덮어쓸지 묻습니다 (`y/n`).

### 명령행 옵션

| 옵션 | 기본값 | 설명 |
| --- | --- | --- |
| `--new_map` | `new_map` | 저장할 새 맵 디렉터리 이름 (`minimaps/<이름>/`) |
| `--cfg` | `custom` | 추가로 적용할 설정 파일. `config/config_<cfg>.yaml` 을 로드 |
| `--map` | `''` | 기존 `map.png` 경로를 넘기면 새로 만들지 않고 그 위에 루트만 추가 녹화 |

### 단축키

| 키 | 동작 |
| --- | --- |
| `F1` | 녹화 일시정지 / 재개 토글 |
| `F2` | 현재 게임 창 스크린샷을 `screenshot/` 폴더에 저장 |
| `F3` | 현재 루트를 `route<N>.png` 로 저장하고 새 루트 시작 |
| `F4` | 현재 누적된 맵을 `map.png` 로 저장 |
| `q` | (디버그 창이 포커스된 상태에서) 종료 |

### 녹화되는 키 입력

이동/스킬 입력을 그대로 색상 코드로 변환해 루트 위에 그립니다:

| 누른 키 | 그려지는 동작 |
| --- | --- |
| `←` | `left none none` (빨강 선) |
| `→` | `right none none` (파랑 선) |
| `↑` | `none up none` (회색 선) |
| `↓` | `none down none` (연노랑 선) |
| `Space` 단독 | `none none jump` (마젠타 점) |
| `←` + `Space` | `left none jump` (주황 점) |
| `→` + `Space` | `right none jump` (청록 점) |
| `↓` + `Space` | `none down jump` (라임 점) |
| `E` 계열 (텔레포트) | 방향별로 `* none teleport` (보라/분홍/진녹/갈색 점) |

> **공격 키는 녹화되지 않습니다.** 루트 녹화 중에 몹을 그냥 잡아도 무방합니다.
> `space`, `e` 같은 액션은 점("blob")으로, 단순 이동은 선으로 표시됩니다. 점 사이에는 `route_recoder.blob_cooldown` (기본 0.7s) 만큼의 쿨다운이 있습니다.

### 권장 작업 순서

1. **맵 스캔 먼저**: `F1` 을 눌러 녹화를 일시정지한 채로 캐릭터를 끌고 다니며 미니맵을 충분히 탐색 → `F4` 로 현재 맵을 저장해 보고 확인.
2. **루트 녹화 시작**: `F1` 을 다시 눌러 녹화 재개 → 원하는 사냥 동선대로 캐릭터를 조작.
3. **루트 끊기**: 한 사이클이 끝나면 `F3` 으로 저장 → 자동으로 새 `route<N>.png` 가 시작됨.
4. **수동 보정**: 원본 녹화 루트는 보통 그대로는 잘 동작하지 않습니다. Paint / Photoshop / GIMP 등으로 노이즈를 정리하고 색상 코드 정합성을 맞춰주는 단계가 필요합니다.
5. **몬스터 등록**: 새 맵을 만든 뒤에는 `config/config_data.yaml` 의 `map_mobs_mapping` 에 해당 맵에서 잡을 몬스터 이름을 등록해야 봇이 그 몹들을 탐지합니다.

### 출력 파일

```
minimaps/<map_directory_name>/
├── map.png          # 누적된 전역 미니맵 (F4 로 저장)
├── route1.png       # 첫 번째 루트 (F3 로 저장)
├── route2.png       # 두 번째 루트 (선택)
└── ...
```

봇은 실행 시 `route*.png` 들을 순서대로 순환합니다 (단, `route_rest.png` 라는 이름은 순환에서 제외).

---

## `mob_maker.py` — 몬스터 스프라이트 다운로더

`maplestory.io` 의 공개 API에서 몬스터 스프라이트(움직임, 피격, 스킬, 정지 프레임)를 받아 `monster/<mob_name>/` 폴더에 저장합니다. 봇의 템플릿 매칭이 사용하는 PNG 들이 바로 이 파일들입니다.

### 동작 원리 (개요)

1. `https://maplestory.io/api/GMS/65/mob` 에서 전체 몬스터 목록을 받아옵니다.
2. 사용자가 입력한 영문 몬스터 이름과 일치하는 항목의 `id` 를 찾습니다 (대소문자 무시).
3. 해당 ID로 `mob/{id}/download` 를 호출해 스프라이트 zip 을 메모리로 받아옵니다.
4. zip 내부 PNG 들을 순회하면서:
   - 파일명에 `die1` 이 포함된 사망 애니메이션 프레임은 **건너뜁니다** (죽은 몹은 다시 인식할 필요가 없음).
   - 알파 채널의 투명 픽셀을 **녹색(0,255,0) 으로 치환** 합니다 → 봇 측 템플릿 매칭에서 이 색을 마스크로 사용.
5. `monster/<mob_name>/<mob_name>_1.png`, `_2.png` ... 형태로 순번을 매겨 저장합니다.

### 실행 명령

```bash
python tools/mob_maker.py
```

실행하면 프롬프트가 뜹니다:

```
Fetching mobs from: https://maplestory.io/api/GMS/65/mob
You can find monster names at https://maplestory.wiki/GMS/65/mob
Enter mob name: Snail        ← 여기에 영문 몬스터 이름 입력
```

저장 위치는 입력한 이름을 소문자로 바꾸고 공백을 `_` 로 치환한 것입니다. 예:

| 입력 | 저장 폴더 |
| --- | --- |
| `Snail` | `monster/snail/` |
| `Green Mushroom` | `monster/green_mushroom/` |
| `Brown Windup Bear` | `monster/brown_windup_bear/` |

### 사용 가능한 몬스터 이름 찾기

- API 라이브러리 위키: <https://maplestory.wiki/GMS/65/mob>
- 입력은 **영어 이름** 그대로 사용해야 합니다 (대소문자는 무시되지만 철자는 정확해야 함).

### 출력 파일

```
monster/<mob_name>/
├── <mob_name>_1.png
├── <mob_name>_2.png
├── <mob_name>_3.png
└── ...
```

각 PNG는 하나의 애니메이션 프레임(stand / move / hit / skill 등) 입니다. 봇은 폴더 안의 모든 PNG를 자동 로드하고, 좌우 반전본까지 함께 매칭에 사용합니다.

### 주의 사항

- **하드코딩된 region/version**: 현재 `DEFAULT_REGION = "GMS"`, `DEFAULT_VERSION = "65"` 가 코드에 박혀 있습니다. 다른 버전/리전을 쓰려면 `tools/mob_maker.py` 상단의 상수를 직접 수정해야 합니다.
- **녹색 (0,255,0) 치환**: 투명 픽셀을 녹색으로 바꾸는 이유는, 본문 엔진(`MapleStoryAutoLevelUp.py` 의 `get_mask`)이 `(0, 255, 0)` 을 배경/마스크 색으로 가정하고 있기 때문입니다. **PNG 를 수동으로 편집할 때 이 색을 다른 곳에 칠하지 마세요** — 그 픽셀이 통째로 마스킹되어 인식이 망가집니다.
- **데스 애니메이션 제외**: `die1` 이 들어간 파일만 거릅니다. 다른 사망 시퀀스 키워드(`die2` 등)는 그대로 들어옵니다. 인식 정확도에 문제가 있다면 폴더에서 수동 정리해 주세요.
- **네트워크 에러**: `maplestory.io` 응답이 없으면 HTTPError/ConnectionError 메시지만 찍고 종료됩니다. VPN/방화벽 환경이라면 확인이 필요합니다.

### 새 맵에 새 몬스터를 붙이는 전체 흐름

1. `python tools/mob_maker.py` 로 스프라이트 다운로드 → `monster/<name>/` 생성.
2. `config/config_data.yaml` 의 `map_mobs_mapping` 에 `<해당 맵>: [<mob1>, <mob2>, ...]` 항목 추가/수정.
3. (선택) `eng_to_cn` 사전에도 영문↔중문 이름 매핑 추가.
4. 봇 실행 시 자동으로 새 몬스터를 인식 후보로 사용.
