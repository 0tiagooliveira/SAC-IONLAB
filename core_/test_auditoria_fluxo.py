from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from core.models import AcaoEmEspera, Cliente, Empresa, SAC, Setor, StatusSAC


class AuditoriaFluxoCommandTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create(username='auditoria_user')
        self.setor_sac = Setor.objects.create(nome='SAC', codigo='SAC', ativo=True)
        self.status_aberto = StatusSAC.objects.create(nome='Aberto', codigo='ABERTO', ativo=True)
        self.status_concluido = StatusSAC.objects.create(nome='Concluído', codigo='CONCLUIDO', ativo=True)
        self.acao = AcaoEmEspera.objects.create(nome='Análise do Ocorrido - SAC', codigo='ANALISE_OCORRIDO_SAC', ativo=True, setor_destino=self.setor_sac)
        self.empresa = Empresa.objects.create(codigo='EMP', razao_social='Empresa', ativo=True)
        self.cliente = Cliente.objects.create(empresa=self.empresa, codigo_interno='CLI', nome='Cliente', razao_social='Cliente', ativo=True)

    def _criar_sac(self, **kwargs):
        base = {
            'numero': kwargs.pop('numero', '001/2099'),
            'ano': 2099,
            'sequencia_ano': kwargs.pop('sequencia_ano', 1),
            'empresa': self.empresa,
            'cliente': self.cliente,
            'usuario_abertura': self.usuario,
            'titulo': 'SAC teste',
        }
        base.update(kwargs)
        return SAC.objects.create(**base)

    def test_auditoria_sem_inconsistencias(self):
        self._criar_sac(status_atual=self.status_aberto, acao_em_espera=self.acao, setor_atual=self.setor_sac, setor_responsavel=self.setor_sac)
        out = StringIO()
        call_command('auditar_fluxo_sac', stdout=out)
        texto = out.getvalue()
        self.assertIn('OK: nenhuma inconsistência principal encontrada.', texto)

    def test_auditoria_detecta_concluido_com_acao(self):
        self._criar_sac(numero='002/2099', sequencia_ano=2, status_atual=self.status_concluido, acao_em_espera=self.acao, setor_atual=self.setor_sac, setor_responsavel=self.setor_sac)
        out = StringIO()
        call_command('auditar_fluxo_sac', stdout=out)
        texto = out.getvalue()
        self.assertIn('SAC concluído com ação pendente: 1', texto)
        self.assertIn('Concluído com ação pendente', texto)
