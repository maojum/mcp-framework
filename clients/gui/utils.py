"""
工具函数模块 - 提供GUI应用中需要的辅助函数

此模块包含用于GUI应用的工具函数，如客户端创建、
配置解析等功能。
"""

import logging
import httpx
import json
from PyQt5.QtWidgets import QMessageBox

logger = logging.getLogger(__name__)

class LLMClient:
    """LLM客户端类，用于与大语言模型API通信"""
    
    def __init__(self, api_key, model_id, model_info, provider_info, parameters=None):
        self.api_key = api_key
        self.model_id = model_id
        self.model_info = model_info
        self.provider_info = provider_info
        
        # 使用提供的参数或模型默认参数
        self.parameters = parameters or model_info.get("default_parameters", {})
    
    def _prepare_headers(self):
        """准备请求头"""
        if not self.provider_info or "headers" not in self.provider_info:
            return {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}
            
        headers = {}
        for key, value in self.provider_info["headers"].items():
            # 替换变量
            if isinstance(value, str):
                value = value.replace("{api_key}", self.api_key)
            headers[key] = value
            
        return headers
    
    def _prepare_payload(self, messages):
        """准备请求负载"""
        if not self.provider_info or "request_format" not in self.provider_info:
            # 默认格式（千问形式）
            return {
                "model": self.model_id,
                "input": {"messages": messages},
                "parameters": self.parameters
            }
            
        # 获取请求格式模板
        template = self.provider_info["request_format"]
        
        # 递归处理模板，替换特殊变量
        def process_template(template, data):
            if isinstance(template, dict):
                result = {}
                for k, v in template.items():
                    result[k] = process_template(v, data)
                return result
            elif isinstance(template, list):
                return [process_template(item, data) for item in template]
            elif isinstance(template, str):
                # 处理特殊变量
                if template == "{model_id}":
                    return self.model_id
                elif template == "{messages}":
                    return messages
                elif template == "{parameters}":
                    return self.parameters
                elif template in data:
                    # 处理参数中的变量
                    return data[template.strip("{}")]
                return template
            else:
                return template
                
        # 处理请求格式
        payload = process_template(template, self.parameters)
        return payload
    
    def _extract_content(self, response_data):
        """从响应数据中提取内容"""
        if not self.provider_info or "response_format" not in self.provider_info:
            # 默认格式（千问形式）
            try:
                return response_data["output"]["choices"][0]["message"]["content"]
            except (KeyError, IndexError):
                logger.error(f"无法从响应中提取内容: {response_data}")
                return "无法解析模型响应"
        
        # 使用配置的内容路径
        content_path = self.provider_info["response_format"].get("content_path")
        if not content_path:
            logger.error("未配置内容路径")
            return "未配置内容路径"
            
        # 解析内容路径
        path_parts = content_path.split(".")
        data = response_data
        
        for part in path_parts:
            # 处理数组索引，如 choices[0]
            if "[" in part and "]" in part:
                name, index_str = part.split("[", 1)
                index = int(index_str.split("]")[0])
                
                if name not in data:
                    logger.error(f"路径不存在: {part} in {data}")
                    return "路径不存在"
                    
                data = data[name][index]
            else:
                if part not in data:
                    logger.error(f"路径不存在: {part} in {data}")
                    return "路径不存在"
                    
                data = data[part]
                
        return data
    
    def get_response(self, messages):
        """从LLM获取响应
        
        Args:
            messages: 消息历史列表
            
        Returns:
            LLM的响应文本
        """
        # 获取基础URL
        base_url = self.model_info.get("base_url")
        if not base_url:
            error_message = f"模型 {self.model_id} 缺少base_url配置"
            logger.error(error_message)
            return f"配置错误: {error_message}"

        # 准备请求头和负载
        headers = self._prepare_headers()
        payload = self._prepare_payload(messages)

        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(base_url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()

                # 提取内容
                return self._extract_content(data)

        except httpx.RequestError as e:
            error_message = f"获取LLM响应出错: {str(e)}"
            logger.error(error_message)

            if isinstance(e, httpx.HTTPStatusError):
                status_code = e.response.status_code
                logger.error(f"状态码: {status_code}")
                logger.error(f"响应详情: {e.response.text}")

            return (
                f"我遇到了一个错误: {error_message}. "
                "请再试一次或者重新表述您的请求。"
            )

def create_llm_client(api_key, model_id, model_info=None, provider_info=None, parameters=None):
    """创建LLM客户端
    
    Args:
        api_key: API密钥
        model_id: 模型ID
        model_info: 模型信息
        provider_info: 提供商信息
        parameters: 模型参数
        
    Returns:
        LLMClient实例
    """
    return LLMClient(api_key, model_id, model_info, provider_info, parameters)

def show_error_dialog(parent, title, message):
    """显示错误对话框
    
    Args:
        parent: 父窗口
        title: 对话框标题
        message: 错误信息
    """
    QMessageBox.critical(parent, title, message)