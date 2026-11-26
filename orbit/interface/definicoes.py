"""Definições em ecrãs próprios dentro da interface /orbit (F2b, 20-11-2026).

As listas de configuração mais usadas editam-se aqui (tabela no sítio, acrescentar, apagar, mudar o nome, ordenar);
o resto continua na roda dentada com ligação para o ecrã do Frappe. Tudo com as permissões da pessoa (`doc.save()`,
`frappe.delete_doc` sem ignorar permissões; um registo em uso não se apaga — o Frappe recusa e diz porquê).
Caixas de email e utilizadores ficam só para consulta: ligar caixas e dar acessos faz-se no portal.
"""
from __future__ import annotations

import frappe
from frappe.utils import cint

# chave → doctype, título, campo do nome ("__name" = nome escrito à mão), campos editáveis (campo, rótulo, tipo), ordem
CONF = {
    "fases": {"dt": "CRM Deal Status", "titulo": "Fases dos negócios", "grupo": "CRM", "nome": "deal_status",
              "campos": [("deal_status", "Fase", "Data"), ("type", "Tipo", "Select"), ("probability", "Probabilidade (%)", "Int"),
                         ("color", "Cor", "Select")], "ordem": "position"},
    "estados-leads": {"dt": "CRM Lead Status", "titulo": "Estados das leads", "grupo": "CRM", "nome": "lead_status",
                      "campos": [("lead_status", "Estado", "Data"), ("type", "Tipo", "Select"), ("color", "Cor", "Select")],
                      "ordem": "position"},
    "origens": {"dt": "CRM Lead Source", "titulo": "Origens", "grupo": "CRM", "nome": "source_name",
                "campos": [("source_name", "Origem", "Data"), ("details", "Notas", "Text")]},
    "motivos-perda": {"dt": "CRM Lost Reason", "titulo": "Motivos de perda", "grupo": "CRM", "nome": "lost_reason",
                      "campos": [("lost_reason", "Motivo", "Data"), ("description", "Descrição", "Text")]},
    "setores": {"dt": "CRM Industry", "titulo": "Setores", "grupo": "CRM", "nome": "industry", "campos": [("industry", "Setor", "Data")]},
    "territorios": {"dt": "CRM Territory", "titulo": "Territórios", "grupo": "CRM", "nome": "territory_name",
                    "campos": [("territory_name", "Território", "Data"), ("parent_crm_territory", "Pertence a", "Link"),
                               ("is_group", "Tem territórios dentro", "Check")]},
    "tipos-ticket": {"dt": "HD Ticket Type", "titulo": "Tipos de ticket", "grupo": "Atendimento (Desk)", "nome": "__name",
                     "campos": [("__name", "Tipo", "Data"), ("description", "Descrição", "Text"), ("priority", "Prioridade", "Link"),
                                ("disabled", "Desligado", "Check")]},
    "prioridades": {"dt": "HD Ticket Priority", "titulo": "Prioridades dos tickets", "grupo": "Atendimento (Desk)", "nome": "__name",
                    "campos": [("__name", "Prioridade", "Data"), ("level", "Nível", "Select"), ("description", "Descrição", "Text"),
                               ("disabled", "Desligada", "Check")]},
    "modelos-email": {"dt": "Email Template", "titulo": "Modelos de email", "grupo": "Correio", "nome": "__name",
                      "campos": [("__name", "Nome", "Data"), ("subject", "Assunto", "Data"), ("response", "Texto", "Text"),
                                 ("enabled", "Ativo", "Check")]},
}


_NOME_FIXO = ("fases", "estados-leads", "tipos-ticket", "prioridades")   # o Desk usa os nomes ingleses; Won/Lost/Ready to Close… são usados pelo código (loja → CRM, funil)
# 26-11-2026 (Inês, JF): nas fases e nos estados das leads o nome muda-se — fica guardado como «nome à vista»
# (`orbit_rotulo`), que é o que o /orbit mostra em todo o lado; o nome interno continua o mesmo, porque o código usa-o.
_COM_ROTULO = {"fases": "CRM Deal Status", "estados-leads": "CRM Lead Status"}


