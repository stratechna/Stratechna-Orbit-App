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


# 20-11-2026: domínios de correio público — numa caixa @gmail.com, um cliente @gmail.com NÃO é «interno»
# (antes deitava-se fora tudo o que vinha de Gmail para a stratechna@gmail.com).
_PUBLICOS = {"gmail.com", "googlemail.com", "hotmail.com", "hotmail.pt", "outlook.com", "outlook.pt", "live.com",
             "live.com.pt", "msn.com", "yahoo.com", "yahoo.com.br", "yahoo.es", "icloud.com", "me.com", "mac.com",
             "sapo.pt", "netcabo.pt", "clix.pt", "zoho.com", "zohomail.eu", "proton.me", "protonmail.com", "aol.com",
             "gmx.com", "gmx.net", "gmx.de", "mail.com", "yandex.com"}


def _excluido(endereco: str, excl: list, propria: str) -> bool:
    e = (endereco or "").strip().lower()
    if not e or e == propria:
        return True
    dom = e.rsplit("@", 1)[-1]
    if dom == propria.rsplit("@", 1)[-1] and dom not in _PUBLICOS:
        return True   # internos do mesmo domínio nunca contam como «cliente»
    if dom in _dominios_casa() or e in _caixas_casa():
        return True   # 20-11: nem os de outro domínio da casa; 21-11: nem as nossas caixas de domínio público (stratechna@gmail.com)
    return any(x == e or x.lstrip("@") == dom or (x.startswith("*.") and dom.endswith(x[1:])) for x in excl)


def _enderecos(texto: str) -> list:
    return [x.lower() for x in re.findall(r"[\w.+'-]+@[\w-]+(?:\.[\w-]+)+", texto or "")]


def _alvos(email: str):
    """Todos os registos do CRM de um endereço (20-11-2026, como o HubSpot: o email aparece em todos).
    Devolve (principal, ligacoes): principal = negócio em curso › lead por converter › negócio mais recente (também
    ganho/perdido) › contacto; ligacoes = [(doctype, nome), …] com contactos, leads, negócios e organizações.
    Antes de 20-11 só se procuravam negócios pela organização e só em curso: um negócio sem organização (as compras
    das lojas) ou já ganho nunca recebia os emails, que iam para o Contacto — onde o CRM não os mostra."""
    from orbit.portal import ESTADOS_FECHADOS
    e = (email or "").strip().lower()
    if not e:
        return None, []
    contactos = frappe.get_all("Contact Email", filters={"email_id": e, "parenttype": "Contact"}, pluck="parent")
    leads = frappe.get_all("CRM Lead", filters={"email": e}, fields=["name", "converted"], order_by="modified desc")
    nomes_neg = set(frappe.get_all("CRM Deal", filters={"email": e}, pluck="name"))
    if contactos:
        nomes_neg |= set(frappe.get_all("CRM Contacts", filters={"parenttype": "CRM Deal", "contact": ["in", contactos]},
                                        pluck="parent"))
    orgs = set()
    for c in contactos:
        emp = frappe.db.get_value("Contact", c, "company_name")
        if emp and frappe.db.exists("CRM Organization", emp):
            orgs.add(emp)
        for org in frappe.get_all("Dynamic Link", filters={"parenttype": "Contact", "parent": c,
                                                             "link_doctype": "CRM Organization"}, pluck="link_name"):
            orgs.add(org)
    negocios = frappe.get_all("CRM Deal", filters={"name": ["in", list(nomes_neg)]},
                              fields=["name", "status", "organization"], order_by="modified desc") if nomes_neg else []
    orgs |= {n.organization for n in negocios if n.organization}
    if orgs:   # negócios em curso da organização (o caso de antes): também contam
        for n in frappe.get_all("CRM Deal", filters={"organization": ["in", list(orgs)], "status": ["not in", ESTADOS_FECHADOS]},
                                fields=["name", "status", "organization"], order_by="modified desc", limit=10):
            if n.name not in nomes_neg:
                negocios.append(n)
                nomes_neg.add(n.name)
    abertos = [n for n in negocios if n.status not in ESTADOS_FECHADOS]
    lead_aberto = next((l for l in leads if not l.converted), None)
    if abertos:
        principal = ("CRM Deal", abertos[0].name)
    elif lead_aberto:
        principal = ("CRM Lead", lead_aberto.name)
    elif negocios:
        principal = ("CRM Deal", negocios[0].name)
    elif leads:
        principal = ("CRM Lead", leads[0].name)
    elif contactos:
        principal = ("Contact", contactos[0])
    else:
        return None, []
    ligacoes = [("CRM Deal", n.name) for n in negocios] + [("CRM Lead", l.name) for l in leads] \
        + [("Contact", c) for c in contactos] + [("CRM Organization", o) for o in sorted(orgs)]
    return principal, [x for x in dict.fromkeys(ligacoes) if x != principal]


