from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django.test import TestCase

from core.models import AcaoEmEspera, Cliente, Empresa, FluxoAcaoSetor, NotaFiscal, SAC, Setor, StatusSAC
from core.services.fluxo_sac import diagnosticar_fluxo_inicial, obter_fluxo_dinamico
from core.services.sac_bridge import sac_aguardando_acao_comercial_queryset as _sac_aguarda_acao_comercial_queryset, sac_aguardando_acao_diretoria_queryset as _sac_aguardando_acao_diretoria_queryset


def _tem_campo(modelo, nome_campo: str) -> bool:
    return any(f.name == nome_campo for f in modelo._meta.get_fields())


def _criar_setor(nome, codigo=None):
    try:
        return Setor.objects.create(nome=nome, ativo=True)
    except TypeError:
        return Setor.objects.create(nome=nome)

    with connection.cursor() as cursor:
        try:
            cursor.execute(
                "INSERT INTO core_setor (nome, codigo, ativo) VALUES (%s, %s, %s) RETURNING id",
                [nome, codigo, True],
            )
            setor_id = cursor.fetchone()[0]
        except Exception:
            cursor.execute(
                "INSERT INTO core_setor (nome, codigo) VALUES (%s, %s) RETURNING id",
                [nome, codigo],
            )
            setor_id = cursor.fetchone()[0]
    return Setor.objects.get(pk=setor_id)


class FluxoAlertasEFilasTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="teste_fluxo_alerta",
            password="12345678",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(self.user)

        self.setor_sac = _criar_setor(nome="SAC", codigo="SAC")
        self.setor_comercial = _criar_setor(nome="Comercial", codigo="COMERCIAL")
        self.setor_arquivo = _criar_setor(nome="Arquivo", codigo="ARQUIVO")

        self.status_aberto = StatusSAC.objects.create(nome="Aberto", codigo="ABERTO", ativo=True)
        self.status_gestao = StatusSAC.objects.create(nome="Gestão do SAC", codigo="GESTAO_SAC", ativo=True)
        self.status_concluido = StatusSAC.objects.create(nome="Concluído", codigo="CONCLUIDO", ativo=True)

        self.empresa = Empresa.objects.create(codigo="EMP1", razao_social="Empresa Teste", ativo=True)
        self.cliente = Cliente.objects.create(
            empresa=self.empresa,
            codigo_interno="CLI1",
            razao_social="Cliente Teste",
            nome="Cliente Teste",
            ativo=True,
        )
        self.nota = NotaFiscal.objects.create(
            empresa=self.empresa,
            cliente=self.cliente,
            numero_nf="NF123",
            numero="NF123",
        )

    def test_diagnostico_avisa_quando_falta_fluxo_inicial(self):
        acao = AcaoEmEspera.objects.create(
            nome="Análise do Ocorrido - Comercial",
            setor_destino=self.setor_comercial,
            ativo=True,
        )
        sac = SAC.objects.create(
            numero="001/2099",
            ano=2099,
            sequencia_ano=1,
            empresa=self.empresa,
            cliente=self.cliente,
            nota_fiscal=self.nota,
            status_inicial="Aberto",
            status_atual=self.status_aberto,
            acao_em_espera=acao,
            setor_responsavel=self.setor_sac,
            setor_atual=None,
            usuario_abertura=self.user,
            titulo="SAC sem fluxo comercial",
        )

        alertas = diagnosticar_fluxo_inicial(sac, setor_contexto=self.setor_comercial, nome_tela="Gestão Comercial")

        self.assertEqual(len(alertas), 1)
        self.assertEqual(alertas[0]["titulo"], "Fluxo não configurado")
        self.assertIn("Análise do Ocorrido - Comercial", alertas[0]["mensagem"])
        self.assertIn("Comercial", alertas[0]["mensagem"])

    def test_fluxo_generico_cobre_quando_setor_atual_ausente(self):
        acao = AcaoEmEspera.objects.create(
            nome="Aguardando Emissão do Pedido (Saída)",
            setor_destino=self.setor_sac,
            ativo=True,
        )
        proxima = AcaoEmEspera.objects.create(
            nome="Aguardando Emissão da Nota fiscal (Saída)",
            setor_destino=self.setor_comercial,
            ativo=True,
        )
        FluxoAcaoSetor.objects.create(
            acao_atual=acao,
            setor_atual=None,
            proxima_acao=proxima,
            proximo_setor=self.setor_comercial,
            ativo=True,
        )

        fluxo = obter_fluxo_dinamico(acao, None)

        self.assertIsNotNone(fluxo)
        self.assertEqual(fluxo.proxima_acao_id, proxima.id)
        self.assertEqual(fluxo.proximo_setor_id, self.setor_comercial.id)

    def test_fila_comercial_considera_setor_destino_da_acao_quando_setor_atual_nulo(self):
        acao = AcaoEmEspera.objects.create(
            nome="Análise do Ocorrido - Comercial",
            setor_destino=self.setor_comercial,
            ativo=True,
        )
        sac = SAC.objects.create(
            numero="002/2099",
            ano=2099,
            sequencia_ano=2,
            empresa=self.empresa,
            cliente=self.cliente,
            nota_fiscal=self.nota,
            status_inicial="Aberto",
            status_atual=self.status_aberto,
            acao_em_espera=acao,
            setor_responsavel=self.setor_sac,
            setor_atual=None,
            usuario_abertura=self.user,
            titulo="SAC fila comercial",
        )

        ids = list(_sac_aguarda_acao_comercial_queryset().values_list("id", flat=True))
        self.assertIn(sac.id, ids)

    def test_view_comercial_exibe_alerta_quando_falta_fluxo(self):
        acao = AcaoEmEspera.objects.create(
            nome="Análise do Ocorrido - Comercial",
            setor_destino=self.setor_comercial,
            ativo=True,
        )
        sac = SAC.objects.create(
            numero="003/2099",
            ano=2099,
            sequencia_ano=3,
            empresa=self.empresa,
            cliente=self.cliente,
            nota_fiscal=self.nota,
            status_inicial="Aberto",
            status_atual=self.status_aberto,
            acao_em_espera=acao,
            setor_responsavel=self.setor_sac,
            setor_atual=None,
            usuario_abertura=self.user,
            titulo="SAC alerta tela comercial",
        )

        response = self.client.get(f"/sac/analise-comercial/?sac={sac.id}")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fluxo não configurado")
        self.assertContains(response, "Investigação do Ocorrido")
        self.assertContains(response, "Comercial")

    def test_auditar_sac_lista_combinacao_sem_fluxo(self):
        acao = AcaoEmEspera.objects.create(
            nome="Análise do Ocorrido - Comercial",
            setor_destino=self.setor_comercial,
            ativo=True,
        )
        sac = SAC.objects.create(
            numero="004/2099",
            ano=2099,
            sequencia_ano=4,
            empresa=self.empresa,
            cliente=self.cliente,
            nota_fiscal=self.nota,
            status_inicial="Aberto",
            status_atual=self.status_gestao,
            acao_em_espera=acao,
            setor_responsavel=self.setor_sac,
            setor_atual=None,
            usuario_abertura=self.user,
            titulo="SAC auditoria fluxo",
        )

        out = StringIO()
        call_command("auditar_sac", stdout=out)
        texto = out.getvalue()

        self.assertIn(f"SAC {sac.id}", texto)
        self.assertIn("Análise do Ocorrido - Comercial", texto)
        self.assertIn("Comercial", texto)

    def test_auditar_sac_nao_lista_quando_fluxo_existe(self):
        acao = AcaoEmEspera.objects.create(
            nome="Análise do Ocorrido - Comercial",
            setor_destino=self.setor_comercial,
            ativo=True,
        )
        proxima = AcaoEmEspera.objects.create(
            nome="Concluído",
            setor_destino=self.setor_arquivo,
            ativo=True,
        )
        FluxoAcaoSetor.objects.create(
            acao_atual=acao,
            setor_atual=self.setor_comercial,
            proxima_acao=proxima,
            proximo_setor=self.setor_arquivo,
            ativo=True,
        )
        sac = SAC.objects.create(
            numero="005/2099",
            ano=2099,
            sequencia_ano=5,
            empresa=self.empresa,
            cliente=self.cliente,
            nota_fiscal=self.nota,
            status_inicial="Aberto",
            status_atual=self.status_aberto,
            acao_em_espera=acao,
            setor_responsavel=self.setor_sac,
            setor_atual=None,
            usuario_abertura=self.user,
            titulo="SAC auditoria sem falha",
        )

        out = StringIO()
        call_command("auditar_sac", stdout=out)
        texto = out.getvalue()

        self.assertNotIn(f"SAC {sac.id}", texto)


class FilaDiretoriaEContextProcessorTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="teste_fila_diretoria",
            password="12345678",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(self.user)

        self.setor_sac = _criar_setor(nome="SAC", codigo="SAC")
        self.setor_diretoria = _criar_setor(nome="Diretoria", codigo="DIRETORIA")
        self.status_aberto = StatusSAC.objects.create(nome="Aberto", codigo="ABERTO", ativo=True)
        self.status_aprovacao = StatusSAC.objects.create(nome="Aguardando Aprovação de Desconto", codigo="APR_DESCONTO", ativo=True)

        self.empresa = Empresa.objects.create(codigo="EMP2", razao_social="Empresa Diretoria", ativo=True)
        self.cliente = Cliente.objects.create(
            empresa=self.empresa,
            codigo_interno="CLI2",
            razao_social="Cliente Diretoria",
            nome="Cliente Diretoria",
            ativo=True,
        )
        self.nota = NotaFiscal.objects.create(
            empresa=self.empresa,
            cliente=self.cliente,
            numero_nf="NF999",
            numero="NF999",
        )

    def test_fila_diretoria_considera_setor_destino_da_acao(self):
        acao = AcaoEmEspera.objects.create(
            nome="Aguardando Aprovação de Desconto",
            setor_destino=self.setor_diretoria,
            ativo=True,
        )
        sac = SAC.objects.create(
            numero="010/2099",
            ano=2099,
            sequencia_ano=10,
            empresa=self.empresa,
            cliente=self.cliente,
            nota_fiscal=self.nota,
            status_inicial="Aberto",
            status_atual=self.status_aprovacao,
            acao_em_espera=acao,
            setor_responsavel=self.setor_sac,
            setor_atual=None,
            usuario_abertura=self.user,
            titulo="SAC diretoria por setor destino",
        )

        ids = list(_sac_aguardando_acao_diretoria_queryset().values_list("id", flat=True))
        self.assertIn(sac.id, ids)

    def test_context_processor_expoe_numero_correto_do_sac(self):
        acao = AcaoEmEspera.objects.create(
            nome="Aguardando Aprovação de Desconto 2",
            setor_destino=self.setor_diretoria,
            ativo=True,
        )
        sac = SAC.objects.create(
            numero="011/2099",
            ano=2099,
            sequencia_ano=11,
            empresa=self.empresa,
            cliente=self.cliente,
            nota_fiscal=self.nota,
            status_inicial="Aberto",
            status_atual=self.status_aberto,
            acao_em_espera=acao,
            setor_responsavel=self.setor_sac,
            setor_atual=self.setor_diretoria,
            usuario_abertura=self.user,
            titulo="SAC diretoria context processor",
        )

        response = self.client.get("/sac/diretoria/")
        fila = response.context["fila_setorial_atual"]
        item = next((x for x in fila if x["id"] == sac.id), None)
        self.assertIsNotNone(item)
        self.assertEqual(item["numero_sac"], "011/2099")
