# Standard import
import time
import threading

# Library import
import mss
import cv2
import numpy as np
import Quartz

# Local import
from src.utils.logger import logger

def get_window_title(token):
    '''
    Get window title that contain token
    '''
    window_list = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
        Quartz.kCGNullWindowID
    )
    # Get all exist windows
    for window in window_list:
        title = window.get(Quartz.kCGWindowName, '')
        if token in title:
            return title
    return None

def get_window_owner_pid(window_title):
    '''
    Return the owner process PID of the on-screen window whose title matches.
    '''
    window_list = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
        Quartz.kCGNullWindowID
    )
    for window in window_list:
        if window.get(Quartz.kCGWindowName, '') == window_title:
            return window.get(Quartz.kCGWindowOwnerPID)
    return None

def resize_window_mac(window_title, width_pt, height_pt):
    '''
    Resize a macOS window via the Accessibility (AX) API.

    width_pt / height_pt are in *points* (the AX coordinate space). On Retina
    displays points = pixels / backing_scale, so the caller must convert from
    desired pixel size using the capture scale.

    Requires Accessibility permission for the app running Python
    (System Settings > Privacy & Security > Accessibility). Returns True on
    success, False otherwise (logs a warning). Never raises.
    '''
    try:
        from ApplicationServices import (
            AXUIElementCreateApplication, AXUIElementCopyAttributeValue,
            AXUIElementSetAttributeValue, AXValueCreate, AXIsProcessTrusted,
            kAXWindowsAttribute, kAXSizeAttribute, kAXTitleAttribute,
            kAXValueTypeCGSize,
        )
    except Exception as e:  # pragma: no cover - framework missing
        logger.warning(f"[resize_window_mac] AX framework unavailable: {e}")
        return False

    if not AXIsProcessTrusted():
        logger.warning(
            "[resize_window_mac] 손쉬운 사용(Accessibility) 권한이 없어 창 크기를 "
            "조정할 수 없습니다. 시스템 설정 > 개인정보 보호 및 보안 > 손쉬운 사용 "
            "에서 터미널/IDE 를 허용하세요."
        )
        return False

    pid = get_window_owner_pid(window_title)
    if pid is None:
        logger.warning(f"[resize_window_mac] window not found: {window_title}")
        return False

    app = AXUIElementCreateApplication(pid)
    err, windows = AXUIElementCopyAttributeValue(app, kAXWindowsAttribute, None)
    if err or not windows:
        logger.warning(f"[resize_window_mac] no AX windows for pid {pid} (err={err})")
        return False

    # Prefer the window whose title matches; fall back to the first window.
    target = None
    for win in windows:
        _, title = AXUIElementCopyAttributeValue(win, kAXTitleAttribute, None)
        if title == window_title:
            target = win
            break
    if target is None:
        target = windows[0]

    size_val = AXValueCreate(kAXValueTypeCGSize,
                             Quartz.CGSizeMake(float(width_pt), float(height_pt)))
    set_err = AXUIElementSetAttributeValue(target, kAXSizeAttribute, size_val)
    if set_err:
        logger.warning(f"[resize_window_mac] set size failed (err={set_err})")
        return False
    logger.info(f"[resize_window_mac] resized '{window_title}' to "
                f"{width_pt:.0f}x{height_pt:.0f} pt")
    return True

def get_window_region(window_title):
    window_list = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
        Quartz.kCGNullWindowID
    )
    # Get all exist windows
    all_titles = []
    for window in window_list:
        title = window.get(Quartz.kCGWindowName, '')
        owner = window.get(Quartz.kCGWindowOwnerName, '')
        if title:
            all_titles.append(f"{title} (Owner: {owner})")
    logger.debug(f"all_titles: {all_titles}")
    for window in window_list:
        if window.get(Quartz.kCGWindowName, '') == window_title:
            bounds = window.get(Quartz.kCGWindowBounds, {})
            return {
                "left": int(bounds.get('X', 0)),
                "top": int(bounds.get('Y', 0)),
                "width": int(bounds.get('Width', 0)),
                "height": int(bounds.get('Height', 0))
            }
    return None

