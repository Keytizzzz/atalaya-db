"""Bitácora de actividad (Activity Log) - Unidad 6."""
from flask import request, session

from app.core import db_meta


def registrar(accion: str, detalle: str = None, id_usuario: int = None):
    """Guarda una acción relevante. Nunca debe tumbar la petición si falla."""
    try:
        db_meta.ejecutar(
            "INSERT INTO dbo.bitacora_actividad (id_usuario, accion, detalle, ip) VALUES (?, ?, ?, ?)",
            id_usuario if id_usuario is not None else session.get("id_usuario"),
            accion[:100],
            (detalle or "")[:1000],
            request.remote_addr if request else None,
        )
    except Exception as e:  # noqa: BLE001
        print(f"[bitacora] No se pudo registrar '{accion}': {e}")
