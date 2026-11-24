"""Faturas de compra do Docs no ERP — F0: o que o ERP precisa antes de receber a 1.ª fatura (24-11-2026).

docs/PLANO-DOCS-FATURA-COMPRA-ERP.md (D1–D12 aceites a 24-11). Para cada empresa do tenant, sem mexer no que existe:

- **IVA de compra (D8):** contas «IVA dedutível 23 % / 13 % / 6 %» e «IVA autoliquidado — dedutível / a entregar»
  em «Duties and Taxes»; modelos de compra «IVA Portugal (compras)», «Isento de IVA (compras)» e «Autoliquidação
  intracomunitária (compras)»; modelos de artigo «IVA compras 23 % / 13 % / 6 % / isento», um por linha da fatura —
  a taxa lida em cada linha escolhe o modelo do artigo e o modelo da fatura sai do país/regime do fornecedor.
- **Gastos por Área do Docs (D5):** contas de gasto com os nomes das etiquetas das Áreas 03–14 (Eletricidade,
  Combustível e carregamento, …) e o mapa etiqueta → conta (`CONTA_DA_ETIQUETA`) que a fatura em rascunho usa nas
  linhas que não são mercadoria; um só artigo de serviço «GASTO-DOCS» (sem stock) leva essas linhas.
- **Referência do fornecedor ↔ artigo (`Item Supplier`):** a partir das «Oferta do Fornecedor» do espelho do
  importador; o espelho mantém-nas a cada volta (`ligar_oferta`).

Os lançamentos do ERP são de gestão (D10): a contabilidade oficial continua com o contabilista.
Repetível; corre em `after_migrate` e à mão: bench --site <site> execute orbit.compras.preparar.tudo
"""
import frappe

# Área / etiqueta do Docs → (grupo, conta de gasto). Grupos dentro de «Indirect Expenses» salvo indicação.
GRUPOS = {
    "Instalações e despesas gerais": "Indirect Expenses",
    "Viaturas": "Indirect Expenses",
    "Pessoal (outros gastos)": "Indirect Expenses",
    "Financeiros e seguros": "Indirect Expenses",
    "Jurídico, fiscal e societário": "Indirect Expenses",
    "Obras, assistência e transportes": "Direct Expenses",
}
CONTAS = {
    # 03 Despesas gerais
    "Renda e condomínio": "Instalações e despesas gerais",
    "Eletricidade": "Instalações e despesas gerais",
    "Água": "Instalações e despesas gerais",
    "Gás": "Instalações e despesas gerais",
    "Telecomunicações e internet": "Instalações e despesas gerais",
    "Software e licenças": "Instalações e despesas gerais",
    "Serviços profissionais": "Instalações e despesas gerais",
    "Seguros gerais": "Instalações e despesas gerais",
    "Limpeza e manutenção das instalações": "Instalações e despesas gerais",
    "Material de escritório": "Instalações e despesas gerais",
    "Marketing próprio": "Instalações e despesas gerais",
    "Formação e cursos": "Instalações e despesas gerais",
    "Deslocações e alojamento": "Instalações e despesas gerais",
    "Refeições e representação": "Instalações e despesas gerais",
    "Quotizações e assinaturas": "Instalações e despesas gerais",
    "Outras despesas": "Instalações e despesas gerais",
    # 04 Viaturas
    "Viaturas — aquisição, leasing e renting": "Viaturas",
    "Combustível e carregamento": "Viaturas",
    "Portagens e estacionamento": "Viaturas",
    "Viaturas — manutenção e pneus": "Viaturas",
    "Viaturas — seguros": "Viaturas",
    "Viaturas — IUC e inspeções": "Viaturas",
    "Viaturas — multas e sinistros": "Viaturas",
    # 05 / 06
    "Notas de despesa e ajudas de custo": "Pessoal (outros gastos)",
    "Medicina e segurança no trabalho": "Pessoal (outros gastos)",
    "Formação do pessoal": "Pessoal (outros gastos)",
    "Seguro de acidentes de trabalho": "Pessoal (outros gastos)",
    "Recrutamento": "Pessoal (outros gastos)",
    # 07 / 08 / 09
    "Taxas e licenças": "Jurídico, fiscal e societário",
    "Serviços jurídicos e societários": "Jurídico, fiscal e societário",
    "Comissões bancárias e meios de pagamento": "Financeiros e seguros",
    "Outros seguros": "Financeiros e seguros",
    # 10–14
    "Manutenção de equipamentos": "Obras, assistência e transportes",
    "Subcontratos de obras": "Obras, assistência e transportes",
    "Subcontratos de assistência técnica": "Obras, assistência e transportes",
    "Recondicionamento de usados": "Obras, assistência e transportes",
    "Transportes de vendas": "Obras, assistência e transportes",
    "Portes de compras": "Obras, assistência e transportes",
}
# etiqueta do Docs (filha ou Área) → conta; a etiqueta mais específica do documento ganha
CONTA_DA_ETIQUETA = {c: c for c in CONTAS if c in (
    "Renda e condomínio", "Eletricidade", "Água", "Gás", "Telecomunicações e internet", "Software e licenças",
    "Serviços profissionais", "Seguros gerais", "Limpeza e manutenção das instalações", "Material de escritório",
    "Marketing próprio", "Formação e cursos", "Deslocações e alojamento", "Refeições e representação",
    "Quotizações e assinaturas", "Outras despesas", "Combustível e carregamento", "Portagens e estacionamento",
    "Medicina e segurança no trabalho", "Formação do pessoal", "Seguro de acidentes de trabalho", "Recrutamento")}
