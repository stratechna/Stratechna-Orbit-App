"""A actividade nas fichas de contacto e de organização do CRM.

O CRM do Orbit (frappe/crm) só mostra a linha de actividade nos leads e nos
negócios. Os emails, as chamadas, as notas, as tarefas, os tickets do Desk e as
reuniões ligados a um contacto ou a uma organização existem na base de dados,
mas a ficha do contacto e a da organização não os mostravam (19-11-2026).

Fica um botão «Actividade (N)» no cabeçalho das duas fichas, por CRM Form Script
(configuração do próprio CRM — nenhum ficheiro do CRM é alterado), que substitui
o antigo botão «Notas» (notas_crm.py, 16-11). Abre uma janela com tudo, da mais
recente para a mais antiga, com filtros por tipo.

O que conta como «do contacto»:
* ligado directamente ao contacto (referência, ligações da linha de tempo dos
  emails, participantes das reuniões, campo `contact` dos tickets);
* ligado aos negócios em que o contacto entra (campo `contact` ou tabela de
  contactos) e aos leads com o mesmo endereço de email;
* tickets do Desk abertos a partir de um dos endereços do contacto.
Na organização junta-se o da organização, o dos contactos dela e o dos negócios
dela.

Tudo se lê com `frappe.get_list`, ou seja, com as permissões de quem abre a
ficha — incluindo o «só para mim» dos emails e das notas (`orbit_privado_de`,
emails_crm.py). Quem não tem acesso ao Desk simplesmente não vê os tickets.

`garantir()` corre no after_migrate/after_install: cria ou repõe os dois
scripts em cada tenant e apaga os do antigo botão «Notas».
"""

import re
from html import unescape

import frappe
from frappe.utils import cstr, get_datetime

_LIMITE = 300          # por tipo
_TEXTO_MAX = 6000      # caracteres de um email mostrados na janela

_TIPOS_DOC = ("Contact", "CRM Organization")
_ANTIGOS = ("Orbit · Notas da organização", "Orbit · Notas do contacto")


# ---------------------------------------------------------------- leitura

def _lista(doctype, **kw):
    """get_list com as permissões do utilizador; sem acesso ao tipo → lista vazia."""
    if not frappe.db.exists("DocType", doctype):
        return []
    try:
        return frappe.get_list(doctype, limit_page_length=_LIMITE, **kw)
    except frappe.PermissionError:
        return []


def _texto(html, maximo=_TEXTO_MAX):
    """HTML → texto simples, depressa (o html2text demorava segundos com as newsletters)."""
    t = cstr(html or "")[: maximo * 8]
    t = re.sub(r"(?is)<(style|script|head)\b.*?</\1>", " ", t)
    t = re.sub(r"(?i)<br\s*/?>|</(p|div|li|tr|h[1-6]|blockquote)>", "\n", t)
    t = unescape(re.sub(r"<[^>]+>", " ", t))
    t = re.sub(r"[ \t\xa0]+", " ", t)
    t = re.sub(r"\s*\n\s*(\n\s*)+", "\n\n", t).strip()
    return (t[:maximo] + "…") if len(t) > maximo else t


def _quando(v):
    return cstr(get_datetime(v)) if v else ""


