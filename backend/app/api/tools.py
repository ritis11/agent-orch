"""Metadata endpoints for tools and supported models."""
from __future__ import annotations

from fastapi import APIRouter

from ..runtime.llm import SUPPORTED_MODELS
from ..runtime.tools import TOOL_DESCRIPTIONS

router = APIRouter(tags=["meta"])


@router.get("/tools")
def list_tools() -> list[dict[str, str]]:
    return TOOL_DESCRIPTIONS


@router.get("/models")
def list_models() -> list[str]:
    return SUPPORTED_MODELS
