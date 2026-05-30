import time
import random

# Local import
from src.states.base_state import State

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

    def on_frame(self):
        # 루트 따라 이동 (normal 모드와 동일)
        self.bot.update_cmd_by_route()

        # 루트 목표 지점 도달 시 다음 루트로 순환
        self.bot.check_reach_goal()

        # 몹 검출 대신 주기적으로 공격 (랜덤 지터 적용)
        if self.next_attack_delay is None:
            self.next_attack_delay = self._roll_attack_delay()
        if time.time() - self.bot.t_last_attack > self.next_attack_delay:
            self.bot.cmd_action = "attack"
            self.bot.t_last_attack = time.time()
            self.next_attack_delay = self._roll_attack_delay() # 다음 간격 새로 추첨

        # 끼임 방지: 너무 오래 멈춰있으면 랜덤 명령
        if self.bot.is_player_stuck():
            self.bot.update_cmd_by_random()

        # send command to keyboard controller
        self.bot.kb.set_command(self.bot.cmd_move_x + ' ' + \
                                self.bot.cmd_move_y + ' ' + \
                                self.bot.cmd_action)
