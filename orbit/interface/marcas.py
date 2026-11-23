"""Marcas nos registos do CRM (23-11-2026, pedido do Vítor).

Cada negócio de um Orbit pode ter várias marcas (Stratechna: Stratechna, Webgate, MBontime; JF: Arnox, JFusados,
Shopinox — a lista é a do doctype Brand). Onde fica:

* Leads, Negócios, Empresas: um campo «Marca» (Link → Brand), um só valor;
* Contactos: «Marcas» (Table MultiSelect → «Marca do Contacto»): a mesma pessoa pode ser cliente de duas marcas.

Preenche-se sozinho, sem nunca apagar nem trocar o que alguém escolheu:

* pelo endereço da casa no email (o cliente escreveu para info@webgate.pt → Webgate; nós escrevemos de @mbontime.pt →
  MBontime) — o mapa domínio → marca é o do Desk (`orbit_desk_dominios`); um domínio cujo nome é o de uma marca
  (stratechna.pt → Stratechna) também conta;
* o negócio herda da lead de onde veio (ou da empresa); ao gravar o negócio, a marca passa à empresa (se não tiver) e
  aos contactos do negócio — é assim que as compras das lojas (o escritor põe a marca no negócio) chegam à pessoa.

`preencher()` faz o mesmo ao que já existe (uma vez, pelo instalador ou à mão).
"""
from __future__ import annotations

import re
import unicodedata

import frappe

FILHO = "Marca do Contacto"
CAMPOS_UM = ("CRM Lead", "CRM Deal", "CRM Organization")


def _sem_acentos(t: str) -> str:
    return unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()


def instalar():
    """after_migrate: o campo «Marca» nos três registos e «Marcas» no contacto."""
    from frappe.custom.doctype.custom_field.custom_field import create_custom_field
    if not frappe.db.exists("DocType", "Brand"):
        return
    depois = {"CRM Lead": "organization", "CRM Deal": "organization", "CRM Organization": "organization_name"}
    for dt in CAMPOS_UM:
        if frappe.db.exists("DocType", dt) and not frappe.get_meta(dt).has_field("marca"):
            create_custom_field(dt, {"fieldname": "marca", "label": "Marca", "fieldtype": "Link", "options": "Brand",
                                     "insert_after": depois[dt], "in_standard_filter": 1})
    if frappe.db.exists("DocType", FILHO) and not frappe.get_meta("Contact").has_field("marcas"):
        create_custom_field("Contact", {"fieldname": "marcas", "label": "Marcas", "fieldtype": "Table MultiSelect",
                                        "options": FILHO, "insert_after": "company_name"})


def lista() -> list:
    if not frappe.db.exists("DocType", "Brand"):
        return []
    return frappe.get_all("Brand", pluck="name", order_by="name asc", limit=50)


def de_dominio(dominio: str) -> str | None:
    dominio = (dominio or "").strip().lower().strip(" <>")
    if not dominio:
        return None
    mapa = {k.lower(): v for k, v in (frappe.conf.get("orbit_desk_dominios") or {}).items()}
    if dominio in mapa and frappe.db.exists("Brand", mapa[dominio]):
        return mapa[dominio]
    raiz = _sem_acentos(dominio.split(".")[0])
    for m in lista():
        if re.sub(r"[^a-z0-9]", "", _sem_acentos(m)) == re.sub(r"[^a-z0-9]", "", raiz):
            return m
    return None


def _enderecos(texto: str) -> list:
    return [e.lower() for e in re.findall(r"[\w.+'-]+@[\w-]+(?:\.[\w-]+)+", texto or "")]


def marcas_do_contacto(contacto: str) -> list:
    return frappe.get_all(FILHO, filters={"parenttype": "Contact", "parent": contacto, "parentfield": "marcas"},
                          pluck="marca", order_by="idx asc")


def juntar_ao_contacto(contacto: str, marca: str) -> bool:
    """Acrescenta a marca ao contacto (sem gravar o contacto inteiro — não corre os ganchos dele)."""
    if not (contacto and marca and frappe.db.exists("Contact", contacto) and frappe.db.exists("Brand", marca)):
        return False
    if not frappe.get_meta("Contact").has_field("marcas"):
        return False
    atuais = marcas_do_contacto(contacto)
    if marca in atuais:
        return False
    frappe.get_doc({"doctype": FILHO, "parent": contacto, "parenttype": "Contact", "parentfield": "marcas",
                    "marca": marca, "idx": len(atuais) + 1}).db_insert()
    return True


def definir_no_contacto(contacto: str, marcas: list) -> list:
    frappe.get_doc("Contact", contacto).check_permission("write")
    validas = [m for m in dict.fromkeys(marcas or []) if frappe.db.exists("Brand", m)]
    frappe.db.delete(FILHO, {"parenttype": "Contact", "parent": contacto, "parentfield": "marcas"})
    for i, m in enumerate(validas, 1):
        frappe.get_doc({"doctype": FILHO, "parent": contacto, "parenttype": "Contact", "parentfield": "marcas",
                        "marca": m, "idx": i}).db_insert()
    frappe.db.set_value("Contact", contacto, "modified", frappe.utils.now(), update_modified=False)
    return validas


def _por_um(dt: str, nome: str, marca: str) -> bool:
    if dt not in CAMPOS_UM or not nome or not frappe.get_meta(dt).has_field("marca"):
        return False
    if frappe.db.get_value(dt, nome, "marca"):
        return False
    frappe.db.set_value(dt, nome, "marca", marca, update_modified=False)
    return True


def _aplicar(dt: str, nome: str, marca: str):
    if dt == "Contact":
        juntar_ao_contacto(nome, marca)
    else:
        _por_um(dt, nome, marca)


