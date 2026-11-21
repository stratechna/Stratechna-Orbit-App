"""Feed da loja a partir do inventário (21-11-2026, docs/PLANO-INVENTARIO-IMPORTADOR-ORBIT.md F2).

Produz, para um canal, os produtos no MESMO formato do feed do importador do portal
(`_gerar_feed_para_conta_sync`), para que a Sync3 — com todas as suas regras (fusão, conflitos de SKU,
rascunhos) — possa um dia ler daqui sem mudar nada na Suite.

Base de cada produto: o item da loja que o espelho guardou (`orbit_dados_loja`). Por cima, o que o Orbit
decide (o inventário é o mestre):
| Campo do feed | Vem de |
|---|---|
| `preco_regular` | Item Price da lista do canal |
| `custo` | Item Price da lista de compra |
| `estado_stock`, `stock`, `prazo_entrega` | `disponibilidade.decidir` (stock próprio + oferta do fornecedor fresca) |
| `marca` | `orbit_fabricante` |
| `peso`, `comprimento`, `largura`, `altura` | artigo |
| `imagem_url`, `imagens_secundarias` | `orbit_imagens` |
| `estado_publicacao` | artigo desactivado → rascunho |

Quando o valor do Orbit é igual em significado ao da loja (5 e 5.0, «» e None), fica o original: a assinatura de
preço/stock da Sync3 compara texto, e uma diferença só de forma faria reenviar o catálogo inteiro.
"""
import gzip
import json
import re

import frappe
from frappe.utils import add_to_date, flt, get_datetime, now_datetime

from orbit.inventario.disponibilidade import decidir

ESTADO_FEED = {"Em stock": "instock", "Sob encomenda": "sob_encomenda", "Esgotado": "outofstock"}


def _igual(a, b) -> bool:
    if a in (None, "") and b in (None, ""):
        return True
    try:
        return abs(float(a) - float(b)) < 0.005
    except (TypeError, ValueError):
        return str(a).strip() == str(b).strip()


def _por(loja: dict, campo: str, valor) -> None:
    """Põe o valor do Orbit, a não ser que seja o mesmo da loja (fica o original)."""
    if not _igual(loja.get(campo), valor):
        loja[campo] = valor


def _carregar(canal) -> dict:
    """Tudo o que o feed precisa, em poucas consultas (11 mil artigos não podem ser 11 mil × 6 consultas)."""
    itens = frappe.get_all("Item", filters={"orbit_chave_importador": ["is", "set"]},
                           fields=["name", "disabled", "orbit_chave_importador", "orbit_fabricante", "weight_per_unit",
                                   "orbit_comprimento", "orbit_largura", "orbit_altura", "orbit_imagens",
                                   "orbit_dados_loja"])
    precos = {r.item_code: r.price_list_rate for r in frappe.get_all(
        "Item Price", filters={"price_list": canal.lista_precos}, fields=["item_code", "price_list_rate"])} \
        if canal.lista_precos else {}
    lista_compra = frappe.db.get_single_value("Buying Settings", "buying_price_list") or "Standard Buying"
    custos = {r.item_code: r.price_list_rate for r in frappe.get_all(
        "Item Price", filters={"price_list": lista_compra}, fields=["item_code", "price_list_rate"])}
    armazens = [a.warehouse for a in canal.armazens]
    proprio = {}
    if armazens:
        for r in frappe.db.sql("""select item_code, sum(actual_qty - reserved_qty) q from `tabBin`
                                  where warehouse in %s group by item_code""", (tuple(armazens),), as_dict=True):
            proprio[r.item_code] = max(0.0, flt(r.q))
    sup = {s.name: s for s in frappe.get_all("Supplier", filters={"orbit_importador_id": [">", 0]},
                                             fields=["name", "orbit_vende_com_stock", "orbit_frescura_horas",
                                                     "orbit_margem_stock"])}
    agora = now_datetime()
    ofertas = {}
    for o in frappe.get_all("Oferta do Fornecedor", filters={"activa": 1, "pode_vender": 1,
                                                            "ausente_desde": ["is", "not set"]},
                            fields=["item_code", "supplier", "quantidade", "quantidade_conhecida", "estado_stock",
                                    "lida_em", "prazo_entrega"]):
        s = sup.get(o.supplier) or frappe._dict()
        if s.get("orbit_vende_com_stock") == 0:
            continue
        horas = int(s.get("orbit_frescura_horas") or 12)
        fresca = bool(o.lida_em) and get_datetime(o.lida_em) >= add_to_date(agora, hours=-horas)
        qtd = None
        if o.quantidade_conhecida:
            qtd = max(0.0, flt(o.quantidade) - int(s.get("orbit_margem_stock") or 0)) if fresca else 0.0
        ofertas.setdefault(o.item_code, []).append({"qtd": qtd, "fresca": fresca, "estado": o.estado_stock,
                                                    "prazo": o.prazo_entrega})
    return {"itens": itens, "precos": precos, "custos": custos, "proprio": proprio, "ofertas": ofertas}


