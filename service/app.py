import os
import sys
from flask import Flask, render_template_string, url_for
from utils.tools import get_result_file_content, get_ip_address, resource_path
from utils.config import config
import utils.constants as constants
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")

# 添加父目录到路径
sys.path.append(os.path.dirname(sys.path[0]))

# 创建 Flask 应用
app = Flask(__name__)

# 公共函数
def get_file_content_or_default(file_path, default_message=constants.waiting_tip):
    """获取文件内容，如果文件不存在则返回默认消息。"""
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()
    return default_message

# 路由定义
@app.route("/")
def show_index():
    """显示结果内容的首页。"""
    return get_result_file_content()

@app.route("/txt")
def show_txt():
    """显示结果内容的 TXT 格式。"""
    return get_result_file_content(file_type="txt")

@app.route("/m3u")
def show_m3u():
    """显示结果内容的 M3U 格式。"""
    return get_result_file_content(file_type="m3u")

@app.route("/content")
def show_content():
    """显示结果的详细内容。"""
    return get_result_file_content(show_content=True)

@app.route("/log")
def show_log():
    """显示日志内容。"""
    log_path = resource_path(constants.sort_log_path)
    content = get_file_content_or_default(log_path)
    return render_template_string(
        """
        <head>
            <link rel='icon' href='{{ url_for('static', filename='images/favicon.ico') }}' type='image/x-icon'>
        </head>
        <pre>{{ content }}</pre>
        """,
        content=content,
    )

# 服务启动
def run_service():
    """启动 Flask 服务。"""
    try:
        if not os.environ.get("GITHUB_ACTIONS"):
            ip_address = get_ip_address()
            logging.info(f"📄 Result content: {ip_address}/content")
            logging.info(f"📄 Log content: {ip_address}/log")
            logging.info(f"🚀 M3u API: {ip_address}/m3u")
            logging.info(f"🚀 Txt API: {ip_address}/txt")
            logging.info(f"✅ IPTV URL: {ip_address}")
            app.run(host="0.0.0.0", port=config.app_port)
    except Exception as e:
        logging.error(f"❌ Failed to start the service: {e}")

# 主函数
if __name__ == "__main__":
    run_service()
