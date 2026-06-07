import time
import random

# Local import
from src.states.base_state import State
from src.utils.logger import logger

class PatrolState(State):
    '''
    patrol 모드: normal 처럼 미니맵 루트(route*.png)를 따라 이동하되,
    몹 검출(템플릿 매칭) 대신 주기적으로 공격한다.
    배경이 몹과 비슷해 템플릿 매칭이 불가한 맵에서 안정적으로 사냥하기 위함.
    '''
    def __init__(self, name, bot):
        super().__init__(name, bot)
        self.bot = bot
        self.next_attack_delay = None # 다음 공격까지 목표 간격(랜덤 지터 포함)
        self.t_hp_hold_until = 0.0    # 몹 HP 바 감지 시 공격 유지 종료 시각
        self.t_hp_hold_start = None   # 연속 HP-홀드(제자리 정지) 시작 시각. 끼임 판정용
        self.t_hp_suppress_until = 0.0 # 끼임/오인식 판정 후 HP 검출 무시 종료 시각


    def _roll_attack_delay(self):
        '''공격 간격에 랜덤 지터를 더해 매크로 감지 회피'''
        base = self.bot.cfg["patrol"]["patrol_attack_interval"]
        jitter = self.bot.cfg["patrol"].get("patrol_attack_interval_random", 0.0)
        return base + random.uniform(0.0, jitter)

    def on_enter(self):
        pass

    def on_exit(self):
        pass

    def check_transitions(self):
        return None

    def _attack_on_interval(self):
        '''공격 간격(랜덤 지터 포함)이 지났으면 cmd_action 을 "attack" 으로 설정.'''
        if self.next_attack_delay is None:
            self.next_attack_delay = self._roll_attack_delay()
        if time.time() - self.bot.t_last_attack > self.next_attack_delay:
            self.bot.cmd_action = "attack"
            self.bot.t_last_attack = time.time()
            self.next_attack_delay = self._roll_attack_delay() # 다음 간격 새로 추첨

    def on_frame(self):
        bot = self.bot

        # 먼저 루트 명령 계산 (이동/점프/로프 여부를 알아야 분기 가능)
        bot.update_cmd_by_route()
        bot.check_reach_goal() # 루트 목표 도달 시 다음 루트로 순환

        # 점프/로프(회색=none up none, 점프 색상 코드) "통과 구간" 여부
        # 이 구간에선 멈추지 말고 점프키+방향키를 누른 채 통과한다.
        is_traverse = (bot.cmd_action == "jump" or bot.cmd_move_y in ("up", "down"))

        hp_detect = bot.cfg["patrol"].get("hp_bar_detect", True)

        # 끼임/오인식 판정 후 쿨다운 동안엔 HP 검출을 무시해 루트로 빠져나간다.
        hp_suppressed = time.time() < self.t_hp_suppress_until

        if hp_detect and not hp_suppressed and bot.has_enemy_hp_bar_near_player():
            duration = bot.cfg["patrol"].get("hp_bar_hold_duration", 1.0)
            self.t_hp_hold_until = time.time() + duration
            if self.t_hp_hold_start is None:
                self.t_hp_hold_start = time.time() # 연속 정지 시작 시각 기록

        if is_traverse:
            # 점프/로프 구간: 멈추지 말고 통과 (HP 바 검출보다 통과 우선).
            # jump_hold(점프키 홀드)는 "점프 색상코드" 와 "위로 오르는 로프(up)" 에만 적용.
            # ⚠️ down(연노랑 none down none)에는 점프를 적용하지 않는다.
            #    점프+아래 = 발판 아래로 드롭 → 루트 밖으로 떨어져 아래키가 안 떨어지는 문제 방지.
            #    down 은 루트 명령 그대로(방향키만) → 로프를 타고 정상적으로 내려간다.
            if bot.cmd_action == "teleport" and bot.cmd_move_y == "down":
                # 텔레포트-다운(보라 none down teleport)은 텔레포트 대신
                # 그냥 아래 방향키만 눌러 내려가게 한다 (down 로프와 동일 동작).
                bot.cmd_action = "none"
            elif bot.cmd_action == "teleport":
                pass # 그 외 텔레포트(핑크 up / 진녹색·갈색 좌우)는 그대로
            elif bot.cmd_action == "jump" or bot.cmd_move_y == "up":
                bot.cmd_action = "jump_hold"
            # else: down 등은 루트 명령 그대로 유지(점프 없음)
            # 통과 구간에선 정지 홀드를 해제 (연속 정지 카운트 리셋)
            self.t_hp_hold_start = None
        elif not hp_suppressed and time.time() < self.t_hp_hold_until:
            max_hold = bot.cfg["patrol"].get("hp_bar_hold_max_duration", 5.0)
            if self.t_hp_hold_start is not None and \
               time.time() - self.t_hp_hold_start > max_hold:
                # 초록 HP 정지가 max_hold 초 이상 연속 → 끼임/오인식 판정.
                # HP 검출을 잠시 무시하고 루트로 빠져나간다.
                cooldown = bot.cfg["patrol"].get("hp_bar_stuck_cooldown", 3.0)
                logger.warning(
                    f"[patrol] 초록 HP 바 정지 {max_hold:.0f}초 초과 → 끼임/오인식 판정. "
                    f"{cooldown:.0f}초간 검출 무시하고 루트로 빠져나감.")
                self.t_hp_suppress_until = time.time() + cooldown
                self.t_hp_hold_until = 0.0
                self.t_hp_hold_start = None
                # 이번 프레임은 멈추지 말고 루트 이동 + 주기 공격
                self._attack_on_interval()
                if bot.is_player_stuck():
                    bot.update_cmd_by_random()
            else:
                # 플레이어 주변에 몹 HP 바가 감지되었거나 홀드가 진행 중인 경우:
                # 초록 HP 가 사라질 때까지 제자리에서 스킬 시전 방식에 따라 공격.
                bot.cmd_move_x = "none"
                bot.cmd_move_y = "none"
                bot.cmd_action = bot.cfg["patrol"].get("hp_bar_action", "attack_hold")
                # 홀드나 공격 중엔 주기 공격 타이머를 계속 리셋 → 끝나도
                # 곧바로 추가 단발 AOE 가 나가지 않도록 한다.
                bot.t_last_attack = time.time()
                self.next_attack_delay = None

        else:
            # 평소: 루트 따라 이동 + 주기 공격
            self.t_hp_hold_start = None # 홀드 종료 → 연속 정지 카운트 리셋
            self._attack_on_interval()
            # 끼임 방지: 너무 오래 멈춰있으면 랜덤 명령
            if bot.is_player_stuck():
                bot.update_cmd_by_random()

        # send command to keyboard controller
        bot.kb.set_command(bot.cmd_move_x + ' ' + \
                           bot.cmd_move_y + ' ' + \
                           bot.cmd_action)
