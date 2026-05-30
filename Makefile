PYTHON=python3
VENV=venv
ACTIVATE=. $(VENV)/bin/activate

# 기본 인자 (오버라이드 가능)
#   예: make record-route MAP=garden_of_red_2
#   예: make download-mob MOB="Green Mushroom"
MAP ?= new_map
CFG ?= custom
EXISTING_MAP ?=
MOB ?=

.PHONY: setup clean run shell activate record-route download-mob help

# -----------------------------------------------------------------------------
# 환경 세팅
# -----------------------------------------------------------------------------
setup:
	$(PYTHON) -m venv $(VENV)
	$(ACTIVATE); pip install --upgrade pip
	$(ACTIVATE); pip install -r requirements.txt

clean:
	rm -rf $(VENV)

# macOS / Linux 셸에서 venv를 활성화하려면 아래 둘 중 하나:
#   1) 직접 실행:        source venv/bin/activate
#   2) make 안내 보기:    make activate
#
# ※ make 타깃 안에서 activate 해도 그 셸은 make 서브셸이라 끝나면 사라집니다.
#    "내 터미널"에서 활성화하려면 1)번처럼 직접 실행해야 합니다.
activate:
	@echo "macOS / Linux 에서 venv 활성화:"
	@echo "    source $(VENV)/bin/activate"
	@echo ""
	@echo "비활성화:"
	@echo "    deactivate"
	@echo ""
	@echo "Windows (PowerShell) 의 경우:"
	@echo "    .\\$(VENV)\\Scripts\\Activate.ps1"

# venv가 활성화된 서브셸로 진입 (exit 으로 빠져나옴)
shell:
	@$(ACTIVATE); exec $$SHELL

# -----------------------------------------------------------------------------
# 봇 실행
# -----------------------------------------------------------------------------
run:
	$(ACTIVATE); $(PYTHON) -m src.main

# -----------------------------------------------------------------------------
# 보조 도구
# -----------------------------------------------------------------------------
# 새 맵의 루트 녹화
#   make record-route MAP=garden_of_red_2
#   make record-route MAP=garden_of_red_2 CFG=cleric
#   기존 map.png 위에 루트만 추가 녹화하고 싶을 때:
#     make record-route MAP=garden_of_red_2 EXISTING_MAP=minimaps/garden_of_red_2/map.png
record-route:
	$(ACTIVATE); $(PYTHON) -m tools.routeRecorder \
		--new_map $(MAP) \
		--cfg $(CFG) \
		$(if $(EXISTING_MAP),--map $(EXISTING_MAP),)

# 몬스터 스프라이트 다운로드
#   make download-mob               # 실행 후 프롬프트에 이름 입력
#   make download-mob MOB="Snail"   # 인자로 바로 지정 (echo 로 stdin 전달)
download-mob:
ifeq ($(strip $(MOB)),)
	$(ACTIVATE); $(PYTHON) tools/mob_maker.py
else
	$(ACTIVATE); echo "$(MOB)" | $(PYTHON) tools/mob_maker.py
endif

# -----------------------------------------------------------------------------
# 도움말
# -----------------------------------------------------------------------------
help:
	@echo "주요 타깃:"
	@echo "  make setup              venv 생성 + requirements 설치"
	@echo "  make activate           venv 활성화 명령 안내 (macOS/Linux/Windows)"
	@echo "  make shell              venv 활성화된 서브셸 진입"
	@echo "  make run                PySide6 UI 로 봇 실행"
	@echo "  make record-route MAP=<name> [CFG=<name>] [EXISTING_MAP=<path>]"
	@echo "                          루트 레코더 실행 (자세히는 docs/tools.md)"
	@echo "  make download-mob [MOB=\"<name>\"]"
	@echo "                          몬스터 스프라이트 다운로드"
	@echo "  make clean              venv 삭제"

# -----------------------------------------------------------------------------
# 레거시(전체 화면 맵 기반) 엔진용 단축 명령
# -----------------------------------------------------------------------------
run-fire-land-2:
	$(ACTIVATE); $(PYTHON) mapleStoryAutoLevelUp.py --map fire_land_2 --monsters fire_pig,black_axe_stump --attack directional --cfg=gun
run-ant-cave-2:
	$(ACTIVATE); $(PYTHON) mapleStoryAutoLevelUp.py --map ant_cave_2 --monsters spike_mushroom,zombie_mushroom --attack directional --cfg=gun
run-cloud-balcony:
	$(ACTIVATE); $(PYTHON) mapleStoryAutoLevelUp.py --map cloud_balcony --monsters brown_windup_bear,pink_windup_bear --attack directional --cfg=gun
run-north-forest-training-ground-2:
	$(ACTIVATE); $(PYTHON) mapleStoryAutoLevelUp.py --map north_forest_training_ground_2 --monsters green_mushroom,spike_mushroom --attack directional --cfg=gun
run-lost-time-1:
	$(ACTIVATE); $(PYTHON) mapleStoryAutoLevelUp.py --map lost_time_1 --monsters evolved_ghost --attack directional --cfg=gun
run-north-forest-training-ground-8:
	$(ACTIVATE); $(PYTHON) mapleStoryAutoLevelUp.py --map north_forest_training_ground_8 --monsters wind_single_eye_beast --attack directional --cfg=gun
run-monkey-swamp-3:
	$(ACTIVATE); $(PYTHON) mapleStoryAutoLevelUp.py --map monkey_swamp_3 --monsters angel_monkey --attack aoe_skill --cfg=gun
run-garden-of-red-2:
	$(ACTIVATE); $(PYTHON) mapleStoryAutoLevelUp.py --map garden_of_red_2 --monsters red_cellion --attack directional --cfg=gun
