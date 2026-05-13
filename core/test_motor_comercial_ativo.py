from django.test import SimpleTestCase
from pathlib import Path


class MotorComercialAtivoEstruturaTest(SimpleTestCase):
    def test_servico_motor_comercial_existe(self):
        p = Path("core/services/motor_comercial_ativo.py")
        self.assertTrue(p.exists())
        texto = p.read_text(encoding="utf-8")
        self.assertIn("aplicar_motor_comercial_seguro", texto)
        self.assertIn("trava de equivalencia", texto)

    def test_view_comercial_chama_motor_seguro(self):
        texto = Path("core/views.py").read_text(encoding="utf-8")
        self.assertIn("aplicar_motor_comercial_seguro", texto)
        self.assertIn("Motor Comercial ativo com trava", texto)
