import configparser
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = BASE_DIR / "config.ini"


@dataclass
class Config:
    base_url: str
    model: str
    api_key: str


def load_config(path: str | Path | None = None) -> Config:
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    parser = configparser.ConfigParser()
    if not parser.read(config_path, encoding="utf-8"):
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    section = parser["default"]
    return Config(
        base_url=section["base_url"],
        model=section["model"],
        api_key=section["api_key"],
    )
