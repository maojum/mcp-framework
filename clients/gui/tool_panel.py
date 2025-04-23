"""
工具面板模块 - 显示和管理可用的MCP工具

此模块实现了工具列表显示，工具详情查看，
以及工具状态监控等功能。
"""

import logging
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QListWidget, 
                           QListWidgetItem, QTextBrowser, QSplitter)
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot

logger = logging.getLogger(__name__)

class ToolPanel(QWidget):
    """工具面板，显示可用的MCP工具"""
    
    tool_selected = pyqtSignal(object)  # 工具被选中时发出信号
    
    def __init__(self, server_manager):
        super().__init__()
        self.server_manager = server_manager
        self.tools = []
        
        # 当服务器状态变化时更新工具列表
        self.server_manager.servers_updated.connect(self.refresh_tools)
        
        self.init_ui()
    
    def init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)
        
        # 标题
        title = QLabel("可用工具")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        
        # 创建分割器
        splitter = QSplitter(Qt.Vertical)
        
        # 工具列表
        self.tool_list = QListWidget()
        self.tool_list.itemClicked.connect(self.on_tool_selected)
        
        # 工具详情
        self.tool_details = QTextBrowser()
        self.tool_details.setOpenExternalLinks(True)
        
        # 添加到分割器
        splitter.addWidget(self.tool_list)
        splitter.addWidget(self.tool_details)
        splitter.setSizes([200, 300])
        
        # 添加到布局
        layout.addWidget(title)
        layout.addWidget(splitter)
        
        # 初始加载工具
        self.refresh_tools()
    
    @pyqtSlot()
    def refresh_tools(self):
        """刷新工具列表"""
        # 获取所有工具
        self.tools = self.server_manager.get_all_tools()
        
        # 清空列表
        self.tool_list.clear()
        self.tool_details.clear()
        
        # 填充工具列表
        for tool in self.tools:
            item = QListWidgetItem(tool.name)
            item.setToolTip(tool.description)
            self.tool_list.addItem(item)
    
    def on_tool_selected(self, item):
        """工具被选中时的处理函数"""
        # 查找对应的工具
        tool_name = item.text()
        selected_tool = next((t for t in self.tools if t.name == tool_name), None)
        
        if selected_tool:
            # 显示工具详情
            self.display_tool_details(selected_tool)
            
            # 发出工具选中信号
            self.tool_selected.emit(selected_tool)
    
    def display_tool_details(self, tool):
        """显示工具的详细信息"""
        details = f"""
        <h3>{tool.name}</h3>
        <p><b>描述:</b> {tool.description}</p>
        <h4>参数:</h4>
        """
        
        if "properties" in tool.input_schema:
            details += "<ul>"
            for param_name, param_info in tool.input_schema["properties"].items():
                param_desc = param_info.get("description", "无描述")
                param_type = param_info.get("type", "any")
                required = "必填" if param_name in tool.input_schema.get("required", []) else "可选"
                
                details += f"<li><b>{param_name}</b> ({param_type}, {required}): {param_desc}</li>"
            details += "</ul>"
        else:
            details += "<p>此工具不需要参数</p>"
        
        self.tool_details.setHtml(details)