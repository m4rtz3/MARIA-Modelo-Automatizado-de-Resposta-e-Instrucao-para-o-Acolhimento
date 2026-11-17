import unittest

from app.config import KB_PATH
from app.kb import chunk_hierarquico
from app.retrieval import SISTEMA_DECOMPOSICAO, TIPOS_KB


class CategoriasKnowledgeBaseTests(unittest.TestCase):
    def test_categorias_acompanham_os_blocos_atuais_da_kb(self):
        texto = KB_PATH.read_text(encoding="utf-8")
        chunks = chunk_hierarquico(texto)

        expectativas = {
            "BLOCO 5 |": "dashboards",
            "BLOCO 6 |": "meta_instrucao",
            "BLOCO 7 |": "orientacao_pratica",
        }
        for prefixo, tipo_esperado in expectativas.items():
            tipos = {
                chunk["tipo"]
                for chunk in chunks
                if chunk["bloco"].startswith(prefixo)
            }
            self.assertEqual(tipos, {tipo_esperado}, prefixo)

    def test_enriquecimento_csv_continua_como_dados_do_pipeline(self):
        chunks = chunk_hierarquico(
            "## BLOCO 7: ESTATÍSTICAS DO PIPELINE\n\n"
            "### Resumo\n\n"
            "Resumo agregado do pipeline para validar a categoria dos dados."
        )

        self.assertEqual({chunk["tipo"] for chunk in chunks}, {"pipeline_dados"})

    def test_roteador_conhece_e_descreve_a_categoria_de_dashboards(self):
        self.assertIn("dashboards", TIPOS_KB)
        self.assertIn("- dashboards:", SISTEMA_DECOMPOSICAO)


if __name__ == "__main__":
    unittest.main()