def _ligar(nome: str, ligacoes: list) -> None:
    """Timeline Links (Communication Link) — o mecanismo do Frappe que põe o email no separador «E-mails» de cada
    registo (frappe.desk.form.load.get_communication_data junta-os). Sem gravar o documento (os ganchos não voltam)."""
    ja = set(frappe.get_all("Communication Link", filters={"parent": nome, "parenttype": "Communication"},
                            fields=["link_doctype", "link_name"], as_list=True))
    idx = len(ja)
    data = frappe.db.get_value("Communication", nome, "communication_date")
    for dt, dn in ligacoes:
        if (dt, dn) in ja:
            continue
        idx += 1
        frappe.get_doc({"doctype": "Communication Link", "parent": nome, "parenttype": "Communication",
                        "parentfield": "timeline_links", "idx": idx, "link_doctype": dt, "link_name": dn,
                        "link_title": dn, "communication_date": data}).db_insert()


def _outros(doc, propria: str) -> list:
    remetente = (_enderecos(doc.sender) or [""])[0]
    return [remetente] if remetente != propria else _enderecos(f"{doc.recipients or ''},{doc.cc or ''}")


def filtrar(doc, method=None):
    """Gancho after_insert de Communication: só nos emails lidos por uma conta «Orbit CRM · …»."""
    if doc.communication_medium != "Email" or not doc.email_account:
        return
    nivel, dono, excl, propria = frappe.db.get_value(
        "Email Account", doc.email_account, ["orbit_registo_crm", "orbit_dono", "orbit_exclusoes", "email_id"]) \
        if frappe.db.has_column("Email Account", "orbit_registo_crm") else (None, None, None, None)
    if nivel not in NIVEIS:
        return
    propria = (propria or "").lower()
    lista = [x for x in (excl or "").splitlines() if x.strip()]
    principal, ligacoes = None, []
    for e in _outros(doc, propria):
        if _excluido(e, lista, propria):
            continue
        p, l = _alvos(e)
        if p and not principal:
            principal = p
        ligacoes += l + ([p] if p else [])
    if not principal and not doc.reference_doctype:
        # 20-11-2026 (Vítor: «devem ser registados todos os emails e criados os respetivos leads; por defeito entram
        # todos»): quem ainda não está no CRM ganha uma lead — salvo robôs e newsletters (ver _robo).
        for e in _outros(doc, propria):
            if _excluido(e, lista, propria) or _robo(e, doc):
                continue
            lead = _criar_lead(e, doc, dono if nivel == "so_eu" else None)
            if lead:
                principal = ("CRM Lead", lead)
                break
    if not principal:
        if not doc.reference_doctype:
            # 20-11-2026: apagar só depois de o Frappe acabar (o receive() faz reload() a seguir ao insert e falhava
            # com «Comunicação … não foi encontrado» — ~70 erros por dia desde 06-11).
            frappe.enqueue("orbit.emails_crm._apagar", queue="short", enqueue_after_commit=True, nome=doc.name)
        return
    valores = {}
    if not doc.reference_doctype:
        valores = {"reference_doctype": principal[0], "reference_name": principal[1]}
    if nivel == "so_eu" and dono:
        valores["orbit_privado_de"] = dono
    if valores:
        frappe.db.set_value("Communication", doc.name, valores, update_modified=False)
    atual = (doc.reference_doctype, doc.reference_name) if doc.reference_doctype else principal
    _ligar(doc.name, [x for x in dict.fromkeys(ligacoes) if x != atual])


