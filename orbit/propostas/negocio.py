"""O orçamento abre ou liga a um negócio do CRM (25-11-2026, plano docs/PLANO-ORCAMENTO-NEGOCIO-ORBIT.md, D1–D7 aceites).

* Cada Quotation pertence a um negócio (`orbit_negocio`); um negócio pode ter vários orçamentos (versões, alternativas).
* Vazio ao gravar = nasce um negócio novo com a empresa, o contacto, a marca, o responsável e o valor do orçamento;
  uma versão (B, C…) fica no negócio da base.
* O negócio segue os orçamentos, só para a frente (D6): submetido → «Proposal/Quotation»; encomendado (Sales Order) →
  Won; todos perdidos → Lost. Valor = soma dos orçamentos abertos, a versão mais recente de cada base (D4);
  `orbit_valor_negocio` substitui o total quando está preenchido (as propostas do portal: 12 × mensal + único).
* Cliente que ainda é lead entra como Prospect (D1); a encomenda converte-o em Customer (o próprio ERPNext o faz).
"""
import frappe
from frappe.utils import flt, nowdate

PROPOSTA = "Proposal/Quotation"
FINAIS = ("Won", "Lost")


# ── fases ────────────────────────────────────────────────────────────────────────────────────────────────────
def _posicoes():
    return {r.name: (r.position or 0, r.type) for r in
            frappe.get_all("CRM Deal Status", fields=["name", "position", "type"])}


def _primeira_fase():
    from orbit.funis import primeira
    return primeira() or "Qualification"


def _avancar(deal, fase):
    """Muda a fase só se for para a frente; ganho/perdido são finais (o que se mudou à mão fica).
    27-11-2026: vários funis — `fase` («Won», «Proposal/Quotation»…) passa à fase equivalente do funil do negócio;
    ganho/perdido decide-se pelo tipo da fase."""
    from orbit import funis as F
    pos = _posicoes()
    pedida_tipo = pos.get(fase, (0, fase if fase in FINAIS else None))[1]
    fase = F.equivalente(deal.get("orbit_funil"), fase)
    if not fase or fase not in pos or pos.get(deal.status, (0, None))[1] in FINAIS:
        return False
    if pedida_tipo not in FINAIS and pos.get(deal.status, (0,))[0] >= pos[fase][0]:
        return False
    deal.status = fase
    fase = pedida_tipo if pedida_tipo in FINAIS else fase
    if fase == "Won":
        deal.probability = 100
        deal.closed_date = nowdate()
    elif fase == "Lost":
        deal.closed_date = nowdate()
        if not deal.lost_reason:
            motivos = frappe.get_all("CRM Lost Reason", pluck="name")
            deal.lost_reason = next((m for m in ("Other", "Outro") if m in motivos), None) or (motivos[0] if motivos else None)
            if not deal.lost_reason:
                frappe.get_doc({"doctype": "CRM Lost Reason", "lost_reason": "Outro"}).insert(ignore_permissions=True)
                deal.lost_reason = "Outro"
        if not deal.lost_notes:
            deal.lost_notes = "Todos os orçamentos do negócio foram dados como perdidos."
    return True


# ── valor ────────────────────────────────────────────────────────────────────────────────────────────────────
def orcamentos(negocio):
    return frappe.get_all("Quotation", filters={"orbit_negocio": negocio, "docstatus": ["<", 2]},
                          fields=["name", "status", "docstatus", "net_total", "grand_total", "currency",
                                  "orbit_valor_negocio", "orbit_proposta_base", "orbit_versao", "creation",
                                  "transaction_date", "valid_till", "orbit_ref_portal", "orbit_link_portal",
                                  "customer_name"],
                          order_by="creation asc")


def valor(negocio):
    ultimas = {}
    for q in orcamentos(negocio):
        if q.status in ("Lost", "Cancelled", "Expired"):
            continue
        ultimas[q.orbit_proposta_base or q.name] = q        # por ordem de criação: fica a mais recente da base
    return round(sum(flt(q.orbit_valor_negocio) or flt(q.net_total) for q in ultimas.values()), 2)


