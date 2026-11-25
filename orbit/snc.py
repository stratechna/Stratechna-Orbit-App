"""Plano de contas SNC do ERPNext arrumado (25-11-2026).

O modelo «Portugal - Plano de Contas SNC» que o ERPNext traz (`pt_pt_chart_template.json`) põe todas as subcontas
penduradas directamente na classe, a classe 2 inteira no Passivo (também os clientes), a classe 3 «Inventários» em
Gastos, a classe 8 no Passivo, as «passivos financeiros» (14x2) como Caixa e tipos de conta trocados (26/27/28 como
«Equity», 89 «Dividendos antecipados» como «Payable»…). O ERP escolhe as contas por omissão pelo tipo — a Stratechna
ficou com os fornecedores em «89 Dividendos antecipados» e não aceita nenhuma conta de clientes (tem de ser do Activo).

`reorganizar(company)` arruma uma empresa com este modelo **sem lançamentos**:
- raízes: classe 2 partida em «Contas a receber e outros activos (classe 2)» (Activo) e a original (Passivo); classe 3
  no Activo; classe 8 em Capital próprio com o 812 (imposto sobre o rendimento) nos Gastos; as 14x2 num grupo do
  Passivo;
- hierarquia pelo código: o pai é o código-prefixo mais longo do mesmo lado (Activo/Passivo); contas com filhos
  passam a grupo;
- tipos de conta só onde o ERP os usa (caixa, bancos, clientes, fornecedores, impostos, stock, CMVMC, depreciação,
  vendas); contas por omissão da empresa e meios de pagamento em contas finais certas.
Só mexe numa empresa com 0 lançamentos (GL Entry) e é idempotente; corre no after_migrate para as empresas novas.
"""
import frappe
from frappe.utils.nestedset import rebuild_tree

MODELO = "Portugal - Plano de Contas SNC"
RAIZ_ACTIVO_2 = "Contas a receber e outros activos (classe 2)"
GRUPO_PASSIVO_1 = "Outros instrumentos financeiros — passivos"

# códigos da classe 1 e 2 que são do Activo (os outros da classe 2 e os 14x2 são do Passivo)
ACTIVO_2 = ("21", "228", "229", "232", "239", "2431", "2432", "2437", "2438", "261", "262", "263", "266", "269",
            "2713", "2721", "2741", "279", "281")
PASSIVO_EXCEPCOES = ("218",)          # adiantamentos de clientes: Passivo dentro dos clientes
PASSIVO_1 = ("1412", "1422", "1432")

TIPOS = {   # código → tipo de conta (o resto fica sem tipo)
    "11": "Cash", "12": "Bank", "13": "Bank",
    **{c: "Receivable" for c in ("2111", "2112", "2113", "2114", "2115", "2116",
                                 "2121", "2122", "2123", "2124", "2125", "2126")},
    **{c: "Payable" for c in ("2211", "2212", "2213", "2214", "2215", "2216",
                              "2221", "2222", "2223", "2224", "2225", "2226", "2711")},
    **{c: "Tax" for c in ("241", "242", "2431", "2432", "2433", "2434", "2435", "2436", "2437", "2438", "2439",
                          "244", "245", "246", "248")},
    "320": "Stock", "382": "Stock Adjustment", "611": "Cost of Goods Sold", "642": "Depreciation",
    "448": "Accumulated Depreciation",
    **{c: "Income Account" for c in ("711", "712", "713", "714", "716", "717", "718", "721", "722", "725", "726", "728")},
}
OMISSAO = {   # campo da empresa → código
    "default_payable_account": "2211", "default_receivable_account": "2111", "default_cash_account": "11",
    "default_bank_account": "12", "default_expense_account": "611", "default_income_account": "721",
    "default_inventory_account": "320", "stock_adjustment_account": "382", "depreciation_expense_account": "642",
    "accumulated_depreciation_account": "448",
}


def _lado(cod: str, root_atual: str) -> str:
    c = cod[0]
    if c == "1":
        return "Liability" if cod.startswith(PASSIVO_1) else "Asset"
    if c == "2":
        if cod.startswith(PASSIVO_EXCEPCOES):
            return "Liability"
        return "Asset" if cod.startswith(ACTIVO_2) else "Liability"
    if c == "3" or c == "4":
        return "Asset"
    if c == "5":
        return "Equity"
    if c == "6":
        return "Expense"
    if c == "7":
        return "Income"
    if c == "8":
        return "Expense" if cod.startswith("812") else "Equity"
    return root_atual


def usa_modelo(company) -> bool:
    return frappe.db.get_value("Company", company, "chart_of_accounts") == MODELO


def ja_arrumada(company) -> bool:
    abbr = frappe.db.get_value("Company", company, "abbr")
    return bool(frappe.db.exists("Account", f"{RAIZ_ACTIVO_2} - {abbr}"))


def _grupo(company, abbr, nome, pai, root_type, numero=None):
    nome_full = f"{numero} - {nome} - {abbr}" if numero else f"{nome} - {abbr}"
    if not frappe.db.exists("Account", nome_full):
        d = frappe.get_doc({"doctype": "Account", "account_name": nome, "account_number": numero, "company": company,
                            "parent_account": pai, "is_group": 1, "root_type": root_type})
        d.flags.ignore_mandatory = True
        d.insert(ignore_permissions=True)
    return nome_full