_ROBOS = re.compile(r"^(no[-_.]?reply|do[-_.]?not[-_.]?reply|donotreply|mailer[-_.]?daemon|postmaster|bounces?|bounce[-+].*|"
                    r"notifications?|notificacoes|notify|alerts?|newsletter|news|marketing|mailing|automated|system|"
                    r"support[-_.]?noreply|billing[-_.]?noreply|calendar[-_.]?notification|dmarc.*|reports?)(@|$)", re.I)
_ROBOS_DOM = ("amazonses.com", "sendgrid.net", "mailchimpapp.net", "mcsv.net", "bounces.google.com", "facebookmail.com",
              "linkedin.com", "mail.instagram.com", "accounts.google.com", "noreply.github.com", "zoho.eu", "zoho.com")
_ANULAR = re.compile(r"(unsubscribe|anular\s+(a\s+)?subscri|cancelar\s+(a\s+)?subscri|deixar\s+de\s+receber|darse\s+de\s+baja|"
                     r"se\s+d[ée]sabonner|manage\s+(your\s+)?(email\s+)?(preferences|subscription)|gerir\s+prefer[êe]ncias|"
                     r"view\s+(it\s+|this\s+email\s+)?in\s+(your\s+)?browser|ver\s+(este\s+e-?mail\s+)?no\s+(seu\s+)?navegador)", re.I)
# (20-11) frases de rodapé como «este email foi enviado para…» ou «não responda» também aparecem nos emails de empresas
# reais (avisos legais) — não servem para distinguir newsletters.
# remetentes de fornecedores de software/serviços que só mandam avisos e marketing
_ROBOS_LOCAL = re.compile(r"^(support|suporte|help|hello|hi|team|equipa|news|noticias|updates?|info-?mail|mail|mailer|"
                          r"marcomms|communications?|comunicacao|promo(tions?|cao)?|offers?|ofertas|campaigns?|billing|invoices?|"
                          r"receipts?|accounts?|security|seguranca|feedback|survey|inquerito)@", re.I)
_SOFTWARE = ("zohobooks.com", "zoho.com", "zoho.eu", "anthropic.com", "openai.com", "google.com", "microsoft.com", "apple.com",
             "hubspot.com", "mailchimp.com", "stripe.com", "paypal.com", "atlassian.com", "slack.com", "notion.so", "canva.com",
             "github.com", "gitlab.com", "hetzner.com", "cloudflare.com", "godaddy.com", "openprovider.com", "wordpress.com",
             "wix.com", "shopify.com", "meta.com", "facebook.com", "linkedin.com", "x.com", "twitter.com", "tiktok.com")


def _dominios_casa() -> set:
    """Domínios da casa neste tenant: os de correio configurados e os dos utilizadores — nunca são clientes."""
    chave = "orbit:emails_crm:dominios_casa"
    d = frappe.cache.get_value(chave)
    if d is None:
        d = {x.lower() for x in frappe.get_all("Email Domain", pluck="domain_name") if x}
        d |= {u.split("@")[-1].lower() for u in frappe.get_all("User", filters={"user_type": "System User", "enabled": 1}, pluck="name")
              if "@" in u}
        d -= _PUBLICOS
        frappe.cache.set_value(chave, list(d), expires_in_sec=3600)
    return set(d)


def _caixas_casa() -> set:
    """Endereços das caixas ligadas a este tenant (também as de domínio público, ex.: stratechna@gmail.com)."""
    chave = "orbit:emails_crm:caixas_casa"
    d = frappe.cache.get_value(chave)
    if d is None:
        d = [x.strip().lower() for x in frappe.get_all("Email Account", pluck="email_id") if x and "@" in x]
        frappe.cache.set_value(chave, d, expires_in_sec=3600)
    return set(d)


