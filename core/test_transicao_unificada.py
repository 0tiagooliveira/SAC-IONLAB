from django.contrib.auth.models import User
from django.test import TestCase

from core.models import AcaoEmEspera, Cliente, Empresa, SAC, Setor, StatusSAC
from core.services.sac_transicao_unificada import aplicar_transicao_sac


class TransicaoUnificadaTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create(username="teste")

        self.setor_sac = Setor.objects.create(nome="SAC")
        self.status_aberto = StatusSAC.objects.create(nome="Aberto")

        self.empresa = Empresa.objects.create(razao_social="Empresa Teste")
        self.cliente = Cliente.objects.create(
            empresa=self.empresa,
            codigo_interno="CLI-TESTE",
            nome="Cliente Teste",
        )

        self.sac = SAC.objects.create(
            empresa=self.empresa,
            cliente=self.cliente,
            status_atual=self.status_aberto,
            setor_atual=self.setor_sac,
        )

    def test_mantem_setor_atual_quando_acao_nao_tem_destino_padrao(self):
        acao = AcaoEmEspera.objects.create(nome="Análise do Ocorrido")

        resultado = aplicar_transicao_sac(
            sac=self.sac,
            usuario=self.usuario,
            acao_em_espera=acao,
            status_novo=self.status_aberto,
        )

        self.sac.refresh_from_db()

        self.assertEqual(self.sac.acao_em_espera_id, acao.id)
        self.assertEqual(self.sac.setor_atual_id, self.setor_sac.id)
        self.assertEqual(resultado.historico.setor_destino_id, self.setor_sac.id)
