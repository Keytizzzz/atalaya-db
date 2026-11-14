"""Páginas recientes y favoritas del usuario (Unidad 1 - pantalla de inicio)."""
from flask import request, session

from app.core import db_meta


def registrar_visita(titulo: str):
    if "id_usuario" not in session:
        return
    try:
        db_meta.ejecutar(
            "INSERT INTO dbo.paginas_visitadas (id_usuario, titulo, url) VALUES (?, ?, ?)",
            session["id_usuario"], titulo[:150], request.full_path.rstrip("?")[:300])
        # Conserva solo las 30 visitas más recientes (los favoritos nunca se borran)
        db_meta.ejecutar(
            """DELETE FROM dbo.paginas_visitadas
               WHERE id_usuario = ? AND favorito = 0 AND id_pagina NOT IN (
                   SELECT TOP 30 id_pagina FROM dbo.paginas_visitadas
                   WHERE id_usuario = ? AND favorito = 0 ORDER BY fecha DESC)""",
            session["id_usuario"], session["id_usuario"])
    except Exception as e:  # noqa: BLE001
        print(f"[visitas] {e}")


def recientes(limite=8):
    return db_meta.consultar(
        f"""SELECT TOP {int(limite)} url, MAX(titulo) AS titulo, MAX(fecha) AS fecha
            FROM dbo.paginas_visitadas WHERE id_usuario = ? AND favorito = 0
            GROUP BY url ORDER BY MAX(fecha) DESC""", session["id_usuario"])


def favoritos():
    return db_meta.consultar(
        "SELECT url, titulo FROM dbo.paginas_visitadas WHERE id_usuario = ? AND favorito = 1 ORDER BY titulo",
        session["id_usuario"])


def es_favorito(url):
    return db_meta.consultar_uno(
        "SELECT 1 AS x FROM dbo.paginas_visitadas WHERE id_usuario = ? AND url = ? AND favorito = 1",
        session["id_usuario"], url) is not None


def alternar_favorito(url, titulo):
    if es_favorito(url):
        db_meta.ejecutar("DELETE FROM dbo.paginas_visitadas WHERE id_usuario = ? AND url = ? AND favorito = 1",
                         session["id_usuario"], url)
        return False
    db_meta.ejecutar("INSERT INTO dbo.paginas_visitadas (id_usuario, titulo, url, favorito) VALUES (?, ?, ?, 1)",
                     session["id_usuario"], titulo[:150], url[:300])
    return True
