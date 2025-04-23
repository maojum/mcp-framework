"""
聊天面板模块 - 处理用户与AI助手的对话界面

此模块实现了聊天界面，包括消息显示、输入框和发送按钮，
并处理与LLM的通信以及工具调用的展示。
"""

import json
import logging
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, 
                            QLineEdit, QPushButton, QLabel, QProgressBar)
from PyQt5.QtCore import Qt, pyqtSignal, QThread
from PyQt5.QtGui import QFont, QColor

logger = logging.getLogger(__name__)

class MessageProcessor(QThread):
    """后台线程处理消息，避免UI阻塞"""
    
    response_ready = pyqtSignal(str)
    tool_result_ready = pyqtSignal(str)
    final_response_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, server_manager, model_selector, message, messages_history):
        super().__init__()
        self.server_manager = server_manager
        self.model_selector = model_selector
        self.message = message
        self.messages_history = messages_history.copy()  # 复制历史记录避免竞态条件
    
    def run(self):
        """运行消息处理流程"""
        try:
            # 获取当前选择的LLM客户端
            llm_client = self.model_selector.get_current_llm_client()
            
            if not llm_client:
                self.error_occurred.emit("无法创建LLM客户端，请检查API密钥和模型配置")
                return
                
            # 添加用户消息到历史
            self.messages_history.append({"role": "user", "content": self.message})
            
            # 获取LLM响应
            llm_response = llm_client.get_response(self.messages_history)
            logger.debug(f"LLM原始响应: {llm_response}")
            self.response_ready.emit(llm_response)
            
            # 尝试处理可能的工具调用
            try:
                tool_call = json.loads(llm_response)
                logger.debug(f"尝试解析JSON: {tool_call}")
                
                if "tool" in tool_call and "arguments" in tool_call:
                    # 这是工具调用
                    logger.info(f"检测到工具调用: {tool_call['tool']}")
                    
                    # 执行工具
                    tool_name = tool_call["tool"]
                    arguments = tool_call["arguments"]
                    
                    # 执行工具并获取结果
                    tool_result = self.server_manager.execute_tool(tool_name, arguments)
                    logger.info(f"工具 {tool_name} 执行结果: {tool_result}")
                    
                    # 发出工具结果信号
                    self.tool_result_ready.emit(str(tool_result))
                    
                    # 添加结果到历史
                    self.messages_history.append({"role": "assistant", "content": llm_response})
                    self.messages_history.append({"role": "system", "content": f"Tool execution result: {tool_result}"})
                    
                    # 获取最终响应
                    final_response = llm_client.get_response(self.messages_history)
                    logger.debug(f"最终响应: {final_response}")
                    self.final_response_ready.emit(final_response)
            except json.JSONDecodeError as e:
                # 不是JSON，可能是普通文本响应
                logger.debug(f"不是JSON响应: {e}")
                # 无需额外处理，已经通过response_ready发送了响应
                pass
                
        except Exception as e:
            error_msg = f"处理消息时出错: {str(e)}"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)


