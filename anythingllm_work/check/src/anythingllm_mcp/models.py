"""Typed payloads returned by the AnythingLLM MCP server."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Source(BaseModel):
    """A document chunk AnythingLLM used to ground an answer."""

    title: str = Field(description="来源文档的名称或标识。")
    chunk: str | None = Field(default=None, description="命中的文档片段内容。")


class Answer(BaseModel):
    """An AI answer grounded in the configured AnythingLLM workspace."""

    answer: str = Field(description="基于工作区文档生成的回答文本。")
    sources: list[Source] = Field(
        default_factory=list,
        description="回答所引用的文档来源，可能为空。",
    )
