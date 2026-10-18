"""A porta do portal no Orbit (17-10-2026, corte do Zoho).

Até hoje o portal falava com o Zoho CRM, o Zoho Desk e o Zoho Projects. Passa a falar com isto.

**Porquê métodos próprios e não `/api/resource`.** A conta de integração do portal (`portal@…`) não tem
— de propósito — poderes de escrita gerais no Orbit (ver `marcacao.cancelar`). Cada operação de que o
portal precisa é um método estreito aqui, que valida o que recebe e escreve com `ignore_permissions`.
Quem chama tem de ser a conta do portal (ou um System Manager): `_so_portal()`.

**Porquê a forma do Zoho.** Os ~30 sítios do portal que liam o CRM esperam dicionários com as chaves do
Zoho (`Account_Name`, `NIPC`, `ID_Cliente_Moloni`, `Billing_Street`…). Devolver essa forma deixa o
portal trocar só o interior do `zoho_crm.py`. O `id` de uma conta é o `crm_account_id` — a chave de
cliente do portal, que nunca muda (as contas antigas mantêm o id do Zoho; as novas recebem um id novo
com o mesmo feitio, ver `_novo_id_conta`). O `id` de um contacto é o `zoho_id` (se veio do Zoho) ou o
`name` do Contact: o portal guarda ids antigos e novos e ambos resolvem.

**Tempo.** Cada Timesheet submetido (ou cancelado) é empurrado para o portal (`/api/v1/orbit/tempo`),
que é o livro de horas dos clientes. Nunca se empurram os importados do Zoho (já lá estão) nem os que
nasceram do próprio portal (`origem_portal`) — sem eco.
"""
import hashlib
import hmac
import json
import time

import frappe
from frappe.utils import cint, flt, get_datetime, now_datetime

PORTAL_UTILIZADORES = {"portal@stratechna.com"}

# ── campos que o portal precisa e que o Zoho tinha ───────────────────────────
CAMPOS = {
    "CRM Organization": [
        dict(fieldname="saas_slug", label="Slug SaaS (portal)", fieldtype="Data", no_copy=1),
        dict(fieldname="faturar_moloni", label="Faturar no Moloni", fieldtype="Check"),
    ],
    "Timesheet": [
        # nasceu de uma estimativa do portal (plano, SEO, marca…): já está no livro de horas, não volta lá
        dict(fieldname="origem_portal", label="Registado pelo portal", fieldtype="Check", read_only=1, no_copy=1),
        dict(fieldname="portal_enviado_em", label="Enviado ao portal em", fieldtype="Datetime", read_only=1, no_copy=1),
    ],
    "Task": [
        # chave estável para o portal fechar uma tarefa sem depender do nome (blueprints, ciclos mensais)
        dict(fieldname="chave_portal", label="Chave (portal)", fieldtype="Data", no_copy=1, read_only=1, search_index=1),
    ],
    "Project": [
        # a bolsa de horas vive no portal; isto é só a fotografia para quem está no Orbit
        dict(fieldname="horas_orcamento", label="Horas do orçamento (portal)", fieldtype="Float", read_only=1, no_copy=1),
        dict(fieldname="blueprint", label="Blueprint", fieldtype="Data", read_only=1, no_copy=1),
    ],
}


def garantir() -> None:
    try:
        from frappe.custom.doctype.custom_field.custom_field import create_custom_field
        for dt, campos in CAMPOS.items():
            if not frappe.db.exists("DocType", dt):
                continue
            meta = frappe.get_meta(dt)
            for c in campos:
                if meta.has_field(c["fieldname"]):
                    continue
                create_custom_field(dt, {**c, "module": "Orbit"})
        frappe.db.commit()
    except Exception:
        frappe.log_error(title="orbit.portal.garantir")


def _so_portal() -> None:
    u = frappe.session.user
    if u in PORTAL_UTILIZADORES or u == "Administrator" or "System Manager" in frappe.get_roles(u):
        return
    frappe.throw("Só a conta de integração do portal pode usar este método.", frappe.PermissionError)


def _dados(v):
    """Pelo HTTP um dicionário/lista chega como texto JSON."""
    if isinstance(v, str):
        try:
            return json.loads(v)
        except ValueError:
            return v
    return v


def _limpo(v):
    v = (v or "").strip() if isinstance(v, str) else v
    return v or None


# ═══════════════════════════════════════════════════════════════════════════
# CRM — contas (CRM Organization) na forma de uma Account do Zoho
# ═══════════════════════════════════════════════════════════════════════════
MAPA_CONTA = {  # chave Zoho → campo da CRM Organization
    "Account_Name": "organization_name", "NIPC": "nipc", "Phone": "telefone", "Website": "website",
    "E_mail_Contabilidade": "email_contabilidade", "ID_Cliente_Moloni": "id_cliente_moloni",
    "Mbontime_CC": "mbontime_cc", "Webgate_CC": "webgate_cc", "SaasSlug": "saas_slug",
    "Rating": "estado_conta", "Account_Type": "tipo_conta", "Description": "company_description",
    "Faturar_Moloni": "faturar_moloni",
}
MAPA_MORADA = {"Billing_Street": "address_line1", "Billing_City": "city", "Billing_Code": "pincode",
               "Billing_State": "state", "Billing_Country": "country"}
PAISES = {"pt": "Portugal", "portugal": "Portugal", "espanha": "Spain", "spain": "Spain", "españa": "Spain",
          "france": "France", "frança": "France", "estados unidos da américa": "United States"}


def _org_por_id(id_conta):
    if not id_conta:
        return None
    return (frappe.db.get_value("CRM Organization", {"crm_account_id": str(id_conta)})
            or frappe.db.get_value("CRM Organization", {"zoho_id": str(id_conta)})
            or (str(id_conta) if frappe.db.exists("CRM Organization", str(id_conta)) else None))


def _conta_zoho(nome: str) -> dict:
    o = frappe.get_doc("CRM Organization", nome)
    d = {"id": o.get("crm_account_id") or o.name, "_orbit": o.name,
         "Account_Number": o.get("zoho_account_number") or o.get("crm_account_id"),
         "Owner": {"email": o.owner}, "Created_Time": str(o.creation), "Modified_Time": str(o.modified)}
    for k, f in MAPA_CONTA.items():
        v = o.get(f)
        d[k] = bool(v) if f == "faturar_moloni" else v
    d["Account_Name"] = o.organization_name or o.name
    if o.get("address"):
        a = frappe.db.get_value("Address", o.address, list(MAPA_MORADA.values()), as_dict=True) or {}
        for k, f in MAPA_MORADA.items():
            d[k] = a.get(f)
        if d.get("Billing_City") == "—":
            d["Billing_City"] = None
    return d


def _novo_id_conta() -> str:
    """Mesmo feitio dos ids do Zoho (18 algarismos, «913244…»): o portal trata-os todos como texto, mas
    há sítios que os reconhecem pela forma. «913249» marca os nascidos no Orbit."""
    while True:
        cand = "913249" + f"{time.time_ns() // 1000 % 10**12:012d}"
        if not frappe.db.exists("CRM Organization", {"crm_account_id": cand}):
            return cand


def _pais(v):
    return PAISES.get((v or "").strip().lower(), v) if v else None


def _gravar_morada(org_nome: str, dados: dict) -> None:
    vals = {f: _limpo(dados.get(k)) for k, f in MAPA_MORADA.items() if k in dados}
    if not vals:
        return
    if "country" in vals:
        vals["country"] = _pais(vals["country"]) if vals["country"] and frappe.db.exists("Country", _pais(vals["country"])) else None
    atual = frappe.db.get_value("CRM Organization", org_nome, "address")
    if atual and frappe.db.exists("Address", atual):
        a = frappe.get_doc("Address", atual)
        for f, v in vals.items():
            if v is not None or f != "country":
                a.set(f, v)
        if not a.address_line1:
            a.address_line1 = a.city or "—"
        a.city = a.city or "—"
        a.country = a.country or "Portugal"
        a.save(ignore_permissions=True)
        return
    if not any(vals.get(f) for f in ("address_line1", "city", "pincode")):
        return
    a = frappe.get_doc({"doctype": "Address", "address_title": org_nome, "address_type": "Billing",
                        "address_line1": vals.get("address_line1") or vals.get("city") or "—",
                        "city": vals.get("city") or "—", "state": vals.get("state"), "pincode": vals.get("pincode"),
                        "country": vals.get("country") or "Portugal",
                        "links": [{"link_doctype": "CRM Organization", "link_name": org_nome}]}).insert(ignore_permissions=True)
    frappe.db.set_value("CRM Organization", org_nome, "address", a.name)


