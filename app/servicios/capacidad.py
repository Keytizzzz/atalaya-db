"""Planeación de capacidad y proyección de crecimiento (Unidad 3) - reglas propias del equipo.

SEMÁFORO DE USO                       verde        amarillo      rojo
  CPU (promedio 60 min)               < 60 %       60-80 %       > 80 %
  Memoria usada por SQL / total       < 75 %       75-90 %       > 90 %
  Almacenamiento usado / total        < 70 %       70-85 %       > 85 %

SEMÁFORO DE LATENCIA
  CPU: % de esperas de señal          < 15 %       15-25 %       > 25 %   (presión de CPU)
  Memoria: Page Life Expectancy       > 300 s      150-300 s     < 150 s
  Disco: latencia promedio de E/S     < 10 ms      10-20 ms      > 20 ms

"LO IDEAL A TENER"
  CPU:            núcleos para que el uso pico quede en 70 %  -> ceil(núcleos x pico / 70)
  Memoria:        memoria para que SQL Server use a lo más el 75 % -> usada / 0.75
  Almacenamiento: espacio usado proyectado a 180 días + 20 % de margen

PROYECCIÓN DE CRECIMIENTO
  Regresión lineal por mínimos cuadrados sobre el histórico (fecha, MB) que guarda el
  recolector:  MB(t) = a + b·t   donde b = crecimiento diario.
  Días hasta llenar el disco = espacio libre / b.
"""
import math
from datetime import datetime


def semaforo(valor, verde, amarillo, mayor_es_mejor=False):
    if valor is None:
        return "secondary"
    if mayor_es_mejor:
        return "success" if valor > verde else ("warning" if valor >= amarillo else "danger")
    return "success" if valor < verde else ("warning" if valor <= amarillo else "danger")


def regresion_lineal(puntos):
    """puntos = [(datetime, valor)]. Regresa dict con pendiente diaria o None si no hay datos suficientes."""
    puntos = [(f, float(v)) for f, v in puntos if v is not None]
    if len(puntos) < 3:
        return None
    t0 = puntos[0][0]
    xs = [(f - t0).total_seconds() / 86400 for f, _ in puntos]
    ys = [v for _, v in puntos]
    if xs[-1] - xs[0] < 10 / 1440:          # menos de 10 minutos de historia
        return None
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    a = my - b * mx
    ss_tot = sum((y - my) ** 2 for y in ys)
    r2 = 1 - sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys)) / ss_tot if ss_tot else 1.0
    hoy = (datetime.now() - t0).total_seconds() / 86400
    return {
        "pendiente_dia": b,
        "actual": a + b * hoy,
        "r2": round(r2, 3),
        "en": lambda dias: a + b * (hoy + dias),
        "horas_historia": round((xs[-1] - xs[0]) * 24, 1),
        "muestras": n,
    }


def evaluar(m, cpu_hist, volumenes, regresion):
    """Arma la tabla Disponible / Usado / Ideal con semáforos."""
    nucleos = m["nucleos"]
    usos = [(c["cpu_sql"] or 0) + (c["cpu_otros"] or 0) for c in cpu_hist] or [0]
    cpu_prom = round(sum(usos) / len(usos), 1)
    cpu_pico = max(usos)
    ideal_nucleos = max(2, math.ceil(nucleos * cpu_pico / 70)) if cpu_pico else 2

    mem_total, mem_sql = m["memoria_total_mb"], m["memoria_sql_mb"]
    mem_pct = round(mem_sql * 100 / mem_total, 1) if mem_total else None
    mem_ideal = max(2048, math.ceil(mem_sql / 0.75))

    disco_total = sum(float(v["total_mb"]) for v in volumenes)
    disco_libre = sum(float(v["libre_mb"]) for v in volumenes)
    disco_usado = disco_total - disco_libre
    disco_pct = round(disco_usado * 100 / disco_total, 1) if disco_total else None
    crecimiento_180 = max(0, regresion["pendiente_dia"] * 180) if regresion else 0
    disco_ideal = math.ceil((disco_usado + crecimiento_180) / 0.80)

    lat_io = None
    if m["latencia_lectura_ms"] is not None or m["latencia_escritura_ms"] is not None:
        lat_io = round((float(m["latencia_lectura_ms"] or 0) + float(m["latencia_escritura_ms"] or 0)) / 2, 2)

    return [
        {
            "recurso": "Procesador", "icono": "bi-cpu",
            "disponible": f"{nucleos} núcleos", "usado": f"{cpu_prom}% prom. · {cpu_pico}% pico",
            "ideal": f"{ideal_nucleos} núcleos", "uso_pct": cpu_prom,
            "uso_color": semaforo(cpu_prom, 60, 80),
            "latencia": f"{m['signal_wait_pct'] or 0}% esperas de señal",
            "lat_color": semaforo(float(m["signal_wait_pct"] or 0), 15, 25),
            "nota": "Más núcleos de los necesarios" if ideal_nucleos < nucleos else
                    ("Núcleos suficientes" if ideal_nucleos == nucleos else "Se recomiendan más núcleos"),
        },
        {
            "recurso": "Memoria", "icono": "bi-memory",
            "disponible": f"{mem_total:,} MB", "usado": f"{mem_sql:,} MB ({mem_pct}%)",
            "ideal": f"{mem_ideal:,} MB", "uso_pct": mem_pct,
            "uso_color": semaforo(mem_pct, 75, 90),
            "latencia": f"PLE {m['ple_seg'] or 0:,} s",
            "lat_color": semaforo(m["ple_seg"], 300, 150, mayor_es_mejor=True),
            "nota": ("Sin límite configurado (max server memory por defecto): se recomienda fijarlo"
                     if (m["max_server_memory_mb"] or 0) >= 2147483647
                     else f"Límite configurado (max server memory): {m['max_server_memory_mb']:,} MB"),
        },
        {
            "recurso": "Almacenamiento", "icono": "bi-device-hdd",
            "disponible": f"{disco_total / 1024:,.1f} GB", "usado": f"{disco_usado / 1024:,.1f} GB ({disco_pct}%)",
            "ideal": f"{disco_ideal / 1024:,.1f} GB", "uso_pct": disco_pct,
            "uso_color": semaforo(disco_pct, 70, 85),
            "latencia": f"{lat_io if lat_io is not None else '—'} ms prom. E/S",
            "lat_color": semaforo(lat_io, 10, 20),
            "nota": "Incluye el crecimiento proyectado a 180 días + 20 % de margen",
        },
    ], {"disco_libre_mb": disco_libre}