def _endereco_da_casa(e: str) -> bool:
    e = (e or "").strip().lower()
    return "@" in e and (e.rsplit("@", 1)[-1] in _dominios_casa() or e in _caixas_casa())


_NOREPLY = re.compile(r"(^|[-_.+])(no[-_.]?reply|do[-_.]?not[-_.]?reply|donotreply|mailer[-_.]?daemon|bounces?)([-_.+]|@)", re.I)


def _robo(endereco: str, doc) -> bool:
    """Remetentes automáticos e newsletters não criam leads (o email também não fica: não há a quem o ligar)."""
    e = (endereco or "").lower()
    if not e or _ROBOS.match(e) or _NOREPLY.search(e.split("@")[0] + "@"):
        return True
    dom = e.rsplit("@", 1)[-1]
    if any(dom == d or dom.endswith("." + d) for d in _ROBOS_DOM):
        return True
    if dom in _dominios_casa():
        return True
    if _ROBOS_LOCAL.match(e) and any(dom == d or dom.endswith("." + d) for d in _SOFTWARE):
        return True

    if doc.sent_or_received == "Received" and _ANULAR.search(doc.content or ""):
        return True
    return False


def _criar_lead(endereco: str, doc, dono: str = None):
    e = endereco.strip().lower()
    ja = frappe.db.get_value("CRM Lead", {"email": e})
    if ja:
        return ja
    nome = ""
    if doc.sent_or_received == "Received" and doc.sender_full_name and "@" not in doc.sender_full_name:
        nome = doc.sender_full_name.strip()
    if not nome:
        local = e.split("@")[0]
        nome = " ".join(p.capitalize() for p in re.split(r"[._\-]+", local) if p and not p.isdigit()) or local
    partes = nome.split()
    dom = e.rsplit("@", 1)[-1]
    fonte = "Caixa de correio"
    if not frappe.db.exists("CRM Lead Source", fonte):
        frappe.get_doc({"doctype": "CRM Lead Source", "source_name": fonte}).insert(ignore_permissions=True)
    try:
        lead = frappe.get_doc({"doctype": "CRM Lead", "first_name": partes[0][:140], "last_name": " ".join(partes[1:])[:140] or None,
                               "email": e, "source": fonte, "lead_owner": dono,
                               "website": None if dom in _PUBLICOS else dom}).insert(ignore_permissions=True)
        return lead.name
    except frappe.DuplicateEntryError:
        return frappe.db.get_value("CRM Lead", {"email": e})
    except Exception:  # noqa: BLE001 — sem lead, o email segue o caminho de antes
        frappe.log_error(title=f"Orbit CRM: lead a partir de {e}")
        return None


# ── Apagar uma lead apaga o que é dela (20-11-2026) ─────────────────────────────────────────────────────
def _registo_da_casa(dt: str, nome: str) -> bool:
    """Contactos/empresas que são a própria casa (as nossas caixas como contactos, a Stratechna, a Webgate…).

    21-11: as caixas ligadas contam mesmo em domínio público, e uma organização sem site nem email geral
    é da casa quando todos os seus contactos (pelo menos um) são da casa."""
    casa = _dominios_casa()
    if dt == "Contact":
        ems = [e for e in frappe.get_all("Contact Email", filters={"parent": nome, "parenttype": "Contact"},
                                         pluck="email_id") if e and "@" in e]
        return bool(ems) and all(_endereco_da_casa(e) for e in ems)
    if dt == "CRM Organization":
        o = frappe.db.get_value("CRM Organization", nome, ["website", "email_geral"], as_dict=True) or {}
        doms = {re.sub(r"^https?://(www\.)?", "", (o.get("website") or "").lower()).split("/")[0],
                (o.get("email_geral") or "").split("@")[-1].lower()}
        if doms & casa:
            return True
        if o.get("website") or o.get("email_geral"):
            return False   # tem site/email de fora: é um cliente
        contactos = frappe.get_all("Contact", filters={"company_name": nome}, pluck="name", limit=50)
        return bool(contactos) and all(_registo_da_casa("Contact", c) for c in contactos)
    return False


