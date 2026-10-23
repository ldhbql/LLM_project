# AnythingLLM 控制台网页

单文件网页，整合四个功能：文档上传、文档树/列表、文档删除、工作区管理。

- 网页文件：`./My_anythingllm_Web.html`（同目录，直接在浏览器打开）
- AnythingLLM：`http://localhost:3001`

## 功能与接口

| 功能 | 接口 |
| --- | --- |
| 上传文档（自动嵌入） | `GET /v1/workspaces`、`POST /v1/document/upload`（`file` + `addToWorkspaces`） |
| 文档树 | `GET /v1/documents`（`localFiles` 嵌套树） |
| 文档列表 | 由上面的树展开得到（路径 = 文件夹 + 文件名） |
| 从工作区移除 | `POST /v1/workspace/{slug}/update-embeddings`（`deletes`） |
| 永久删除 | `DELETE /v1/system/remove-documents`（`names`） |
| 删除文件夹 | `DELETE /v1/document/remove-folder`（`name`） |
| 工作区列表/新建/重命名/删除 | `GET /v1/workspaces`、`POST /v1/workspace/new`、`POST /v1/workspace/{slug}/update`、`DELETE /v1/workspace/{slug}` |

认证：请求头 `Authorization: Bearer <ANYTHINGLLM_API_KEY>`。所有删除操作均二次确认。

## 使用

1. 浏览器打开 `E:\LLM\AnythingLLMServer\My_anythingllm_Web.html`。
2. 顶部下拉选择当前工作区（上传与“从工作区移除”使用）。
3. 四个标签页：上传 / 文档 / 删除 / 工作区。

> 若因 `file://` 的 Origin=null 预检被浏览器拦截，可在项目根执行
> `py -m http.server 5500`，再访问 `http://localhost:5500/My_anythingllm_Web.html`。

## 备注

- API Key 明文写在 `My_anythingllm_Web.html` 中，仅本地使用，请勿外传该文件。
- 上传时 `fetch` 不手动设置 `Content-Type`，由浏览器自动生成 multipart boundary。
