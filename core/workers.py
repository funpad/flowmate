import time
import sys
import psutil
from PyQt6.QtCore import QThread, pyqtSignal
from core.ai import AIGuardian

# Platform-specific imports
if sys.platform == 'darwin':  # macOS
    try:
        from Quartz import (
            CGWindowListCopyWindowInfo,
            kCGWindowListOptionOnScreenOnly,
            kCGNullWindowID
        )
        from AppKit import NSWorkspace
        PLATFORM_SUPPORTED = True
    except ImportError:
        PLATFORM_SUPPORTED = False
        print("Warning: macOS window monitoring requires pyobjc. Install with: pip install pyobjc-framework-Quartz pyobjc-framework-AppKit")
elif sys.platform == 'win32':  # Windows
    try:
        import win32gui
        import win32process
        PLATFORM_SUPPORTED = True
    except ImportError:
        PLATFORM_SUPPORTED = False
        print("Warning: Windows window monitoring requires pywin32. Install with: pip install pywin32")
else:
    PLATFORM_SUPPORTED = False
    print(f"Warning: Window monitoring not supported on platform: {sys.platform}")


def get_active_window_info():
    """Get active window title and process name in a cross-platform way"""
    if not PLATFORM_SUPPORTED:
        return "Unknown", "Unknown"
    
    try:
        if sys.platform == 'darwin':  # macOS
            # Get active application
            workspace = NSWorkspace.sharedWorkspace()
            active_app = workspace.activeApplication()
            app_name = active_app.get('NSApplicationName', 'Unknown')
            pid = active_app.get('NSApplicationProcessIdentifier', 0)
            
            # Get window title from frontmost window
            window_list = CGWindowListCopyWindowInfo(
                kCGWindowListOptionOnScreenOnly,
                kCGNullWindowID
            )
            
            title = ""
            for window in window_list:
                window_pid = window.get('kCGWindowOwnerPID', 0)
                if window_pid == pid:
                    window_layer = window.get('kCGWindowLayer', 0)
                    if window_layer == 0:  # Normal window layer
                        title = window.get('kCGWindowName', '')
                        if title:
                            break
            
            if not title:
                title = app_name
            
            # Get process name
            try:
                proc = psutil.Process(pid).name()
            except:
                proc = app_name
            
            return title, proc
            
        elif sys.platform == 'win32':  # Windows
            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd)
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            try:
                proc = psutil.Process(pid).name()
            except:
                proc = "System"
            return title, proc
            
    except Exception as e:
        print(f"Error getting active window: {e}")
        return "Unknown", "Unknown"
    
    return "Unknown", "Unknown"


class PlannerThread(QThread):
    result_signal = pyqtSignal(list)
    def __init__(self, goal): 
        super().__init__() 
        self.goal = goal
        self.ai = AIGuardian()
    def run(self): 
        self.result_signal.emit(self.ai.smart_planner(self.goal))


class MonitorThread(QThread):
    update_signal = pyqtSignal(str, str, bool, str)
    def __init__(self, user_goal): 
        super().__init__()
        self.user_goal = user_goal
        self.running = True
        self.ai = AIGuardian()
        self.last_check = (0, "")
        
    def run(self):
        if not PLATFORM_SUPPORTED:
            # Gracefully degrade - emit a message and stop
            self.update_signal.emit("System", "Window monitoring not available", False, "Platform not supported")
            return
            
        self.ai.create_task_profile(self.user_goal)
        while self.running:
            try:
                title, proc = get_active_window_info()
                
                # 白名单逻辑优化：显式发送"安全"信号，以便UI能清除Distraction状态
                proc_lower = proc.lower()
                if "flowmate" in proc_lower or "python" in proc_lower or "FlowMate" in title:
                    self.update_signal.emit(proc, title, False, "FlowMate Safe")
                    self.last_check = (time.time(), title)
                    time.sleep(1)
                    continue

                t = time.time()
                
                if title != self.last_check[1] or t - self.last_check[0] > 5:
                    is_d, reason = self.ai.judge(self.user_goal, title, proc)
                    self.update_signal.emit(proc, title, is_d, reason)
                    self.last_check = (t, title)
            except Exception as e:
                print(f"Monitor error: {e}")
                pass
            time.sleep(1)
            
    def stop(self): 
        self.running = False


class ReportThread(QThread):
    result_signal = pyqtSignal(str)
    def __init__(self, db): 
        super().__init__()
        self.db = db
        self.ai = AIGuardian()
    def run(self): 
        tasks, dists = self.db.get_today_stats()
        self.result_signal.emit(self.ai.generate_daily_report(tasks, dists))