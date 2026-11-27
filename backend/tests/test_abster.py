import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch

from app import maria as maria_module


class AbstencaoTests(unittest.TestCase):
    def executar_maria(
        self,
        score_max,
        *,
        trivial=False,
        contextos_extra=None,
        pede_dados=False,
        limiar=0.30,
    ):
        contextos = (
            [{"tipo": "legislacao", "sim": score_max, "titulo": "Trecho", "texto": "Texto"}]
            if score_max is not None
            else []
        )
        contextos.extend(contextos_extra or [])

        with (
            patch.object(maria_module, "LIMIAR_SIMILARIDADE", limiar),
            patch.object(maria_module, "_eh_mensagem_trivial", return_value=trivial),
            patch.object(
                maria_module,
                "decompoe_pergunta",
                new_callable=AsyncMock,
                return_value=[{"tipo": "legislacao", "pergunta": "pergunta"}],
            ),
            patch.object(
                maria_module,
                "busca_multipla",
                new_callable=AsyncMock,
                return_value=contextos,
            ),
            patch.object(
                maria_module,
                "pergunta_pede_dados_reais",
                return_value=pede_dados,
            ),
            patch.object(
                maria_module,
                "consultar_dados_via_function_calling",
                return_value="Resultado ao vivo",
            ),
            patch.object(maria_module, "analisar_dados", return_value=""),
            patch.object(
                maria_module,
                "llm",
                return_value="Resposta do modelo",
            ) as llm_mock,
        ):
            resultado = asyncio.run(maria_module.maria("pergunta"))

        return resultado, llm_mock

    def test_alta_relevancia_nao_abstem(self):
        resultado, llm_mock = self.executar_maria(0.75)

        self.assertFalse(resultado["absteve"])
        self.assertEqual(resultado["score_max_recuperacao"], 0.75)
        llm_mock.assert_called_once()

    def test_relevancia_abaixo_do_limiar_abstem_sem_chamar_llm(self):
        resultado, llm_mock = self.executar_maria(0.20)

        self.assertTrue(resultado["absteve"])
        self.assertEqual(resultado["resposta"], maria_module.RESPOSTA_ABSTENCAO)
        self.assertEqual(resultado["score_max_recuperacao"], 0.20)
        llm_mock.assert_not_called()

    def test_saudacao_trivial_nao_abstem(self):
        resultado, llm_mock = self.executar_maria(0.20, trivial=True)

        self.assertFalse(resultado["absteve"])
        self.assertEqual(resultado["score_max_recuperacao"], 1.0)
        llm_mock.assert_not_called()

    def test_obrigado_responde_diretamente_sem_llm(self):
        with patch.object(maria_module, "llm") as llm_mock:
            resultado = asyncio.run(maria_module.maria("Muito obrigado pela ajuda!"))

        self.assertFalse(resultado["absteve"])
        self.assertEqual(resultado["score_max_recuperacao"], 1.0)
        self.assertIn("De nada", resultado["resposta"])
        llm_mock.assert_not_called()

    def test_obrigado_stream_responde_diretamente_sem_llm_stream(self):
        with patch.object(maria_module, "llm_stream") as llm_stream_mock:
            fragmentos, _, score_max, absteve = asyncio.run(
                maria_module.maria_stream("Obrigada!")
            )

        self.assertEqual(list(fragmentos), [
            "De nada! Estou aqui para ajudar. "
        ])
        self.assertEqual(score_max, 1.0)
        self.assertFalse(absteve)
        llm_stream_mock.assert_not_called()

    def test_consulta_a_dados_sem_contexto_kb_nao_abstem(self):
        resultado, llm_mock = self.executar_maria(
            None,
            pede_dados=True,
            contextos_extra=[
                {
                    "tipo": "consulta_dados",
                    "sim": 1.0,
                    "titulo": "Consulta ao vivo",
                    "texto": "Resultado ao vivo",
                }
            ],
        )

        self.assertFalse(resultado["absteve"])
        self.assertEqual(resultado["score_max_recuperacao"], 0.0)
        llm_mock.assert_called_once()

    def test_limiar_zero_desativa_abstencao(self):
        resultado, llm_mock = self.executar_maria(0.20, limiar=0.0)

        self.assertFalse(resultado["absteve"])
        self.assertEqual(resultado["score_max_recuperacao"], 0.20)
        llm_mock.assert_called_once()

    def test_stream_abstencao_nao_chama_llm_stream(self):
        with (
            patch.object(maria_module, "LIMIAR_SIMILARIDADE", 0.30),
            patch.object(maria_module, "_eh_mensagem_trivial", return_value=False),
            patch.object(
                maria_module,
                "decompoe_pergunta",
                new_callable=AsyncMock,
                return_value=[{"tipo": "legislacao", "pergunta": "pergunta"}],
            ),
            patch.object(
                maria_module,
                "busca_multipla",
                new_callable=AsyncMock,
                return_value=[
                    {
                        "tipo": "legislacao",
                        "sim": 0.20,
                        "titulo": "Trecho",
                        "texto": "Texto",
                    }
                ],
            ),
            patch.object(
                maria_module,
                "pergunta_pede_dados_reais",
                return_value=False,
            ),
            patch.object(maria_module, "llm_stream") as llm_stream_mock,
        ):
            fragmentos, localizacao, score_max, absteve = asyncio.run(
                maria_module.maria_stream("pergunta")
            )

        self.assertEqual(list(fragmentos), [maria_module.RESPOSTA_ABSTENCAO])
        self.assertIsNone(localizacao)
        self.assertEqual(score_max, 0.20)
        self.assertTrue(absteve)
        llm_stream_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
