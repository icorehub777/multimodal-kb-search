[繁體中文](../01-%E9%AB%98%E9%9A%8E%E8%A8%AD%E8%A8%88%E8%A6%8F%E5%8A%83.md) | English

# I. Synchronizing Google Drive Documents with the Multimodal Vector Database

Fully synchronize documents within configured Google Drive sources to Qdrant to support Agent's multimodal document similarity search.

## 1. Google Drive Document Synchronization

The system keeps the vector database consistent with the configured Google Drive sources, including document creation, modification, movement, renaming, and deletion.

Background synchronization accesses Google Drive using Service Account credentials with Domain-Wide Delegation.

Synchronization compares complete inventories: obtain the full document list within the Drive scan scope and the complete list of synchronized documents in Qdrant, grouped by Google file ID, then compare them to detect changes.

Process the comparison results as follows:

```text
1. Present only in Google Drive: perform a full import.
2. Present only in the vector database: remove all vector data for the document.
3. Present in both but changed, as determined by Drive modifiedTime: remove all existing vector data and perform a full import again.
4. Present in both and unchanged: skip.
```

Changed documents are always processed as complete documents. Remove their existing vector data before regenerating and writing vectors to avoid stale pages or inconsistent partial updates. When a document is deleted or removed from the scan scope, remove its corresponding vector data so search results do not refer to missing or outdated content.

## 2. Per-Page Document Vectorization

Vectorize each document through these steps:

```text
1. Convert the document into one image per page.
2. Embed each page image using the Alibaba Cloud multimodal embedding model.
3. Import each page vector and its required metadata into Qdrant.
```

Supported types include PDF, Word, PowerPoint, TXT, MD, Google Docs, Google Slides, PNG, JPG, JPEG, and WEBP.

PNG, JPG, JPEG, and WEBP are treated as single-page documents with page number 1. Convert them to a single-page PNG before vectorization. Other document types are converted to PDF before rendering pages to images.

Excel and Google Sheets are excluded because their layouts vary. To include their content in the vector database, users must manually convert it to an A4-layout PDF, verify the layout, and place it within the scan scope.

## 3. Per-Page Vector Metadata

Each vector imported into Qdrant must carry metadata that allows tracing at least:

```text
1. Google file ID
2. Original document name
3. Original document path or location
4. Original document URL
5. Google Drive file version, for troubleshooting and traceability
6. Google Drive modifiedTime, used for synchronization comparison in §1
7. Page number
```

---

# II. User Queries and Codex Agent Reading

Let users query through Codex Agent with natural language or images and let Agent retrieve relevant document pages and original files that the user is authorized to access.

## 1. Keyword and Multimodal Similarity Search

Users can ask Codex Agent natural-language questions or upload images as query input. On receiving a query, the system guides the user to choose both search methods or only one. Each search's results are saved in its corresponding result list.

**Google Drive keyword search**

Agent extracts keywords from the user's question and images, if supplied. It uses the **current user's** OAuth credentials to call the Google Drive API and search file names, full text, or metadata.

Results are at **file level**, such as `file_id` and file name, and **contain no document page numbers**. Preserve the original Google API result order.

The result list must include at least the file name, Google Drive file ID, and file URL.

Notes:

- Search scope follows the current user's Drive permissions and is not restricted to source directories synchronized to the vector database.
- Search scope is not limited to the types supported for vectorization. Any Drive MIME type that supports keyword search is included; ZIP files, videos, and other non-document formats may match through names or metadata.
- Exclude items that cannot be downloaded and unsupported Google-native MIME types. Currently, only Google Docs, Slides, and Sheets are supported.

This method suits explicit terms that can be matched literally, such as customer names, project codes, product models, contract numbers, people, dates, and document names. It complements vector search for identifiers and proper nouns that semantic search may miss.

**Qdrant multimodal similarity search**

Agent sends the user's original description or user-approved query text, together with any images, to the multimodal embedding model. It searches page vectors using the result count or minimum similarity threshold specified by Agent.

Group **page-level** results by Google file ID into two levels: files and their matched pages. Order files by their highest page similarity score, descending. Order pages within each file by similarity score, descending.

For each file, use the current user's OAuth credentials to verify continued access through the Google Drive API and exclude inaccessible files.

The result list must include at least the file name, Google Drive file ID, file URL, and each matched page's number and similarity score.

This method suits semantically similar content, visually similar images, or needs that users cannot precisely describe in words.

## 2. Task Workspace

When Agent receives a new user task, it creates a separate task workspace. Inputs, subsequent queries, analysis, and outputs for that task remain in the same workspace. Follow-up requests for an existing task continue using its workspace.

One or more queries within a task store their results in a fixed location. Agent organizes other content according to the task's needs.

## 3. Downloading Query Result Files

Each query creates a separate results directory within the current task workspace. It must not overwrite or mix results from other queries. If the intended results location already exists, stop before executing the query to protect its contents.

After creating the results directory, organize its contents as follows:

```text
1. Create lists of the actual query conditions, keyword results, and similarity results.
2. Take the union of files in the searches actually performed. If only one search type ran, its result list is the union.
3. Create a directory for each file using a safe file name and Google file ID.
4. Download each file into its directory. Export Google Docs and Slides as PDF and Google Sheets as XLSX; download other files in their original formats.
5. For formats supporting conversion to PDF and per-page text, provide both the PDF and page text: PDF, Word, PowerPoint, TXT, MD, Google Docs, and Google Slides.
6. For formats supporting page images, provide an image for each matched page. Similarity search supplies page numbers directly; keyword search locates them in per-page text using the search keywords. If both searches match a page, generate its image only once.
```

Notes:

- Drive keyword search covers names, descriptions, indexableText, content, and some metadata. Therefore, searching document text for keywords may not locate matched pages. When a page is located, write its number and matched keywords back to the result list.
- Image files, including PNG, JPG, JPEG, and WEBP, produce a page-1 image only for similarity matches. Drive OCR or full-text matches retain file-level results because no per-page text is available for locating matches.
- If a file cannot be downloaded, or a supported document cannot complete processing, continue with the other files. Retain successful results and provide the failed file, failure stage, reason, and original URL. For similarity results, also provide matched page numbers; for keyword results, provide the query conditions. This lets Agent explain incomplete results and help the user inspect original documents.

## 4. Codex Agent Reading and Response Principles

Codex Agent reads and responds from query result directories, result lists, and downloaded files within the current task rather than connecting directly to the entire Drive repository. It follows these principles:

```text
1. After searching, normally guide the user to inspect the result lists and page images before analyzing individual images. After the user reviews the results, assist with detailed analysis as efficiently as possible.
2. Agree with the user on which files and pages to analyze and how deeply. Prioritize result lists, exported page images for visual understanding, and per-page text for keyword location to improve efficiency and avoid reading large files in full.
3. Prefer page-image analysis to capture text, images, and tables together. If relevant content belongs to a supported document but falls outside already rendered pages, locate its page number and render that page before analyzing it.
4. For formats unsupported for page-image processing, use Agent's available tools to read and analyze them.
5. Identify cited files and pages in responses. If a page image exists, include that image in the response.
6. If result quality is poor, confirm an adjusted query plan with the user before searching again, such as increasing result count or changing search types, query text, or keywords. Read and respond according to these same principles.
```

---
