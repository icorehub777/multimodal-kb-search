# Agent 檔案讀取方式與 Skill 依賴

本文整理 KBSearch Agent 取得檔案後，應依檔案格式使用的讀取方式，以及 PDF、Documents、Presentations、Spreadsheets Skill 明確定義的工具與依賴。

本文只記錄 Skill 明確定義的能力與目前 Codex bundled runtime 實測結果，不將推測性做法視為既有支援。Bundled runtime 會隨 Codex 更新而變動，因此安裝狀態應定期重新檢查。

目前檢查基準：

- Codex bundled runtime：`26.601.10930`
- bundled Python：`C:\Users\MarcoChang\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`
- bundled Node.js：`C:\Users\MarcoChang\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe`
- bundled Node packages：`C:\Users\MarcoChang\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules`

## 1. 檔案格式與操作方式總覽

| Google Drive 或下載格式 | Agent 操作方式 | 備註 |
|---|---|---|
| Google Docs | 由 `query_cli` 匯出為 PDF，再使用 PDF Skill | 不以 Google Docs 原生格式交給 Documents Skill |
| Google Slides | 由 `query_cli` 匯出為 PDF，再使用 PDF Skill | 若取得的是原始 PPTX，才使用 Presentations Skill |
| Google Sheets | 由 `query_cli` 匯出為 XLSX，再使用 Spreadsheets Skill | 不納入向量化，但可能由關鍵字搜尋命中 |
| PDF | PDF Skill | 可先抽取文字，再視需要渲染頁面 |
| DOCX | Documents Skill | 可讀取結構；視覺檢查需渲染 |
| PPTX | Presentations Skill | 使用 `@oai/artifact-tool` 讀取與渲染 |
| XLSX | Spreadsheets Skill | 使用 `@oai/artifact-tool` 匯入、檢查與渲染 |
| CSV | Spreadsheets Skill | 明確使用 `Workbook.fromCSV(...)` |
| TXT、MD | 直接文字讀取與搜尋 | 不屬於本文四個 Skill 的明確處理流程 |
| PNG、JPG、JPEG、WEBP | 直接視覺檢視原圖 | 不屬於本文四個 Skill 的明確處理流程 |

格式限制：

- Documents Skill 明確以 DOCX 為核心，沒有明確保證舊式 `.doc` 的結構化讀取與渲染能力。
- Presentations Skill 明確以 PPTX 為核心，沒有明確保證舊式 `.ppt`。
- Spreadsheets Skill 的描述宣告適用 `.xlsx`、`.xls`、`.csv`、`.tsv`，但明確 API 只提供 `SpreadsheetFile.importXlsx(...)` 與 `Workbook.fromCSV(...)` 範例。不能僅依現有 Skill 指令宣稱 `.xls`、`.tsv` 與 `.xlsx`、CSV 有完全相同的匯入能力。

## 2. PDF Skill

### 2.1 只讀取原始 PDF 內容

PDF Skill 明確要求使用 `pdfplumber` 或 `pypdf` 進行文字抽取與快速檢查，不應將文字抽取結果視為版面正確性的證明。

| 套件 | 動作 | Bundled runtime |
|---|---|---|
| `pypdf` | 讀取頁數、metadata、逐頁文字並進行快速檢查 | 已包含，版本 `6.10.0` |
| `pdfplumber` | PDF 文字抽取與快速檢查 | 未包含 |

目前只依賴 bundled runtime 時，可以使用 `pypdf` 讀取文字型 PDF。掃描型 PDF、文件圖片、圖表與複雜版面不能只靠文字抽取確認。

### 2.2 Skill 明確定義的進階動作

| 進階動作 | 套件或軟體 | Bundled runtime |
|---|---|---|
| 將 PDF 頁面渲染為 PNG 並進行視覺檢查 | Poppler `pdftoppm` | 未包含 |
| 建立 PDF | `reportlab` | 已包含，版本 `4.4.9` |

