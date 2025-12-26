DIALOG_STYLE = """
    /* 基础弹窗样式 */
    QDialog { 
        background-color: #1E1E2E; 
        border: 1px solid #444; 
        border-radius: 12px; 
    }
    
    /* 统一字体栈 - Windows兼容优化 */
    QLabel, QLineEdit, QSpinBox, QComboBox, QPushButton { 
        font-family: "Microsoft YaHei UI", "Microsoft YaHei", ".AppleSystemUIFont", "SF Pro Display", "Helvetica Neue", sans-serif;
        color: #DDD; 
    }
    
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

    /* 按钮样式 - 优化视觉效果 */
    QPushButton { 
        background: #6C5CE7; 
        color: white; 
        border-radius: 10px; 
        padding: 10px 18px; 
        font-weight: 600;
        font-size: 13px;
        border: none;
    }
    QPushButton:hover { 
        background: #5B4CC4; 
    }
    QPushButton:pressed {
        background: #4A3BA3;
    }
    QPushButton#CancelBtn { 
        background: rgba(51, 51, 51, 0.8); 
        color: #BBB; 
        border: 1px solid rgba(85, 85, 85, 0.6); 
    }
    QPushButton#CancelBtn:hover {
        background: rgba(60, 60, 60, 0.9);
        color: #DDD;
    }
    QPushButton#CloseBtn { 
        background: transparent; 
        color: #888; 
        font-size: 18px; 
        border: none; 
    }
    QPushButton#CloseBtn:hover { 
        color: white; 
        background: rgba(255, 255, 255, 0.1);
    }
    
    QScrollArea { border: none; background: transparent; }
"""

MAIN_WINDOW_STYLE = "background: rgba(20, 20, 30, 0.85); border-radius: 15px; border: 1px solid #444;"
BREAK_STYLE = "background: rgba(20, 50, 30, 0.85); border-radius: 15px; border: 1px solid #4CAF50;"
ALERT_STYLE = "background: rgba(60, 20, 20, 0.85); border-radius: 15px; border: 2px solid #FF5555;"