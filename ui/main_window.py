import sys
import time
# 【修复点 1】在此处导入 QApplication
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QTextEdit,
                             QPushButton, QHBoxLayout, QFrame, QMessageBox,
                             QSystemTrayIcon, QMenu, QProgressBar, QGraphicsOpacityEffect)
from PyQt6.QtCore import Qt, QTimer, QUrl, QPropertyAnimation, QEasingCurve, QRectF  # <--- 加上动画相关组件
from PyQt6.QtGui import QFont, QCursor, QMovie, QIcon, QAction, QPixmap, QPainter, QColor, QPainterPath, QRegion
from PyQt6.QtMultimedia import QSoundEffect
from core.config import CONFIG, MOCK_MODE
from core.database import DatabaseManager
from core.utils import check_assets
from core.workers import PlannerThread, MonitorThread
from ui.dialogs import SettingsDialog, PlanDialog, ReportDialog, Toast
from ui.styles import DIALOG_STYLE

class FlowMate(QWidget):
    def __init__(self):
        super().__init__()
        check_assets()
        self.db = DatabaseManager()
        self.current_session_id = None
        self.task_queue = []
        self.current_index = -1
        self.state = "IDLE"
        self.main_goal = ""  # 存储用户输入的总目标
        self.monitor = None

        self.movie_focus = QMovie("assets/focus.gif")
        self.movie_break = QMovie("assets/break.gif")
        self.movie_alert = QMovie("assets/alert.gif")
        for m in [self.movie_focus, self.movie_break, self.movie_alert]: m.setCacheMode(QMovie.CacheMode.CacheAll)
        self.tray_icon = None # 确保在init_tray之前初始化
        self.toast = Toast()  # 初始化极简提醒
        self.show_toast = True # 弹幕开关
        self.last_audio_time = 0  # 声音节流锁
        # 滑动窗口：记录最近1分钟内的注意力分散事件
        self.distraction_history = []  # [(timestamp, reason), ...]
        self.task_paused = False # 任务暂停 (计时+监督)
        self.supervision_paused = False # 仅监督暂停 (计时继续)

        self.initUI()
        self.init_tray() # 初始化托盘
        
        # 音效初始化
        self.alert_sound = QSoundEffect(self)
        self.alert_sound.setSource(QUrl.fromLocalFile("assets/alert.wav"))
        self.alert_sound.setVolume(0.5)

        self.success_sound = QSoundEffect(self)
        self.success_sound.setSource(QUrl.fromLocalFile("assets/success.wav"))
        self.success_sound.setVolume(0.5)

        self.start_sound = QSoundEffect(self)
        self.start_sound.setSource(QUrl.fromLocalFile("assets/start_task.wav"))
        self.start_sound.setVolume(0.5)

        self.timer = QTimer(); self.timer.timeout.connect(self.tick)

    def initUI(self):
        self.setFixedSize(320, 260)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(DIALOG_STYLE)

        # 屏幕居中
        screen = QApplication.primaryScreen().geometry()
        self.move(
            (screen.width() - self.width()) // 2,
            (screen.height() - self.height()) // 2
        )


        # Layer 1: Avatar
        self.avatar_bg = QLabel(self); self.avatar_bg.setGeometry(0, 0, self.width(), self.height()); self.avatar_bg.setScaledContents(True); self.avatar_bg.lower()
        
        # 为背景 GIF 添加圆角裁切，防止直角溢出
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 15, 15)
        self.avatar_bg.setMask(QRegion(path.toFillPolygon().toPolygon()))

        # Layer 2: Content
        self.content_layer = QFrame(self); self.content_layer.setGeometry(0, 0, self.width(), self.height())
        self.content_layer.setObjectName("ContentLayer")

        layout = QVBoxLayout(self.content_layer)

        top = QHBoxLayout()
        top.setContentsMargins(10, 8, 10, 0)
        top.setSpacing(10)
        
        self.step_lbl = QLabel("FlowMate Pet")
        self.step_lbl.setStyleSheet("color: #AAA; font-size: 11px; font-weight: bold; border:none; background:transparent;")
        
        btn_set = QPushButton("⚙️")
        btn_set.setFixedSize(26, 26)
        btn_set.setToolTip("设置")
        btn_set.clicked.connect(self.open_set)
        btn_set.setObjectName("IconBtn")
        btn_set.setCursor(Qt.CursorShape.PointingHandCursor)
        
        btn_rep = QPushButton("📊")
        btn_rep.setFixedSize(26, 26)
        btn_rep.setToolTip("报告")
        btn_rep.clicked.connect(self.open_rep)
        btn_rep.setObjectName("IconBtn")
        btn_rep.setCursor(Qt.CursorShape.PointingHandCursor)

        btn_cls = QPushButton("×")
        btn_cls.setFixedSize(26, 26)
        btn_cls.setToolTip("隐藏 (彻底退出请右键托盘)")
        btn_cls.clicked.connect(self.close)
        btn_cls.setObjectName("CloseBtn")
        btn_cls.setCursor(Qt.CursorShape.PointingHandCursor)

        self.btn_list = QPushButton("📋")
        self.btn_list.setFixedSize(26, 26)
        self.btn_list.setToolTip("任务列表")
        self.btn_list.clicked.connect(self.open_task_list)
        self.btn_list.setObjectName("IconBtn")
        self.btn_list.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_list.hide()

        top.addWidget(btn_set)
        top.addWidget(self.step_lbl)
        top.addStretch()
        top.addWidget(self.btn_list)
        top.addWidget(btn_rep)
        top.addWidget(btn_cls)
        layout.addLayout(top)

        # --- 内容区域堆叠 ---
        
        # 1. 初始状态 (闲置) - 大输入框
        self.idle_ui = QWidget()
        il = QVBoxLayout(self.idle_ui); il.setContentsMargins(30, 0, 30, 0); il.setSpacing(20)
        il.setAlignment(Qt.AlignmentFlag.AlignCenter)
        il.addStretch(1)
        
        welcome_lbl = QLabel("今天想达成什么目标？")
        welcome_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_lbl.setStyleSheet("color: #888; font-size: 13px; font-weight: 500; background:transparent;")
        il.addWidget(welcome_lbl)
        
        # 输入框容器 (为了上下排列)
        self.in_box = QWidget(); vb = QVBoxLayout(self.in_box); vb.setContentsMargins(0,0,0,0); vb.setSpacing(30)
        vb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.inp = QTextEdit()
        self.inp.setPlaceholderText("🎯 描述你的复杂任务目标...\n建议至少三行内容以获得更精准的规划。\n(回车启动任务，Shift+回车换行)")
        self.inp.setObjectName("BigInput")
        self.inp.setFixedHeight(100) # 约 3-4 行高度
        self.inp.setAcceptRichText(False)
        self.inp.installEventFilter(self) # 安装过滤器以支持回车触发
        
        self.mag = QPushButton("🚀"); self.mag.setFixedSize(50, 50); self.mag.clicked.connect(self.plan);
        self.mag.setObjectName("RocketBtn")
        self.mag.setCursor(Qt.CursorShape.PointingHandCursor)
        
        vb.addWidget(self.inp)
        vb.addWidget(self.mag, 0, Qt.AlignmentFlag.AlignCenter) 
        
        il.addWidget(self.in_box)
        il.addStretch(1)
        layout.addWidget(self.idle_ui)

        # 2. AI 规划中特效 (酷炫动画)
        self.ai_loading_ui = QWidget()
        al0 = QVBoxLayout(self.ai_loading_ui)
        al0.setContentsMargins(0, 0, 0, 0)
        self.ai_loading_ui.hide()
        
        al0.addStretch(1)
        
        # 核心容器 (确保真正居中)
        self.ai_core_container = QWidget()
        al_core = QVBoxLayout(self.ai_core_container)
        al_core.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 核心脉冲球
        self.ai_core = QFrame()
        self.ai_core.setFixedSize(80, 80)
        self.ai_core.setStyleSheet("""
            background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5, stop:0 #6C5CE7, stop:1 transparent);
            border-radius: 40px;
            border: none;
        """)
        
        # 动画效果挂载
        self.ai_opa_effect = QGraphicsOpacityEffect(self.ai_core)
        self.ai_core.setGraphicsEffect(self.ai_opa_effect)
        
        al_core.addWidget(self.ai_core)
        
        self.ai_lbl = QLabel("AI 正在深度思考中...")
        self.ai_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ai_lbl.setStyleSheet("color: #A29BFE; font-size: 13px; font-weight: bold; margin-top: 20px; border:none; background:transparent;")
        al_core.addWidget(self.ai_lbl)
        
        al0.addWidget(self.ai_core_container)
        al0.addStretch(1)
        
        # AI 核心脉冲动画 (透明度)
        self.ai_pulse = QPropertyAnimation(self.ai_opa_effect, b"opacity")
        self.ai_pulse.setDuration(1200)
        self.ai_pulse.setStartValue(1.0)
        self.ai_pulse.setEndValue(0.2)
        self.ai_pulse.setLoopCount(-1)
        self.ai_pulse.setEasingCurve(QEasingCurve.Type.InOutSine)
        
        layout.addWidget(self.ai_loading_ui)

        # 3. 运行中状态 (活动)
        self.active_ui = QWidget()
        al_active = QVBoxLayout(self.active_ui); al_active.setContentsMargins(0,0,0,0); al_active.setSpacing(10)
        
        al_active.addStretch(1)
        self.task_lbl = QLabel("准备就绪"); self.task_lbl.setWordWrap(True); self.task_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); 
        self.task_lbl.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold)); 
        self.task_lbl.setStyleSheet("color: white; border:none; background:transparent;")
        al_active.addWidget(self.task_lbl)

        self.time_lbl = QLabel("00:00"); self.time_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); self.time_lbl.setStyleSheet("color: white; font-size: 40px; font-weight: bold; font-family: Arial; border:none; background:transparent;")
        al_active.addWidget(self.time_lbl)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1000); self.progress_bar.setValue(0); self.progress_bar.setTextVisible(False); self.progress_bar.setFixedHeight(4)
        al_active.addWidget(self.progress_bar)
        al_active.addStretch(1)

        self.act_box = QWidget(); al_btns = QHBoxLayout(self.act_box); al_btns.setContentsMargins(0,0,0,0)
        self.btn_ab = QPushButton("⛔ 放弃"); self.btn_ab.clicked.connect(self.abandon); self.btn_ab.setObjectName("DangerBtn")
        self.btn_ab.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.btn_ps = QPushButton("⏸️ 暂停"); self.btn_ps.clicked.connect(lambda: self.toggle_task_pause(not self.task_paused))
        self.btn_ps.setObjectName("WarningBtn")
        self.btn_ps.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_ps.setFixedWidth(80)
        
        self.btn_ok = QPushButton("✅ 完成"); self.btn_ok.clicked.connect(self.next); self.btn_ok.setObjectName("SuccessBtn")
        self.btn_ok.setCursor(Qt.CursorShape.PointingHandCursor)
        al_btns.addWidget(self.btn_ab); al_btns.addWidget(self.btn_ps); al_btns.addWidget(self.btn_ok)
        al_active.addWidget(self.act_box)
        
        self.active_ui.hide()
        layout.addWidget(self.active_ui)

        # 按钮脉冲动画 (点击火箭后的反馈)
        self.btn_pulse = QPropertyAnimation(self.mag, b"windowOpacity")
        self.btn_pulse.setDuration(800)
        self.btn_pulse.setStartValue(1.0); self.btn_pulse.setEndValue(0.4); self.btn_pulse.setLoopCount(-1); self.btn_pulse.setEasingCurve(QEasingCurve.Type.InOutSine)

        self.set_state("FOCUS"); self.drag_pos = None

    # ================= 系统托盘逻辑 =================
    def init_tray(self):
        self.tray_icon = QSystemTrayIcon(self)

        # 默认就绪图标
        self.tray_icon.setIcon(QIcon("assets/tray_idle.png"))

        # 菜单
        menu = QMenu()
        
        # 1. 显示主界面
        action_show = QAction("🖥️ 显示主界面", self)
        action_show.triggered.connect(self.show_window)
        menu.addAction(action_show)
        
        # 2. 任务列表（仅在有任务时显示）
        self.action_task_list = QAction("📋 任务列表", self)
        self.action_task_list.triggered.connect(self.open_task_list)
        self.action_task_list.setEnabled(False)  # 默认禁用，有任务时启用
        menu.addAction(self.action_task_list)
        
        # 3. 今日日报
        action_report = QAction("📊 今日日报", self)
        action_report.triggered.connect(self.open_rep)
        menu.addAction(action_report)
        
        menu.addSeparator()

        # 4. 任务暂停 (计时+监督)
        self.action_task_pause = QAction("⏸️ 暂停任务", self)
        self.action_task_pause.setCheckable(True)
        self.action_task_pause.setEnabled(False)
        self.action_task_pause.toggled.connect(self.toggle_task_pause)
        menu.addAction(self.action_task_pause)
        
        # 5. 暂停监督 (计时继续)
        self.action_sup_pause = QAction("💤 暂停监督", self)
        self.action_sup_pause.setCheckable(True)
        self.action_sup_pause.setEnabled(False)
        self.action_sup_pause.toggled.connect(self.toggle_sup_pause)
        menu.addAction(self.action_sup_pause)

        # 5. 放弃
        self.action_abandon = QAction("🛑 放弃任务", self)
        self.action_abandon.triggered.connect(self.abandon)
        self.action_abandon.setEnabled(False) # 默认禁用
        menu.addAction(self.action_abandon)

        menu.addSeparator()

        # 6. 弹幕开关
        self.action_toast = QAction("👁️ 显示弹幕", self)
        self.action_toast.setCheckable(True)
        self.action_toast.setChecked(True)
        self.action_toast.toggled.connect(self.toggle_toast_cfg)
        menu.addAction(self.action_toast)

        # 7. 设置
        action_settings = QAction("⚙️ 设置", self)
        action_settings.triggered.connect(self.open_set)
        menu.addAction(action_settings)
        
        # 8. 退出
        action_quit = QAction("❌ 退出程序", self)
        action_quit.triggered.connect(self.quit_app)
        menu.addAction(action_quit)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()

    def show_window(self):
        self.show()
        self.raise_()
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
        self.activateWindow()

    def open_task_list(self):
        """打开任务列表管理对话框，支持更稳健的任务追踪和处理删除当前任务的情况"""
        if not self.task_queue:
            QMessageBox.information(self, "提示", "当前没有运行中的任务")
            return

        # 1. 记下当前正在做的任务 ID (如果有)
        current_task_id = None
        if 0 <= self.current_index < len(self.task_queue):
            current_task_id = self.task_queue[self.current_index].get('id')
        
        old_tasks = [t.copy() for t in self.task_queue]
        dlg = PlanDialog(self.task_queue, self, mode="MANAGING")
        
        if dlg.exec():
            new_tasks = dlg.tasks
            import uuid
            for nt in new_tasks:
                if 'id' not in nt: nt['id'] = str(uuid.uuid4())

            # 2. 找到当前任务在新列表中的位置
            new_idx = -1
            if current_task_id:
                for i, nt in enumerate(new_tasks):
                    if nt.get('id') == current_task_id:
                        new_idx = i
                        break
            
            # 3. 处理逻辑
            if new_idx != -1:
                # 情况 A: 任务依然存在 (可能移动了，或者改名了，或者时长变了)
                old_t = old_tasks[self.current_index]
                new_t = new_tasks[new_idx]
                
                # 如果时长变了，实时补偿
                if self.state == "FOCUS" and new_t['duration'] != old_t['duration']:
                    diff = (new_t['duration'] - old_t['duration']) * 60
                    self.duration = max(0, self.duration + diff)
                elif self.state == "BREAK" and new_t['break'] != old_t['break']:
                    diff = (new_t['break'] - old_t['break']) * 60
                    self.duration = max(0, self.duration + diff)
                
                self.current_index = new_idx
                self.task_queue = new_tasks
                # 同步显示标题和步骤
                if self.state == "FOCUS":
                    self.task_lbl.setText(new_t['step'])
                self.step_lbl.setText(f"Step {self.current_index+1}/{len(self.task_queue)}")
                self.update_tm()
            else:
                # 情况 B: 当前运行的任务被删除了！
                self.task_queue = new_tasks
                
                if not self.task_queue:
                    # 列表全空了，直接重置
                    self.reset()
                    return
                
                # 当前任务既然没了，我们结束旧 Session
                if self.current_session_id:
                    self.db.end_session(self.current_session_id, "DELETED")
                    self.current_session_id = None
                
                # 尝试加载后续任务 (当前的 index 对应新队列里的下一个)
                if self.current_index >= len(self.task_queue):
                    # 如果删掉的是最后一个，且后面没任务了，则完成
                    self.reset(); self.task_lbl.setText("🎉 完成!"); self.open_rep()
                else:
                    # 还在范围内，加载这个新位置的任务 (不需要 index+1)
                    # 我们手动回退一下 index，然后调 load_next()
                    self.current_index -= 1
                    self.load_next()
        
        # 不自动显示主窗口，保持后台运行

    def toggle_toast_cfg(self, checked):
        self.show_toast = checked
        if not checked: self.toast.hide()

    def on_tray_click(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible(): self.hide()
            else: self.show_window()

    # ================= 助手方法 =================
    def eventFilter(self, obj, event):
        # 让文本框支持回车提交 (Shift+Enter 换行)
        if obj == self.inp and event.type() == event.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                    self.plan()
                    return True
        return super().eventFilter(obj, event)

    def toggle_task_pause(self, checked):
        # 任务暂停：停止计时 + 停止监督
        if not self.task_queue or self.state == "IDLE":
            self.action_task_pause.setChecked(False)
            return
            
        self.task_paused = checked
        self.action_task_pause.setChecked(checked) # 同步托盘菜单
        
        if self.task_paused:
            if self.monitor: self.monitor.stop()
            self.task_lbl.setText("⏸️ 任务已暂停")
            self.btn_ps.setText("▶️ 继续")
            self.action_task_pause.setText("▶️ 恢复任务")
            self.tray_icon.setIcon(QIcon("assets/tray_paused.png")) 
        else:
            self.btn_ps.setText("⏸️ 暂停")
            self.action_task_pause.setText("⏸️ 暂停任务")
            self.tray_icon.setIcon(QIcon("assets/tray_active.png"))
            self.refresh_monitor_state()
            if self.state == "BREAK": self.task_lbl.setText("☕ 休息时间")

    def toggle_sup_pause(self, checked):
        # 监督暂停：计时继续 + 停止监督
        if not self.task_queue or self.state == "IDLE":
            self.action_sup_pause.setChecked(False)
            return
            
        self.supervision_paused = checked
        self.action_sup_pause.setChecked(checked) # 同步托盘菜单
        
        if self.supervision_paused:
            if self.monitor: self.monitor.stop()
            if not self.task_paused: self.task_lbl.setText("💤 监督暂停中")
            self.action_sup_pause.setText("▶️ 恢复监督")
        else:
            self.action_sup_pause.setText("💤 暂停监督")
            self.refresh_monitor_state()

    def refresh_monitor_state(self):
        """根据当前状态决定是否启动监督"""
        if self.monitor: self.monitor.stop()
        
        if self.state == "FOCUS" and self.task_queue and not self.task_paused and not self.supervision_paused:
            step = self.task_queue[self.current_index].get('step', "Work")
            self.task_lbl.setText(step)
            self.monitor = MonitorThread(self.main_goal, step)
            self.monitor.update_signal.connect(self.on_mon)
            self.monitor.start()
        elif self.state == "FOCUS" and (self.task_paused or self.supervision_paused):
            # 保持当前步骤文本，除非已经被设置了暂停文案
            pass

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
        if state == "FOCUS": m = self.movie_focus
        elif state == "BREAK": m = self.movie_break
        elif state == "ALERT": m = self.movie_alert
        
        # 通过动态属性切换 CSS 状态，避免 inline style 覆盖 hover
        self.content_layer.setProperty("state", state)
        self.content_layer.style().unpolish(self.content_layer)
        self.content_layer.style().polish(self.content_layer)
        
        if m and m.isValid(): self.avatar_bg.setMovie(m); m.start()
        else: self.avatar_bg.clear()

    def open_set(self): 
        if SettingsDialog(self).exec(): 
            if self.monitor: self.monitor.ai.reload_client()
            self.task_lbl.setText("✅ 已更新"); QTimer.singleShot(1000, lambda: self.task_lbl.setText(self.task_queue[self.current_index]['step'] if self.task_queue else "准备就绪"))

    def plan(self):
        g = self.inp.toPlainText().strip(); 
        if not g: return
        if not CONFIG.get("api_key") and not MOCK_MODE: QMessageBox.warning(self,"提示","请先点击⚙️设置API Key"); self.open_set(); return
        
        # 进入 AI 规划状态
        self.idle_ui.hide()
        self.ai_loading_ui.show()
        self.ai_pulse.start()
        
        self.main_goal = g # 记录总目标
        self.th = PlannerThread(g); self.th.result_signal.connect(self.on_plan); self.th.start()

    def on_plan(self, tasks):
        # 停止 AI 动画
        self.ai_pulse.stop()
        self.ai_loading_ui.hide()
        
        # 恢复状态
        self.mag.setEnabled(True)
        self.mag.setText("🚀")
        self.inp.setReadOnly(False)
        self.mag.setGraphicsEffect(None) # 清除可能的残余效果
        
        if not tasks: 
            self.task_lbl.setText("AI 响应失败")
            return
            
        dlg = PlanDialog(tasks, self)
        if dlg.exec(): 
            self.inp.clear() # 只有确认开始后才清空输入框
            import uuid
            self.task_queue = []
            for t in dlg.tasks:
                if 'id' not in t: t['id'] = str(uuid.uuid4())
                self.task_queue.append(t)
            self.current_index = -1; self.load_next()
        else:
            # 如果取消，确保回到输入界面
            self.idle_ui.show()

    def load_next(self):
        # 移除 self.hide()，确保任务切换时界面不消失
        # 启用任务列表菜单
        self.action_task_list.setEnabled(True)
        self.action_task_pause.setEnabled(True) 
        self.action_sup_pause.setEnabled(True)
        self.action_abandon.setEnabled(True) # 启用放弃
        self.tray_icon.setIcon(QIcon("assets/tray_active.png")) # 切换活跃图标
        self.current_index += 1
        if self.current_index >= len(self.task_queue): self.reset(); self.task_lbl.setText("🎉 完成!"); self.open_rep(); return
        
        self.task_paused = False
        self.btn_ps.setText("⏸️ 暂停")
        self.action_task_pause.setChecked(False)
        self.action_sup_pause.setChecked(False)
        
        # 提醒开始新任务 (如果不是第一步，或者用户希望每次都响)
        self.start_sound.play()
        
        t = self.task_queue[self.current_index]
        self.state = "FOCUS"; self.duration = t['duration'] * 60; self.current_session_id = self.db.start_session(t['step'], t['duration'])
        
        self.toggle_ui(False); 
        self.step_lbl.setText(f"Step {self.current_index+1}/{len(self.task_queue)}")
        self.task_lbl.setText(t['step'])
        self.update_tm()
        self.set_state("FOCUS")
        
        if self.monitor: self.monitor.stop()
        self.monitor = MonitorThread(self.main_goal, t['step'])
        self.monitor.update_signal.connect(self.on_mon); self.monitor.start(); self.timer.start(1000)

    def start_break(self):
        if self.current_session_id: self.db.end_session(self.current_session_id, "COMPLETED"); self.current_session_id = None
        
        # 播放成功音效
        self.success_sound.play()
        
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
        self.task_paused = False
        self.supervision_paused = False
        self.btn_ps.setText("⏸️ 暂停")
        # 禁用任务相关菜单
        self.action_task_list.setEnabled(False)
        self.action_task_pause.setEnabled(False); self.action_task_pause.setChecked(False); self.action_task_pause.setText("⏸️ 暂停任务")
        self.action_sup_pause.setEnabled(False); self.action_sup_pause.setChecked(False); self.action_sup_pause.setText("💤 暂停监督")
        self.action_abandon.setEnabled(False) # 禁用放弃
        self.tray_icon.setIcon(QIcon("assets/tray_idle.png")) # 恢复就绪图标
        self.tray_icon.setToolTip("FlowMate - Ready")
        if self.monitor: self.monitor.stop()
        self.timer.stop(); self.toggle_ui(True); self.set_state("FOCUS")
        self.progress_bar.setValue(0); self.progress_bar.hide()
        # 清空滑动窗口记录
        self.distraction_history = []

    def open_rep(self): ReportDialog(self.db, self).exec()
    def tick(self):
        if self.task_paused: return # 任务暂停中 (不扣时间)
        if self.duration > 0: 
            self.duration -= 1; self.update_tm()
            # 更新托盘 Tooltip
            m, s = divmod(self.duration, 60)
            status_icon = "🔥" if self.state == "FOCUS" else "☕"
            task_name = self.task_queue[self.current_index]['step'] if self.task_queue else "No Task"
            self.tray_icon.setToolTip(f"{status_icon} {m:02d}:{s:02d} - {task_name}")
            
            # 更新进度条 (全局进度)
            if self.task_queue:
                total_steps = len(self.task_queue)
                current_step_base = self.current_index / total_steps * 1000
                
                # 计算当前步骤内的进度 (如果是 FOCUS 状态)
                step_progress = 0
                if self.state == "FOCUS":
                    total_sec = self.task_queue[self.current_index]['duration'] * 60
                    if total_sec > 0:
                        step_progress = (1 - self.duration / total_sec) * (1000 / total_steps)
                
                self.progress_bar.setValue(int(current_step_base + step_progress))
        else: 
            # 时间到，自动呼出并激活窗口
            self.show_window()
            self.tray_icon.showMessage(
                "FlowMate", "⏰ 时间到！", 
                QSystemTrayIcon.MessageIcon.Information, 3000
            )
            self.next()
    def update_tm(self): m, s = divmod(self.duration, 60); self.time_lbl.setText(f"{m:02d}:{s:02d}")
    
    def paintEvent(self, event):
        # 核心绘制逻辑：确保底部有一层干净的圆角底色，解决带背景时的直角/透明度异常
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        # 获取当前状态对应的背景色 (同步 CSS)
        bg = QColor("#14141E")
        if self.state == "BREAK": bg = QColor("#14321E")
        elif self.state == "ALERT": bg = QColor("#3C1414")
        
        painter.setBrush(bg)
        painter.drawRoundedRect(self.rect(), 15, 15)

    def toggle_ui(self, show_input):
        if show_input: 
            self.idle_ui.show()
            self.active_ui.hide()
            self.ai_loading_ui.hide()
            self.btn_list.hide()
            self.step_lbl.setText("FlowMate Pet") # 初始显示 Pet
        else: 
            self.idle_ui.hide()
            self.active_ui.show()
            self.btn_list.show()
            if self.state == "BREAK": self.btn_ab.hide(); self.btn_ok.setText("⏩ 结束休息")
            else: self.btn_ab.show(); self.btn_ok.setText("✅ 完成")

    def on_mon(self, p, t, d, r):
        if self.state != "FOCUS": return
        now = time.time()
        
        if d:
            # 记录分散事件到滑动窗口
            self.distraction_history.append((now, r))
            # 清理1分钟之前的历史记录
            self.distraction_history = [(ts, reason) for ts, reason in self.distraction_history if now - ts <= 60]
            
            # 计算最近1分钟内的分散次数
            recent_count = len(self.distraction_history)
            is_critical = recent_count > 3  # 1分钟内超过3次为严重 (即第4次开始变红)
            
            # 极简提醒逻辑：不改变主界面，只显示弹幕toast
            if self.show_toast:
                # 只有当没有正在显示的弹幕，或者当前是紧急情况而之前不是时，才触发新弹幕
                if not self.toast.isVisible() or (is_critical and not getattr(self, '_last_was_critical', False)):
                    display_reason = r[:30] + "..." if len(r) > 30 else r
                    message = f"⚠️ {display_reason}" if display_reason else "⚠️ 注意力分散"
                    self.toast.show_message(message, is_critical=is_critical)
                    self._last_was_critical = is_critical
            
            # 播放提示音 (每5秒最多一次)
            if now - self.last_audio_time > 5:
                self.alert_sound.play()
                self.last_audio_time = now

            if self.current_session_id and int(now)%5==0: 
                self.db.log_distraction(self.current_session_id, p, r)
        else:
            # 专注回去后不强制隐藏，让弹幕自然完成动画
            # self.toast.hide() # 移除强制隐藏，让弹幕自然飞出
            if self.avatar_bg.movie() != self.movie_focus: self.set_state("FOCUS")
            self.task_lbl.setText(self.task_queue[self.current_index]['step'])

    def mousePressEvent(self, e): 
        if e.button() == Qt.MouseButton.LeftButton: self.drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft(); e.accept()
    def mouseMoveEvent(self, e): 
        if e.buttons() == Qt.MouseButton.LeftButton and self.drag_pos: self.move(e.globalPosition().toPoint() - self.drag_pos); e.accept()
    def resizeEvent(self, e): self.avatar_bg.setGeometry(0,0,self.width(),self.height()); self.content_layer.setGeometry(0,0,self.width(),self.height()); super().resizeEvent(e)