def instalar() -> None:
    """Campo «Nome à vista (Orbit)» nas fases dos negócios e nos estados das leads (idempotente; after_migrate)."""
    from frappe.custom.doctype.custom_field.custom_field import create_custom_field
    for dt in _COM_ROTULO.values():
        if frappe.db.exists("DocType", dt) and not frappe.db.exists("Custom Field", {"dt": dt, "fieldname": "orbit_rotulo"}):
            create_custom_field(dt, {"fieldname": "orbit_rotulo", "label": "Nome à vista (Orbit)", "fieldtype": "Data",
                                     "insert_after": "type", "description": "Vazio = o nome de origem, traduzido."})


def _guarda():
    from orbit.interface.api import _guarda as g
    g()


def _cfg(chave):
    c = CONF.get(chave)
    if not c or not frappe.db.exists("DocType", c["dt"]):
        frappe.throw("Definição desconhecida.")
    return c


def _opcoes(meta, campo, tipo):
    f = meta.get_field(campo)
    if tipo == "Select" and f:
        return [o for o in (f.options or "").split("\n") if o]
    if tipo == "Link" and f and f.options:
        return [""] + frappe.get_all(f.options, pluck="name", limit=200)
    return None


@frappe.whitelist()
def indice():
    _guarda()
    out = []
    for k, c in CONF.items():
        if frappe.db.exists("DocType", c["dt"]) and frappe.has_permission(c["dt"], "read"):
            out.append({"chave": k, "titulo": c["titulo"], "grupo": c["grupo"], "n": frappe.db.count(c["dt"])})
    return out


@frappe.whitelist()
def lista(chave: str):
    _guarda()
    c = _cfg(chave)
    meta = frappe.get_meta(c["dt"])
    campos = [x for x in c["campos"] if x[0] == "__name" or meta.has_field(x[0])]
    reais = [x[0] for x in campos if x[0] != "__name"]
    linhas = frappe.get_list(c["dt"], fields=["name"] + reais, order_by=(f"{c['ordem']} asc, name asc" if c.get("ordem") else "name asc"),
                             limit=500)
    for l in linhas:
        l["__name"] = l.name
    from orbit.interface.api import _rotulo_estado
    return {"titulo": c["titulo"], "ordenavel": bool(c.get("ordem")), "nome": c["nome"],
            "nome_fixo": chave in _NOME_FIXO and chave not in _COM_ROTULO, "nome_rotulo": chave in _COM_ROTULO,
            "campos": [{"campo": x[0], "rotulo": x[1], "tipo": x[2], "opcoes": _opcoes(meta, x[0], x[2])} for x in campos],
            "linhas": linhas, "pode_criar": frappe.has_permission(c["dt"], "create"),
            "pode_editar": frappe.has_permission(c["dt"], "write"), "pode_apagar": frappe.has_permission(c["dt"], "delete"),
            "rotulos": {l.name: _rotulo_estado(l.name) for l in linhas} if chave in _NOME_FIXO else {}}


def _aplicar(doc, c, valores):
    for campo, _r, tipo in c["campos"]:
        if campo == "__name" or campo == c["nome"] or campo not in valores:
            continue
        v = valores[campo]
        if tipo in ("Check", "Int"):
            v = cint(v)
        doc.set(campo, v)


@frappe.whitelist(methods=["POST"])
def gravar(chave: str, nome: str, valores: str):
    _guarda()
    import json
    c = _cfg(chave)
    valores = json.loads(valores) if isinstance(valores, str) else valores
    doc = frappe.get_doc(c["dt"], nome)
    _aplicar(doc, c, valores)
    novo = (valores.get(c["nome"]) or "").strip() if c["nome"] in valores else ""
    if chave in _COM_ROTULO and doc.meta.has_field("orbit_rotulo"):
        # o nome escrito fica como nome à vista; igual ao de origem (ou vazio) = sem nome próprio
        from orbit.interface.api import _rotulo_origem
        doc.orbit_rotulo = "" if not novo or novo in (nome, _rotulo_origem(nome)) else novo
        doc.save()
        return {"ok": True, "nome": nome}
    doc.save()
    if novo and novo != nome and chave in _NOME_FIXO:
        frappe.throw("O nome interno desta fase/estado é usado pelo Orbit (lojas, funil, relatórios) e não muda; "
                     "no ecrã aparece em português.")
    if novo and novo != nome:
        frappe.rename_doc(c["dt"], nome, novo, merge=False)
        nome = novo
    return {"ok": True, "nome": nome}