def lead_apagada(doc, method=None):
    """on_trash de CRM Lead: emails, notas, tarefas, chamadas e reuniões da lead saem com ela — excepto o que também
    está ligado a outro registo (um negócio que nasceu da lead, um contacto), que passa para esse registo."""
    nome = doc.name
    comms = set(frappe.get_all("Communication", filters={"reference_doctype": "CRM Lead", "reference_name": nome}, pluck="name"))
    comms |= set(frappe.get_all("Communication Link", filters={"parenttype": "Communication", "link_doctype": "CRM Lead",
                                                              "link_name": nome}, pluck="parent"))
    for c in comms:
        outros = [o for o in frappe.get_all("Communication Link", filters={"parent": c, "parenttype": "Communication",
                                                                           "link_doctype": ["!=", "CRM Lead"]}, fields=["link_doctype", "link_name"])
                  if not _registo_da_casa(o.link_doctype, o.link_name)]
        frappe.db.delete("Communication Link", {"parent": c, "link_doctype": "CRM Lead", "link_name": nome})
        if outros:
            ref = frappe.db.get_value("Communication", c, ["reference_doctype", "reference_name"])
            if ref and ref[0] == "CRM Lead" and ref[1] == nome:
                frappe.db.set_value("Communication", c, {"reference_doctype": outros[0].link_doctype,
                                                         "reference_name": outros[0].link_name}, update_modified=False)
        else:
            frappe.delete_doc("Communication", c, ignore_permissions=True, force=True)
    for dt in ("FCRM Note", "CRM Task", "CRM Call Log"):
        if frappe.db.exists("DocType", dt):
            for n in frappe.get_all(dt, filters={"reference_doctype": "CRM Lead", "reference_docname": nome}, pluck="name"):
                frappe.delete_doc(dt, n, ignore_permissions=True, force=True)
    for n in frappe.get_all("Event", filters={"reference_doctype": "CRM Lead", "reference_docname": nome}, pluck="name"):
        frappe.delete_doc("Event", n, ignore_permissions=True, force=True)


def _apagar(nome: str):
    if frappe.db.exists("Communication", nome) and not frappe.db.get_value("Communication", nome, "reference_doctype"):
        frappe.delete_doc("Communication", nome, ignore_permissions=True, force=True)
        frappe.db.commit()


# ── Recuperar o passado (20-11-2026) ────────────────────────────────────────────────────────────────────
# Uma caixa ligada só guarda o que chega com a pessoa JÁ no CRM; o resto apaga-se. Quando o contacto, a lead ou o
# negócio nasce depois (as compras das lojas, um contacto criado à mão), procura-se nas caixas ligadas o que se
# trocou com esse endereço e entra pelo caminho normal do Frappe (InboundMail → Communication → `filtrar`).
_DIAS = 365
_MAX_POR_PASTA = 300


def _imap_da_conta(acc):
    if acc.email_server:
        servidor, porta, ssl = acc.email_server, int(acc.incoming_port or 993), bool(acc.use_ssl)
    else:
        d = frappe.get_doc("Email Domain", acc.domain)
        servidor, porta, ssl = d.email_server, int(d.incoming_port or 993), bool(d.use_ssl)
    m = imaplib.IMAP4_SSL(servidor, porta, timeout=60) if ssl else imaplib.IMAP4(servidor, porta, timeout=60)
    m.login(acc.login_id or acc.email_id, acc.get_password("password"))
    return m


