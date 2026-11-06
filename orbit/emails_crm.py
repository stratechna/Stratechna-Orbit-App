"""Os emails no Orbit CRM (05-11-2026) — plano docs/PLANO-EMAILS-NO-CRM.md, regra decidida pelo Vítor.

Uma caixa entra no CRM quando é **partilhada** (sempre, visível para a equipa) ou **pessoal com o interruptor da
pessoa ligado** («para a equipa» ou «só para mim»). O portal decide e chama `ligar_caixa`; aqui:

* cada caixa é uma Email Account própria («Orbit CRM · <caixa>»), só de entrada, com a **palavra-passe de
  aplicação** que o portal gerou para ela (nunca a de uma pessoa), a ler a Entrada e os Enviados **a partir de
  agora** (uidvalidity/uidnext acertados antes da 1.ª leitura — não despeja anos de correio no CRM);
* cada email que chega (`filtrar`, gancho de Communication) só fica se a outra pessoa da conversa já está no CRM
  (negócio em curso › lead › contacto — o mesmo alvo do «Associar este email») e não está na lista de exclusões;
  senão apaga-se logo. Nunca cria contactos nem leads;
* «só para mim»: o email (e as notas que daí nascem) leva `orbit_privado_de` = o utilizador dono da caixa, e
  `filtrar_actividades` / as permissões escondem-no dos outros, também dos administradores do tenant (06-11-2026).

A ligação automática do Frappe não serve aqui: só existe para uma Email Account por site e liga por endereços
com etiqueta (`caixa+Doctype=nome@`), não pelo endereço de quem escreve.
"""
from __future__ import annotations

import imaplib
import json
import re

import frappe

NIVEIS = ("equipa", "so_eu")
_CAMPOS = {
    "Email Account": [
        {"fieldname": "orbit_registo_crm", "label": "Registo no CRM (Orbit)", "fieldtype": "Select",
         "options": "\nequipa\nso_eu", "insert_after": "email_id", "read_only": 1},
        {"fieldname": "orbit_dono", "label": "Dono da caixa (Orbit)", "fieldtype": "Link", "options": "User",
         "insert_after": "orbit_registo_crm", "read_only": 1},
        {"fieldname": "orbit_exclusoes", "label": "Nunca registar (Orbit)", "fieldtype": "Small Text",
         "insert_after": "orbit_dono", "read_only": 1},
    ],
    "Communication": [
        {"fieldname": "orbit_privado_de", "label": "Privado de (Orbit)", "fieldtype": "Link", "options": "User",
         "insert_after": "email_account", "read_only": 1},
    ],
    "FCRM Note": [
        {"fieldname": "orbit_privado_de", "label": "Privado de (Orbit)", "fieldtype": "Link", "options": "User",
         "insert_after": "reference_docname", "read_only": 1},
    ],
}


def instalar() -> None:
    """Os campos próprios (idempotente; também no after_migrate)."""
    from frappe.custom.doctype.custom_field.custom_field import create_custom_field
    for dt, campos in _CAMPOS.items():
        if not frappe.db.exists("DocType", dt):
            continue
        for c in campos:
            if not frappe.db.exists("Custom Field", {"dt": dt, "fieldname": c["fieldname"]}):
                create_custom_field(dt, {**c, "module": "Orbit"})


def _so_portal():
    from orbit.portal import _so_portal as s
    s()


def _nome_conta(email: str) -> str:
    return f"Orbit CRM · {email}"


def _dominio_email(email: str) -> str | None:
    dom = email.rsplit("@", 1)[-1]
    return frappe.db.get_value("Email Domain", {"domain_name": dom}) or frappe.db.get_value("Email Domain", dom)


def _imap_estado(email: str, senha: str, dominio: str | None, servidor: str | None = None, porta: int | None = None) -> dict:
    """Pastas a ler (Entrada + a pasta \\Sent) e o uidvalidity/uidnext de cada uma AGORA.
    Com `servidor` (conta de fora: Gmail, Zoho…, 06-11-2026) liga-se a esse servidor por SSL em vez do do domínio."""
    if servidor:
        m = imaplib.IMAP4_SSL(servidor, int(porta or 993), timeout=30)
    else:
        d = frappe.get_doc("Email Domain", dominio)
        m = imaplib.IMAP4_SSL(d.email_server, int(d.incoming_port or 993)) if d.use_ssl else imaplib.IMAP4(d.email_server, int(d.incoming_port or 143))
    try:
        m.login(email, senha)
        pastas = ["INBOX"]
        _, linhas = m.list()
        for l in linhas or []:
            t = l.decode("utf-8", "replace")
            if "\\Sent" in t:
                nome = t.rsplit(' "', 1)[-1].rstrip('"') if t.endswith('"') else t.rsplit(" ", 1)[-1]
                pastas.append(nome)
                break
        estado = {}
        for p in pastas:
            _, r = m.status(f'"{p}"', "(UIDVALIDITY UIDNEXT)")
            s = r[0].decode() if r and r[0] else ""
            uv = re.search(r"UIDVALIDITY (\d+)", s)
            un = re.search(r"UIDNEXT (\d+)", s)
            if uv and un:
                estado[p] = (int(uv.group(1)), int(un.group(1)))
        return estado
    finally:
        try:
            m.logout()
        except Exception:
            pass


