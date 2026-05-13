from types import SimpleNamespace
from django.test import TestCase

from core.services.motor_fluxo_sac import resolver_fluxo
from core.services.validacao_motor_fluxo import validar_motor_em_paralelo


class MotorLogisticaValidacaoTest(TestCase):
    def test_motor_nao_quebra_com_sac_minimo(self):
        sac = SimpleNamespace(setor_atual=None, status_atual=None, acao_em_espera_atual=None)
        resultado = resolver_fluxo(sac)
        self.assertIsNone(resultado)

    def test_validador_paralelo_nao_altera_regra(self):
        sac = SimpleNamespace(setor_atual=None, status_atual=None, acao_em_espera_atual=None)
        resultado = validar_motor_em_paralelo(sac, contexto="teste_logistica")
        self.assertTrue(resultado["ok"])
        self.assertIn("resultado", resultado)
        self.assertIn("divergencias", resultado)
