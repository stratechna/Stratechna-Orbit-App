"""Quem pode receber, e quem está num segmento.

É a única função que decide a quem se escreve. Tudo passa por aqui: a
contagem que o ecrã mostra, a verificação antes de aprovar, e a lista fixada
no momento da saída.

Pode receber quem cumprir as quatro coisas, todas lidas do próprio CRM:
  1. está marcado «Pode receber», com base legal;
  2. o contacto não está `unsubscribed`;
  3. não pediu para sair de tudo (Email Unsubscribe global);
  4. não saiu do assunto desta campanha (Email Unsubscribe do assunto).

Um lead já convertido não conta: a pessoa vive agora no contacto, e contá-la
duas vezes era escrever-lhe duas vezes.
"""

from datetime import timedelta

import frappe
from frappe.utils import cint, now_datetime

from orbit.marketing.consentimento import NOMES


def _registos() -> list[dict]:
    """Leads e contactos com email, com os campos de marketing. Um endereço
    que esteja nos dois fica o contacto."""
    saida: dict[str, dict] = {}
    if frappe.db.exists("DocType", "CRM Lead") and frappe.get_meta("CRM Lead").has_field("mkt_estado"):
        campos = ["name", "email", "first_name", "last_name", "organization", "status", "converted"] + NOMES
        for l in frappe.get_all("CRM Lead", fields=campos, filters={"email": ("is", "set")},
                                limit_page_length=0):
            if cint(l.get("converted")):
                continue
            saida[l.email.strip().lower()] = {
                "doctype": "CRM Lead", "name": l.name, "email": l.email.strip().lower(),
                "nome": l.first_name, "apelido": l.last_name, "organizacao": l.organization,
                "estado_lead": l.status, "unsubscribed": 0, **{k: l.get(k) for k in NOMES}}
    if frappe.get_meta("Contact").has_field("mkt_estado"):
        campos = ["name", "email_id", "first_name", "last_name", "company_name", "unsubscribed"] + NOMES
        for c in frappe.get_all("Contact", fields=campos, filters={"email_id": ("is", "set")},
                                limit_page_length=0):
            saida[c.email_id.strip().lower()] = {
                "doctype": "Contact", "name": c.name, "email": c.email_id.strip().lower(),
                "nome": c.first_name, "apelido": c.last_name, "organizacao": c.company_name,
                "estado_lead": None, "unsubscribed": cint(c.unsubscribed), **{k: c.get(k) for k in NOMES}}
    return list(saida.values())


def _sairam(assunto: str | None) -> tuple[set, set]:
    globais = {(e or "").lower() for e in frappe.get_all(
        "Email Unsubscribe", filters={"global_unsubscribe": 1}, pluck="email", limit_page_length=0)}
    do_assunto = set()
    if assunto:
        do_assunto = {(e or "").lower() for e in frappe.get_all(
            "Email Unsubscribe", filters={"reference_doctype": "Assunto de Marketing",
                                          "reference_name": assunto}, pluck="email", limit_page_length=0)}
    return globais, do_assunto


def contactaveis(assunto: str | None = None) -> list[dict]:
    globais, do_assunto = _sairam(assunto)
    # Quem devolveu ou se queixou (Supressao de Marketing) fica de fora sempre.
    suprimidos = {(e or "").lower() for e in frappe.get_all("Supressao de Marketing", pluck="email",
                                                            limit_page_length=0)}
    return [r for r in _registos()
            if r.get("mkt_estado") == "Pode receber" and r.get("mkt_base_legal")
            and not r["unsubscribed"] and r["email"] not in globais and r["email"] not in do_assunto
            and r["email"] not in suprimidos]


def _comportamento(coluna: str, dias: int) -> set:
    desde = now_datetime() - timedelta(days=dias)
    return {(e or "").lower() for e in frappe.get_all(
        "Envio de Marketing", filters={coluna: (">=", desde)}, pluck="email", limit_page_length=0)}


def _cumpre(r: dict, regra: str, valor: str, cache: dict) -> bool:
    v = (valor or "").strip()
    baixo = v.lower()
    if regra == "Assunto de interesse":
        return baixo in {a.strip().lower() for a in (r.get("mkt_assuntos") or "").split(",")}
    if regra == "Segmento":
        return (r.get("mkt_segmento") or "").strip().lower() == baixo
    if regra == "Idioma":
        return (r.get("mkt_idioma") or "") == baixo
    if regra == "Base legal":
        return (r.get("mkt_base_legal") or "") == baixo
    if regra == "Tipo de registo":
        return {"lead": "CRM Lead", "contacto": "Contact"}.get(baixo) == r["doctype"]
    if regra == "Estado do lead":
        return (r.get("estado_lead") or "").lower() == baixo
    if regra == "Organização contém":
        return baixo in (r.get("organizacao") or "").lower()
    if regra in ("Comprou nos últimos N dias", "Não compra há mais de N dias", "Comprou no grupo de artigos",
                 "Tem pelo menos N encomendas"):
        from frappe.utils import add_days, getdate, nowdate
        from orbit.marketing import loja
        if "compras" not in cache:
            cache["compras"] = loja.ultima_compra()
        x = cache["compras"].get(r["email"])
        if not x:
            return False
        if regra == "Comprou nos últimos N dias":
            return getdate(x["ultima"]) >= getdate(add_days(nowdate(), -cint(v)))
        if regra == "Não compra há mais de N dias":
            return getdate(x["ultima"]) < getdate(add_days(nowdate(), -cint(v)))
        if regra == "Comprou no grupo de artigos":
            return baixo in {g.lower() for g in x["grupos"]}
        return x["n"] >= cint(v)
    if regra in ("Abriu nos últimos N dias", "Clicou nos últimos N dias"):
        coluna = "aberto_em" if regra.startswith("Abriu") else "clicado_em"
        chave = (coluna, cint(v))
        if chave not in cache:
            cache[chave] = _comportamento(coluna, cint(v) or 30)
        return r["email"] in cache[chave]
    return False


def do_segmento(segmento: str, base: list[dict] | None = None) -> list[dict]:
    """Um segmento: todas as regras dele têm de se cumprir. Sem regras, é toda
    a gente que pode receber."""
    regras = frappe.get_all("Regra de Segmento", filters={"parent": segmento, "parenttype": "Segmento de Marketing"},
                            fields=["regra", "valor"], order_by="idx")
    base = contactaveis() if base is None else base
    cache: dict = {}
    return [r for r in base if all(_cumpre(r, x.regra, x.valor, cache) for x in regras)]


def da_campanha(campanha) -> list[dict]:
    """Os destinatários de uma campanha: os que podem receber o assunto dela e
    estão em pelo menos um dos segmentos."""
    base = contactaveis(campanha.assunto_marketing)
    segmentos = [s.segmento for s in (campanha.segmentos or [])]
    if not segmentos:
        return []
    vistos, saida = set(), []
    for s in segmentos:
        for r in do_segmento(s, base):
            if r["email"] not in vistos:
                vistos.add(r["email"])
                saida.append(r)
    return saida