CONTA_DA_ETIQUETA.update({
    "03 Despesas gerais": "Outras despesas",
    "Aquisição, leasing e renting": "Viaturas — aquisição, leasing e renting",
    "Manutenção e pneus": "Viaturas — manutenção e pneus",
    "Seguro da viatura": "Viaturas — seguros",
    "IUC": "Viaturas — IUC e inspeções",
    "Inspeção periódica": "Viaturas — IUC e inspeções",
    "Multas e sinistros": "Viaturas — multas e sinistros",
    "04 Viaturas": "Viaturas — manutenção e pneus",
    "05 Notas de despesa": "Notas de despesa e ajudas de custo",
    "Notas de despesa (colaboradores)": "Notas de despesa e ajudas de custo",
    "Ajudas de custo e quilómetros": "Notas de despesa e ajudas de custo",
    "Taxas e licenças municipais": "Taxas e licenças",
    "09 Societário e Jurídico": "Serviços jurídicos e societários",
    "Terminais e meios de pagamento": "Comissões bancárias e meios de pagamento",
    "Apólices (outras)": "Outros seguros",
    "Manutenções de equipamentos": "Manutenção de equipamentos",
    "11 Obras e Instalações": "Subcontratos de obras",
    "12 Assistência Técnica": "Subcontratos de assistência técnica",
    "Recondicionamento": "Recondicionamento de usados",
    "Cotações e contratação de transporte": "Transportes de vendas",
    "Guias e transporte": "Portes de compras",
})

IVA = [  # (conta, taxa)
    ("IVA dedutível 23 %", 23), ("IVA dedutível 13 %", 13), ("IVA dedutível 6 %", 6),
    ("IVA autoliquidado — dedutível", 23), ("IVA autoliquidado — a entregar", 23),
]
ARTIGO_GASTO = "GASTO-DOCS"


def _abbr(company):
    return frappe.db.get_value("Company", company, "abbr")


def _conta(company, nome, pai, **campos):
    abbr = _abbr(company)
    full = f"{nome} - {abbr}"
    if frappe.db.exists("Account", full):
        return full
    pai_full = pai if pai.endswith(f" - {abbr}") else f"{pai} - {abbr}"
    if not frappe.db.exists("Account", pai_full):
        return None
    frappe.get_doc({"doctype": "Account", "account_name": nome, "parent_account": pai_full, "company": company,
                    **campos}).insert(ignore_permissions=True)
    return full


