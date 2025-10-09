"""
项目配置文件模块。

此模块负责从环境变量或 .env 文件中加载配置，并初始化全局常量和日志记录器。
"""

import os
import logging
from dotenv import load_dotenv

# 如果项目根目录下存在 .env 文件，则加载其中的环境变量
load_dotenv()

# --- 全局常量 ---

# Ollama 服务的 API 基地址
OLLAMA_BASE = os.getenv("OLLAMA_BASE", "http://localhost:11434")

# 默认的系统提示 (System Prompt)
DEFAULT_SYSTEM_PROMPT = os.getenv("DEFAULT_SYSTEM_PROMPT", 
    "You are a helpful AI assistant. Please answer the user's questions concisely.")

# --- 日志记录器初始化 ---

# 获取名为 "zodel" 的日志记录器实例，以便在整个应用中统一使用
logger = logging.getLogger("zodel")

# 防止重复添加 handler，确保日志只输出一次
if not logger.handlers:
    handler = logging.StreamHandler()
    # 定义日志输出格式：时间 - 日志级别 - 记录器名称: 消息
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    handler.setFormatter(fmt)
    logger.addHandler(handler)

# 设置日志记录器的默认级别为 INFO
logger.setLevel(logging.INFO)