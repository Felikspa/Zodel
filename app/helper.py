"""
辅助函数模块。

此模块包含与外部服务交互的各种辅助函数，包括：
- 初始化不同 LLM 提供商 (Ollama, OpenAI, GenStudio) 的客户端。
- 一个统一的流式聊天函数 `stream_chat` 来处理对不同提供商的 API 调用。
- 自动发现并列出所有可用模型的函数。
- 从模型全名中推断提供商和提取纯模型名的工具函数。
"""

import os
import requests
import subprocess
from typing import List, Dict, Generator, Optional

# 从配置模块导入日志记录器
from .config import logger

# --- 客户端导入与实例化 ---

# 尝试导入 ollama 库
try:
    import ollama
except ImportError:
    ollama = None
    logger.warning("Ollama library not installed. To use local models, run `pip install ollama`.")

# 尝试导入 openai 库
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None # 定义一个占位符以避免后续代码出错
    logger.warning("OpenAI library not installed. Cloud and GenStudio services will be unavailable.")


def _initialize_openai_client(api_key_env: str, base_url_env: str, client_name: str) -> Optional[OpenAI]: # type: ignore
    """
    一个通用的 OpenAI 兼容客户端初始化函数。

    Args:
        api_key_env (str): 存储 API Key 的环境变量名称。
        base_url_env (str): 存储 Base URL 的环境变量名称。
        client_name (str): 用于日志记录的客户端名称。

    Returns:
        Optional[OpenAI]: 成功则返回 OpenAI 客户端实例，否则返回 None。
    """
    if not OpenAI: # 如果 openai 库未安装，则直接返回
        return None
        
    api_key = os.getenv(api_key_env)
    base_url = os.getenv(base_url_env)
    
    if api_key and base_url:
        try:
            client = OpenAI(api_key=api_key, base_url=base_url)
            logger.info(f"{client_name} client initialized successfully.")
            return client
        except Exception as e:
            logger.error(f"Failed to initialize {client_name} client: {e}")
            return None
    else:
        logger.warning(f"{client_name} client not initialized. Missing '{api_key_env}' or '{base_url_env}' environment variables.")
        return None

# 初始化各个客户端
openai_client = _initialize_openai_client("OPENAI_API_KEY", "OPENAI_BASE_URL", "OpenAI")
genstudio_client = _initialize_openai_client("GENSTUDIO_API_KEY", "GENSTUDIO_BASE_URL", "GenStudio")


# --- 核心流式聊天函数 ---

def stream_chat(provider: str, model: str, messages: List[Dict[str, str]]) -> Generator[str, None, None]:
    """
    统一的流式聊天接口，兼容 Ollama, OpenAI, 和 GenStudio。

    Args:
        provider (str): 提供商名称 ('ollama', 'openai', 'genstudio')，大小写不敏感。
        model (str): 不带前缀的纯模型名称。
        messages (List[Dict[str, str]]): OpenAI 聊天格式的消息列表。
    
    Returns:
        Generator[str, None, None]: 一个生成器，每次 yield 一个字符串内容块 (token)。
    
    Raises:
        ImportError: 如果所需的客户端库未安装。
        ConnectionError: 如果客户端未被成功初始化。
        ValueError: 如果提供了不支持的 provider。
    """
    provider = provider.lower()

    if provider == "ollama":
        if not ollama:
            raise ImportError("Ollama client is not available. Please run `pip install ollama`.")
        
        stream = ollama.chat(model=model, messages=messages, stream=True)
        for chunk in stream:
            content = chunk.get("message", {}).get("content")
            if content:
                yield content

    elif provider in ["openai", "genstudio"]:
        client_map = {
            "openai": openai_client,
            "genstudio": genstudio_client
        }
        client_to_use = client_map[provider]
        
        if not client_to_use:
            raise ConnectionError(f"{provider.upper()} client is not initialized. Please check your environment variables.")
        
        stream = client_to_use.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
        )
        
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
    
    else:
        raise ValueError(f"Unsupported provider: '{provider}'. Supported providers are 'ollama', 'openai', 'genstudio'.")

