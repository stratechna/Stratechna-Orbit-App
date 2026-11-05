"""Adaptador Moloni (programa certificado AT n.º 1456) — C1 da DP8, 05-11-2026.

O que se sabe da API v1 vem do portal, que a usa há meses para a faturação da Stratechna
(backend/app/moloni_client.py), e foi aprendido à força:

- Pedidos POST em formulário «à PHP» (products[0][taxes][0][tax_id]=…), com `access_token` na query e
  `company_id` em todos.
- Uma inserção recusada NÃO dá erro HTTP: devolve 200 com uma LISTA de avisos de validação. Só um dict com
  `valid == 1` é sucesso.
- `customers/insert` exige `number` (o Moloni não atribui o seguinte: `"0"` grava mesmo zero), e
  `maturity_date_id`, `payment_method_id`, `delivery_method_id` reais da empresa — vêm da Ligacao.
- O `value` de uma taxa num produto é o MONTANTE, não a percentagem; a percentagem está em `tax.value`.
- `status: 0` cria um RASCUNHO (não é documento fiscal, não gasta numeração, pode apagar-se); `status: 1`
  fecha-o com o número definitivo — irreversível (só nota de crédito).
- 4xx (excepto 429) é erro dos dados: não se repete. Rede, 429 e 5xx repetem-se (a fila volta a tentar).
"""
from __future__ import annotations

import time
from typing import Optional

from orbit.faturacao.base import (CONSUMIDOR_FINAL, Adaptador, Cliente, ErroFaturacao, Linha, Pedido, Resultado,
                                  limpar_nif, registar, validar_pedido)

API = "https://api.moloni.pt/v1"
MODULO = {"fatura": "invoices", "fatura_recibo": "invoiceReceipts", "nota_credito": "creditNotes",
          "recibo": "receipts"}
PAISES = {"PT": 1, "ES": 70, "FR": 75, "DE": 56, "IT": 109, "GB": 230, "BR": 31}   # country_id do Moloni


def achatar(obj, prefixo: str = "") -> dict:
    """{"products": [{"taxes": [{"tax_id": 3}]}]} → {"products[0][taxes][0][tax_id]": 3}"""
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(achatar(v, f"{prefixo}[{k}]" if prefixo else str(k)))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            out.update(achatar(v, f"{prefixo}[{i}]"))
    else:
        out[prefixo] = obj
    return out