def recuperar(email: str, dias: int = _DIAS, simular: int = 0) -> dict:
    """Traz das caixas ligadas ao CRM os emails trocados com `email` nos últimos `dias` (sem repetir: o Frappe
    reconhece o Message-ID). `simular=1` só conta."""
    from email.utils import formatdate
    from frappe.email.receive import InboundMail, SentEmailInInboxError
    e = (email or "").strip().lower()
    if "@" not in e or not re.fullmatch(r"[\w.+'-]+@[\w-]+(\.[\w-]+)+", e):
        return {"ok": False, "erro": "endereço inválido"}
    if not _alvos(e)[0]:
        return {"ok": True, "contas": {}, "nota": "sem registo no CRM"}
    desde = frappe.utils.add_days(frappe.utils.nowdate(), -int(dias))
    desde_imap = frappe.utils.getdate(desde).strftime("%d-%b-%Y")
    res = {}
    for nome in frappe.get_all("Email Account", filters={"enable_incoming": 1,
                                                         "orbit_registo_crm": ["in", list(NIVEIS)]}, pluck="name"):
        acc = frappe.get_doc("Email Account", nome)
        propria = (acc.email_id or "").lower()
        if _excluido(e, [x for x in (acc.orbit_exclusoes or "").splitlines() if x.strip()], propria):
            continue
        conta = {"encontrados": 0, "novos": 0, "erros": 0}
        try:
            m = _imap_da_conta(acc)
        except Exception as ex:  # noqa: BLE001
            res[nome] = {"erro": str(ex)[:150]}
            continue
        try:
            for pasta in acc.imap_folder:
                if m.select(f'"{pasta.folder_name}"', readonly=True)[0] != "OK":
                    continue
                _, r = m.uid("SEARCH", None, f'SINCE {desde_imap} OR OR FROM "{e}" TO "{e}" CC "{e}"')
                uids = (r[0] or b"").split()[-_MAX_POR_PASTA:]
                conta["encontrados"] += len(uids)
                if simular:
                    continue
                for uid in uids:
                    try:
                        _, dados = m.uid("FETCH", uid, "(RFC822)")
                        bruto = next((p[1] for p in dados if isinstance(p, tuple)), None)
                        if not bruto:
                            continue
                        mail = InboundMail(bruto, acc, uid=None, seen_status=1, append_to=pasta.append_to)
                        if mail.message_id and frappe.db.exists("Communication", {"message_id": mail.message_id}):
                            c = frappe.db.get_value("Communication", {"message_id": mail.message_id}, "name")
                            filtrar(frappe.get_doc("Communication", c))   # já existia: só acerta as ligações
                        else:
                            mail.process()
                            conta["novos"] += 1
                        frappe.db.commit()
                    except SentEmailInInboxError:
                        frappe.db.rollback()
                    except Exception:  # noqa: BLE001
                        frappe.db.rollback()
                        conta["erros"] += 1
                        frappe.log_error(title=f"Orbit CRM: recuperar {e} em {nome}")
        finally:
            try:
                m.logout()
            except Exception:
                pass
        res[nome] = conta
    return {"ok": True, "contas": res}


def _pedir_recuperacao(emails) -> None:
    for e in {(x or "").strip().lower() for x in emails if x and "@" in x}:
        chave = f"orbit:emails_crm:recuperado:{e}"
        if frappe.cache.get_value(chave):
            continue
        frappe.cache.set_value(chave, 1, expires_in_sec=7 * 86400)
        frappe.enqueue("orbit.emails_crm.recuperar", queue="long", timeout=1800, enqueue_after_commit=True,
                       job_id=f"orbit-recuperar-{e}", deduplicate=True, email=e)


def ao_gravar_registo(doc, method=None):
    """Gancho de Contact, CRM Lead e CRM Deal: um endereço novo no CRM → ir buscar o que já se trocou com ele.
    Desligado durante importações (`frappe.flags.orbit_sem_recuperar`): mil contactos não podem ser mil pesquisas."""
    if frappe.flags.get("orbit_sem_recuperar"):
        return
    if not frappe.db.exists("Email Account", {"enable_incoming": 1, "orbit_registo_crm": ["in", list(NIVEIS)]}):
        return
    if doc.doctype == "Contact":
        emails = [r.email_id for r in (doc.get("email_ids") or [])]
    elif doc.doctype == "CRM Deal":
        emails = [doc.get("email")] + [r.get("email") for r in (doc.get("contacts") or [])]
    else:
        emails = [doc.get("email")]
    _pedir_recuperacao(emails)


