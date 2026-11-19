"""Chamadas telefónicas no CRM do Orbit — fase C1 (docs/PLANO-CHAMADAS-CRM.md, 19-11-2026).

Nenhuma app pode ver o histórico de chamadas do iPhone; o que o Zoho fazia no iPhone era perguntar
«registar?» nas chamadas lançadas da app dele. Aqui é o mesmo, sem app nativa:

1. «Ligar» numa ficha (lead, negócio, contacto, organização) chama `iniciar()`: o `CRM Call Log` nasce logo
   (Saída, «Initiated», meio «Manual»), com a chave gerada no telemóvel em `id`, e o telefone abre a chamada.
2. Ao voltar ao CRM, o `orbit-chamadas.js` mostra «Como correu a chamada?» e grava com `comentar()`: estado,
   duração, nota (`FCRM Note` ligada à mesma ficha) e, se quiser, a próxima tarefa (`CRM Task`).
3. `por_comentar()` devolve as chamadas da pessoa ainda «Initiated» dos últimos 7 dias — o CRM volta a perguntar
   da próxima vez que abre. Ao fim de 7 dias deixa de perguntar e a chamada fica «Iniciada» (o estado
   «sem comentário» não existe na lista fechada do CRM; ver §3 do plano).

Os botões «Ligar» entram pelos CRM Form Scripts (`garantir()`), como o botão «Actividade».
"""

import re

import frappe
from frappe.utils import add_days, add_to_date, cint, cstr, get_datetime, now_datetime

DIAS_A_PERGUNTAR = 7

_ESTADOS = {"atendida": "Completed", "nao_atendeu": "No Answer", "ocupado": "Busy", "numero_errado": "Failed"}
_TITULO_NOTA = {"atendida": "Chamada", "nao_atendeu": "Chamada — não atendeu", "ocupado": "Chamada — ocupado",
                "numero_errado": "Chamada — número errado"}
_FICHAS = ("CRM Lead", "CRM Deal", "Contact", "CRM Organization")


def _numero(n):
    n = re.sub(r"[^\d+]", "", cstr(n))
    return n[:20]


def _meu_numero():
    u = frappe.db.get_value("User", frappe.session.user, ["mobile_no", "phone"], as_dict=True) or {}
    return _numero(u.get("mobile_no") or u.get("phone")) or "0"


def _nome_da_ficha(doctype, name):
    campo = {"CRM Lead": "lead_name", "CRM Deal": "organization", "Contact": "full_name",
             "CRM Organization": "organization_name"}[doctype]
    return frappe.db.get_value(doctype, name, campo) or name


@frappe.whitelist(methods=["POST"])
def iniciar(chave, numero, doctype, name):
    """O registo da chamada, criado no momento em que se toca em «Ligar»."""
    if doctype not in _FICHAS:
        frappe.throw("Ficha não suportada.")
    frappe.get_doc(doctype, name).check_permission("read")
    chave = "orbit-" + re.sub(r"[^a-zA-Z0-9-]", "", cstr(chave))[:40]
    if frappe.db.exists("CRM Call Log", chave):
        return chave
    numero = _numero(numero)
    if not numero:
        frappe.throw("Número inválido.")
    doc = frappe.get_doc({
        "doctype": "CRM Call Log", "id": chave, "type": "Outgoing", "status": "Initiated",
        "telephony_medium": "Manual", "medium": "Telemóvel", "from": _meu_numero(), "to": numero,
        "caller": frappe.session.user, "start_time": now_datetime(),
        "reference_doctype": doctype, "reference_docname": name,
    })
    doc.append("links", {"link_doctype": doctype, "link_name": name})
    doc.insert(ignore_permissions=True)
    return doc.name


def _minha(nome):
    c = frappe.get_doc("CRM Call Log", nome)
    if c.caller != frappe.session.user and "System Manager" not in frappe.get_roles():
        frappe.throw("Esta chamada não é sua.", frappe.PermissionError)
    return c


@frappe.whitelist()
def por_comentar():
    """As chamadas da pessoa à espera de comentário (últimos 7 dias), da mais recente para a mais antiga."""
    linhas = frappe.get_all(
        "CRM Call Log",
        filters={"caller": frappe.session.user, "status": "Initiated", "telephony_medium": "Manual",
                 "start_time": [">=", add_days(now_datetime(), -DIAS_A_PERGUNTAR)]},
        fields=["name", "to", "start_time", "reference_doctype", "reference_docname"],
        order_by="start_time desc", limit_page_length=20)
    for l in linhas:
        l["nome"] = _nome_da_ficha(l.reference_doctype, l.reference_docname) if l.reference_doctype in _FICHAS else ""
        l["start_time"] = cstr(l.start_time)
    return linhas


