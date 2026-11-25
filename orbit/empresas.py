"""Várias empresas no mesmo Orbit (25-11-2026, docs/PLANO-ORBIT-VARIAS-EMPRESAS.md, D1–D7 aceites).

A marca é o que o cliente vê; a empresa é quem fatura. Cada marca pertence a uma empresa (`Brand.orbit_empresa`);
sem empresa indicada, a marca é da empresa principal do tenant (a por omissão, ou a primeira). Tudo o que escolhe a
marca escolhe também a empresa por ela: orçamentos, faturas (séries do programa certificado por marca), encomendas
(pelo canal), faturas de compra (pelo NIF do adquirente).
"""
import re

import frappe

CAMPOS = {
    "Brand": [
        {"fieldname": "orbit_empresa", "fieldtype": "Link", "options": "Company", "label": "Empresa",
         "insert_after": "brand", "in_list_view": 1, "in_standard_filter": 1,
         "description": "A empresa que fatura esta marca. Vazio = a empresa principal."},
    ],
    "Sales Invoice": [
        {"fieldname": "orbit_marca", "fieldtype": "Link", "options": "Brand", "label": "Marca",
         "insert_after": "company", "in_standard_filter": 1,
         "description": "Escolhe a série no programa certificado. Vazio = a marca dos artigos."},
    ],
    "Sales Order": [
        {"fieldname": "orbit_marca", "fieldtype": "Link", "options": "Brand", "label": "Marca",
         "insert_after": "company", "in_standard_filter": 1},
    ],
}


def garantir():
    if not frappe.db.exists("DocType", "Company"):
        return
    try:
        from frappe.custom.doctype.custom_field.custom_field import create_custom_field
        for dt, campos in CAMPOS.items():
            if not frappe.db.exists("DocType", dt):
                continue
            for c in campos:
                if not frappe.db.exists("Custom Field", {"dt": dt, "fieldname": c["fieldname"]}):
                    create_custom_field(dt, {**c, "module": "Orbit"})
        frappe.db.commit()
    except Exception:
        frappe.log_error(title="orbit.empresas.garantir")


def principal() -> str | None:
    return frappe.defaults.get_global_default("company") or (frappe.get_all("Company", pluck="name", order_by="creation asc", limit=1) or [None])[0]


def da_marca(marca: str | None) -> str | None:
    if marca and frappe.get_meta("Brand").has_field("orbit_empresa"):
        e = frappe.db.get_value("Brand", marca, "orbit_empresa")
        if e:
            return e
    return principal()


def marcas_de(empresa: str) -> list[str]:
    """As marcas que a empresa fatura (as sem empresa são da principal)."""
    todas = frappe.get_all("Brand", fields=["name", "orbit_empresa"]) if frappe.get_meta("Brand").has_field("orbit_empresa") \
        else frappe.get_all("Brand", fields=["name"])
    p = principal()
    return [b.name for b in todas if (b.get("orbit_empresa") or p) == empresa]


def _digitos(nif: str) -> str:
    return re.sub(r"\D", "", nif or "")


def por_nif(nif: str) -> str | None:
    """A empresa do tenant com este NIF (com ou sem prefixo de país)."""
    n = _digitos(nif)
    if not n:
        return None
    for c in frappe.get_all("Company", fields=["name", "tax_id"]):
        if _digitos(c.tax_id) == n:
            return c.name
    return None


def marca_do_documento(doc) -> str | None:
    """A marca de uma venda: a do campo, a da encomenda/orçamento de origem, ou a mais frequente nos artigos."""
    if doc.get("orbit_marca"):
        return doc.orbit_marca
    for l in doc.get("items") or []:
        so = l.get("sales_order")
        if so:
            m = frappe.db.get_value("Sales Order", so, "orbit_marca") if frappe.get_meta("Sales Order").has_field("orbit_marca") else None
            if m:
                return m
        q = l.get("prevdoc_docname")
        if q and frappe.db.exists("Quotation", q):
            m = frappe.db.get_value("Quotation", q, "orbit_marca")
            if m:
                return m
    contagem = {}
    for l in doc.get("items") or []:
        b = l.get("brand") or frappe.db.get_value("Item", l.item_code, "brand")
        if b:
            contagem[b] = contagem.get(b, 0) + 1
    return max(contagem, key=contagem.get) if contagem else None


