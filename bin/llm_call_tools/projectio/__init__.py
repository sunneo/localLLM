import os
import re
from ..common import register_ai_tool

@register_ai_tool(
    "project_reader",
    "讀取專案目錄結構或檔案內容，支援 path 參數指定目錄或檔案。",
    ["project", "reader", "file"]
)
def handle_project_reader(params, sys_inst):
    path = params.get("path", ".")
    max_lines = int(params.get("max_lines", 50))
    if os.path.isdir(path):
        tree = []
        for root, dirs, files in os.walk(path):
            level = root.replace(path, '').count(os.sep)
            indent = '    ' * level
            tree.append(f"{indent}{os.path.basename(root)}/")
            subindent = '    ' * (level + 1)
            for f in files:
                tree.append(f"{subindent}{f}")
        return "\n".join(tree)
    elif os.path.isfile(path):
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            preview = ''.join(lines[:max_lines])
        return f"【檔案預覽】{path}\n{preview}"
    else:
        return f"[-] project_reader: 找不到路徑 {path}"

@register_ai_tool(
    "code_searcher",
    "根據關鍵字搜尋程式片段，支援 file 與 keyword 參數。",
    ["search", "code", "project"]
)
def handle_code_searcher(params, sys_inst):
    file = params.get("file")
    keyword = params.get("keyword")
    if not file or not keyword:
        return "[-] code_searcher: 缺少 file 或 keyword 參數。"
    if not os.path.isfile(file):
        return f"[-] code_searcher: 找不到檔案 {file}"
    with open(file, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    # 搜尋所有包含 keyword 的程式片段（以函式/類別為單位）
    pattern = rf"(^.*{re.escape(keyword)}.*$[\s\S]*?^\s*$)"  # 簡易分段
    matches = re.findall(pattern, content, re.MULTILINE)
    if matches:
        return f"【搜尋結果】共 {len(matches)} 段\n" + "\n---\n".join(matches)
    # 若無分段，回傳所有包含 keyword 的行
    lines = [line for line in content.splitlines() if keyword in line]
    if lines:
        return f"【搜尋結果】共 {len(lines)} 行\n" + "\n".join(lines)
    return f"[-] code_searcher: 未找到關鍵字 {keyword}"

@register_ai_tool(
    "code_modifier",
    "根據需求自動修改程式碼，支援 file 與 instruction 參數。",
    ["modify", "code", "project"]
)
def handle_code_modifier(params, sys_inst):
    file = params.get("file")
    instruction = params.get("instruction")
    if not file or not instruction:
        return "[-] code_modifier: 缺少 file 或 instruction 參數。"
    if not os.path.isfile(file):
        return f"[-] code_modifier: 找不到檔案 {file}"
    with open(file, 'r', encoding='utf-8', errors='ignore') as f:
        original_code = f.read()
    prompt = f"請根據以下需求修改程式碼：\n需求：{instruction}\n原始程式碼：\n{original_code}\n請直接輸出修改後完整程式碼，不要解釋。"
    sys_msg = "你是一個專業工程師，請直接輸出修改後完整程式碼。"
    new_code = sys_inst.call_llm("coder", prompt, system_prompt=sys_msg, n_tokens=4096, temp=0.2)
    # 嘗試提取 code block
    code = new_code
    match = re.search(r'```(?:\w+)?\n([\s\S]+?)```', new_code)
    if match:
        code = match.group(1).strip()
    if len(code) < 10:
        return f"[-] code_modifier: LLM 未產生有效程式碼。原始回應：\n{new_code}"
    with open(file, 'w', encoding='utf-8') as f:
        f.write(code)
    preview = code[:100].replace('\n', ' ')
    return f"【程式碼修改成功】已寫入至 {file}。預覽：{preview}..."
