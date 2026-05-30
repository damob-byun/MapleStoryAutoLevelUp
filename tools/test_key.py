'''
pynput 키 입력 감지 격리 테스트 (macOS 권한 진단용)

실행:
    source venv/bin/activate
    python tools/test_key.py

- 아무 키나 누르면 "감지됨: ..." 이 출력됩니다.
- F2 를 눌렀을 때 "감지됨: Key.f2" 가 뜨면 pynput 정상.
- 아무것도 안 뜨면 → 입력 모니터링/손쉬운 사용 권한 없음 (터미널.app 에 부여 필요)
- ESC 를 누르면 종료.
'''
from pynput import keyboard

print("=" * 50)
print("아무 키나 눌러보세요 (F2 포함).")
print("ESC 를 누르면 종료합니다.")
print("=" * 50)

def on_press(key):
    print(f"감지됨: {key}")
    if key == keyboard.Key.esc:
        print("ESC 감지, 종료합니다.")
        return False  # 리스너 종료

with keyboard.Listener(on_press=on_press) as listener:
    listener.join()
