from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import AcaoEmEspera, Cliente, Empresa, NotaFiscal, SAC, Setor, StatusSAC
from core.services.sac_transicao_unificada import ErroTransicaoSAC, aplicar_transicao_sac


class TransicaoNFPendenteTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.usuario = User.objects.create(username="teste_nf")

        self.setor_sac = Setor.objects.create(nome="SAC")
        self.setor_arquivo = Setor.objects.create(nome="Arquivo")

        self.status_aberto = StatusSAC.objects.create(nome="Aberto", ativo=True)
        self.status_concluido = StatusSAC.objects.create(nome="Concluído", ativo=True)
        self.acao_concluir = AcaoEmEspera.objects.create(nome="Concluído", setor_destino=self.setor_arquivo, ativo=True)

        self.empresa = Empresa.objects.create(razao_social="Empresa Teste", ativo=True)
        self.cliente = Cliente.objects.create(
            empresa=self.empresa,
            codigo_interno="CLI-TESTE",
            nome="Cliente Teste",
        )
        self.nota = NotaFiscal.objects.create(
            empresa=self.empresa,
            cliente=self.cliente,
            numero_nf="NF-TESTE-1",
        )

    def _criar_sac(self, numero, status):
        return SAC.objects.create(
            numero=numero,
            ano=2099,
            sequencia_ano=int(numero.split('/')[0]),
            empresa=self.empresa,
            cliente=self.cliente,
            nota_fiscal=self.nota,
            status_atual=status,
            acao_em_espera=None,
            setor_atual=self.setor_sac,
        )

    def test_bloqueia_conclusao_quando_existe_outro_sac_da_mesma_nf_pendente(self):
        sac_principal = self._criar_sac("001/2099", self.status_aberto)
        self._criar_sac("002/2099", self.status_aberto)

        with self.assertRaisesMessage(
            ErroTransicaoSAC,
            "Não é permitido concluir este SAC. Existem outros SACs da mesma Nota Fiscal ainda pendentes em outros setores.",
        ):
            aplicar_transicao_sac(
                sac=sac_principal,
                usuario=self.usuario,
                acao_em_espera=self.acao_concluir,
                setor_destino=self.setor_arquivo,
                status_novo=self.status_concluido,
                observacao="Tentativa de conclusão",
            )

    def test_permite_conclusao_quando_outros_sacs_da_mesma_nf_ja_estao_concluidos(self):
        sac_principal = self._criar_sac("003/2099", self.status_aberto)
        self._criar_sac("004/2099", self.status_concluido)

        resultado = aplicar_transicao_sac(
            sac=sac_principal,
            usuario=self.usuario,
            acao_em_espera=self.acao_concluir,
            setor_destino=self.setor_arquivo,
            status_novo=self.status_concluido,
            observacao="Conclusão permitida",
        )

        sac_principal.refresh_from_db()
        self.assertEqual(sac_principal.status_atual_id, self.status_concluido.id)
        self.assertEqual(resultado.status_novo.id, self.status_concluido.id)