# ── Ganchos ─────────────────────────────────────────────────────────────────────────────────────────────
def de_email(doc, method=None):
    """Communication.after_insert: a marca pelo endereço da casa (para onde o cliente escreveu, ou de onde saímos)."""
    try:
        if doc.communication_medium != "Email":
            return
        casa = _enderecos(",".join(filter(None, [doc.recipients, doc.cc]))) if doc.sent_or_received == "Received" \
            else _enderecos(doc.sender or "")
        marca = None
        for e in casa:
            marca = de_dominio(e.split("@")[-1])
            if marca:
                break
        if not marca:
            return
        alvos = set()
        if doc.reference_doctype in CAMPOS_UM + ("Contact",) and doc.reference_name:
            alvos.add((doc.reference_doctype, doc.reference_name))
        for l in doc.get("timeline_links") or []:
            if l.link_doctype in CAMPOS_UM + ("Contact",):
                alvos.add((l.link_doctype, l.link_name))
        for dt, nome in alvos:
            _aplicar(dt, nome, marca)
    except Exception:
        frappe.log_error(title="Orbit: marca pelo email")


def negocio_antes(doc, method=None):
    """CRM Deal.before_insert: sem marca, herda da lead de onde veio, ou da empresa."""
    if not doc.meta.has_field("marca") or doc.get("marca"):
        return
    m = None
    if doc.get("lead") and frappe.get_meta("CRM Lead").has_field("marca"):
        m = frappe.db.get_value("CRM Lead", doc.lead, "marca")
    if not m and doc.get("organization") and frappe.get_meta("CRM Organization").has_field("marca"):
        m = frappe.db.get_value("CRM Organization", doc.organization, "marca")
    if m:
        doc.marca = m


def negocio_gravado(doc, method=None):
    """CRM Deal.after_insert/on_update: a marca do negócio passa à empresa (se não tiver) e aos contactos dele."""
    try:
        m = doc.get("marca")
        if not m:
            return
        if doc.get("organization"):
            _por_um("CRM Organization", doc.organization, m)
        for c in doc.get("contacts") or []:
            juntar_ao_contacto(c.contact, m)
    except Exception:
        frappe.log_error(title="Orbit: marca do negócio")


# ── O que já existe ─────────────────────────────────────────────────────────────────────────────────────
@frappe.whitelist()
def preencher(simular: int = 1):
    """Aplica as mesmas regras aos registos que já existem. Só preenche vazios; nunca troca nem apaga."""
    frappe.only_for("System Manager")
    simular = int(simular or 0)
    conta = {"negocios_da_lead": 0, "empresas_do_negocio": 0, "contactos_do_negocio": 0, "pelo_email": 0}
    if not lista():
        return conta

    def faz(fn, *a):
        if simular:
            return True
        return fn(*a)

    # 1. negócio sem marca ← lead
    for d in frappe.get_all("CRM Deal", filters={"marca": ["is", "not set"], "lead": ["is", "set"]}, fields=["name", "lead"]):
        m = frappe.db.get_value("CRM Lead", d.lead, "marca")
        if m:
            conta["negocios_da_lead"] += 1
            faz(_por_um, "CRM Deal", d.name, m)
    # 2. pelo email (o mais recente primeiro: decide a marca da última conversa)
    vistos = set()
    comms = frappe.db.sql("""SELECT name, sent_or_received, recipients, cc, sender, reference_doctype, reference_name
                             FROM `tabCommunication` WHERE communication_medium='Email' AND communication_type='Communication'
                             ORDER BY creation DESC LIMIT 20000""", as_dict=True)
    links = {}
    for l in frappe.db.sql("""SELECT parent, link_doctype, link_name FROM `tabCommunication Link`
                              WHERE link_doctype IN ('CRM Lead','CRM Deal','CRM Organization','Contact')""", as_dict=True):
        links.setdefault(l.parent, []).append((l.link_doctype, l.link_name))
    for c in comms:
        casa = _enderecos(",".join(filter(None, [c.recipients, c.cc]))) if c.sent_or_received == "Received" else _enderecos(c.sender or "")
        marca = next((x for x in (de_dominio(e.split("@")[-1]) for e in casa) if x), None)
        if not marca:
            continue
        alvos = set(links.get(c.name, []))
        if c.reference_doctype in CAMPOS_UM + ("Contact",) and c.reference_name:
            alvos.add((c.reference_doctype, c.reference_name))
        for dt, nome in alvos:
            if (dt, nome) in vistos or not frappe.db.exists(dt, nome):
                continue
            if dt == "Contact":
                if marca in marcas_do_contacto(nome):
                    continue
            elif frappe.db.get_value(dt, nome, "marca"):
                vistos.add((dt, nome))
                continue
            vistos.add((dt, nome))
            conta["pelo_email"] += 1
            faz(_aplicar, dt, nome, marca)
    # 3. negócio com marca → empresa e contactos
    for d in frappe.get_all("CRM Deal", filters={"marca": ["is", "set"]}, fields=["name", "marca", "organization"]):
        if d.organization and not frappe.db.get_value("CRM Organization", d.organization, "marca"):
            conta["empresas_do_negocio"] += 1
            faz(_por_um, "CRM Organization", d.organization, d.marca)
        for ct in frappe.get_all("CRM Contacts", filters={"parent": d.name, "parenttype": "CRM Deal"}, pluck="contact"):
            if ct and d.marca not in marcas_do_contacto(ct):
                conta["contactos_do_negocio"] += 1
                faz(juntar_ao_contacto, ct, d.marca)
    if not simular:
        frappe.db.commit()
    return conta
