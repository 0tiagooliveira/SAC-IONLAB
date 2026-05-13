from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import resolve


class FluxoDiretoriaProtecaoSmokeTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='teste_diretoria', password='123456')
        self.client.force_login(self.user)

    def test_url_diretoria_resolve_para_view(self):
        match = resolve('/sac/diretoria/')
        self.assertEqual(match.url_name, 'analise_diretoria')

    def test_fila_diretoria_nao_retorna_erro_500(self):
        response = self.client.get('/sac/diretoria/')
        self.assertNotEqual(response.status_code, 500)
        self.assertIn(response.status_code, [200, 302])

    def test_diretoria_com_sac_inexistente_nao_retorna_erro_500(self):
        response = self.client.get('/sac/diretoria/?sac=999999')
        self.assertNotEqual(response.status_code, 500)
        self.assertIn(response.status_code, [200, 302])

    def test_view_diretoria_preserva_pontos_criticos(self):
        import inspect
        from core.views_modular import views_diretoria

        fonte = inspect.getsource(views_diretoria)
        for termo in [
            'def analise_diretoria',
            'aplicar_transicao_sac',
            'is_aprovacao_desconto',
            'decisao_desconto',
            '_fluxo_preview_aprovado',
            '_fluxo_preview_reprovado',
        ]:
            self.assertIn(termo, fonte)