def _ambito(doctype, name):
    """Os contactos, endereços, organização, negócios e leads que pertencem à ficha."""
    contactos = [name] if doctype == "Contact" else [
        c.parent for c in frappe.get_all(
            "Dynamic Link", fields=["parent"],
            filters={"parenttype": "Contact", "link_doctype": "CRM Organization", "link_name": name})]
    contactos = sorted(set(contactos))

    emails = set()
    if contactos:
        for r in frappe.get_all("Contact Email", fields=["email_id"],
                                filters={"parenttype": "Contact", "parent": ["in", contactos]}):
            if r.email_id:
                emails.add(r.email_id.strip().lower())
        for r in frappe.get_all("Contact", fields=["email_id"], filters={"name": ["in", contactos]}):
            if r.email_id:
                emails.add(r.email_id.strip().lower())

    negocios = {}
    filtros_neg = []
    if contactos:
        filtros_neg.append({"contact": ["in", contactos]})
        for r in frappe.get_all("CRM Contacts", fields=["parent"],
                                filters={"parenttype": "CRM Deal", "contact": ["in", contactos]}):
            filtros_neg.append({"name": r.parent})
    if doctype == "CRM Organization":
        filtros_neg.append({"organization": name})
    vistos = set()
    for f in filtros_neg:
        for d in _lista("CRM Deal", filters=f, fields=["name", "organization", "lead_name", "status"]):
            if d.name not in vistos:
                vistos.add(d.name)
                negocios[d.name] = d

    leads = {}
    if emails:
        for l in _lista("CRM Lead", filters={"email": ["in", list(emails)]},
                        fields=["name", "lead_name", "organization", "status"]):
            leads[l.name] = l

    return {"contactos": contactos, "emails": sorted(emails), "negocios": negocios, "leads": leads}


def _origens(doctype, name, amb):
    """(doctype, nome) → texto curto e ligação, para dizer de onde vem cada linha."""
    o = {}
    nomes_contacto = {c.name: c.full_name or c.name for c in frappe.get_all(
        "Contact", fields=["name", "full_name"], filters={"name": ["in", amb["contactos"] or [""]]})}
    for c, n in nomes_contacto.items():
        o[("Contact", c)] = ("" if (doctype == "Contact" and c == name) else f"Contacto · {n}",
                             f"/crm/contacts/{c}")
    if doctype == "CRM Organization":
        o[("CRM Organization", name)] = ("", f"/crm/organizations/{name}")
    for n, d in amb["negocios"].items():
        o[("CRM Deal", n)] = (f"Negócio · {d.organization or d.lead_name or n}", f"/crm/deals/{n}")
    for n, l in amb["leads"].items():
        o[("CRM Lead", n)] = (f"Lead · {l.lead_name or l.organization or n}", f"/crm/leads/{n}")
    return o


def _refs(doctype, name, amb):
    """Pares (doctype, [nomes]) a que uma actividade pode estar ligada por referência."""
    r = [("Contact", amb["contactos"]), ("CRM Deal", list(amb["negocios"])), ("CRM Lead", list(amb["leads"]))]
    if doctype == "CRM Organization":
        r.append(("CRM Organization", [name]))
    return [(dt, ns) for dt, ns in r if ns]


def _juntar(destino, linhas):
    for l in linhas:
        destino.setdefault(l.name, l)


