"""Base legal preenchida sozinha (plano da segmentação, S6 — 25-11-2026).

Sem base legal ninguém recebe; até aqui só a preenchia quem a escrevesse à mão, e por isso quase ninguém podia
receber (2 pessoas na Stratechna, 0 na JF). As regras:

* **B2B** — contacto de uma empresa (pessoa colectiva: NIPC português começado por 5, 6 ou 9, ou número de IVA de
  outro país da UE) cujo email é do domínio da empresa (nunca gmail, hotmail, sapo…): «Pode receber», base «b2b».
  Para pessoas colectivas vale o regime de oposição; o primeiro email traz sempre a saída num clique.
* **Cliente faturado** — com a opção «As vendas fora da loja dão a hipótese de recusar» ligada nas Definições de
  Marketing: na 1.ª fatura emitida, «Pode receber», base «cliente». Sem a opção fica «Sem registo» com a base
  «cliente» anotada — o soft opt-in só vale se a pessoa teve a hipótese de recusar quando deu o contacto.
* **Lojas** — já tratado pelo escritor das encomendas (Apps02): «Pode receber» só quando o aviso foi mostrado no
  checkout e não recusou. Os compradores sem aviso ficam «Sem registo»; aqui não se mexe neles.

Nunca se toca em «Pode receber» já registado, nem em «Recusou» ou «Retirou». Tudo fica no histórico de versões do
registo (é a prova), com «Origem» e «Texto aceite» a explicar de onde veio.
"""
from __future__ import annotations

import re

import frappe
from frappe.utils import cint, today

from orbit.marketing import destinatarios

GRATUITOS = {"gmail.com", "googlemail.com", "hotmail.com", "hotmail.pt", "outlook.com", "outlook.pt", "live.com",
             "live.com.pt", "msn.com", "yahoo.com", "yahoo.com.br", "yahoo.es", "yahoo.fr", "icloud.com", "me.com",
             "mac.com", "aol.com", "proton.me", "protonmail.com", "gmx.com", "gmx.net", "mail.com", "sapo.pt",
             "iol.pt", "clix.pt", "netcabo.pt", "net.novis.pt", "vodafone.pt", "meo.pt", "zonmail.pt", "portugalmail.pt",
             "hotmail.es", "hotmail.fr", "orange.fr", "free.fr", "laposte.net", "telefonica.net", "yandex.com"}
MUTAVEIS = (None, "", "Sem registo")


def _definicao(campo: str, omissao: int) -> int:
    try:
        v = frappe.db.get_single_value("Definicoes de Marketing", campo)
    except Exception:  # noqa: BLE001
        return omissao
    return omissao if v is None else cint(v)


def colectiva(nif: str | None) -> bool:
    n = re.sub(r"[\s.-]", "", str(nif or "")).upper()
    if not n:
        return False
    if n.startswith("PT"):
        n = n[2:]
    if n.isdigit():
        return len(n) == 9 and n[0] in "569"
    return bool(re.match(r"^[A-Z]{2}[0-9A-Z]{6,13}$", n))  # IVA de outro país


def dominio_profissional(email: str) -> bool:
    d = (email or "").rsplit("@", 1)[-1].strip().lower()
    return bool(d) and "." in d and d not in GRATUITOS


def _aplicar(doctype: str, nome: str, valores: dict, nota: str) -> None:
    doc = frappe.get_doc(doctype, nome)
    doc.update(valores)
    doc.flags.ignore_permissions = True
    doc.flags.orbit_base_legal = True
    doc.save()
    doc.add_comment("Comment", nota)


def proposta(r: dict, faturados: set) -> dict | None:
    """O que a regra faria a este registo (ou None)."""
    if r.get("mkt_estado") not in MUTAVEIS or r.get("mkt_base_legal") not in (None, "", "b2b", "cliente"):
        return None
    if r.get("unsubscribed"):
        return None
    if r.get("cliente_erp") in faturados and _definicao("aviso_na_venda", 0):
        return {"mkt_estado": "Pode receber", "mkt_base_legal": "cliente", "mkt_data": today(),
                "mkt_origem": "Contrato ou proposta",
                "mkt_texto": "Cliente com fatura emitida; as vendas informam que pode recusar comunicações de marketing."}
    if _definicao("b2b_automatico", 1) and colectiva(r.get("nif")) and dominio_profissional(r["email"]):
        return {"mkt_estado": "Pode receber", "mkt_base_legal": "b2b", "mkt_data": today(),
                "mkt_origem": r.get("mkt_origem") or "Outra",
                "mkt_texto": f"Contacto profissional de pessoa colectiva (NIPC {r.get('nif')}), email do domínio da "
                             "empresa — regime de oposição; cada email traz a saída num clique."}
    return None


