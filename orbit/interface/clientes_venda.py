# Escolher o cliente de uma proposta/encomenda/fatura (pedido do Vítor a 26-11: «ao escrever cliente não tenho como
# pesquisar»). Procura nos clientes do ERP e também no CRM (empresas, contactos, leads) — quem está no CRM ainda não é
# cliente do ERP; ao escolher, nasce o cliente (com NIF, email e o contacto ligado). E «+ Criar cliente» de raiz.
import frappe
from frappe import _
from frappe.utils import cstr

from orbit.interface.api import _guarda


@frappe.whitelist()
def procurar(q: str = "", modo: str = "cliente"):
    _guarda()
    q = cstr(q).strip()
    if modo == "lead":
        return _procurar_leads(q)
    like = f"%{q}%"
    out = []
    if frappe.has_permission("Customer", "read"):
        ou = [["customer_name", "like", like], ["name", "like", like], ["tax_id", "like", like]] if q else None
        for c in frappe.get_list("Customer", or_filters=ou, filters={"disabled": 0}, fields=["name", "customer_name", "tax_id", "customer_type"], limit=10, order_by="modified desc"):
            out.append({"tipo": "cliente", "doctype": "Customer", "name": c.name, "titulo": c.customer_name or c.name,
                        "sub": " · ".join(x for x in (c.tax_id and ("NIF " + c.tax_id), _("Empresa") if c.customer_type == "Company" else _("Particular")) if x)})
    # 27-11-2026: sem texto também se mostram os mais recentes do CRM (a JF tem 1 cliente no ERP e o resto no CRM —
    # parecia que só havia aquele); com texto procura-se logo a partir da 1.ª letra.
    if True:
        if frappe.db.exists("DocType", "CRM Organization") and frappe.has_permission("CRM Organization", "read"):
            for o in frappe.get_list("CRM Organization", or_filters=([["organization_name", "like", like], ["nipc", "like", like]] if frappe.get_meta("CRM Organization").has_field("nipc") else [["organization_name", "like", like]]) if q else None, order_by="modified desc",
                                     fields=["name", "organization_name"] + (["nipc"] if frappe.get_meta("CRM Organization").has_field("nipc") else []), limit=6):
                out.append({"tipo": "crm", "doctype": "CRM Organization", "name": o.name, "titulo": o.organization_name or o.name,
                            "sub": _("Empresa do CRM") + (f" · NIPC {o.get('nipc')}" if o.get("nipc") else "")})
        if frappe.has_permission("Contact", "read"):
            # a equipa e as caixas da casa não são clientes (contactos de utilizadores e das contas de email)
            casa = {e.lower() for e in frappe.get_all("Email Account", pluck="email_id") if e} | {u.lower() for u in frappe.get_all("User", filters={"user_type": "System User"}, pluck="name")}
            for c in frappe.get_list("Contact", filters={"user": ["is", "not set"]}, or_filters=[["full_name", "like", like], ["email_id", "like", like], ["company_name", "like", like], ["mobile_no", "like", like]] if q else None, order_by="modified desc",
                                     fields=["name", "full_name", "email_id", "company_name"], limit=12):
                if (c.email_id or "").lower() in casa or len([x for x in out if x["doctype"] == "Contact"]) >= 6:
                    continue
                out.append({"tipo": "crm", "doctype": "Contact", "name": c.name, "titulo": c.full_name or c.name,
                            "sub": " · ".join(x for x in (_("Contacto do CRM"), c.company_name, c.email_id) if x)})
        if frappe.db.exists("DocType", "CRM Lead") and frappe.has_permission("CRM Lead", "read"):
            for l in frappe.get_list("CRM Lead", or_filters=[["lead_name", "like", like], ["email", "like", like], ["organization", "like", like]] if q else None, order_by="modified desc",
                                     filters={"converted": 0}, fields=["name", "lead_name", "organization", "email"], limit=4):
                out.append({"tipo": "crm", "doctype": "CRM Lead", "name": l.name, "titulo": l.organization or l.lead_name or l.name,
                            "sub": " · ".join(x for x in (_("Lead do CRM"), l.lead_name if l.organization else "", l.email) if x)})
    # o que já é cliente não aparece duas vezes (mesmo nome)
    vistos = {x["titulo"].lower() for x in out if x["tipo"] == "cliente"}
    return [x for x in out if x["tipo"] == "cliente" or x["titulo"].lower() not in vistos]


