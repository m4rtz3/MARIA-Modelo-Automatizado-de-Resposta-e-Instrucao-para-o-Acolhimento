import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from app import maria as maria_module


class DashboardContextTests(unittest.TestCase):
    def test_pergunta_sobre_dashboard_busca_kb_sem_desviar_para_csvs(self):
        pergunta = "Sobre os dashboards, o que pode me dizer sobre o dashboard de panorama?"
        texto_dashboard = "Detalhes do Panorama " + ("indicadores e gráficos. " * 30)

        with (
            patch.object(maria_module, "LIMIAR_SIMILARIDADE", 0.30),
            patch.object(
                maria_module,
                "decompoe_pergunta",
                new_callable=AsyncMock,
            ) as decompoe,
            patch.object(
                maria_module.kb,
                "chunks_dashboards",
                [{
                    "tipo": "dashboards",
                    "chunk_id": "panorama",
                    "titulo": "Painel 1: Panorama",
                    "texto": texto_dashboard,
                }],
            ),
            patch.object(
                maria_module,
                "busca_multipla",
                new_callable=AsyncMock,
            ) as busca_multipla,
            patch.object(
                maria_module,
                "pergunta_pede_dados_reais",
                return_value=True,
            ) as pede_dados,
            patch.object(
                maria_module,
                "consultar_dados_via_function_calling",
            ) as consulta_dados,
            patch.object(maria_module, "analisar_dados") as analisar_dados,
        ):
            prompt, _, _, absteve = asyncio.run(
                maria_module._preparar_prompt(pergunta, None, 3, False)
            )

        self.assertFalse(absteve)
        decompoe.assert_not_called()
        busca_multipla.assert_not_awaited()
        pede_dados.assert_not_called()
        consulta_dados.assert_not_called()
        analisar_dados.assert_not_called()
        self.assertIn(texto_dashboard, prompt)

    def test_carregamento_meta_tambem_disponibiliza_contexto_de_dashboards(self):
        knowledge_base = maria_module.kb.__class__()
        knowledge_base.carregar_meta_instrucao()

        panorama = [
            chunk for chunk in knowledge_base.chunks_dashboards
            if "panorama" in chunk["titulo"].lower()
        ]
        self.assertTrue(panorama)
        pergunta = (
            "E agora? Sobre os dashboards, o que pode me dizer "
            "sobre o dashboard de panorama?"
        )
        contextos = maria_module.selecionar_contexto_dashboard(
            pergunta,
            knowledge_base.chunks_dashboards,
        )
        texto = "\n".join(chunk["texto"] for chunk in contextos)
        self.assertIn("2.785.288", texto)
        self.assertIn("41.371", texto)
        self.assertIn("14,9", texto)