def actualizar(negocio, fase=None):
    """Nunca impede o orçamento: um erro no negócio fica registado e o orçamento grava na mesma."""
    try:
        _actualizar(negocio, fase)
    except Exception:
        frappe.log_error(title=f"Orbit: negócio {negocio} a partir do orçamento")


def _actualizar(negocio, fase=None):
    if not negocio or not frappe.db.exists("CRM Deal", negocio):
        return
    deal = frappe.get_doc("CRM Deal", negocio)
    mudou = False
    v = valor(negocio)
    abertos = [q for q in orcamentos(negocio) if q.status not in ("Lost", "Cancelled", "Expired")]
    if _posicoes().get(deal.status, (0, None))[1] not in FINAIS and flt(deal.deal_value) != v and abertos:      # tudo perdido: fica o último valor
        deal.deal_value = v
        mudou = True
    if fase:
        mudou = _avancar(deal, fase) or mudou
    else:
        qs = [q for q in orcamentos(negocio) if q.docstatus == 1]
        if qs and all(q.status == "Lost" for q in qs) and len(qs) == len(orcamentos(negocio)):
            mudou = _avancar(deal, "Lost") or mudou
    if mudou:
        deal.flags.ignore_permissions = True
        deal.save()


# ── o negócio de um orçamento novo ───────────────────────────────────────────────────────────────────────────
def organizacao(doc):
    """A empresa do CRM do cliente do orçamento (Customer → campo customer; senão pelo nome)."""
    if doc.quotation_to == "Customer" and doc.party_name:
        o = frappe.db.get_value("CRM Organization", {"customer": doc.party_name}, "name")
        if o:
            return o
    nome = doc.customer_name or doc.party_name
    if nome and frappe.db.exists("CRM Organization", nome):
        return nome
    if doc.quotation_to == "Prospect" and doc.party_name:
        o = frappe.db.get_value("Prospect", doc.party_name, "company_name")
        if o and frappe.db.exists("CRM Organization", o):
            return o
    return None


def antes_de_inserir(doc, method=None):
    if doc.get("orbit_negocio"):
        return
    base = doc.get("orbit_proposta_base")
    if base:
        doc.orbit_negocio = frappe.db.get_value("Quotation", base, "orbit_negocio")


def depois_de_inserir(doc, method=None):
    """Sem negócio escolhido: nasce um negócio novo para este orçamento."""
    if not frappe.db.exists("DocType", "CRM Deal"):
        return
    if doc.get("orbit_negocio") or doc.flags.get("orbit_sem_negocio"):
        if doc.get("orbit_negocio"):
            actualizar(doc.orbit_negocio)
        return
    org = organizacao(doc)
    deal = frappe.get_doc({
        "doctype": "CRM Deal",
        "status": _primeira_fase(),
        "organization": org,
        "deal_owner": doc.owner if frappe.db.exists("User", doc.owner) and doc.owner != "Administrator" else None,
        "deal_value": flt(doc.get("orbit_valor_negocio")) or flt(doc.net_total),
        "expected_closure_date": doc.valid_till,
    })
    if frappe.get_meta("CRM Deal").has_field("titulo"):
        deal.titulo = f"{doc.name} — {doc.customer_name or doc.party_name or 'Orçamento'}"[:140]
    if doc.get("orbit_marca") and frappe.get_meta("CRM Deal").has_field("marca"):
        deal.marca = doc.orbit_marca
    if doc.get("contact_person") and frappe.db.exists("Contact", doc.contact_person):
        deal.append("contacts", {"contact": doc.contact_person, "is_primary": 1})
    elif doc.get("contact_email"):
        deal.email = doc.contact_email
    deal.flags.ignore_permissions = True
    deal.insert()
    doc.db_set("orbit_negocio", deal.name, update_modified=False)


def ao_submeter(doc, method=None):
    actualizar(doc.get("orbit_negocio"), PROPOSTA)


