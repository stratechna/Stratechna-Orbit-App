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
import os
import re
from urllib.parse import urlparse

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


_INDICE_MAX = 3000          # lojas maiores (a shopinox.eu tem ~9 600) ficam só pelo SKU e pela pesquisa
_INDICE_HORAS = 6


def _tokens(*textos) -> set:
    """Códigos soltos num texto: «M-GN2100», «N877-1.jpg», «…-a2543» → mgn2100, n877, a2543 (sem pontuação)."""
    out = set()
    for t in textos:
        for bruto in re.findall(r"[A-Za-z0-9][A-Za-z0-9.\-/_]*", _html.unescape(t or "")):
            out.add(_normal(bruto))
            for parte in re.split(r"[-_/.]", bruto):
                if len(parte) >= 3:
                    out.add(_normal(parte))
    return {x for x in out if len(x) >= 3}


def _api(loja: str, **params):
    import requests
    r = requests.get(f"https://{loja}/wp-json/wc/store/v1/products", params=params, headers=_CABECALHOS,
                     timeout=_TEMPO)
    return r.json() if r.ok else [], r


def _indice(loja: str) -> list:
    """O que identifica cada produto da loja: SKU, endereço, nomes das imagens e descrição breve.
    Guardado algumas horas — a 1.ª procura numa loja demora uns segundos (a Arnox tem ~2 000 produtos)."""
    chave = f"orbit_prop_indice:{loja}"
    guardado = frappe.cache().get_value(chave)
    if guardado is not None:
        return guardado
    primeira, r = _api(loja, per_page=100, page=1)
    total = int(r.headers.get("X-WP-Total") or 0)
    paginas = int(r.headers.get("X-WP-TotalPages") or 1)
    if total > _INDICE_MAX:
        frappe.cache().set_value(chave, [], expires_in_sec=_INDICE_HORAS * 3600)
        return []
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=6) as ex:
        resto = list(ex.map(lambda n: _api(loja, per_page=100, page=n)[0], range(2, paginas + 1)))
    indice = []
    for p in [x for pag in [primeira] + resto for x in (pag or [])]:
        imagens = [os.path.splitext(os.path.basename(urlparse(i.get("src") or "").path))[0] for i in p.get("images") or []]
        indice.append({"id": p.get("id"), "sku": _normal(p.get("sku")),
                       "t": sorted(_tokens(p.get("sku"), p.get("slug"), " ".join(imagens),
                                           _texto(p.get("short_description") or "")))})
    frappe.cache().set_value(chave, indice, expires_in_sec=_INDICE_HORAS * 3600)
    return indice


def _produto_da_loja(loja: str, p: dict) -> dict:
    sku = (p.get("sku") or "").strip()
    linhas = [l for l in _texto(p.get("short_description") or "").splitlines() if l.strip() and l.strip() != sku]
    breve = "\n".join(linhas)
    completa = _texto(p.get("description") or "")
    caract = [[a.get("name"), ", ".join(t.get("name") for t in a.get("terms") or [])]
              for a in p.get("attributes") or [] if a.get("terms")]
    for c in _caracteristicas_do_texto(breve + "\n" + completa):
        if c[0] not in {x[0] for x in caract}:
            caract.append(c)
    # a descrição breve sem as linhas «Nome: valor», que já vão nas características
    descricao = "\n".join(l for l in linhas if not re.match(r"^([^:]{2,40}):\s*(.{1,120})$", l.strip()))
    precos = p.get("prices") or {}
    preco = flt(precos["price"]) / (10 ** int(precos.get("currency_minor_unit") or 2)) if precos.get("price") else None
    return {"fonte": f"loja {loja}" + (f" (SKU {sku})" if sku else ""), "titulo": _html.unescape(p.get("name") or ""),
            "descricao": descricao, "caracteristicas": caract,
            "imagens": [i.get("src") for i in p.get("images") or [] if i.get("src")],
            "preco": preco or None, "preco_nota": "preço da loja — confirmar se é com ou sem IVA" if preco else None,
            "url": p.get("permalink"), "sku": sku}


def _loja(referencia: str, marca: str | None):
    """Na loja da marca: SKU exacto → pesquisa da loja (título e descrição breve) → índice (endereço, imagens,
    descrição breve). O EAN só se encontra se estiver escrito na descrição: a API pública da loja não o mostra."""
    loja = frappe.db.get_value("Brand", marca, "orbit_loja") if marca else None
    if not loja:
        return None
    loja = re.sub(r"^https?://", "", loja.strip()).rstrip("/")
    alvo = _normal(referencia)
    if len(alvo) < 2:
        return None
    produtos, _r = _api(loja, sku=referencia.strip(), per_page=5)
    escolhido = next((p for p in produtos or [] if _normal(p.get("sku")) == alvo), None)
    if not escolhido:
        termos = [referencia.strip()]
        if re.search(r"[-_/]", referencia):
            termos.append(re.sub(r"[-_/]+", " ", referencia.strip()))   # «L081-PC-130» também como «L081 PC 130»
        produtos = [p for t in termos for p in (_api(loja, search=t, per_page=20)[0] or [])]
        for p in produtos:
            if alvo == _normal(p.get("sku")) or alvo in _tokens(p.get("slug"), _texto(p.get("short_description") or ""),
                                                             " ".join(i.get("src") or "" for i in p.get("images") or [])):
                escolhido = p
                break
    if not escolhido:
        achado = next((x for x in _indice(loja) if x["sku"] == alvo or alvo in x["t"]), None)
        if achado:
            import requests
            r = requests.get(f"https://{loja}/wp-json/wc/store/v1/products/{achado['id']}", headers=_CABECALHOS,
                             timeout=_TEMPO)
            escolhido = r.json() if r.ok else None
    return _produto_da_loja(loja, escolhido) if escolhido else None


# ── chamadas do ecrã ─────────────────────────────────────────────────────────
@frappe.whitelist()
def procurar(referencia: str, marca: str | None = None):
    """Com marca escolhida: SÓ a loja dessa marca (pedido do Vítor, 10-11-2026) — a internet fica no botão à parte.
    Sem marca: artigo já usado no Orbit → catálogo da conta no portal. Devolve {"produto": {...}} ou {"produto": None}."""
    frappe.has_permission("Quotation", "create", throw=True)
    referencia = (referencia or "").strip()
    if len(referencia) < 2:
        frappe.throw("Escreva a referência.")
    if marca:
        passos = (lambda: _loja(referencia, marca),)
    else:
        existente = _artigo_existente(referencia)
        if existente:
            return {"produto": existente}
        passos = (lambda: _portal("catalogo", referencia, marca),)
    for passo in passos:
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
