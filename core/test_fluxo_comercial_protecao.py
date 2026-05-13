from django.test import TestCase, Client
from django.urls import reverse, resolve
import inspect


class FluxoComercialProtecaoTests(TestCase):
    """Testes de proteção do Comercial.

    Objetivo: detectar regressões básicas sem alterar regras de negócio.
    Estes testes não validam decisão final de fluxo; eles protegem URL, view
    e campos/trechos essenciais usados pela regra Comercial atual.
    """

    def setUp(self):
        self.client = Client()

    def test_urls_comercial_resolvem_para_view(self):
        lista = reverse('analise_comercial_sac_lista')
        detalhe = reverse('analise_comercial_sac', kwargs={'sac_id': 999999})
        self.assertEqual(lista, '/sac/analise-comercial/')
        self.assertEqual(detalhe, '/sac/999999/analise-comercial/')
        self.assertEqual(resolve(lista).url_name, 'analise_comercial_sac_lista')
        self.assertEqual(resolve(detalhe).url_name, 'analise_comercial_sac')

    def test_lista_comercial_nao_retorna_erro_500(self):
        resposta = self.client.get(reverse('analise_comercial_sac_lista'))
        self.assertLess(resposta.status_code, 500)

    def test_detalhe_comercial_inexistente_nao_retorna_erro_500(self):
        resposta = self.client.get(reverse('analise_comercial_sac', kwargs={'sac_id': 999999}))
        self.assertLess(resposta.status_code, 500)

    def test_form_comercial_preserva_campos_criticos(self):
        from core.forms import AnaliseComercialSACForm
        form = AnaliseComercialSACForm()
        campos_obrigatorios = [
            'cliente_confirmou_pedido',
            'cliente_aceita_negociacao',
            'valor_desconto_pleiteado',
        ]
        for campo in campos_obrigatorios:
            self.assertIn(campo, form.fields)

    def test_view_comercial_preserva_trechos_criticos(self):
        from core.views_modular import views_comercial
        fonte = inspect.getsource(views_comercial)
        termos_criticos = [
            'cliente_confirmou_pedido',
            'cliente_aceita_negociacao',
            'valor_desconto_pleiteado',
            'fluxo_comercial_negociacao',
            'fluxo_comercial_sem_negociacao',
        ]
        for termo in termos_criticos:
            self.assertIn(termo, fonte)
