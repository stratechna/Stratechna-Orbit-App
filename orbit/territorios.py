"""Territórios do CRM: Europa → países europeus, Portugal → 18 distritos e as 2 regiões autónomas (24-11-2026).

Pedido do Vítor: «Nos territórios podes abrir os distritos de Portugal? E juntas também os países da Europa.»
`CRM Territory` é uma árvore (grupo «Europa» → «Portugal» → distritos). Só cria o que falta; o que cada
tenant tenha acrescentado ou mudado fica. Corre em `after_migrate` (todos os Orbit, os novos também).
Países transcontinentais (Rússia, Turquia, Cáucaso, Cazaquistão) ficam de fora; acrescentam-se à mão se fizer falta.
"""
import frappe

DISTRITOS = ["Aveiro", "Beja", "Braga", "Bragança", "Castelo Branco", "Coimbra", "Évora", "Faro", "Guarda", "Leiria",
             "Lisboa", "Portalegre", "Porto", "Santarém", "Setúbal", "Viana do Castelo", "Vila Real", "Viseu",
             "Região Autónoma dos Açores", "Região Autónoma da Madeira"]
PAISES = ["Albânia", "Alemanha", "Andorra", "Áustria", "Bélgica", "Bielorrússia", "Bósnia e Herzegovina", "Bulgária",
          "Chéquia", "Chipre", "Croácia", "Dinamarca", "Eslováquia", "Eslovénia", "Espanha", "Estónia", "Finlândia",
          "França", "Grécia", "Hungria", "Irlanda", "Islândia", "Itália", "Kosovo", "Letónia", "Listenstaine",
          "Lituânia", "Luxemburgo", "Macedónia do Norte", "Malta", "Moldávia", "Mónaco", "Montenegro", "Noruega",
          "Países Baixos", "Polónia", "Reino Unido", "Roménia", "São Marinho", "Sérvia", "Suécia", "Suíça", "Ucrânia",
          "Vaticano"]


def _t(nome, pai=None, grupo=0):
    if frappe.db.exists("CRM Territory", nome):
        return
    frappe.get_doc({"doctype": "CRM Territory", "territory_name": nome, "parent_crm_territory": pai,
                    "is_group": grupo}).insert(ignore_permissions=True)


def acertar():
    if not frappe.db.exists("DocType", "CRM Territory"):
        return
    try:
        _t("Europa", grupo=1)
        _t("Portugal", "Europa", 1)
        if not frappe.db.get_value("CRM Territory", "Portugal", "is_group"):
            frappe.db.set_value("CRM Territory", "Portugal", "is_group", 1)
        for d in DISTRITOS:
            _t(d, "Portugal")
        for p in PAISES:
            _t(p, "Europa")
        frappe.db.commit()
    except Exception as e:  # noqa: BLE001 — nunca deita abaixo uma migração
        frappe.db.rollback()
        frappe.log_error(f"territorios: {e}", "orbit territórios")
