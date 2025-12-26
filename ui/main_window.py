import sys
import time
# 【修复点 1】在此处导入 QApplication
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit,
                             QPushButton, QHBoxLayout, QFrame, QMessageBox,
                             QSystemTrayIcon, QMenu)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QCursor, QMovie, QIcon, QAction, QPixmap, QPainter, QColor
from core.config import CONFIG, MOCK_MODE
from core.database import DatabaseManager
from core.utils import check_assets
from core.workers import PlannerThread, MonitorThread
from ui.dialogs import SettingsDialog, PlanDialog, ReportDialog, Toast
from ui.styles import MAIN_WINDOW_STYLE, BREAK_STYLE, ALERT_STYLE

class FlowMate(QWidget):
    def __init__(self):
        super().__init__()
        check_assets()
        self.db = DatabaseManager()
        self.current_session_id = None
        self.task_queue = []
        self.current_index = -1
        self.state = "IDLE"
        self.monitor = None

        self.movie_focus = QMovie("assets/focus.gif")
        self.movie_break = QMovie("assets/break.gif")
        self.movie_alert = QMovie("assets/alert.gif")
        for m in [self.movie_focus, self.movie_break, self.movie_alert]: m.setCacheMode(QMovie.CacheMode.CacheAll)
        self.tray_icon = None # 确保在init_tray之前初始化
        self.toast = Toast()  # 初始化极简提醒
        self.show_toast = True # 弹幕开关
        self.last_audio_time = 0  # 声音节流锁

        self.initUI()
        self.init_tray() # 初始化托盘

        self.timer = QTimer(); self.timer.timeout.connect(self.tick)

    def initUI(self):
        self.setFixedSize(320, 260)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 屏幕居中
        screen = QApplication.primaryScreen().geometry()
        self.move(
            (screen.width() - self.width()) // 2,
            (screen.height() - self.height()) // 2
        )


        # Layer 1: Avatar
        self.avatar_bg = QLabel(self); self.avatar_bg.setGeometry(0, 0, self.width(), self.height()); self.avatar_bg.setScaledContents(True); self.avatar_bg.lower()

        # Layer 2: Content
        self.content_layer = QFrame(self); self.content_layer.setGeometry(0, 0, self.width(), self.height())
        self.content_layer.setStyleSheet(MAIN_WINDOW_STYLE)

        layout = QVBoxLayout(self.content_layer)

        top = QHBoxLayout()
        top.setContentsMargins(5, 5, 5, 0)
        top.setSpacing(8)
        
        self.step_lbl = QLabel("FlowMate Pet")
        self.step_lbl.setStyleSheet("color: #AAA; font-size: 11px; font-weight: bold; border:none;")
        
        btn_style = "QPushButton { background:transparent; border:none; color:#999; font-size:16px; } QPushButton:hover { color:white; }"
        
        btn_set = QPushButton("⚙️")
        btn_set.setFixedSize(26, 26)
        btn_set.setToolTip("设置")
        btn_set.clicked.connect(self.open_set)
        btn_set.setStyleSheet(btn_style)
        
        btn_rep = QPushButton("📊")
        btn_rep.setFixedSize(26, 26)
        btn_rep.setToolTip("报告")
        btn_rep.clicked.connect(self.open_rep)
        btn_rep.setStyleSheet(btn_style)

        btn_cls = QPushButton("×")
        btn_cls.setFixedSize(26, 26)
        btn_cls.setToolTip("隐藏 (彻底退出请右键托盘)")
        btn_cls.clicked.connect(self.close)
        btn_cls.setStyleSheet("""
            QPushButton { background:transparent; border:none; color:#888; font-size:22px; font-weight:bold; padding-bottom:2px; }
            QPushButton:hover { background:#E81123; color:white; border-radius:4px; }
        """)

        top.addWidget(self.step_lbl)
        top.addStretch()
        top.addWidget(btn_set)
        top.addWidget(btn_rep)
        top.addWidget(btn_cls)
        layout.addLayout(top)

        layout.addStretch(1)
        self.task_lbl = QLabel("准备就绪"); self.task_lbl.setWordWrap(True); self.task_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); self.task_lbl.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold)); self.task_lbl.setStyleSheet("color: white; border:none;")
        layout.addWidget(self.task_lbl)

        self.time_lbl = QLabel("00:00"); self.time_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); self.time_lbl.setStyleSheet("color: white; font-size: 40px; font-weight: bold; font-family: Arial; border:none;")
        layout.addWidget(self.time_lbl); layout.addStretch(1)

        self.in_box = QWidget(); hl = QHBoxLayout(self.in_box); hl.setContentsMargins(0,0,0,0)
        self.inp = QLineEdit(); self.inp.setPlaceholderText("🎯 输入目标..."); self.inp.setStyleSheet("background: rgba(40,40,50,0.8); color:white; border:1px solid #555; padding:8px; border-radius:5px;")
        self.inp.returnPressed.connect(self.plan) # 回车直接提交
        self.mag = QPushButton("✨"); self.mag.setFixedSize(36,36); self.mag.clicked.connect(self.plan); self.mag.setStyleSheet("background:#6C5CE7; color:white; border-radius:5px;")
        hl.addWidget(self.inp); hl.addWidget(self.mag); layout.addWidget(self.in_box)

        self.act_box = QWidget(); al = QHBoxLayout(self.act_box); al.setContentsMargins(0,0,0,0); self.act_box.hide()
        self.btn_ab = QPushButton("⛔ 放弃"); self.btn_ab.clicked.connect(self.abandon); self.btn_ab.setStyleSheet("background:rgba(200,50,50,0.2); color:#FF8888; border:1px solid #FF5555; border-radius:5px; padding:8px;")
        self.btn_ok = QPushButton("✅ 完成"); self.btn_ok.clicked.connect(self.next); self.btn_ok.setStyleSheet("background:#4CAF50; color:white; border-radius:5px; padding:8px; font-weight:bold;")
        al.addWidget(self.btn_ab); al.addWidget(self.btn_ok); layout.addWidget(self.act_box)

        self.set_state("FOCUS"); self.drag_pos = None

    # ================= 系统托盘逻辑 =================
    def init_tray(self):
        self.tray_icon = QSystemTrayIcon(self)

        # 默认就绪图标
        self.tray_icon.setIcon(QIcon("assets/tray_idle.png"))

        # 菜单
        menu = QMenu()
        
        # 1. 任务列表 (管理入口)
        # 1. 任务列表 (管理入口) / 显示主界面
        self.action_manage = QAction("🖥️ 显示主界面", self)
        self.action_manage.triggered.connect(self.open_manage_dialog)
        menu.addAction(self.action_manage)
        
        # 1.1 今日日报
        action_report = QAction("📊 今日日报", self)
        action_report.triggered.connect(self.open_rep)
        menu.addAction(action_report)
        
        menu.addSeparator()

        # 2. 暂停/恢复
        self.action_pause = QAction("⏸️ 暂停", self)
        self.action_pause.setCheckable(True)
        self.action_pause.toggled.connect(self.toggle_pause)
        menu.addAction(self.action_pause)

        # 3. 放弃
        self.action_abandon = QAction("🛑 放弃任务", self)
        self.action_abandon.triggered.connect(self.abandon)
        self.action_abandon.setEnabled(False) # 默认禁用
        menu.addAction(self.action_abandon)

        menu.addSeparator()

        # 4. 弹幕开关
        self.action_toast = QAction("👁️ 显示弹幕", self)
        self.action_toast.setCheckable(True)
        self.action_toast.setChecked(True)
        self.action_toast.toggled.connect(self.toggle_toast_cfg)
        menu.addAction(self.action_toast)

        # 5. 设置
        action_settings = QAction("⚙️ 设置", self)
        action_settings.triggered.connect(self.open_set)
        menu.addAction(action_settings)
        
        # 6. 退出
        action_quit = QAction("❌ 退出程序", self)
        action_quit.triggered.connect(self.quit_app)
        menu.addAction(action_quit)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()

    def show_window(self):
        self.showNormal()
        self.activateWindow()

    def open_manage_dialog(self):
        """打开正在运行的任务管理列表 或 显示主界面"""
        if not self.task_queue:
             self.show_window(); return # 如果没任务，直接显示主窗口

        # 记录旧状态用于比对
        old_tasks = [t.copy() for t in self.task_queue]
        
        dlg = PlanDialog(self.task_queue, self, mode="MANAGING")
        if dlg.exec():
            # 更新任务队列
            new_tasks = dlg.tasks
            
            # 检查当前任务时间是否变动，实时调整倒计时
            if 0 <= self.current_index < len(new_tasks):
                old_t = old_tasks[self.current_index]
                new_t = new_tasks[self.current_index]
                
                # 如果是专注状态且时长变了
                if self.state == "FOCUS" and new_t['duration'] != old_t['duration']:
                    diff = (new_t['duration'] - old_t['duration']) * 60
                    self.duration += diff
                    self.update_tm()
                
                # 如果是休息状态且时长变了
                if self.state == "BREAK" and new_t['break'] != old_t['break']:
                    diff = (new_t['break'] - old_t['break']) * 60
                    self.duration += diff
                    self.update_tm()

            self.task_queue = new_tasks
            # 刷新标签
            if self.state == "FOCUS":
                self.task_lbl.setText(self.task_queue[self.current_index]['step'])
        
        # 保持焦点
        self.activateWindow()

    def toggle_toast_cfg(self, checked):
        self.show_toast = checked
        if not checked: self.toast.hide()

    def on_tray_click(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible(): self.hide()
            else: self.show_window()

    def toggle_pause(self, checked):
        if checked:
            if self.monitor: self.monitor.stop()
            self.task_lbl.setText("💤 监督已暂停")
            self.action_pause.setText("▶️ 恢复监督")
            self.tray_icon.setIcon(QIcon("assets/tray_paused.png")) # 暂停图标
        else:
            if self.state == "FOCUS" and self.task_queue:
                step = self.task_queue[self.current_index]['step']
                self.monitor = MonitorThread(step)
                self.monitor.update_signal.connect(self.on_mon)
                self.monitor.start()
                self.task_lbl.setText(step)
                self.tray_icon.setIcon(QIcon("assets/tray_active.png")) # 恢复活跃图标
            self.action_pause.setText("⏸️ 暂停监督")

    # ================= 关闭拦截 =================
    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            "FlowMate", "我在后台等你~ 双击托盘图标唤醒。",
            QSystemTrayIcon.MessageIcon.Information, 2000
        )

    def quit_app(self):
        """【修复点 2】使用导入后的 QApplication 退出"""
        if self.monitor: self.monitor.stop()
        self.tray_icon.hide()
        QApplication.quit()

    # ================= 原有逻辑 =================
    def set_state(self, state):
        if self.avatar_bg.movie(): self.avatar_bg.movie().stop()
        m = None
        if state == "FOCUS": m = self.movie_focus; self.content_layer.setStyleSheet(MAIN_WINDOW_STYLE)
        elif state == "BREAK": m = self.movie_break; self.content_layer.setStyleSheet(BREAK_STYLE)
        elif state == "ALERT": m = self.movie_alert; self.content_layer.setStyleSheet(ALERT_STYLE)
        if m and m.isValid(): self.avatar_bg.setMovie(m); m.start()
        else: self.avatar_bg.clear()

    def open_set(self): 
        if SettingsDialog(self).exec(): 
            if self.monitor: self.monitor.ai.reload_client()
            self.task_lbl.setText("✅ 已更新"); QTimer.singleShot(1000, lambda: self.task_lbl.setText(self.task_queue[self.current_index]['step'] if self.task_queue else "准备就绪"))

    def plan(self):
        g = self.inp.text(); 
        if not g: return
        if not CONFIG.get("api_key") and not MOCK_MODE: QMessageBox.warning(self,"提示","请先点击⚙️设置API Key"); self.open_set(); return
        self.inp.setText("🤖 规划中..."); self.mag.setDisabled(True)
        self.th = PlannerThread(g); self.th.result_signal.connect(self.on_plan); self.th.start()

    def on_plan(self, tasks):
        self.inp.clear(); self.mag.setDisabled(False)
        if not tasks: self.task_lbl.setText("AI 响应失败"); return
        dlg = PlanDialog(tasks, self)
        if dlg.exec(): 
            self.task_queue = dlg.tasks; self.current_index = -1; self.load_next()

    def load_next(self):
        self.hide() # 开始任务后隐藏主窗口
        self.action_manage.setText("📋 任务列表") # 菜单变为任务列表
        self.action_abandon.setEnabled(True) # 启用放弃
        self.tray_icon.setIcon(QIcon("assets/tray_active.png")) # 切换活跃图标
        self.current_index += 1
        if self.current_index >= len(self.task_queue): self.reset(); self.task_lbl.setText("🎉 完成!"); self.open_rep(); return
        t = self.task_queue[self.current_index]
        self.state = "FOCUS"; self.duration = t['duration'] * 60; self.current_session_id = self.db.start_session(t['step'], t['duration'])
        
        self.toggle_ui(False); self.step_lbl.setText(f"Step {self.current_index+1}/{len(self.task_queue)}"); self.task_lbl.setText(t['step']); self.update_tm(); self.set_state("FOCUS")
        if self.monitor: self.monitor.stop()
        self.monitor = MonitorThread(t['step']); self.monitor.update_signal.connect(self.on_mon); self.monitor.start(); self.timer.start(1000)

    def start_break(self):
        if self.current_session_id: self.db.end_session(self.current_session_id, "COMPLETED"); self.current_session_id = None
        self.state = "BREAK"; t = self.task_queue[self.current_index]; self.duration = t.get('break', 5) * 60
        if self.monitor: self.monitor.stop()
        self.task_lbl.setText("☕ 休息时间"); self.update_tm(); self.set_state("BREAK"); self.toggle_ui(False)

    def abandon(self):
        # 无需二次确认，直接放弃
        if self.current_session_id: self.db.end_session(self.current_session_id, "ABANDONED")
        self.reset(); self.task_lbl.setText("🚫 已放弃"); self.set_state("ALERT"); QTimer.singleShot(1500, lambda: self.set_state("FOCUS"))

    def next(self):
        if self.state == "FOCUS": self.start_break()
        elif self.state == "BREAK": self.load_next()

    def reset(self):
        self.state = "IDLE"; self.task_lbl.setText("准备就绪"); self.time_lbl.setText("00:00"); self.task_queue=[]; self.current_index=-1
        self.action_manage.setText("🖥️ 显示主界面") # 恢复菜单
        self.action_abandon.setEnabled(False) # 禁用放弃
        self.tray_icon.setIcon(QIcon("assets/tray_idle.png")) # 恢复就绪图标
        self.tray_icon.setToolTip("FlowMate - Ready")
        if self.monitor: self.monitor.stop()
        self.timer.stop(); self.toggle_ui(True); self.set_state("FOCUS")

    def open_rep(self): ReportDialog(self.db, self).exec()
    def tick(self):
        if self.duration > 0: 
            self.duration -= 1; self.update_tm()
            # 更新托盘 Tooltip
            m, s = divmod(self.duration, 60)
            status_icon = "🔥" if self.state == "FOCUS" else "☕"
            task_name = self.task_queue[self.current_index]['step'] if self.task_queue else "No Task"
            self.tray_icon.setToolTip(f"{status_icon} {m:02d}:{s:02d} - {task_name}")
        else: 
            # Cross-platform notification instead of FlashWindow
            self.activateWindow()
            self.raise_()
            self.tray_icon.showMessage(
                "FlowMate", "⏰ 时间到！", 
                QSystemTrayIcon.MessageIcon.Information, 3000
            )
            self.next()
    def update_tm(self): m, s = divmod(self.duration, 60); self.time_lbl.setText(f"{m:02d}:{s:02d}")
    def toggle_ui(self, show_input):
        if show_input: self.in_box.show(); self.act_box.hide()
        else: 
            self.in_box.hide(); self.act_box.show()
            if self.state == "BREAK": self.btn_ab.hide(); self.btn_ok.setText("⏩ 结束休息")
            else: self.btn_ab.show(); self.btn_ok.setText("✅ 完成")

    def on_mon(self, p, t, d, r):
        if self.state != "FOCUS": return
        if d:
            # 极简提醒逻辑：不改变主界面，只显示弹幕toast
            if self.show_toast:
                self.toast.show_message("⚠️ 注意力分散")
            
            # 播放提示音 (每5秒最多一次)
            now = time.time()
            if now - self.last_audio_time > 5:
                QApplication.beep()
                self.last_audio_time = now

            if self.current_session_id and int(now)%5==0: 
                self.db.log_distraction(self.current_session_id, p, r)
        else:
            self.toast.hide() # 专注回去后隐藏
            if self.avatar_bg.movie() != self.movie_focus: self.set_state("FOCUS")
            self.task_lbl.setText(self.task_queue[self.current_index]['step'])

    def mousePressEvent(self, e): 
        if e.button() == Qt.MouseButton.LeftButton: self.drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft(); e.accept()
    def mouseMoveEvent(self, e): 
        if e.buttons() == Qt.MouseButton.LeftButton and self.drag_pos: self.move(e.globalPosition().toPoint() - self.drag_pos); e.accept()
    def resizeEvent(self, e): self.avatar_bg.setGeometry(0,0,self.width(),self.height()); self.content_layer.setGeometry(0,0,self.width(),self.height()); super().resizeEvent(e)