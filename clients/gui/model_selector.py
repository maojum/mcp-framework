"""
模型选择器模块 - 用于选择和管理大语言模型

此模块实现了模型的选择界面，支持不同类型的LLM，
并提供模型切换的功能。
"""

import logging
import os
import json
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QComboBox, 
                           QPushButton, QGroupBox, QFormLayout)
from PyQt5.QtCore import pyqtSignal, Qt

from .utils import create_llm_client

logger = logging.getLogger(__name__)

class ModelSelector(QWidget):
    """模型选择和管理界面"""
    
    model_changed = pyqtSignal(str)  # 模型变更信号
    
    def __init__(self):
        super().__init__()
        
        # 加载API密钥
        self.api_key = os.getenv("LLM_API_KEY")
        
        # 加载模型配置
        self.load_models_config()
        
        self.init_ui()
    
    def load_models_config(self):
        """从配置文件加载模型配置"""

        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models_config.json")
        
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                self.models_config = json.load(f)
            
            self.models = {}
            for model_id, model_info in self.models_config["models"].items():
                self.models[model_id] = model_info["display_name"]
            
            self.current_model = self.models_config.get("default_model", next(iter(self.models)))
            
            logger.info(f"成功加载模型配置: {len(self.models)} 个模型")
        else:
            logger.error(f"模型配置文件不存在: {config_path}")

    def init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)
        
        # 创建模型选择组
        model_group = QGroupBox("模型选择")
        model_layout = QFormLayout()
        
        # 模型下拉选择框
        self.model_combo = QComboBox()
        for model_id, model_name in self.models.items():
            model_info = self.models_config["models"][model_id]
            tooltip = model_info.get("description", "")
            self.model_combo.addItem(model_name, model_id)
            
            # 设置工具提示
            index = self.model_combo.count() - 1
            self.model_combo.setItemData(index, tooltip, Qt.ToolTipRole)
        
        # 设置默认选中项
        try:
            default_index = list(self.models.keys()).index(self.current_model)
            self.model_combo.setCurrentIndex(default_index)
        except (ValueError, IndexError):
            if self.model_combo.count() > 0:
                self.model_combo.setCurrentIndex(0)
                self.current_model = self.model_combo.itemData(0)
        
        # 连接信号
        self.model_combo.currentIndexChanged.connect(self.on_model_changed)
        
        # 添加到布局
        model_layout.addRow("选择模型:", self.model_combo)
        model_group.setLayout(model_layout)
        
        # API密钥状态
        key_status = "已配置" if self.api_key else "未配置"
        self.key_label = QLabel(f"API密钥: {key_status}")
        
        # 添加到主布局
        layout.addWidget(model_group)
        layout.addWidget(self.key_label)
        layout.addStretch()
    
    def on_model_changed(self, index):
        """处理模型变更"""
        model_id = self.model_combo.itemData(index)
        self.current_model = model_id
        logger.info(f"模型已更改为: {model_id}")
        self.model_changed.emit(model_id)
    
    def get_current_model(self):
        """获取当前选择的模型ID"""
        return self.current_model
    
    def get_current_model_info(self):
        """获取当前模型的详细信息"""
        if self.current_model in self.models_config["models"]:
            return self.models_config["models"][self.current_model]
        return None
    
    def get_provider_info(self, provider_id):
        """获取提供商信息"""
        if "providers" in self.models_config and provider_id in self.models_config["providers"]:
            return self.models_config["providers"][provider_id]
        return None
    
    def get_current_llm_client(self):
        """获取当前模型的LLM客户端"""
        if not self.api_key:
            logger.error("缺少API密钥，无法创建LLM客户端")
            return None
        
        model_info = self.get_current_model_info()
        if not model_info:
            logger.error(f"未找到模型信息: {self.current_model}")
            return None
            
        provider_id = model_info.get("provider")
        provider_info = self.get_provider_info(provider_id)
        
        return create_llm_client(
            api_key=self.api_key,
            model_id=self.current_model,
            model_info=model_info,
            provider_info=provider_info
        )