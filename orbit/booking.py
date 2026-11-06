"""O Stratechna Booking a escrever no CRM do tenant (O1, §20.1 do plano das marcações; I1 do plano das pendências).

Chega pela ponte do portal (`agenda-evento <slug> <json_b64>` no Apps02), uma marcação de cada vez, com o estado
actual. Tudo aqui é idempotente pela referência da marcação: a ponte repete quando a rede falha.

| Booking | Orbit |
|---|---|
| cliente final | **Contact** (ligado pelo email ou telemóvel; criado se não existir) |
| marcação | **Event** na agenda do profissional (orbit.marcacao.criar/reagendar/cancelar) + nota no contacto |
| pagamento confirmado | **CRM Deal** ganho com o valor pago e a marca do negócio; o 2.º pagamento actualiza o mesmo; reembolso total → perdido |

As reuniões da própria Stratechna (§21) não passam por aqui: já têm o seu caminho (`orbit.marcacao`, lead no CRM).
"""
from __future__ import annotations

import frappe

from orbit import marcacao

CAMPO_DEAL = "orbit_referencia_booking"


def garantir() -> None:
    """after_migrate: o campo que liga um negócio do CRM à marcação que o pagou."""
    if not frappe.db.exists("DocType", "CRM Deal"):
        return
    if not frappe.db.exists("Custom Field", {"dt": "CRM Deal", "fieldname": CAMPO_DEAL}):
        from frappe.custom.doctype.custom_field.custom_field import create_custom_field
        create_custom_field("CRM Deal", {"fieldname": CAMPO_DEAL, "fieldtype": "Data", "label": "Marcação (Booking)",
                                         "read_only": 1, "no_copy": 1, "search_index": 1, "module": "Orbit",
                                         "insert_after": "source"})


def _limpo(v) -> str:
    return (str(v) if v is not None else "").strip()


def _contacto(c: dict) -> str | None:
    email = _limpo(c.get("email")).lower()
    tel = _limpo(c.get("telemovel"))
    nome = None
    if email:
        nome = frappe.db.get_value("Contact Email", {"email_id": email}, "parent")
    if not nome and tel:
        nome = frappe.db.get_value("Contact Phone", {"phone": tel}, "parent") or \
            frappe.db.get_value("Contact", {"mobile_no": tel}, "name")
    if nome:
        return nome
    if not email and not tel:
        return None
    partes = (_limpo(c.get("nome")) or email.split("@")[0] or tel).split(" ", 1)
    d = frappe.get_doc({"doctype": "Contact", "first_name": partes[0][:100],
                        "last_name": partes[1][:100] if len(partes) > 1 else "",
                        "email_ids": [{"email_id": email, "is_primary": 1}] if email else [],
                        "phone_nos": [{"phone": tel, "is_primary_mobile_no": 1}] if tel else []})
    d.insert(ignore_permissions=True)
    return d.name


def _nota(contacto: str, texto: str) -> None:
    """Uma linha na história do contacto, uma só vez por texto (a ponte pode repetir)."""
    if not contacto or frappe.db.exists("Comment", {"reference_doctype": "Contact", "reference_name": contacto,
                                                    "content": texto}):
        return
    frappe.get_doc({"doctype": "Comment", "comment_type": "Comment", "reference_doctype": "Contact",
                    "reference_name": contacto, "content": texto}).insert(ignore_permissions=True)


def _evento(p: dict, contacto_email: str) -> str | None:
    ref = p["referencia"]
    activa = bool(p.get("activa"))
    existe = frappe.db.get_value("Event", {"custom_referencia_marcacao": ref}, ["name", "starts_on", "ends_on",
                                                                                  "status"], as_dict=True)
    if not activa:
        if existe and existe.status != "Cancelled":
            marcacao.cancelar(ref, p.get("motivo") or "Anulada no Booking")
        return existe.name if existe else None
    if existe:
        if str(existe.starts_on)[:16] != p["inicio"][:16] or str(existe.ends_on)[:16] != p["fim"][:16] \
                or existe.status == "Cancelled":
            marcacao.reagendar(ref, p["inicio"], p["fim"])
        return existe.name
    anfitriao = _limpo(p.get("profissional_email")).lower()
    if not anfitriao or not frappe.db.get_value("User", {"name": anfitriao, "enabled": 1}):
        return None   # o profissional não é utilizador deste Orbit: fica só a nota no contacto
    titulo = f"{_limpo(p.get('servicos')) or 'Marcação'} — {_limpo((p.get('cliente') or {}).get('nome'))}".strip(" —")
    linhas = [f"Marcação {ref} no Stratechna Booking ({_limpo(p.get('negocio'))})"]
    c = p.get("cliente") or {}
    if c.get("telemovel"):
        linhas.append(f"Telemóvel: {c['telemovel']}")
    if c.get("email"):
        linhas.append(f"Email: {c['email']}")
    r = marcacao.criar(anfitriao=anfitriao, assunto=titulo[:140], inicio=p["inicio"], fim=p["fim"],
                       descricao="\n".join(linhas), local=_limpo(p.get("local")) or None,
                       convidado=contacto_email or None, referencia=ref)
    return r.get("evento")


