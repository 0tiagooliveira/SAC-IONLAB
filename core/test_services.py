from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import AcaoEmEspera, Cliente, Empresa, SAC, SacHistorico, Setor, StatusSAC
from core.services.fluxo_sac import (
    acao_permite_selecao_manual_setor,
    obter_setor_destino_padrao,
    validar_transicao_basica,
)
from core.services.historico_sac import registrar_historico_sac


class ClienteModelTests(TestCase):
    def test_preenche_nome_e_razao_social_quando_ausentes(self):
        empresa = Empresa.objects.create(razao_social='Empresa Teste')
        cliente = Cliente.objects.create(empresa=empresa, codigo_interno='C1')

        self.assertEqual(cliente.nome, 'CLIENTE NÃO INFORMADO')
        self.assertEqual(cliente.razao_social, 'CLIENTE NÃO INFORMADO')


class ServicoFluxoSACTests(TestCase):
    def setUp(self):
        self.setor_origem = Setor.objects.create(nome='Origem')
        self.setor_destino = Setor.objects.create(nome='Destino')
        self.status_aberto = StatusSAC.objects.create(nome='Aberto')
        self.status_concluido = StatusSAC.objects.create(nome='Concluído')
        self.acao_manual = AcaoEmEspera.objects.create(nome='Análise do Ocorrido')
        self.acao_padrao = AcaoEmEspera.objects.create(
            nome='Aguardando coleta',
            setor_destino=self.setor_destino,
        )
        self.sac = SAC.objects.create(
            numero='SAC-TESTE-1',
            ano=2026,
            sequencia_ano=1,
            status_atual=self.status_aberto,
            setor_responsavel=self.setor_origem,
            setor_atual=self.setor_origem,
        )

    def test_acao_sem_setor_destino_permite_selecao_manual(self):
        self.assertTrue(acao_permite_selecao_manual_setor(self.acao_manual))
        self.assertIsNone(obter_setor_destino_padrao(self.acao_manual))

    def test_acao_com_setor_destino_retorna_setor_padrao(self):
        self.assertFalse(acao_permite_selecao_manual_setor(self.acao_padrao))
        self.assertEqual(obter_setor_destino_padrao(self.acao_padrao), self.setor_destino)

    def test_validacao_bloqueia_setor_diferente_do_padrao(self):
        outro_setor = Setor.objects.create(nome='Outro Setor')
        with self.assertRaisesMessage(ValueError, 'Setor de destino divergente'):
            validar_transicao_basica(
                self.sac,
                acao_nova=self.acao_padrao,
                setor_destino=outro_setor,
            )

    def test_validacao_bloqueia_avanco_em_sac_concluido(self):
        self.sac.status_atual = self.status_concluido
        with self.assertRaisesMessage(ValueError, 'SAC concluído só pode avançar'):
            validar_transicao_basica(self.sac, acao_nova=self.acao_padrao)


class ServicoHistoricoSACTests(TestCase):
    def test_registrar_historico_cria_item_com_dados_minimos(self):
        user = get_user_model().objects.create_user(username='tester', password='123456')
        setor = Setor.objects.create(nome='Setor Teste')
        status = StatusSAC.objects.create(nome='Aberto')
        sac = SAC.objects.create(
            numero='SAC-TESTE-2',
            ano=2026,
            sequencia_ano=2,
            status_atual=status,
            setor_responsavel=setor,
            setor_atual=setor,
        )

        historico = registrar_historico_sac(
            sac=sac,
            usuario=user,
            acao_executada='Teste de histórico',
            observacao='  observação exemplo  ',
            status_novo=status,
            setor_origem=setor,
            setor_destino=setor,
        )

        self.assertIsInstance(historico, SacHistorico)
        self.assertEqual(historico.acao_executada, 'Teste de histórico')
        self.assertEqual(historico.observacao, 'observação exemplo')
        self.assertEqual(SacHistorico.objects.count(), 1)
