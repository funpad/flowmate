import sys
import random
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QHBoxLayout, QFrame, QScrollArea, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QTextBrowser, 
                             QFormLayout, QComboBox, QCheckBox, QSpinBox,
                             QWidget, QListWidget, QListWidgetItem, QAbstractItemView, QGridLayout, QApplication)
from PyQt6.QtCore import Qt, QSize, QTimer, QPropertyAnimation, QParallelAnimationGroup, QSequentialAnimationGroup, QEasingCurve, QPoint  # <--- 加上动画相关组件
from PyQt6.QtGui import QFont, QColor, QPainter
from core.config import CONFIG
from core.workers import ReportThread
from ui.styles import DIALOG_STYLE

class BaseDialog(QDialog):
    """支持拖拽的基础弹窗类"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.drag_pos = None

    def mousePressEvent(self, e):
        # 仅当点击背景（非子控件）时才触发拖拽逻辑
        if e.button() == Qt.MouseButton.LeftButton:
            # 这里的坐标判断要考虑到内边距
            child = self.childAt(e.position().toPoint())
            # 如果点击的是 QPushButton 或 QSpinBox 等交互控件，绝对不处理拖拽
            from PyQt6.QtWidgets import QPushButton, QSpinBox, QComboBox, QLineEdit
            if isinstance(child, (QPushButton, QSpinBox, QComboBox, QLineEdit)):
                return
            
            # 点击的是背景或普通文本，则允许拖动
            if not child or isinstance(child, (QLabel, QFrame, QWidget)):
                self.drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
                e.accept()

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.MouseButton.LeftButton and self.drag_pos:
            self.move(e.globalPosition().toPoint() - self.drag_pos)
            e.accept()

    def paintEvent(self, event):
        # 强制绘制圆角背景，防止 macOS/Windows 下出现直角边或全透明问题
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#1E1E2E")) # 使用固定的深色背景
        painter.drawRoundedRect(self.rect(), 15, 15)

    def center_on_parent(self):
        """确保窗口在父窗口中心显示，防止 macOS 负坐标导致窗口不可见"""
        if self.parent():
            p_geo = self.parent().geometry()
            s_geo = self.geometry()
            self.move(
                p_geo.center().x() - s_geo.width() // 2,
                max(30, p_geo.center().y() - s_geo.height() // 2) # 确保不被 macOS 菜单栏遮挡
            )
            self.raise_()
            self.activateWindow()

class SettingsDialog(BaseDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()
        self.load_settings()
        self.center_on_parent()

    def initUI(self):
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setFixedSize(400, 350)
        self.setStyleSheet(DIALOG_STYLE)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)

        header = QHBoxLayout()
        header.addWidget(QLabel("⚙️ 设置", styleSheet="font-size: 16px; font-weight: bold; border:none;"))
        header.addStretch()

        close = QPushButton("×")
        close.setObjectName("CloseBtn")
        close.setFixedSize(30, 30)
        close.clicked.connect(self.reject)
        header.addWidget(close)

        layout.addLayout(header)

        form = QFormLayout()
        form.setSpacing(15)

        self.api_input = QLineEdit()
        self.api_input.setPlaceholderText("sk-...")
        self.api_input.setEchoMode(QLineEdit.EchoMode.Password)

        self.model_input = QComboBox()
        self.model_input.addItems(["deepseek-chat", "gpt-3.5-turbo"])
        self.model_input.setEditable(True)

        self.strict_check = QCheckBox("开启魔鬼教官模式")
        self.strict_check.setStyleSheet("color: #DDD;")

        form.addRow("API Key:", self.api_input)
        form.addRow("模型:", self.model_input)
        form.addRow("", self.strict_check)

        layout.addLayout(form)
        layout.addStretch()

        h_layout = QHBoxLayout()
        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("CancelBtn")
        cancel_btn.clicked.connect(self.reject)
        
        save_btn = QPushButton("保存配置")
        save_btn.clicked.connect(self.save_settings)
        
        h_layout.addWidget(cancel_btn, 1)
        h_layout.addWidget(save_btn, 2)
        layout.addLayout(h_layout)
        self.setLayout(layout)

    def load_settings(self):
        self.api_input.setText(CONFIG.get("api_key", ""))
        self.model_input.setCurrentText(CONFIG.get("model", "deepseek-chat"))
        self.strict_check.setChecked(CONFIG.get("strict_mode", False))

    def save_settings(self):
        CONFIG.save_config("api_key", self.api_input.text().strip())
        CONFIG.save_config("model", self.model_input.currentText().strip())
        CONFIG.save_config("strict_mode", self.strict_check.isChecked())
        self.accept()

# ================= 任务规划弹窗 (支持拖拽排序) =================

class PlanDialog(BaseDialog):
    def __init__(self, tasks, parent=None, mode="PLANNING"):
        super().__init__(parent)
        self.tasks = tasks
        self.mode = mode  # PLANNING or MANAGING
        self.original_tasks = [t.copy() for t in tasks] # Deep copy for dirty check
        self.initUI()
        self.center_on_parent()

    def initUI(self):
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setFixedSize(460, 650)
        self.setStyleSheet(DIALOG_STYLE)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(12)

        # 1. 标题栏（标题 + 关闭按钮）
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        
        # 标题 - 跨平台兼容字体处理
        title_lbl = QLabel("✨ 任务规划")
        if sys.platform == "darwin":
            font_family = "SF Pro Display"
        elif sys.platform == "win32":
            font_family = "Microsoft YaHei UI"
        else:
            font_family = "Microsoft YaHei"
        title_lbl.setFont(QFont(font_family, 13, QFont.Weight.Bold))
        
        # 标题根据模式变化
        title_text = "✨ 任务规划" if self.mode == "PLANNING" else "📋 任务列表"
        title_lbl.setText(title_text)
        
        header.addWidget(title_lbl)
        header.addStretch()
        
        # 关闭按钮
        close_btn = QPushButton("×")
        close_btn.setObjectName("CloseBtn")
        close_btn.setFixedSize(30, 30)
        close_btn.clicked.connect(self.reject)
        header.addWidget(close_btn)
        
        main_layout.addLayout(header)

        # 2. 任务列表 (QListWidget)
        self.task_list = QListWidget()
        self.task_list.setStyleSheet("""
            QListWidget { background: transparent; border: none; outline: none; }
            QListWidget::item { background: transparent; padding: 10px 5px; }
            QListWidget::item:selected { background: transparent; }
        """)
        # 开启拖拽
        self.task_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.task_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.task_list.setDragEnabled(True)
        self.task_list.setAcceptDrops(True)
        self.task_list.setDropIndicatorShown(True)

        # 监听排序变化
        self.task_list.model().rowsMoved.connect(self.refresh_indices)

        main_layout.addWidget(self.task_list)

        # 3. 初始化加载任务
        for t in self.tasks:
            self.add_task_item(t)
            
        # 4. 新增按钮 (统一开启)
        add_btn = QPushButton("＋ 新增步骤")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setFixedHeight(45)
        # ... (样式保持不变) ...
        add_btn.setStyleSheet("""
            QPushButton { 
                background: rgba(255, 255, 255, 0.05); 
                border: 1px dashed #444; 
                color: #888; 
                border-radius: 8px;
                margin: 5px 0px;
                font-size: 13px;
                cursor: pointer;
            }
            QPushButton:hover { 
                background: rgba(255, 255, 255, 0.08); 
                color: #DDD; 
                border-color: #6C5CE7; 
            }
        """)
        add_btn.clicked.connect(lambda: self.add_task_item(None))
        main_layout.addWidget(add_btn)

        # 5. 底部操作栏
        btn_layout = QHBoxLayout()
        cancel_text = "取消" if self.mode == "PLANNING" else "关闭"
        cancel_btn = QPushButton(cancel_text)
        cancel_btn.setObjectName("CancelBtn")
        cancel_btn.setFixedSize(80, 40)
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(cancel_btn)

        if self.mode == "PLANNING":
            confirm_btn = QPushButton("🚀 确认并开始")
            confirm_btn.setFixedHeight(40)
            confirm_btn.clicked.connect(self.on_confirm)
            btn_layout.addWidget(confirm_btn, 1)
        else:
            # 管理模式下显示更新按钮 (初始禁用，有变动时启用)
            self.update_btn = QPushButton("💾 更新任务")
            self.update_btn.setFixedHeight(40)
            self.update_btn.clicked.connect(self.on_confirm) 
            self.update_btn.setEnabled(False)
            btn_layout.addWidget(self.update_btn, 1)

        main_layout.addLayout(btn_layout)

        self.setLayout(main_layout)

    def add_task_item(self, task_data=None):
        """添加一个任务项"""
        if not task_data:
            task_data = {"step": "", "duration": 25, "break": 5}

        # 1. 创建 item - 增加高度以提供更好的间距感
        item = QListWidgetItem()
        item.setSizeHint(QSize(400, 170))

        # 2. 创建 widget
        card_widget = TaskCardWidget(task_data, parent_list=self, item=item, mode=self.mode)

        # 3. 关联
        self.task_list.addItem(item)
        self.task_list.setItemWidget(item, card_widget)

        # 4. 刷新序号
        self.refresh_indices()

        # 5. 聚焦
        if not task_data.get('step'):
            card_widget.name_edit.setFocus()
            self.task_list.scrollToBottom()

    def refresh_indices(self):
        """重新计算序号"""
        # 使用 QTimer 延迟刷新，确保拖拽动作完成后再更新
        QTimer.singleShot(10, self._do_refresh_indices)

    def _do_refresh_indices(self):
        for i in range(self.task_list.count()):
            item = self.task_list.item(i)
            widget = self.task_list.itemWidget(item)
            if widget:
                widget.idx_lbl.setText(f"步骤 {i + 1}")
        # 拖拽排序也是一种变动
        self.check_dirty()

    def check_dirty(self):
        """检查是否有变动 (仅用于管理模式)"""
        if self.mode != "MANAGING": return
        
        is_dirty = False
        current_data = self.collect_data()
        
        # 简单比对长度和内容
        if len(current_data) != len(self.original_tasks):
            is_dirty = True
        else:
            for i, task in enumerate(current_data):
                org = self.original_tasks[i]
                if (task['step'] != org['step'] or 
                    task['duration'] != org['duration'] or 
                    task['break'] != org['break']):
                    is_dirty = True
                    break
        
        # 更新按钮状态
        self.update_btn.setEnabled(is_dirty)

    def collect_data(self):
        """收集当前列表数据"""
        new_tasks = []
        for i in range(self.task_list.count()):
            item = self.task_list.item(i)
            widget = self.task_list.itemWidget(item)
            if widget:
                step_name = widget.name_edit.text().strip()
                if not step_name: continue
                task_dict = {
                    "step": step_name,
                    "duration": widget.dur_spin.value(),
                    "break": widget.brk_spin.value()
                }
                if 'id' in widget.data:
                    task_dict['id'] = widget.data['id']
                new_tasks.append(task_dict)
        return new_tasks

    def on_confirm(self):
        """收集数据并关闭"""
        new_tasks = self.collect_data()

        if not new_tasks:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "提示", "请至少保留一个任务！")
            return

        self.tasks = new_tasks
        self.accept()

class TaskCardWidget(QFrame):
    """单个任务卡片组件"""
    def __init__(self, data, parent_list, item, mode="PLANNING"):
        super().__init__()
        self.data = data # 存储原始数据以获取 ID 等信息
        self.parent_list = parent_list
        self.my_item = item
        self.mode = mode
        self.setObjectName("TaskCard")

        self.setStyleSheet("""
            #TaskCard {
                background-color: #252535;
                border-radius: 12px;
                border: 1px solid #3A3A4A;
            }
            #TaskCard:hover {
                border: 1px solid #4A4A6A;
                background-color: #28283D;
            }
        """)

        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)

        # 顶部栏：编号 + 极简风格的叉号删除按钮 (透明背景)
        header = QHBoxLayout()
        header.setContentsMargins(0, 2, 0, 5)
        self.idx_lbl = QLabel("步骤 ?")
        # Windows兼容字体
        if sys.platform == "win32":
            font_family = "Microsoft YaHei UI"
        else:
            font_family = "SF Pro Display" if sys.platform == "darwin" else "Microsoft YaHei"
        self.idx_lbl.setFont(QFont(font_family, 11, QFont.Weight.Bold))
        self.idx_lbl.setStyleSheet("color: #666; border: none;")
        
        header.addWidget(self.idx_lbl)
        header.addStretch()
        
        # 统一开启叉号删除按钮 (透明背景)
        del_btn = QPushButton("×")
        del_btn.setFixedSize(30, 30)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.clicked.connect(self.remove_self)
        del_btn.setStyleSheet("""
            QPushButton { 
                background: transparent; 
                color: #666; 
                border: none; 
                font-family: Arial, sans-serif;
                font-size: 24px;
                font-weight: normal;
                padding: 0;
                margin: 0;
                cursor: pointer;
            }
            QPushButton:hover { 
                color: #FF5555; 
            }
        """)
        header.addWidget(del_btn)
        
        main_layout.addLayout(header)

        # 网格布局用于输入表单
        grid = QGridLayout()
        grid.setSpacing(15)  # 显著增加垂直间距，提升呼吸感
        grid.setColumnStretch(1, 1)

        # 任务描述
        self.name_edit = QLineEdit()
        self.name_edit.setText(data.get('step', ''))
        self.name_edit.setPlaceholderText("要做什么？")
        grid.addWidget(self.name_edit, 0, 0, 1, 2)

        # 时间设置
        time_hbox = QHBoxLayout()
        time_hbox.setSpacing(15)

        # 专注时间
        self.dur_spin = QSpinBox()
        self.dur_spin.setRange(1, 180)
        self.dur_spin.setValue(int(data.get('duration', 25)))
        self.dur_spin.setSuffix(" min 专注")
        self.dur_spin.setMinimumWidth(110)

        # 休息时间
        self.brk_spin = QSpinBox()
        self.brk_spin.setRange(1, 60)
        self.brk_spin.setValue(int(data.get('break', 5)))
        self.brk_spin.setSuffix(" min 休息")
        self.brk_spin.setMinimumWidth(110)

        time_hbox.addWidget(self.dur_spin)
        time_hbox.addWidget(self.brk_spin)
        time_hbox.addStretch()

        if self.mode == "MANAGING":
            self.name_edit.textChanged.connect(self.parent_list.check_dirty)
            self.dur_spin.valueChanged.connect(self.parent_list.check_dirty)
            self.brk_spin.valueChanged.connect(self.parent_list.check_dirty)

        grid.addLayout(time_hbox, 1, 0, 1, 2)
        main_layout.addLayout(grid)

    def remove_self(self):
        row = self.parent_list.task_list.row(self.my_item)
        self.parent_list.task_list.takeItem(row)
        self.parent_list.refresh_indices()
        self.parent_list.check_dirty()

# ================= 日报弹窗 =================

class ReportDialog(BaseDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.initUI()
        self.load_data()
        self.center_on_parent() # 初始化后强制居中显示
    def initUI(self):
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True) # 显式设置模态
        self.setFixedSize(500, 600)
        self.setStyleSheet(DIALOG_STYLE + """
            QTableWidget { background: #2A2A3A; color: #EEE; border: none; border-radius: 6px; }
            QHeaderView::section { background: #333; color: white; border: none; padding: 4px; }
            QTextBrowser { background: #2A2A3A; color: #EEE; border: none; border-radius: 6px; padding: 10px; }
        """)
        layout = QVBoxLayout(); layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(12)

        header = QHBoxLayout()
        font_family = ".AppleSystemUIFont" if sys.platform == "darwin" else "Microsoft YaHei"
        header.addWidget(QLabel("📊 今日复盘", font=QFont(font_family, 14, QFont.Weight.Bold))); header.addStretch()
        layout.addLayout(header)
        
        layout.addWidget(QLabel("📝 任务记录:"))
        self.table = QTableWidget(); self.table.setColumnCount(4); self.table.setHorizontalHeaderLabels(["任务", "时长", "状态", "分心"]); self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch); self.table.verticalHeader().setVisible(False); self.table.setFixedHeight(180)
        layout.addWidget(self.table)
        
        layout.addWidget(QLabel("🤖 AI 点评:"))
        self.box = QTextBrowser(); self.box.setHtml("<div style='color:#888;'>等待生成...</div>")
        layout.addWidget(self.box)
        
        # 底部操作区
        footer = QHBoxLayout()
        exit_btn = QPushButton("我知道了")
        exit_btn.setObjectName("CancelBtn")
        exit_btn.clicked.connect(lambda: self.done(0))
        
        self.btn = QPushButton("🔍 生成 AI 分析")
        self.btn.clicked.connect(self.run_ai)
        
        footer.addWidget(exit_btn, 1)
        footer.addWidget(self.btn, 2)
        layout.addLayout(footer)

        self.setLayout(layout)

    def load_data(self):
        tasks, _ = self.db.get_today_stats()
        self.table.setRowCount(len(tasks))
        for i, (n, d, s, dc) in enumerate(tasks):
            self.table.setItem(i, 0, QTableWidgetItem(str(n))); self.table.setItem(i, 1, QTableWidgetItem(str(d))); self.table.setItem(i, 2, QTableWidgetItem(str(s)))
            item = QTableWidgetItem(str(dc)); item.setForeground(QColor("#FF5555") if dc > 0 else QColor("#4CAF50"))
            self.table.setItem(i, 3, item)
    def run_ai(self):
        self.btn.setDisabled(True); self.btn.setText("分析中..."); self.th = ReportThread(self.db); self.th.result_signal.connect(self.show); self.th.start()
    def show(self, txt):
        self.btn.setDisabled(False); self.btn.setText("重新生成"); self.box.setHtml(f"<div style='line-height:1.6; font-size:13px;'>{txt.replace(chr(10), '<br>')}</div>")

# ================= 极简提醒弹窗 =================

class Toast(QWidget):
    def __init__(self):
        super().__init__()
        # 强力置顶 Flags，但不抢夺焦点
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool |
            Qt.WindowType.X11BypassWindowManagerHint
            # 注意：不设置 WindowDoesNotAcceptFocus，因为可能导致窗口不显示
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating) # 不抢夺焦点
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # 不接受焦点
        
        self.is_animating = False  # 动画状态标志
        self.current_anim = None  # 当前运行的动画组
        self.shake_anim = None  # 抖动动画引用，用于清理
        
        self.initUI()
    
    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.lbl = QLabel("")
        self.lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl)
        self.set_severity(False) # 默认黄色
        
        # 初始化定时器用于自动隐藏
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._start_fade_out)
        
    def set_severity(self, is_critical):
        """设置提醒等级：黄色(警告) vs 红色(严重)"""
        if is_critical:
            # 红色高危：1分钟内频繁分散
            bg_color = "rgba(40, 0, 0, 0.95)"
            accent_color = "#FF5555"
        else:
            # 黄色常规：偶发性分散
            bg_color = "rgba(40, 40, 0, 0.95)"
            accent_color = "#FFCC00"
            
        self.lbl.setStyleSheet(f"""
            background-color: {bg_color};
            color: {accent_color};
            font-size: 16px;
            font-weight: bold;
            border-radius: 15px;
            padding: 12px 24px;
            border: 2px solid {accent_color};
        """)

    def show_message(self, text, is_critical=False):
        """显示弹幕消息：采用更稳健的动画生命周期管理，解决红色弹幕可能停滞的问题"""
        # 如果当前正在显示动画，且新的请求不是紧急的，则跳过，避免动画冲突
        if self.is_animating and not is_critical:
            return
            
        # 如果正在运行动画，先强制停止并清理
        if self.current_anim:
            self.current_anim.stop()
            self.current_anim.deleteLater()
            self.current_anim = None
            
        self.is_animating = True
        self.set_severity(is_critical)
        self.lbl.setText(f"{text}")
        self.adjustSize()
        
        # 获取位置
        screen = QApplication.primaryScreen().geometry()
        sw, sh = screen.width(), screen.height()
        y_pos = sh // 4 + random.randint(-15, 15)
        tw = self.width() if self.width() > 0 else 200
        cx = (sw - tw) // 2
        
        # 1. 创建总控顺序动画组
        main_seq = QSequentialAnimationGroup(self)
        
        # 2. 飞入阶段 (并行：位置 + 透明度)
        fly_in = QParallelAnimationGroup(main_seq)
        
        pos_in = QPropertyAnimation(self, b"pos", fly_in)
        pos_in.setDuration(500)
        pos_in.setStartValue(QPoint(sw, y_pos))
        pos_in.setEndValue(QPoint(cx, y_pos))
        pos_in.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        fade_in = QPropertyAnimation(self, b"windowOpacity", fly_in)
        fade_in.setDuration(500)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        
        fly_in.addAnimation(pos_in)
        fly_in.addAnimation(fade_in)
        main_seq.addAnimation(fly_in)
        
        # 3. 严重警告时的抖动阶段
        if is_critical:
            shake = QPropertyAnimation(self, b"pos", main_seq)
            shake.setDuration(400)
            shake.setStartValue(QPoint(cx, y_pos))
            # 关键帧实现剧烈抖动
            shake.setKeyValueAt(0.2, QPoint(cx - 12, y_pos))
            shake.setKeyValueAt(0.4, QPoint(cx + 12, y_pos))
            shake.setKeyValueAt(0.6, QPoint(cx - 12, y_pos))
            shake.setKeyValueAt(0.8, QPoint(cx + 12, y_pos))
            shake.setEndValue(QPoint(cx, y_pos))
            main_seq.addAnimation(shake)
            
        # 4. 停留阶段 (使用透明度动画作为稳定的延时，比addPause更可靠)
        stay = QPropertyAnimation(self, b"windowOpacity", main_seq)
        stay.setDuration(2500 if is_critical else 2000)
        stay.setStartValue(1.0)
        stay.setEndValue(1.0)
        main_seq.addAnimation(stay)
        
        # 5. 飞出阶段 (并行：位置 + 透明度)
        fly_out = QParallelAnimationGroup(main_seq)
        
        pos_out = QPropertyAnimation(self, b"pos", fly_out)
        pos_out.setDuration(500)
        pos_out.setStartValue(QPoint(cx, y_pos))
        pos_out.setEndValue(QPoint(-tw - 50, y_pos)) # 多飞出一段距离
        pos_out.setEasingCurve(QEasingCurve.Type.InCubic)
        
        fade_out = QPropertyAnimation(self, b"windowOpacity", fly_out)
        fade_out.setDuration(500)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        
        fly_out.addAnimation(pos_out)
        fly_out.addAnimation(fade_out)
        main_seq.addAnimation(fly_out)
        
        # 监听结束
        main_seq.finished.connect(self._on_animation_finished)
        
        # 准备并启动
        self.move(sw, y_pos)
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        
        self.current_anim = main_seq
        main_seq.start()

    def _start_fade_out(self): pass
        
    def _on_animation_finished(self):
        """动画真正物理结束"""
        self.is_animating = False
        self.current_anim = None
        self.hide()
        self.setWindowOpacity(1.0)
        
    def _cleanup_shake(self): pass