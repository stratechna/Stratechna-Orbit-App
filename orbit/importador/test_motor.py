"""Testes do motor do importador (F5.1). Sem frappe e sem base de dados.

Correr na raiz da app:  python -m unittest orbit.importador.test_motor
A prova de equivalência com o portal é o guião
orbit-scripts/inventario/portal/replay_motor.py; aqui fixam-se as regras que
custam dinheiro quando mudam sem querer (preços) e a identidade do produto.
"""
import unittest
from datetime import datetime, timezone

from orbit.importador import motor

RM_PRECOS = {  # a configuração real da RM Gastro (fornecedor 14) a 21-11-2026
    "pvp": {"base": "base_venda", "modo": "unica", "escaloes": [], "expressao": ""},
    "regular": {"base": "custo", "modo": "unica", "escaloes": [], "expressao": "+35%"},
}


class Expressao(unittest.TestCase):
    def test_vazia_devolve_a_base(self):
        self.assertEqual(motor._aplicar_expressao(100.0, ""), 100.0)
        self.assertEqual(motor._aplicar_expressao(100.0, None), 100.0)
        self.assertIsNone(motor._aplicar_expressao(None, "+10%"))

    def test_percentagens_e_euros_em_cadeia(self):
        self.assertAlmostEqual(motor._aplicar_expressao(100.0, "+35%"), 135.0)
        self.assertAlmostEqual(motor._aplicar_expressao(100.0, "-10%"), 90.0)
        self.assertAlmostEqual(motor._aplicar_expressao(100.0, "+10% +5€"), 115.0)
        self.assertAlmostEqual(motor._aplicar_expressao(100.0, "+5€ +10%"), 115.5)
        self.assertAlmostEqual(motor._aplicar_expressao(100.0, "+2,5%"), 102.5)

    def test_absoluto(self):
        # 21-11-2026: «=123,45» fixa o preço (corrigido no portal); «=123,45$» deixa de ser a forma
        self.assertEqual(motor._aplicar_expressao(10.0, "=123,45"), 123.45)
        self.assertEqual(motor._aplicar_expressao(None, "=123,45"), 123.45)
        self.assertEqual(motor._aplicar_expressao(10.0, "= 7"), 7.0)

    def test_dropship_lista(self):
        self.assertFalse(motor._dropshipping_proibido({"Dropshipping Permitido": ["Não"]}))
        self.assertTrue(motor._dropshipping_proibido({"Dropshipping Permitido": "Não"}))

    def test_escaloes(self):
        linha = {"modo": "escaloes", "escaloes": [
            {"ate": "100", "expressao": "+50%"},
            {"ate": "500", "expressao": "+30%"},
            {"ate": "", "expressao": "+20%"},
        ]}
        self.assertAlmostEqual(motor._calcular_linha_preco(linha, 100.0), 150.0)
        self.assertAlmostEqual(motor._calcular_linha_preco(linha, 200.0), 260.0)
        self.assertAlmostEqual(motor._calcular_linha_preco(linha, 1000.0), 1200.0)
        self.assertIsNone(motor._calcular_linha_preco(linha, None))


class Precos(unittest.TestCase):
    def test_cadeia_da_rm_gastro(self):
        p = motor._calcular_precos_produto(RM_PRECOS, None, 2527.33, None, False, 4837.0)
        self.assertEqual(p["custo_produto"], 2527.33)
        self.assertEqual(p["custo"], 2527.33)
        self.assertEqual(p["pvp"], 4837.0)
        self.assertAlmostEqual(p["regular"], 2527.33 * 1.35)
        self.assertIsNone(p["promocional"])  # «manual» por omissão

    def test_recargo_soma_depois_do_desconto(self):
        cfg = {"custo": {"base": "base", "modo": "unica", "expressao": "-10%"},
               "regular": {"base": "custo", "modo": "unica", "expressao": "+0%"}}
        p = motor._calcular_precos_produto(cfg, None, 100.0, 5.0, False)
        self.assertEqual(p["custo_produto"], 90.0)
        self.assertEqual(p["custo"], 95.0)
        self.assertAlmostEqual(p["regular"], 95.0)

    def test_excepcao_e_congelado(self):
        exc = {"expressao_regular": "+10%"}
        self.assertAlmostEqual(motor._calcular_precos_produto(RM_PRECOS, exc, 100.0, None, False)["regular"], 110.0)
        p = motor._calcular_precos_produto(RM_PRECOS, exc, 100.0, None, True)
        self.assertIsNone(p["pvp"])
        self.assertIsNone(p["regular"])
        self.assertEqual(p["custo"], 100.0)

    def test_parse_numero(self):
        self.assertEqual(motor._parse_numero("1.234,50 €"), 1234.5)
        self.assertEqual(motor._parse_numero("2527.33"), 2527.33)
        self.assertIsNone(motor._parse_numero(""))
        self.assertIsNone(motor._parse_numero("n/d"))


