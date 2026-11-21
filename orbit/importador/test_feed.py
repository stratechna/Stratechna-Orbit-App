"""Testes da montagem do feed (F5.2). Sem frappe e sem base de dados.

Correr na raiz da app:  python -m unittest orbit.importador.test_feed
A prova de equivalência com o portal é o guião
orbit-scripts/inventario/portal/replay_feed.py (21-11-2026: JF 10 984/10 984
e stratechna.pt 19 977/19 977 iguais, 867 fusões); aqui fixam-se o stock, a
escolha do vencedor e a fusão por EAN e por referência+marca.
"""
import unittest
from decimal import Decimal

from orbit.importador import feed

TD, DEPAU = 10, 11
FORNECEDORES = {
    TD: {"nome": "TD Synnex", "estado": "activo", "na_loja": True, "prioridade": 1, "config": {}},
    DEPAU: {"nome": "Depau", "estado": "activo", "na_loja": True, "prioridade": 2, "config": {}},
    32: {"nome": "ALL.TO", "estado": "activo", "na_loja": False, "prioridade": None, "config": {}},
    40: {"nome": "Antigo", "estado": "inactivo", "na_loja": True, "prioridade": None, "config": {}},
}
DEFINICOES = {"estado_publicacao_default": "publicado", "publicar_sem_imagem_default": False,
              "estado_stock_zero_default": "esgotado"}


def linha(fid, ref, *, ean=None, custo="10", stock="5", preco="12.30", marca="HP", imagem=None,
          descricao="", **extra):
    dados = {"titulo": f"Artigo {ref}", "custo": custo, "stock": stock, "marca": marca,
             "imagem_url": imagem, "descricao": descricao}
    dados.update(extra.pop("dados", {}))
    p = {"fornecedor_id": fid, "produto_ref": ref, "ean": ean, "mpn": None, "dados": dados,
         "preco_pvp": Decimal(preco) if preco else None, "preco_regular": Decimal(preco) if preco else None,
         "preco_promocional": None, "preco_congelado": False}
    p.update(extra)
    return p


class HaStock(unittest.TestCase):
    def test_numeros(self):
        self.assertTrue(feed._ha_stock("3"))
        self.assertTrue(feed._ha_stock(2.5))
        self.assertTrue(feed._ha_stock("1,5"))
        self.assertFalse(feed._ha_stock("0"))
        self.assertFalse(feed._ha_stock(-1))

    def test_desconhecido(self):
        self.assertIsNone(feed._ha_stock(None))
        self.assertIsNone(feed._ha_stock("   "))

    def test_armazens_somam_o_minimo_de_cada_um(self):
        self.assertTrue(feed._ha_stock("Lisboa: 10-99 | Porto: -"))
        self.assertFalse(feed._ha_stock("Lisboa: - | Porto: -"))
        self.assertFalse(feed._ha_stock("Lisboa: 0 | Porto: 0-5"))

    def test_rotulos_negativos_antes_dos_afirmativos(self):
        self.assertFalse(feed._ha_stock("Indisponível"))  # contém «disponivel»
        self.assertFalse(feed._ha_stock("Sob consulta"))
        self.assertFalse(feed._ha_stock("Upon Request"))
        self.assertTrue(feed._ha_stock("Em stock"))
        self.assertTrue(feed._ha_stock("Stock Limitado"))
        self.assertTrue(feed._ha_stock("Delivery from Stock"))
        self.assertFalse(feed._ha_stock("brevemente"))


class Item(unittest.TestCase):
    def setUp(self):
        self.pub = feed._resolver_publicacao({}, DEFINICOES)

    def test_sem_imagem_vai_a_rascunho_e_sem_preco_fica_sob_encomenda(self):
        it = feed._construir_item_feed(dict(linha(TD, "A", preco=None), fornecedor_nome="TD"), self.pub)
        self.assertEqual(it["estado_publicacao"], "rascunho")
        self.assertTrue(it["preco_sob_consulta"])
        self.assertEqual(it["estado_stock"], "sob_encomenda")

    def test_stock_zero_segue_a_conta_e_tira_o_prazo(self):
        p = linha(TD, "A", stock="0", imagem="x.jpg", prazo_entrega="2 dias")
        it = feed._construir_item_feed(dict(p, fornecedor_nome="TD"), self.pub)
        self.assertEqual(it["estado_publicacao"], "publicado")
        self.assertEqual(it["estado_stock"], "esgotado")
        self.assertIsNone(it["prazo_entrega"])

    def test_sem_quantidade_e_so_por_encomenda(self):
        p = linha(TD, "A", stock=None, tipo_fornecimento="Apenas por encomenda")
        it = feed._construir_item_feed(dict(p, fornecedor_nome="TD"), self.pub)
        self.assertEqual(it["estado_stock"], "sob_encomenda")

    def test_ligacoes_para_fora_saem_da_descricao(self):
        html = '<p>Ver <a href="https://fornecedor.com/x">aqui</a> e <a href="https://youtu.be/v">vídeo</a></p>' \
               '<ul><li><a href="https://fornecedor.com/a.pdf">PDF</a></li></ul>'
        self.assertEqual(feed._sem_ligacoes_para_fora(html),
                         '<p>Ver aqui e <a href="https://youtu.be/v">vídeo</a></p>')


