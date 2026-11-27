import asyncio
import unicodedata
import unittest
from unittest.mock import AsyncMock, patch

from app import data_analysis
from app import maria as maria_module
from app.config import DADOS_BI_PATH
from app.retrieval import TIPOS_KB


class RegressaoQualidadeTests(unittest.TestCase):
    def test_prompt_nao_anuncia_quatro_ou_cinco_tipos_obsoletos(self):
        texto = maria_module.SYSTEM_PROMPT + "\n" + maria_module.CONTEXTO_FIXO
        texto = texto.lower()
        self.assertNotIn("dos 5 tipos", texto)
        self.assertIn("todas as categorias pertinentes", texto)
        texto_sem_acento = "".join(
            c for c in unicodedata.normalize("NFD", texto)
            if unicodedata.category(c) != "Mn"
        )
        self.assertIn("vicaria:", texto_sem_acento)

    def test_categoria_legislacao_nao_descreve_cinco_tipos(self):
        descricao = TIPOS_KB["legislacao"].lower()
        self.assertNotIn("os 5 tipos", descricao)
        self.assertIn("violência vicária", descricao)

    def test_consulta_vitima_retoma_gestacao_aggregada_por_chave(self):
        data_analysis.carregar_datasets()
        linhas = data_analysis._consulta_vitima()
        texto = "\n".join(linhas)
        self.assertTrue("46.909" in texto or "46,909" in texto)
        self.assertIn("12.9%", texto)

    def test_consulta_dataset_geral_retorna_chaves_consolidadas(self):
        data_analysis.carregar_datasets()
        linhas = data_analysis._consulta_dataset_geral()
        texto = "\n".join(linhas)
        self.assertIn("363,522", texto)
        self.assertIn("chaves compostas distintas", texto)
        self.assertIn("não são pessoas individuais", texto)

    def test_distribuicao_risco_e_extraida_da_kb_sem_constante_no_codigo(self):
        linhas = data_analysis._consulta_distribuicao_risco()
        texto = "\n".join(linhas)
        self.assertIn("Basal", texto)
        self.assertIn("140.388", texto)
        self.assertIn("Moderado", texto)
        self.assertIn("201.979", texto)
        self.assertIn("Alto", texto)
        self.assertIn("21.155", texto)

    def test_texto_de_abstencao_semantica_e_marcado(self):
        resposta = "Não há dados disponíveis para essa previsão futura."
        self.assertTrue(maria_module._resposta_indica_abstencao(resposta))
        resposta_sem_acesso = "Não tenho acesso nem registro de nomes pessoais."
        self.assertTrue(maria_module._resposta_indica_abstencao(resposta_sem_acesso))

    def test_chunk_numerico_pipeline_e_datasenado_fica_completo_no_prompt(self):
        contextos = [
            {
                "tipo": "pipeline_dados",
                "sim": 0.70,
                "titulo": "Distribuição",
                "texto": "Basal: 140.388; Moderado: 201.979; Alto: 21.155",
            },
            {
                "tipo": "datasenado",
                "sim": 0.75,
                "titulo": "Prevalência",
                "texto": "27% ao longo da vida; 4% nos últimos 12 meses",
            },
        ]
        with (
            patch.object(maria_module, "_eh_mensagem_trivial", return_value=False),
            patch.object(maria_module, "_eh_pergunta_sobre_dashboard", return_value=False),
            patch.object(maria_module, "extrair_localizacao", return_value=None),
            patch.object(
                maria_module,
                "decompoe_pergunta",
                new_callable=AsyncMock,
                return_value=[{"tipo": "pipeline_dados", "pergunta": "distribuição"}],
            ),
            patch.object(
                maria_module,
                "busca_multipla",
                new_callable=AsyncMock,
                return_value=contextos,
            ),
            patch.object(maria_module, "pergunta_pede_dados_reais", return_value=False),
        ):
            prompt, _, _, absteve = asyncio.run(
                maria_module._preparar_prompt("qual a distribuição?", [], 3, False)
            )
        self.assertFalse(absteve)
        self.assertIn("140.388", prompt)
        self.assertIn("21.155", prompt)
        self.assertIn("27%", prompt)
        self.assertIn("4%", prompt)


if __name__ == "__main__":
    unittest.main()