@frappe.whitelist()
def listar(doctype, name):
    """Toda a actividade de um contacto ou de uma organização, da mais recente para a mais antiga."""
    if doctype not in _TIPOS_DOC:
        frappe.throw("Só contactos e organizações.")
    frappe.get_doc(doctype, name).check_permission("read")

    amb = _ambito(doctype, name)
    refs = _refs(doctype, name, amb)
    origens = _origens(doctype, name, amb)
    sem = ("", "")

    def origem(dt, dn):
        return origens.get((dt, dn), sem)

    itens = []

    # Notas
    notas = {}
    for dt, ns in refs:
        _juntar(notas, _lista("FCRM Note", filters={"reference_doctype": dt, "reference_docname": ["in", ns]},
                              fields=["name", "title", "content", "creation", "owner",
                                      "reference_doctype", "reference_docname"]))
    notas_das_chamadas = set()

    # Chamadas
    chamadas = {}
    for dt, ns in refs:
        _juntar(chamadas, _lista("CRM Call Log", filters={"reference_doctype": dt, "reference_docname": ["in", ns]},
                                 fields=["name", "type", "status", "duration", "start_time", "creation", "from", "to",
                                         "note", "caller", "receiver", "reference_doctype", "reference_docname"]))
        _juntar(chamadas, _lista("CRM Call Log", filters=[["Dynamic Link", "link_doctype", "=", dt],
                                                          ["Dynamic Link", "link_name", "in", ns]],
                                 fields=["name", "type", "status", "duration", "start_time", "creation", "from", "to",
                                         "note", "caller", "receiver", "reference_doctype", "reference_docname"]))
    for c in chamadas.values():
        nota = notas.get(c.note) if c.note else None
        if c.note:
            notas_das_chamadas.add(c.note)
            if not nota and frappe.db.exists("FCRM Note", c.note):
                nota = frappe.db.get_value("FCRM Note", c.note, ["title", "content"], as_dict=True)
        quem = c.caller if c.type == "Outgoing" else c.receiver
        sentido = "efectuada" if c.type == "Outgoing" else "recebida"
        estado = {"Completed": "atendida", "No Answer": "não atendida", "Busy": "ocupado",
                  "Failed": "falhou", "Canceled": "cancelada", "Ringing": "a tocar",
                  "In Progress": "em curso", "Queued": "em fila", "Initiated": "a ligar"}.get(c.status, c.status or "")
        dur = int(c.duration or 0)
        duracao = f"{dur // 60} min {dur % 60:02d} s" if dur else ""
        numero = c.get("to") if c.type == "Outgoing" else c.get("from")
        o, lig = origem(c.reference_doctype, c.reference_docname)
        itens.append({
            "tipo": "chamada", "data": _quando(c.start_time or c.creation),
            "titulo": f"Chamada {sentido}" + (f" · {estado}" if estado else ""),
            "detalhe": " · ".join(x for x in [numero, duracao, frappe.utils.get_fullname(quem) if quem else ""] if x),
            "texto": _texto((nota or {}).get("content")) if nota else "",
            "origem": o, "ligacao": lig,
        })

    for n in notas.values():
        if n.name in notas_das_chamadas:
            continue
        o, lig = origem(n.reference_doctype, n.reference_docname)
        itens.append({
            "tipo": "nota", "data": _quando(n.creation), "titulo": n.title or "Nota",
            "detalhe": frappe.utils.get_fullname(n.owner), "texto": _texto(n.content),
            "origem": o, "ligacao": lig,
        })

    # Emails (os dos tickets ficam no ticket)
    emails = {}
    campos_email = ["name", "subject", "communication_date", "creation", "sent_or_received", "sender",
                    "sender_full_name", "recipients", "content", "communication_medium",
                    "reference_doctype", "reference_name"]
    base = [["communication_type", "=", "Communication"], ["reference_doctype", "!=", "HD Ticket"]]
    for dt, ns in refs:
        _juntar(emails, _lista("Communication", fields=campos_email,
                               filters=[["reference_doctype", "=", dt], ["reference_name", "in", ns],
                                        ["communication_type", "=", "Communication"]]))
        if dt in ("Contact", "CRM Organization"):
            _juntar(emails, _lista("Communication", fields=campos_email,
                                   filters=base + [["Communication Link", "link_doctype", "=", dt],
                                                   ["Communication Link", "link_name", "in", ns]]))
        # 27-11-2026: as conversas do Stratechna Chat ligadas à ficha (orbit/chat_crm.py) — meio «Chat»
        # get_all: sem caixa de correio, a regra do Frappe «email_account in (…)» escondia-os; as fichas (refs) já
        # vêm das listas com as permissões de quem abre (D5: vê quem pode abrir a ficha)
        _juntar(emails, frappe.get_all("Communication", fields=campos_email, limit_page_length=_LIMITE,
                                       filters=[["reference_doctype", "=", dt], ["reference_name", "in", ns],
                                                ["communication_medium", "=", "Chat"]]))
    for e in emails.values():
        if e.reference_doctype == "HD Ticket":
            continue
        if e.communication_medium == "Chat":
            o, lig = origem(e.reference_doctype, e.reference_name)
            itens.append({"tipo": "email", "data": _quando(e.communication_date or e.creation),
                          "titulo": e.subject or "Chat", "detalhe": "Chat · " + cstr(e.sender_full_name or ""),
                          "texto": _texto(e.content), "origem": o, "ligacao": lig})
            continue
        enviado = e.sent_or_received == "Sent"
        meio = {"Event": "Convite", "Phone": "Telefone", "Chat": "Chat", "SMS": "SMS"}.get(e.communication_medium, "")
        o, lig = origem(e.reference_doctype, e.reference_name)
        itens.append({
            "tipo": "email", "data": _quando(e.communication_date or e.creation),
            "titulo": e.subject or "(sem assunto)",
            "detalhe": " · ".join(x for x in [
                ("Enviado" + (" para " + cstr(e.recipients) if e.recipients else "")) if enviado else ("Recebido de " + (e.sender_full_name or e.sender or "")),
                meio] if x),
            "texto": _texto(e.content), "origem": o, "ligacao": lig,
        })

    # Tarefas
    tarefas = {}
    for dt, ns in refs:
        _juntar(tarefas, _lista("CRM Task", filters={"reference_doctype": dt, "reference_docname": ["in", ns]},
                                fields=["name", "title", "description", "status", "priority", "due_date",
                                        "assigned_to", "creation", "reference_doctype", "reference_docname"]))
    for t in tarefas.values():
        o, lig = origem(t.reference_doctype, t.reference_docname)
        itens.append({
            "tipo": "tarefa", "data": _quando(t.creation), "titulo": t.title or "Tarefa",
            "detalhe": " · ".join(x for x in [
                _("Estado") + ": " + _(t.status) if t.status else "",
                ("Até " + frappe.utils.formatdate(t.due_date, "dd-MM-yyyy")) if t.due_date else "",
                frappe.utils.get_fullname(t.assigned_to) if t.assigned_to else ""] if x),
            "texto": _texto(t.description), "origem": o, "ligacao": lig,
        })

    # Tickets do Desk
    tickets = {}
    campos_t = ["name", "subject", "status", "priority", "opening_date", "creation", "raised_by", "contact"]
    if amb["contactos"]:
        _juntar(tickets, _lista("HD Ticket", filters={"contact": ["in", amb["contactos"]]}, fields=campos_t))
    if amb["emails"]:
        _juntar(tickets, _lista("HD Ticket", filters={"raised_by": ["in", amb["emails"]]}, fields=campos_t))
    for t in tickets.values():
        mensagens = frappe.db.count("Communication", {"reference_doctype": "HD Ticket", "reference_name": t.name})
        itens.append({
            "tipo": "ticket", "data": _quando(t.creation), "titulo": f"Ticket #{t.name} · {t.subject or ''}",
            "detalhe": " · ".join(x for x in [_(t.status) if t.status else "", t.raised_by or "",
                                              f"{mensagens} mensage{'m' if mensagens == 1 else 'ns'}"] if x),
            "texto": "", "origem": "", "ligacao": f"/helpdesk/tickets/{t.name}", "fora": 1,
        })

    # Reuniões (agenda do Orbit e marcações do Booking)
    reunioes = {}
    campos_r = ["name", "subject", "starts_on", "ends_on", "description", "location", "event_type"]
    for dt, ns in refs:
        _juntar(reunioes, _lista("Event", fields=campos_r,
                                 filters=[["Event Participants", "reference_doctype", "=", dt],
                                          ["Event Participants", "reference_docname", "in", ns]]))
        _juntar(reunioes, _lista("Event", fields=campos_r,
                                 filters={"reference_doctype": dt, "reference_docname": ["in", ns]}))
    for r in reunioes.values():
        fim = frappe.utils.format_datetime(r.ends_on, "HH:mm") if r.ends_on else ""
        itens.append({
            "tipo": "reuniao", "data": _quando(r.starts_on), "titulo": r.subject or "Reunião",
            "detalhe": " · ".join(x for x in [
                frappe.utils.format_datetime(r.starts_on, "dd-MM-yyyy HH:mm") + (f"–{fim}" if fim else ""),
                r.location or ""] if x),
            "texto": _texto(r.description), "origem": "", "ligacao": "",
        })

    itens.sort(key=lambda i: i["data"] or "", reverse=True)
    return itens