def antes_de_validar_venda(doc, method=None):
    """Sales Order / Sales Invoice: a marca fica escrita (escolhe a série do programa certificado)."""
    if doc.docstatus == 0 and frappe.get_meta(doc.doctype).has_field("orbit_marca") and not doc.get("orbit_marca"):
        m = marca_do_documento(doc)
        if m:
            doc.orbit_marca = m


# ── Definições › Empresas (interface /orbit) ─────────────────────────────────────────────────────────────────
def _so_admin():
    if "System Manager" not in frappe.get_roles() and frappe.session.user != "Administrator":
        frappe.throw("Só o administrador do Orbit pode gerir empresas.", frappe.PermissionError)


@frappe.whitelist()
def lista():
    _so_admin()
    p = principal()
    out = []
    for c in frappe.get_all("Company", fields=["name", "tax_id", "abbr", "country", "default_currency", "creation"],
                            order_by="creation asc"):
        out.append({**c, "principal": c.name == p, "marcas": marcas_de(c.name)})
    marcas = frappe.get_all("Brand", fields=["name"] + (["orbit_empresa"] if frappe.get_meta("Brand").has_field("orbit_empresa") else []),
                            order_by="name asc")
    return {"empresas": out, "marcas": marcas, "principal": p}


def nif_pt_valido(nif: str) -> bool:
    n = _digitos(nif)
    if len(n) != 9:
        return False
    soma = sum(int(n[i]) * (9 - i) for i in range(8))
    resto = soma % 11
    return int(n[8]) == (0 if resto < 2 else 11 - resto)


def _abreviatura(nome: str) -> str:
    palavras = [w for w in re.split(r"[\s\-–,.]+", nome) if w and w.lower() not in ("de", "da", "do", "e", "lda", "sa", "unipessoal")]
    base = "".join(w[0] for w in palavras).upper()[:5] or "EMP"
    abrev, n = base, 2
    while frappe.db.exists("Company", {"abbr": abrev}):
        abrev, n = f"{base}{n}", n + 1
    return abrev


@frappe.whitelist(methods=["POST"])
def criar(nome: str, nif: str, pais: str = "Portugal", moeda: str = "EUR", abreviatura: str = None,
          morada: str = None, codigo_postal: str = None, cidade: str = None, marcas: str = None):
    """Nova empresa: a Company do ERPNext com o plano de contas da principal (D3), armazéns, centro de custo e
    os modelos de IVA de venda e de compra (os do tenant, copiados para a empresa nova)."""
    _so_admin()
    import json
    nome = (nome or "").strip()
    if not nome:
        frappe.throw("Escreva o nome legal da empresa.")
    if frappe.db.exists("Company", nome):
        frappe.throw("Já existe uma empresa com esse nome.")
    if pais == "Portugal" and not nif_pt_valido(nif):
        frappe.throw("O NIF não é válido.")
    if por_nif(nif):
        frappe.throw(f"Já existe uma empresa com o NIF {nif}.")
    p = principal()
    plano = frappe.db.get_value("Company", p, "chart_of_accounts") if p else None
    c = frappe.get_doc({"doctype": "Company", "company_name": nome, "abbr": (abreviatura or "").strip().upper()[:10] or _abreviatura(nome),
                        "default_currency": moeda or "EUR", "country": pais or "Portugal", "tax_id": _digitos(nif) if pais == "Portugal" else nif,
                        "chart_of_accounts": plano or "Standard", "create_chart_of_accounts_based_on": "Standard Template"})
    c.flags.ignore_permissions = True
    c.insert()
    if morada:
        frappe.get_doc({"doctype": "Address", "address_title": nome, "address_type": "Billing", "address_line1": morada[:140],
                        "pincode": codigo_postal, "city": cidade or "-", "country": pais or "Portugal", "is_your_company_address": 1,
                        "links": [{"link_doctype": "Company", "link_name": c.name}]}).insert(ignore_permissions=True)
    _iva_para(c.name, p)
    for m in json.loads(marcas) if marcas else []:
        associar(m, c.name)
    frappe.db.commit()
    return {"ok": True, "empresa": c.name, "abbr": c.abbr}