@frappe.whitelist()
def ligar_caixa(email: str, senha: str = None, nivel: str = "equipa", dono: str = None, exclusoes=None,
                servidor: str = None, porta=None):
    """Liga (ou actualiza) uma caixa no CRM. `nivel`: equipa | so_eu. `dono`: o User do Orbit da pessoa (só_eu).
    `servidor`/`porta` (06-11-2026): conta de fora (Gmail, Zoho…) — IMAP por SSL nesse servidor, com a palavra-passe
    de aplicação do fornecedor; sem eles, o servidor é o do domínio configurado no Orbit (caixas da casa)."""
    _so_portal()
    instalar()
    email = (email or "").strip().lower()
    if nivel not in NIVEIS or "@" not in email:
        return {"ok": False, "erro": "pedido inválido"}
    if nivel == "so_eu" and not (dono and frappe.db.exists("User", dono)):
        return {"ok": False, "erro": "«só para mim» precisa do utilizador do Orbit da pessoa"}
    excl = exclusoes if isinstance(exclusoes, list) else json.loads(exclusoes or "[]")
    excl = sorted({str(x).strip().lower() for x in excl if str(x).strip()})[:200]
    nome = _nome_conta(email)
    existe = frappe.db.exists("Email Account", nome)
    if not existe and not senha:
        return {"ok": False, "erro": "falta a palavra-passe de aplicação"}
    servidor = (servidor or "").strip().lower() or None
    if servidor and not re.fullmatch(r"[a-z0-9-]+(\.[a-z0-9-]+)+", servidor):
        return {"ok": False, "erro": "servidor IMAP inválido"}
    dominio = None if servidor else _dominio_email(email)
    if not servidor and not dominio:
        return {"ok": False, "erro": f"o domínio de {email} não está configurado no Orbit"}
    acc = frappe.get_doc("Email Account", nome) if existe else frappe.new_doc("Email Account")
    if servidor:
        acc.update({"email_server": servidor, "incoming_port": str(int(porta or 993)), "use_ssl": 1})
    acc.update({"email_account_name": nome, "email_id": email, "domain": dominio, "use_imap": 1,
                "enable_incoming": 1, "enable_outgoing": 0, "default_incoming": 0, "default_outgoing": 0,
                "create_contact": 0, "enable_automatic_linking": 0, "awaiting_password": 0,
                "orbit_registo_crm": nivel, "orbit_dono": dono if nivel == "so_eu" else None,
                "orbit_exclusoes": "\n".join(excl)})
    if acc.meta.has_field("create_lead_from_incoming_email"):
        acc.create_lead_from_incoming_email = 0
    if senha:
        acc.password = senha
    novas = {}
    if senha:
        try:
            novas = _imap_estado(email, senha, dominio, servidor, porta)
        except Exception as e:  # noqa: BLE001 — a mensagem do servidor ajuda quem liga (palavra-passe, IMAP desligado…)
            return {"ok": False, "erro": f"o servidor {servidor or dominio} recusou: {str(e)[:200]}"}
        if not novas:
            return {"ok": False, "erro": "a caixa não respondeu por IMAP com esta palavra-passe"}
        acc.set("imap_folder", [{"folder_name": p, "append_to": None} for p in novas])
    if existe:
        acc.save(ignore_permissions=True)
    else:
        acc.insert(ignore_permissions=True)
    # Só a partir de agora: com o uidvalidity igual ao do servidor, o Frappe lê do uidnext para a frente.
    for p, (uv, un) in novas.items():
        frappe.db.set_value("IMAP Folder", {"parent": acc.name, "folder_name": p},
                            {"uidvalidity": uv, "uidnext": un}, update_modified=False)
    frappe.db.commit()
    return {"ok": True, "conta": acc.name, "pastas": list(novas) or [f.folder_name for f in acc.imap_folder]}


@frappe.whitelist()
def desligar_caixa(email: str):
    """Pára de ler a caixa (a conta fica, desligada; o que já foi registado fica, como as notas do Associar)."""
    _so_portal()
    nome = _nome_conta((email or "").strip().lower())
    if frappe.db.exists("Email Account", nome):
        frappe.db.set_value("Email Account", nome, {"enable_incoming": 0, "orbit_registo_crm": ""})
        frappe.db.commit()
    return {"ok": True}