def reorganizar(company: str, aplicar: bool = False) -> dict:
    """Plano (aplicar=False) ou aplicação. Devolve o resumo das mudanças."""
    if not usa_modelo(company):
        return {"ok": False, "motivo": f"A empresa não usa o modelo «{MODELO}»."}
    if frappe.db.count("GL Entry", {"company": company}):
        return {"ok": False, "motivo": "A empresa já tem lançamentos — reorganizar à mão, com o contabilista."}
    abbr = frappe.db.get_value("Company", company, "abbr")
    contas = frappe.get_all("Account", filters={"company": company},
                            fields=["name", "account_number", "account_name", "parent_account", "root_type",
                                    "account_type", "is_group"])
    por_num = {c.account_number: c for c in contas if c.account_number}
    raiz = {}   # (classe, lado) → nome do grupo raiz
    for c in contas:
        if not c.parent_account and c.name[:1].isdigit():
            raiz[c.name[:1]] = c.name
    mudancas = []

    if aplicar:
        # raízes e grupos novos
        raiz_a2 = _grupo(company, abbr, RAIZ_ACTIVO_2, None, "Asset")
        pas1 = _grupo(company, abbr, GRUPO_PASSIVO_1, raiz["2"], "Liability")
        if "320" not in por_num and "32" in por_num:
            frappe.get_doc({"doctype": "Account", "account_name": "Mercadorias em armazém", "account_number": "320",
                            "company": company, "parent_account": raiz["3"], "is_group": 0,
                            "root_type": "Expense"}).insert(ignore_permissions=True)
            contas = frappe.get_all("Account", filters={"company": company},
                                    fields=["name", "account_number", "account_name", "parent_account", "root_type",
                                            "account_type", "is_group"])
            por_num = {c.account_number: c for c in contas if c.account_number}
    else:
        raiz_a2, pas1 = f"{RAIZ_ACTIVO_2} - {abbr}", f"{GRUPO_PASSIVO_1} - {abbr}"

    def raiz_de(cod, lado):
        cl = cod[0]
        if cl == "2" and lado == "Asset":
            return raiz_a2
        if cl == "1" and lado == "Liability":
            return pas1
        if cl == "8" and lado == "Expense":
            return raiz["6"]
        return raiz[cl]

    lados = {n: _lado(n, por_num[n].root_type) for n in por_num}
    pais, com_filhos = {}, set()
    for n in por_num:
        if len(n) < 2:
            continue
        p = next((n[:k] for k in range(len(n) - 1, 1, -1) if n[:k] in por_num and lados[n[:k]] == lados[n]), None)
        pais[n] = por_num[p].name if p else raiz_de(n, lados[n])
        if p:
            com_filhos.add(p)
    for n, c in por_num.items():
        novo = {"parent_account": pais.get(n, c.parent_account), "root_type": lados[n],
                "report_type": "Balance Sheet" if lados[n] in ("Asset", "Liability", "Equity") else "Profit and Loss",
                "is_group": 1 if n in com_filhos else 0,
                "account_type": "" if n in com_filhos else TIPOS.get(n, "")}
        dif = {k: v for k, v in novo.items() if (c.get(k) or "") != (v or "")}
        if dif:
            mudancas.append((c.name, dif))
            if aplicar:
                frappe.db.set_value("Account", c.name, dif, update_modified=False)
    if aplicar:
        # raízes: classe 3 no Activo, 8 em Capital próprio
        for cl, rt in (("3", "Asset"), ("8", "Equity")):
            frappe.db.set_value("Account", raiz[cl], {"root_type": rt, "report_type": "Balance Sheet"},
                                update_modified=False)
        # os grupos de gasto da F0 (fatura de compra) ficam directamente nos Gastos
        for g in ("Instalações e despesas gerais", "Viaturas", "Pessoal (outros gastos)", "Financeiros e seguros",
                  "Jurídico, fiscal e societário", "Obras, assistência e transportes"):
            if frappe.db.exists("Account", f"{g} - {abbr}"):
                frappe.db.set_value("Account", f"{g} - {abbr}", "parent_account", raiz["6"], update_modified=False)
        # contas sem número (IVA da F0, Duties and Taxes, Others…) herdam o lado do pai
        rebuild_tree("Account")
        for c in frappe.get_all("Account", filters={"company": company, "account_number": ["is", "not set"],
                                                     "parent_account": ["is", "set"]}, fields=["name", "lft", "rgt"]):
            rt = frappe.db.sql("""select root_type from tabAccount where company=%s and lft<%s and rgt>%s
                                  and ifnull(parent_account,'')='' limit 1""", (company, c.lft, c.rgt))
            if rt:
                frappe.db.set_value("Account", c.name, {"root_type": rt[0][0], "report_type":
                                    "Balance Sheet" if rt[0][0] in ("Asset", "Liability", "Equity") else "Profit and Loss"},
                                    update_modified=False)
        omissao = {campo: por_num[cod].name for campo, cod in OMISSAO.items() if cod in por_num}
        frappe.db.set_value("Company", company, omissao)
        for mp in frappe.get_all("Mode of Payment Account", filters={"company": company},
                                 fields=["name", "default_account"]):
            tipo = frappe.db.get_value("Account", mp.default_account, "account_type")
            if tipo not in ("Cash", "Bank"):
                frappe.db.set_value("Mode of Payment Account", mp.name, "default_account", por_num["11"].name)
        frappe.clear_cache()
    return {"ok": True, "mudancas": len(mudancas), "amostra": mudancas[:15]}


def arrumar_novas():
    """after_migrate: empresas com o modelo SNC, sem lançamentos e ainda por arrumar."""
    for co in frappe.get_all("Company", filters={"chart_of_accounts": MODELO}, pluck="name"):
        if not ja_arrumada(co) and not frappe.db.count("GL Entry", {"company": co}):
            try:
                reorganizar(co, aplicar=True)
                frappe.db.commit()
            except Exception:  # noqa: BLE001
                frappe.db.rollback()
                frappe.log_error(title=f"SNC: arrumar {co}")
