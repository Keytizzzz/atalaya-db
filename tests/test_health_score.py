"""Pruebas unitarias de la fórmula del Health Score.

    python -m pytest tests      (o)      python -m unittest discover tests
"""
import unittest

from app.servicios.health_score import calcular, clasificar


class PruebasHealthScore(unittest.TestCase):
    def test_servidor_sano_tiene_100(self):
        score, detalle = calcular(cpu=20, disco_libre_pct=60)
        self.assertEqual(score, 100)
        self.assertEqual(detalle, [])

    def test_servidor_caido_tiene_0(self):
        score, _ = calcular(en_linea=False)
        self.assertEqual(score, 0)

    def test_penalizaciones_se_acumulan(self):
        score, detalle = calcular(cpu=95, disco_libre_pct=5)   # -30 -30
        self.assertEqual(score, 40)
        self.assertEqual(len(detalle), 2)

    def test_tope_de_errores(self):
        score, _ = calcular(errores_24h=50)                      # máximo -20
        self.assertEqual(score, 80)

    def test_nunca_negativo(self):
        score, _ = calcular(cpu=99, disco_libre_pct=1, errores_24h=9, alertas_activas=9, bd_sin_respaldo=9)
        self.assertGreaterEqual(score, 0)

    def test_clasificacion(self):
        self.assertEqual(clasificar(90)[1], "success")
        self.assertEqual(clasificar(60)[1], "warning")
        self.assertEqual(clasificar(10)[1], "danger")


if __name__ == "__main__":
    unittest.main()