class Vencedor(unittest.TestCase):
    PRIO = {TD: 1, DEPAU: 2}

    def item(self, fid, ref, **kw):
        p = linha(fid, ref, **kw)
        return feed._construir_item_feed(dict(p, fornecedor_nome=FORNECEDORES[fid]["nome"]),
                                         feed._resolver_publicacao({}, DEFINICOES))

    def test_conteudo_do_mais_rico_e_preco_do_mais_barato_com_stock(self):
        td = self.item(TD, "X1", ean="0123", custo="9", stock="0")  # mais barata, sem stock
        dp = self.item(DEPAU, "X1", ean="0123", custo="11", stock="4", imagem="img.jpg")  # mais rica
        (v,) = feed._fundir_grupo([td, dp], self.PRIO)
        self.assertEqual(v["imagem_url"], "img.jpg")      # conteúdo da Depau
        self.assertEqual(v["fornecedor_id"], DEPAU)       # e a parte comercial também: é a única com stock
        self.assertNotIn("dados_de_fornecedor_id", v)
        self.assertEqual(v["fundidos"], [{"fornecedor_id": TD, "ref": "X1"}])

    def test_parte_comercial_de_outro_fornecedor(self):
        td = self.item(TD, "X1", ean="0123", custo="9", stock="3")
        dp = self.item(DEPAU, "X1", ean="0123", custo="11", stock="4", imagem="img.jpg")
        (v,) = feed._fundir_grupo([td, dp], self.PRIO)
        self.assertEqual(v["imagem_url"], "img.jpg")
        self.assertEqual((v["fornecedor_id"], v["custo"]), (TD, "9"))
        self.assertEqual(v["dados_de_fornecedor_id"], DEPAU)
        self.assertEqual(v["fundidos"], [{"fornecedor_id": DEPAU, "ref": "X1"}])

    def test_sem_stock_em_nenhum_vale_o_mais_barato(self):
        td = self.item(TD, "X1", ean="0123", custo="12", stock="0")
        dp = self.item(DEPAU, "X1", ean="0123", custo="11", stock="0")
        (v,) = feed._fundir_grupo([td, dp], self.PRIO)
        self.assertEqual(v["custo"], "11")

    def test_empate_de_riqueza_desempata_pela_prioridade(self):
        td = self.item(TD, "X1", ean="0123")
        dp = self.item(DEPAU, "X2", ean="0123")
        (v,) = feed._fundir_grupo([dp, td], self.PRIO)
        self.assertEqual(v["titulo"], "Artigo X1")

    def test_chave_repetida_no_mesmo_fornecedor_nao_funde(self):
        a, b = self.item(TD, "A", ean="5"), self.item(TD, "B", ean="5")
        self.assertEqual(feed._fundir_grupo([a, b], self.PRIO), [a, b])


class Fusao(unittest.TestCase):
    def ensaio(self, linhas):
        return feed.gerar_feed(linhas, FORNECEDORES, DEFINICOES)

    def test_por_ean(self):
        saida = self.ensaio([linha(TD, "T-1", ean="4006381333931"), linha(DEPAU, "D-9", ean="4006381333931")])
        self.assertEqual(len(saida), 1)

    def test_por_referencia_com_ean_deslocado(self):
        # a Depau publica 952050695630 onde a TD publica 095205069563
        saida = self.ensaio([linha(TD, "ST2000", ean="095205069563", marca="Seagate"),
                             linha(DEPAU, "ST2000", ean="952050695630", marca="Outra")])
        self.assertEqual(len(saida), 1)

    def test_por_referencia_e_mesma_marca_sem_ean_que_confirme(self):
        saida = self.ensaio([linha(TD, "WD80EFPX", ean="111", marca="HP INC"),
                             linha(DEPAU, "WD80EFPX", ean=None, marca="hp")])
        self.assertEqual(len(saida), 1)

    def test_referencia_igual_marcas_diferentes_nao_funde(self):
        saida = self.ensaio([linha(TD, "R1", ean="111", marca="WD"),
                             linha(DEPAU, "R1", ean="222", marca="Western Digital")])
        self.assertEqual(len(saida), 2)

    def test_fornecedores_fora_do_feed_ficam_de_fora(self):
        saida = self.ensaio([linha(32, "A"), linha(40, "B"), linha(TD, "C")])
        self.assertEqual([i["ref"] for i in saida], ["C"])

    def test_relacionados_por_matnr_e_por_recurso(self):
        linhas = [
            linha(TD, "A", preco="100", marca="HP", categoria_valor="c", dados={"_matnr_interno": "m-a",
                  "relacionados_crosssell": ["m-b", "nao-existe"]}),
            linha(TD, "B", preco="200", marca="HP", categoria_valor="c", dados={"_matnr_interno": "m-b"}),
            linha(TD, "C", preco="110", marca="Dell", categoria_valor="c"),
        ]
        a = {i["ref"]: i for i in self.ensaio(linhas)}["A"]
        self.assertEqual(a["cross_sell_refs"], ["B"])     # dado pelo fornecedor
        self.assertEqual(a["upsell_refs"], ["B"])         # recurso: mesma marca, 1,15×–3×
        self.assertTrue(a["relacionados_por_recurso"])
        self.assertNotIn("_categoria_valor_tmp", a)

    def test_documentos_so_com_copia_no_portal(self):
        defs = dict(DEFINICOES, documentos_alojados=[(TD, "https://f.com/a.pdf", "https://portal/x/a.pdf")],
                    portal_base_url="https://portal")
        p = linha(TD, "A", documentos=[{"url": "https://f.com/a.pdf", "tipo": "Data sheet"},
                                       {"url": "https://f.com/b.pdf"},
                                       {"url": "/api/v1/importador/docs/1/A/c.pdf"}])
        (it,) = feed.gerar_feed([p], FORNECEDORES, defs)
        self.assertEqual(it["documentos"], [
            {"url": "https://portal/x/a.pdf", "tipo": "Ficha Técnica", "url_origem": "https://f.com/a.pdf"},
            {"url": "https://portal/api/v1/importador/docs/1/A/c.pdf"},
        ])


if __name__ == "__main__":
    unittest.main()