def _(t):
    return frappe._(t) if t else ""


# ---------------------------------------------------------------- botão

_COMUM = r"""
const _oaEsc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))
const _oaData = (d) => { try { const x = new Date(String(d).replace(' ', 'T')); return x.toLocaleDateString('pt-PT', { day: '2-digit', month: '2-digit', year: 'numeric' }) + ' ' + x.toLocaleTimeString('pt-PT', { hour: '2-digit', minute: '2-digit' }) } catch (e) { return '' } }
const _OA_TIPOS = [
  ['email', 'Emails', '✉'], ['chamada', 'Chamadas', '☎'], ['nota', 'Notas', '✎'],
  ['tarefa', 'Tarefas', '☑'], ['reuniao', 'Reuniões', '◷'], ['ticket', 'Tickets', '⚑'],
]

function _oaJanela($dialog, itens, id) {
  const conta = (t) => itens.filter((i) => i.tipo === t).length
  const tipos = _OA_TIPOS.filter(([t]) => conta(t))
  const filtros = [`<input type="radio" name="${id}" id="${id}-todos" class="oa-f" checked><label for="${id}-todos" class="oa-c">Tudo (${itens.length})</label>`]
    .concat(tipos.map(([t, nome]) => `<input type="radio" name="${id}" id="${id}-${t}" class="oa-f"><label for="${id}-${t}" class="oa-c">${nome} (${conta(t)})</label>`)).join('')
  const regras = tipos.map(([t]) => `#${id}-${t}:checked ~ .oa-lista .oa-i:not([data-t="${t}"]){display:none}`).join('')
  const icone = Object.fromEntries(_OA_TIPOS.map(([t, , i]) => [t, i]))
  const linhas = itens.map((i) => {
    const titulo = i.ligacao
      ? `<a href="${_oaEsc(i.ligacao)}" ${i.fora ? 'target="_blank" rel="noopener"' : ''} class="hover:underline">${_oaEsc(i.titulo)}</a>`
      : _oaEsc(i.titulo)
    const corpo = i.texto
      ? (i.texto.length > 280
          ? `<details class="mt-1"><summary class="cursor-pointer text-sm text-ink-gray-6">${_oaEsc(i.texto.slice(0, 220))}… <span class="text-ink-gray-5">ver tudo</span></summary><div class="oa-t mt-1 text-sm text-ink-gray-8">${_oaEsc(i.texto)}</div></details>`
          : `<div class="oa-t mt-1 text-sm text-ink-gray-8">${_oaEsc(i.texto)}</div>`)
      : ''
    return `<div class="oa-i mb-2 flex gap-3 rounded-lg border border-outline-gray-2 p-3" data-t="${i.tipo}">
      <div class="w-5 shrink-0 text-center text-ink-gray-5" title="${_oaEsc(i.tipo)}">${icone[i.tipo] || '•'}</div>
      <div class="min-w-0 flex-1">
        <div class="flex items-baseline justify-between gap-3">
          <div class="truncate text-base font-semibold text-ink-gray-9">${titulo}</div>
          <div class="shrink-0 text-sm text-ink-gray-5">${_oaData(i.data)}</div>
        </div>
        ${i.detalhe ? `<div class="truncate text-sm text-ink-gray-6">${_oaEsc(i.detalhe)}</div>` : ''}
        ${i.origem ? `<div class="text-sm text-ink-gray-5">${_oaEsc(i.origem)}</div>` : ''}
        ${corpo}
      </div>
    </div>`
  }).join('')
  const estilo = `<style>
    .oa-f{position:absolute;opacity:0;pointer-events:none}
    .oa-c{display:inline-block;margin:0 6px 6px 0;padding:3px 10px;border-radius:999px;font-size:13px;cursor:pointer;border:1px solid var(--outline-gray-2,#e2e2e2);color:var(--ink-gray-7,#444)}
    .oa-f:checked + .oa-c{background:var(--surface-gray-7,#22303d);border-color:transparent;color:#fff}
    .oa-f:focus-visible + .oa-c{outline:2px solid #b20009;outline-offset:1px}
    .oa-t{white-space:pre-wrap;overflow-wrap:anywhere}
    ${regras}
  </style>`
  $dialog({
    title: 'Actividade',
    size: '4xl',
    html: itens.length
      ? `${estilo}<div>${filtros}<div class="oa-lista mt-2 max-h-[62vh] overflow-y-auto pr-1">${linhas}</div></div>`
      : '<p class="text-p-base text-ink-gray-6">Ainda não há actividade registada aqui.</p>',
  })
}

async function _oaBotao($dialog, call, doctype, name) {
  let itens = []
  try { itens = await call('orbit.actividade_crm.listar', { doctype, name }) || [] } catch (e) { itens = [] }
  const id = 'oa' + Math.random().toString(36).slice(2, 8)
  return {
    label: itens.length ? `Actividade (${itens.length})` : 'Actividade',
    icon: 'lucide-history',
    onClick: () => _oaJanela($dialog, itens, id),
  }
}
"""

