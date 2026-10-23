import subprocess

from .registry import tool


@tool(name="getData", description="获取当前电脑的日期和时间")
def get_data() -> str:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", "date"],
        capture_output=True,
        text=True,
        encoding="mbcs",
        errors="replace",
    )
    return result.stdout.strip()


@tool(
    name="isLeapYear",
    description="判断输入的年份是否为闰年",
    parameters={
        "type": "object",
        "properties": {"year": {"type": "integer", "description": "要判断的年份"}},
        "required": ["year"],
    },
)
def is_leap_year(year: int) -> str:
    year = int(year)
    if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
        return f"{year} 是闰年"
    return f"{year} 不是闰年"
