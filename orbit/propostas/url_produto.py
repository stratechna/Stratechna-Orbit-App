# Produto a partir de um endereço colado na proposta (pedido do Vítor a 26-11): «se colo uma url é para que possam ser
# gerados os dados do produto automaticamente e pode haver a pergunta se deve ser criado o produto».
#
# 1.º sem custos: lê a página e tira o que ela já declara (JSON-LD Product, Open Graph, microdados, título, tabela
# de especificações). 2.º só a pedido: a IA da conta lê a página (créditos), pelo mesmo caminho do portal que a
# procura na internet. Nada é criado aqui — a pessoa revê e escolhe «Criar o artigo e acrescentar».
import html as H
import json
import re

import frappe
from frappe.utils import flt

from orbit.propostas.referencia import _CABECALHOS, _TEMPO, _portal

_TAG = re.compile(r"<[^>]+>")


def _limpo(t):
    return re.sub(r"\s+", " ", H.unescape(_TAG.sub(" ", t or ""))).strip()


def _jsonld(pagina):
    for bloco in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', pagina, re.S | re.I):
        try:
            d = json.loads(bloco.strip())
        except ValueError:
            continue
        for x in (d if isinstance(d, list) else d.get("@graph", [d]) if isinstance(d, dict) else []):
            if isinstance(x, dict) and ("Product" in str(x.get("@type"))):
                return x
    return None


def _meta(pagina, prop):
    m = re.search(r'<meta[^>]+(?:property|name)=["\']' + re.escape(prop) + r'["\'][^>]+content=["\']([^"\']*)', pagina, re.I) or \
        re.search(r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:property|name)=["\']' + re.escape(prop), pagina, re.I)
    return H.unescape(m.group(1)).strip() if m else ""


def _especificacoes(pagina):
    """Pares «nome: valor» de tabelas e listas de definições (fichas técnicas)."""
    out = []
    for a, b in re.findall(r"<tr[^>]*>\s*<t[hd][^>]*>(.*?)</t[hd]>\s*<td[^>]*>(.*?)</td>", pagina, re.S | re.I)[:40]:
        a, b = _limpo(a), _limpo(b)
        if a and b and len(a) < 60 and len(b) < 200:
            out.append([a.rstrip(":"), b])
    if not out:
        for a, b in re.findall(r"<dt[^>]*>(.*?)</dt>\s*<dd[^>]*>(.*?)</dd>", pagina, re.S | re.I)[:40]:
            a, b = _limpo(a), _limpo(b)
            if a and b:
                out.append([a.rstrip(":"), b])
    return out[:30]


@frappe.whitelist()
def ler(url: str):
    """Os dados do produto que a página declara. Sem custos."""
    frappe.has_permission("Quotation", "create", throw=True)
    url = (url or "").strip()
    if not re.match(r"^https?://", url):
        frappe.throw("Isso não é um endereço (deve começar por https://).")
    import requests
    try:
        r = requests.get(url, headers={**_CABECALHOS, "Accept-Language": "pt-PT,pt;q=0.9,es;q=0.8,en;q=0.7"}, timeout=_TEMPO)
        pagina = r.text if r.ok else ""
    except Exception:
        pagina = ""
    if not pagina:
        return {"url": url, "lido": False, "falta": ["a página não abriu (pode bloquear robôs)"]}
    p = _jsonld(pagina) or {}
    oferta = p.get("offers") or {}
    if isinstance(oferta, list):
        oferta = oferta[0] if oferta else {}
    marca = p.get("brand")
    marca = marca.get("name") if isinstance(marca, dict) else marca
    imagens = p.get("image") or []
    imagens = [imagens] if isinstance(imagens, str) else [i.get("url") if isinstance(i, dict) else i for i in imagens]
    og_img = _meta(pagina, "og:image")
    if og_img and og_img not in imagens:
        imagens.append(og_img)
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", pagina, re.S | re.I)
    titulo = p.get("name") or _meta(pagina, "og:title") or (_limpo(h1.group(1)) if h1 else "")
    descricao = _limpo(p.get("description") or _meta(pagina, "og:description") or _meta(pagina, "description"))
    caract = [[x.get("name", ""), str(x.get("value", ""))] for x in (p.get("additionalProperty") or []) if isinstance(x, dict)] or _especificacoes(pagina)
    preco = flt(oferta.get("price") or oferta.get("lowPrice") or _meta(pagina, "product:price:amount")) or None
    ref = p.get("sku") or p.get("mpn") or ""
    if not ref:
        m = re.search(r"(?:Ref(?:er[eê]ncia)?|SKU|C[oó]d(?:igo)?)\.?\s*[:#]?\s*([A-Z0-9][A-Z0-9._/-]{2,30})", _limpo(pagina), re.I)
        ref = m.group(1) if m else ""
    from urllib.parse import urljoin
    imagens = [urljoin(url, i) for i in imagens if i][:6]
    res = {"url": url, "lido": True, "titulo": (titulo or "").strip()[:140], "descricao": descricao[:2000], "caracteristicas": caract,
           "imagens": imagens, "preco": preco, "moeda": oferta.get("priceCurrency"), "referencia": str(ref).strip()[:60],
           "ean": p.get("gtin13") or p.get("gtin") or "", "fabricante": marca or "", "fonte": "página do produto — " + url}
    res["falta"] = [n for n, v in (("título", res["titulo"]), ("referência", res["referencia"]), ("imagem", res["imagens"]),
                                   ("características", res["caracteristicas"])) if not v]
    from orbit.propostas.referencia import _artigo_existente
    res["existente"] = _artigo_existente(res["referencia"]) if res["referencia"] else None
    return res


@frappe.whitelist()
def ler_com_ia(url: str, marca: str = None):
    """A IA da conta lê a página (créditos de IA), para o que a página não declara."""
    frappe.has_permission("Quotation", "create", throw=True)
    p = _portal("internet", f"Lê esta página de produto e tira os dados: {url}", marca) or {}
    if not p:
        return {"url": url, "lido": False, "falta": ["a IA não conseguiu ler a página"]}
    return {"url": url, "lido": True, "titulo": p.get("titulo") or "", "descricao": p.get("descricao") or "",
            "caracteristicas": p.get("caracteristicas") or [], "imagens": p.get("imagens") or [], "preco": p.get("preco"),
            "referencia": p.get("referencia") or "", "fabricante": p.get("fabricante") or "", "fonte": "IA — " + url, "falta": [], "ia": True}
