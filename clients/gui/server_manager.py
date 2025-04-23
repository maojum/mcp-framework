"""
服务器管理器模块 - 管理MCP服务器连接

此模块负责MCP服务器的启动、停止、状态监控，
以及工具的获取和执行。
"""

import json
import logging
import threading
import asyncio
from contextlib import AsyncExitStack 
import shutil
import os
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QListWidget, 
                           QListWidgetItem, QPushButton, QHBoxLayout)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QThread

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)

# 工具类定义
class Tool:
    """表示MCP工具"""
    
    def __init__(self, name, description, input_schema):
        self.name = name
        self.description = description
        self.input_schema = input_schema

# 服务器工作线程
class ServerWorker(QThread):
    """后台线程处理服务器操作"""
    
    server_ready = pyqtSignal(str, object)  # 服务器就绪信号
    server_failed = pyqtSignal(str, str)  # 服务器失败信号
    tools_ready = pyqtSignal(str, list)  # 工具列表就绪信号
    tool_executed = pyqtSignal(str, str, object)  # 工具执行完成信号
    tool_failed = pyqtSignal(str, str, str)  # 工具执行失败信号
    
    def __init__(self, name, config):
        super().__init__()
        self.name = name
        self.config = config
        self.session = None
        self.command = "initialize"  # 初始命令
        self.tool_name = None
        self.tool_args = None
        self.loop = None
        self.exit_stack = None
        self.result = None  # 存储工具执行结果
        
    def run(self):
        """运行服务器操作"""
        if self.command == "initialize":
            self._initialize_server()
        elif self.command == "list_tools":
            self._list_tools()
        elif self.command == "execute_tool":
            self._execute_tool()
    
    def _initialize_server(self):
        """初始化服务器连接"""
        try:
            # 创建事件循环
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            
            # 初始化服务器
            command = (
                shutil.which("npx")
                if self.config["command"] == "npx"
                else self.config["command"]
            )
            
            if command is None:
                self.server_failed.emit(self.name, "无法找到指定命令")
                return
            
            server_params = StdioServerParameters(
                command=command,
                args=self.config["args"],
                env={**os.environ, **self.config["env"]}
                if self.config.get("env")
                else None,
            )
            
            # 使用 AsyncExitStack 来管理资源
            async def setup_server():
                self.exit_stack = AsyncExitStack()  # 从 contextlib 导入
                stdio_transport = await self.exit_stack.enter_async_context(
                    stdio_client(server_params)
                )
                read, write = stdio_transport
                session = await self.exit_stack.enter_async_context(
                    ClientSession(read, write)
                )
                await session.initialize()
                return session
            
            self.session = self.loop.run_until_complete(setup_server())
            
            # 发出服务器就绪信号
            self.server_ready.emit(self.name, self.session)
            
            # 获取工具列表
            self._list_tools()
            
        except Exception as e:
            error_msg = f"初始化服务器失败: {str(e)}"
            logger.error(error_msg)
            self.server_failed.emit(self.name, error_msg)
    
    def cleanup(self):
        """清理服务器资源"""
        if self.exit_stack and self.loop:
            try:
                # 创建一个新的事件循环用于清理
                cleanup_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(cleanup_loop)

                # 关闭旧的循环中的任务
                if not self.loop.is_closed():
                    for task in asyncio.all_tasks(self.loop):
                        task.cancel()

                    # 给任务一点时间完成取消
                    try:
                        self.loop.run_until_complete(asyncio.sleep(0.1))
                    except:
                        pass

                    self.loop.close()

                # 重新初始化资源以安全关闭
                self.exit_stack = None

            except Exception as e:
                logger.error(f"清理服务器资源时出错: {str(e)}")
            finally:
                # 确保循环已关闭
                if self.loop and not self.loop.is_closed():
                    self.loop.close()

        self.session = None
        self.exit_stack = None
   
    def _list_tools(self):
        """获取工具列表"""
        if not self.session:
            self.server_failed.emit(self.name, "服务器未初始化")
            return

        try:
            # 使用现有事件循环而不是创建新的
            if not self.loop or self.loop.is_closed():
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)

            # 获取工具列表
            async def get_tools():
                tools_response = await self.session.list_tools()
                tools = []
                for item in tools_response:
                    if isinstance(item, tuple) and item[0] == "tools":
                        for tool in item[1]:
                            tools.append(Tool(tool.name, tool.description, tool.inputSchema))
                return tools

            tools = self.loop.run_until_complete(get_tools())

            # 发出工具列表就绪信号
            self.tools_ready.emit(self.name, tools)

        except Exception as e:
            error_msg = f"获取工具列表失败: {str(e)}"
            logger.error(error_msg)
            self.server_failed.emit(self.name, error_msg)
    
    def _execute_tool(self):
        """执行工具，直接同步方式"""
        if not self.session or not self.tool_name:
            error_msg = "服务器未初始化或工具名称为空"
            self.tool_failed.emit(self.name, self.tool_name, error_msg)
            return error_msg
            
        try:
            # 确保我们有一个工作的事件循环
            if not self.loop or self.loop.is_closed():
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)
            
            # 定义异步执行函数
            async def exec_tool():
                try:
                    logger.debug(f"开始调用工具 {self.tool_name} 参数: {self.tool_args}")
                    return await self.session.call_tool(self.tool_name, self.tool_args)
                except Exception as e:
                    logger.error(f"工具调用异步异常: {e}")
                    raise
            
            # 执行异步函数并获取结果
            logger.debug("开始执行工具异步调用")
            result = self.loop.run_until_complete(exec_tool())
            logger.debug(f"工具执行完成，结果: {result}")
            
            # 发出信号
            self.tool_executed.emit(self.name, self.tool_name, result)
            return result
            
        except Exception as e:
            error_msg = f"执行工具失败: {str(e)}"
            logger.error(error_msg)
            self.tool_failed.emit(self.name, self.tool_name, error_msg)
            return error_msg

    def execute_tool(self, tool_name, arguments):
        """设置工具执行任务"""
        self.command = "execute_tool"
        self.tool_name = tool_name
        self.tool_args = arguments
        self.start()