def _pai_impostos(company):
    abbr = _abbr(company)
    for n in (f"Duties and Taxes - {abbr}", f"Impostos e Taxas - {abbr}"):
        if frappe.db.exists("Account", n):
            return n
    return frappe.db.get_value("Account", {"company": company, "is_group": 1, "account_type": "Tax"}, "name")


def _pai_gasto(company, nome):
    abbr = _abbr(company)
    if frappe.db.exists("Account", f"{nome} - {abbr}"):
        return f"{nome} - {abbr}"
    return frappe.db.get_value("Account", {"company": company, "is_group": 1, "root_type": "Expense",
                                           "parent_account": ("is", "set")}, "name") \
        or frappe.db.get_value("Account", {"company": company, "is_group": 1, "root_type": "Expense"}, "name")


def contas_iva(company) -> dict:
    pai = _pai_impostos(company)
    if not pai:
        return {}
    return {n: _conta(company, n, pai, account_type="Tax", tax_rate=t, is_group=0) for n, t in IVA}


def modelos_iva(company, contas: dict) -> None:
    abbr = _abbr(company)
    c23, c13, c6, ad, ap = (contas.get(n) for n, _ in IVA)
    modelos = {
        "IVA Portugal (compras)": [(c23, 23, "Add"), (c13, 0, "Add"), (c6, 0, "Add")],
        "Isento de IVA (compras)": [],
        "Autoliquidação intracomunitária (compras)": [(ad, 23, "Add"), (ap, 23, "Deduct")],
    }
    for titulo, linhas in modelos.items():
        if frappe.db.exists("Purchase Taxes and Charges Template", f"{titulo} - {abbr}"):
            continue
        frappe.get_doc({"doctype": "Purchase Taxes and Charges Template", "title": titulo, "company": company,
                        "taxes": [{"charge_type": "On Net Total", "account_head": a, "rate": r, "add_deduct_tax": s,
                                   "category": "Total", "description": a.rsplit(" - ", 1)[0]}
                                  for a, r, s in linhas if a]}).insert(ignore_permissions=True)
    # modelo de artigo por taxa: diz a taxa de cada conta para essa linha (vale para o modelo nacional e o da
    # autoliquidação; isento põe tudo a zero)
    for taxa in (23, 13, 6, 0):
        titulo = f"IVA compras {taxa} %" if taxa else "IVA compras isento"
        if frappe.db.exists("Item Tax Template", f"{titulo} - {abbr}"):
            continue
        linhas = [(c23, 23 if taxa == 23 else 0), (c13, 13 if taxa == 13 else 0), (c6, 6 if taxa == 6 else 0),
                  (ad, taxa), (ap, taxa)]
        frappe.get_doc({"doctype": "Item Tax Template", "title": titulo, "company": company,
                        "taxes": [{"tax_type": a, "tax_rate": r} for a, r in linhas if a]}).insert(ignore_permissions=True)


def contas_gasto(company) -> dict:
    grupos = {}
    for g, pai in GRUPOS.items():
        p = _pai_gasto(company, pai)
        grupos[g] = _conta(company, g, p, is_group=1, root_type="Expense") if p else None
    out = {}
    for nome, g in CONTAS.items():
        if grupos.get(g):
            out[nome] = _conta(company, nome, grupos[g], is_group=0, root_type="Expense",
                               account_type="Expense Account")
    return out


def artigo_gasto() -> None:
    if frappe.db.exists("Item", ARTIGO_GASTO):
        return
    grupo = "Services" if frappe.db.exists("Item Group", "Services") else \
        frappe.db.get_value("Item Group", {"is_group": 0}, "name")
    frappe.get_doc({"doctype": "Item", "item_code": ARTIGO_GASTO, "item_name": "Gasto (fatura do Docs)",
                    "description": "Linha de uma fatura de compra que não é mercadoria; a conta de gasto vem da Área do Docs.",
                    "item_group": grupo, "is_stock_item": 0, "is_purchase_item": 1, "is_sales_item": 0,
                    "include_item_in_manufacturing": 0,
                    "stock_uom": frappe.db.get_single_value("Stock Settings", "stock_uom") or "Nos"}
                   ).insert(ignore_permissions=True)


