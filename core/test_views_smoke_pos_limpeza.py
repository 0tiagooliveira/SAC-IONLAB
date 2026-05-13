from django.test import TestCase, Client
from django.urls import reverse, NoReverseMatch


class SmokeViewsPosLimpezaTests(TestCase):
    """
    Testes de protecao basica: garantem que URLs principais continuam resolvendo
    e que chamadas simples nao explodem com erro 500 por import/sintaxe.
    Nao validam regra de negocio e nao alteram banco de producao.
    """

    def setUp(self):
        self.client = Client()

    def _try_get(self, url_name, fallback_path=None):
        try:
            url = reverse(url_name)
        except NoReverseMatch:
            if not fallback_path:
                self.skipTest(f"URL name nao encontrado: {url_name}")
            url = fallback_path
        response = self.client.get(url)
        self.assertNotEqual(response.status_code, 500, f"Erro 500 em {url}")

    def test_gestao_nao_retorna_erro_500(self):
        self._try_get("gestao_sac", "/sac/gestao/")

    def test_abertura_nao_retorna_erro_500(self):
        self._try_get("abrir_sac", "/sac/abrir/")

    def test_comercial_nao_retorna_erro_500(self):
        self._try_get("analise_comercial", "/sac/analise-comercial/")

    def test_logistica_nao_retorna_erro_500(self):
        self._try_get("gestao_logistica", "/sac/gestao-logistica/")

    def test_assessoria_nao_retorna_erro_500(self):
        self._try_get("assessoria_cientifica", "/sac/assessoria-cientifica/")

    def test_diretoria_nao_retorna_erro_500(self):
        self._try_get("diretoria", "/sac/diretoria/")