@registar
class Moloni(Adaptador):
    nome = "moloni"
    rotulo = "Moloni"

    def __init__(self, cfg, guardar=None, transporte=None):
        super().__init__(cfg, guardar, transporte)
        if self.transporte is None:
            import requests
            self.transporte = requests.Session()
        self._taxas: Optional[list] = None
        self._series: Optional[list] = None

    # ── autenticação ─────────────────────────────────────────────────────────

    def _grant(self, params: dict) -> str:
        r = self.transporte.get(f"{API}/grant/", params={"client_id": self.cfg.get("client_id"),
                                                         "client_secret": self.cfg.get("client_secret"), **params},
                                timeout=20)
        try:
            d = r.json()
        except ValueError:
            d = {}
        if "access_token" not in d:
            raise ErroFaturacao("o Moloni recusou as credenciais da ligação (verifique o utilizador de integração, "
                                "a palavra-passe e a app de programador)", permanente=True,
                                resposta={k: v for k, v in d.items() if k != "access_token"})
        self.cfg["access_token"] = d["access_token"]
        self.cfg["refresh_token"] = d.get("refresh_token") or self.cfg.get("refresh_token", "")
        self.cfg["token_expira"] = time.time() + int(d.get("expires_in", 3600))
        self.guardar({"access_token": self.cfg["access_token"], "refresh_token": self.cfg["refresh_token"],
                      "token_expira": self.cfg["token_expira"]})
        return d["access_token"]

    def _token(self, forcar: bool = False) -> str:
        if not forcar and self.cfg.get("access_token") and float(self.cfg.get("token_expira") or 0) > time.time() + 60:
            return self.cfg["access_token"]
        if self.cfg.get("refresh_token") and not forcar:
            try:
                return self._grant({"grant_type": "refresh_token", "refresh_token": self.cfg["refresh_token"]})
            except ErroFaturacao:
                pass   # refresh caducado: volta a entrar com o utilizador de integração
        return self._grant({"grant_type": "password", "username": self.cfg.get("utilizador"),
                            "password": self.cfg.get("palavra_passe")})

    def _post(self, endpoint: str, dados: Optional[dict] = None):
        corpo = achatar({"company_id": self.cfg.get("empresa_id"), **(dados or {})})
        url = f"{API}/{endpoint}/"
        for tentativa in (1, 2):
            try:
                r = self.transporte.post(url, params={"access_token": self._token(forcar=tentativa == 2)},
                                         data=corpo, timeout=30)
            except Exception as e:  # noqa: BLE001 — rede: a fila volta a tentar
                raise ErroFaturacao(f"Moloni {endpoint}: sem ligação ({e.__class__.__name__})", permanente=False)
            if r.status_code == 401 and tentativa == 1:
                continue
            if r.status_code == 429 or r.status_code >= 500:
                raise ErroFaturacao(f"Moloni {endpoint}: HTTP {r.status_code}", permanente=False)
            if r.status_code >= 400:
                raise ErroFaturacao(f"Moloni {endpoint}: HTTP {r.status_code} {r.text[:300]}", permanente=True)
            try:
                return r.json()
            except ValueError:
                raise ErroFaturacao(f"Moloni {endpoint}: resposta que não é JSON", permanente=False)
        raise ErroFaturacao(f"Moloni {endpoint}: token recusado duas vezes", permanente=True)

    @staticmethod
    def _valido(res, oque: str) -> dict:
        if isinstance(res, dict) and res.get("valid") == 1:
            return res
        avisos = res if isinstance(res, list) else [res]
        texto = "; ".join(str((a or {}).get("description") or a) if isinstance(a, dict) else str(a)
                          for a in avisos)[:500]
        raise ErroFaturacao(f"o Moloni recusou {oque}: {texto}", permanente=True, resposta=res)

    # ── leitura da empresa ───────────────────────────────────────────────────

    def testar_ligacao(self) -> dict:
        r = self._post("companies/getOne")
        if not isinstance(r, dict) or not r.get("company_id"):
            raise ErroFaturacao("o Moloni não devolveu a empresa — confirme o «ID da empresa»", resposta=r)
        return {"ok": True, "empresa": r.get("name"), "nif": r.get("vat")}

    def opcoes(self) -> dict:
        def lista(ep, campos):
            r = self._post(ep)
            return [{c: x.get(c) for c in campos} for x in (r if isinstance(r, list) else [])]
        return {
            "series": lista("documentSets/getAll", ("document_set_id", "name")),
            "taxas": lista("taxes/getAll", ("tax_id", "name", "value", "fiscal_zone", "saft_type")),
            "prazos": lista("maturityDates/getAll", ("maturity_date_id", "name", "days")),
            "metodos_pagamento": lista("paymentMethods/getAll", ("payment_method_id", "name")),
            "metodos_envio": lista("deliveryMethods/getAll", ("delivery_method_id", "name")),
            "unidades": lista("measurementUnits/getAll", ("unit_id", "name", "short_name")),
            "categorias": lista("productCategories/getAll", ("category_id", "name")),
        }

    def _serie(self, tipo: str) -> int:
        nome = (self.cfg.get(f"serie_{tipo}") or "").strip().upper()
        if not nome:
            raise ErroFaturacao(f"a ligação não tem série para «{tipo}»")
        if self._series is None:
            r = self._post("documentSets/getAll")
            self._series = r if isinstance(r, list) else []
        for s in self._series:
            if str(s.get("name", "")).strip().upper() == nome:
                return int(s["document_set_id"])
        raise ErroFaturacao(f"a série «{nome}» não existe no Moloni")

    def _taxa_id(self, pct: float) -> int:
        if self._taxas is None:
            r = self._post("taxes/getAll")
            self._taxas = r if isinstance(r, list) else []
        zona = (self.cfg.get("zona_fiscal") or "PT").upper()
        for t in self._taxas:
            if abs(float(t.get("value") or 0) - pct) < 0.001 and str(t.get("fiscal_zone") or "PT").upper() == zona:
                return int(t["tax_id"])
        raise ErroFaturacao(f"não há taxa de IVA de {pct:g} % (zona {zona}) no Moloni")

    # ── fichas ───────────────────────────────────────────────────────────────

    def _proximo_numero_cliente(self) -> str:
        """O Moloni não atribui o código: lê-se a sequência numérica da empresa (o 99999 do Consumidor Final fica
        de fora, como no portal)."""
        maior, offset = 0, 0
        while offset <= 5000:
            r = self._post("customers/getAll", {"qty": 50, "offset": offset})
            if not isinstance(r, list) or not r:
                break
            for c in r:
                n = str(c.get("number") or "").strip()
                if n.isdigit() and int(n) < 90000:
                    maior = max(maior, int(n))
            offset += 50
        return str(maior + 1).zfill(int(self.cfg.get("largura_codigo_cliente") or 5))

    def garantir_cliente(self, c: Cliente) -> str:
        if c.id_externo:
            return c.id_externo
        nif = limpar_nif(c.nif, c.pais) or CONSUMIDOR_FINAL
        ja = self._post("customers/getByVat", {"vat": nif})
        if isinstance(ja, list) and ja:
            return str(ja[0]["customer_id"])
        if nif == CONSUMIDOR_FINAL:
            raise ErroFaturacao("não existe a ficha «Consumidor Final» (999999990) no Moloni")
        for campo in ("prazo_id", "metodo_pagamento_id", "metodo_envio_id"):
            if not self.cfg.get(campo):
                raise ErroFaturacao(f"falta escolher «{campo}» na ligação (botão «Ler opções do programa»)")
        res = self._post("customers/insert", {
            "vat": nif, "number": self._proximo_numero_cliente(), "name": c.nome[:100], "email": c.email,
            "address": c.morada or "—", "zip_code": c.codigo_postal or "0000-000", "city": c.cidade or "—",
            "country_id": PAISES.get(c.pais.upper(), 1), "language_id": 1, "phone": c.telefone,
            "maturity_date_id": int(self.cfg["prazo_id"]), "payment_method_id": int(self.cfg["metodo_pagamento_id"]),
            "delivery_method_id": int(self.cfg["metodo_envio_id"]),
            "payment_day": 0, "discount": 0, "credit_limit": 0, "salesman_id": 0,
        })
        res = self._valido(res, f"o cliente {c.nome}")
        return str(res["customer_id"])

    def garantir_artigo(self, l: Linha) -> str:
        if l.id_externo:
            return l.id_externo
        ja = self._post("products/getByReference", {"reference": l.codigo, "exact": 1})
        if isinstance(ja, list):
            for p in ja:
                if str(p.get("reference")) == l.codigo:
                    return str(p["product_id"])
        for campo in ("categoria_id", "unidade_id"):
            if not self.cfg.get(campo):
                raise ErroFaturacao(f"falta escolher «{campo}» na ligação (botão «Ler opções do programa»)")
        corpo = {"category_id": int(self.cfg["categoria_id"]), "type": 2 if l.servico else 1, "name": l.nome[:200],
                 "reference": l.codigo[:50], "price": round(l.preco_unitario, 6), "unit_id": int(self.cfg["unidade_id"]),
                 "has_stock": 0, "summary": l.resumo[:200]}
        if l.taxa_iva > 0:
            corpo["taxes"] = [{"tax_id": self._taxa_id(l.taxa_iva), "order": 0, "cumulative": 0,
                               "value": round(l.preco_unitario * l.taxa_iva / 100, 4)}]
        else:
            corpo["exemption_reason"] = l.motivo_isencao
        res = self._valido(self._post("products/insert", corpo), f"o artigo {l.codigo}")
        return str(res["product_id"])

    # ── documentos ───────────────────────────────────────────────────────────

    def _linhas(self, p: Pedido, relacionados: Optional[dict] = None) -> list[dict]:
        out = []
        for i, l in enumerate(p.linhas):
            pid = self.garantir_artigo(l)
            l.id_externo = str(pid)
            linha = {"product_id": int(pid), "name": l.nome[:200], "summary": l.resumo[:200], "qty": l.quantidade,
                     "price": round(l.preco_unitario, 6), "discount": round(l.desconto_pct, 2), "order": i}
            if l.taxa_iva > 0:
                linha["taxes"] = [{"tax_id": self._taxa_id(l.taxa_iva)}]
            else:
                linha["exemption_reason"] = l.motivo_isencao
            if relacionados and str(pid) in relacionados:
                linha["related_id"] = relacionados[str(pid)]
            out.append(linha)
        return out

    @staticmethod
    def _total(p: Pedido) -> float:
        return round(sum(l.quantidade * l.preco_unitario * (1 - l.desconto_pct / 100) * (1 + l.taxa_iva / 100)
                         for l in p.linhas), 2)

    def _procurar_por_referencia(self, tipo: str, referencia: str) -> Optional[dict]:
        """Idempotência: o nome interno do Orbit vai em `our_reference`. Uma falha a meio (o Moloni gravou, a
        resposta perdeu-se) não pode dar duas faturas."""
        r = self._post(f"{MODULO[tipo]}/getAll", {"our_reference": referencia, "qty": 50})
        for d in (r if isinstance(r, list) else []):
            if str(d.get("our_reference") or "") == referencia:
                return d
        return None

    def _resultado(self, doc: dict, ja_existia: bool = False) -> Resultado:
        estado = {0: "rascunho", 1: "emitido"}.get(int(doc.get("status") or 0), "emitido")
        if doc.get("status") in (2, "2") or doc.get("canceled") in (1, "1"):
            estado = "anulado"
        numero = ""
        if doc.get("number"):
            serie = (doc.get("document_set") or {}).get("name") or doc.get("document_set_name") or ""
            numero = f"{serie}/{doc['number']}".strip("/")
        # O ATCUD = <código de validação da série>-<número>. O Moloni devolve-o em `atcud` nos documentos
        # recentes; se não vier, compõe-se a partir da série.
        atcud = doc.get("atcud") or ""
        if not atcud and doc.get("number"):
            cod = (doc.get("document_set") or {}).get("validation_code") or \
                  (doc.get("document_set") or {}).get("atcud_code") or ""
            atcud = f"{cod}-{doc['number']}" if cod else ""
        return Resultado(id_externo=str(doc.get("document_id")), numero=numero, atcud=atcud, estado=estado,
                         total=float(doc.get("gross_value") or doc.get("net_value") or 0), ja_existia=ja_existia,
                         bruto={k: doc.get(k) for k in ("document_id", "number", "status", "date", "gross_value",
                                                         "net_value", "our_reference", "customer_id")})

    def obter(self, tipo: str, id_externo: str) -> Resultado:
        r = self._post("documents/getOne", {"document_id": int(id_externo)})
        doc = r[0] if isinstance(r, list) and r else r
        if not isinstance(doc, dict) or not doc.get("document_id"):
            raise ErroFaturacao(f"o documento {id_externo} não existe no Moloni", resposta=r)
        return self._resultado(doc)

    def emitir(self, p: Pedido) -> Resultado:
        p.cliente.nif = limpar_nif(p.cliente.nif, p.cliente.pais)
        validar_pedido(p)
        ja = self._procurar_por_referencia(p.tipo, p.referencia)
        if ja:
            res = self.obter(p.tipo, str(ja["document_id"]))
            res.ja_existia = True
            return res
        cliente_id = int(self.garantir_cliente(p.cliente))
        p.cliente.id_externo = str(cliente_id)        # quem chama guarda-o, para não voltar a procurar
        relacionados = None
        corpo = {"document_set_id": self._serie(p.tipo), "customer_id": cliente_id, "date": p.data,
                 "expiration_date": p.vencimento or p.data, "our_reference": p.referencia[:60],
                 "notes": p.notas[:1000], "financial_discount": 0, "special_discount": 0,
                 "status": 0 if p.rascunho else 1}
        if self.cfg.get("prazo_id"):
            corpo["maturity_date_id"] = int(self.cfg["prazo_id"])
        if p.tipo == "nota_credito":
            origem = self._post("documents/getOne", {"document_id": int(p.origem_id_externo)})
            origem = origem[0] if isinstance(origem, list) and origem else origem
            relacionados = {str(x.get("product_id")): x.get("document_product_id")
                            for x in (origem or {}).get("products", []) if x.get("document_product_id")}
            corpo["associated_documents"] = [{"associated_id": int(p.origem_id_externo),
                                              "value": round(p.origem_valor or self._total(p), 2)}]
            if p.motivo:
                corpo["notes"] = (p.motivo + ("\n" + p.notas if p.notas else ""))[:1000]
        if p.tipo == "fatura_recibo":
            if not self.cfg.get("metodo_pagamento_id"):
                raise ErroFaturacao("falta o método de pagamento da ligação para emitir faturas-recibo")
            corpo["payments"] = [{"payment_method_id": int(self.cfg["metodo_pagamento_id"]), "date": p.data,
                                  "value": self._total(p)}]
        corpo["products"] = self._linhas(p, relacionados)
        res = self._valido(self._post(f"{MODULO[p.tipo]}/insert", corpo), f"o documento {p.referencia}")
        return self.obter(p.tipo, str(res["document_id"]))

    def apagar_rascunho(self, tipo: str, id_externo: str) -> None:
        atual = self.obter(tipo, id_externo)
        if atual.estado != "rascunho":
            raise ErroFaturacao(f"o documento {id_externo} já não é rascunho ({atual.estado}) — não se apaga; "
                                f"corrige-se com nota de crédito")
        self._valido(self._post(f"{MODULO[tipo]}/delete", {"document_id": int(id_externo)}),
                     f"apagar o rascunho {id_externo}")

    def obter_pdf(self, tipo: str, id_externo: str) -> str:
        r = self._post("documents/getPDFLink", {"document_id": int(id_externo), "signed": 0})
        url = (r or {}).get("url") if isinstance(r, dict) else None
        if not url:
            raise ErroFaturacao(f"o Moloni não deu o PDF do documento {id_externo}", permanente=False)
        return url

    def registar_pagamento(self, cliente_id, data, valor, documentos, referencia="", notas="", rascunho=False):
        if not self.cfg.get("metodo_pagamento_id"):
            raise ErroFaturacao("falta o método de pagamento da ligação para emitir recibos")
        corpo = {"document_set_id": self._serie("recibo"), "customer_id": int(cliente_id), "date": data,
                 "our_reference": referencia[:60], "notes": notas[:1000], "status": 0 if rascunho else 1,
                 "net_value": round(valor, 2),
                 "payments": [{"payment_method_id": int(self.cfg["metodo_pagamento_id"]), "date": data,
                               "value": round(valor, 2)}],
                 "associated_documents": [{"associated_id": int(d), "value": round(v, 2)} for d, v in documentos]}
        if referencia:
            ja = self._procurar_por_referencia("recibo", referencia)
            if ja:
                res = self.obter("recibo", str(ja["document_id"]))
                res.ja_existia = True
                return res
        res = self._valido(self._post("receipts/insert", corpo), f"o recibo {referencia}")
        return self.obter("recibo", str(res["document_id"]))

    def alterados_desde(self, desde: str) -> list[Resultado]:
        """Documentos mudados desde `desde` (AAAA-MM-DD HH:MM:SS): anulações e recibos feitos no próprio Moloni."""
        try:
            r = self._post("documents/getModifiedSince", {"lastmodified": desde})
        except ErroFaturacao as e:
            if not e.permanente:
                raise
            r = [d for d in (self._post("documents/getAll", {"qty": 50}) or [])
                 if str(d.get("lastmodified") or "") >= desde]
        return [self._resultado(d) for d in (r if isinstance(r, list) else []) if d.get("document_id")]
