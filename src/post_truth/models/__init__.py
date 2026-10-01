"""Modelos de dominio (logica pura, sin pygame). Reexporta lo existente para no romper imports."""
from post_truth.models.dominio import Impact, NewsEvent, Role

__all__ = ["Impact", "NewsEvent", "Role"]
