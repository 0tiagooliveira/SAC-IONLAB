"""
Testes de protecao do fluxo/telas de Logistica do SAC.
Nao alteram regra de negocio. Servem para detectar erro 500/regressao futura.
"""

from django.test import TestCase, Client
from django.urls import reverse, NoReverseMatch
from django.contrib.auth import get_user_model


class FluxoLogisticaProtecaoSmokeTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_superuser(
            username="teste_logistica_protecao",
            email="teste_logistica@example.com",
            password="SenhaTeste123!",
        )
        self.client = Client()
        self.client.force_login(self.user)

    def _abrir(self, nomes_urls, caminhos):
        ultimo_erro = None
        for nome in nomes_urls:
            try:
                return self.client.get(reverse(nome), follow=True)
            except NoReverseMatch as exc:
                ultimo_erro = exc
        for caminho in caminhos:
            resp = self.client.get(caminho, follow=True)
            if resp.status_code != 404:
                return resp
        if ultimo_erro:
            self.fail(f"Nenhuma URL de Logistica encontrada. Ultimo erro: {ultimo_erro}")
        self.fail("Nenhuma URL de Logistica encontrada.")

    def test_tela_fila_logistica_nao_retorna_erro_500(self):
        resposta = self._abrir(
            nomes_urls=[
                "gestao_logistica",
                "sac_gestao_logistica",
                "logistica",
            ],
            caminhos=[
                "/sac/gestao-logistica/",
                "/sac/logistica/",
            ],
        )
        self.assertLess(resposta.status_code, 500)

    def test_dashboard_geral_nao_retorna_erro_500(self):
        resposta = self._abrir(
            nomes_urls=[
                "gestao_sac",
                "sac_gestao",
                "gestao",
            ],
            caminhos=[
                "/sac/gestao/",
                "/sac/",
            ],
        )
        self.assertLess(resposta.status_code, 500)