Bundled runtime 另有 `pdf2image`，版本 `1.17.0`，但 PDF Skill 的明確渲染命令是直接使用 `pdftoppm`。`pdf2image` 只是 `pdftoppm`／`pdftocairo` 的 Python wrapper；只有 `pdf2image`、沒有 Poppler 時，仍無法完成 PDF 轉圖。

若要完成 PDF Skill 的視覺渲染流程，需另外安裝：

- **Poppler**：提供 `pdftoppm`，安裝後須確保執行程序可從 `PATH` 找到。
- **`pdfplumber`**：安裝於 `agent_runtime/_internal/.venv`；只有需要使用該套件時才需呼叫，PDF Skill 允許以 `pypdf` 進行基本文字抽取。

## 3. Documents Skill

### 3.1 只讀取原始 DOCX 內容

Documents Skill 明確以 bundled runtime 與 Skill 內建 OOXML helpers 處理 DOCX，不使用 system Python、global Python 套件或 repo `.venv`。

| 套件或工具 | 動作 | Bundled runtime／Skill |
|---|---|---|
| `python-docx` | 讀取與操作段落、文字 run、標題、表格、頁首頁尾 | 已包含，版本 `1.2.0` |
| `lxml` | OOXML 結構處理 | 已包含，版本 `6.0.2` |
| Python `zipfile`、XML API | 讀取 DOCX package 與 OOXML | Python 標準函式庫已包含 |
| Documents Skill OOXML scripts | 處理 comments、tracked changes、fields 等結構 | 隨 Skill 提供 |

只使用上述結構化工具時，可以讀取文件文字、表格與部分 OOXML 結構，但不能可靠確認：

- 內容實際位於哪一頁。
- 表格、文字與圖片是否裁切、重疊或跨頁異常。
- 圖片、shape、drawing 與複雜版面的實際呈現。

### 3.2 Skill 明確定義的進階動作

Documents Skill 對既有 DOCX 的主要視覺審查流程為：

```text
DOCX
  -> LibreOffice soffice
  -> 中介 PDF
  -> pdf2image
  -> Poppler
  -> page-<N>.png
  -> 視覺檢查
```

| 進階動作 | 套件或軟體 | Bundled runtime／目前機器 |
|---|---|---|
| 執行 Skill 標準渲染流程 | Documents Skill `render_docx.py` | 隨 Skill 提供 |
| DOCX 轉中介 PDF | LibreOffice `soffice` | 不屬於 bundled runtime；目前已安裝於 `C:\Program Files\LibreOffice\program\soffice.exe` |
| 取得 PDF 資訊並將 PDF 轉 PNG | Poppler `pdfinfo`、`pdftoppm` | 未包含，且目前未偵測到 |
| 從 Python 呼叫 Poppler | `pdf2image` | 已包含，版本 `1.17.0` |
| 產生與處理圖片 | `Pillow` | 已包含，版本 `12.2.0` |

若沒有 LibreOffice，Documents Skill 無法將 DOCX 轉為 PDF；即使已安裝 Poppler，也無法完成 DOCX 視覺渲染。此時 Skill 允許略過視覺 QA，但只能依結構化內容檢查，且必須說明未完成渲染。

若要完成 Documents Skill 的完整 DOCX 視覺渲染流程，需另外安裝：

- **LibreOffice**：提供 `soffice`。目前機器已安裝。
- **Poppler**：提供 `pdfinfo` 與 `pdftoppm`。目前機器尚未安裝或未加入 `PATH`。
- **文件使用的系統字型**：不是 Skill package；缺少字型時仍可能成功渲染，但排版與文字呈現可能偏移。

Documents Skill 的 `render_docx.py` 目前會轉換整份文件，沒有提供指定單頁渲染參數。

## 4. Presentations Skill

### 4.1 只讀取原始 PPTX 內容

Presentations Skill 明確使用 bundled Node.js 與 `@oai/artifact-tool`，不使用 LibreOffice、Poppler、Python PPTX 套件或直接 OOXML 修改作為標準流程。

