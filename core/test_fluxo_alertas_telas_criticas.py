from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import AcaoEmEspera, Cliente, Empresa, FluxoAcaoSetor, NotaFiscal, SAC, Setor, StatusSAC


def _tem_campo(modelo, nome_campo: str) -> bool:
    return any(f.name == nome_campo for f in modelo._meta.get_fields())


def _create_instance(modelo, **kwargs):
    allowed = {f.name for f in modelo._meta.get_fields() if getattr(f, 'concrete', False)}
    payload = {k: v for k, v in kwargs.items() if k in allowed}
    return modelo.objects.create(**payload)


def _criar_setor(nome, codigo=None):
    return _create_instance(Setor, nome=nome, codigo=codigo, ativo=True)


def _criar_status(nome, codigo=None):
    return _create_instance(StatusSAC, nome=nome, codigo=codigo, ativo=True)


def _criar_acao(nome, setor_destino=None):
    payload = {"nome": nome, "ativo": True}
    if _tem_campo(AcaoEmEspera, "setor_destino"):
        payload["setor_destino"] = setor_destino
    return _create_instance(AcaoEmEspera, **payload)


class FluxoAlertasTelasCriticasTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="teste_alertas_criticos",
            password="12345678",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(self.user)

        self.setor_sac = _criar_setor("SAC", "SAC")
        self.setor_logistica = _criar_setor("Logística", "LOG")
        self.setor_diretoria = _criar_setor("Diretoria", "DIR")

        self.status_aberto = _criar_status("Aberto", "ABERTO")
        self.status_gestao = _criar_status("Gestão do SAC", "GESTAO")

        self.empresa = _create_instance(Empresa, codigo="EMP1", razao_social="Empresa Teste", ativo=True)
        self.cliente = _create_instance(
            Cliente,
            empresa=self.empresa,
            codigo_interno="CLI1",
            razao_social="Cliente Teste",
            nome="Cliente Teste",
            ativo=True,
        )
        self.nota = _create_instance(
            NotaFiscal,
            empresa=self.empresa,
            cliente=self.cliente,
            numero_nf="NF123",
            numero="NF123",
        )

    def _criar_sac(self, *, numero, setor_atual, acao_nome, setor_destino_acao=None, status=None, sequencia):
        acao = _criar_acao(acao_nome, setor_destino=setor_destino_acao)
        return _create_instance(
            SAC,
            numero=numero,
            ano=2099,
            sequencia_ano=sequencia,
            empresa=self.empresa,
            cliente=self.cliente,
            nota_fiscal=self.nota,
            status_inicial="Aberto",
            status_atual=status or self.status_aberto,
            acao_em_espera=acao,
            setor_responsavel=setor_atual,
            setor_atual=setor_atual,
            usuario_abertura=self.user,
            titulo=f"SAC {numero}",
        )

    def test_gestao_sac_exibe_alerta_quando_falta_fluxo(self):
        sac = self._criar_sac(
            numero="010/2099",
            setor_atual=self.setor_sac,
            acao_nome="Aguardando Emissão do Pedido (Entrada/Retorno)",
            setor_destino_acao=self.setor_sac,
            status=self.status_gestao,
            sequencia=10,
        )

        response = self.client.get(f"/sac/gestao/?sac={sac.id}")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fluxo não configurado")
        self.assertContains(response, "Gestão do SAC")

    def test_logistica_exibe_alerta_quando_falta_fluxo(self):
        sac = self._criar_sac(
            numero="011/2099",
            setor_atual=self.setor_logistica,
            acao_nome="Aguardando Coleta no Cliente",
            setor_destino_acao=self.setor_logistica,
            status=self.status_aberto,
            sequencia=11,
        )

        response = self.client.get(f"/sac/{sac.id}/gestao-logistica/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fluxo não configurado")
        self.assertContains(response, "Gestão Logística")

    def test_diretoria_exibe_alerta_quando_falta_fluxo(self):
        sac = self._criar_sac(
            numero="012/2099",
            setor_atual=self.setor_diretoria,
            acao_nome="Aguardando Aprovação de orçamento (Interno Diretoria)",
            setor_destino_acao=self.setor_diretoria,
            status=self.status_aberto,
            sequencia=12,
        )

        response = self.client.get(f"/sac/diretoria/?sac={sac.id}")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fluxo não configurado")
        self.assertContains(response, "Diretoria")

    def test_alerta_some_quando_fluxo_existe_na_gestao_sac(self):
        acao_atual = _criar_acao("Aguardando Emissão do Pedido (Saída)", setor_destino=self.setor_sac)
        proxima_acao = _criar_acao("Aguardando Emissão da Nota fiscal (Saída)", setor_destino=self.setor_logistica)
        _create_instance(
            FluxoAcaoSetor,
            acao_atual=acao_atual,
            setor_atual=self.setor_sac,
            proxima_acao=proxima_acao,
            proximo_setor=self.setor_logistica,
            ativo=True,
        )
        sac = _create_instance(
            SAC,
            numero="013/2099",
            ano=2099,
            sequencia_ano=13,
            empresa=self.empresa,
            cliente=self.cliente,
            nota_fiscal=self.nota,
            status_inicial="Aberto",
            status_atual=self.status_gestao,
            acao_em_espera=acao_atual,
            setor_responsavel=self.setor_sac,
            setor_atual=self.setor_sac,
            usuario_abertura=self.user,
            titulo="SAC 013/2099",
        )

        response = self.client.get(f"/sac/gestao/?sac={sac.id}")

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Fluxo não configurado")
