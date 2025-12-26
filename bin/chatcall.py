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
    get_weighted_tool_prompts,
    get_tool_prompts
)

# --- 強化學習與 RAG 整合區 ---
try:
    from rag_tool import (
        rag_query_knowledge, 
        rag_store_knowledge,
        rag_calculate_engagement,
        rag_record_engagement_feedback,
        rag_query_failures,
        rag_store_failure_feedback,
        rag_record_user_feedback
    )
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False

RAG_FORCE_KEYWORDS = ["100分", "幫我加入rag", "幫我記下來", "好極了, 這必須記下來"]
RAG_FAILURE_KEYWORDS = ["失敗", "錯誤", "不滿", "爛", "不行", "不對", "不滿意"]
RAG_ENGAGEMENT_THRESHOLD = 2.0

def adjust_tool_selection_and_tags(rag_result, tags):
    # 6. 根據RAG查詢結果的權重，調整工具選擇與tag參數
    if rag_result.get('results'):
        # 取最高分的RAG結果，若其metadata有推薦tag則優先加入
        best = rag_result['results'][0]
        if 'metadata' in best and 'tools_used' in best['metadata']:
            try:
                tags_from_rag = json.loads(best['metadata']['tools_used'])
                if isinstance(tags_from_rag, list):
                    tags = list(set(tags + tags_from_rag))
            except Exception:
                pass
    return tags

# --- 主系統類別 ---