@frappe.whitelist(methods=["POST"])
def criar(chave: str, valores: str):
    _guarda()
    import json
    c = _cfg(chave)
    valores = json.loads(valores) if isinstance(valores, str) else valores
    nome = (valores.get(c["nome"]) or "").strip()
    if not nome:
        frappe.throw("Falta o nome.")
    d = {"doctype": c["dt"]}
    if c["nome"] == "__name":
        d["__newname"] = nome
        doc = frappe.get_doc(d)
        doc.name = nome
    else:
        d[c["nome"]] = nome
        doc = frappe.get_doc(d)
    _aplicar(doc, c, valores)
    if c.get("ordem"):
        doc.set(c["ordem"], (frappe.db.sql(f"select max(`{c['ordem']}`) from `tab{c['dt']}`")[0][0] or 0) + 1)
    if c["dt"] == "Email Template" and not doc.get("subject"):
        doc.subject = nome
    doc.insert(set_name=nome if c["nome"] == "__name" else None)
    return {"ok": True, "nome": doc.name}


@frappe.whitelist(methods=["POST"])
def apagar(chave: str, nome: str):
    _guarda()
    c = _cfg(chave)
    try:
        frappe.delete_doc(c["dt"], nome)
    except frappe.LinkExistsError:
        frappe.throw("Está em uso — não se pode apagar. Pode desligá-lo ou mudar-lhe o nome.")
    return {"ok": True}


@frappe.whitelist(methods=["POST"])
def ordenar(chave: str, nomes: str):
    _guarda()
    import json
    c = _cfg(chave)
    if not c.get("ordem"):
        frappe.throw("Esta lista não tem ordem.")
    for i, n in enumerate(json.loads(nomes), start=1):
        d = frappe.get_doc(c["dt"], n)
        d.set(c["ordem"], i)
        d.save()
    return {"ok": True}


@frappe.whitelist()
def caixas():
    """Só consulta: as caixas que entram no CRM e como (ligar/desligar faz-se no portal, em Stratechna Orbit)."""
    _guarda()
    if not frappe.has_permission("Email Account", "read"):
        return []
    out = []
    for a in frappe.get_list("Email Account", fields=["name", "email_id", "enable_incoming", "enable_outgoing", "orbit_registo_crm",
                                                       "orbit_dono", "default_outgoing"], order_by="email_id asc", limit=200):
        if a.orbit_registo_crm:
            uso = "CRM · " + ("só para o dono" if a.orbit_registo_crm == "so_eu" else "equipa")
        elif a.default_outgoing:
            uso = "Envio dos avisos do Orbit"
        else:
            uso = "Desk / outro"
        n = frappe.db.count("Communication", {"email_account": a.name})
        out.append({"email": a.email_id, "uso": uso, "entrada": bool(a.enable_incoming), "envio": bool(a.enable_outgoing),
                    "dono": a.orbit_dono, "mensagens": n})
    return out


@frappe.whitelist()
def utilizadores():
    """Só consulta: quem tem acesso a este Orbit (dar e tirar acessos faz-se no portal — utilizadores contratados)."""
    _guarda()
    if not frappe.has_permission("User", "read"):
        return []
    us = frappe.get_list("User", filters={"user_type": "System User", "name": ["not in", ["Administrator", "Guest"]]},
                         fields=["name", "full_name", "enabled", "last_login", "last_active"], order_by="enabled desc, full_name asc", limit=300)
    for u in us:
        papeis = frappe.get_all("Has Role", filters={"parent": u.name, "parenttype": "User"}, pluck="role")
        u.perfil = next((p for p in papeis if p.startswith("Orbit")), None) or ("Gestão" if "System Manager" in papeis else f"{len(papeis)} papéis")
    return us
