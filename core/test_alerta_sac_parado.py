from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from core.models import AcaoEmEspera, Empresa, SAC, Setor, StatusSAC, Cliente
from core.services.monitoramento_sac import listar_sacs_parados


class TestAlertaSacParado(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(razao_social='Empresa Teste')
        self.setor = Setor.objects.create(nome='Comercial', codigo='COMERCIAL')
        self.status = StatusSAC.objects.create(nome='Aberto', codigo='ABERTO')
        self.acao = AcaoEmEspera.objects.create(nome='Análise do Ocorrido - Comercial', codigo='ANALISE_OCORRIDO', setor_destino=self.setor)
        self.cliente = Cliente.objects.create(empresa=self.empresa, codigo_interno='CLI1', razao_social='Cliente Teste')

    def _criar_sac(self, numero: str, horas_atras: int):
        sac = SAC.objects.create(
            numero=numero,
            ano=2026,
            sequencia_ano=1,
            empresa=self.empresa,
            cliente=self.cliente,
            setor_atual=self.setor,
            status_atual=self.status,
            acao_em_espera=self.acao,
        )
        SAC.objects.filter(pk=sac.pk).update(data_abertura=timezone.now() - timedelta(hours=horas_atras))
        sac.refresh_from_db()
        return sac

    def test_listar_sacs_parados_respeita_limite(self):
        sac_antigo = self._criar_sac('001/2026', 30)
        self._criar_sac('002/2026', 2)
        itens = listar_sacs_parados(24)
        ids = [i.sac_id for i in itens]
        self.assertIn(sac_antigo.id, ids)
        self.assertEqual(len(ids), 1)

    def test_comando_alertar_sac_parado(self):
        self._criar_sac('003/2026', 26)
        from io import StringIO
        out = StringIO()
        call_command('alertar_sac_parado', horas=24, stdout=out)
        texto = out.getvalue()
        self.assertIn('ALERTA DE SAC PARADO', texto)
        self.assertIn('003/2026', texto)
