"""«Adicionar por referência» no Orçamento.

Procura por esta ordem e pára no primeiro que encontra:
  1. o catálogo da conta no portal (os produtos que o importador lê dos fornecedores) — sem custo;
  2. a loja WooCommerce da marca (API pública da loja: /wp-json/wc/store/v1/products) — sem custo;
  3. a internet, só a pedido (botão próprio): a IA do portal procura o fabricante/fornecedor e lê a ficha —
     gasta créditos de IA da conta, e os dados ficam marcados «a confirmar».

Tudo o que se encontra chega ao ecrã para ser revisto e editado antes de entrar no Orçamento; a imagem pode
ser trocada por outra carregada pela pessoa. Ao gravar, o artigo (Item) é criado ou actualizado com a
referência como código — o ERPNext exige um artigo em cada linha.
"""
import hashlib
import hmac
import html as _html
import json
import re

import frappe
from frappe.utils import flt

_TEMPO = 25
_CABECALHOS = {"User-Agent": "Mozilla/5.0 (compatible; StratechnaOrbit/1.0)"}


# ── 1 e 3: portal ─────────────────────────────────────────────────────────────
def _portal(modo: str, referencia: str, marca: str | None):
    base = (frappe.conf.get("orbit_portal_url") or "").rstrip("/")
    seg = frappe.conf.get("orbit_portal_segredo")
    if not base or not seg:
        return None
    import requests
    corpo = json.dumps({"site": frappe.local.site, "modo": modo, "referencia": referencia, "marca": marca},
                       ensure_ascii=False).encode()
    r = requests.post(f"{base}/api/v1/orbit/produto-referencia", data=corpo, timeout=110 if modo == "internet" else _TEMPO,
                      headers={"Content-Type": "application/json",
                               "X-Orbit-Assinatura": hmac.new(seg.encode(), corpo, hashlib.sha256).hexdigest()})
    if r.status_code == 402:
        frappe.throw("A conta não tem créditos de IA para procurar na internet.")
    if r.status_code >= 300:
        frappe.log_error(title="orbit.propostas.portal", message=f"{r.status_code} {r.text[:500]}")
        return None
    return (r.json() or {}).get("produto")


# ── 2: loja WooCommerce da marca ─────────────────────────────────────────────
def _texto(v: str) -> str:
    v = re.sub(r"<(br|/p|/li)[^>]*>", "\n", v or "", flags=re.I)
    v = re.sub(r"<[^>]+>", " ", v)
    v = _html.unescape(v)
    return "\n".join(re.sub(r"[ \t]+", " ", l).strip() for l in v.splitlines() if l.strip())


def _caracteristicas_do_texto(texto: str) -> list:
    """Linhas «Nome: valor» que as descrições das lojas costumam ter."""
    out = []
    for l in texto.splitlines():
        m = re.match(r"^([^:]{2,40}):\s*(.{1,120})$", l.strip())
        if m:
            out.append([m.group(1).strip(), m.group(2).strip()])
    return out


