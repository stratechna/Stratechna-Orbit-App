"""Calendário do Orbit em ICS, para o webmail o subscrever.

Nem o Frappe nem o CRM falam CalDAV ou exportam ICS — só têm integração com o
Google Calendar. Sem isto, o calendário do CRM não chega ao webmail.

O feed publica o que o utilizador tem marcado: os eventos do Frappe em que
participa e as tarefas do CRM com data. É só de leitura — quem marca continua a
marcar no CRM ou no calendário do webmail, que é o do SOGo.

Autenticação: a normal do Frappe. O SOGo subscreve um calendário remoto com
utilizador e palavra-passe no pedido, e aí usa-se a chave de API do utilizador
(Authorization: Basic api_key:api_secret), que se gera no perfil dele. Nunca uma
palavra-passe de sessão.
"""

from datetime import datetime, timedelta

import frappe
from frappe.utils import get_datetime, now_datetime


def _escapar(texto: str) -> str:
    """As regras de escape do iCalendar (RFC 5545, 3.3.11)."""
    if not texto:
        return ""
    return (
        str(texto)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _quando(valor) -> str:
    d = get_datetime(valor)
    return d.strftime("%Y%m%dT%H%M%S")


def _dobrar(linha: str) -> str:
    """O RFC manda partir linhas com mais de 75 octetos, continuando com um espaço."""
    saida, actual = [], linha
    while len(actual.encode("utf-8")) > 75:
        corte = 74
        while len(actual[:corte].encode("utf-8")) > 74:
            corte -= 1
        saida.append(actual[:corte])
        actual = " " + actual[corte:]
    saida.append(actual)
    return "\r\n".join(saida)


def _evento(uid: str, inicio, fim, resumo: str, descricao: str = "", local: str = "") -> list[str]:
    linhas = [
        "BEGIN:VEVENT",
        f"UID:{uid}@orbit.stratechna.com",
        f"DTSTAMP:{_quando(now_datetime())}",
        f"DTSTART:{_quando(inicio)}",
        f"DTEND:{_quando(fim)}",
        f"SUMMARY:{_escapar(resumo)}",
    ]
    if descricao:
        linhas.append(f"DESCRIPTION:{_escapar(descricao)}")
    if local:
        linhas.append(f"LOCATION:{_escapar(local)}")
    linhas.append("END:VEVENT")
    return linhas


@frappe.whitelist()
def calendario(dias_atras: int = 60, dias_adiante: int = 365):
    """Devolve o calendário do utilizador autenticado, em iCalendar."""
    utilizador = frappe.session.user
    if utilizador == "Guest":
        raise frappe.PermissionError("é preciso autenticação")

    inicio = now_datetime() - timedelta(days=int(dias_atras))
    fim = now_datetime() + timedelta(days=int(dias_adiante))

    linhas = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Stratechna//Orbit//PT",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Orbit",
        "X-WR-TIMEZONE:Europe/Lisbon",
    ]

    # Eventos do Frappe em que o utilizador participa
    if frappe.db.exists("DocType", "Event"):
        for e in frappe.get_all(
            "Event",
            filters={"starts_on": ["between", [inicio, fim]], "status": ["!=", "Cancelled"]},
            fields=["name", "subject", "starts_on", "ends_on", "description"],
            limit_page_length=0,
        ):
            linhas += _evento(
                f"evento-{e.name}", e.starts_on,
                e.ends_on or get_datetime(e.starts_on) + timedelta(hours=1),
                e.subject, e.description or "",
            )

    # Tarefas do CRM com data, atribuídas ao utilizador
    if frappe.db.exists("DocType", "CRM Task"):
        for t in frappe.get_all(
            "CRM Task",
            filters={
                "due_date": ["between", [inicio, fim]],
                "assigned_to": utilizador,
                "status": ["!=", "Done"],
            },
            fields=["name", "title", "due_date", "description", "reference_docname"],
            limit_page_length=0,
        ):
            ref = f"\nRegisto: {t.reference_docname}" if t.reference_docname else ""
            linhas += _evento(
                f"tarefa-{t.name}", t.due_date,
                get_datetime(t.due_date) + timedelta(minutes=30),
                f"[Tarefa] {t.title}", (t.description or "") + ref,
            )

    linhas.append("END:VCALENDAR")
    ics = "\r\n".join(_dobrar(linha) for linha in linhas) + "\r\n"

    frappe.local.response.filename = "orbit.ics"
    frappe.local.response.filecontent = ics.encode("utf-8")
    frappe.local.response.type = "download"
    frappe.local.response.display_content_as = "inline"
    frappe.local.response.content_type = "text/calendar; charset=utf-8"
