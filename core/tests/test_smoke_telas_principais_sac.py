from django.test import TestCase, Client
from django.urls import reverse, NoReverseMatch


class SmokeTelasPrincipaisSacTest(TestCase):
    """Testes de proteção simples: não validam regra de negócio.

    Objetivo: detectar erro 500/URL quebrada nas telas principais do SAC.
    São conservadores: se a URL exigir login ou redirecionar, o teste aceita.
    """

    def setUp(self):
        self.client = Client()

    def _get_url(self, name=None, path=None, kwargs=None):
        if path:
            return path
        try:
            return reverse(name, kwargs=kwargs or {})
        except NoReverseMatch:
            self.skipTest(f"URL name não encontrado: {name}")

    def _assert_no_server_error(self, url):
        response = self.client.get(url)
        self.assertNotEqual(
            response.status_code,
            500,
            f"Tela retornou erro 500: {url}\nConteúdo inicial: {response.content[:500]!r}",
        )

    def test_dashboard_gestao_nao_retorna_500(self):
        self._assert_no_server_error('/sac/gestao/')

    def test_analise_comercial_nao_retorna_500(self):
        self._assert_no_server_error('/sac/analise-comercial/')

    def test_gestao_logistica_nao_retorna_500(self):
        self._assert_no_server_error('/sac/gestao-logistica/')

    def test_assessoria_cientifica_nao_retorna_500(self):
        self._assert_no_server_error('/sac/assessoria-cientifica/')

    def test_diretoria_nao_retorna_500(self):
        self._assert_no_server_error('/sac/diretoria/')

    def test_abertura_sac_nao_retorna_500(self):
        self._assert_no_server_error('/sac/abrir/')
