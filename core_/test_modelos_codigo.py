from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from core.models import AcaoEmEspera, Setor, StatusSAC


class ModelosCodigoTests(TestCase):
    def test_setor_normaliza_codigo_no_save(self):
        setor = Setor.objects.create(nome='Assessoria Científica')
        self.assertEqual(setor.codigo, 'ASSESSORIA_CIENTIFICA')

    def test_acao_normaliza_codigo_no_save(self):
        acao = AcaoEmEspera.objects.create(nome='Aguardando Emissão da Nota fiscal (Saída)')
        self.assertEqual(acao.codigo, 'AGUARDANDO_EMISSAO_DA_NOTA_FISCAL_SAIDA')

    def test_status_normaliza_codigo_no_save(self):
        status = StatusSAC.objects.create(nome='Concluído')
        self.assertEqual(status.codigo, 'CONCLUIDO')

    def test_status_codigo_unico(self):
        StatusSAC.objects.create(nome='Concluído')
        with self.assertRaises(Exception):
            StatusSAC.objects.create(nome='Concluido')

    def test_setor_codigo_obrigatorio_pos_normalizacao(self):
        setor = Setor(nome='   ')
        with self.assertRaises(ValidationError):
            setor.save()

    def test_acao_codigo_obrigatorio_pos_normalizacao(self):
        acao = AcaoEmEspera(nome='   ')
        with self.assertRaises(ValidationError):
            acao.save()

    def test_acao_codigo_unico(self):
        AcaoEmEspera.objects.create(nome='Ação X')
        with self.assertRaises(IntegrityError):
            AcaoEmEspera.objects.create(nome='Acao X', codigo='ACAO_X')
