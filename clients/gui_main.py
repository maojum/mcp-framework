"""
GUI入口文件 - 负责启动MCP的图形界面应用

此模块作为MCP GUI应用的启动点，初始化应用程序并显示主窗口。
它确保所有必要的组件和依赖项被正确加载。
"""

import sys
import logging
from PyQt5.QtWidgets import QApplication
from gui.main_window import MainWindow
from dotenv import load_dotenv

# 配置日志
logging.basicConfig(
    level=logging.DEBUG, 
    format="%(asctime)s - [%(levelname)s] - %(module)s - %(message)s"
)
logger = logging.getLogger(__name__)

def main():
    """初始化并启动GUI应用程序"""
    # 加载环境变量
    load_dotenv()
    
    # 创建Qt应用
    app = QApplication(sys.argv)
    app.setApplicationName("MCP Assistant")
    
    # 创建并显示主窗口
    window = MainWindow()
    window.show()
    
    # 执行应用
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()