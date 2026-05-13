from django.test import SimpleTestCase

from core.services.fluxo_comercial import resolver_fluxo_comercial
from core.services.motor_fluxo_sac import resolver_fluxo_comercial_validacao


class MotorFluxoComercialValidacaoTest(SimpleTestCase):
    def comparar(self, confirmado_cliente, aceita_negociacao, item_pequeno_valor):
        atual = resolver_fluxo_comercial(
            confirmado_cliente=confirmado_cliente,
            aceita_negociacao=aceita_negociacao,
            item_pequeno_valor=item_pequeno_valor,
        )
        motor = resolver_fluxo_comercial_validacao(
            confirmado_cliente=confirmado_cliente,
            aceita_negociacao=aceita_negociacao,
            item_pequeno_valor=item_pequeno_valor,
        )

        self.assertEqual(motor["status_nome"], atual.status_nome)
        self.assertEqual(motor["status_codigo"], atual.status_codigo)
        self.assertEqual(motor["acao_nome"], atual.acao_nome)
        self.assertEqual(motor["acao_codigo"], atual.acao_codigo)
        self.assertEqual(motor["setor_nome"], atual.setor_nome)
        self.assertEqual(motor["setor_codigo"], atual.setor_codigo)
        self.assertEqual(motor["exigir_desconto"], atual.exigir_desconto)
        self.assertEqual(motor["ocultar_campos_abaixo"], atual.ocultar_campos_abaixo)

    def test_cliente_confirmou_pedido_equivalente(self):
        self.comparar(True, False, False)

    def test_cliente_aceita_negociacao_equivalente(self):
        self.comparar(False, True, False)

    def test_item_pequeno_valor_equivalente(self):
        self.comparar(False, False, True)

    def test_item_nao_pequeno_valor_equivalente(self):
        self.comparar(False, False, False)
