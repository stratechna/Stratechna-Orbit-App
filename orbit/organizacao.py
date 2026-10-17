"""Pessoas e Desk de um tenant (17-10-2026, pedido do Vítor).

Perfis — o que uma pessoa pode fazer. Cada perfil é um Role Profile «Orbit · <nome>» com as funções das
apps; o tenant pode criar os seus (qualquer Role Profile serve), e a Fase 0 do portal lê a lista. Uma
pessoa sem perfil entrava no Orbit sem função nenhuma — era o que acontecia antes disto.

Departamento — onde a pessoa trabalha (Design Gráfico, TI, Administração…): campo `orbit_departamento`
no User (Link → Department). É independente do perfil e da marca.

Desk — regra do Vítor (17-10-2026): TODOS os bilhetes vão para «Triagem», a não ser que o destino seja
claro, por onde vieram ou pelo assunto:
  1. o campo «Marca» do formulário (portal do Helpdesk, área de cliente) — `orbit_marca`;
  2. o endereço para onde o cliente escreveu (o «Para»/«Cc» do email: suporte@webgate.pt → Webgate),
     mesmo que todos os endereços reencaminhem para uma só caixa física — só domínios PRÓPRIOS de uma
     marca; os do grupo (ex.: stratechna.pt/.com) não decidem nada;
  3. o assunto nomeia UMA só marca (pelo nome ou por um domínio próprio dela);
  4. sem nada disto — ou com dúvida — «Triagem», que quem gere o Desk vê toda; quem pega no pedido
     muda-lhe a equipa e daí em diante só essa equipa o vê.
O portal manda (marcas-tenant → site_config) `orbit_desk_dominios` (domínio → marca, só os próprios) e
`orbit_desk_marcas` (as marcas que se reconhecem no assunto — sem as que são o grupo).
"""
import frappe

PREFIXO = "Orbit · "
TRIAGEM = "Triagem"

# funções por perfil — só entram as que existem no tenant (depende das apps instaladas)
PERFIS = {
    "Gestão": ["System Manager", "Sales Manager", "Sales User", "Agent Manager", "Agent", "Projects Manager",
               "Projects User", "Accounts Manager", "Accounts User", "HR Manager", "HR User", "Purchase Manager",
               "Purchase User", "Stock Manager", "Stock User", "Marketing Manager", "Wiki Approver",
               "Knowledge Base Editor", "Report Manager", "Gestor de Correio", "Employee"],
    "Comercial": ["Sales User", "Sales Manager", "Marketing Manager", "Projects User", "Wiki Approver", "Employee"],
    "Apoio ao cliente": ["Agent", "Agent Manager", "Knowledge Base Editor", "Projects User", "Sales User",
                         "Wiki Approver", "Employee"],
    "Recursos humanos": ["HR User", "HR Manager", "Employee", "Wiki Approver"],
    "Contabilidade": ["Accounts User", "Accounts Manager", "Purchase User", "Sales User", "Employee", "Wiki Approver"],
    "Produção": ["Projects User", "Wiki Approver", "Employee"],
    "Operações": ["Projects User", "Projects Manager", "Stock User", "Purchase User", "Sales User", "Agent",
                  "Wiki Approver", "Employee"],
}


def _criar_equipa(nome: str) -> bool:
    """O Helpdesk não aceita uma equipa sem pessoas (`users` obrigatório): nasce com os agentes activos,
    e o orbit_isolamento.py acerta depois quem fica. Sem agentes, fica para quando os houver."""
    if frappe.db.exists("HD Team", nome) or not frappe.db.exists("DocType", "HD Team"):
        return False
    agentes = frappe.get_all("HD Agent", filters={"is_active": 1}, pluck="name") if \
        frappe.get_meta("HD Agent").has_field("is_active") else frappe.get_all("HD Agent", pluck="name")
    if not agentes:
        return False
    frappe.get_doc({"doctype": "HD Team", "team_name": nome, "users": [{"user": a} for a in agentes]}).insert(
        ignore_permissions=True)
    return True


def garantir() -> None:
    """after_migrate: perfis base, equipa Triagem e o campo de departamento — em todos os tenants.
    Nunca faz falhar a migração: um problema aqui fica no Error Log e o resto da migração segue."""
    try:
        _garantir()
    except Exception:
        frappe.db.rollback()
        frappe.log_error(title="orbit.organizacao.garantir")


def _garantir() -> None:
    existentes = set(frappe.get_all("Role", pluck="name"))
    for nome, funcoes in PERFIS.items():
        rp = PREFIXO + nome
        doc = frappe.get_doc("Role Profile", rp) if frappe.db.exists("Role Profile", rp) else \
            frappe.get_doc({"doctype": "Role Profile", "role_profile": rp})
        quer = [f for f in funcoes if f in existentes]
        if sorted(r.role for r in doc.get("roles") or []) != sorted(quer):
            doc.set("roles", [{"role": f} for f in quer])
            doc.save(ignore_permissions=True)
    _criar_equipa(TRIAGEM)
    if not frappe.db.exists("Custom Field", {"dt": "User", "fieldname": "orbit_departamento"}):
        from frappe.custom.doctype.custom_field.custom_field import create_custom_field
        create_custom_field("User", {"fieldname": "orbit_departamento", "label": "Departamento",
                                     "fieldtype": "Link", "options": "Department", "insert_after": "role_profile_name"})
    frappe.db.commit()