def _procurar_leads(q):
    """«Lead / potencial cliente» (27-11-2026): as leads do CRM e as do ERP numa só lista."""
    like, out = f"%{q}%", []
    if frappe.db.exists("DocType", "CRM Lead") and frappe.has_permission("CRM Lead", "read"):
        for l in frappe.get_list("CRM Lead", or_filters=[["lead_name", "like", like], ["email", "like", like], ["organization", "like", like]] if q else None,
                                 filters={"converted": 0}, fields=["name", "lead_name", "organization", "email"], order_by="modified desc", limit=10):
            out.append({"tipo": "crm", "doctype": "CRM Lead", "name": l.name, "titulo": l.organization or l.lead_name or l.name,
                        "sub": " · ".join(x for x in (_("Lead do CRM"), l.lead_name if l.organization else "", l.email) if x)})
    if frappe.has_permission("Lead", "read"):
        for l in frappe.get_list("Lead", or_filters=[["lead_name", "like", like], ["company_name", "like", like], ["email_id", "like", like]] if q else None,
                                 fields=["name", "lead_name", "company_name", "email_id"], order_by="modified desc", limit=10):
            out.append({"tipo": "cliente", "doctype": "Lead", "name": l.name, "titulo": l.company_name or l.lead_name or l.name,
                        "sub": " · ".join(x for x in (_("Lead"), l.lead_name if l.company_name else "", l.email_id) if x)})
    return out


def _lead_erp(nome, empresa=None, email=None, telefone=None):
    """A lead do ERP (a Proposta do ERPNext liga-se a «Lead»); a mesma pessoa/email não se repete."""
    if email:
        existe = frappe.db.get_value("Lead", {"email_id": email})
        if existe:
            return existe
    d = frappe.get_doc({"doctype": "Lead", "first_name": (nome or empresa or "")[:140], "company_name": empresa or None,
                        "email_id": email or None, "mobile_no": telefone or None})
    d.insert()
    return d.name


def _novo(nome, tipo="Company", nif=None, email=None, telefone=None):
    existe = frappe.db.get_value("Customer", {"customer_name": nome})
    if existe:
        return existe
    c = frappe.get_doc({"doctype": "Customer", "customer_name": nome[:140], "customer_type": tipo})
    if nif and c.meta.has_field("tax_id"):
        c.tax_id = cstr(nif).replace(" ", "").upper().removeprefix("PT")
    if email and c.meta.has_field("email_id"):
        c.email_id = email
    if telefone and c.meta.has_field("mobile_no"):
        c.mobile_no = telefone
    c.insert()
    return c.name


@frappe.whitelist(methods=["POST"])
def usar(doctype: str = None, name: str = None, dados: str = None, modo: str = "cliente"):
    """Devolve o cliente do ERP para o registo do CRM escolhido (criando-o se ainda não existir) ou para os dados novos."""
    _guarda()
    if modo == "lead":
        if not frappe.has_permission("Lead", "create"):
            frappe.throw(_("Sem permissão para criar leads."), frappe.PermissionError)
        if dados:
            d = frappe.parse_json(dados)
            if not cstr(d.get("nome")).strip():
                frappe.throw(_("Falta o nome."))
            return {"customer": _lead_erp(cstr(d["nome"]).strip(), d.get("empresa"), d.get("email"), d.get("telefone"))}
        l = frappe.get_doc("CRM Lead", name)
        l.check_permission("read")
        return {"customer": _lead_erp(l.lead_name or l.organization, l.organization, l.email, l.mobile_no)}
    if not frappe.has_permission("Customer", "create"):
        frappe.throw(_("Sem permissão para criar clientes."), frappe.PermissionError)
    if dados:
        d = frappe.parse_json(dados)
        if not cstr(d.get("nome")).strip():
            frappe.throw(_("Falta o nome do cliente."))
        return {"customer": _novo(cstr(d["nome"]).strip(), "Company" if d.get("tipo") != "Particular" else "Individual", d.get("nif"), d.get("email"), d.get("telefone"))}
    if doctype == "CRM Organization":
        o = frappe.get_doc(doctype, name)
        o.check_permission("read")
        return {"customer": _novo(o.organization_name or o.name, "Company", o.get("nipc"))}
    if doctype == "Contact":
        c = frappe.get_doc(doctype, name)
        c.check_permission("read")
        cli = _novo(c.company_name or c.full_name or c.name, "Company" if c.company_name else "Individual", None, c.email_id, c.mobile_no)
        if not any(l.link_doctype == "Customer" and l.link_name == cli for l in c.links):
            c.append("links", {"link_doctype": "Customer", "link_name": cli})
            c.save(ignore_permissions=True)
        return {"customer": cli, "contacto": c.name}
    if doctype == "CRM Lead":
        l = frappe.get_doc(doctype, name)
        l.check_permission("read")
        return {"customer": _novo(l.organization or l.lead_name or l.name, "Company" if l.organization else "Individual", None, l.email, l.mobile_no)}
    frappe.throw(_("Origem desconhecida."))