@frappe.whitelist(methods=["POST"])
def comentar(nome, estado, duracao=0, nota="", tarefa="", tarefa_data=""):
    """Fecha a chamada com o que a pessoa disse na janela «Como correu a chamada?»."""
    if estado not in _ESTADOS:
        frappe.throw("Estado inválido.")
    c = _minha(nome)
    duracao = max(0, min(cint(duracao), 6 * 3600)) if estado == "atendida" else 0
    c.status = _ESTADOS[estado]
    c.duration = duracao
    c.end_time = add_to_date(get_datetime(c.start_time), seconds=duracao) if c.start_time else now_datetime()

    nota = cstr(nota).strip()
    if nota or estado == "numero_errado":
        texto = frappe.utils.escape_html(nota or "Número errado.").replace("\n", "<br>")
        n = frappe.get_doc({"doctype": "FCRM Note", "title": _TITULO_NOTA[estado], "content": f"<p>{texto}</p>",
                            "reference_doctype": c.reference_doctype, "reference_docname": c.reference_docname})
        n.insert(ignore_permissions=True)
        c.note = n.name
    c.save(ignore_permissions=True)

    tarefa = cstr(tarefa).strip()
    if tarefa and c.reference_doctype in ("CRM Lead", "CRM Deal"):
        frappe.get_doc({"doctype": "CRM Task", "title": tarefa[:140], "status": "Todo", "priority": "Medium",
                        "assigned_to": frappe.session.user, "due_date": tarefa_data or None,
                        "reference_doctype": c.reference_doctype, "reference_docname": c.reference_docname,
                        }).insert(ignore_permissions=True)
    elif tarefa:
        # Tarefas do CRM só se mostram em leads e negócios; numa ficha de contacto/organização fica como nota.
        frappe.get_doc({"doctype": "FCRM Note", "title": "Próxima tarefa",
                        "content": f"<p>{frappe.utils.escape_html(tarefa)}"
                                   + (f" — até {frappe.utils.escape_html(tarefa_data)}" if tarefa_data else "") + "</p>",
                        "reference_doctype": c.reference_doctype, "reference_docname": c.reference_docname,
                        }).insert(ignore_permissions=True)
    return c.name


@frappe.whitelist(methods=["POST"])
def anular(nome):
    """«Não cheguei a ligar»: apaga o registo criado ao tocar."""
    c = _minha(nome)
    if c.status == "Initiated" and c.telephony_medium == "Manual":
        frappe.delete_doc("CRM Call Log", c.name, ignore_permissions=True)
    return True


# ------------------------------------------------------------------ botões «Ligar» (CRM Form Scripts)

_COMUM = r"""
function _ocTelefones(lista) {
  const vistos = new Set(), out = []
  for (const [num, rotulo] of lista) {
    const n = String(num || '').replace(/[^\d+]/g, '')
    if (n.length < 6 || vistos.has(n)) continue
    vistos.add(n); out.push([n, rotulo])
  }
  return out
}
function _ocBotao($dialog, doctype, name, nome, tel) {
  const telefones = _ocTelefones(tel)
  if (!telefones.length || !window.orbitChamadas) return null
  const ligar = (n) => window.orbitChamadas.ligar({ numero: n, doctype, name, nome })
  return {
    label: __('Ligar'),
    icon: 'lucide-phone',
    onClick: () => {
      if (telefones.length === 1) return ligar(telefones[0][0])
      $dialog({
        title: __('Ligar para'),
        actions: telefones.map(([n, r]) => ({ label: (r ? r + ' · ' : '') + n, variant: 'subtle',
                                             onClick: (close) => { close(); ligar(n) } })),
      })
    },
  }
}
"""

SCRIPTS = {
    "Orbit · Ligar do lead": ("CRM Lead", _COMUM + r"""
class CRMLead {}
function setupForm({ doc, $dialog }) {
  const b = _ocBotao($dialog, 'CRM Lead', doc.name, doc.lead_name || doc.organization || doc.name,
                     [[doc.mobile_no, __('Telemóvel')], [doc.phone, __('Telefone')]])
  return { actions: b ? [b] : [] }
}
"""),
    "Orbit · Ligar do negócio": ("CRM Deal", _COMUM + r"""
class CRMDeal {}
async function setupForm({ doc, $dialog, call }) {
  const tel = [[doc.mobile_no, __('Telemóvel')], [doc.phone, __('Telefone')]]
  for (const c of (doc.contacts || [])) tel.push([c.mobile_no, c.full_name], [c.phone, c.full_name])
  const b = _ocBotao($dialog, 'CRM Deal', doc.name, doc.organization || doc.lead_name || doc.name, tel)
  return { actions: b ? [b] : [] }
}
"""),
}


def garantir():
    if not frappe.db.exists("DocType", "CRM Form Script"):
        return
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
