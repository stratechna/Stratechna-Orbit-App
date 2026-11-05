"""Testes da faturação certificada (DP8). Sem rede e sem base de dados: o adaptador Moloni fala com um transporte
falso que devolve respostas no formato da API v1 (as mesmas que o portal vê em produção).

Testa-se sobretudo o que custa caro quando corre mal: emitir duas vezes a mesma fatura, mandar uma linha isenta sem
motivo, tomar uma lista de avisos do Moloni por sucesso, apagar um documento que já é fiscal.
"""
import json
import unittest
from urllib.parse import urlparse

from orbit.faturacao.adaptadores.moloni import Moloni, achatar
from orbit.faturacao.base import (Cliente, ErroFaturacao, Linha, Pedido, limpar_nif, nif_pt_valido, validar_pedido)


class _Resp:
    def __init__(self, dados, status=200):
        self._d, self.status_code, self.text = dados, status, json.dumps(dados)

    def json(self):
        return self._d


class Transporte:
    """Responde por endpoint (`invoices/insert`…). Guarda o que lhe foi enviado."""

    def __init__(self, rotas: dict):
        self.rotas, self.enviados, self.grants = rotas, [], []

    def get(self, url, params=None, timeout=None):
        self.grants.append(params)
        return _Resp({"access_token": "tok", "refresh_token": "ref", "expires_in": 3600})

    def post(self, url, params=None, data=None, timeout=None):
        ep = urlparse(url).path.split("/v1/")[1].strip("/")
        self.enviados.append((ep, data))
        r = self.rotas.get(ep, [])
        r = r(data) if callable(r) else r
        return r if isinstance(r, _Resp) else _Resp(r)

    def chamadas(self, ep):
        return [d for e, d in self.enviados if e == ep]


CFG = {"client_id": "c", "client_secret": "s", "utilizador": "u", "palavra_passe": "p", "empresa_id": "42",
       "serie_fatura": "A", "serie_nota_credito": "NC", "serie_recibo": "R", "prazo_id": "11",
       "metodo_pagamento_id": "22", "metodo_envio_id": "33", "categoria_id": "44", "unidade_id": "55"}

BASE = {
    "invoices/getAll": [],
    "customers/getByVat": [{"customer_id": 7}],
    "products/getByReference": [],
    "products/insert": {"valid": 1, "product_id": 99},
    "taxes/getAll": [{"tax_id": 1, "value": 23, "fiscal_zone": "PT"}, {"tax_id": 2, "value": 6, "fiscal_zone": "PT"},
                     {"tax_id": 9, "value": 23, "fiscal_zone": "PT-AC"}],
    "documentSets/getAll": [{"document_set_id": 5, "name": "A"}, {"document_set_id": 6, "name": "NC"}],
    "invoices/insert": {"valid": 1, "document_id": 1234},
    "documents/getOne": {"document_id": 1234, "status": 0, "number": 0, "gross_value": 123.0},
}


def pedido(**kw):
    base = dict(tipo="fatura", referencia="ACC-SINV-2026-00001", data="2026-11-05", vencimento="2026-12-05",
                cliente=Cliente(nome="Cliente Teste", nif="PT 123456789"),
                linhas=[Linha(codigo="SERV-1", nome="Serviço", quantidade=1, preco_unitario=100, taxa_iva=23)])
    base.update(kw)
    return Pedido(**base)


class TestBase(unittest.TestCase):
    def test_nif_perde_o_prefixo_antes_de_validar(self):
        self.assertEqual(limpar_nif("PT 123.456.789"), "123456789")
        self.assertTrue(nif_pt_valido("123456789"))
        self.assertFalse(nif_pt_valido("123456788"))
        self.assertFalse(nif_pt_valido("PT123456789"))

    def test_linha_isenta_sem_motivo_e_recusada(self):
        p = pedido(cliente=Cliente(nome="X", nif="123456789"),
                   linhas=[Linha(codigo="J", nome="Juros", quantidade=1, preco_unitario=5, taxa_iva=0)])
        with self.assertRaises(ErroFaturacao):
            validar_pedido(p)
        p.linhas[0].motivo_isencao = "M01"
        validar_pedido(p)

    def test_nota_de_credito_precisa_da_origem(self):
        with self.assertRaises(ErroFaturacao):
            validar_pedido(pedido(tipo="nota_credito", cliente=Cliente(nome="X", nif="123456789")))

    def test_achatar_a_moda_php(self):
        self.assertEqual(achatar({"products": [{"taxes": [{"tax_id": 3}]}], "n": 1}),
                         {"products[0][taxes][0][tax_id]": 3, "n": 1})


