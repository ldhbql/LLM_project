from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    func: Callable[..., str]


_REGISTRY: dict[str, Tool] = {}


def tool(name: str, description: str, parameters: dict[str, Any] | None = None):
    def decorator(func: Callable[..., str]) -> Callable[..., str]:
        _REGISTRY[name] = Tool(
            name=name,
            description=description,
            parameters=parameters or {"type": "object", "properties": {}},
            func=func,
        )
        return func

    return decorator


def get_schemas() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": item.name,
                "description": item.description,
                "parameters": item.parameters,
            },
        }
        for item in _REGISTRY.values()
    ]


def get_tool(name: str) -> Tool | None:
    return _REGISTRY.get(name)


def dispatch(name: str, arguments: dict[str, Any]) -> str:
    item = _REGISTRY.get(name)
    if item is None:
        return f"未知工具: {name}"
    try:
        return item.func(**arguments)
    except Exception as exc:  # noqa: BLE001 - 工具错误回传给模型
        return f"错误: {exc}"