| 套件或 API | 動作 | Bundled runtime |
|---|---|---|
| `@oai/artifact-tool` | PPTX 匯入、檢查、渲染與輸出 | 已包含，版本 `2.8.4` |
| `PresentationFile.importPptx(...)` | 匯入原始 PPTX | 已通過 runtime probe |
| `presentation.inspect(...)` | 讀取 slide、textbox、shape、image、table、chart | 由 `@oai/artifact-tool` 提供 |
| `presentation.export({format: "layout"})` | 輸出版面結構 | 由 `@oai/artifact-tool` 提供 |

目前 bundled runtime probe 已確認：

- `FileBlob.load` 可用。
- `PresentationFile.importPptx` 可用。
- `PresentationFile.exportPptx` 可用。
- Presentation JSX exports 可用。

### 4.2 Skill 明確定義的進階動作

| 進階動作 | 套件或軟體 | Bundled runtime／目前機器 |
|---|---|---|
| 將指定投影片直接渲染為 PNG | `presentation.export({slide, format: "png"})` | `@oai/artifact-tool` 已包含 |
| 在簡報製作、編輯、template-following 或來源／參考簡報審查流程中渲染全部投影片 | `inspect_template_deck.mjs` + `@oai/artifact-tool` | Skill script 與 `@oai/artifact-tool` 已包含 |
| 擷取 PPTX package 媒體、掃描字型與圖表 package parts | `unzip -Z1`、`unzip -p` | bundled runtime 與目前 `PATH` 未偵測到 `unzip` |
| 建立／編輯／輸出 PPTX | `@oai/artifact-tool/presentation-jsx`、`PresentationFile.exportPptx(...)` | 已包含 |

Presentations Skill 的渲染不需要中介 PDF，也不需要 LibreOffice 或 Poppler：

```text
PPTX
  -> @oai/artifact-tool
  -> 投影片 PNG
```

API 可以只渲染指定投影片。只有在簡報新增、修改、template-following，或需要完整理解來源／參考簡報設計風格與版型的審查流程時，會要求逐張渲染全部投影片、建立 contact sheet 並抽取結構。

PPTX 本質上是 ZIP package，裡面包含投影片 XML、圖片、圖表、字型設定與其他 Office package parts。`inspect_template_deck.mjs` 除了透過 `@oai/artifact-tool` 匯入與渲染投影片外，還會直接打開 PPTX package 做輔助檢查：

- 列出 PPTX 內所有 package 檔案名稱。
- 從 `ppt/media/` 擷取內嵌圖片與媒體檔。
- 掃描 slide、master、layout、theme XML 中使用的字型名稱。
- 統計圖表、表格與投影片 XML package parts。

這些輔助檢查使用外部 `unzip` 指令，不是 Python 套件，也不是 Node 套件。需要的指令能力是：

```powershell
unzip -Z1 <file.pptx>          # 列出 PPTX package 內的檔案清單
unzip -p <file.pptx> <entry>   # 將 package 內指定檔案輸出到 stdout
```

若 Windows 環境沒有相容的 `unzip` CLI，`@oai/artifact-tool` 仍可負責 PPTX 匯入與投影片 PNG 渲染；但 `inspect_template_deck.mjs` 的媒體擷取、字型掃描與 package parts 清單會無法完整執行。若要使用這些完整檢查功能，需要安裝可支援 `unzip -Z1` 與 `unzip -p` 的 unzip 工具，並將其執行檔所在目錄加入系統 `PATH`。

## 5. Spreadsheets Skill

### 5.1 只讀取原始試算表內容

Spreadsheets Skill 明確要求使用 bundled Node.js 與 `@oai/artifact-tool`，不得自行改用 `openpyxl`、`xlsxwriter` 或 `pandas.ExcelWriter` 作為替代方案。

