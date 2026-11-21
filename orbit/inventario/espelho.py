"""Espelho do importador do portal no inventário do Orbit (21-11-2026, docs/PLANO-INVENTARIO-IMPORTADOR-ORBIT.md F1).

O portal continua a ser quem manda nas lojas. Em cada volta manda para aqui, em lotes, o mesmo feed (já
fundido) que a Sync3 leva à loja; aqui fica em artigos, preços e ofertas de fornecedor, só para comparar.
Nada daqui volta à loja enquanto o canal estiver com «A loja recebe do» = Portal.

| Feed | Orbit |
|---|---|
| produto (fornecedor, ref) | **Item** pela `orbit_chave_importador`; código = o SKU público da loja |
| marca do fabricante | `orbit_fabricante` → **Manufacturer** (a Brand do artigo é a marca do negócio, do canal) |
| 1.ª categoria da loja | **Item Group** dentro de «Loja online» |
| EAN | **Item Barcode** (se ainda não for de outro artigo) |
| preço regular | **Item Price** na lista do canal |
| custo | **Item Price** na lista de compra por omissão |
| fornecedor, quantidade, estado, prazo, custo | **Oferta do Fornecedor** (não mexe no livro de stock) |
| saiu do feed (volta final) | oferta com «Fora do fornecedor desde»; o artigo fica (como na loja: rascunho, nunca apagado) |

Chega pela ponte do Apps02 (`inventario-espelho <slug>`, dados no stdin): é entrada, não instrução — só estes
campos, com tamanhos limitados.
"""
import gzip
import json
import re

import frappe
from frappe.utils import cint, flt, getdate, now_datetime

RAIZ_GRUPO = "Loja online"
ESTADOS = {"em_stock": "Em stock", "disponivel": "Em stock", "sob_encomenda": "Sob encomenda",
           "esgotado": "Esgotado", "sem_stock": "Esgotado"}


def _l(v, n=140) -> str:
    return (str(v) if v is not None else "").strip()[:n]


def _num(v):
    try:
        return float(str(v).replace(",", ".")) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


# ── referências que se criam quando faltam ─────────────────────────────────────────────────────────────────
def _raiz_grupos() -> str:
    raiz = frappe.db.get_value("Item Group", {"lft": 1}, "name") or frappe.db.get_value(
        "Item Group", {"parent_item_group": ["in", ["", None]], "is_group": 1}, "name")
    if not frappe.db.exists("Item Group", RAIZ_GRUPO):
        frappe.get_doc({"doctype": "Item Group", "item_group_name": RAIZ_GRUPO, "parent_item_group": raiz,
                        "is_group": 1}).insert(ignore_permissions=True)
    return RAIZ_GRUPO


def _grupo(categoria: str, cache: dict) -> str:
    """Uma folha dentro de «Loja online» (o ERPNext não aceita artigos num grupo de grupos)."""
    categoria = _l(categoria, 140) or f"{RAIZ_GRUPO} · sem categoria"
    if categoria not in cache:
        nome = categoria
        if frappe.db.exists("Item Group", nome) and frappe.db.get_value("Item Group", nome, "is_group"):
            nome = f"{categoria} · artigos"
        if not frappe.db.exists("Item Group", nome):
            frappe.get_doc({"doctype": "Item Group", "item_group_name": nome,
                            "parent_item_group": _raiz_grupos(), "is_group": 0}).insert(ignore_permissions=True)
        cache[categoria] = nome
    return cache[categoria]


def _fabricante(marca: str, cache: dict):
    marca = _l(marca, 140)
    if not marca:
        return None
    if marca not in cache:
        if not frappe.db.exists("Manufacturer", marca):
            frappe.get_doc({"doctype": "Manufacturer", "short_name": marca}).insert(ignore_permissions=True)
        cache[marca] = marca
    return cache[marca]


def _fornecedor(fid: int, nome: str, cache: dict) -> str:
    if fid not in cache:
        s = frappe.db.get_value("Supplier", {"orbit_importador_id": fid}, "name")
        if not s:
            nome = _l(nome, 120) or f"Fornecedor {fid}"
            if frappe.db.exists("Supplier", nome):
                nome = f"{nome} ({fid})"
            grupo = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name") or \
                frappe.db.get_value("Supplier Group", {}, "name")
            s = frappe.get_doc({"doctype": "Supplier", "supplier_name": nome, "supplier_group": grupo,
                                "orbit_importador_id": fid}).insert(ignore_permissions=True).name
        cache[fid] = s
    return cache[fid]


def _lista_compra() -> str:
    return frappe.db.get_single_value("Buying Settings", "buying_price_list") or "Standard Buying"


