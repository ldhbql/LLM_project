from .registry import tool
from .shell import quote, run_ps


@tool(name="getCurrentDirectory", description="获取当前工作目录")
def get_current_directory() -> str:
    return run_ps("(Get-Location).Path")


@tool(
    name="listDirectory",
    description="列出指定目录下所有文件和子目录",
    parameters={
        "type": "object",
        "properties": {"path": {"type": "string", "description": "目录路径"}},
        "required": ["path"],
    },
)
def list_directory(path: str) -> str:
    cmd = (
        "Get-ChildItem -LiteralPath " + quote(path) +
        " | ForEach-Object { if ($_.PSIsContainer) { '[DIR] ' + $_.Name } else { '[FILE] ' + $_.Name } }"
    )
    out = run_ps(cmd)
    return out if out != "完成" else "(目录为空)"


@tool(
    name="getFileType",
    description="获取指定文件的文件类型（扩展名）",
    parameters={
        "type": "object",
        "properties": {"path": {"type": "string", "description": "文件路径"}},
        "required": ["path"],
    },
)
def get_file_type(path: str) -> str:
    out = run_ps("(Get-Item -LiteralPath " + quote(path) + ").Extension")
    return out if out != "完成" else "(无扩展名)"


@tool(
    name="readTextFile",
    description="获取指定纯文本文件的内容",
    parameters={
        "type": "object",
        "properties": {"path": {"type": "string", "description": "文件路径"}},
        "required": ["path"],
    },
)
def read_text_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return f.read()
    except UnicodeDecodeError:
        with open(path, "r", encoding="gbk", errors="replace") as f:
            return f.read()


@tool(
    name="createFile",
    description="在指定目录下创建新文件，目录不存在时自动创建，同名文件会被覆盖",
    parameters={
        "type": "object",
        "properties": {
            "directory": {"type": "string", "description": "目录路径"},
            "filename": {"type": "string", "description": "文件名"},
            "content": {"type": "string", "description": "文件内容，默认为空"},
        },
        "required": ["directory", "filename"],
    },
)
def create_file(directory: str, filename: str, content: str = "") -> str:
    cmd = (
        "New-Item -ItemType Directory -Force -Path " + quote(directory) + " | Out-Null; "
        "$p = Join-Path -Path " + quote(directory) + " -ChildPath " + quote(filename) + "; "
        "Set-Content -LiteralPath $p -Value " + quote(content) + " -Encoding UTF8 -NoNewline; "
        "'已创建: ' + $p"
    )
    return run_ps(cmd)


@tool(
    name="editTextFile",
    description="编辑指定纯文本文件的内容",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"},
            "content": {"type": "string", "description": "新内容"},
            "mode": {
                "type": "string",
                "enum": ["overwrite", "append"],
                "description": "overwrite 覆盖（默认），append 追加",
            },
        },
        "required": ["path", "content"],
    },
)
def edit_text_file(path: str, content: str, mode: str = "overwrite") -> str:
    m = "a" if mode == "append" else "w"
    with open(path, m, encoding="utf-8") as f:
        f.write(content)
    return "已编辑: " + path


@tool(
    name="createDirectory",
    description="创建新目录（支持多级）",
    parameters={
        "type": "object",
        "properties": {"path": {"type": "string", "description": "目录路径"}},
        "required": ["path"],
    },
)
def create_directory(path: str) -> str:
    return run_ps(
        "New-Item -ItemType Directory -Force -Path " + quote(path)
        + " | Out-Null; '已创建目录: ' + " + quote(path)
    )


@tool(
    name="deleteDirectory",
    description="删除目录（递归删除非空目录）",
    parameters={
        "type": "object",
        "properties": {"path": {"type": "string", "description": "目录路径"}},
        "required": ["path"],
    },
)
def delete_directory(path: str) -> str:
    return run_ps(
        "Remove-Item -LiteralPath " + quote(path)
        + " -Recurse -Force; '已删除目录: ' + " + quote(path)
    )


@tool(
    name="deleteFile",
    description="删除指定文件",
    parameters={
        "type": "object",
        "properties": {"path": {"type": "string", "description": "文件路径"}},
        "required": ["path"],
    },
)
def delete_file(path: str) -> str:
    return run_ps(
        "Remove-Item -LiteralPath " + quote(path)
        + " -Force; '已删除文件: ' + " + quote(path)
    )


@tool(
    name="renamePath",
    description="重命名文件或目录",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "原路径"},
            "newName": {"type": "string", "description": "新名称（不含目录）"},
        },
        "required": ["path", "newName"],
    },
)
def rename_path(path: str, newName: str) -> str:
    return run_ps(
        "Rename-Item -LiteralPath " + quote(path)
        + " -NewName " + quote(newName) + "; '已重命名: ' + " + quote(newName)
    )