def produto(it, canal, dados: dict) -> dict | None:
    try:
        loja = json.loads(it.orbit_dados_loja or "{}")
    except ValueError:
        return None
    if not loja:
        return None
    if it.name in dados["precos"] and not loja.get("preco_sob_consulta"):
        _por(loja, "preco_regular", dados["precos"][it.name])
    if it.name in dados["custos"]:
        _por(loja, "custo", dados["custos"][it.name])
    d = decidir(dados["proprio"].get(it.name, 0.0), dados["ofertas"].get(it.name, []), canal.modo_stock)
    estado = ESTADO_FEED[d["estado"]]
    mesmo_estado = loja.get("estado_stock") == estado
    _por(loja, "estado_stock", estado)
    if mesmo_estado and estado != "instock":
        pass   # fora de stock com o mesmo estado: fica o stock da loja (o portal manda None, não 0)
    elif d["quantidade"] is not None:
        _por(loja, "stock", d["quantidade"])
    elif not mesmo_estado:
        loja["stock"] = None
    if estado == "instock":
        if d["prazo"] and not _igual(loja.get("prazo_entrega_com_preco") or loja.get("prazo_entrega"), d["prazo"]):
            loja["prazo_entrega"] = d["prazo"]
    else:
        loja["prazo_entrega"] = None if not mesmo_estado else loja.get("prazo_entrega")
    if loja.get("estado_stock_com_preco") and not loja.get("preco_sob_consulta"):
        loja["estado_stock_com_preco"] = loja["estado_stock"]
    if it.orbit_fabricante:
        _por(loja, "marca", it.orbit_fabricante)
    for campo, valor in (("peso", it.weight_per_unit), ("comprimento", it.orbit_comprimento),
                         ("largura", it.orbit_largura), ("altura", it.orbit_altura)):
        if valor:
            _por(loja, campo, valor)
    imagens = [u for u in (it.orbit_imagens or "").splitlines() if u.strip()]
    if imagens:
        _por(loja, "imagem_url", imagens[0])
        if [u for u in (loja.get("imagens_secundarias") or [])] != imagens[1:]:
            loja["imagens_secundarias"] = imagens[1:]
    if it.disabled and loja.get("estado_publicacao") == "publicado":
        loja["estado_publicacao"] = "rascunho"
    return loja


def feed(canal: str) -> list:
    c = frappe.get_doc("Canal de Venda", canal)
    dados = _carregar(c)
    out = []
    for it in dados["itens"]:
        p = produto(it, c, dados)
        if p:
            out.append(p)
    return out


def exportar_ficheiro(canal: str, caminho: str) -> dict:
    """Para a ponte: escreve o feed do canal em gzip no /tmp do contentor."""
    if not re.fullmatch(r"/tmp/orbit-feed-[A-Za-z0-9_-]+\.json\.gz", caminho or ""):
        return {"ok": False, "erro": "caminho inválido"}
    if not frappe.db.exists("Canal de Venda", canal):
        return {"ok": False, "erro": "canal inexistente"}
    produtos = feed(canal)
    with gzip.open(caminho, "wt", encoding="utf-8") as f:
        json.dump({"canal": canal, "gerado_em": str(now_datetime()), "produtos": produtos}, f, ensure_ascii=False, default=str)
    return {"ok": True, "produtos": len(produtos)}