def ao_mudar(doc, method=None):
    """Perdido, cancelado, valor — o negócio volta a fazer as contas (on_change e on_cancel)."""
    if doc.get("orbit_negocio") and doc.docstatus >= 1:
        actualizar(doc.orbit_negocio)


def encomenda_submetida(doc, method=None):
    """Sales Order a partir de orçamentos: o negócio deles fica ganho."""
    vistos = set()
    for l in doc.items or []:
        q = l.get("prevdoc_docname")
        if not q or q in vistos:
            continue
        vistos.add(q)
        n = frappe.db.get_value("Quotation", q, "orbit_negocio")
        if n:
            actualizar(n, "Won")


# ── para a interface /orbit ──────────────────────────────────────────────────────────────────────────────────
ESTADOS = {"Draft": "Rascunho", "Open": "Enviado", "Replied": "Respondido", "Partially Ordered": "Parcialmente encomendado",
           "Ordered": "Encomendado", "Lost": "Perdido", "Cancelled": "Anulado", "Expired": "Expirado"}


def para_ficha(negocio):
    out = []
    for q in reversed(orcamentos(negocio)):
        out.append({"name": q.name, "versao": q.orbit_versao, "estado": ESTADOS.get(q.status, q.status),
                    "estado_raw": q.status, "total": flt(q.grand_total), "sem_iva": flt(q.net_total),
                    "valor_negocio": flt(q.orbit_valor_negocio), "moeda": q.currency, "data": str(q.transaction_date or ""),
                    "validade": str(q.valid_till or ""), "ref_portal": q.orbit_ref_portal, "link_portal": q.orbit_link_portal,
                    "pdf": f"/api/method/frappe.utils.print_format.download_pdf?doctype=Quotation&name={q.name}"})
    return out


@frappe.whitelist()
def do_negocio(negocio: str):
    """Orçamentos do negócio para a ficha do /orbit."""
    frappe.get_doc("CRM Deal", negocio).check_permission("read")
    if not frappe.db.exists("DocType", "Quotation"):
        return {"erp": False, "itens": []}
    return {"erp": True, "pode_criar": bool(frappe.has_permission("Quotation", "create")), "itens": para_ficha(negocio)}


def _prospect(nome, org=None):
    """D1: cliente que ainda não é Customer entra como Prospect (a encomenda converte-o)."""
    nome = (nome or "").strip()[:140]
    if not nome:
        return None
    p = frappe.db.get_value("Prospect", {"company_name": nome}, "name")
    if p:
        return p
    d = frappe.get_doc({"doctype": "Prospect", "company_name": nome})
    d.flags.ignore_permissions = True
    d.insert()
    return d.name


def cliente_do_negocio(deal):
    """(quotation_to, party_name) para um orçamento deste negócio."""
    org = deal.organization
    if org:
        c = frappe.db.get_value("CRM Organization", org, "customer")
        if c and frappe.db.exists("Customer", c):
            return "Customer", c
        if frappe.db.exists("Customer", org):
            return "Customer", org
        return "Prospect", _prospect(org)
    nome = deal.get("organization_name") or deal.get("lead_name") or " ".join(
        x for x in [deal.get("first_name"), deal.get("last_name")] if x)
    if nome and frappe.db.exists("Customer", nome):
        return "Customer", nome
    return "Prospect", _prospect(nome or deal.name)


@frappe.whitelist()
def dados_para_orcamento(negocio: str):
    """«Criar orçamento» na ficha do negócio: o orçamento novo já vem com o negócio, o cliente, a marca e o contacto."""
    deal = frappe.get_doc("CRM Deal", negocio)
    deal.check_permission("read")
    para, parte = cliente_do_negocio(deal)
    contacto = next((c.contact for c in deal.get("contacts") or [] if c.is_primary), None) or \
        (deal.contacts[0].contact if deal.get("contacts") else None)
    return {"orbit_negocio": deal.name, "quotation_to": para, "party_name": parte, "contact_person": contacto,
            "orbit_marca": deal.get("marca") if deal.get("marca") and frappe.db.exists("Brand", deal.get("marca")) else None}