def _deal(p: dict, contacto: str | None) -> str | None:
    pago = round(float(p.get("valor_pago") or 0), 2)
    ref = p["referencia"]
    nome = frappe.db.get_value("CRM Deal", {CAMPO_DEAL: ref}, "name")
    if not nome and pago <= 0:
        return None
    perdido = bool(p.get("reembolsado")) and pago <= 0
    estado = "Lost" if perdido else "Won"
    if nome:
        d = frappe.get_doc("CRM Deal", nome)
        mudou = False
        if d.status != estado:
            d.status, mudou = estado, True
            if perdido:
                # o CRM exige um motivo para perder um negócio
                if d.meta.has_field("lost_reason") and frappe.db.exists("CRM Lost Reason", "Other"):
                    d.lost_reason = "Other"
                if d.meta.has_field("lost_notes"):
                    d.lost_notes = f"Reembolso total da marcação {ref} no Stratechna Booking."
        if pago > 0 and float(d.deal_value or 0) != pago:
            d.deal_value, mudou = pago, True
        if mudou:
            d.save(ignore_permissions=True)
        return nome
    c = p.get("cliente") or {}
    partes = (_limpo(c.get("nome")) or "Cliente").split(" ", 1)
    valores = {"doctype": "CRM Deal", "status": estado, "deal_value": pago, "currency": p.get("moeda") or "EUR",
               "probability": 100, CAMPO_DEAL: ref, "first_name": partes[0][:100],
               "last_name": partes[1][:100] if len(partes) > 1 else "", "email": _limpo(c.get("email")).lower(),
               "mobile_no": _limpo(c.get("telemovel")), "closed_date": frappe.utils.today()}
    marca = _limpo(p.get("marca"))
    if marca and frappe.db.exists("Brand", marca):
        valores["marca"] = marca
    if frappe.db.exists("CRM Lead Source", "Booking"):
        valores["source"] = "Booking"
    if contacto:
        valores["contacts"] = [{"contact": contacto, "is_primary": 1}]
    meta = frappe.get_meta("CRM Deal")
    d = frappe.get_doc({k: v for k, v in valores.items() if k in ("doctype", "contacts") or meta.has_field(k)})
    d.insert(ignore_permissions=True)
    return d.name


def registar(p: dict) -> dict:
    """Uma marcação do Booking no CRM. `p`: referencia, activa, estado, inicio/fim (hora local do tenant,
    AAAA-MM-DD HH:MM:SS), negocio, marca, servicos, profissional_email, local, cliente{nome,email,telemovel},
    valor_pago (euros), reembolsado, moeda, motivo."""
    if not _limpo(p.get("referencia")):
        return {"ok": False, "erro": "sem referência"}
    c = p.get("cliente") or {}
    contacto = _contacto(c)
    evento = _evento(p, _limpo(c.get("email")).lower())
    deal = _deal(p, contacto)
    if contacto:
        quando = p["inicio"][:16].replace("T", " ")
        estado = "anulada" if not p.get("activa") else ("paga" if float(p.get("valor_pago") or 0) > 0 else "marcada")
        _nota(contacto, f"Booking {p['referencia']} — {_limpo(p.get('servicos'))} a {quando}"
                        f"{' com ' + _limpo(p.get('profissional_nome')) if p.get('profissional_nome') else ''}: {estado}"
                        f"{' (' + format(float(p.get('valor_pago') or 0), '.2f') + ' €)' if estado == 'paga' else ''}")
    frappe.db.commit()
    return {"ok": True, "contacto": contacto, "evento": evento, "deal": deal}
