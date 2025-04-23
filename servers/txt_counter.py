import os
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# 创建 MCP Server
mcp = FastMCP("桌面 TXT 文件统计器")

@mcp.tool()
def count_desktop_txt_files() -> int:
    """统计桌面上 .txt 文件的数量。"""
    # 获取桌面路径
    desktop_path = Path("D:/桌面")

    # 统计 .txt 文件
    txt_files = list(desktop_path.glob("*.txt"))
    return len(txt_files)

@mcp.tool()
def list_desktop_txt_files() -> str:
    """获取桌面上所有 .txt 文件的列表。"""
    # 获取桌面路径
    desktop_path = Path("D:/桌面")

    # 获取所有 .txt 文件
    txt_files = list(desktop_path.glob("*.txt"))

    # 返回文件名
    if not txt_files:
        return "桌面上未找到 .txt 文件。"

    # 格式化文件名列表
    file_list = "\n".join([f"- {file.name}" for file in txt_files])
    return f"在桌面上找到 {len(txt_files)} 个 .txt 文件：\n{file_list}"

if __name__ == "__main__":
    # 初始化并运行服务器
    mcp.run()