def _canal(c: dict) -> "frappe.model.document.Document":
    nome = _l(c.get("nome"), 140)
    if not nome:
        frappe.throw("o canal não tem nome")
    if frappe.db.exists("Canal de Venda", nome):
        doc = frappe.get_doc("Canal de Venda", nome)
    else:
        company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
        lista = f"Loja · {nome}"
        if not frappe.db.exists("Price List", lista):
            frappe.get_doc({"doctype": "Price List", "price_list_name": lista, "selling": 1, "buying": 0,
                            "currency": "EUR", "enabled": 1}).insert(ignore_permissions=True)
        marca = _l(c.get("marca"), 140)
        doc = frappe.get_doc({"doctype": "Canal de Venda", "nome": nome, "activo": 1, "company": company,
                              "url": _l(c.get("url"), 200), "lista_precos": lista,
                              "marca": marca if marca and frappe.db.exists("Brand", marca) else None,
                              "fonte_sync3": "Portal"}).insert(ignore_permissions=True)
    if c.get("conta") and doc.conta_importador != _l(c["conta"], 40):
        doc.db_set("conta_importador", _l(c["conta"], 40), update_modified=False)
    return doc


# ── um produto do feed ─────────────────────────────────────────────────────────────────────────────────────
def _codigo_livre(sku: str, chave: str) -> str:
    sku = re.sub(r"[^\w.\-/ ]", "", _l(sku, 120)).strip() or chave.replace(":", "-")
    dono = frappe.db.get_value("Item", sku, "orbit_chave_importador") if frappe.db.exists("Item", sku) else False
    if dono is False or dono == chave:
        return sku
    return f"{sku}-{chave.split(':')[0]}"   # o código já é de outro artigo (da casa ou de outro fornecedor)


def _preco(lista: str, item_code: str, valor) -> None:
    valor = _num(valor)
    if not lista or valor is None or valor <= 0:
        return
    nome = frappe.db.get_value("Item Price", {"price_list": lista, "item_code": item_code}, "name")
    if nome:
        if flt(frappe.db.get_value("Item Price", nome, "price_list_rate")) != flt(valor):
            frappe.db.set_value("Item Price", nome, "price_list_rate", valor)
    else:
        frappe.get_doc({"doctype": "Item Price", "price_list": lista, "item_code": item_code,
                        "price_list_rate": valor}).insert(ignore_permissions=True)


def _artigo(p: dict, canal, caches: dict) -> str:
    chave = _l(p.get("chave"), 200)
    nome = frappe.db.get_value("Item", {"orbit_chave_importador": chave}, "name")
    doc = frappe.get_doc("Item", nome) if nome else frappe.new_doc("Item")
    if nome and doc.get("orbit_hash_espelho") == p.get("hash"):
        return nome   # nada mudou desde a última volta
    if not nome:
        doc.item_code = _codigo_livre(p.get("sku"), chave)
        doc.stock_uom = frappe.db.get_single_value("Stock Settings", "stock_uom") or "Nos"
        doc.is_stock_item = 1
        doc.include_item_in_manufacturing = 0
        doc.orbit_chave_importador = chave
    doc.item_name = _l(p.get("titulo"), 140) or doc.item_code
    doc.description = (p.get("descricao") or p.get("titulo") or "")[:60000]
    doc.item_group = _grupo((p.get("categorias") or [""])[0], caches["grupos"])
    if canal.marca:
        doc.brand = canal.marca
    doc.orbit_fabricante = _fabricante(p.get("marca"), caches["fabricantes"])
    doc.orbit_pai_ref = _l(p.get("pai"), 140)
    doc.orbit_origem_stock = _l(p.get("origem_stock"), 140)
    doc.orbit_categorias_loja = "\n".join(_l(c, 140) for c in (p.get("categorias") or [])[:20])
    imagens = [_l(u, 500) for u in (p.get("imagens") or []) if u][:30]
    doc.orbit_imagens = "\n".join(imagens)
    if imagens and not (doc.image or "").startswith("/files/"):
        doc.image = imagens[0]
    for campo, k in (("orbit_comprimento", "c"), ("orbit_largura", "l"), ("orbit_altura", "a")):
        doc.set(campo, _num(p.get(k)))
    peso = _num(p.get("peso"))
    if peso:
        doc.weight_per_unit = peso
        if frappe.db.exists("UOM", "Kg"):
            doc.weight_uom = "Kg"
    ean = re.sub(r"\D", "", _l(p.get("ean"), 20))
    if len(ean) in (8, 12, 13, 14) and not any(b.barcode == ean for b in doc.get("barcodes") or []):
        dono = frappe.db.get_value("Item Barcode", {"barcode": ean}, "parent")
        if not dono or dono == doc.name:
            doc.append("barcodes", {"barcode": ean})
    doc.disabled = 0 if p.get("publicacao") in (None, "", "publicado") else 1
    doc.orbit_hash_espelho = _l(p.get("hash"), 64)
    doc.flags.ignore_permissions = True
    doc.flags.orbit_espelho = True
    doc.save() if nome else doc.insert()
    _preco(canal.lista_precos, doc.name, p.get("preco_venda"))
    _preco(caches["lista_compra"], doc.name, p.get("custo"))
    return doc.name


