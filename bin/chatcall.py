import subprocess
import json
import sys
import os
import re
import time
from ai_config import LLAMA_BIN, MODELS, STATE_FILE
from llm_call_tools.common import (
    TOOLS_LIST, 
    execute_tool, 
    get_tool_names, 
    get_weighted_tool_prompts
)

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
        self.todo_list = ""          # 存放剩餘任務描述 (接力用)
        self.current_theme = ""      # 當前任務主題
        
        # 強化的 Schema：要求模型輸出主題、標籤、任務陣列以及剩餘計畫
        # 這能有效防止小模型在執行長任務時邏輯崩潰
        self.architect_schema = {
            "type": "object",
            "properties": {
                "theme": {"type": "string", "description": "本次任務的核心主題關鍵字"},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "相關技術標籤"},
                "tasks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "tool": {"type": "string", "enum": get_tool_names()},
                            "params": {"type": "object", "additionalProperties": True}
                        },
                        "required": ["tool", "params"]
                    }
                },
                "remaining_plan": {"type": "string", "description": "若任務步數過長，請在此描述接下來還需做的步驟，以便接力執行"}
            },
            "required": ["theme", "tasks"]
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
            json.dump(self.history[-15:], f, ensure_ascii=False, indent=2)

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

    def run_relay(self, user_input, is_continuation=False):
        """
        核心執行邏輯：支援主題鎖定、權重引導與自動接力
        """
        # 1. 預處理：嘗試獲取引導標籤 (可結合 RAG)
        suggested_tags = []
        if RAG_AVAILABLE:
            # 簡單正則提取潛在關鍵字作為標籤來源
            potential_keywords = re.findall(r'\b(python|c|cpp|file|read|write|analyze|debug)\b', user_input.lower())
            suggested_tags = list(set(potential_keywords))

        # 2. 獲取動態加權後的工具描述 (由 common.py 提供)
        tools_description = get_weighted_tool_prompts(suggested_tags)

        # 3. 構建 System Prompt (注入接力狀態與權重)
        status_msg = ""
        if is_continuation:
            status_msg = f"\n[接力狀態]: 正在執行任務 '{self.current_theme}' 的續接步驟。剩餘進度描述: {self.todo_list}"

        architect_sys = f"""你是一個專業的任務規劃架構師。
請根據使用者的需求與目前狀態，判斷應執行的工具序列。

**可用工具說明 (含推薦權重標記)：**
{tools_description}
{status_msg}

**執行規範：**
1. 必須輸出 JSON 格式。
2. 若任務複雜，請規劃當前最緊急的 1~3 步，並在 'remaining_plan' 描述後續工作。
3. 若不需要工具（單純對話），請直接以自然語言回答，不要輸出 JSON（觸發 Chatter 保底）。
4. 'theme' 應設定為任務的核心主題，'tags' 應包含相關技術關鍵字。"""

        print(f"[*] {'[接力中]' if is_continuation else '[規劃中]'} 正在分析任務主題...", flush=True)
        raw_res = self.call_llm("architect", user_input, system_prompt=architect_sys, schema=self.architect_schema)
        
        # 4. 解析規劃與 Chatter 保底
        plan_data = None
        is_tool_call = False
        try:
            # 尋找 JSON 特徵
            json_match = re.search(r'\{.*\}', raw_res, re.S)
            if json_match:
                plan_data = json.loads(json_match.group(0))
                if "tasks" in plan_data and len(plan_data["tasks"]) > 0:
                    is_tool_call = True
        except:
            is_tool_call = False

        if not is_tool_call:
            # --- Chatter 保底邏輯 ---
            print("[*] 偵測到非工具需求，切換至對話模式。")
            self.history.append({"role": "user", "content": user_input})
            self.history.append({"role": "assistant", "content": raw_res})
            self.save_history()
            print(f"\n>> {raw_res}")
            return True

        # 5. 執行當前階段任務
        self.current_theme = plan_data.get("theme", "一般任務")
        tasks = plan_data.get("tasks", [])
        next_step_desc = plan_data.get("remaining_plan", "")
        tags = plan_data.get("tags", [])
        
        print(f"[*] 任務主題: {self.current_theme} | 標籤: {tags}")
        print(f"[*] 執行當前階段 ({len(tasks)} 個任務)...")

        results = []
        for i, task in enumerate(tasks):
            name = task.get("tool")
            params = task.get("params", {})
            print(f"\n[步驟 {i+1}] 呼叫: {name}")
            
            res = execute_tool(name, params, self)
            results.append(res)
            print(f" >> 執行結果: {res}")

        # 6. 接力邏輯判斷 (Recursive Planning)
        if next_step_desc and len(next_step_desc.strip()) > 5:
            self.todo_list = next_step_desc
            print(f"\n[*] 偵測到後續任務需求，啟動自動接力：{next_step_desc}")
            # 彙整執行上下文，讓下一棒有依據
            self.context += f"\n[階段結果] {self.current_theme}: {' '.join(results)}"
            # 遞迴執行下一棒
            return self.run_relay(f"請繼續完成任務 '{self.current_theme}'。後續目標：{next_step_desc}", is_continuation=True)
        else:
            # 任務完成，更新對話歷史
            print("\n[*] 所有階段任務執行完畢。")
            self.history.append({"role": "user", "content": user_input})
            self.history.append({"role": "assistant", "content": f"【主題：{self.current_theme}】任務已成功執行完畢。\n結果彙整：\n" + "\n".join(results)})
            self.save_history()
            self.todo_list = ""
            return True

if __name__ == "__main__":
    relay = PiAiRelaySystem()
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else input("需求 > ")
    if query: relay.run_relay(query)
