"""Páginas temporales de los módulos que se programarán en las siguientes entregas.

Cuando un módulo esté listo se crea su carpeta propia en app/modulos/ y se
quita de esta lista (y se marca listo=True en app/menu.py).
"""
from flask import Blueprint, abort, render_template

from app.core import visitas
from app.core.decoradores import login_requerido
from app.menu import DESCRIPCIONES, MENU

bp = Blueprint("proximamente", __name__, url_prefix="/modulo")


@bp.route("/<clave>")
@login_requerido
def modulo(clave):
    entrada = next((m for m in MENU if m[0] == clave and not m[4]), None)
    if not entrada:
        abort(404)
    visitas.registrar_visita(entrada[1])
    return render_template("en_desarrollo.html", clave=clave, titulo=entrada[1], icono=entrada[2],
                           unidad=entrada[3], descripcion=DESCRIPCIONES.get(clave, ""))
