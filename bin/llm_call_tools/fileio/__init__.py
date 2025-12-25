import os
import sys
import json
import re
from ..common import register_ai_tool
def get_possible_request(p,sys_inst,possibleKeys={}):
    content=""
    if sys_inst.context:
       content=sys_inst.context
    else:
       otherKeys=""
       for k,v in p.items():
          if k in possibleKeys:
             content=p.get(k,'')
             break
          else:
             otherKeys=k
       if not content:
          content=p.get(otherKeys,'')
    return content

def repair_and_parse_json(raw_text):
    """
    針對小模型生成的截斷或損毀 JSON 進行修復與解析
    """
    text = raw_text.strip()
    try:
        # 嘗試直接解析
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            # 嘗試尋找最外層的 JSON 結構
            start = text.find('{')
            end = text.rfind('}')
            if start != -1:
                if end != -1 and end > start:
                    return json.loads(text[start:end+1])
                else:
                    # 只有開頭，嘗試手動閉合
                    return json.loads(text[start:] + '"}')
        except:
            pass
    return None

# --- 工具定義區 ---

@register_ai_tool(
   "text_reader",
   "單純讀取檔案作為系統Context，如果有工具的目標是讀取文字，但分析的內容還沒載入，應優先執行text_reader",
   ['reader','text']
)
def handle_text_reader(p: dict, sys_inst):
    """讀取檔案內容並存入系統 Context"""
    print(f'dump={json.dumps(p)}')
    possibleKeys={"file_path", "filename", "target", "file"}
    fname = get_possible_request(p,sys_inst,possibleKeys)
    if not fname:
        return "[-] 錯誤: text_reader 缺少檔案路徑。"

    if os.path.exists(fname):
        try:
            with open(fname, 'r', encoding='utf-8') as f:
                content = f.read()
                sys_inst.context = content
            return f"【讀取成功】檔案: {fname} (共 {len(content)} 字元)，內容已載入背景 Context。"
        except Exception as e:
            return f"【讀取失敗】讀取過程發生錯誤: {str(e)}"
    return f"【讀取失敗】找不到檔案: {fname}"

@register_ai_tool(
    "code_analyzer",
    "分析程式邏輯，code_analyzer的輸入只能是程式內容，如果是檔案請優先跑過text_reader",
    ["analyzer","source","code"]
)
def handle_code_analyzer(p: dict, sys_inst):
    """分析 Context 中的代碼邏輯"""
    print(f'dump={json.dumps(p)}')
    possibleKeys={"code","content","topic"}
    content=get_possible_request(p,sys_inst,possibleKeys)
    if not content:
        return "[-] 錯誤: 無可供分析的代碼內容。"

    prompt = f"請專業地分析以下代碼邏輯，並指出潛在問題或關鍵點：\n\n{content}"
    sys_msg = "你是一個資深工程師，請用繁體中文提供簡潔且具備技術深度的分析。"
    analysis = sys_inst.call_llm("coder", prompt, system_prompt=sys_msg)
    return f"【代碼分析結果】\n{analysis}"


@register_ai_tool(
    "write_code",
    "當訊息提到**寫*程式*，都要用這個，這主要用來處理程式撰寫需求，提到寫什麼程式都要用write_code",
    ["codegen","write","programming"]
)
def handle_write_code(p: dict, sys_inst):
    """根據需求生成代碼並儲存至檔案"""
    desc = p.get('task_description') or "撰寫程式碼"
    # 整合背景 Context
    context_prefix = f"背景資訊:\n{sys_inst.context}\n\n" if sys_inst.context else ""
    prompt = f"{context_prefix}任務需求: {desc}"

    # 強制 Schema
    schema = {
        "type": "object",
        "properties": {
            "code": {"type": "string"},
            "filename": {"type": "string"}
        },
        "required": ["code"]
    }

    sys_msg = "你是一個專業工程師。必須嚴格輸出 JSON。'code' 欄位放置程式碼，'filename' 放置建議檔名。"
    raw_res = sys_inst.call_llm("coder", prompt, system_prompt=sys_msg, schema=schema)

    # 嘗試解析
    data = repair_and_parse_json(raw_res)
    
    if data and "code" in data:
        code = data["code"]
        fname = data.get("filename") or "generated_code.txt"
        with open(fname, "w", encoding="utf-8") as f:
            f.write(code)
        return f"【代碼生成成功】已寫入至 {fname}。\n預覽：\n{code[:60]}..."
    else:
        # 保底方案：如果解析失敗但有足夠長度的文字，嘗試提取代碼
        if len(raw_res) > 30:
            # 嘗試過濾掉 JSON 殘骸，提取引號內的內容或直接存檔
            clean_code = re.sub(r'^{\s*"code":\s*"|",\s*"filename":.*}$', '', raw_res, flags=re.DOTALL)
            fallback_name = "fallback_code.txt"
            with open(fallback_name, "w", encoding="utf-8") as f:
                f.write(clean_code)
            return f"【警告：格式異常】JSON 解析失敗，已啟動保底模式存至 {fallback_name}。原始回傳預覽:\n{raw_res[:80]}"
        
        return f"【生成失敗】模型回傳內容過短或無效。原始內容:\n{raw_res}"

@register_ai_tool(
   "chatter",
   "這是最後的選項，用來回應聊天",
   ["chat"]
)
def handle_chatter(p: dict, sys_inst):
    """聊天"""
    #print(f'dump={json.dumps(p)}')
    possibleKeys={"text","topic"}
    content=get_possible_request(p,sys_inst,possibleKeys)
    if not content:
        return "[-] 錯誤: 無內容。"

    prompt = f"{content}"
    sys_msg = "你是一個資深工程師，請用繁體中文提供對話內容。你絕對不會回應口水，不會無限的重複"
    res = sys_inst.call_llm("chatter", prompt, system_prompt=sys_msg)
    return f"{res}"