def _iva_para(empresa: str, origem: str):
    """Copia os modelos de IVA (venda e compra) da empresa principal, com as contas equivalentes da nova."""
    if not origem:
        return
    ab_o = frappe.db.get_value("Company", origem, "abbr")
    ab_n = frappe.db.get_value("Company", empresa, "abbr")
    for dt in ("Sales Taxes and Charges Template", "Purchase Taxes and Charges Template"):
        for nome in frappe.get_all(dt, filters={"company": origem}, pluck="name"):
            t = frappe.get_doc(dt, nome)
            titulo = t.title
            if frappe.db.exists(dt, {"title": titulo, "company": empresa}):
                continue
            novo = frappe.copy_doc(t)
            novo.company = empresa
            ok = True
            for linha in novo.get("taxes") or []:
                conta = (linha.account_head or "").replace(f" - {ab_o}", f" - {ab_n}")
                if not frappe.db.exists("Account", conta):
                    nome_conta = frappe.db.get_value("Account", linha.account_head, "account_name")
                    conta = frappe.db.get_value("Account", {"company": empresa, "account_name": nome_conta}, "name")
                if not conta:
                    ok = False
                    break
                linha.account_head = conta
                cc = frappe.db.get_value("Company", empresa, "cost_center")
                if linha.get("cost_center") and cc:
                    linha.cost_center = cc
            if ok:
                novo.flags.ignore_permissions = True
                try:
                    novo.insert()
                except Exception:
                    frappe.log_error(title=f"orbit.empresas: IVA {titulo} → {empresa}")


@frappe.whitelist(methods=["POST"])
def associar(marca: str, empresa: str):
    """A marca passa a ser faturada pela empresa: campo da marca, armazém por omissão da marca na empresa
    (Brand.brand_defaults, que o ERPNext usa nas encomendas e faturas)."""
    _so_admin()
    if not frappe.db.exists("Brand", marca) or not frappe.db.exists("Company", empresa):
        frappe.throw("Marca ou empresa desconhecida.")
    b = frappe.get_doc("Brand", marca)
    b.orbit_empresa = None if empresa == principal() else empresa
    abrev = frappe.db.get_value("Company", empresa, "abbr")
    # armazém da marca: o que já existe noutra empresa passa a ter um igual na empresa nova
    antigo = next((d.default_warehouse for d in b.get("brand_defaults") or [] if d.default_warehouse), None)
    novo_arm = None
    if antigo and frappe.db.get_value("Warehouse", antigo, "company") != empresa:
        base = frappe.db.get_value("Warehouse", antigo, "warehouse_name")
        novo_arm = frappe.db.get_value("Warehouse", {"warehouse_name": base, "company": empresa}, "name")
        if not novo_arm:
            pai = frappe.db.get_value("Warehouse", {"is_group": 1, "company": empresa, "parent_warehouse": ["in", ["", None]]}, "name")
            w = frappe.get_doc({"doctype": "Warehouse", "warehouse_name": base, "company": empresa, "parent_warehouse": pai})
            w.insert(ignore_permissions=True)
            novo_arm = w.name
    elif antigo:
        novo_arm = antigo
    linhas = [d for d in b.get("brand_defaults") or [] if d.company != empresa]
    b.set("brand_defaults", [])
    for d in linhas:
        b.append("brand_defaults", {k: d.get(k) for k in ("company", "default_warehouse", "default_price_list",
                                                           "selling_cost_center", "income_account", "expense_account",
                                                           "buying_cost_center", "default_supplier", "default_discount_account")})
    if novo_arm:
        b.append("brand_defaults", {"company": empresa, "default_warehouse": novo_arm})
    b.flags.ignore_permissions = True
    b.save()
    # o armazém antigo sem stock nenhum, noutra empresa, desactiva-se (fica no histórico)
    if antigo and novo_arm and antigo != novo_arm and not frappe.db.sql(
            "select 1 from `tabStock Ledger Entry` where warehouse=%s limit 1", antigo):
        frappe.db.set_value("Warehouse", antigo, "disabled", 1)
    frappe.db.commit()
    return {"ok": True, "marca": marca, "empresa": empresa, "armazem": novo_arm}
