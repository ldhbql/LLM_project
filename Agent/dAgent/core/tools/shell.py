import subprocess


def quote(text: str) -> str:
    return "'" + str(text).replace("'", "''") + "'"


def run_ps(cmd: str) -> str:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", "$ErrorActionPreference='Stop'; " + cmd],
        capture_output=True,
        text=True,
        encoding="mbcs",
        errors="replace",
    )
    out = (result.stdout or "").strip()
    err = (result.stderr or "").strip()
    if result.returncode != 0:
        return "错误: " + (err or out or "PowerShell 执行失败")
    return out or "完成"