def _faturados() -> set:
    if not frappe.db.exists("DocType", "Sales Invoice"):
        return set()
    return set(frappe.db.sql_list("SELECT DISTINCT customer FROM `tabSales Invoice` WHERE docstatus = 1"))


@frappe.whitelist()
def previsao() -> dict:
    """Relatório antes de aplicar a passagem única: quem passaria a poder receber, e com que base."""
    frappe.only_for(("System Manager", "Sales Manager"))
    fat = _faturados()
    linhas = []
    for r in destinatarios._registos(True):
        p = proposta(r, fat)
        if p:
            linhas.append({"doctype": r["doctype"], "name": r["name"], "email": r["email"],
                           "organizacao": r.get("organizacao"), "nif": r.get("nif"), "base": p["mkt_base_legal"],
                           "antes": r.get("mkt_estado") or "Sem registo"})
    return {"total": len(linhas), "b2b": sum(1 for l in linhas if l["base"] == "b2b"),
            "cliente": sum(1 for l in linhas if l["base"] == "cliente"), "linhas": linhas}


@frappe.whitelist()
def aplicar() -> dict:
    """A passagem única, depois de o relatório ser visto."""
    frappe.only_for(("System Manager", "Sales Manager"))
    fat = _faturados()
    n = 0
    for r in destinatarios._registos(True):
        p = proposta(r, fat)
        if p:
            _aplicar(r["doctype"], r["name"], p, f"Marketing: «{p['mkt_estado']}» com base «{p['mkt_base_legal']}» "
                                                 "(base legal automática, passagem única).")
            n += 1
    frappe.db.commit()
    return {"aplicados": n}


def _um(doctype: str, nome: str) -> None:
    for r in destinatarios._registos(True):
        if r["doctype"] == doctype and r["name"] == nome:
            p = proposta(r, _faturados())
            if p:
                _aplicar(doctype, nome, p, f"Marketing: «{p['mkt_estado']}» com base «{p['mkt_base_legal']}» (automático).")
            return


def ao_criar(doc, method=None):
    """Contacto ou lead novo: a regra B2B logo à entrada (em segundo plano — nunca atrasa nem trava quem grava)."""
    if doc.flags.get("orbit_base_legal") or doc.get("mkt_estado") not in MUTAVEIS:
        return
    frappe.enqueue("orbit.marketing.base_legal._um_seguro", doctype=doc.doctype, nome=doc.name, queue="short",
                   enqueue_after_commit=True)


def _um_seguro(doctype: str, nome: str) -> None:
    try:
        _um(doctype, nome)
        frappe.db.commit()
    except Exception:  # noqa: BLE001
        frappe.db.rollback()
        frappe.log_error(title="Marketing: base legal automática", message=frappe.get_traceback())


def fatura_submetida(doc, method=None):
    """1.ª fatura do cliente: os contactos dele passam a «cliente» (com a opção ligada) e ganham a marca da venda."""
    if not _definicao("aviso_na_venda", 0) or doc.get("is_return"):
        return
    contactos = frappe.get_all("Dynamic Link", filters={"parenttype": "Contact", "link_doctype": "Customer",
                                                         "link_name": doc.customer}, pluck="parent")
    for c in contactos:
        frappe.enqueue("orbit.marketing.base_legal._um_seguro", doctype="Contact", nome=c, queue="short",
                       enqueue_after_commit=True)
        marca = doc.get("orbit_marca")
        if marca:
            try:
                from orbit.interface.marcas import juntar_ao_contacto
                juntar_ao_contacto(c, marca)
            except Exception:  # noqa: BLE001
                pass
