import unittest
from unittest.mock import patch

from app import maria as maria_module


class MetaInstrucoesTests(unittest.TestCase):
    def test_system_prompt_inclui_meta_instrucoes_carregadas(self):
        instrucao = "Não misture os dados de fontes diferentes."

        with patch.object(
            maria_module.kb,
            "chunks_meta",
            [{"tipo": "meta_instrucao", "texto": instrucao}],
        ):
            prompt = maria_module._system_prompt_com_meta()

        self.assertIn(maria_module.SYSTEM_PROMPT, prompt)
        self.assertIn(instrucao, prompt)

    def test_system_prompt_preserva_fallback_sem_meta_instrucoes(self):
        with patch.object(maria_module.kb, "chunks_meta", []):
            prompt = maria_module._system_prompt_com_meta()

        self.assertEqual(prompt, maria_module.SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