from orbit.chamadas_crm import _COMUM as _LIGAR  # noqa: E402 — o botão «Ligar», partilhado

SCRIPTS = {
    "Orbit · Actividade da organização": ("CRM Organization", _COMUM + _LIGAR + r"""
class CRMOrganization {}

async function setupForm({ doc, $dialog, call }) {
  const acts = [await _oaBotao($dialog, call, 'CRM Organization', doc.name)]
  // «Ligar» (chamadas_crm.py): os telefones dos contactos da organização
  let contactos = []
  try {
    contactos = await call('frappe.client.get_list', {
      doctype: 'Contact', fields: ['full_name', 'mobile_no', 'phone'], limit_page_length: 50,
      filters: [['Dynamic Link', 'link_doctype', '=', 'CRM Organization'], ['Dynamic Link', 'link_name', '=', doc.name]],
    }) || []
  } catch (e) {}
  const tel = []
  for (const c of contactos) tel.push([c.mobile_no, c.full_name], [c.phone, c.full_name])
  const b = _ocBotao($dialog, 'CRM Organization', doc.name, doc.organization_name || doc.name, tel)
  if (b) acts.unshift(b)
  return { actions: acts }
}
"""),
    "Orbit · Actividade do contacto": ("Contact", _COMUM + _LIGAR + r"""
class Contact {}

async function setupForm({ doc, $dialog, call }) {
  const acts = [await _oaBotao($dialog, call, 'Contact', doc.name)]
  // «Ligar» (chamadas_crm.py)
  const tel = [[doc.mobile_no, __('Telemóvel')], [doc.phone, __('Telefone')]]
  for (const p of (doc.phone_nos || [])) tel.push([p.phone, ''])
  const b = _ocBotao($dialog, 'Contact', doc.name, doc.full_name || doc.name, tel)
  if (b) acts.unshift(b)
  return { actions: acts }
}
"""),
}


def garantir():
    if not frappe.db.exists("DocType", "CRM Form Script"):
        return
    for nome in _ANTIGOS:
        if frappe.db.exists("CRM Form Script", nome):
            frappe.delete_doc("CRM Form Script", nome, ignore_permissions=True, force=True)
    for nome, (dt, script) in SCRIPTS.items():
        if frappe.db.exists("CRM Form Script", nome):
            d = frappe.get_doc("CRM Form Script", nome)
            if d.script == script and d.dt == dt and d.view == "Form" and d.enabled:
                continue
            d.update({"dt": dt, "view": "Form", "script": script, "enabled": 1})
            d.save(ignore_permissions=True)
        else:
            frappe.get_doc({"doctype": "CRM Form Script", "name": nome, "__newname": nome, "dt": dt,
                            "view": "Form", "enabled": 1, "is_standard": 0, "script": script}).insert(ignore_permissions=True)
    frappe.db.commit()
