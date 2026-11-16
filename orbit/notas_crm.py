"""As notas nas fichas de organização e de contacto do CRM.

O CRM do Orbit só mostra o separador «Notas» nos leads e nos negócios. As notas
ligadas a uma organização ou a um contacto (todas as que vieram do Zoho para
contas e contactos, por exemplo) existem, mas não tinham onde se ver a partir
da ficha — só na lista geral de Notas, sem dizer de quem eram.

Fica um botão «Notas (N)» — com o número de notas — no cabeçalho da organização e do contacto, por CRM Form
Script (configuração do próprio CRM — nenhum ficheiro do CRM é alterado). Na
organização mostra as notas dela e as dos contactos dela; no contacto, as do
contacto. Abre numa janela, da mais recente para a mais antiga.

`garantir()` corre no after_migrate/after_install: cria ou repõe os dois
scripts em cada tenant, incluindo os que nascem depois.
"""

import frappe

_COMUM = r"""
const _esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))
const _data = (d) => { try { return new Date(String(d).replace(' ', 'T')).toLocaleDateString('pt-PT', { day: '2-digit', month: '2-digit', year: 'numeric' }) } catch (e) { return '' } }

async function _orbitNotas(call, refs) {
  let todas = []
  for (const [dt, nomes, origem] of refs) {
    if (!nomes.length) continue
    const r = await call('frappe.client.get_list', {
      doctype: 'FCRM Note',
      filters: [['reference_doctype', '=', dt], ['reference_docname', 'in', nomes]],
      fields: ['name', 'title', 'content', 'creation', 'reference_docname'],
      order_by: 'creation desc',
      limit_page_length: 500,
    })
    todas = todas.concat((r || []).map((n) => ({ ...n, origem: origem ? origem + ' · ' + n.reference_docname : '' })))
  }
  todas.sort((a, b) => String(b.creation).localeCompare(String(a.creation)))
  return todas
}

function _orbitBotao($dialog, router, notas) {
  return {
    label: notas.length ? `Notas (${notas.length})` : 'Notas',
    icon: 'lucide-sticky-note',
    onClick: () => _orbitJanela($dialog, router, notas),
  }
}

function _orbitJanela($dialog, router, notas) {
  const cartoes = notas.map((n) => `
    <div class="mb-3 rounded-lg border border-outline-gray-2 p-3">
      <div class="mb-1 flex items-baseline justify-between gap-3">
        <div class="text-base font-semibold text-ink-gray-9">${_esc(n.title || 'Nota')}</div>
        <div class="shrink-0 text-sm text-ink-gray-5">${_data(n.creation)}</div>
      </div>
      ${n.origem ? `<div class="mb-1 text-sm text-ink-gray-5">${_esc(n.origem)}</div>` : ''}
      <div class="prose prose-sm max-w-none text-ink-gray-8">${n.content || ''}</div>
    </div>`).join('')
  $dialog({
    title: notas.length === 1 ? '1 nota' : `${notas.length} notas`,
    size: '3xl',
    html: notas.length ? `<div class="max-h-[65vh] overflow-y-auto pr-1">${cartoes}</div>`
                       : '<p class="text-p-base text-ink-gray-6">Ainda não há notas aqui.</p>',
    actions: [{ label: 'Abrir a lista de Notas', variant: 'subtle', onClick: (close) => { close(); router.push({ name: 'Notes' }) } }],
  })
}
"""

SCRIPTS = {
    "Orbit · Notas da organização": ("CRM Organization", _COMUM + r"""
class CRMOrganization {}

async function setupForm({ doc, $dialog, call, router }) {
  // As notas lêem-se já ao abrir a ficha, para o botão dizer quantas há.
  const contactos = await call('frappe.client.get_list', {
    doctype: 'Contact',
    filters: [['Dynamic Link', 'link_doctype', '=', 'CRM Organization'], ['Dynamic Link', 'link_name', '=', doc.name]],
    fields: ['name'],
    limit_page_length: 500,
  })
  const notas = await _orbitNotas(call, [
    ['CRM Organization', [doc.name], ''],
    ['Contact', (contactos || []).map((c) => c.name), 'Contacto'],
  ])
  return { actions: [_orbitBotao($dialog, router, notas)] }
}
"""),
    "Orbit · Notas do contacto": ("Contact", _COMUM + r"""
class Contact {}

async function setupForm({ doc, $dialog, call, router }) {
  const notas = await _orbitNotas(call, [['Contact', [doc.name], '']])
  return { actions: [_orbitBotao($dialog, router, notas)] }
}
"""),
}


def garantir():
    if not frappe.db.exists("DocType", "CRM Form Script"):
        return
    for nome, (dt, script) in SCRIPTS.items():
        if frappe.db.exists("CRM Form Script", nome):
            d = frappe.get_doc("CRM Form Script", nome)
            if d.script == script and d.dt == dt and d.view == "Form":
                continue
            d.update({"dt": dt, "view": "Form", "script": script})
            d.save(ignore_permissions=True)
        else:
            frappe.get_doc({"doctype": "CRM Form Script", "name": nome, "__newname": nome, "dt": dt,
                            "view": "Form", "enabled": 1, "is_standard": 0, "script": script}).insert(ignore_permissions=True)
    frappe.db.commit()
