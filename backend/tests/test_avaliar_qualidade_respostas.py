import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "avaliar_qualidade_respostas.py"
spec = importlib.util.spec_from_file_location("avaliador", SCRIPT)
avaliador = importlib.util.module_from_spec(spec)
spec.loader.exec_module(avaliador)

class TestMetricasOffline(unittest.TestCase):
    def test_token_f1_identico(self):
        m = avaliador.token_scores("A Lei prevê 48 horas", "A Lei prevê 48 horas")
        self.assertEqual(m["token_f1"], 1.0)

    def test_token_f1_sem_intersecao(self):
        m = avaliador.token_scores("violência doméstica", "clima ensolarado")
        self.assertEqual(m["token_f1"], 0.0)

    def test_rouge_l_identico(self):
        self.assertEqual(avaliador.rouge_l("medidas protetivas urgentes", "medidas protetivas urgentes"), 1.0)

    def test_cobertura_pontos(self):
        media, detalhes = avaliador.cobertura_pontos(["Emergência policial: 190", "Ligue 180 para denúncias"], "Em emergência ligue 190. Para denúncias, use o Ligue 180.")
        self.assertGreater(media, 0.5)
        self.assertEqual(len(detalhes), 2)

    def test_abstencao_esperada_detectada(self):
        corpus=[{"id":"Q1","categoria":"x","pergunta":"q","resposta_referencia":"Não é possível determinar","pontos_essenciais":["Não é possível determinar"],"espera_abstencao":True}]
        respostas=[{"id":"Q1","resposta_avaliada":"Não é possível determinar essa informação."}]
        r=avaliador.avaliar(corpus,respostas)[0]
        self.assertTrue(r["abstencao_detectada_heuristicamente"])
        self.assertTrue(r["abstencao_compativel_heuristicamente"])

    def test_sem_resposta_nao_inventa_resultado(self):
        corpus=[{"id":"Q1","resposta_referencia":"x","pontos_essenciais":[]}]
        self.assertEqual(avaliador.avaliar(corpus,[{"id":"Q1","resposta_avaliada":""}]), [])

if __name__ == "__main__": unittest.main()
