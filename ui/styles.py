DIALOG_STYLE = """
    /* 基础弹窗样式 */
    QDialog { 
        background-color: #1E1E2E; 
        border: none; 
        border-radius: 15px; 
    }
    
    /* 统一字体栈 - Windows兼容优化 */
    QLabel, QLineEdit, QTextEdit, QSpinBox, QComboBox, QPushButton { 
        font-family: "Microsoft YaHei UI", "Microsoft YaHei", ".AppleSystemUIFont", "SF Pro Display", "Helvetica Neue", sans-serif;
        color: #DDD;
        outline: none;
    }
    
    QLabel { border: none; background: transparent; }
    
    /* 输入框样式修正 - 增加高度和更清晰的边框 */
    QLineEdit { 
        background: #252535; 
        color: white; 
        border: 1px solid #444; 
        padding: 6px 10px; 
        border-radius: 4px; 
        min-height: 28px;
        selection-background-color: #6C5CE7;
    }
    QLineEdit:focus {
        border: 1px solid #6C5CE7;
    }
    
    QTextEdit#BigInput {
        background: #252535;
        border: 1px solid #444;
        border-radius: 15px;
        font-size: 15px;
        padding: 12px;
        line-height: 1.5;
    }
    QTextEdit#BigInput:focus {
        border-color: #6C5CE7;
        background: #28283D;
    }
    
    /* 数字输入框 (SpinBox) - 采用更简洁的一体化设计 */
    QSpinBox { 
        background: #252535; 
        color: white; 
        border: 1px solid #444; 
        padding: 4px 8px; 
        border-radius: 4px;
        min-height: 30px;
    }
    QSpinBox:focus {
        border: 1px solid #6C5CE7;
    }
    QSpinBox::up-button, QSpinBox::down-button {
        background: transparent;
        width: 18px;
        border: none;
    }
    QSpinBox::up-arrow {
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-bottom: 5px solid #888;
        width: 0; height: 0;
    }
    QSpinBox::down-arrow {
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid #888;
        width: 0; height: 0;
    }
    QSpinBox::up-arrow:hover { border-bottom-color: #AAA; }
    QSpinBox::down-arrow:hover { border-top-color: #AAA; }

    /* 下拉框 (ComboBox) - 保持与 SpinBox 一致的简洁感 */
    QComboBox { 
        background: #252535; 
        color: white; 
        border: 1px solid #444; 
        padding: 4px 10px; 
        border-radius: 4px;
        min-height: 30px;
    }
    QComboBox:focus { border: 1px solid #6C5CE7; }
    QComboBox::drop-down {
        border: none;
        width: 24px;
    }
    QComboBox::down-arrow {
        image: none;
        border-left: 5px solid transparent;
        border-right: 5px solid transparent;
        border-top: 5px solid #888;
        width: 0; height: 0;
    }
    QComboBox QAbstractItemView {
        background: #252535;
        color: white;
        border: 1px solid #444;
        selection-background-color: #6C5CE7;
        outline: none;
    }

    /* 按钮样式系统 */
    QPushButton { 
        background: #6C5CE7; 
        color: white; 
        border-radius: 8px; 
        padding: 8px 16px; 
        font-weight: 600;
        font-size: 13px;
        border: none;
        outline: none;
    }
    QPushButton:hover { background: #7D6DF2; }
    QPushButton:pressed { background: #4A3BA3; }
    QPushButton:disabled { background: #333344; color: #666; border: 1px solid #444; }

    /* 成功色 (完成/开始) */
    QPushButton#SuccessBtn { background: #00B894; }
    QPushButton#SuccessBtn:hover { background: #00D1AA; }

    /* 危险色 (放弃/删除) */
    QPushButton#DangerBtn { background: #D63031; }
    QPushButton#DangerBtn:hover { background: #FF4757; }

    /* 警告色 (暂停) */
    QPushButton#WarningBtn { background: #F1C40F; color: #2D3436; }
    QPushButton#WarningBtn:hover { background: #F9D84A; }

    /* 次级/取消色 */
    QPushButton#CancelBtn { background: #636E72; }
    QPushButton#CancelBtn:hover { background: #7A868B; color: white; }

    /* 顶部图标按钮 */
    QPushButton#IconBtn { background: transparent; color: #888; font-size: 16px; padding: 0; border: none; }
    QPushButton#IconBtn:hover { color: #FFF; background: rgba(255,255,255,0.2); }
    
    QPushButton#CloseBtn { background: transparent; color: #888; font-size: 18px; font-weight: bold; padding: 0; border: none; }
    QPushButton#CloseBtn:hover { background: #FF3B30; color: white; }
    
    /* 火箭启动按钮专用 */
    QPushButton#RocketBtn {
        background: #6C5CE7;
        color: white;
        border-radius: 22px;
        font-size: 20px;
        padding: 0;
        border: none;
    }
    QPushButton#RocketBtn:hover {
        background: #7D6DF2;
    }
    QPushButton#RocketBtn:pressed {
        background: #4A3BA3;
    }

    QProgressBar {
        background: rgba(255, 255, 255, 0.05);
        border: none;
        border-radius: 4px;
        height: 6px;
        text-align: center;
    }
    QProgressBar::chunk {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6C5CE7, stop:1 #A29BFE);
        border-radius: 4px;
    }
    
    QScrollArea { border: none; background: transparent; }
    QListWidget { background: transparent; border: none; outline: none; }
    QTableWidget { background: #2A2A3A; color: #EEE; border: none; border-radius: 6px; gridline-color: #444; }
    QHeaderView::section { background: #333; color: white; border: none; padding: 4px; }
    QTextBrowser { background: #2A2A3A; color: #EEE; border: none; border-radius: 6px; padding: 10px; }
    
    /* 主界面容器样式 */
    #ContentLayer {
        background: rgba(20, 20, 30, 0.9);
        border-radius: 15px;
    }
    #ContentLayer[state="BREAK"] {
        background: rgba(20, 50, 30, 0.9);
    }
    #ContentLayer[state="ALERT"] {
        background: rgba(60, 20, 20, 0.9);
    }
"""

MAIN_WINDOW_STYLE = "background: rgba(20, 20, 30, 0.85); border-radius: 15px; border: none;"
BREAK_STYLE = "background: rgba(20, 50, 30, 0.85); border-radius: 15px; border: none;"
ALERT_STYLE = "background: rgba(60, 20, 20, 0.85); border-radius: 15px; border: none;"