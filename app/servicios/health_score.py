"""Indicador de salud del servidor ("Health Score") - fórmula propia del equipo.

Se parte de 100 puntos y se restan penalizaciones:

  Factor                                   Penalización
  ---------------------------------------  ---------------------------
  CPU de SQL Server   > 90 %               -30
                      > 75 %               -15
                      > 60 %                -5
  Disco libre         < 10 %               -30
                      < 20 %               -15
  Errores severos últimas 24 h             -5 c/u   (máximo -20)
  Alertas activas (notificaciones no leídas) -5 c/u (máximo -20)
  BD de usuario sin respaldo completo en 24 h -5 c/u (máximo -15)
  Servidor sin respuesta (sin heartbeat)    el score es 0

Clasificación:  80-100 Saludable (verde) | 50-79 Atención (amarillo) | 0-49 Crítico (rojo)
"""
from datetime import datetime, timedelta


def calcular(cpu=None, disco_libre_pct=None, errores_24h=0, alertas_activas=0,
             bd_sin_respaldo=0, en_linea=True):
    if not en_linea:
        return 0, [("Servidor sin respuesta", -100)]

    detalle = []

    if cpu is not None:
        if cpu > 90:
            detalle.append((f"CPU muy alto ({cpu}%)", -30))
        elif cpu > 75:
            detalle.append((f"CPU alto ({cpu}%)", -15))
        elif cpu > 60:
            detalle.append((f"CPU elevado ({cpu}%)", -5))

    if disco_libre_pct is not None:
        if disco_libre_pct < 10:
            detalle.append((f"Disco casi lleno ({disco_libre_pct:.1f}% libre)", -30))
        elif disco_libre_pct < 20:
            detalle.append((f"Poco espacio en disco ({disco_libre_pct:.1f}% libre)", -15))

    if errores_24h:
        detalle.append((f"{errores_24h} errores severos en 24 h", -min(20, 5 * errores_24h)))
    if alertas_activas:
        detalle.append((f"{alertas_activas} alertas activas", -min(20, 5 * alertas_activas)))
    if bd_sin_respaldo:
        detalle.append((f"{bd_sin_respaldo} BD sin respaldo reciente", -min(15, 5 * bd_sin_respaldo)))

    score = max(0, min(100, 100 + sum(p for _, p in detalle)))
    return score, detalle


def contar_sin_respaldo(respaldos, horas=24):
    limite = datetime.now() - timedelta(hours=horas)
    return sum(1 for r in respaldos if not r["ultimo_respaldo"] or r["ultimo_respaldo"] < limite)


def clasificar(score):
    if score is None:
        return ("Sin datos", "secondary")
    if score >= 80:
        return ("Saludable", "success")
    if score >= 50:
        return ("Atención", "warning")
    return ("Crítico", "danger")
