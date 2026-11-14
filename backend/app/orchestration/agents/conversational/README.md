# Conversational Agent

Implementado en `agent.py`, como nodo `conversation` del grafo LangGraph de la Sesión 17A.
Reutiliza `build_context`, el historial SQLite y el puerto `ResponseGenerator.chat()` con
Cloudflare/Qwen3 en la composición normal. Es el único nodo que llama al proveedor, una vez
como máximo. Explica hechos, aclaraciones y propuestas orientativas; no dispone de
herramientas de escritura ni del motor estadístico.

Ver [arquitectura y demo](../../../../../docs/ORQUESTACION_MULTIAGENTE.md).
