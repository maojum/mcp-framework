"""
主窗口模块 - MCP GUI的核心窗口

此模块实现了应用程序的主窗口，整合了所有GUI组件，
包括聊天面板、工具面板、模型选择和配置等功能。
"""

import logging
import json
import os
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QSplitter, QAction, QMenuBar, QStatusBar)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QIcon

from .chat_panel import ChatPanel
from .tool_panel import ToolPanel
from .model_selector import ModelSelector
from .model_config_panel import ModelConfigPanel
from .server_manager import ServerManager

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    """MCP应用的主窗口，整合所有GUI组件"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MCP Assistant")
        self.resize(1200, 800)
        
        # 加载配置
        self.load_config()
        
        # 初始化UI
        self.init_ui()
        self.setup_menu()
        self.setup_status_bar()
        
        logger.info("GUI主窗口已初始化")
    
    def load_config(self):
        """加载应用配置"""
        try:
            config_path = "servers_config.json"
            with open(config_path, 'r') as f:
                self.config = json.load(f)
            logger.info(f"成功加载配置: {config_path}")
        except Exception as e:
            logger.error(f"加载配置失败: {str(e)}")
            self.config = {"mcpServers": {}}
    
    def init_ui(self):
        """初始化用户界面组件"""
        # 创建中央小部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QHBoxLayout(central_widget)
        
        # 创建分割器
        self.splitter = QSplitter(Qt.Horizontal)
        
        # 左侧面板 - 工具和服务器管理
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # 服务器管理器
        self.server_manager = ServerManager(self.config)
        
        # 工具面板
        self.tool_panel = ToolPanel(self.server_manager)
        
        left_layout.addWidget(self.server_manager)
        left_layout.addWidget(self.tool_panel)
        
        # 右侧面板 - 聊天和模型配置
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # 模型选择器
        self.model_selector = ModelSelector()
        
        # 模型配置面板
        self.model_config = ModelConfigPanel(self.model_selector)
        
        # 聊天面板
        self.chat_panel = ChatPanel(self.server_manager, self.model_selector)
        
        # 添加到右侧布局
        model_widget = QWidget()
        model_layout = QHBoxLayout(model_widget)
        model_layout.addWidget(self.model_selector)
        model_layout.addWidget(self.model_config)
        
        right_layout.addWidget(model_widget, 1)  # 占比较小
        right_layout.addWidget(self.chat_panel, 5)  # 占比较大
        
        # 添加到分割器
        self.splitter.addWidget(left_panel)
        self.splitter.addWidget(right_panel)
        self.splitter.setSizes([300, 900])  # 设置初始大小比例
        
        main_layout.addWidget(self.splitter)
    
    def setup_menu(self):
        """设置菜单栏"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu("文件")
        
        # 添加退出操作
        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 设置菜单
        settings_menu = menubar.addMenu("设置")
        model_config_action = QAction("编辑模型配置", self)
        model_config_action.triggered.connect(self.model_config.show_models_config_dialog)
        settings_menu.addAction(model_config_action)
    
    def setup_status_bar(self):
        """设置状态栏"""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("就绪")
    
    def closeEvent(self, event):
        """窗口关闭事件处理"""
        # 确保服务器正确关闭
        self.server_manager.close_all_servers()
        event.accept()