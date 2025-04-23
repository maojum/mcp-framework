"""
模型配置面板模块 - 用于配置大语言模型参数

此模块实现了模型参数的配置界面，包括温度、top_p、
最大token数等参数的设置。
"""

import logging
import json
import os
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QSlider, 
                           QSpinBox, QDoubleSpinBox, QFormLayout, 
                           QPushButton, QDialog, QLineEdit, QMessageBox,
                           QGroupBox, QTabWidget, QTextEdit, QDialogButtonBox)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont 
logger = logging.getLogger(__name__)

class ModelConfigPanel(QWidget):
    """模型配置面板，用于调整LLM参数"""
    
    config_changed = pyqtSignal(dict)  # 配置变更信号
    
    def __init__(self, model_selector=None):
        super().__init__()
        
        # 存储模型选择器实例
        self.model_selector = model_selector
        
        # 加载模型配置文件
        self.load_models_config()
        
        self.init_ui()
        
        # 连接模型选择器的信号（如果提供）
        if self.model_selector:
            self.model_selector.model_changed.connect(self.on_model_changed)
    
    def init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)
        
        # 创建参数配置组
        self.param_group = QGroupBox("模型参数")
        form_layout = QFormLayout()
        
        # 温度滑块
        self.temp_slider = QDoubleSpinBox()
        self.temp_slider.setRange(0.0, 2.0)
        self.temp_slider.setSingleStep(0.1)
        self.temp_slider.valueChanged.connect(self.on_config_changed)
        form_layout.addRow("温度:", self.temp_slider)
        
        # Top-p滑块
        self.top_p_slider = QDoubleSpinBox()
        self.top_p_slider.setRange(0.0, 1.0)
        self.top_p_slider.setSingleStep(0.05)
        self.top_p_slider.valueChanged.connect(self.on_config_changed)
        form_layout.addRow("Top-p:", self.top_p_slider)
        
        # 最大Token数
        self.max_tokens = QSpinBox()
        self.max_tokens.setRange(50, 8000)
        self.max_tokens.setSingleStep(50)
        self.max_tokens.valueChanged.connect(self.on_config_changed)
        form_layout.addRow("最大Token:", self.max_tokens)
        
        self.param_group.setLayout(form_layout)
        
        # 添加到主布局
        layout.addWidget(self.param_group)
        layout.addStretch()
        
        # 加载当前模型参数
        self.refresh_controls()
    
    def refresh_controls(self):
        """刷新控件以显示当前选中模型的参数"""
        if not self.model_selector:
            return
            
        # 获取当前模型ID和信息
        model_id = self.model_selector.get_current_model()
        if not model_id or model_id not in self.models_config["models"]:
            logger.warning(f"未找到模型配置: {model_id}")
            return
            
        model_info = self.models_config["models"][model_id]
        
        # 获取默认参数
        if "default_parameters" in model_info:
            params = model_info["default_parameters"]
            
            # 更新GUI控件（阻断信号以避免循环触发）
            self.temp_slider.blockSignals(True)
            self.top_p_slider.blockSignals(True)
            self.max_tokens.blockSignals(True)
            
            self.temp_slider.setValue(params.get("temperature", 0.7))
            self.top_p_slider.setValue(params.get("top_p", 0.8))
            self.max_tokens.setValue(params.get("max_tokens", 2000))
            
            self.temp_slider.blockSignals(False)
            self.top_p_slider.blockSignals(False)
            self.max_tokens.blockSignals(False)
            
            # 更新组标题以显示当前模型
            self.param_group.setTitle(f"模型参数 ({model_info.get('display_name', model_id)})")
    
    def on_config_changed(self):
        """处理配置变更"""
        if not self.model_selector:
            return
            
        # 获取当前模型ID
        model_id = self.model_selector.get_current_model()
        if not model_id or model_id not in self.models_config["models"]:
            logger.warning(f"未找到模型配置: {model_id}")
            return
            
        # 获取GUI控件的值
        temperature = self.temp_slider.value()
        top_p = self.top_p_slider.value()
        max_tokens = self.max_tokens.value()
        
        # 更新模型配置
        if "default_parameters" not in self.models_config["models"][model_id]:
            self.models_config["models"][model_id]["default_parameters"] = {}
            
        self.models_config["models"][model_id]["default_parameters"]["temperature"] = temperature
        self.models_config["models"][model_id]["default_parameters"]["top_p"] = top_p
        self.models_config["models"][model_id]["default_parameters"]["max_tokens"] = max_tokens
        
        # 保存配置
        self.save_models_config()
        
        # 构建当前参数字典并发出信号
        current_params = {
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens
        }
        self.config_changed.emit(current_params)
        
        logger.info(f"已更新模型 {model_id} 的参数配置")
    
    def on_model_changed(self, model_id):
        """当选择的模型变化时更新界面"""
        logger.info(f"模型已更改为: {model_id}，正在更新参数控件")
        self.refresh_controls()
    
    def load_models_config(self):
        """加载模型配置文件"""
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models_config.json")
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    self.models_config = json.load(f)
                logger.info(f"已加载模型配置文件: {config_path}")
            else:
                logger.error(f"模型配置文件不存在: {config_path}")
                self.models_config = {"models": {}, "default_model": ""}
                
        except Exception as e:
            logger.error(f"加载模型配置文件失败: {str(e)}")
            self.models_config = {"models": {}, "default_model": ""}
    
    def save_models_config(self):
        """保存模型配置文件"""
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models_config.json")
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.models_config, f, indent=2, ensure_ascii=False)
            logger.info(f"模型配置已保存至: {config_path}")
            return True
        except Exception as e:
            logger.error(f"保存模型配置失败: {str(e)}")
            return False
    
    def show_models_config_dialog(self):
        """显示模型配置编辑对话框"""
        dialog = QDialog(self)
        dialog.setWindowTitle("编辑模型配置")
        dialog.setMinimumWidth(800)
        dialog.setMinimumHeight(600)
        
        layout = QVBoxLayout(dialog)
        
        # 创建配置编辑器
        self.config_editor = QTextEdit()
        self.config_editor.setFont(QFont("Courier New", 10))
        
        # 将当前配置转换为JSON文本
        config_text = json.dumps(self.models_config, indent=2, ensure_ascii=False)
        self.config_editor.setText(config_text)
        
        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        button_box.accepted.connect(lambda: self.save_models_config_from_editor(dialog))
        button_box.rejected.connect(dialog.reject)
        
        # 添加到布局
        layout.addWidget(QLabel("编辑模型配置文件 (JSON格式):"))
        layout.addWidget(self.config_editor)
        layout.addWidget(button_box)
        
        dialog.exec_()
    
    def save_models_config_from_editor(self, dialog):
        """从编辑器保存模型配置"""
        try:
            # 获取编辑器文本
            config_text = self.config_editor.toPlainText()
            
            # 尝试解析JSON
            new_config = json.loads(config_text)
            
            # 验证配置结构
            if not self._validate_models_config(new_config):
                QMessageBox.warning(
                    self, 
                    "配置无效", 
                    "模型配置结构无效，请检查格式。必须包含'models'和'default_model'字段。"
                )
                return
            
            # 更新配置
            self.models_config = new_config
            
            # 保存到文件
            if self.save_models_config():
                QMessageBox.information(self, "成功", "模型配置已保存")
                dialog.accept()
                
                # 刷新控件显示
                self.refresh_controls()
            else:
                QMessageBox.critical(self, "错误", "保存模型配置失败")
                
        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "JSON错误", f"JSON解析错误：{str(e)}")
    
    def _validate_models_config(self, config):
        """验证模型配置结构"""
        # 基本验证：确保配置包含必要的字段
        if not isinstance(config, dict):
            return False
            
        if "models" not in config or not isinstance(config["models"], dict):
            return False
            
        if "default_model" not in config:
            return False
            
        # 验证默认模型是否在模型列表中
        if config["default_model"] not in config["models"]:
            return False
            
        return True