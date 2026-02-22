"""
Modelos Pydantic para payloads de entrada en la REST API.
Sin `from typing import` — tipos nativos Python 3.12.

v2.0 — Solo 2 endpoints REST: GET /api/health y GET /api/restore.
Ninguno requiere request body, por lo que este archivo queda vacío
de modelos de entrada REST. Se conserva para uso interno / futuro.
"""

# No hay endpoints REST con body en v2.0.
# Los modelos de mensajes WebSocket están en ws_messages.py.
