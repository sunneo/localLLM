import json
from typing import Dict, Any, Callable, List

# TOOLS_LIST 是一個字典，存放工具名稱與對應的處理函數
# 格式: { "tool_name": function_reference }
TOOLS_LIST: Dict[str, Callable] = {}
TOOLS_PROMPT:Dict[str, str] = {}

def register_ai_tool(name: str,prompt=None):
    """
    裝飾器：註冊 AI 工具到系統中
    :param name: 工具的名稱 (需對應 LLM 輸出的 tool key)
    """
    def decorator(func: Callable):
        TOOLS_LIST[name] = func
        if prompt != None:
            TOOLS_PROMPT[name] = prompt
        return func
    return decorator

def get_tool_prompts()-> Dict[str,str]:
    return TOOLS_PROMPT

def get_tool_names() -> List[str]:
    """取得所有已註冊工具的名稱清單，用於 ARCHITECT_SCHEMA"""
    return list(TOOLS_LIST.keys())

def execute_tool(name: str, params: Dict[str, Any], context_obj: Any):
    """
    執行工具
    :param name: 工具名稱
    :param params: LLM 傳入的參數字典
    :param context_obj: 傳遞 PiAiRelaySystem 的實例 (self)，以便工具讀取/寫入 context
    """
    if name in TOOLS_LIST:
        return TOOLS_LIST[name](params, context_obj)
    return f"[-] 錯誤: 工具 '{name}' 尚未註冊。"