class GameWindowCapturor:
    '''
    GameWindowCapturor for macOS
    '''
    def __init__(self, cfg):
        self.cfg = cfg
        self.frame = None
        self.lock = threading.Lock()
        self.is_terminated = False

        self.window_title = get_window_title(cfg["game_window"]["title"])
        if self.window_title is None:
            logger.error(
                f"[GameWindowCapturor] Unable to find window titles that contain {cfg['game_window']['title']}"
            )
            return -1

        self.fps = 0
        self.fps_limit = cfg["system"]["fps_limit_window_capturor"]
        self.t_last_run = 0.0

        # 使用 mss 來擷取特定螢幕區域
        self.capture = mss.mss()

        # Get game window region
        self.update_window_region()

        # start game window capture
        threading.Thread(target=self.start_capture, daemon=True).start()

        # Wait frame init
        time.sleep(0.1)
        while self.frame is None:
            self.limit_fps()

        # Auto-resize the game window so the captured frame matches game_window.size
        if cfg["game_window"].get("auto_resize", True):
            self.resize_to_target()

    def resize_to_target(self):
        '''
        Resize the game window (via AX) so the captured frame ends up the size
        configured in game_window.size (+ title_bar_height for the title bar).

        Works in pixel space but the AX API expects points, so it derives the
        display scale from the already-captured frame:
            scale = frame_pixels_width / window_region_points_width
        and sets the AX size to target_pixels / scale.
        '''
        gw = self.cfg["game_window"]
        with self.lock:
            frame = None if self.frame is None else self.frame.copy()
        if frame is None or not self.region or not self.region.get("width"):
            return

        cur_w_px, cur_h_px = frame.shape[1], frame.shape[0]
        target_w_px = gw["size"][1]
        target_h_px = gw["size"][0] + gw["title_bar_height"]

        # Already the right size (allow a few px tolerance) -> nothing to do.
        if abs(cur_w_px - target_w_px) <= 4 and abs(cur_h_px - target_h_px) <= 4:
            logger.info(f"[GameWindowCapturor] window already {cur_w_px}x{cur_h_px}px, "
                        f"no resize needed")
            return

        scale = cur_w_px / float(self.region["width"])  # pixels per point
        if scale <= 0:
            return
        target_w_pt = target_w_px / scale
        target_h_pt = target_h_px / scale

        logger.info(f"[GameWindowCapturor] resizing window: captured "
                    f"{cur_w_px}x{cur_h_px}px -> target {target_w_px}x{target_h_px}px "
                    f"(scale={scale:.2f}, AX {target_w_pt:.0f}x{target_h_pt:.0f}pt)")
        if resize_window_mac(self.window_title, target_w_pt, target_h_pt):
            time.sleep(0.3)  # let the window settle
            self.update_window_region()

    def start_capture(self):
        '''
        開始螢幕擷取，並不斷更新 frame。
        '''
        while not self.is_terminated:
            # Update self.region
            self.update_window_region()

            # Update self.frame
            self.capture_frame()

            # Limit FPS to save systme resources
            self.limit_fps()

    def stop(self):
        '''
        Stop capturing thread
        '''
        self.is_terminated = True
        logger.info("[GameWindowCapturor] Terminated")

    def update_window_region(self):
        '''
        Update window region
        '''
        self.region = get_window_region(self.window_title)
        if self.region is None:
            text = f"Cannot find window: {self.window_title}"
            logger.error(text)
            raise RuntimeError(text)

    def capture_frame(self):
        '''
        捕捉當前遊戲區域畫面
        '''
        img = self.capture.grab(self.region)
        frame = np.array(img)
        with self.lock:
            self.frame = frame

    def get_frame(self):
        '''
        安全地獲取最新的螢幕畫面
        '''
        with self.lock:
            if self.frame is None:
                return None
            # cv2.imwrite("debug_frame.png", self.frame)
            return cv2.cvtColor(self.frame, cv2.COLOR_BGRA2BGR)

    def on_closed(self):
        '''
        捕捉結束後的回調
        '''
        logger.warning("Capture session closed.")
        cv2.destroyAllWindows()

    def limit_fps(self):
        '''
        Limit FPS
        '''
        # If the loop finished early, sleep to maintain target FPS
        target_duration = 1.0 / self.fps_limit  # seconds per frame
        frame_duration = time.time() - self.t_last_run
        if frame_duration < target_duration:
            time.sleep(target_duration - frame_duration)

        # Update FPS
        self.fps = round(1.0 / (time.time() - self.t_last_run))
        self.t_last_run = time.time()
        # logger.info(f"FPS = {self.fps}")