# --- 模型发现函数 ---

def get_ollama_models(timeout: float = 2.0) -> List[str]:
    """
    获取本地 Ollama 模型列表，并为每个模型名称添加 'Ollama:' 前缀。

    Args:
        timeout (float): API 请求的超时时间（秒）。

    Returns:
        List[str]: 带有前缀的 Ollama 模型名称列表。
    """
    try:
        response = requests.get(f"{os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')}/api/tags", timeout=timeout)
        response.raise_for_status()
        models_data = response.json().get("models", [])
        models = [f"Ollama:{m['name']}" for m in models_data]
        if models:
            logger.info("Found local Ollama models via API: %s", [m.split(':')[-1] for m in models])
            return models
    except Exception as e:
        logger.debug("Ollama API discovery failed: %s. Falling back to CLI.", e)

    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True, check=True, timeout=5)
        lines = result.stdout.strip().splitlines()[1:]
        models = [f"Ollama:{line.split()[0]}" for line in lines]
        logger.info("Found local Ollama models via CLI: %s", [m.split(':')[-1] for m in models])
        return models
    except Exception as e:
        logger.warning("Ollama CLI discovery failed: %s. Is the ollama service running?", e)
        return []

def get_openai_compatible_models(client: Optional[OpenAI], prefix: str) -> List[str]: # type: ignore
    """
    一个通用的函数，用于从任何 OpenAI 兼容的 API 获取模型列表。

    Args:
        client (Optional[OpenAI]): 已初始化的 OpenAI 客户端实例。
        prefix (str): 要添加到每个模型名称的前缀 (例如, 'Cloud', 'GenStudio')。

    Returns:
        List[str]: 带有前缀的模型名称列表。
    """
    if not client:
        return []
    
    try:
        models_list = client.models.list()
        models = [f"{prefix}:{model.id}" for model in models_list]
        logger.info("Found %s compatible models: %s", prefix, [m.split(':')[-1] for m in models])
        return models
    except Exception as e:
        logger.warning(f"Failed to get {prefix} model list: {e}. Please check API Key and Base URL.")
        return []

def get_all_models() -> List[str]:
    """
    合并所有来源的模型，构建一个统一的、带前缀的模型名称列表。

    Returns:
        List[str]: 所有可用模型的完整列表。
    """
    all_models = []
    all_models.extend(get_openai_compatible_models(openai_client, "Cloud"))
    all_models.extend(get_openai_compatible_models(genstudio_client, "GenStudio"))
    all_models.extend(get_ollama_models())
    
    if not all_models:
        logger.error("No models found from any provider. The application may not function correctly.")
    
    return all_models

# --- 名称处理工具函数 ---

def infer_provider_from_model(prefixed_model_name: str) -> str:
    """
    根据模型名称的前缀 ('Ollama:', 'Cloud:', 'GenStudio:') 推断出提供商。

    Args:
        prefixed_model_name (str): 带有前缀的完整模型名称。

    Returns:
        str: 小写的提供商名称 ('ollama', 'openai', 'genstudio')。
    """
    name_lower = prefixed_model_name.lower()
    if name_lower.startswith("ollama:"):
        return "ollama"
    if name_lower.startswith("cloud:"):
        return "openai" # Cloud 使用标准的 'openai' provider
    if name_lower.startswith("genstudio:"):
        return "genstudio"
    
    # 如果没有匹配的前缀，根据经验回退到 ollama
    logger.debug(f"Could not infer provider from '{prefixed_model_name}'. Falling back to 'ollama'.")
    return "ollama"

def extract_model_name(prefixed_model_name: str) -> str:
    """
    从带有前缀的模型名称中提取出纯净的模型 ID，用于 API 调用。

    Args:
        prefixed_model_name (str): 带有前缀的完整模型名称。

    Returns:
        str: 不含前缀的纯模型名称。
    """
    if ':' in prefixed_model_name:
        return prefixed_model_name.split(':', 1)[1]
    return prefixed_model_name