def perfil_do_nome(nome: str) -> str | None:
    """«Gestão» → «Orbit · Gestão»; um Role Profile do próprio tenant usa-se pelo nome."""
    for n in (PREFIXO + (nome or ""), nome or ""):
        if n and frappe.db.exists("Role Profile", n):
            return n
    return None


def configurar_desk(dominios: dict, marcas: list, reconheciveis: list | None = None) -> list:
    """Chamado pelo marcas-tenant: o mapa domínio → marca, o campo «Marca» no bilhete e no formulário."""
    from frappe.installer import update_site_config
    feito = []
    if not frappe.db.exists("DocType", "HD Ticket"):
        return ["Desk não instalado"]
    update_site_config("orbit_desk_dominios", {d.lower(): m for d, m in (dominios or {}).items()})
    update_site_config("orbit_desk_marcas", list(reconheciveis if reconheciveis is not None else marcas))
    opcoes = "\n".join([""] + list(marcas))
    nome = "HD Ticket-orbit_marca"
    if frappe.db.exists("Custom Field", nome):
        cf = frappe.get_doc("Custom Field", nome)
        if cf.options != opcoes:
            cf.options = opcoes
            cf.save(ignore_permissions=True)
    else:
        from frappe.custom.doctype.custom_field.custom_field import create_custom_field
        create_custom_field("HD Ticket", {"fieldname": "orbit_marca", "label": "Marca", "fieldtype": "Select",
                                          "options": opcoes, "insert_after": "agent_group"})
        feito.append("campo Marca no bilhete")
    if frappe.db.exists("HD Ticket Template", "Default"):
        t = frappe.get_doc("HD Ticket Template", "Default")
        if not any(f.fieldname == "orbit_marca" for f in t.fields):
            t.append("fields", {"fieldname": "orbit_marca", "required": 1})
            t.save(ignore_permissions=True)
            feito.append("Marca obrigatória no formulário de abertura")
    for m in list(marcas) + [TRIAGEM]:
        if _criar_equipa(m):
            feito.append(f"equipa {m}")
    return feito or ["Desk: já estava"]


def _equipa_da_marca(marca: str) -> str | None:
    return marca if marca and frappe.db.exists("HD Team", marca) else None


def _sem_acentos(t: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()


def marca_pelo_assunto(assunto: str) -> str | None:
    """A marca que o assunto nomeia — só se for UMA. Nome inteiro (palavra) ou domínio próprio."""
    import re
    texto = _sem_acentos(assunto)
    if not texto:
        return None
    dominios = frappe.conf.get("orbit_desk_dominios") or {}
    achadas = set()
    for m in frappe.conf.get("orbit_desk_marcas") or []:
        if re.search(r"(?<![a-z0-9])" + re.escape(_sem_acentos(m)) + r"(?![a-z0-9])", texto):
            achadas.add(m)
    for d, m in dominios.items():
        if d in texto:
            achadas.add(m)
    return achadas.pop() if len(achadas) == 1 else None


def ticket_equipa(doc, method=None):
    """HD Ticket.before_insert: formulário → assunto → Triagem (nunca fica sem equipa, nunca invisível)."""
    if doc.get("agent_group"):
        return
    marca = doc.get("orbit_marca") or marca_pelo_assunto(doc.get("subject"))
    equipa = _equipa_da_marca(marca)
    if equipa:
        doc.agent_group = equipa
        doc.orbit_marca = marca
    elif frappe.db.exists("HD Team", TRIAGEM):
        doc.agent_group = TRIAGEM


def ticket_por_destinatario(doc, method=None):
    """Communication.after_insert: o primeiro email de um bilhete em Triagem decide a marca pelo domínio
    para onde o cliente escreveu (Para e Cc)."""
    if doc.reference_doctype != "HD Ticket" or doc.sent_or_received != "Received" or not doc.reference_name:
        return
    mapa = frappe.conf.get("orbit_desk_dominios") or {}
    if not mapa:
        return
    t = frappe.db.get_value("HD Ticket", doc.reference_name, ["agent_group", "orbit_marca"], as_dict=True)
    if not t or (t.agent_group and t.agent_group != TRIAGEM) or t.orbit_marca:
        return
    destinos = ",".join(filter(None, [doc.recipients, doc.cc]))
    for end in (e.strip().lower() for e in destinos.replace(";", ",").split(",")):
        dominio = end.split("@")[-1].strip(" >")
        marca = mapa.get(dominio)
        if marca and _equipa_da_marca(marca):
            frappe.db.set_value("HD Ticket", doc.reference_name, {"agent_group": marca, "orbit_marca": marca},
                                update_modified=False)
            return
