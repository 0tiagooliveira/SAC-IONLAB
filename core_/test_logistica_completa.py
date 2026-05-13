from django.contrib.auth import get_user_model
from django.test import TestCase

from core.forms import GestaoLogisticaAcaoExecutadaForm
from core.models import (
    AcaoEmEspera,
    Cliente,
    Empresa,
    ItemNotaFiscal,
    NotaFiscal,
    SAC,
    SACItem,
    SacHistorico,
    Setor,
    StatusSAC,
    TipoOcorrencia,
)
from core.views_modular.views_logistica import _dados_historico_logistica


class LogisticaCompletaTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='tester', password='123')
        self.user.first_name = 'Ana'
        self.user.last_name = 'Silva'
        self.user.save()

        self.setor_sac = Setor.objects.create(nome='SAC', codigo='SAC')
        self.setor_log = Setor.objects.create(nome='Logística', codigo='LOGISTICA')
        self.setor_ass = Setor.objects.create(nome='Assessoria Científica', codigo='ASSESSORIA_CIENTIFICA')
        self.status_aberto = StatusSAC.objects.create(nome='Aberto', codigo='ABERTO')
        self.status_analise = StatusSAC.objects.create(nome='Em Análise', codigo='EM_ANALISE')
        self.acao_log = AcaoEmEspera.objects.create(nome='Análise do Ocorrido - Logística', codigo='ANALISE_DO_OCORRIDO_LOGISTICA', setor_destino=self.setor_log)
        self.acao_sac = AcaoEmEspera.objects.create(nome='Análise do Ocorrido - SAC', codigo='ANALISE_DO_OCORRIDO_SAC', setor_destino=self.setor_sac)
        self.acao_ass = AcaoEmEspera.objects.create(nome='Análise do Ocorrido - Assessoria Científica', codigo='ANALISE_DO_OCORRIDO_ASSESSORIA_CIENTIFICA', setor_destino=self.setor_ass)

        self.empresa = Empresa.objects.create(razao_social='Empresa X')
        self.cliente = Cliente.objects.create(empresa=self.empresa, codigo_interno='1', razao_social='Cliente Y')
        self.nota = NotaFiscal.objects.create(empresa=self.empresa, cliente=self.cliente, numero_nf='123')
        self.item_nf = ItemNotaFiscal.objects.create(nota_fiscal=self.nota, codigo_produto='P1', descricao_item='Produto 1')
        self.sac = SAC.objects.create(
            numero='SAC-1', empresa=self.empresa, cliente=self.cliente, nota_fiscal=self.nota,
            status_atual=self.status_aberto, acao_em_espera=self.acao_log, setor_atual=self.setor_log, usuario_abertura=self.user,
        )

    def test_item_vencido_direciona_para_assessoria(self):
        tipo = TipoOcorrencia.objects.create(nome='Item Vencido')
        SACItem.objects.create(sac=self.sac, item_nota_fiscal=self.item_nf, tipo_ocorrencia=tipo, tipo_rastreio='LOTE', numero_rastreio='L1')
        form = GestaoLogisticaAcaoExecutadaForm(
            data={
                'nome_separador': 'Sep',
                'nome_bip': 'Bip',
                'nome_embalador': 'Emb',
                'numero_lote': 'LT-01',
                'fabricacao': '2026-01-10',
                'validade': '2027-01-10',
                'quantidade_estoque': '12',
                'observacoes': 'ok',
            },
            sac=self.sac,
            acao_atual_nome='Análise do Ocorrido - Logística',
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['proximo_status'].codigo, 'EM_ANALISE')
        self.assertEqual(form.cleaned_data['proximo_setor'].codigo, 'ASSESSORIA_CIENTIFICA')
        self.assertEqual(form.cleaned_data['proxima_acao_em_espera'].codigo, 'ANALISE_DO_OCORRIDO_ASSESSORIA_CIENTIFICA')

    def test_dados_historico_logistica_extrai_origem_usuario_e_acao(self):
        SacHistorico.objects.create(
            sac=self.sac,
            usuario=self.user,
            status_anterior=self.status_aberto,
            status_novo=self.status_analise,
            setor_origem=self.setor_sac,
            setor_destino=self.setor_log,
            acao_executada='Envio para Logística',
            observacao='Tipo de ocorrência: Item Vencido\nPróxima ação em espera: Análise do Ocorrido - Logística',
        )
        dados = _dados_historico_logistica(self.sac)
        self.assertEqual(dados['status_adicionado_pelo_setor'], 'SAC')
        self.assertEqual(dados['nome_usuario_solicitante'], 'Ana Silva')
        self.assertEqual(dados['tipo_ocorrencia_historico'], 'Item Vencido')
        self.assertEqual(dados['acao_em_espera_historico'], 'Análise do Ocorrido - Logística')
