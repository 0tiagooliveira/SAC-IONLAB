from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from core.models import AcaoEmEspera, Empresa, SAC, Setor, StatusSAC
from core.services.monitoramento_sac import listar_sacs_parados, auditar_fluxo_operacional


class MonitoramentoSACTestCase(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(razao_social='Empresa Teste')
        self.setor = Setor.objects.create(nome='Comercial', codigo='COMERCIAL')
        self.status = StatusSAC.objects.create(nome='Aberto', codigo='ABERTO')
        self.acao = AcaoEmEspera.objects.create(nome='Análise do Ocorrido - Comercial', codigo='ANALISE_OCORRIDO_COMERCIAL')

    def test_listar_sacs_parados_encontra_item_antigo(self):
        sac = SAC.objects.create(numero='001/2026', empresa=self.empresa, setor_atual=self.setor, status_atual=self.status, acao_em_espera=self.acao)
        sac.data_abertura = timezone.now() - timedelta(hours=30)
        sac.save(update_fields=['data_abertura'])
        itens = listar_sacs_parados(horas=24, limite=10)
        self.assertTrue(any(item['numero'] == '001/2026' for item in itens))

    def test_auditar_fluxo_operacional_encontra_sac_sem_acao(self):
        sac = SAC.objects.create(numero='002/2026', empresa=self.empresa, setor_atual=self.setor, status_atual=self.status)
        itens = auditar_fluxo_operacional(limite=10)
        self.assertTrue(any(item.numero == sac.numero and item.tipo == 'SEM_ACAO' for item in itens))