@frappe.whitelist()
def conta(id_conta: str):
    _so_portal()
    n = _org_por_id(id_conta)
    return _conta_zoho(n) if n else None


@frappe.whitelist()
def procurar_contas(nome: str = None, nipc: str = None, email_contabilidade: str = None,
                    comeca: str = None, limite: int = 20):
    _so_portal()
    f = {}
    if nipc:
        nipc = "".join(ch for ch in str(nipc) if ch.isdigit())[-9:]
        f["nipc"] = ["like", f"%{nipc}"]
    if email_contabilidade:
        f["email_contabilidade"] = email_contabilidade.strip()
    if nome:
        f["organization_name"] = nome.strip()
    if comeca:
        f["organization_name"] = ["like", f"{comeca.strip()}%"]
    if not f:
        return []
    nomes = frappe.get_all("CRM Organization", filters=f, pluck="name", limit=cint(limite) or 20,
                           order_by="modified desc")
    if comeca and len(nomes) < (cint(limite) or 20):          # «começa por» também apanha palavras do meio
        mais = frappe.get_all("CRM Organization", filters={"organization_name": ["like", f"% {comeca.strip()}%"]},
                              pluck="name", limit=cint(limite) or 20)
        nomes += [m for m in mais if m not in nomes]
    return [_conta_zoho(n) for n in nomes]


def _campos_conta(dados: dict) -> dict:
    out = {}
    for k, f in MAPA_CONTA.items():
        if k in dados:
            v = dados[k]
            out[f] = (1 if v else 0) if f == "faturar_moloni" else _limpo(v)
    if out.get("nipc"):
        out["nipc"] = "".join(ch for ch in str(out["nipc"]) if ch.isalnum())
        if out["nipc"].upper().startswith("PT") and len(out["nipc"]) == 11:
            out["nipc"] = out["nipc"][2:]          # regra da casa: 9 algarismos no que se guarda
    if out.get("estado_conta") and out["estado_conta"] not in ("Activo", "Adquirido", "Encerrar", "Projecto cancelado", "Falhou"):
        out.pop("estado_conta")
    if out.get("tipo_conta") and out["tipo_conta"] not in ("Cliente", "Parceiro", "Fornecedor", "Revendedor", "Concorrente", "Outro"):
        out.pop("tipo_conta")
    return out


@frappe.whitelist()
def criar_conta(dados):
    """Cria a conta (e a morada). Se já existe uma com o mesmo NIPC, devolve essa — o portal fazia esta
    deduplicação contra o Zoho antes de criar; aqui fica garantida do lado de quem guarda."""
    _so_portal()
    dados = _dados(dados) or {}
    campos = _campos_conta(dados)
    if not campos.get("organization_name"):
        frappe.throw("Falta o nome da conta (Account_Name).")
    if campos.get("nipc"):
        ja = frappe.db.get_value("CRM Organization", {"nipc": campos["nipc"]})
        if ja:
            return _conta_zoho(ja)
    nome = campos["organization_name"]
    if frappe.db.exists("CRM Organization", nome):
        nome = f"{nome} ({(campos.get('nipc') or str(int(time.time())))[-4:]})"
    id_conta = _limpo(dados.get("id")) or _novo_id_conta()
    o = frappe.get_doc({"doctype": "CRM Organization", **campos, "organization_name": nome, "crm_account_id": id_conta})
    o.insert(ignore_permissions=True)
    _gravar_morada(o.name, dados)
    frappe.db.commit()
    return _conta_zoho(o.name)


@frappe.whitelist()
def atualizar_conta(id_conta: str, dados):
    _so_portal()
    n = _org_por_id(id_conta)
    if not n:
        frappe.throw(f"Conta {id_conta} não existe no Orbit.", frappe.DoesNotExistError)
    dados = _dados(dados) or {}
    o = frappe.get_doc("CRM Organization", n)
    campos = _campos_conta(dados)
    campos.pop("organization_name", None) if not campos.get("organization_name") else None
    o.update(campos)
    o.save(ignore_permissions=True)
    _gravar_morada(o.name, dados)
    # o cliente do ERP acompanha o que interessa à faturação
    if o.get("customer") and frappe.db.exists("Customer", o.customer):
        c = {k: v for k, v in {"id_cliente_moloni": o.get("id_cliente_moloni"), "email_contabilidade": o.get("email_contabilidade"),
                               "faturar_moloni": o.get("faturar_moloni")}.items() if v is not None}
        if c:
            frappe.db.set_value("Customer", o.customer, c)
    frappe.db.commit()
    return _conta_zoho(o.name)


# ═══════════════════════════════════════════════════════════════════════════
# CRM — contactos na forma de um Contact do Zoho
# ═══════════════════════════════════════════════════════════════════════════
def _contacto_por_id(id_contacto):
    if not id_contacto:
        return None
    return (frappe.db.get_value("Contact", {"zoho_id": str(id_contacto)})
            or (str(id_contacto) if frappe.db.exists("Contact", str(id_contacto)) else None))


def _org_do_contacto(c) -> str | None:
    for l in c.links or []:
        if l.link_doctype == "CRM Organization":
            return l.link_name
    return c.get("company_name") if c.get("company_name") and frappe.db.exists("CRM Organization", c.company_name) else None


def _contacto_zoho(nome: str) -> dict:
    c = frappe.get_doc("Contact", nome)
    org = _org_do_contacto(c)
    secundario = next((e.email_id for e in c.email_ids or [] if not e.is_primary), None)
    d = {"id": c.get("zoho_id") or c.name, "_orbit": c.name, "First_Name": c.first_name, "Last_Name": c.last_name,
         "Full_Name": " ".join(filter(None, [c.first_name, c.last_name])), "Email": c.email_id,
         "Secondary_Email": secundario, "Phone": c.phone, "Mobile": c.mobile_no, "Title": c.designation,
         "Department": c.department, "Salutation": c.salutation, "NIF": c.get("nif"),
         "Lead_Source": c.get("origem"),
         "Aprova_Redes_Sociais": bool(c.get("aprova_redes_sociais")),
         "Aprova_Publicidade_Digital": bool(c.get("aprova_publicidade_digital")),
         "Owner": {"email": c.owner}, "Created_Time": str(c.creation), "Modified_Time": str(c.modified)}
    if org:
        d["Account_Name"] = {"id": frappe.db.get_value("CRM Organization", org, "crm_account_id") or org,
                             "name": frappe.db.get_value("CRM Organization", org, "organization_name") or org}
    else:
        d["Account_Name"] = None
    return d


@frappe.whitelist()
def contacto(id_contacto: str):
    _so_portal()
    n = _contacto_por_id(id_contacto)
    return _contacto_zoho(n) if n else None


@frappe.whitelist()
def procurar_contactos(email: str = None, nome: str = None, limite: int = 20):
    _so_portal()
    nomes = []
    if email:
        e = email.strip().lower()
        nomes = frappe.get_all("Contact Email", filters={"email_id": e, "parenttype": "Contact"}, pluck="parent", distinct=True)
        nomes += [n for n in frappe.get_all("Contact", filters={"email_id": e}, pluck="name") if n not in nomes]
    elif nome:
        nomes = frappe.get_all("Contact", or_filters={"first_name": ["like", f"%{nome}%"], "last_name": ["like", f"%{nome}%"],
                                                      "full_name": ["like", f"%{nome}%"]},
                               pluck="name", limit=cint(limite) or 20)
    return [_contacto_zoho(n) for n in nomes[: cint(limite) or 20]]


@frappe.whitelist()
def contactos(id_conta: str):
    _so_portal()
    org = _org_por_id(id_conta)
    if not org:
        return []
    nomes = frappe.get_all("Dynamic Link", filters={"parenttype": "Contact", "link_doctype": "CRM Organization",
                                                    "link_name": org}, pluck="parent", distinct=True)
    nomes += [n for n in frappe.get_all("Contact", filters={"company_name": org}, pluck="name") if n not in nomes]
    return [_contacto_zoho(n) for n in nomes]