class TestMoloni(unittest.TestCase):
    def novo(self, **rotas):
        t = Transporte({**BASE, **rotas})
        guardados = []
        return Moloni(dict(CFG), guardar=guardados.append, transporte=t), t, guardados

    def test_emitir_rascunho(self):
        m, t, guardados = self.novo()
        p = pedido()
        r = m.emitir(p)
        self.assertEqual(r.estado, "rascunho")
        self.assertEqual(r.id_externo, "1234")
        corpo = t.chamadas("invoices/insert")[0]
        self.assertEqual(corpo["status"], 0)
        self.assertEqual(corpo["our_reference"], "ACC-SINV-2026-00001")
        self.assertEqual(corpo["company_id"], "42")
        self.assertEqual(corpo["document_set_id"], 5)
        self.assertEqual(corpo["products[0][taxes][0][tax_id]"], 1)       # 23 % do continente, não dos Açores
        self.assertEqual(corpo["products[0][product_id]"], 99)
        self.assertEqual((p.cliente.id_externo, p.linhas[0].id_externo), ("7", "99"))   # ficam para guardar
        self.assertTrue(guardados and guardados[0]["access_token"] == "tok")
        self.assertEqual(t.grants[0]["grant_type"], "password")

    def test_emitir_real_fecha(self):
        m, t, _ = self.novo(**{"documents/getOne": {"document_id": 1234, "status": 1, "number": 12,
                                                     "document_set": {"name": "A", "validation_code": "JJ3K"}}})
        r = m.emitir(pedido(rascunho=False))
        self.assertEqual(t.chamadas("invoices/insert")[0]["status"], 1)
        self.assertEqual((r.estado, r.numero, r.atcud), ("emitido", "A/12", "JJ3K-12"))

    def test_nao_emite_duas_vezes(self):
        m, t, _ = self.novo(**{"invoices/getAll": [{"document_id": 1234, "our_reference": "ACC-SINV-2026-00001"}]})
        r = m.emitir(pedido())
        self.assertTrue(r.ja_existia)
        self.assertEqual(t.chamadas("invoices/insert"), [])

    def test_lista_de_avisos_nao_e_sucesso(self):
        m, _, _ = self.novo(**{"invoices/insert": [{"code": "2 document_set_id", "description": "inválido"}]})
        with self.assertRaises(ErroFaturacao) as c:
            m.emitir(pedido())
        self.assertTrue(c.exception.permanente)

    def test_erro_do_servico_volta_a_tentar(self):
        m, _, _ = self.novo(**{"invoices/getAll": _Resp({}, status=503)})
        with self.assertRaises(ErroFaturacao) as c:
            m.emitir(pedido())
        self.assertFalse(c.exception.permanente)

    def test_nao_apaga_documento_fiscal(self):
        m, t, _ = self.novo(**{"documents/getOne": {"document_id": 1234, "status": 1, "number": 3}})
        with self.assertRaises(ErroFaturacao):
            m.apagar_rascunho("fatura", "1234")
        self.assertEqual(t.chamadas("invoices/delete"), [])

    def test_apaga_rascunho(self):
        m, t, _ = self.novo(**{"invoices/delete": {"valid": 1}})
        m.apagar_rascunho("fatura", "1234")
        self.assertEqual(t.chamadas("invoices/delete")[0]["document_id"], 1234)

    def test_linha_isenta_leva_motivo(self):
        m, t, _ = self.novo()
        m.emitir(pedido(linhas=[Linha(codigo="J", nome="Juros", quantidade=1, preco_unitario=5, taxa_iva=0,
                                      motivo_isencao="M01")]))
        corpo = t.chamadas("invoices/insert")[0]
        self.assertEqual(corpo["products[0][exemption_reason]"], "M01")
        self.assertNotIn("products[0][taxes][0][tax_id]", corpo)

    def test_cliente_novo_recebe_o_codigo_seguinte(self):
        m, t, _ = self.novo(**{"customers/getByVat": [],
                               "customers/getAll": lambda d: [{"number": "00041"}, {"number": "99999"}]
                               if d.get("offset") == 0 else [],
                               "customers/insert": {"valid": 1, "customer_id": 8}})
        m.emitir(pedido())
        novo = t.chamadas("customers/insert")[0]
        self.assertEqual(novo["number"], "00042")          # o 99999 (Consumidor Final) fica fora da sequência
        self.assertEqual(novo["vat"], "123456789")
        self.assertEqual(t.chamadas("invoices/insert")[0]["customer_id"], 8)

    def test_nota_de_credito_liga_a_origem(self):
        m, t, _ = self.novo(**{"creditNotes/getAll": [], "creditNotes/insert": {"valid": 1, "document_id": 77},
                               "products/getByReference": [{"product_id": 99, "reference": "SERV-1"}],
                               "documents/getOne": lambda d: {"document_id": d["document_id"], "status": 0,
                                                              "products": [{"product_id": 99,
                                                                            "document_product_id": 501}]}})
        m.emitir(pedido(tipo="nota_credito", origem_id_externo="1234", origem_valor=123, motivo="Devolução"))
        corpo = t.chamadas("creditNotes/insert")[0]
        self.assertEqual(corpo["associated_documents[0][associated_id]"], 1234)
        self.assertEqual(corpo["products[0][related_id]"], 501)
        self.assertEqual(corpo["document_set_id"], 6)