class ChatPanel(QWidget):
    """聊天界面面板，处理用户与AI的对话"""
    
    def __init__(self, server_manager, model_selector):
        super().__init__()
        self.server_manager = server_manager
        self.model_selector = model_selector
        self.messages_history = []
        
        # 初始化系统提示
        self.init_system_prompt()
        
        # 设置界面
        self.init_ui()
    
    def init_system_prompt(self):
        """初始化系统提示消息"""
        # 获取所有工具
        tools = self.server_manager.get_all_tools()

        # 格式化工具描述
        tools_description = "\n".join([self.format_tool(tool) for tool in tools])

        system_message = (
            "You are a helpful assistant with access to these tools:\n\n"
            f"{tools_description}\n"
            "Choose the appropriate tool based on the user's question. "
            "If no tool is needed, reply directly.\n\n"
            "IMPORTANT: When you need to use a tool, you must ONLY respond with "
            "the exact JSON object format below, nothing else:\n"
            "{\n"
            '    "tool": "tool-name",\n'
            '    "arguments": {\n'
            '        "argument-name": "value"\n'
            "    }\n"
            "}\n\n"
            "After receiving a tool's response:\n"
            "1. Transform the raw data into a natural, conversational response\n"
            "2. Keep responses concise but informative\n"
            "3. Focus on the most relevant information\n"
            "4. Use appropriate context from the user's question\n"
            "5. Avoid simply repeating the raw data\n\n"
            "Please use only the tools that are explicitly defined above."
        )

        # 添加到消息历史
        self.messages_history = [{"role": "system", "content": system_message}]

        logger.debug(f"系统提示: {system_message}")
        logger.debug(f"检测到的工具数量: {len(tools)}")
        for tool in tools:
            logger.debug(f"工具名称: {tool.name}, 描述: {tool.description}")

   
    def format_tool(self, tool):
        args_desc = []
        if "properties" in tool.input_schema:
            for param_name, param_info in tool.input_schema["properties"].items():
                arg_desc = (
                    f"- {param_name}: {param_info.get('description', 'No description')}"
                )
                if param_name in tool.input_schema.get("required", []):
                    arg_desc += " (required)"
                args_desc.append(arg_desc)

        return f"""
Tool: {tool.name}
Description: {tool.description}
Arguments:
{chr(10).join(args_desc)}
"""
    
    def init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)
        
        # 聊天历史显示区域
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setFont(QFont("Arial", 10))
        
        # 输入区域
        input_layout = QHBoxLayout()
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("输入消息...")
        self.message_input.returnPressed.connect(self.send_message)
        
        self.send_button = QPushButton("发送")
        self.send_button.clicked.connect(self.send_message)
        
        input_layout.addWidget(self.message_input)
        input_layout.addWidget(self.send_button)
        
        # 进度条（初始隐藏）
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        
        # 添加到主布局
        layout.addWidget(self.chat_display)
        layout.addWidget(self.progress_bar)
        layout.addLayout(input_layout)
        
        # 显示欢迎消息
        self.add_system_message("欢迎使用MCP助手！请输入您的问题。")
    
    def add_user_message(self, text):
        """添加用户消息到聊天显示区域"""
        self.chat_display.append(f'<div style="text-align: right;"><b>你:</b> {text}</div>')

    def add_assistant_message(self, text):
        """添加助手消息到聊天显示区域"""
        self.chat_display.append(f'<div style="text-align: left;"><b>助手:</b> {text}</div>')
    
    def add_system_message(self, text):
        """添加系统消息到聊天显示区域"""
        self.chat_display.append(f'<div style="color: gray; text-align: left;">{text}</div>')
    
    def add_tool_result(self, text):
        """添加工具执行结果到聊天显示区域"""
        self.chat_display.append(f'<div style="color: blue; font-family: monospace; background-color: #f0f0f0; padding: 5px;"><b>工具执行结果:</b> {text}</div>')
    
    def send_message(self):
        """发送用户消息"""
        message = self.message_input.text().strip()
        if not message:
            return

        # 在每次发送消息前刷新系统提示，确保工具信息是最新的
        self.refresh_system_prompt()

        # 清空输入框
        self.message_input.clear()

        # 添加用户消息到聊天显示
        self.add_user_message(message)

        # 显示"正在思考"的提示
        self.add_system_message("助手正在思考...")
        self.send_button.setEnabled(False)

        # 创建并启动处理线程
        self.processor = MessageProcessor(
            self.server_manager,
            self.model_selector,
            message,
            self.messages_history
        )

        # 连接信号
        self.processor.response_ready.connect(self.handle_llm_response)
        self.processor.tool_result_ready.connect(self.handle_tool_result)
        self.processor.final_response_ready.connect(self.handle_final_response)
        self.processor.error_occurred.connect(self.handle_error)

        # 启动线程
        self.processor.start()
        
    def refresh_system_prompt(self):
        """刷新系统提示以获取最新工具信息"""
        # 获取所有工具
        tools = self.server_manager.get_all_tools()

        # 记录工具数量以进行调试
        logger.debug(f"刷新系统提示，当前工具数量: {len(tools)}")
        for tool in tools:
            logger.debug(f"工具: {tool.name}")

        # 如果没有工具可用，记录警告但继续执行
        if not tools:
            logger.warning("无可用工具，可能服务器尚未准备好")

        # 格式化工具描述
        tools_description = "\n".join([self.format_tool(tool) for tool in tools])

        # 更新系统提示
        system_message = (
            "You are a helpful assistant with access to these tools:\n\n"
            f"{tools_description}\n"
            "Choose the appropriate tool based on the user's question. "
            "If no tool is needed, reply directly.\n\n"
            "IMPORTANT: When you need to use a tool, you must ONLY respond with "
            "the exact JSON object format below, nothing else:\n"
            "{\n"
            '    "tool": "tool-name",\n'
            '    "arguments": {\n'
            '        "argument-name": "value"\n'
            "    }\n"
            "}\n\n"
            "After receiving a tool's response:\n"
            "1. Transform the raw data into a natural, conversational response\n"
            "2. Keep responses concise but informative\n"
            "3. Focus on the most relevant information\n"
            "4. Use appropriate context from the user's question\n"
            "5. Avoid simply repeating the raw data\n\n"
            "Please use only the tools that are explicitly defined above."
        )

        # 更新消息历史中的系统提示
        if self.messages_history and self.messages_history[0]["role"] == "system":
            self.messages_history[0] = {"role": "system", "content": system_message}
        else:
            # 如果历史中没有系统提示，则添加
            self.messages_history.insert(0, {"role": "system", "content": system_message})

        logger.debug(f"已更新系统提示，包含工具数量: {len(tools)}")    
        
    def handle_llm_response(self, response):
        """处理LLM的初始响应"""
        cursor = self.chat_display.textCursor()
        cursor.movePosition(cursor.End)
        cursor.movePosition(cursor.StartOfBlock, cursor.KeepAnchor)
        cursor.removeSelectedText()
        
        try:
            # 尝试解析是否为工具调用
            tool_call = json.loads(response)
            if "tool" in tool_call and "arguments" in tool_call:
                tool_name = tool_call["tool"]
                args = json.dumps(tool_call["arguments"], indent=2, ensure_ascii=False)

                logger.info(f"助手正在调用工具: {tool_name}")
                logger.info(f"参数: {args}")

                self.add_system_message("助手正在处理您的请求...")

                # 存储到历史
                self.messages_history.append({"role": "assistant", "content": response})
                return
        except json.JSONDecodeError:
            # 不是工具调用，显示为普通回复
            pass
            
        # 常规回复
        self.add_assistant_message(response)
        
        # 添加到历史
        self.messages_history.append({"role": "assistant", "content": response})
        
        # 重新启用发送按钮
        self.send_button.setEnabled(True)
    
    def handle_tool_result(self, result):
        """处理工具执行结果"""
        # self.add_tool_result(result)
        logger.info(f"工具执行结果: {result}")
        
        # 添加到历史
        self.messages_history.append({"role": "system", "content": f"Tool execution result: {result}"})
    
    def handle_final_response(self, response):
        """处理基于工具结果的最终响应"""
        self.add_assistant_message(response)
        
        # 添加到历史
        self.messages_history.append({"role": "assistant", "content": response})
        
        # 重新启用发送按钮
        self.send_button.setEnabled(True)
    
    def handle_error(self, error_message):
        """处理错误"""
        self.add_system_message(f"错误: {error_message}")
        self.send_button.setEnabled(True)