class Identidade(unittest.TestCase):
    def test_sku_depois_ean_depois_mpn(self):
        m = {"sku": "sku", "ean": "ean", "mpn": "mpn"}
        self.assertEqual(motor._resolver_identidade({"sku": " A1 ", "ean": "560", "mpn": "X"}, m), ("A1", "560", "X"))
        self.assertEqual(motor._resolver_identidade({"sku": "", "ean": "560", "mpn": "X"}, m), ("560", "560", "X"))
        self.assertEqual(motor._resolver_identidade({"sku": "", "ean": "", "mpn": "X"}, m), ("X", None, "X"))
        self.assertEqual(motor._resolver_identidade({"sku": "  "}, m), (None, None, None))

    def test_mapeamento_nulo(self):
        self.assertEqual(motor._resolver_identidade({"sku": "Z"}, {"sku": "sku", "ean": None, "mpn": None}), ("Z", None, None))


def _ctx(**extra):
    ctx = {
        "fornecedor": {"id": 14, "crm_account_id": "x", "config": {
            "campo_categoria": "category_key",
            "mapeamento_identidade": {"sku": "sku", "ean": None, "mpn": None},
            "mapeamento_campos": [
                {"campo_woo": "titulo", "como_aplicar": "traduzido", "campo_fornecedor": "name"},
                {"campo_woo": "custo", "como_aplicar": "directo", "campo_fornecedor": "partner_price"},
                {"campo_woo": "preco_base_venda", "como_aplicar": "directo", "campo_fornecedor": "pvp_fornecedor"},
            ],
            "precos": RM_PRECOS,
        }},
        "agora": datetime(2026, 11, 21, 15, 0, tzinfo=timezone.utc),
        "sync_run_id": None,
        "categorias": {"a": {"activo": True, "categorias_loja": ["Fornos"], "categorias_loja_ids": [7], "tags_loja": []},
                       "b": {"activo": False, "categorias_loja": [], "categorias_loja_ids": [], "tags_loja": []}},
        "existentes": {},
    }
    ctx.update(extra)
    return ctx


class Normalizar(unittest.TestCase):
    def test_categoria_inactiva_lista_negra_e_parcial(self):
        linhas = motor.converter_linhas_push([
            {"sku": "1", "name": "Oven", "category_key": "a", "partner_price": 100, "pvp_fornecedor": 180},
            {"sku": "2", "name": "Oven", "category_key": "b", "partner_price": 100},
            {"sku": "3", "name": "Oven", "category_key": "a"},
        ])
        r = motor.normalizar(linhas, _ctx(lista_negra=["3"]), parcial=False, finalizar=True, cobertura_completa=True)
        self.assertEqual([l["produto_ref"] for l in r["linhas"]], ["1"])
        self.assertEqual(r["ignoradas"]["categoria_nao_activa"], 1)
        self.assertEqual(r["ignoradas"]["lista_negra"], 1)
        l = r["linhas"][0]
        self.assertEqual(l["dados"]["custo"], "100")
        self.assertEqual(l["preco_pvp"], 180.0)
        self.assertAlmostEqual(l["preco_regular"], 135.0)
        self.assertEqual(l["categorias_loja_ids"], [7])
        self.assertEqual(l["pendente_ia"], ["titulo"])
        self.assertTrue(l["conteudo_mudou"])
        r2 = motor.normalizar(linhas[:1], _ctx(), parcial=True, finalizar=True, cobertura_completa=True)
        self.assertEqual(r2["linhas"], [])
        self.assertEqual(r2["ignoradas"]["parcial_produto_novo"], 1)

    def test_texto_traduzido_nao_e_reescrito_e_ausentes(self):
        existentes = {
            "1": {"dados": {"titulo": "Forno", "custo": "100", "preco_base_venda": "180"}, "campos_personalizados": {},
                  "atributos": {}, "atributos_locais": {}, "categorias_loja": ["Fornos"], "tags_loja": []},
            "9": {"dados": {"stock": "5"}},
        }
        linhas = motor.converter_linhas_push(
            [{"sku": "1", "name": "Oven", "category_key": "a", "partner_price": 100, "pvp_fornecedor": 180}])
        r = motor.normalizar(linhas, _ctx(existentes=existentes), parcial=False, finalizar=True, cobertura_completa=True)
        l = r["linhas"][0]
        self.assertEqual(l["dados"]["titulo"], "Forno")
        self.assertEqual(l["texto_bruto"], {"titulo": "Oven"})
        self.assertFalse(l["conteudo_mudou"])
        self.assertEqual(r["ausentes"], ["9"])  # 1 de 2 = 50 %, no limiar (não acima)
        self.assertEqual(motor.aplicar_ausencia(existentes["9"], _ctx()["agora"])["dados"]["stock"], "0")


if __name__ == "__main__":
    unittest.main()