def conta_para_etiquetas(company, etiquetas: list) -> str | None:
    """A conta de gasto da etiqueta mais específica (as filhas antes das Áreas)."""
    abbr = _abbr(company)
    for e in sorted(etiquetas or [], key=lambda x: x[:2].isdigit()):
        c = CONTA_DA_ETIQUETA.get(e)
        if c and frappe.db.exists("Account", f"{c} - {abbr}"):
            return f"{c} - {abbr}"
    return None


# ---- referência do fornecedor ↔ artigo ----

def _ref_limpa(ref: str, item_code: str) -> str:
    """O importador prefixa algumas referências («maranpro-227622»); a do fornecedor é a parte final."""
    ref = (ref or "").strip()
    if ref and item_code and ref != item_code and ref.lower().endswith("-" + item_code.lower()):
        return item_code
    return ref


def ligar_oferta(item_code: str, supplier: str, ref: str, ja: set | None = None) -> bool:
    """Garante a linha `Item Supplier` (artigo, fornecedor, referência). `ja` = cache de (artigo, fornecedor)."""
    if not (item_code and supplier):
        return False
    chave = (item_code, supplier)
    if ja is not None and chave in ja:
        return False
    ref = _ref_limpa(ref, item_code)
    nome = frappe.db.get_value("Item Supplier", {"parent": item_code, "parenttype": "Item", "supplier": supplier},
                               ["name", "supplier_part_no"], as_dict=True)
    if nome:
        if ref and not nome.supplier_part_no:
            frappe.db.set_value("Item Supplier", nome.name, "supplier_part_no", ref, update_modified=False)
    else:
        idx = (frappe.db.sql("select max(idx) from `tabItem Supplier` where parent=%s and parenttype='Item'",
                             item_code)[0][0] or 0) + 1
        frappe.get_doc({"doctype": "Item Supplier", "parent": item_code, "parenttype": "Item",
                        "parentfield": "supplier_items", "idx": idx, "supplier": supplier,
                        "supplier_part_no": ref[:140]}).db_insert()
    if ja is not None:
        ja.add(chave)
    return True


def ligar_referencias() -> dict:
    ja = {(r[0], r[1]) for r in frappe.db.sql(
        "select parent, supplier from `tabItem Supplier` where parenttype='Item' and ifnull(supplier_part_no,'')!=''")}
    novas = 0
    for o in frappe.db.sql("""select o.item_code, o.supplier, o.ref_fornecedor from `tabOferta do Fornecedor` o
                              join tabItem i on i.name=o.item_code""", as_dict=True):
        if ligar_oferta(o.item_code, o.supplier, o.ref_fornecedor, ja):
            novas += 1
    frappe.db.commit()
    return {"ligadas": novas, "total": len(ja)}


def tudo() -> dict:
    """F0 em todas as empresas do tenant; nunca deita abaixo uma migração."""
    out = {}
    for company in frappe.get_all("Company", pluck="name"):
        try:
            c = contas_iva(company)
            modelos_iva(company, c)
            g = contas_gasto(company)
            out[company] = {"iva": len([x for x in c.values() if x]), "gastos": len([x for x in g.values() if x])}
            frappe.db.commit()
        except Exception as e:  # noqa: BLE001
            frappe.db.rollback()
            frappe.log_error(f"compras.preparar {company}: {e}", "orbit compras F0")
            out[company] = {"erro": str(e)[:200]}
    try:
        if frappe.get_all("Company", limit=1):
            artigo_gasto()
            frappe.db.commit()
        out["referencias"] = ligar_referencias()
    except Exception as e:  # noqa: BLE001
        frappe.db.rollback()
        frappe.log_error(f"compras.preparar referências: {e}", "orbit compras F0")
        out["referencias"] = {"erro": str(e)[:200]}
    return out
