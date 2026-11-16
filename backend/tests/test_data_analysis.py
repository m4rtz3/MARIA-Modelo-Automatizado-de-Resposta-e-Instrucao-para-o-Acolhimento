import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app import data_analysis


class FunctionCallingTests(unittest.TestCase):
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
