from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from core.context_processors import fila_inteligente
from core.models import AcaoEmEspera, Cliente, Empresa, NotaFiscal, SAC, Setor, StatusSAC


class ContextoFilaTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='ctx', password='12345678')
        self.factory = RequestFactory()
        self.setor = Setor.objects.create(nome='Comercial', codigo='COMERCIAL', ativo=True)
        self.status = StatusSAC.objects.create(nome='Aberto', codigo='ABERTO', ativo=True)
        self.acao = AcaoEmEspera.objects.create(nome='Análise do Ocorrido - Comercial', codigo='ANALISE_OCORRIDO', ativo=True, setor_destino=self.setor)
        empresa = Empresa.objects.create(codigo='E1', razao_social='Empresa', ativo=True)
        cliente = Cliente.objects.create(empresa=empresa, codigo_interno='C1', nome='Cliente', razao_social='Cliente', ativo=True)
        nota = NotaFiscal.objects.create(empresa=empresa, cliente=cliente, numero_nf='NF1', numero='NF1')
        SAC.objects.create(numero='003/2099', ano=2099, sequencia_ano=3, empresa=empresa, cliente=cliente, nota_fiscal=nota, status_inicial='Aberto', status_atual=self.status, acao_em_espera=self.acao, setor_atual=self.setor, setor_responsavel=self.setor, usuario_abertura=self.user)

    def test_fila_inteligente_retorna_dados(self):
        request = self.factory.get('/intra/')
        request.user = self.user
        dados = fila_inteligente(request)
        self.assertIn('fila_inteligente', dados)
        self.assertTrue(any(item['setor'] == 'Gestão Comercial' or item['setor'] == 'Comercial' for item in dados['fila_inteligente']))
