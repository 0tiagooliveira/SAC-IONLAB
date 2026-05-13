from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase

from core.models import AcaoEmEspera, Cliente, Empresa, NotaFiscal, SAC, Setor, StatusSAC


def _tem_campo(modelo, nome_campo: str) -> bool:
    return any(f.name == nome_campo for f in modelo._meta.get_fields())


def _criar_setor(nome: str, codigo: str):
    """Cria Setor mesmo quando o banco exigir coluna `ativo` que não está no model."""
    if _tem_campo(Setor, "ativo"):
        return Setor.objects.create(nome=nome, codigo=codigo, ativo=True)

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


class SmokeViewsAutenticadasTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="teste_smoke",
            password="12345678",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(self.user)

        self.setor = _criar_setor(nome="SAC", codigo="SAC")
        self.status = StatusSAC.objects.create(nome="Aberto", codigo="ABERTO", ativo=True)

        kwargs_acao = {"nome": "Aberto", "ativo": True}
        if _tem_campo(AcaoEmEspera, "setor_destino"):
            kwargs_acao["setor_destino"] = self.setor
        self.acao = AcaoEmEspera.objects.create(**kwargs_acao)

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
        self.sac = SAC.objects.create(
            numero="001/2099",
            ano=2099,
            sequencia_ano=1,
            empresa=self.empresa,
            cliente=self.cliente,
            nota_fiscal=self.nota,
            status_inicial="Aberto",
            status_atual=self.status,
            acao_em_espera=self.acao,
            setor_responsavel=self.setor,
            setor_atual=self.setor,
            usuario_abertura=self.user,
            titulo="SAC teste smoke",
        )

    def test_paginas_gerais_abrem_autenticadas(self):
        rotas = ["/intra/", "/sac/pesquisa/"]
        for rota in rotas:
            with self.subTest(rota=rota):
                resposta = self.client.get(rota)
                self.assertEqual(resposta.status_code, 200, msg=f"Rota {rota} retornou {resposta.status_code}")

    def test_paginas_dependentes_de_sac_abrem_com_sac_selecionado(self):
        rotas = [
            f"/sac/assessoria-cientifica/?sac={self.sac.id}",
            f"/sac/analise-comercial/?sac={self.sac.id}",
            f"/sac/gestao/?sac={self.sac.id}",
            f"/sac/gestao-logistica/?sac={self.sac.id}",
            f"/sac/diretoria/?sac={self.sac.id}",
        ]
        for rota in rotas:
            with self.subTest(rota=rota):
                resposta = self.client.get(rota)
                self.assertEqual(resposta.status_code, 200, msg=f"Rota {rota} retornou {resposta.status_code}")
