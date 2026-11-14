"""Selector de servidor compartido por los módulos que trabajan "por instancia"."""
from flask import request

from app.modulos.inicio.routes import servidores_visibles


def servidor_seleccionado():
    """Regresa (lista_de_servidores_visibles, servidor_elegido_o_None) según ?servidor=<id>."""
    servidores = servidores_visibles()
    if not servidores:
        return servidores, None
    try:
        elegido = int(request.args.get("servidor", 0))
    except ValueError:
        elegido = 0
    srv = next((s for s in servidores if s["id_servidor"] == elegido), None)
    return servidores, srv or servidores[0]
