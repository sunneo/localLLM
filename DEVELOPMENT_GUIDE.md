# DEVELOPMENT_GUIDE

本文件說明如何在 localLLM 專案中開發、擴充工具與功能。

## 1. 工具註冊機制

所有工具需在 `llm_call_tools/common.py` 透過 `@register_ai_tool` 裝飾器註冊。

### 註冊範例
```python
@register_ai_tool(
   "text_reader",
   "讀取檔案內容並存入系統 Context",
   ['reader','text']
)
def handle_text_reader(p: dict, sys_inst):
    ...
```
- `name`：工具名稱。
- `prompt`：用途描述。
- `tags`：工具標籤，影響自動推薦。

## 2. 新增工具步驟
1. 在 `llm_call_tools/` 下建立新模組或於現有模組新增函式。
2. 匯入 `register_ai_tool` 並用裝飾器註冊。
3. 實作工具邏輯，參數為 (params, sys_inst)。
4. 工具會自動加入系統工具清單，主程式可自動調度。

## 3. fileio 範例
- `text_reader`：讀取檔案。
- `code_analyzer`：分析程式。
- `write_code`：生成程式。
- `chatter`：聊天。

## 4. 主程式 chatcall.py
- 動態獲取工具清單，根據用戶需求自動規劃任務。
- 支援 JSON 任務規劃自動修復。
- 整合 RAG 模組。

## 架構設計理念

本專案建議將 chatcall.py 保持為「核心任務調度器」，所有功能（如讀取檔案、搜尋程式、修改程式等）都由 llm_call_tools 內的工具模組實作與註冊。chatcall.py 僅負責：
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

## 5. 測試與除錯
- 可直接在主程式輸入需求測試工具。
- 工具回傳錯誤時，請檢查參數格式與檔案路徑。

## 6. 進階擴充
- 可新增 RAG 工具、檔案操作工具、分析工具等。
- 標籤設計可提升工具自動推薦效果。

---

如需更詳細開發說明，請參考 README.md 或現有工具模組程式碼。
