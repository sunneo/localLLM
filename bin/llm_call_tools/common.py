import json
from typing import Dict, Any, Callable, List, Optional

# 擴展工具字典，包含描述與標籤
TOOLS_LIST: Dict[str, Callable] = {}
TOOLS_PROMPT: Dict[str, str] = {}
TOOLS_TAGS: Dict[str, List[str]] = {} # 新增：存放工具的標籤

def register_ai_tool(name: str, prompt: Optional[str] = None, tags: Optional[List[str]] = None):
    """
    擴展版裝飾器：註冊 AI 工具
    :param tags: 該工具擅長的領域，如 ["file", "analysis", "rag"]
    """
    def decorator(func: Callable):
        TOOLS_LIST[name] = func
        if prompt:
            TOOLS_PROMPT[name] = prompt
        TOOLS_TAGS[name] = tags if tags else []
        return func
    return decorator

def get_weighted_tool_prompts(query_tags: List[str] = None) -> str:
    """
    根據查詢標籤動態生成加權後的工具說明
    """
    output = ""
    for name, prompt in TOOLS_PROMPT.items():
        weight_mark = ""
        # 如果 query 包含工具標籤，加上星星符號引導模型
        if query_tags and any(t in query_tags for t in TOOLS_TAGS.get(name, [])):
            weight_mark = " [推薦優先使用]"
        output += f"- {name}{weight_mark}: {prompt}\n"
    return output

def get_tool_names() -> List[str]:
    return list(TOOLS_LIST.keys())

def get_tool_prompts():
    return TOOLS_PROMPT

def execute_tool(name: str, params: Dict[str, Any], context_obj: Any):
    if name in TOOLS_LIST:
        return TOOLS_LIST[name](params, context_obj)
    return f"[-] 錯誤: 工具 '{name}' 尚未註冊。"
