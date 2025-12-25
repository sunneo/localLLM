import os

# ================= 配置區 (RPi 3B 記憶體最小化) =================
LLAMA_BIN = "./llama.bin/llama-completion" 
MODELS = {
    "architect": "./models/qwen2.5-0.5b-instruct-q8_0.gguf",
    "chatter": "./models/qwen2.5-0.5b-instruct-q8_0.gguf",
    "coder": "./models/qwen2.5-coder-1.5b-instruct-q8_0.gguf" 
}
STATE_FILE = "pi_ai_state.json"


# 確保模型路徑存在，若不存在則提示（不中斷程式以利除錯）
def check_config():
    if not os.path.exists(LLAMA_BIN):
        print(f"[-] Warning: 找不到執行檔 {LLAMA_BIN}")
    for key, path in MODELS.items():
        if not os.path.exists(path):
            print(f"[-] Warning: 模型檔案不存在: {path}")

if __name__ == "__main__":
    check_config()