def _aplicar_contacto(c, dados: dict) -> None:
    mapa = {"First_Name": "first_name", "Last_Name": "last_name", "Title": "designation", "Department": "department",
            "NIF": "nif"}
    for k, f in mapa.items():
        if k in dados:
            c.set(f, _limpo(dados[k]))
    if "Salutation" in dados and dados["Salutation"] and frappe.db.exists("Salutation", dados["Salutation"]):
        c.salutation = dados["Salutation"]
    if "Lead_Source" in dados and dados["Lead_Source"]:
        if not frappe.db.exists("CRM Lead Source", dados["Lead_Source"]):
            frappe.get_doc({"doctype": "CRM Lead Source", "source_name": dados["Lead_Source"]}).insert(ignore_permissions=True)
        c.origem = dados["Lead_Source"]
    for k, f in (("Aprova_Redes_Sociais", "aprova_redes_sociais"), ("Aprova_Publicidade_Digital", "aprova_publicidade_digital")):
        if k in dados:
            c.set(f, 1 if dados[k] else 0)
    if not c.first_name:
        c.first_name = c.last_name or (dados.get("Email") or "Contacto").split("@")[0]
        if c.first_name == c.last_name:
            c.last_name = None
    if dados.get("Email"):
        e = dados["Email"].strip().lower()
        if not any((x.email_id or "").lower() == e for x in c.email_ids or []):
            for x in c.email_ids or []:
                x.is_primary = 0
            c.append("email_ids", {"email_id": e, "is_primary": 1})
        else:
            for x in c.email_ids:
                x.is_primary = 1 if (x.email_id or "").lower() == e else 0
    if dados.get("Secondary_Email"):
        e2 = dados["Secondary_Email"].strip().lower()
        if not any((x.email_id or "").lower() == e2 for x in c.email_ids or []):
            c.append("email_ids", {"email_id": e2, "is_primary": 0})
    for k, primario in (("Mobile", "is_primary_mobile_no"), ("Phone", "is_primary_phone")):
        if k in dados and dados[k]:
            t = str(dados[k]).strip()
            linha = next((x for x in c.phone_nos or [] if x.phone == t), None)
            if not linha:
                for x in c.phone_nos or []:
                    x.set(primario, 0)
                c.append("phone_nos", {"phone": t, primario: 1})
            else:
                linha.set(primario, 1)
    conta_ref = dados.get("Account_Name")
    id_conta = conta_ref.get("id") if isinstance(conta_ref, dict) else dados.get("id_conta")
    org = _org_por_id(id_conta) if id_conta else None
    if org:
        c.company_name = org
        if not any(l.link_doctype == "CRM Organization" and l.link_name == org for l in c.links or []):
            c.append("links", {"link_doctype": "CRM Organization", "link_name": org})
        cust = frappe.db.get_value("CRM Organization", org, "customer")
        if cust and not any(l.link_doctype == "Customer" and l.link_name == cust for l in c.links or []):
            c.append("links", {"link_doctype": "Customer", "link_name": cust})


@frappe.whitelist()
def criar_contacto(dados):
    """Cria (ou devolve o existente com o mesmo email — dois contactos com o mesmo email não existem)."""
    _so_portal()
    dados = _dados(dados) or {}
    if dados.get("Email"):
        ja = procurar_contactos(email=dados["Email"], limite=1)
        if ja:
            return atualizar_contacto(ja[0]["id"], dados)
    c = frappe.new_doc("Contact")
    _aplicar_contacto(c, dados)
    c.insert(ignore_permissions=True)
    frappe.db.commit()
    return _contacto_zoho(c.name)


@frappe.whitelist()
def atualizar_contacto(id_contacto: str, dados):
    _so_portal()
    n = _contacto_por_id(id_contacto)
    if not n:
        frappe.throw(f"Contacto {id_contacto} não existe no Orbit.", frappe.DoesNotExistError)
    c = frappe.get_doc("Contact", n)
    _aplicar_contacto(c, _dados(dados) or {})
    c.save(ignore_permissions=True)
    frappe.db.commit()
    return _contacto_zoho(c.name)


# ═══════════════════════════════════════════════════════════════════════════
# CRM — leads e negócios
# ═══════════════════════════════════════════════════════════════════════════
FASES = {"Ganho fechado": "Won", "Closed Won": "Won", "Proposta Aceite": "Ready to Close",
         "Proposta de valor": "Proposal/Quotation", "Negociação": "Negotiation", "Perdido": "Lost",
         "Qualificação": "Qualification"}


@frappe.whitelist()
def criar_lead(dados):
    _so_portal()
    d = _dados(dados) or {}
    fonte = _limpo(d.get("Lead_Source"))
    if fonte and not frappe.db.exists("CRM Lead Source", fonte):
        frappe.get_doc({"doctype": "CRM Lead Source", "source_name": fonte}).insert(ignore_permissions=True)
    l = frappe.get_doc({"doctype": "CRM Lead", "status": "New",
                        "first_name": _limpo(d.get("First_Name")) or _limpo(d.get("Last_Name")) or "—",
                        "last_name": _limpo(d.get("Last_Name")) if d.get("First_Name") else None,
                        "email": _limpo(d.get("Email")), "mobile_no": _limpo(d.get("Mobile")), "phone": _limpo(d.get("Phone")),
                        "organization": _limpo(d.get("Company")), "website": _limpo(d.get("Website")), "source": fonte,
                        "marca": d.get("marca") if d.get("marca") and frappe.db.exists("Brand", d.get("marca")) else None})
    l.insert(ignore_permissions=True)
    if d.get("Description"):
        frappe.get_doc({"doctype": "FCRM Note", "title": "Pedido", "content": frappe.utils.escape_html(d["Description"]).replace("\n", "<br>"),
                        "reference_doctype": "CRM Lead", "reference_docname": l.name}).insert(ignore_permissions=True)
    frappe.db.commit()
    return {"id": l.name}


@frappe.whitelist()
def criar_deal(dados):
    _so_portal()
    d = _dados(dados) or {}
    conta_ref = d.get("Account_Name")
    org = _org_por_id(conta_ref.get("id") if isinstance(conta_ref, dict) else conta_ref)
    cont_ref = d.get("Contact_Name")
    cont = _contacto_por_id(cont_ref.get("id") if isinstance(cont_ref, dict) else cont_ref)
    status = FASES.get(d.get("Stage"), d.get("Stage") if frappe.db.exists("CRM Deal Status", d.get("Stage") or "") else "Qualification")
    deal = frappe.get_doc({"doctype": "CRM Deal", "status": status, "organization": org, "titulo": _limpo(d.get("Deal_Name")),
                           "deal_value": flt(d.get("Amount")), "expected_deal_value": flt(d.get("Amount")),
                           "probability": flt(d.get("Probability") or (100 if status == "Won" else 0)),
                           "expected_closure_date": d.get("Closing_Date"),
                           "closed_date": d.get("Closing_Date") if status == "Won" else None,
                           "moloni_document_id": _limpo(d.get("Moloni_Document_ID")),
                           "marca": d.get("marca") if d.get("marca") and frappe.db.exists("Brand", d.get("marca")) else
                           (frappe.db.get_value("CRM Organization", org, "marca") if org else None)})
    if cont:
        deal.append("contacts", {"contact": cont, "is_primary": 1})
    # Negócio em nome do lead (propostas, 18-10-2026): fica ligado ao lead e com os dados dele.
    lead = d.get("Lead") if d.get("Lead") and frappe.db.exists("CRM Lead", d.get("Lead")) else None
    if lead:
        l = frappe.db.get_value("CRM Lead", lead, ["first_name", "last_name", "email", "mobile_no", "phone",
                                                  "organization", "source", "marca", "lead_name"], as_dict=True)
        deal.update({"lead": lead, "lead_name": l.lead_name, "first_name": l.first_name, "last_name": l.last_name,
                     "email": l.email, "mobile_no": l.mobile_no, "phone": l.phone, "source": l.source,
                     "organization_name": l.organization})
        if not deal.marca and l.marca:
            deal.marca = l.marca
    elif d.get("Lead_Source") and frappe.db.exists("CRM Lead Source", d.get("Lead_Source")):
        deal.source = d.get("Lead_Source")
    deal.insert(ignore_permissions=True)
    if lead and frappe.db.get_value("CRM Lead", lead, "status") in ("New", "Contacted", "Nurture"):
        frappe.db.set_value("CRM Lead", lead, "status", "Qualified")
    if d.get("Description"):
        frappe.get_doc({"doctype": "FCRM Note", "title": "Descrição", "content": frappe.utils.escape_html(d["Description"]).replace("\n", "<br>"),
                        "reference_doctype": "CRM Deal", "reference_docname": deal.name}).insert(ignore_permissions=True)
    frappe.db.commit()
    return {"id": deal.name}


