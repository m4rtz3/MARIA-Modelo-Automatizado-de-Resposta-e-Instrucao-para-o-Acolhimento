import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app import data_analysis


class FunctionCallingTests(unittest.TestCase):
    def test_feature_csvs_are_registered_and_summarized_in_small_chunks(self):
        conteudo = (
            "chave_linkage,vitima_gestante,vitima_idade_media,"
            "vitima_idade_min,vitima_idade_max\n"
            "pessoa_2020_a,1,25,20,30\n"
            "pessoa_2020_b,0,35,30,40\n"
            "pessoa_2021_a,1,45,40,50\n"
        )
        with TemporaryDirectory() as diretorio:
            arquivo = Path(diretorio) / "features_vitima.csv"
            arquivo.write_text(conteudo, encoding="utf-8")
            with (
                patch.object(data_analysis, "DADOS_BI_PATH", Path(diretorio)),
                patch.object(data_analysis, "_TAMANHO_BLOCO_CSV", 1),
                patch.object(data_analysis, "_dados", {}),
                patch.object(data_analysis, "_arquivos_csv", {}),
                patch.object(data_analysis, "_csvs_sob_demanda", {}),
                patch.object(data_analysis, "_colunas_csv", {}),
            ):
                data_analysis.carregar_datasets()
                resultado = data_analysis._consulta_vitima(2020)

        self.assertEqual(data_analysis._dados, {})
        self.assertIn("(filtrado para 2020: 2 pessoas)", resultado[0])
        self.assertTrue(any("Gestantes: 1 de 2 (50.0%)" in linha for linha in resultado))
        self.assertTrue(any("Idade média: 30.0 anos" in linha for linha in resultado))
        self.assertTrue(any("Idade mínima: 20 anos" in linha for linha in resultado))
        self.assertTrue(any("Idade máxima: 40 anos" in linha for linha in resultado))

    def test_individual_query_receives_dataset_category_and_year(self):
        function_call = SimpleNamespace(
            name="consultar_dados_individuais",
            args={
                "dataset": "MARIA_individual",
                "categoria": "faixa_etaria",
                "ano": 2020,
            },
        )
        response = SimpleNamespace(
            candidates=[
                SimpleNamespace(
                    content=SimpleNamespace(
                        parts=[SimpleNamespace(function_call=function_call)]
                    )
                )
            ]
        )
        modelo = SimpleNamespace(
            generate_content=Mock(return_value=response)
        )
        consulta = Mock(return_value=["Faixa etária: resultado agregado"])

        with (
            patch.object(data_analysis, "GenerativeModel", return_value=modelo),
            patch.object(
                data_analysis,
                "_chama_com_retry",
                side_effect=lambda chamada: chamada(),
            ),
            patch.dict(
                data_analysis._csvs_sob_demanda,
                {"MARIA_individual": Path("MARIA_individual.csv")},
            ),
            patch.dict(
                data_analysis._FERRAMENTAS_DADOS,
                {"consultar_dados_individuais": consulta},
            ),
        ):
            resultado = data_analysis.consultar_dados_via_function_calling(
                "Qual a distribuição por faixa etária em 2020?"
            )

        self.assertEqual(resultado, "Faixa etária: resultado agregado")
        consulta.assert_called_once_with(
            dataset="MARIA_individual",
            categoria="faixa_etaria",
            ano=2020,
        )


if __name__ == "__main__":
    unittest.main()
