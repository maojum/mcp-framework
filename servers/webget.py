import requests
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import base64
import re
from mcp.server.fastmcp import FastMCP

# 创建 MCP Server
mcp = FastMCP("网页内容获取器")

# 存储已获取的网页内容
page_cache = {}

# URL与资源ID之间的转换
def url_to_resource_id(url):
    return base64.urlsafe_b64encode(url.encode()).decode()

def resource_id_to_url(resource_id):
    try:
        return base64.urlsafe_b64decode(resource_id.encode()).decode()
    except:
        return None

@mcp.tool()
def fetch_webpage(url: str, timeout: int = 5) -> str:
    """获取指定URL的网页内容。
    
    Args:
        url: 完整的网页URL，需以http://或https://开头
        timeout: 请求超时时间（秒），默认为5秒
    
    Returns:
        获取状态信息和如何访问内容的指导
    """
    if not url.startswith(('http://', 'https://')):
        return "错误：URL必须以http://或https://开头"
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'close',  # 不保持连接
        }
        
        # 使用更短的超时时间
        response = requests.get(
            url, 
            headers=headers, 
            timeout=timeout,
            allow_redirects=True,
            stream=False  # 不使用流式传输
        )
        response.raise_for_status()
        
        content_type = response.headers.get('Content-Type', 'text/html')
        # 限制内容大小，防止超大页面导致问题
        content = response.text[:1000000]  # 限制为约1MB文本
        
        # 存储内容
        page_cache[url] = (content, content_type)
        resource_id = url_to_resource_id(url)
        
        return f"""成功获取网页: {url}
网页内容现在可通过以下资源访问:
- 内容: webpage://{resource_id}
- 信息: webpage://{resource_id}/info
        """
    except requests.exceptions.Timeout:
        return f"错误：获取网页 {url} 超时。请考虑增加超时时间或检查网站可访问性。"
    except requests.exceptions.ConnectionError:
        return f"错误：连接到 {url} 失败。请检查网络连接或URL是否正确。"
    except requests.exceptions.HTTPError as e:
        return f"HTTP错误: {e}。服务器返回了错误状态码。"
    except requests.exceptions.TooManyRedirects:
        return f"错误：获取 {url} 时重定向过多。这可能表明URL配置有问题。"
    except Exception as e:
        return f"获取网页失败: {str(e)}"

@mcp.resource("webpage://{resource_id}")
def get_webpage_content(resource_id: str) -> str:
    """获取之前下载的网页内容。
    
    Args:
        resource_id: 网页的资源ID
    """
    url = resource_id_to_url(resource_id)
    if url and url in page_cache:
        content, _ = page_cache[url]
        return content
    return f"错误：找不到资源ID为 {resource_id} 的网页。请先使用fetch_webpage工具获取。"

@mcp.resource("webpage://{resource_id}/info")
def get_webpage_info(resource_id: str) -> str:
    """获取已下载网页的信息。
    
    Args:
        resource_id: 网页的资源ID
    """
    url = resource_id_to_url(resource_id)
    if url and url in page_cache:
        content, content_type = page_cache[url]
        parsed_url = urlparse(url)
        
        # 计算一些基本统计信息
        word_count = len(re.findall(r'\w+', content))
        line_count = content.count('\n') + 1
        
        return f"""网页信息:
URL: {url}
域名: {parsed_url.netloc}
内容类型: {content_type}
内容大小: {len(content)} 字节
估计单词数: {word_count}
行数: {line_count}
"""
    return f"错误：找不到资源ID为 {resource_id} 的网页。请先使用fetch_webpage工具获取。"

@mcp.tool()
def list_fetched_pages() -> str:
    """列出所有已获取的网页。"""
    if not page_cache:
        return "尚未获取任何网页。"
    
    result = "已获取的网页:\n"
    for url in page_cache:
        resource_id = url_to_resource_id(url)
        result += f"- {url}\n  资源ID: {resource_id}\n"
    return result

@mcp.tool()
def extract_links(url: str) -> str:
    """从已获取的网页中提取所有链接。
    
    Args:
        url: 要分析的网页URL
    """
    if url not in page_cache:
        return f"错误：网页 {url} 尚未获取。请先使用fetch_webpage工具获取。"
    
    content, _ = page_cache[url]
    
    try:
        soup = BeautifulSoup(content, 'html.parser')
        links = []
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            # 处理相对链接
            if href.startswith('/'):
                parsed_url = urlparse(url)
                base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
                href = base_url + href
            links.append(href)
        
        if not links:
            return f"在 {url} 中未找到链接"
        
        return f"在 {url} 中找到 {len(links)} 个链接:\n" + "\n".join([f"- {link}" for link in links])
    except Exception as e:
        return f"提取链接时出错: {str(e)}"

@mcp.tool()
def extract_text(url: str) -> str:
    """从已获取的网页中提取纯文本内容，去除HTML标签。
    
    Args:
        url: 要处理的网页URL
    """
    if url not in page_cache:
        return f"错误：网页 {url} 尚未获取。请先使用fetch_webpage工具获取。"
    
    content, _ = page_cache[url]
    
    try:
        soup = BeautifulSoup(content, 'html.parser')
        
        # 删除脚本和样式元素
        for script in soup(["script", "style"]):
            script.extract()
            
        # 获取文本
        text = soup.get_text()
        
        # 清理文本（删除多余空白）
        lines = (line.strip() for line in text.splitlines())
        text = '\n'.join(line for line in lines if line)
        
        return text
    except Exception as e:
        return f"提取文本时出错: {str(e)}"

@mcp.prompt()
def web_scraping_guide() -> str:
    """提供网页爬取的最佳实践和提示"""
    return """# 网页爬取最佳实践指南

1. **尊重robots.txt文件**
   始终检查网站的robots.txt文件，了解哪些内容允许爬取。

2. **设置合理的请求频率**
   不要发送过多过快的请求，考虑在请求之间添加延迟。

3. **使用适当的User-Agent**
   标识你的爬虫身份，不要伪装成浏览器。

4. **检查API可用性**
   许多网站提供API，这通常比直接爬取页面更好。

5. **错误处理**
   实现重试机制和错误处理，优雅地处理异常情况。

6. **网站条款合规**
   确保你的爬取活动符合网站服务条款。

7. **数据使用道德**
   合理使用爬取的数据，尊重版权和隐私。

8. **使用适当的解析工具**
   使用BeautifulSoup、lxml等专门的HTML解析库。

9. **避免滥用资源**
   只获取必要的数据，避免不必要的带宽消耗。

10. **缓存数据**
    存储已获取的内容，避免重复请求相同内容。
"""

if __name__ == "__main__":
    # 初始化并运行服务器
    mcp.run()