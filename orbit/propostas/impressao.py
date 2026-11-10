"""O que o modelo de impressão precisa, já arrumado (hooks.jinja → `orbit_proposta(doc)`).

O Jinja fica só com a forma; as contas e as regras (numeração 1, 1A, 2…; transporte por linha; IVA por taxa)
vivem aqui, onde se testam.
"""
import frappe
from frappe.utils import cint, flt, formatdate

from orbit.propostas.regras import taxa_iva

_COR = "#22303d"


def _eur(v) -> str:
    """1 234,50 € — à portuguesa, com espaço inseparável nos milhares (o WebKit do PDF não tem o espaço fino)."""
    s = f"{flt(v):,.2f}".replace(",", " ").replace(".", ",").replace(" ", "\u00a0")
    return f"{s} €"


def _taxa(v) -> str:
    v = flt(v)
    return (f"{v:.0f}" if v == int(v) else f"{v:.1f}".replace(".", ",")) + " %"


def _caracteristicas(texto):
    linhas = []
    for bruto in (texto or "").splitlines():
        bruto = bruto.strip().lstrip("•-– ").strip()
        if not bruto:
            continue
        if ":" in bruto:
            k, v = bruto.split(":", 1)
            linhas.append((k.strip(), v.strip()))
        else:
            linhas.append(("", bruto))
    return linhas


def _imagem(url):
    if not url:
        return None
    if url.startswith("/"):
        return frappe.utils.get_url(url)
    return url


def _luz(cor: str) -> float:
    """Luminância relativa (0 escuro … 1 claro) de #rrggbb."""
    try:
        r, g, b = (int(cor.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except (ValueError, IndexError):
        return 0.0
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def _escurecer(cor: str, fator: float = 0.62) -> str:
    try:
        r, g, b = (int(cor.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    except (ValueError, IndexError):
        return _COR
    return "#%02x%02x%02x" % (int(r * fator), int(g * fator), int(b * fator))


def _marca(doc):
    nome = doc.get("orbit_marca")
    m = frappe.get_cached_doc("Brand", nome) if nome and frappe.db.exists("Brand", nome) else None
    empresa = frappe.get_cached_doc("Company", doc.company) if doc.company else None
    cor = (m.get("orbit_cor") if m else None) or _COR
    clara = _luz(cor) > 0.35   # laranja, amarelo…: texto branco por cima não se lê
    return frappe._dict({
        "nome": (m.name if m else (empresa.company_name if empresa else "")),
        "cor_texto": "#1d2329" if clara else "#ffffff",
        "cor_letra": _escurecer(cor) if clara else cor,   # títulos pequenos e referências sobre o branco
        "logo": _imagem(m.image) if m and m.image else None,
        "cor": cor,
        "morada": (m.get("orbit_morada") if m else None) or "",
        "nif": (m.get("orbit_nif") if m else None) or (empresa.tax_id if empresa else ""),
        "empresa": empresa.company_name if empresa else "",
        "telefones": (m.get("orbit_telefones") if m else None) or "",
        "email": (m.get("orbit_email") if m else None) or (empresa.email if empresa else ""),
        "site": (m.get("orbit_site") if m else None) or "",
        "iban": (m.get("orbit_iban") if m else None) or "",
        "condicoes": (m.get("orbit_condicoes") if m else None) or "",
    })


def proposta(doc):
    marca = _marca(doc)
    modo = doc.get("orbit_transporte_modo") or "Por produto"
    linhas, n, letra = [], 0, 0
    for l in doc.items or []:
        if l.get("orbit_de"):
            continue
        if l.is_alternative:
            letra += 1
            numero = f"{n}{chr(64 + letra)}"
        else:
            n, letra = n + 1, 0
            numero = str(n)
        extras = []
        if modo == "Por produto":
            for rotulo, v in (("Transporte", l.get("orbit_transporte")), ("Montagem", l.get("orbit_montagem"))):
                if flt(v) > 0:
                    extras.append(frappe._dict(rotulo=rotulo, valor=_eur(v)))
        taxa = taxa_iva(doc, l)
        linhas.append(frappe._dict({
            "numero": numero, "alternativa": bool(l.is_alternative), "de": str(n),
            "imagem": _imagem(l.image), "referencia": l.item_code, "nome": l.item_name,
            "descricao": l.description if l.description and frappe.utils.strip_html(l.description).strip()
            not in ("", (l.item_name or "").strip()) else "",
            "caracteristicas": _caracteristicas(l.get("orbit_caracteristicas")),
            "qtd": (f"{flt(l.qty):g}".replace(".", ",")), "unidade": l.uom,
            "preco": _eur(l.rate), "total": _eur(l.amount), "iva": _taxa(taxa),
            "observacoes": l.get("orbit_observacoes") or "", "extras": extras,
        }))

    soma = lambda f: sum(flt(l.amount) for l in doc.items or [] if f(l) and not l.is_alternative)
    equipamentos = soma(lambda l: not l.get("orbit_de"))
    transporte = soma(lambda l: l.get("orbit_de") and l.item_code == "TRANSPORTE")
    montagem = soma(lambda l: l.get("orbit_de") and l.item_code == "MONTAGEM")
    ivas = []
    for t in doc.get("taxes") or []:
        if flt(t.tax_amount):
            rotulo = f"IVA {_taxa(t.rate)}" if t.charge_type == "On Net Total" and flt(t.rate) else (t.description or "")
            ivas.append(frappe._dict(rotulo=rotulo, valor=_eur(t.tax_amount)))
    total_com = doc.rounded_total if flt(doc.rounded_total) and not cint(doc.disable_rounded_total) else doc.grand_total
    validade = ""
    if doc.valid_till and doc.transaction_date:
        dias = (frappe.utils.getdate(doc.valid_till) - frappe.utils.getdate(doc.transaction_date)).days
        validade = f"{dias} dias, até {formatdate(doc.valid_till, 'dd-MM-yyyy')}"

    return frappe._dict({
        "marca": marca, "linhas": linhas, "modo": modo,
        "equipamentos": _eur(equipamentos), "transporte": _eur(transporte), "montagem": _eur(montagem),
        "tem_transporte": modo != "Não incluir" and (transporte or montagem),
        "desconto": _eur(doc.discount_amount) if flt(doc.discount_amount) else None,
        "sem_iva": _eur(doc.net_total), "ivas": ivas, "com_iva": _eur(total_com),
        "mostrar_iva": cint(doc.get("orbit_mostrar_iva")) == 1,
        "data": formatdate(doc.transaction_date, "dd-MM-yyyy"), "validade": validade,
        "comercial": frappe.db.get_value("User", doc.owner, "full_name") if doc.owner else "",
        "anexar": cint(doc.get("orbit_anexar_condicoes")) == 1 and bool(frappe.utils.strip_html(marca.condicoes).strip()),
    })


def orbit_proposta(doc):
    """O nome que o modelo de impressão usa (hooks.jinja exporta a função pelo nome dela)."""
    return proposta(doc)