@frappe.whitelist()
def atualizar_deal(id_deal: str, dados):
    _so_portal()
    n = id_deal if frappe.db.exists("CRM Deal", id_deal) else frappe.db.get_value("CRM Deal", {"zoho_id": id_deal})
    if not n:
        frappe.throw(f"Negócio {id_deal} não existe no Orbit.", frappe.DoesNotExistError)
    d = _dados(dados) or {}
    deal = frappe.get_doc("CRM Deal", n)
    if d.get("Stage"):
        deal.status = FASES.get(d["Stage"], d["Stage"] if frappe.db.exists("CRM Deal Status", d["Stage"]) else deal.status)
        if deal.status in ("Won", "Lost") and d.get("Closing_Date"):
            deal.closed_date = d["Closing_Date"]
        if deal.status == "Won":
            deal.probability = 100
        if deal.status == "Lost":
            motivo = d.get("Lost_Reason") if frappe.db.exists("CRM Lost Reason", d.get("Lost_Reason") or "") else "Other"
            deal.lost_reason = deal.lost_reason or motivo
            if deal.lost_reason == "Other" and not deal.lost_notes:
                deal.lost_notes = _limpo(d.get("Lost_Notes")) or "Sem motivo indicado."
    for k, f in (("Amount", "deal_value"), ("Closing_Date", "expected_closure_date"), ("Moloni_Document_ID", "moloni_document_id"),
                 ("Deal_Name", "titulo")):
        if k in d:
            deal.set(f, d[k])
    deal.save(ignore_permissions=True)
    frappe.db.commit()
    return {"id": deal.name}


# ═══════════════════════════════════════════════════════════════════════════
# Tempo — Timesheet → livro de horas do portal
# ═══════════════════════════════════════════════════════════════════════════
def _destino():
    url = frappe.conf.get("orbit_portal_tempo_url")
    seg = frappe.conf.get("orbit_portal_segredo")
    return (url, seg) if url and seg else (None, None)


def _payload_tempo(ts, accao: str) -> dict:
    linhas = []
    for l in ts.time_logs or []:
        linhas.append({"id": l.name, "horas": flt(l.hours), "faturavel": cint(l.is_billable),
                       "inicio": str(l.from_time) if l.from_time else None, "descricao": l.description,
                       "projeto": l.project, "tarefa": l.task, "actividade": l.activity_type})
    crm_id, equipa, marca, bilhete, info_bilhete = None, None, None, ts.get("custom_hd_ticket"), None
    if bilhete and frappe.db.exists("HD Ticket", bilhete):
        b = frappe.db.get_value("HD Ticket", bilhete, ["crm_account_id", "agent_group", "orbit_marca", "customer", "subject",
                                                       "status", "contact", "tarefa_mbontime", "zoho_ticket_number"], as_dict=True)
        crm_id = b.crm_account_id or (frappe.db.get_value("HD Customer", b.customer, "crm_account_id") if b.customer else None)
        equipa, marca = b.agent_group, b.orbit_marca
        info_bilhete = {"numero": b.zoho_ticket_number or bilhete, "assunto": b.subject, "estado": b.status,
                        "tarefa": b.tarefa_mbontime,
                        "contacto": frappe.db.get_value("Contact", b.contact, "full_name") if b.contact else None}
    projeto = ts.get("parent_project") or next((l.project for l in ts.time_logs or [] if l.project), None)
    if projeto and frappe.db.exists("Project", projeto):
        p = frappe.db.get_value("Project", projeto, ["crm_account_id", "marca", "zoho_id", "subscricao_portal"], as_dict=True)
        crm_id = crm_id or p.crm_account_id
        marca = marca or p.marca
    return {"accao": accao, "timesheet": ts.name, "utilizador": ts.get("user") or ts.owner, "bilhete": bilhete,
            "equipa": equipa, "marca": marca, "projeto": projeto,
            "projeto_zoho_id": frappe.db.get_value("Project", projeto, "zoho_id") if projeto else None,
            "crm_account_id": crm_id, "nota": ts.get("note"), "linhas": linhas, "site": frappe.local.site,
            "info_bilhete": info_bilhete}


def enviar_tempo(timesheet: str, accao: str) -> None:
    """Corre na fila (enqueue). Assina o corpo com HMAC-SHA256; o portal recusa sem assinatura."""
    url, seg = _destino()
    if not url:
        return
    if not frappe.db.exists("Timesheet", timesheet) and accao != "apagado":
        return
    import requests
    corpo = json.dumps(_payload_tempo(frappe.get_doc("Timesheet", timesheet), accao) if frappe.db.exists("Timesheet", timesheet)
                       else {"accao": accao, "timesheet": timesheet, "linhas": [], "site": frappe.local.site},
                       ensure_ascii=False, default=str).encode()
    assinatura = hmac.new(seg.encode(), corpo, hashlib.sha256).hexdigest()
    r = requests.post(url, data=corpo, timeout=20,
                      headers={"Content-Type": "application/json", "X-Orbit-Assinatura": assinatura})
    if r.status_code >= 300:
        raise Exception(f"portal recusou o tempo de {timesheet}: {r.status_code} {r.text[:200]}")
    if frappe.db.exists("Timesheet", timesheet):
        frappe.db.set_value("Timesheet", timesheet, "portal_enviado_em", now_datetime(), update_modified=False)


def _deve_enviar(doc) -> bool:
    return not (doc.get("importado_zoho") or doc.get("origem_portal")) and bool(_destino()[0])


def tempo_submetido(doc, method=None):
    if _deve_enviar(doc):
        frappe.enqueue("orbit.portal.enviar_tempo", queue="short", timesheet=doc.name, accao="submetido",
                       enqueue_after_commit=True)


def tempo_cancelado(doc, method=None):
    if _deve_enviar(doc):
        frappe.enqueue("orbit.portal.enviar_tempo", queue="short", timesheet=doc.name, accao="cancelado",
                       enqueue_after_commit=True)


@frappe.whitelist()
def registar_tempo(dados):
    """O portal regista tempo no Orbit (cronómetros do admin, bilhetes, projectos).
    `origem_portal=1` quando o portal já lançou a linha no livro de horas; senão o Orbit empurra-a."""
    _so_portal()
    d = _dados(dados) or {}
    if d.get("referencia"):
        ja = frappe.db.get_value("Timesheet", {"note": ["like", f"%[ref:{d['referencia']}]%"], "docstatus": ["<", 2]})
        if ja:
            return {"timesheet": ja, "repetido": True}
    bilhete = d.get("bilhete") if d.get("bilhete") and frappe.db.exists("HD Ticket", d.get("bilhete")) else None
    projeto = d.get("projeto") if d.get("projeto") and frappe.db.exists("Project", d.get("projeto")) else None
    tarefa = d.get("tarefa") if d.get("tarefa") and frappe.db.exists("Task", d.get("tarefa")) else None
    inicio = get_datetime(d.get("inicio")) if d.get("inicio") else now_datetime()
    horas = flt(d.get("horas"))
    if horas <= 0:
        frappe.throw("Horas têm de ser positivas.")
    actividade = d.get("actividade") or ("Apoio ao cliente" if bilhete else "Execution")
    if not frappe.db.exists("Activity Type", actividade):
        frappe.get_doc({"doctype": "Activity Type", "activity_type": actividade}).insert(ignore_permissions=True)
    cust = None
    if projeto:
        cust = frappe.db.get_value("Project", projeto, "customer")
    elif bilhete:
        crm = frappe.db.get_value("HD Ticket", bilhete, "crm_account_id")
        cust = frappe.db.get_value("Customer", {"crm_account_id": crm}) if crm else None
    utilizador = d.get("utilizador") if d.get("utilizador") and frappe.db.exists("User", d.get("utilizador")) else None
    nota = (d.get("nota") or "") + (f" [ref:{d['referencia']}]" if d.get("referencia") else "")
    ts = frappe.get_doc({"doctype": "Timesheet", "company": frappe.get_all("Company", pluck="name")[0],
                         "custom_hd_ticket": bilhete, "parent_project": projeto, "customer": cust,
                         "origem_portal": 1 if d.get("origem_portal") else 0, "note": nota.strip() or None,
                         "user": utilizador,
                         "time_logs": [{"activity_type": actividade, "from_time": inicio, "hours": horas,
                                        "to_time": frappe.utils.add_to_date(inicio, seconds=int(horas * 3600)),
                                        "project": projeto, "task": tarefa, "description": d.get("descricao"),
                                        "is_billable": 1 if d.get("faturavel") else 0}]})
    ts.flags.ignore_permissions = True
    ts.insert()
    ts.submit()
    if utilizador:
        frappe.db.set_value("Timesheet", ts.name, "user", utilizador, update_modified=False)
    frappe.db.commit()
    return {"timesheet": ts.name, "linha": ts.time_logs[0].name}


