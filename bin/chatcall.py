import subprocess
import json
import sys
import os
import re
import time
from ai_config import LLAMA_BIN, MODELS, STATE_FILE
from llm_call_tools.common import TOOLS_LIST, register_ai_tool, execute_tool, get_tool_names, get_tool_prompts

# --- 強化學習與 RAG 整合區 ---
try:
    from rag_tool import (
        rag_query_knowledge, 
        rag_store_knowledge,
        rag_calculate_engagement,
        rag_record_engagement_feedback
    )
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False

# --- 主系統類別 ---

class PiAiRelaySystem:
    def __init__(self):
        self.context = ""
        self.history = self.load_history()
        # 動態生成架構師所需的 Schema (從 common.py 取得已註冊工具)
        self.architect_schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tool": {"type": "string", "enum": get_tool_names()},
                    "params": {"type": "object", "additionalProperties": True}
                },
                "required": ["tool", "params"]
            }
        }

    def load_history(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except: pass
        return []

    def save_history(self):
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.history[-20:], f, ensure_ascii=False, indent=2)

    def strip_noise(self, text):
        noise_markers = ["load_tensors:", "llama_", "main:", "build:", "repeat_last_n", "dry_multiplier"]
        lines = text.splitlines()
        clean_lines = [line for line in lines if not any(m in line for m in noise_markers)]
        return "\n".join(clean_lines).strip()

    def call_llm(self, model_key, prompt, system_prompt=None, n_tokens=512, temp=0.1, schema=None):
        model_path = MODELS.get(model_key)
        if not model_path or not os.path.exists(model_path):
            return f"Error: 找不到模型檔案 {model_path}"

        subprocess.run(["pkill", "-9", "llama-completion"], stderr=subprocess.DEVNULL)
        
        cmd = [
            LLAMA_BIN, 
            "-m", model_path, 
            "-st",                 
            "--no-display-prompt", 
            "--simple-io",
            "--temp", str(temp),
            "-n", str(n_tokens),
            "-p", prompt           
        ]
        if system_prompt: cmd.extend(["-sys", system_prompt])
        if schema: cmd.extend(["-j", json.dumps(schema)])
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=180)
            output = self.strip_noise(result.stdout)
            for tag in ["assistant", "<|im_start|>", "<|im_end|>", "[end of text]", "Assistant:", "User:"]:
                output = output.replace(tag, "")
            return output.strip()
        except Exception as e:
            return f"Error: {str(e)}"

    def process_learning_phase(self, user_input):
        """利用 RAG 判斷是否需要學習紀錄"""
        if not RAG_AVAILABLE: return False
        # 這裡可以根據 user_input 內容決定是否觸發紀錄
        return False

    def run_relay(self, user_input):
        # 1. 學習階段判斷
        if self.process_learning_phase(user_input):
            self.history.append({"role": "user", "content": user_input})
            self.history.append({"role": "assistant", "content": "已記錄相關知識點。"})
            self.save_history()
            return True

        # 2. 準備工具說明 (從 common.py 獲取已註冊的 prompts)
        tool_prompts = get_tool_prompts()
        tools_description = ""
        for name in get_tool_names():
            desc = tool_prompts.get(name, "執行該工具指定的任務。")
            tools_description += f"- {name}: {desc}\n"

        # 3. 架構師規劃
        print(f"[*] 【架構師】正在規劃任務...", flush=True)
        
        architect_sys = f"""你是一個專業的任務規劃架構師。
根據使用者的需求，判斷是否需要呼叫工具。

可用工具說明：
{tools_description}

**規則：**
1. 如果需求可透過工具完成，請務必輸出 JSON 陣列格式，例如：[{{"tool": "工具名", "params": {{...}}}}]。
2. 如果只是純粹聊天、打招呼、或無對應工具，請直接以自然語言回覆，不要輸出 JSON。
3. 輸出必須簡潔。"""

        raw_plan = self.call_llm("architect", user_input, system_prompt=architect_sys, schema=self.architect_schema)
        
        # 4. 解析規劃：判斷是 Tool Call 還是 Chatter
        tasks = []
        is_tool_call = False
        try:
            # 尋找 JSON 陣列特徵
            json_match = re.search(r'\[.*\]', raw_plan, re.S)
            if json_match:
                tasks = json.loads(json_match.group(0))
                if isinstance(tasks, list) and len(tasks) > 0:
                    is_tool_call = True
        except:
            is_tool_call = False

        if not is_tool_call:
            # --- 轉交為 Chatter 邏輯 ---
            print("[*] 無對應工具或模型選擇對話。")
            self.history.append({"role": "user", "content": user_input})
            self.history.append({"role": "assistant", "content": raw_plan})
            self.save_history()
            print(f"\n>> {raw_plan}")
            return True

        # 5. 順序執行工具
        print(f"[*] 執行清單：{len(tasks)} 個任務。")
        results = []
        for i, task in enumerate(tasks):
            name = task.get("tool")
            params = task.get("params", {})
            print(f"\n[任務 {i+1}] 執行: {name}")
            
            res = execute_tool(name, params, self)
            results.append(res)
            print(f" >> {res}")

        # 6. 更新歷史
        self.history.append({"role": "user", "content": user_input})
        self.history.append({"role": "assistant", "content": "\n".join(results)})
        self.save_history()
        return True
if __name__ == "__main__":
    relay = PiAiRelaySystem()
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else input("需求 > ")
    if query: relay.run_relay(query)