@frappe.whitelist()
def recuperar_agora(email: str, dias: int = _DIAS):
    """Botão «Procurar emails antigos» (interface nova) — quem pode ler o registo pode pedir."""
    p, _ = _alvos(email)
    if not p or not frappe.has_permission(p[0], "read", p[1]):
        frappe.throw("Sem permissão", frappe.PermissionError)
    frappe.cache.delete_value(f"orbit:emails_crm:recuperado:{(email or '').strip().lower()}")
    _pedir_recuperacao([email])
    return {"ok": True}


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


# ── Responder pelo CRM (E8 do plano dos emails; interface /orbit, 20-11-2026) ─────────────────────────────
# A conta «Orbit CRM · <caixa>» ganha a saída: o SMTP do mesmo servidor com a mesma palavra-passe de aplicação, e o
# Frappe guarda a resposta nos Enviados da caixa (aparece no Orbit Mail e no telemóvel como as outras).
_SMTP_FORA = {"imap.gmail.com": ("smtp.gmail.com", 587), "imap.googlemail.com": ("smtp.gmail.com", 587),
              "imap.zoho.eu": ("smtp.zoho.eu", 587), "imap.zoho.com": ("smtp.zoho.com", 587)}


def preparar_saida(nome_conta: str):
    """Liga a saída da conta (idempotente). O Frappe confirma o SMTP ao gravar — erro claro se a palavra-passe falhar."""
    acc = frappe.get_doc("Email Account", nome_conta)
    if acc.orbit_registo_crm not in NIVEIS:
        frappe.throw("Esta caixa não está ligada ao CRM.")
    if acc.enable_outgoing and acc.smtp_server:
        if not acc.track_email_status:   # H9: saber se o email foi aberto (pixel do próprio Frappe)
            frappe.db.set_value("Email Account", acc.name, "track_email_status", 1, update_modified=False)
            acc.track_email_status = 1
        return acc
    if acc.email_server and not acc.domain:
        smtp = _SMTP_FORA.get((acc.email_server or "").lower())
        if not smtp:
            frappe.throw(f"Não sei o servidor de envio de {acc.email_server}.")
        servidor, porta, tls, ssl = smtp[0], smtp[1], 1, 0
    else:
        d = frappe.get_doc("Email Domain", acc.domain)
        servidor, porta = d.smtp_server, int(d.smtp_port or 587)
        tls, ssl = int(d.use_tls or 0), int(d.get("use_ssl_for_outgoing") or 0)
    acc.update({"enable_outgoing": 1, "default_outgoing": 0, "smtp_server": servidor, "smtp_port": str(porta),
                "use_tls": tls, "use_ssl_for_outgoing": ssl, "append_emails_to_sent_folder": 1,
                "always_use_account_email_id_as_sender": 1, "send_unsubscribe_message": 0,
                "track_email_status": 1, "add_signature": 1 if acc.get("signature") else 0})
    if acc.meta.has_field("login_id_is_different") and not acc.get("login_id"):
        acc.login_id_is_different = 0
    acc.save(ignore_permissions=True)
    frappe.db.commit()
    return acc


def pode_responder(nome_conta: str, user: str = None) -> bool:
    """«Só para mim»: só o dono. Partilhadas: quem vê a conversa (a permissão de leitura já foi verificada)."""
    user = user or frappe.session.user
    nivel, dono = frappe.db.get_value("Email Account", nome_conta, ["orbit_registo_crm", "orbit_dono"]) or (None, None)
    if nivel not in NIVEIS:
        return False
    return nivel != "so_eu" or dono == user