def _excluido(endereco: str, excl: list, propria: str) -> bool:
    e = (endereco or "").strip().lower()
    if not e or e == propria:
        return True
    dom = e.rsplit("@", 1)[-1]
    if dom == propria.rsplit("@", 1)[-1]:
        return True   # internos do mesmo domínio nunca contam como «cliente»
    return any(x == e or x.lstrip("@") == dom or (x.startswith("*.") and dom.endswith(x[1:])) for x in excl)


def _enderecos(texto: str) -> list:
    return [x.lower() for x in re.findall(r"[\w.+'-]+@[\w-]+(?:\.[\w-]+)+", texto or "")]


def filtrar(doc, method=None):
    """Gancho after_insert de Communication: só nos emails lidos por uma conta «Orbit CRM · …»."""
    if doc.communication_medium != "Email" or not doc.email_account or doc.reference_doctype:
        return
    nivel, dono, excl, propria = frappe.db.get_value(
        "Email Account", doc.email_account, ["orbit_registo_crm", "orbit_dono", "orbit_exclusoes", "email_id"]) \
        if frappe.db.has_column("Email Account", "orbit_registo_crm") else (None, None, None, None)
    if nivel not in NIVEIS:
        return
    propria = (propria or "").lower()
    lista = [x for x in (excl or "").splitlines() if x.strip()]
    remetente = (_enderecos(doc.sender) or [""])[0]
    outros = [remetente] if remetente != propria else _enderecos(f"{doc.recipients or ''},{doc.cc or ''}")
    from orbit.portal import _alvo_crm
    alvo = None
    for e in outros:
        if _excluido(e, lista, propria):
            continue
        alvo = _alvo_crm(e)
        if alvo:
            break
    if not alvo:
        frappe.delete_doc("Communication", doc.name, ignore_permissions=True, force=True)
        return
    valores = {"reference_doctype": alvo[0], "reference_name": alvo[1]}
    if nivel == "so_eu" and dono:
        valores["orbit_privado_de"] = dono
    frappe.db.set_value("Communication", doc.name, valores, update_modified=False)


# ── «Só para mim»: esconder dos outros ─────────────────────────────────────────────────────────────────
def _ve_tudo(user: str) -> bool:
    # 06-11-2026 (segurança das contas, plano das pendências): «só para mim» quer dizer só para o dono — nem os
    # administradores do tenant («System Manager», que o perfil Gestão traz) nem a assistência o vêem. Fica só o
    # Administrator técnico do Frappe, que ninguém usa para trabalhar.
    return user == "Administrator"


def condicao(user=None, doctype="Communication"):
    user = user or frappe.session.user
    if _ve_tudo(user) or not frappe.db.has_column(doctype, "orbit_privado_de"):
        return ""   # tenants sem os campos (ainda sem migrar) ficam como estavam
    t = f"`tab{doctype}`"
    return f"(ifnull({t}.orbit_privado_de, '') = '' or {t}.orbit_privado_de = {frappe.db.escape(user)})"


def condicao_nota(user=None):
    return condicao(user, "FCRM Note")


def pode(doc, ptype=None, user=None):
    user = user or frappe.session.user
    dono = doc.get("orbit_privado_de") if hasattr(doc, "get") else None
    if dono and dono != user and not _ve_tudo(user):
        return False
    # True e não None: o Frappe (permissions.has_controller_permissions) trata qualquer valor falso como recusa —
    # com None, ninguém abria emails nem notas (05-11, apanhado no ensaio). True só quer dizer «este gancho não
    # se opõe»; as permissões normais continuam a valer.
    return True


def _privados_de_outros(doctype: str, nomes: list) -> set:
    user = frappe.session.user
    if not nomes or _ve_tudo(user) or not frappe.db.has_column(doctype, "orbit_privado_de"):
        return set()
    return set(frappe.get_all(doctype, filters={"name": ["in", nomes], "orbit_privado_de": ["not in", ["", user]]},
                              pluck="name", ignore_permissions=True))


@frappe.whitelist()
def filtrar_actividades(name: str):
    """Substitui crm.api.activities.get_activities: o mesmo resultado sem os emails e notas privados de outros."""
    from crm.api.activities import get_activities
    r = get_activities(name)
    if not isinstance(r, (list, tuple)) or not r:
        return r
    r = list(r)
    acts = r[0] if isinstance(r[0], list) else []
    notas = r[2] if len(r) > 2 and isinstance(r[2], list) else []
    com = _privados_de_outros("Communication", [a.get("name") for a in acts if a.get("activity_type") == "communication"])
    nts = _privados_de_outros("FCRM Note", [a.get("name") for a in acts if a.get("activity_type") == "note"]
                              + [n.get("name") for n in notas])
    if com or nts:
        r[0] = [a for a in acts if not ((a.get("activity_type") == "communication" and a.get("name") in com)
                                        or (a.get("activity_type") == "note" and a.get("name") in nts))]
        if len(r) > 2:
            r[2] = [n for n in notas if n.get("name") not in nts]
    return tuple(r)