def _oferta(p: dict, item_code: str, caches: dict, agora) -> None:
    chave = _l(p.get("chave"), 200)
    sup = _fornecedor(cint(p.get("fid")), p.get("fornecedor"), caches["fornecedores"])
    qtd = _num(p.get("stock_qtd"))
    valores = {
        "item_code": item_code, "supplier": sup, "ref_fornecedor": _l(p.get("ref"), 140) or chave,
        "activa": 1, "estado_stock": ESTADOS.get(_l(p.get("estado"), 40).lower(), ""),
        "quantidade": qtd, "quantidade_conhecida": 0 if qtd is None else 1, "lida_em": agora,
        "tipo_fornecimento": _l(p.get("tipo_fornecimento"), 140), "prazo_entrega": _l(p.get("prazo"), 140),
        "data_reposicao": getdate(p["reposicao"]) if p.get("reposicao") else None,
        "custo": _num(p.get("custo")), "preco_base_venda": _num(p.get("preco_base_venda")),
        "pvr": _num(p.get("pvr")), "ausente_desde": None,
    }
    nome = frappe.db.get_value("Oferta do Fornecedor", {"chave": chave}, "name")
    if nome:
        frappe.db.set_value("Oferta do Fornecedor", nome, valores, update_modified=False)
    else:
        frappe.get_doc({"doctype": "Oferta do Fornecedor", "chave": chave, **valores}).insert(ignore_permissions=True)


# ── entrada ────────────────────────────────────────────────────────────────────────────────────────────────
def receber(dados: dict) -> dict:
    """Um lote: {"canal": {nome, url, conta, marca}, "itens": [...], "fim": bool, "chaves": [...]}."""
    frappe.set_user("Administrator")
    canal = _canal(dados.get("canal") or {})
    caches = {"grupos": {}, "fabricantes": {}, "fornecedores": {}, "lista_compra": _lista_compra()}
    agora = now_datetime()
    ok, erros, falhadas = 0, [], []
    for p in (dados.get("itens") or [])[:1000]:
        if not p.get("chave"):
            continue
        frappe.db.savepoint("orbit_espelho")
        try:
            codigo = _artigo(p, canal, caches)
            _oferta(p, codigo, caches, agora)
            ok += 1
        except Exception as e:  # noqa: BLE001 — um produto mau não pára o lote
            frappe.db.rollback(save_point="orbit_espelho")
            erros.append(f"{p.get('chave')} → {str(e)[:200]}")
            falhadas.append(p.get("chave"))
    frappe.db.commit()
    out = {"ok": True, "gravados": ok, "erros": len(erros), "amostra_erros": erros[:5], "chaves_com_erro": falhadas}
    if dados.get("fim"):
        out.update(_fechar(canal, set(dados.get("chaves") or []), agora))
    return out


def _fechar(canal, chaves: set, agora) -> dict:
    """Volta final: o que já não está no feed fica «fora do fornecedor» (o artigo não se apaga)."""
    saiu = 0
    if chaves:
        for o in frappe.get_all("Oferta do Fornecedor", filters={"ausente_desde": ["is", "not set"]}, fields=["name", "chave"]):
            if o.chave and o.chave not in chaves:
                frappe.db.set_value("Oferta do Fornecedor", o.name, "ausente_desde", agora, update_modified=False)
                saiu += 1
    resumo = resumo_canal(canal.name)
    resumo["fora_do_feed_nesta_volta"] = saiu
    canal.db_set({"ultimo_espelho": agora, "resumo_espelho": json.dumps(resumo, ensure_ascii=False)},
                 update_modified=False)
    frappe.db.commit()
    return {"resumo": resumo}


def resumo_canal(canal: str) -> dict:
    return {
        "artigos": frappe.db.count("Item", {"orbit_chave_importador": ["is", "set"]}),
        "artigos_inactivos": frappe.db.count("Item", {"orbit_chave_importador": ["is", "set"], "disabled": 1}),
        "ofertas": frappe.db.count("Oferta do Fornecedor", {"ausente_desde": ["is", "not set"]}),
        "ofertas_fora": frappe.db.count("Oferta do Fornecedor", {"ausente_desde": ["is", "set"]}),
        "fornecedores": frappe.db.count("Supplier", {"orbit_importador_id": [">", 0]}),
        "precos_canal": frappe.db.count("Item Price", {"price_list": frappe.db.get_value("Canal de Venda", canal, "lista_precos")}),
    }


def receber_ficheiro(caminho: str) -> dict:
    """Para a ponte: o lote chega num ficheiro gzip de JSON (o caminho é o do contentor, em /tmp)."""
    if not re.fullmatch(r"/tmp/orbit-espelho-[A-Za-z0-9_-]+\.json\.gz", caminho or ""):
        return {"ok": False, "erro": "caminho inválido"}
    with gzip.open(caminho, "rt", encoding="utf-8") as f:
        dados = json.load(f)
    return receber(dados)
