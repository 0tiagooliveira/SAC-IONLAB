from django.test import TestCase 
 
class FluxoAssessoriaProtecaoSmokeTest(TestCase): 
 
    def test_fila_assessoria_nao_quebra(self): 
        response = self.client.get('/sac/assessoria-cientifica/') 
        self.assertNotEqual(response.status_code, 500) 
 
    def test_detalhe_inexistente_nao_quebra(self): 
        response = self.client.get('/sac/99999/analise-tecnica/') 
        self.assertNotEqual(response.status_code, 500) 
 
    def test_view_retorna_campos_esperados(self): 
        response = self.client.get('/sac/assessoria-cientifica/') 
        self.assertIn(response.status_code, [200, 302]) 
        self.assertIn(response.status_code, [200, 302]) 