# «Ao cuidado de» (27-11-2026, Vítor: «deveriam poder ser pesquisados os contactos»): primeiro os da empresa/cliente
# escolhida, depois os outros; «+ Criar contacto» já ligado a ela.
@frappe.whitelist()
def contactos(q: str = "", parte: str = None, tipo: str = "Customer"):
    _guarda()
    q = cstr(q).strip()
    like = f"%{q}%"
    casa = {e.lower() for e in frappe.get_all("Email Account", pluck="email_id") if e}
    ou = [["full_name", "like", like], ["email_id", "like", like], ["mobile_no", "like", like], ["phone", "like", like]] if q else None
    out, vistos = [], set()
    if parte:
        ligados = frappe.get_all("Dynamic Link", filters={"parenttype": "Contact", "link_doctype": tipo, "link_name": parte}, pluck="parent")
        if ligados:
            for c in frappe.get_list("Contact", filters={"name": ["in", ligados]}, or_filters=ou, fields=["name", "full_name", "email_id", "mobile_no", "company_name"], limit=20):
                vistos.add(c.name)
                out.append({"name": c.name, "titulo": c.full_name or c.name, "sub": " · ".join(x for x in (c.email_id, c.mobile_no) if x), "da_parte": 1})
    if q or not out:
        for c in frappe.get_list("Contact", filters={"user": ["is", "not set"]}, or_filters=ou, fields=["name", "full_name", "email_id", "mobile_no", "company_name"],
                                 order_by="modified desc", limit=15):
            if c.name in vistos or (c.email_id or "").lower() in casa:
                continue
            out.append({"name": c.name, "titulo": c.full_name or c.name, "sub": " · ".join(x for x in (c.company_name, c.email_id, c.mobile_no) if x), "da_parte": 0})
    return out[:20]


@frappe.whitelist(methods=["POST"])
def criar_contacto(dados: str, parte: str = None, tipo: str = "Customer"):
    _guarda()
    if not frappe.has_permission("Contact", "create"):
        frappe.throw(_("Sem permissão para criar contactos."), frappe.PermissionError)
    d = frappe.parse_json(dados or "{}")
    nome = cstr(d.get("nome")).strip()
    if not nome:
        frappe.throw(_("Falta o nome do contacto."))
    partes = nome.split(" ", 1)
    c = frappe.get_doc({"doctype": "Contact", "first_name": partes[0][:140], "last_name": partes[1][:140] if len(partes) > 1 else None})
    if d.get("email"):
        c.append("email_ids", {"email_id": cstr(d["email"]).strip(), "is_primary": 1})
    if d.get("telefone"):
        c.append("phone_nos", {"phone": cstr(d["telefone"]).strip(), "is_primary_mobile_no": 1})
    if parte and tipo in ("Customer", "Lead", "Supplier") and frappe.db.exists(tipo, parte):
        c.append("links", {"link_doctype": tipo, "link_name": parte})
    c.insert()
    return {"name": c.name, "titulo": c.full_name or c.name}


# Números de série e lotes nas guias e faturas (27-11-2026, Vítor: «não foram pedidos nem números de série nem lotes»):
# quais dos artigos os exigem e os lotes com stock, para o ecrã os pedir na linha (campos serial_no/batch_no do ERPNext,
# com «use_serial_batch_fields», que o ERPNext converte no «Serial and Batch Bundle» ao submeter).
@frappe.whitelist()
def serie_lote(codigos: str, armazem: str = None):
    _guarda()
    lista = [c for c in frappe.parse_json(codigos or "[]") if c][:200]
    if not lista:
        return {}
    out = {}
    for it in frappe.get_all("Item", filters={"name": ["in", lista]}, fields=["name", "has_serial_no", "has_batch_no"]):
        if not (it.has_serial_no or it.has_batch_no):
            continue
        x = {"serie": int(it.has_serial_no or 0), "lote": int(it.has_batch_no or 0), "lotes": [], "series": []}
        if it.has_batch_no:
            x["lotes"] = [{"lote": b.name, "validade": str(b.expiry_date or "")} for b in frappe.get_all(
                "Batch", filters={"item": it.name, "disabled": 0}, fields=["name", "expiry_date"], order_by="creation asc", limit=50)]
        if it.has_serial_no:
            f = {"item_code": it.name, "status": "Active"}
            if armazem:
                f["warehouse"] = armazem
            x["series"] = frappe.get_all("Serial No", filters=f, pluck="name", order_by="creation asc", limit=200)
        out[it.name] = x
    return out