# ═══════════════════════════════════════════════════════════════════════════
# Desk — bilhetes (HD Ticket) na forma que o portal já mostrava
# ═══════════════════════════════════════════════════════════════════════════
EQUIPA_SLUG = {"Stratechna": "stratechna", "Webgate": "webgate", "MBontime": "mbontime", "Triagem": "triagem"}
SLUG_EQUIPA = {v: k for k, v in EQUIPA_SLUG.items()}
ESTADO_TIPO = {"Open": "Open", "Replied": "On Hold", "Resolved": "Closed", "Closed": "Closed"}


def _bilhete_por_id(b):
    if not b:
        return None
    b = str(b)
    if frappe.db.exists("HD Ticket", b):
        return b
    return frappe.db.get_value("HD Ticket", {"zoho_id": b})


def _nome_utilizador(u):
    return frappe.db.get_value("User", u, "full_name") if u else None


def _bilhete_resumo(t) -> dict:
    resp = None
    try:
        a = json.loads(t.get("_assign") or "[]")
        resp = _nome_utilizador(a[0]) if a else None
    except ValueError:
        pass
    conta_nome = None
    if t.get("crm_account_id"):
        conta_nome = frappe.db.get_value("CRM Organization", {"crm_account_id": t["crm_account_id"]}, "organization_name")
    return {"id": t["name"], "numero": t.get("zoho_ticket_number") or t["name"], "assunto": t.get("subject"),
            "estado": t.get("status"), "estado_tipo": ESTADO_TIPO.get(t.get("status"), t.get("status")),
            "prioridade": t.get("priority"), "departamento_id": t.get("agent_group"),
            "departamento": t.get("agent_group"), "dept_slug": EQUIPA_SLUG.get(t.get("agent_group") or "", ""),
            "conta": conta_nome or t.get("customer") or "", "responsavel": resp,
            "criado_em": str(t.get("creation")), "modificado_em": str(t.get("modified")),
            "crm_account_id": t.get("crm_account_id")}


