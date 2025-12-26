# localLLM
small, multiple model LLM front-end

---

## 專案架構

```
bin/
    ai_config.py           # AI模型與狀態設定
    BUILD                  # 建置相關設定
    chatcall.py            # 主系統入口，任務調度與工具調用
    create-sub-chat.sh     # 建立子聊天腳本
    pi_ai_state.json       # 任務/對話歷史狀態
    README                 # bin 資料夾說明
    llama.bin/             # LLM 執行檔與動態連結庫
        libggml-*.so       # GGML 相關動態庫
        libllama.so*       # Llama 相關動態庫
        libmtmd.so*        # MTMD 相關動態庫
        llama-cli          # Llama 命令列工具
        llama-completion   # Llama 補全工具
        llama-server       # Llama 伺服器
    llm_call_tools/        # 工具調用模組
        __init__.py
        common.py          # 工具清單、執行邏輯
        fileio/            # 檔案讀寫相關工具
            __init__.py
    models/                # LLM 模型檔案（Qwen2.5 系列）
    rag_data/              # RAG 相關資料庫
        chroma.sqlite3     # Chroma 向量資料庫
    rag_tool/              # RAG 工具模組
        __init__.py
        engagement_scorer.py # 互動評分工具
        README.md
    user_profiles/         # 使用者個人化資料
        hungfu.lee/
            1766580096/
                llama.bin
                llm_call_tool
                models
                rag_data
                ai_config.py
                chatcall.py
                create-sub-chat.sh
                addons
                ai_config_common.py
                add.js
                hi.js
                override_ai_config.py
                pi_ai_state.json
```

## 架構說明

- **bin/**：主要執行檔、腳本與系統入口，包含所有核心 Python 腳本與 Shell 工具。
- **chatcall.py**：本專案主程式，負責任務規劃、工具調度、與 LLM 互動。其功能包含：
  - 根據用戶需求自動規劃任務流程（支援多工具串接）。
  - 動態選擇可用工具，並根據需求自動修復/解析 JSON 任務規劃。
  - 整合 RAG（檢索增強生成）模組，支援知識查詢、儲存、互動評分。
  - 管理對話歷史與狀態，支援多輪任務接力。
  - 以架構師 Schema 驅動任務規劃，確保工具調用流程結構化。
- **llama.bin/**：本地 LLM 執行檔與相關動態連結庫，支援多模型推論。
- **llm_call_tools/**：工具調用模組，包含工具清單、執行邏輯與檔案操作工具。
- **models/**：LLM 模型檔案（如 Qwen2.5 系列），供推論使用。
- **rag_data/**、**rag_tool/**：RAG 相關資料庫與工具模組，支援知識檢索、互動評分等。
- **user_profiles/**：使用者個人化資料與設定，支援多使用者環境。

---

## chatcall.py 主要功能說明

`chatcall.py` 是本專案的主程式，負責整合本地 LLM 與多工具調度，核心功能如下：

- **任務規劃**：根據用戶輸入，動態分析需求，規劃工具調用序列。
- **工具調用**：自動選擇並執行合適的工具，支援多步驟任務串接。
- **RAG 整合**：可選用 RAG 工具進行知識查詢、儲存與互動評分。
- **對話管理**：保存對話與任務歷史，支援多輪任務接力。
- **自動修復**：遇到不完整或毀損的 JSON 任務規劃時，能自動修復並執行。
- **架構師 Schema**：以結構化 Schema 驅動任務規劃，確保工具調用流程清晰。

本專案適合用於本地多模型 LLM 前端，支援多工具協作、RAG 增強、互動評分等多種 AI 任務，並可根據需求擴充工具與模型。

---

## 架構設計理念

本專案設計讓 chatcall.py 僅作為「核心任務調度器」，所有實際功能（如讀取檔案、搜尋程式、修改程式等）都由 llm_call_tools 內的工具模組實作與註冊。chatcall.py 負責：
- 解析用戶需求
- 規劃工具調用流程（由 LLM/Schema 決定）
- 執行工具（透過 execute_tool）
- 管理對話與任務歷史

所有功能擴充都在 llm_call_tools 進行，chatcall.py 不需知道工具細節，只需動態取得工具清單並調用。未來要加新功能只需在 llm_call_tools 新增工具即可。

### 典型流程
1. 用戶輸入需求
2. chatcall.py 規劃工具串接流程（如 project_reader → code_searcher → code_modifier）
3. 依序執行，所有細節都由 llm_call_tools 處理

這樣 chatcall.py 就像 Copilot agent 的「大腦」，所有「手腳」都在 llm_call_tools，易於維護與擴展。

---

## llm_call_tools 工具註冊機制

`llm_call_tools` 資料夾下的工具模組（如 `fileio`）會透過 `common.py` 中的 `@register_ai_tool` 裝飾器來註冊工具。

### 註冊方式說明

每個工具函式都需用 `@register_ai_tool` 裝飾，範例：

```python
@register_ai_tool(
   "text_reader",
   "單純讀取檔案作為系統Context，如果有工具的目標是讀取文字，但分析的內容還沒載入，應優先執行text_reader",
   ['reader','text']
)
def handle_text_reader(p: dict, sys_inst):
    ...
```

#### 參數意義
- **name**：工具名稱（如 `text_reader`），用於系統調度與呼叫。
- **prompt**：工具用途描述，會被 LLM 用於規劃任務時參考。
- **tags**：工具標籤，代表此工具擅長的領域或用途（如 `['reader','text']`），系統會根據用戶需求自動加權推薦。

#### 註冊流程
1. 工具模組匯入 `register_ai_tool`。
2. 以裝飾器方式註冊工具，並提供名稱、描述、標籤。
3. 工具會自動加入系統工具清單，供主程式（如 `chatcall.py`）動態選用。

### fileio 範例
- `text_reader`：讀取檔案內容並存入系統 Context，標籤為 `reader`、`text`。
- `code_analyzer`：分析程式邏輯，標籤為 `analyzer`、`source`、`code`。
- `write_code`：根據需求生成程式碼檔案，標籤為 `code`、`writer`。
- `chatter`：回應聊天，標籤為 `chat`。

這些工具都可被主程式自動調度，並根據標籤與描述進行智能選擇。

---

## @register_ai_tool 參數補充
- `name`：唯一識別工具的字串。
- `prompt`：工具用途說明，協助 LLM 理解並規劃。
- `tags`：工具領域標籤，支援多標籤，影響工具推薦與自動選擇。

> 例如：
> - `text_reader` 適合用於檔案讀取任務。
> - `code_analyzer` 適合用於程式分析。
> - `write_code` 適合用於程式生成。

系統會根據用戶需求自動比對標籤，推薦最合適的工具。
