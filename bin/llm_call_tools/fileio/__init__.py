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
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            start = text.find('{')
            end = text.rfind('}')
            if start != -1:
                if end != -1 and end > start:
                    return json.loads(text[start:end+1])
                else:
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


def repair_and_parse_json(raw_text):
    """
    針對小模型生成的截斷 JSON 進行修復。
    如果是長代碼任務，模型可能在 JSON 結束前就斷掉。
    """
    text = raw_text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 嘗試尋找並修補 JSON 結構
        match = re.search(r'\{.*\}', text, re.S)
        if match:
            try: return json.loads(match.group(0))
            except: pass
        # 如果是截斷的字串內容，嘗試暴力閉合
        if text.startswith('{') and '"code":' in text:
            try: return json.loads(text + '"}')
            except: pass
    return None

@register_ai_tool(
   "write_code",
   "根據需求生成完整的程式碼檔案。參數：task_description (需求描述), filename (建議檔名)",
   tags=["code", "writer"]
)
def handle_write_code(p, sys_inst):
    task = p.get("task_description", sys_inst.context)
    fname = p.get("filename", "generated_code.txt")
    
    # 策略：高效能環境下移除 Schema 限制
    sys_msg = (
        "你是一個專業工程師。請直接輸出完整的程式碼。"
        "請將程式碼包裹在 Markdown 程式碼塊中。"
        "不要解釋、不要引言、不要結語，只輸出程式碼內容。"
    )
    
    prompt = f"請實作以下功能並提供完整、可執行的代碼：\n{task}"
    
    print(f"[*] 正在生成代碼 {fname} (高效能模式，上限 4096 tokens)...")
    
    # 呼叫 LLM
    raw_res = sys_inst.call_llm("coder", prompt, system_prompt=sys_msg, n_tokens=4096, temp=0.2)
    
    code = ""
    
    # --- 關鍵修正：使用字串拼接避免渲染器中斷 ---
    # 這裡將 ``` 分開寫成 "`" * 3，防止 Canvas 的 Markdown 渲染器誤判結束
    backticks = "`" * 3
    pattern = backticks + r'(?:\w+)?\n?(.*?)' + backticks
    
    # 邏輯 A：尋找 Markdown 區塊
    code_blocks = re.findall(pattern, raw_res, re.DOTALL)
    if code_blocks:
        code = max(code_blocks, key=len).strip()
    
    # 邏輯 B：JSON 備援
    if not code:
        data = repair_and_parse_json(raw_res)
        if data and isinstance(data, dict) and "code" in data:
            code = data["code"]
            
    # 邏輯 C：純文字清理保底
    if not code:
        code = re.sub(r'^{\s*"code":\s*"|",\s*"filename":.*}$', '', raw_res, flags=re.DOTALL).strip()
        code = code.strip('"` \n')

    if len(code) > 10:
        # 自動判定副檔名
        final_fname = fname
        if final_fname == "generated_code.txt":
            low_c = code.lower()
            if "import " in low_c or "def " in low_c: final_fname = "script.py"
            elif "#include" in low_c: final_fname = "program.c"
            elif "fn main" in low_c: final_fname = "main.rs"

        with open(final_fname, "w", encoding="utf-8") as f:
            f.write(code)
            
        preview = code[:100].replace('\n', ' ')
        return f"【代碼生成成功】已寫入至 {final_fname} (共 {len(code)} 字元)。\n預覽：{preview}..."
    else:
        # 失敗紀錄
        with open("error_raw_output.txt", "w", encoding="utf-8") as f:
            f.write(raw_res)
        return f"[-] 錯誤：代碼提取失敗。原始內容已存至 error_raw_output.txt。"

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