def _normal(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _loja(referencia: str, marca: str | None):
    loja = frappe.db.get_value("Brand", marca, "orbit_loja") if marca else None
    if not loja:
        return None
    import requests
    loja = re.sub(r"^https?://", "", loja.strip()).rstrip("/")
    try:
        r = requests.get(f"https://{loja}/wp-json/wc/store/v1/products",
                         params={"search": referencia, "per_page": 10}, headers=_CABECALHOS, timeout=_TEMPO)
        produtos = r.json() if r.ok else []
    except Exception:
        return None
    alvo = _normal(referencia)
    escolhido = next((p for p in produtos if _normal(p.get("sku")) == alvo), None) \
        or next((p for p in produtos if alvo and alvo in _normal(p.get("name"))), None) \
        or next((p for p in produtos if alvo and alvo in _normal(p.get("description"))), None)
    if not escolhido:
        return None
    p = escolhido
    descricao = _texto(p.get("short_description") or "")
    completa = _texto(p.get("description") or "")
    caract = [[a.get("name"), ", ".join(t.get("name") for t in a.get("terms") or [])]
              for a in p.get("attributes") or [] if a.get("terms")]
    caract += [c for c in _caracteristicas_do_texto(completa) if c[0] not in {x[0] for x in caract}]
    precos = p.get("prices") or {}
    preco = None
    if precos.get("price"):
        preco = flt(precos["price"]) / (10 ** int(precos.get("currency_minor_unit") or 2))
    return {"fonte": f"loja {loja}", "titulo": _html.unescape(p.get("name") or ""), "descricao": descricao,
            "caracteristicas": caract, "imagens": [i.get("src") for i in p.get("images") or [] if i.get("src")],
            "preco": preco, "preco_nota": "preço da loja — confirmar se é com ou sem IVA", "url": p.get("permalink")}


# ── chamadas do ecrã ─────────────────────────────────────────────────────────
@frappe.whitelist()
def procurar(referencia: str, marca: str | None = None):
    """Catálogo do portal → loja da marca. Devolve {"produto": {...}} ou {"produto": None}."""
    frappe.has_permission("Quotation", "create", throw=True)
    referencia = (referencia or "").strip()
    if len(referencia) < 2:
        frappe.throw("Escreva a referência.")
    existente = _artigo_existente(referencia)
    if existente:
        return {"produto": existente}
    for passo in (lambda: _portal("catalogo", referencia, marca), lambda: _loja(referencia, marca)):
        try:
            produto = passo()
        except Exception:
            frappe.log_error(title="orbit.propostas.procurar")
            produto = None
        if produto:
            return {"produto": produto}
    return {"produto": None}


@frappe.whitelist()
def procurar_internet(referencia: str, marca: str | None = None):
    """Só a pedido: a IA do portal procura a referência na internet (gasta créditos de IA da conta)."""
    frappe.has_permission("Quotation", "create", throw=True)
    produto = _portal("internet", (referencia or "").strip(), marca)
    if produto:
        produto["a_confirmar"] = 1
    return {"produto": produto}


def _artigo_existente(referencia: str):
    """Já usado numa proposta anterior: vem do próprio Orbit, com o que lá se corrigiu."""
    nome = frappe.db.get_value("Item", {"item_code": referencia}) or frappe.db.get_value("Item", {"item_code": referencia.upper()})
    if not nome or nome in ("TRANSPORTE", "MONTAGEM"):
        return None
    it = frappe.get_doc("Item", nome)
    return {"fonte": "artigo do Orbit", "titulo": it.item_name, "descricao": _texto(it.description or ""),
            "caracteristicas": [l.split(":", 1) if ":" in l else ["", l]
                                for l in (it.get("orbit_caracteristicas") or "").splitlines() if l.strip()],
            "imagens": [it.image] if it.image else [], "preco": flt(it.standard_rate) or None, "artigo": it.name}


def _guardar_imagem(url: str, artigo: str) -> str | None:
    """A imagem de fora passa a ficheiro do Orbit — o PDF não depende do site de ninguém."""
    if not url or url.startswith("/files/") or url.startswith("/private/"):
        return url
    import requests
    try:
        r = requests.get(url, headers=_CABECALHOS, timeout=_TEMPO)
        if not r.ok or not r.headers.get("content-type", "").startswith("image/"):
            return None
        ext = {"image/png": "png", "image/webp": "webp", "image/gif": "gif"}.get(
            r.headers["content-type"].split(";")[0], "jpg")
        f = frappe.get_doc({"doctype": "File", "file_name": f"{re.sub(r'[^A-Za-z0-9_-]', '-', artigo)}.{ext}",
                            "content": r.content, "is_private": 0, "attached_to_doctype": "Item",
                            "attached_to_name": artigo})
        f.save(ignore_permissions=True)
        return f.file_url
    except Exception:
        frappe.log_error(title="orbit.propostas.imagem")
        return None


@frappe.whitelist()
def gravar_artigo(dados):
    """Cria ou actualiza o artigo da referência com o que a pessoa reviu. Devolve o que vai para a linha."""
    frappe.has_permission("Quotation", "create", throw=True)
    d = frappe.parse_json(dados) if isinstance(dados, str) else frappe._dict(dados or {})
    ref = (d.get("referencia") or "").strip()
    if not ref:
        frappe.throw("Falta a referência.")
    if ref.upper() in ("TRANSPORTE", "MONTAGEM"):
        frappe.throw("Essa referência está reservada.")
    nome = (d.get("titulo") or ref).strip()[:140]
    caract = (d.get("caracteristicas") or "").strip()
    descricao = (d.get("descricao") or "").strip()
    grupo = "Products" if frappe.db.exists("Item Group", "Products") else \
        frappe.db.get_value("Item Group", {"is_group": 0}, "name")
    uom = frappe.db.get_single_value("Stock Settings", "stock_uom") or "Nos"
    if frappe.db.exists("Item", ref):
        it = frappe.get_doc("Item", ref)
    else:
        it = frappe.get_doc({"doctype": "Item", "item_code": ref, "item_group": grupo, "stock_uom": uom,
                             "is_stock_item": 0, "is_sales_item": 1, "include_item_in_manufacturing": 0})
    it.item_name = nome
    it.description = descricao.replace("\n", "<br>") or nome
    if d.get("marca") and frappe.db.exists("Brand", d.get("marca")) and not it.brand:
        it.brand = d.get("marca")
    if it.meta.has_field("orbit_caracteristicas"):
        it.orbit_caracteristicas = caract
    it.flags.ignore_permissions = True
    it.save() if not it.is_new() else it.insert()
    imagem = d.get("imagem")
    if imagem and imagem != it.image:
        imagem = _guardar_imagem(imagem, it.name) or it.image
        if imagem:
            it.db_set("image", imagem)
    return {"item_code": it.name, "item_name": it.item_name, "description": it.description,
            "image": it.image, "orbit_caracteristicas": caract, "brand": it.brand, "uom": it.stock_uom,
            "orbit_fonte": d.get("fonte") or ""}