@frappe.whitelist()
def bilhetes(id_conta: str = None, equipa: str = None, estado: str = None, limite: int = 50, pagina: int = 1):
    """Sem conta: todos (aba Suporte do admin). Com conta: só os dessa conta."""
    _so_portal()
    f = {}
    if id_conta:
        cust = frappe.db.get_value("HD Customer", {"crm_account_id": str(id_conta)})
        f_or = {"crm_account_id": str(id_conta)}
        if cust:
            f_or["customer"] = cust
    else:
        f_or = None
    if equipa:
        f["agent_group"] = SLUG_EQUIPA.get(equipa, equipa)
    if estado:
        f["status"] = estado
    limite, pagina = cint(limite) or 50, max(1, cint(pagina) or 1)
    campos = ["name", "subject", "status", "priority", "agent_group", "customer", "crm_account_id", "creation",
              "modified", "_assign", "zoho_ticket_number"]
    linhas = frappe.get_all("HD Ticket", filters=f, or_filters=f_or, fields=campos, order_by="modified desc",
                            limit_start=(pagina - 1) * limite, limit_page_length=limite)
    total = len(frappe.get_all("HD Ticket", filters=f, or_filters=f_or, pluck="name"))
    return {"tickets": [_bilhete_resumo(t) for t in linhas], "total": total, "page": pagina,
            "pages": max(1, -(-total // limite))}


@frappe.whitelist()
def bilhete(id_bilhete: str):
    _so_portal()
    n = _bilhete_por_id(id_bilhete)
    if not n:
        return None
    t = frappe.get_doc("HD Ticket", n)
    d = _bilhete_resumo(t.as_dict())
    d["descricao"] = frappe.utils.strip_html(t.description or "")
    d["resolucao"] = frappe.utils.strip_html(t.get("resolution_details") or "")
    d["tarefa"] = t.get("tarefa_mbontime")
    d["contacto"] = frappe.db.get_value("Contact", t.contact, "full_name") if t.contact else None
    d["raised_by"] = t.raised_by
    mensagens = frappe.get_all("Communication", filters={"reference_doctype": "HD Ticket", "reference_name": n},
                               fields=["name", "content", "sender", "sender_full_name", "communication_date", "sent_or_received"],
                               order_by="communication_date asc")
    comentarios = frappe.get_all("HD Ticket Comment", filters={"reference_ticket": n},
                                 fields=["name", "content", "commented_by", "creation"], order_by="creation asc")
    # o cliente vê as mensagens trocadas; os comentários internos do Desk não saem daqui
    d["comentarios"] = [{"id": m.name, "conteudo": frappe.utils.strip_html(m.content or ""),
                         "autor": m.sender_full_name or m.sender, "criado_em": str(m.communication_date),
                         "sentido": "recebida" if m.sent_or_received == "Received" else "enviada"} for m in mensagens]
    d["notas_internas"] = [{"id": c.name, "conteudo": frappe.utils.strip_html(c.content or ""),
                            "autor": _nome_utilizador(c.commented_by) or c.commented_by, "criado_em": str(c.creation)}
                           for c in comentarios]
    tempos = frappe.db.sql("""select ts.name, ts.user, d.hours, d.description, d.from_time
                              from `tabTimesheet` ts join `tabTimesheet Detail` d on d.parent = ts.name
                              where ts.custom_hd_ticket = %s and ts.docstatus = 1 order by d.from_time""", n, as_dict=True)
    d["time_entries"] = [{"agente": _nome_utilizador(x.user) or x.user or "", "minutos": round(flt(x.hours) * 60),
                          "descricao": x.description or "", "data": str(x.from_time)[:10] if x.from_time else ""} for x in tempos]
    d["tempo_total_min"] = sum(x["minutos"] for x in d["time_entries"])
    return d


@frappe.whitelist()
def criar_bilhete(dados):
    """Abre um bilhete em nome do cliente. Equipa pela marca (`equipa`), senão o Desk decide (Triagem)."""
    _so_portal()
    d = _dados(dados) or {}
    if not d.get("assunto"):
        frappe.throw("Falta o assunto.")
    id_conta = _limpo(d.get("id_conta"))
    cust = frappe.db.get_value("HD Customer", {"crm_account_id": id_conta}) if id_conta else None
    if id_conta and not cust:
        org = _org_por_id(id_conta)
        if org:
            nome = frappe.db.get_value("CRM Organization", org, "organization_name") or org
            if frappe.db.exists("HD Customer", nome):
                nome = f"{nome} ({id_conta[-4:]})"
            cust = frappe.get_doc({"doctype": "HD Customer", "customer_name": nome, "crm_account_id": id_conta}).insert(ignore_permissions=True).name
    email = _limpo(d.get("email"))
    cont = None
    if email:
        cont = frappe.db.get_value("Contact", {"email_id": email.lower()})
    equipa = SLUG_EQUIPA.get(d.get("equipa") or "", d.get("equipa"))
    t = frappe.get_doc({"doctype": "HD Ticket", "subject": d["assunto"][:140],
                        "description": frappe.utils.escape_html(d.get("descricao") or "").replace("\n", "<br>"),
                        "raised_by": email, "contact": cont, "customer": cust, "crm_account_id": id_conta,
                        "priority": d.get("prioridade") if d.get("prioridade") in ("Low", "Medium", "High", "Urgent") else "Medium",
                        "canal": d.get("canal") or "Web", "tarefa_mbontime": _limpo(d.get("tarefa")),
                        "agent_group": equipa if equipa and frappe.db.exists("HD Team", equipa) else None,
                        "orbit_marca": equipa if equipa in ("Stratechna", "Webgate", "MBontime") else None})
    t.flags.ignore_permissions = True
    t.insert()
    frappe.db.commit()
    return {"ok": True, "ticket_id": t.name, "numero": t.name}


@frappe.whitelist()
def comentar_bilhete(id_bilhete: str, conteudo: str, autor_email: str = None, interno: int = 0):
    """Resposta do cliente pelo portal (entra como mensagem recebida) ou nota interna da equipa."""
    _so_portal()
    n = _bilhete_por_id(id_bilhete)
    if not n:
        frappe.throw("Bilhete não existe.", frappe.DoesNotExistError)
    html = frappe.utils.escape_html(conteudo or "").replace("\n", "<br>")
    if cint(interno):
        frappe.get_doc({"doctype": "HD Ticket Comment", "reference_ticket": n, "content": html,
                        "commented_by": autor_email if autor_email and frappe.db.exists("User", autor_email) else "Administrator"}
                       ).insert(ignore_permissions=True)
    else:
        frappe.get_doc({"doctype": "Communication", "communication_type": "Communication", "communication_medium": "Email",
                        "sent_or_received": "Received", "subject": frappe.db.get_value("HD Ticket", n, "subject"),
                        "sender": autor_email or frappe.db.get_value("HD Ticket", n, "raised_by"), "content": html,
                        "reference_doctype": "HD Ticket", "reference_name": n, "communication_date": now_datetime(),
                        "seen": 0}).insert(ignore_permissions=True)
        if frappe.db.get_value("HD Ticket", n, "status") in ("Replied", "Resolved"):
            frappe.db.set_value("HD Ticket", n, "status", "Open")
    frappe.db.commit()
    return {"ok": True}


@frappe.whitelist()
def fechar_bilhete(id_bilhete: str):
    _so_portal()
    n = _bilhete_por_id(id_bilhete)
    if not n:
        frappe.throw("Bilhete não existe.", frappe.DoesNotExistError)
    # db_set: o fecho pelo portal não pede a avaliação que o ecrã do Desk exige
    frappe.db.set_value("HD Ticket", n, {"status": "Closed", "resolution_date": now_datetime()})
    frappe.db.commit()
    return {"ok": True}


@frappe.whitelist()
def contactos_para_bilhete(q: str, limite: int = 10):
    """Pesquisa do admin ao abrir um bilhete em nome de alguém."""
    _so_portal()
    out = []
    for c in frappe.get_all("Contact", or_filters={"full_name": ["like", f"%{q}%"], "email_id": ["like", f"%{q}%"]},
                            fields=["name", "full_name", "email_id"], limit=cint(limite) or 10):
        org = frappe.db.get_value("Dynamic Link", {"parenttype": "Contact", "parent": c.name, "link_doctype": "CRM Organization"}, "link_name")
        out.append({"id": c.name, "nome": c.full_name, "email": c.email_id,
                    "crm_account_id": frappe.db.get_value("CRM Organization", org, "crm_account_id") if org else None,
                    "account_nome": frappe.db.get_value("CRM Organization", org, "organization_name") if org else ""})
    return {"contactos": out}


# ═══════════════════════════════════════════════════════════════════════════
# Projectos (Project / Task)
# ═══════════════════════════════════════════════════════════════════════════
def _projeto_por_id(p):
    if not p:
        return None
    p = str(p)
    if frappe.db.exists("Project", p):
        return p
    return frappe.db.get_value("Project", {"zoho_id": p})


def _url(doctype_rota: str, nome: str) -> str:
    return f"{frappe.utils.get_url()}/app/{doctype_rota}/{nome}"


@frappe.whitelist()
def projetos(id_conta: str = None, estado: str = "Open"):
    _so_portal()
    f = {"crm_account_id": str(id_conta)} if id_conta else {}
    if estado:
        f["status"] = estado
    out = []
    for p in frappe.get_all("Project", filters=f, fields=["name", "project_name", "status", "percent_complete",
                                                           "crm_account_id", "subscricao_portal", "dominio", "marca",
                                                           "zoho_id", "blueprint", "horas_orcamento", "creation",
                                                           "expected_start_date", "expected_end_date"],
                            order_by="creation desc"):
        p["id"] = p["name"]
        p["url"] = _url("project", p["name"])
        out.append(p)
    return out


def _horas_reais(tarefas: list) -> dict:
    if not tarefas:
        return {}
    r = frappe.db.sql("""select d.task, sum(d.hours) from `tabTimesheet Detail` d join `tabTimesheet` ts on ts.name = d.parent
                         where ts.docstatus = 1 and d.task in %(t)s group by d.task""", {"t": tuple(tarefas)})
    return {a: flt(b) for a, b in r}


@frappe.whitelist()
def projeto(id_projeto: str):
    """Projecto com as fases (tarefas-grupo) e as tarefas, horas estimadas e registadas."""
    _so_portal()
    n = _projeto_por_id(id_projeto)
    if not n:
        return None
    p = frappe.get_doc("Project", n)
    ts = frappe.get_all("Task", filters={"project": n}, fields=["name", "subject", "status", "progress", "is_group",
                                                                 "parent_task", "expected_time", "exp_start_date",
                                                                 "exp_end_date", "completed_on", "ordem", "chave_portal",
                                                                 "zoho_id"], order_by="ordem asc, creation asc")
    reais = _horas_reais([t.name for t in ts])
    por_mae = {}
    for t in ts:
        t["horas_registadas"] = reais.get(t.name, 0)
        t["url"] = _url("task", t.name)
        por_mae.setdefault(t.parent_task, []).append(t)
    fases = []
    for g in [t for t in ts if t.is_group and not t.parent_task]:
        filhas = por_mae.get(g.name, [])
        netas = [x for f in filhas if f.is_group for x in por_mae.get(f.name, [])]
        todas = [f for f in filhas] + netas
        fases.append({"id": g.name, "nome": g.subject, "estado": g.status,
                      "tarefas": [{**f, "subtarefas": por_mae.get(f.name, [])} for f in filhas],
                      "total": len([f for f in filhas]), "concluidas": len([f for f in filhas if f.status == "Completed"]),
                      "horas_estimadas": sum(flt(x.expected_time) for x in todas),
                      "horas_registadas": sum(x["horas_registadas"] for x in todas)})
    soltas = [t for t in por_mae.get(None, []) if not t.is_group] + [t for t in por_mae.get("", []) if not t.is_group]
    return {"id": p.name, "nome": p.project_name, "estado": p.status, "percentagem": flt(p.percent_complete),
            "crm_account_id": p.get("crm_account_id"), "subscricao_portal": p.get("subscricao_portal"),
            "dominio": p.get("dominio"), "marca": p.get("marca"), "blueprint": p.get("blueprint"),
            "horas_orcamento": flt(p.get("horas_orcamento")), "zoho_id": p.get("zoho_id"),
            "url": _url("project", p.name), "fases": fases, "tarefas_soltas": soltas,
            "horas_estimadas": sum(flt(t.expected_time) for t in ts if not t.is_group),
            "horas_registadas": sum(reais.values())}


def _nova_tarefa(projeto: str, nome: str, mae: str = None, grupo: int = 0, horas=None, inicio=None, fim=None,
                 chave=None, ordem=None, descricao=None) -> str:
    t = frappe.get_doc({"doctype": "Task", "subject": (nome or "Tarefa")[:140], "project": projeto, "parent_task": mae,
                        "is_group": cint(grupo), "expected_time": flt(horas) if horas else 0,
                        "exp_start_date": inicio or None, "exp_end_date": fim or inicio or None,
                        "chave_portal": chave, "ordem": ordem, "description": descricao})
    t.flags.ignore_permissions = True
    t.insert()
    return t.name


@frappe.whitelist()
def criar_projeto(spec):
    """Materializa no Orbit um projecto que o portal já planeou (blueprint, nível, datas — tudo do portal).

    spec = {nome, descricao, id_conta, dominio, marca, subscricao, blueprint, horas_orcamento,
            fases: [{nome, inicio, fim, tarefas: [{nome, horas, inicio, fim, chave, subtarefas: [nome|{nome,...}]}]}]}
    Idempotente pela subscrição+blueprint: pedir duas vezes devolve o mesmo projecto."""
    _so_portal()
    s = _dados(spec) or {}
    if not s.get("nome"):
        frappe.throw("Falta o nome do projecto.")
    if s.get("subscricao") and s.get("blueprint"):
        ja = frappe.db.get_value("Project", {"subscricao_portal": str(s["subscricao"]), "blueprint": s["blueprint"]})
        if ja:
            return {"ok": True, "projeto_id": ja, "projeto_nome": frappe.db.get_value("Project", ja, "project_name"),
                    "projeto_url": _url("project", ja), "repetido": True}
    nome = s["nome"][:140]
    if frappe.db.exists("Project", {"project_name": nome}):
        nome = f"{nome[:120]} ({frappe.utils.nowdate()})"
        k = 2
        while frappe.db.exists("Project", {"project_name": nome}):
            nome = f"{s['nome'][:120]} ({frappe.utils.nowdate()} #{k})"; k += 1
    id_conta = _limpo(s.get("id_conta"))
    cust = frappe.db.get_value("Customer", {"crm_account_id": id_conta}) if id_conta else None
    marca = s.get("marca") if s.get("marca") and frappe.db.exists("Brand", s.get("marca")) else None
    p = frappe.get_doc({"doctype": "Project", "project_name": nome, "company": frappe.get_all("Company", pluck="name")[0],
                        "status": "Open", "customer": cust, "crm_account_id": id_conta, "dominio": _limpo(s.get("dominio")),
                        "marca": marca, "subscricao_portal": _limpo(str(s.get("subscricao") or "")),
                        "blueprint": _limpo(s.get("blueprint")), "horas_orcamento": flt(s.get("horas_orcamento")),
                        "notes": frappe.utils.escape_html(s.get("descricao") or "").replace("\n", "<br>")})
    p.flags.ignore_permissions = True
    p.insert()
    detalhe = []
    for i, f in enumerate(s.get("fases") or []):
        g = _nova_tarefa(p.name, f.get("nome"), grupo=1, inicio=f.get("inicio"), fim=f.get("fim"), ordem=i + 1,
                         chave=f.get("chave"))
        criadas = sub = 0
        for j, t in enumerate(f.get("tarefas") or []):
            t = t if isinstance(t, dict) else {"nome": t}
            subs = t.get("subtarefas") or []
            tn = _nova_tarefa(p.name, t.get("nome"), mae=g, grupo=1 if subs else 0, horas=t.get("horas"),
                              inicio=t.get("inicio"), fim=t.get("fim"), chave=t.get("chave"), ordem=j + 1,
                              descricao=t.get("descricao"))
            criadas += 1
            for k, st in enumerate(subs):
                st = st if isinstance(st, dict) else {"nome": st}
                _nova_tarefa(p.name, st.get("nome"), mae=tn, horas=st.get("horas"), inicio=t.get("inicio"),
                             fim=t.get("fim"), chave=st.get("chave"), ordem=k + 1)
                sub += 1
        detalhe.append({"fase": f.get("nome"), "tarefas_criadas": criadas, "tarefas_total": len(f.get("tarefas") or []),
                        "subtarefas_criadas": sub})
        frappe.db.commit()
    frappe.db.commit()
    return {"ok": True, "projeto_id": p.name, "projeto_nome": nome, "projeto_url": _url("project", p.name),
            "fases_criadas": len(detalhe), "detalhe": detalhe}


@frappe.whitelist()
def garantir_lista(id_projeto: str, nome: str, tarefas=None):
    """A lista de um período («Outubro 2026»): tarefa-grupo + as tarefas que faltarem. Idempotente."""
    _so_portal()
    n = _projeto_por_id(id_projeto)
    if not n:
        return None
    g = frappe.db.get_value("Task", {"project": n, "is_group": 1, "subject": nome})
    if not g:
        ordem = cint(frappe.db.sql("select max(ordem) from tabTask where project=%s and ifnull(parent_task,'')=''", n)[0][0]) + 1
        g = _nova_tarefa(n, nome, grupo=1, ordem=ordem, inicio=frappe.utils.nowdate())
    ja = set(frappe.get_all("Task", filters={"parent_task": g}, pluck="subject"))
    criadas = 0
    for j, t in enumerate(_dados(tarefas) or []):
        t = t if isinstance(t, dict) else {"nome": t}
        if (t.get("nome") or "")[:140] in ja:
            continue
        _nova_tarefa(n, t.get("nome"), mae=g, horas=t.get("horas"), chave=t.get("chave"), ordem=j + 1,
                     descricao=t.get("descricao"))
        criadas += 1
    frappe.db.commit()
    return {"lista": g, "criadas": criadas}


@frappe.whitelist()
def fechar_tarefas(id_projeto: str, nomes=None, lista: str = None, chaves=None):
    """Fecha as tarefas abertas com estes nomes (ou chaves) no projecto — só dentro de `lista`, se dada."""
    _so_portal()
    n = _projeto_por_id(id_projeto)
    if not n:
        return {"fechadas": 0, "erro": "projecto inexistente"}
    nomes = [x[:140] for x in (_dados(nomes) or [])]
    chaves = _dados(chaves) or []
    f = {"project": n, "status": ["not in", ["Completed", "Cancelled"]], "is_group": 0}
    if lista:
        g = lista if frappe.db.exists("Task", lista) else frappe.db.get_value("Task", {"project": n, "is_group": 1, "subject": lista})
        if not g:
            return {"fechadas": 0}
        f["parent_task"] = g
    alvos = set()
    if nomes:
        alvos |= set(frappe.get_all("Task", filters={**f, "subject": ["in", nomes]}, pluck="name"))
    if chaves:
        alvos |= set(frappe.get_all("Task", filters={**f, "chave_portal": ["in", chaves]}, pluck="name"))
    for t in alvos:
        frappe.db.set_value("Task", t, {"status": "Completed", "progress": 100, "completed_on": frappe.utils.nowdate()})
    if alvos:
        try:
            frappe.get_doc("Project", n).update_percent_complete()
            frappe.db.set_value("Project", n, "percent_complete", frappe.get_doc("Project", n).percent_complete)
        except Exception:
            pass
    frappe.db.commit()
    return {"fechadas": len(alvos), "tarefas": sorted(alvos)}


@frappe.whitelist()
def tarefas(id_projeto: str, lista: str = None):
    _so_portal()
    n = _projeto_por_id(id_projeto)
    if not n:
        return []
    f = {"project": n}
    if lista:
        f["parent_task"] = lista
    ts = frappe.get_all("Task", filters=f, fields=["name", "subject", "status", "progress", "is_group", "parent_task",
                                                    "expected_time", "chave_portal", "zoho_id"], order_by="ordem asc, creation asc")
    reais = _horas_reais([t.name for t in ts])
    for t in ts:
        t["horas_registadas"] = reais.get(t.name, 0)
        t["url"] = _url("task", t.name)
    return ts


@frappe.whitelist()
def somar_orcamento(id_projeto: str, horas: float):
    """Fotografia da bolsa (o saldo verdadeiro é o do portal)."""
    _so_portal()
    n = _projeto_por_id(id_projeto)
    if not n:
        return None
    novo = flt(frappe.db.get_value("Project", n, "horas_orcamento")) + flt(horas)
    frappe.db.set_value("Project", n, "horas_orcamento", novo)
    frappe.db.commit()
    return {"projeto": n, "horas_orcamento": novo}


# ═══════════════════════════════════════════════════════════════════════════
# Webmail ↔ CRM (17-10-2026): o painel do Orbit CRM ao lado do email, à maneira do Zoho
# ═══════════════════════════════════════════════════════════════════════════
ESTADOS_FECHADOS = ("Won", "Lost")


def _url_crm(tipo: str, nome: str) -> str:
    from urllib.parse import quote
    return f"{frappe.utils.get_url()}/crm/{tipo}/{quote(nome)}"


@frappe.whitelist()
def perfil_remetente(email: str):
    """Quem é este endereço no CRM: contacto, organização, lead, negócios em curso, bilhetes abertos."""
    _so_portal()
    e = (email or "").strip().lower()
    if "@" not in e:
        return {"encontrado": False}
    out = {"email": e, "encontrado": False, "contacto": None, "organizacao": None, "lead": None,
           "negocios": [], "bilhetes": []}
    cn = (frappe.get_all("Contact Email", filters={"email_id": e, "parenttype": "Contact"}, pluck="parent", limit=1)
          or frappe.get_all("Contact", filters={"email_id": e}, pluck="name", limit=1))
    org = None
    if cn:
        c = frappe.get_doc("Contact", cn[0])
        org = _org_do_contacto(c)
        out["contacto"] = {"nome": c.full_name or c.name, "cargo": c.designation, "telefone": c.mobile_no or c.phone,
                           "url": _url_crm("contacts", c.name)}
    else:
        # sem contacto: a organização pelo domínio do email (se for de empresa e único)
        dom = e.split("@")[1]
        if dom not in ("gmail.com", "hotmail.com", "outlook.com", "sapo.pt", "icloud.com", "yahoo.com", "live.com", "outlook.pt"):
            orgs = frappe.get_all("CRM Organization", filters={"website": ["like", f"%{dom}%"]}, pluck="name", limit=2)
            org = orgs[0] if len(orgs) == 1 else None
    if org:
        o = frappe.db.get_value("CRM Organization", org, ["name", "organization_name", "crm_account_id", "estado_conta",
                                                          "tipo_conta", "marca", "owner"], as_dict=True)
        out["organizacao"] = {"nome": o.organization_name, "crm_account_id": o.crm_account_id, "estado": o.estado_conta,
                              "tipo": o.tipo_conta, "marca": o.marca, "url": _url_crm("organizations", o.name)}
        for d in frappe.get_all("CRM Deal", filters={"organization": org, "status": ["not in", ESTADOS_FECHADOS]},
                                fields=["name", "titulo", "status", "deal_value", "deal_owner"], order_by="modified desc", limit=5):
            out["negocios"].append({"id": d.name, "titulo": d.titulo or d.name, "estado": d.status, "valor": flt(d.deal_value),
                                    "dono": _nome_utilizador(d.deal_owner), "url": _url_crm("deals", d.name)})
        cust = frappe.db.get_value("HD Customer", {"crm_account_id": o.crm_account_id}) if o.crm_account_id else None
        fb = {"status": ["in", ["Open", "Replied"]]}
        filtros = [dict(fb, customer=cust)] if cust else []
        filtros.append(dict(fb, raised_by=e))
        vistos = set()
        for f in filtros:
            for t in frappe.get_all("HD Ticket", filters=f, fields=["name", "subject", "status", "agent_group"], limit=5):
                if t.name not in vistos:
                    vistos.add(t.name)
                    out["bilhetes"].append({"id": t.name, "assunto": t.subject, "estado": t.status, "equipa": t.agent_group,
                                            "url": f"{frappe.utils.get_url()}/helpdesk/tickets/{t.name}"})
    lead = frappe.get_all("CRM Lead", filters={"email": e, "converted": 0}, fields=["name", "lead_name", "status", "lead_owner"],
                          order_by="modified desc", limit=1) if frappe.get_meta("CRM Lead").has_field("converted") else \
        frappe.get_all("CRM Lead", filters={"email": e}, fields=["name", "lead_name", "status", "lead_owner"], order_by="modified desc", limit=1)
    if lead:
        l = lead[0]
        out["lead"] = {"id": l.name, "nome": l.lead_name, "estado": l.status, "dono": _nome_utilizador(l.lead_owner),
                       "url": _url_crm("leads", l.name)}
    out["encontrado"] = bool(out["contacto"] or out["organizacao"] or out["lead"])
    return out


@frappe.whitelist()
def associar_email(email: str, assunto: str = None, data: str = None, resumo: str = None, criar: str = None,
                   nome: str = None, por: str = None):
    """Guarda o email como nota no registo do remetente (negócio em curso › lead › contacto).
    `criar` = "lead" | "contacto" cria o registo quando ainda não existe."""
    _so_portal()
    p = perfil_remetente(email)
    alvo = None
    if p.get("negocios"):
        alvo = ("CRM Deal", p["negocios"][0]["id"])
    elif p.get("lead"):
        alvo = ("CRM Lead", p["lead"]["id"])
    if not alvo and criar == "lead":
        partes = (nome or email.split("@")[0]).strip().split(None, 1)
        r = criar_lead({"First_Name": partes[0], "Last_Name": partes[1] if len(partes) > 1 else None, "Email": email,
                        "Lead_Source": "Email"})
        alvo = ("CRM Lead", r["id"])
    elif not alvo and criar == "contacto":
        partes = (nome or email.split("@")[0]).strip().split(None, 1)
        r = criar_contacto({"First_Name": partes[0], "Last_Name": partes[1] if len(partes) > 1 else None, "Email": email})
        alvo = ("Contact", frappe.db.get_value("Contact", {"zoho_id": r["id"]}) or r.get("_orbit") or r["id"])
    if not alvo and p.get("contacto"):
        cn = frappe.get_all("Contact", filters={"email_id": email.strip().lower()}, pluck="name", limit=1)
        alvo = ("Contact", cn[0]) if cn else None
    if not alvo:
        return {"ok": False, "erro": "sem registo no CRM — crie primeiro a lead ou o contacto"}
    corpo = (f"<p><b>Email</b> de {frappe.utils.escape_html(email)}"
             + (f" — {frappe.utils.escape_html(data)}" if data else "") + "</p>"
             + (f"<p>{frappe.utils.escape_html(resumo)}</p>" if resumo else ""))
    frappe.get_doc({"doctype": "FCRM Note", "title": (f"Email: {assunto}" if assunto else "Email")[:140], "content": corpo,
                    "reference_doctype": alvo[0], "reference_docname": alvo[1]}).insert(ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True, "doctype": alvo[0], "nome": alvo[1]}


@frappe.whitelist()
def definir_dono(email: str, utilizador: str, assunto: str = None):
    """O responsável pelo email passa a dono do negócio em curso (ou da lead) do remetente."""
    _so_portal()
    if not frappe.db.get_value("User", utilizador, "enabled"):
        return {"ok": False, "erro": "utilizador desconhecido no Orbit"}
    p = perfil_remetente(email)
    if p.get("negocios"):
        dt, nome, campo = "CRM Deal", p["negocios"][0]["id"], "deal_owner"
    elif p.get("lead"):
        dt, nome, campo = "CRM Lead", p["lead"]["id"], "lead_owner"
    else:
        return {"ok": False, "erro": "o remetente não tem negócio em curso nem lead"}
    doc = frappe.get_doc(dt, nome)
    doc.set(campo, utilizador)
    doc.flags.ignore_permissions = True
    doc.save()
    frappe.get_doc({"doctype": "FCRM Note", "title": "Responsável definido a partir do email",
                    "content": f"<p>{frappe.utils.escape_html(_nome_utilizador(utilizador) or utilizador)} passou a responsável"
                               + (f" — a partir do email «{frappe.utils.escape_html(assunto)}»" if assunto else "") + ".</p>",
                    "reference_doctype": dt, "reference_docname": nome}).insert(ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True, "doctype": dt, "nome": nome}


# ── língua das pessoas (18-10-2026, docs/PLANO-I18N-ORBIT-APPS.md) ───────────
# O portal é a fonte (idioma_pessoa; colaboradores da casa = pt). Chama `definir_lingua` quando a língua de
# alguém muda, e `acertar_linguas` todas as noites com a lista completa do tenant.

@frappe.whitelist(methods=["POST"])
def definir_lingua(email: str, lingua: str):
    _so_portal()
    from orbit.lingua import definir
    r = definir(email, lingua)
    frappe.db.commit()
    return {"email": email, "resultado": r}


@frappe.whitelist(methods=["POST"])
def acertar_linguas(pessoas):
    """`pessoas` = {email: lingua}. Só mexe em quem existe e está diferente; devolve as contagens."""
    _so_portal()
    from orbit.lingua import definir
    contas = {}
    for email, lingua in (_dados(pessoas) or {}).items():
        r = definir(email, lingua)
        contas[r] = contas.get(r, 0) + 1
    frappe.db.commit()
    return contas