class ServerManager(QWidget):
    """管理MCP服务器的组件"""
    
    servers_updated = pyqtSignal()  # 服务器状态更新信号
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.servers = {}  # 服务器字典
        self.workers = {}  # 工作线程字典
        self.tools = {}  # 工具字典，按服务器分组
        
        self.init_ui()
        self.load_servers()
    
    def init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)
        
        # 标题
        title = QLabel("MCP服务器")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        
        # 服务器列表
        self.server_list = QListWidget()
        
        # 控制按钮
        button_layout = QHBoxLayout()
        
        self.refresh_button = QPushButton("刷新")
        self.refresh_button.clicked.connect(self.refresh_servers)
        
        self.restart_button = QPushButton("重启")
        self.restart_button.clicked.connect(self.restart_selected_server)
        
        button_layout.addWidget(self.refresh_button)
        button_layout.addWidget(self.restart_button)
        
        # 添加到布局
        layout.addWidget(title)
        layout.addWidget(self.server_list)
        layout.addLayout(button_layout)
    
    def load_servers(self):
        """加载服务器配置"""
        if "mcpServers" in self.config:
            for name, srv_config in self.config["mcpServers"].items():
                self.add_server(name, srv_config)
    
    def add_server(self, name, config):
        """添加服务器"""
        # 创建服务器线程
        worker = ServerWorker(name, config)
        
        # 连接信号
        worker.server_ready.connect(self.on_server_ready)
        worker.server_failed.connect(self.on_server_failed)
        worker.tools_ready.connect(self.on_tools_ready)
        worker.tool_executed.connect(self.on_tool_executed)
        worker.tool_failed.connect(self.on_tool_failed)
        
        # 存储工作线程
        self.workers[name] = worker
        
        # 启动工作线程
        worker.start()
        
        # 添加到服务器列表
        item = QListWidgetItem(f"{name} (连接中...)")
        item.setData(Qt.UserRole, name)
        self.server_list.addItem(item)
    
    def on_server_ready(self, name, session):
        """服务器就绪处理函数"""
        logger.info(f"服务器 {name} 已就绪")
        
        # 更新列表项
        for i in range(self.server_list.count()):
            item = self.server_list.item(i)
            if item.data(Qt.UserRole) == name:
                item.setText(f"{name} (已连接)")
                item.setToolTip("服务器已连接")
                break
    
    def on_server_failed(self, name, error):
        """服务器失败处理函数"""
        logger.error(f"服务器 {name} 失败: {error}")
        
        # 更新列表项
        for i in range(self.server_list.count()):
            item = self.server_list.item(i)
            if item.data(Qt.UserRole) == name:
                item.setText(f"{name} (错误)")
                item.setToolTip(f"错误: {error}")
                break
    
    def on_tools_ready(self, name, tools):
        """工具列表就绪处理函数"""
        logger.info(f"服务器 {name} 提供 {len(tools)} 个工具")
        
        # 存储工具
        self.tools[name] = tools
        
        # 发出更新信号
        self.servers_updated.emit()
    
    def on_tool_executed(self, server_name, tool_name, result):
        """工具执行完成处理函数"""
        logger.info(f"工具 {tool_name} 在服务器 {server_name} 上执行完成")
        # 此处保存结果供查询，在实际实现中可能需要更复杂的处理
    
    def on_tool_failed(self, server_name, tool_name, error):
        """工具执行失败处理函数"""
        logger.error(f"工具 {tool_name} 在服务器 {server_name} 上执行失败: {error}")
    
    def refresh_servers(self):
        """刷新所有服务器"""
        # 清空服务器列表
        self.server_list.clear()
        
        # 清空工具缓存
        self.tools.clear()
        
        # 关闭所有工作线程
        for worker in self.workers.values():
            worker.terminate()
            worker.wait()
        
        self.workers.clear()
        
        # 重新加载服务器
        self.load_servers()
    
    def restart_selected_server(self):
        """重启选中的服务器"""
        selected_items = self.server_list.selectedItems()
        if not selected_items:
            return
            
        # 获取选中服务器名称
        name = selected_items[0].data(Qt.UserRole)
        
        # 从配置中获取服务器配置
        if name in self.config["mcpServers"]:
            # 关闭现有工作线程
            if name in self.workers:
                # 先执行清理
                try:
                    self.workers[name].cleanup()
                except Exception as e:
                    logger.error(f"重启服务器时清理资源出错: {str(e)}")
                    
                self.workers[name].terminate()
                self.workers[name].wait()
                del self.workers[name]
            
            # 从工具缓存中移除
            if name in self.tools:
                del self.tools[name]
            
            # 移除列表项
            for i in range(self.server_list.count()):
                item = self.server_list.item(i)
                if item.data(Qt.UserRole) == name:
                    self.server_list.takeItem(i)
                    break
                
            # 重新添加服务器
            self.add_server(name, self.config["mcpServers"][name])
    
    def get_all_tools(self):
        """获取所有可用工具"""
        all_tools = []
        for tools in self.tools.values():
            all_tools.extend(tools)
        return all_tools
    
    def execute_tool(self, tool_name, arguments):
        """执行指定工具 - 直接同步方式"""
        # 查找拥有此工具的服务器
        for server_name, tools in self.tools.items():
            for tool in tools:
                if tool.name == tool_name:
                    logger.info(f"找到工具 {tool_name} 在服务器 {server_name} 上，准备执行")
                    
                    # 获取已初始化的工作线程
                    worker = self.workers[server_name]
                    
                    # 设置执行参数
                    worker.tool_name = tool_name
                    worker.tool_args = arguments
                    
                    # 直接调用执行方法
                    result = worker._execute_tool()
                    return result
        
        error_msg = f"未找到工具: {tool_name}"
        logger.warning(error_msg)
        return error_msg
    
    def close_all_servers(self):
        """关闭所有服务器"""
        for worker in self.workers.values():
            # 先执行清理
            if hasattr(worker, 'cleanup'):
                try:
                    worker.cleanup()
                except Exception as e:
                    logger.error(f"关闭服务器时出错: {str(e)}")

            # 然后终止线程
            worker.terminate()
            worker.wait()