class PiAiRelaySystem:
    def __init__(self):
        self.context = ""
        self.history = self.load_history()
        self.todo_list = ""
        self.current_theme = ""
        
        # 動態獲取工具名清單
        self.available_tools = get_tool_names()
        
        # 定義架構師 Schema
        self.architect_schema = {
            "type": "object",
            "properties": {
                "theme": {"type": "string", "description": "核心主題"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "tasks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "tool": {"type": "string", "enum": self.available_tools},
                            "params": {"type": "object", "additionalProperties": True}
                        },
                        "required": ["tool", "params"]
                    }
                },
                "remaining_plan": {"type": "string", "description": "後續步驟描述"}
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

    def repair_json(self, raw_text):
        """嘗試修復截斷的 JSON"""
        text = raw_text.strip()
        # 移除 markdown 標籤
        text = re.sub(r'^```json\s*|\s*```$', '', text, flags=re.MULTILINE)
        
        # 補齊括號
        open_braces = text.count('{') - text.count('}')
        open_brackets = text.count('[') - text.count(']')
        if open_braces > 0: text += '}' * open_braces
        if open_brackets > 0: text += ']' * open_brackets
        
        try:
            return json.loads(text)
        except:
            # 嘗試找最後一個完整的對象
            match = re.search(r'(\{.*?\})', text, re.S)
            if match:
                try: return json.loads(match.group(1))
                except: return None
        return None

    def strip_noise(self, text):
        #print(f'原始文字:\n{text}')
        noise_markers = ["<|im_start|>", "<|im_end|>", "[end of text]"]
        lines = text.splitlines()
        clean_lines = []
        for line in lines:
           for tag in noise_markers:
              line=line.replace(tag,"")
           clean_lines.append(line)
        result = "\n".join(clean_lines).strip()
        #print(f'清理後原始文字:\n{result}')

        return result

    def call_llm(self, model_key, prompt, system_prompt=None, n_tokens=8192, temp=0.1, schema=None):
        model_path = MODELS.get(model_key)
        if not model_path or not os.path.exists(model_path):
            return f"Error: 找不到模型檔案 {model_path}"
        subprocess.run(["pkill", "-9", "llama-completion"], stderr=subprocess.DEVNULL)
        cmd = [
            LLAMA_BIN, "-m", model_path, "-st", "--no-display-prompt", "--simple-io",
            "--temp", str(temp), "-n", str(n_tokens), "-p", prompt
#            ,"--ctx-size",str(32768)
        ]
        if system_prompt: cmd.extend(["-sys", system_prompt])
        if schema: cmd.extend(["-j", json.dumps(schema)])
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=180)
            return self.strip_noise(result.stdout)
        except Exception as e:
            return f"Error: {str(e)}"

    def run_relay(self, user_input, is_continuation=False):
        # 1. 預選標籤 (保底用)
        possible_tags = ["c", "python", "file", "code", "reader", "writer", "analyze"]
        suggested = [t for t in possible_tags if t in user_input.lower()]

        next_input = user_input
        continuation = is_continuation
        while True:
            # 1. RAG查詢，將相關知識納入 context
            rag_context = ""
            rag_result = {"results": []}
            if RAG_AVAILABLE:
                rag_result = json.loads(rag_query_knowledge(next_input, n_results=3))
                rag_context = "\n".join([r['content'] for r in rag_result.get('results', [])]) if rag_result.get('results') else ""
            if rag_context:
                self.context = f"[RAG知識]\n{rag_context}\n" + self.context

            # 2. 查詢失敗經驗，納入 context
            fail_context = ""
            if RAG_AVAILABLE:
                rag_fail = json.loads(rag_query_failures(next_input, n_results=2))
                fail_context = "\n".join([f"失敗經驗: {r['failed_approach']}\n修正: {r['solution']}" for r in rag_fail.get('results', [])]) if rag_fail.get('results') else ""
            if fail_context:
                self.context += f"\n[失敗經驗]\n{fail_context}"

            # 2. 獲取工具描述
            tools_description = get_weighted_tool_prompts(suggested)

            architect_sys = f"""你是一個任務架構師。
請根據用戶需求規劃工具調用序列。

**可用工具清單：**
{tools_description}

**要求：**
1. 必須輸出 JSON。
2. 'tags' 必須包含對應工具的標籤。
3. 如果只是打招呼，請文字回答。"""

            print(f"[*] {'[接力中]' if continuation else '[規劃中]'} 分析任務...", flush=True)
            raw_res = self.call_llm("architect", next_input, system_prompt=architect_sys, schema=self.architect_schema)

            # 3. 解析與修復
            plan_data = self.repair_json(raw_res)
            is_tool_call = False

            if plan_data and isinstance(plan_data, dict) and "tasks" in plan_data:
                is_tool_call = True
            else:
                # --- 強制執行路徑：使用動態工具名比對 ---
                for tool_name in self.available_tools:
                    if tool_name in raw_res:
                        print(f"[!] 偵測到毀損 JSON 但包含工具關鍵字 '{tool_name}'，嘗試自動構造任務...")
                        plan_data = {
                            "theme": "自動復原任務",
                            "tags": suggested,
                            "tasks": [{"tool": tool_name, "params": {"task_description": next_input}}]
                        }
                        is_tool_call = True
                        break

            if not is_tool_call:
                print("[*] 進入對話模式。")
                self.history.append({"role": "user", "content": next_input})
                self.history.append({"role": "assistant", "content": raw_res})
                self.save_history()
                print(f"\n>> {raw_res}")
                return True

            # 4. 提取資訊並執行
            self.current_theme = plan_data.get("theme", "任務處理")
            tasks = plan_data.get("tasks", [])
            tags = plan_data.get("tags", suggested if not plan_data.get("tags") else plan_data.get("tags"))

            # RAG動態調整tags
            tags = adjust_tool_selection_and_tags(rag_result, tags)

            print(f"[*] 主題: {self.current_theme} | 標籤: {tags}")

            results = []
            for i, task in enumerate(tasks):
                name = task.get("tool")
                params = task.get("params", {})
                if name not in self.available_tools: continue

                print(f"\n[步驟 {i+1}] 執行: {name}")
                res = execute_tool(name, params, self)
                results.append(res)
                print(f" >> {res}")

            # 互動參與度計算
            engagement_score = 0
            follow_up_count = 0
            context_tokens_added = 0
            question_depth = 0
            if RAG_AVAILABLE and results:
                engagement_json = rag_calculate_engagement(len(self.history)-1, self.history, results[-1])
                engagement_data = json.loads(engagement_json).get('engagement_analysis', {}) if engagement_json else {}
                engagement_score = engagement_data.get('engagement_score', 0)
                follow_up_count = engagement_data.get('follow_up_count', 0)
                context_tokens_added = engagement_data.get('context_tokens_added', 0)
                question_depth = engagement_data.get('question_depth', 0)

            task_success = True
            force_rag = any(kw in next_input for kw in RAG_FORCE_KEYWORDS)
            failure_rag = any(kw in next_input for kw in RAG_FAILURE_KEYWORDS)

            if RAG_AVAILABLE and task_success and (engagement_score >= RAG_ENGAGEMENT_THRESHOLD or force_rag):
                rag_store_knowledge(
                    task_description=next_input,
                    solution=results[-1] if results else "",
                    task_type=self.current_theme,
                    tools_used=[t.get('tool') for t in tasks],
                    success_metrics={
                        "engagement_score": engagement_score,
                        "follow_up_count": follow_up_count,
                        "context_tokens_added": context_tokens_added,
                        "question_depth": question_depth
                    }
                )

            if RAG_AVAILABLE and failure_rag:
                rag_store_failure_feedback(
                    task_description=next_input,
                    failed_approach=results[-1] if results else "",
                    error_message="user negative feedback",
                    correct_solution="(待補充)"
                )

            # 5. 判斷接力
            next_step = plan_data.get("remaining_plan", "")
            if next_step and len(next_step.strip()) > 10 and not continuation:
                self.todo_list = next_step
                next_input = f"繼續執行：{next_step}"
                continuation = True
                continue
            else:
                self.history.append({"role": "user", "content": next_input})
                self.history.append({"role": "assistant", "content": f"【{self.current_theme}】執行完畢。"})
                self.save_history()
                break
        return True

if __name__ == "__main__":
    relay = PiAiRelaySystem()
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else input("需求 > ")
    if query: relay.run_relay(query)