| 格式或 API | 動作 | Bundled runtime |
|---|---|---|
| XLSX：`SpreadsheetFile.importXlsx(...)` | 匯入原始 XLSX | `@oai/artifact-tool` 已包含，版本 `2.8.4` |
| CSV：`Workbook.fromCSV(...)` | 匯入 CSV | `@oai/artifact-tool` 已包含 |
| `workbook.inspect(...)` | 讀取工作表、範圍、值、公式、表格、drawing 等結構 | `@oai/artifact-tool` 已包含 |
| `pandas`、`numpy` | 需要 Python 進行額外分析時可使用 | 已包含，版本分別為 `3.0.1`、`2.3.5` |

Google Sheets 由 `query_cli` 匯出為 XLSX，因此使用明確定義的 XLSX 流程。

### 5.2 Skill 明確定義的進階動作

| 進階動作 | 套件或軟體 | Bundled runtime |
|---|---|---|
| 檢查值、公式、樣式與錯誤 | `workbook.inspect(...)` | `@oai/artifact-tool` 已包含 |
| 計算與追蹤公式 | artifact-tool formula engine、`workbook.trace(...)` | `@oai/artifact-tool` 已包含 |
| 渲染工作表或指定範圍為 PNG | `workbook.render(...)` | `@oai/artifact-tool` 已包含 |
| 建立／編輯表格、圖表、圖片、格式與驗證 | `@oai/artifact-tool` workbook APIs | 已包含 |
| 輸出 XLSX | `SpreadsheetFile.exportXlsx(...)` | 已包含 |

依 Skill 明確定義的 XLSX 與 CSV 流程，不需要另外安裝 LibreOffice、Poppler 或其他 Python 試算表套件。

對 `.xls` 與 `.tsv`，Skill 描述雖宣告適用，但目前指令沒有提供與 `importXlsx(...)`、`fromCSV(...)` 同等明確的匯入流程。因此需要實際驗證或補充規範後，才能宣稱完整支援。

## 6. 目前需要另外安裝的軟體與套件

依目前 Skill 明確定義流程與本機實測，缺少項目如下：

| 項目 | 類型 | 影響能力 | 是否必要 |
|---|---|---|---|
| Poppler：`pdftoppm` | 外部軟體 | PDF Skill 的 PDF 頁面轉 PNG；Documents Skill 的中介 PDF 轉 PNG | 若需要視覺渲染，必要 |
| Poppler：`pdfinfo` | 外部軟體 | Documents Skill `render_docx.py` 取得 PDF 資訊 | Documents Skill 完整渲染必要 |
| `pdfplumber` | Python 套件 | PDF Skill 可選的文字抽取工具；由 Agent 使用 `_internal/.venv/Scripts/python.exe` 執行 | 非基本讀取必要，因已有 `pypdf` |
| `unzip` CLI | 外部軟體 | Presentations Skill 完整擷取 PPTX package 媒體、字型與圖表清單 | 只在執行該完整檢查流程時必要 |

目前已安裝但不屬於 bundled runtime：

| 項目 | 用途 | 狀態 |
|---|---|---|
| LibreOffice `soffice` | Documents Skill 將 DOCX 轉為 PDF | 已安裝 |

## 7. Bundled runtime 與外部安裝的判斷原則

- Documents、Presentations、Spreadsheets Skill 明確要求使用 Codex workspace dependencies／bundled runtime，不應將所需 Python 或 Node 套件安裝到 repo `.venv` 後，就假設 Skill 會自動使用。
- Poppler、LibreOffice、`unzip` 與系統字型屬於外部軟體或系統資源，不是 Python 套件。
- `pdf2image` 是 Python wrapper，不包含 Poppler。
- 此 repo 將 PDF Skill 需要的 `pdfplumber` 安裝於 `agent_runtime/_internal/.venv`，Agent 需使用該 `.venv` 的 Python 執行。
- 安裝 Skill 不等於安裝所有外部軟體。Skill package 主要提供規範、scripts 與 helper；bundled runtime 由 Codex 管理，外部軟體仍需另外確認。
