"""Faz a grelha de apps servir os ícones desta app, em vez dos do upstream.

O caminho óbvio — escrever os nossos SVG por cima dos do ERPNext, do HR e do
Frappe — não funciona e ainda bem: o contentor corre como `frappe` e as pastas
das apps são de root. Uma marca que dependesse de escrever dentro de código
alheio ficaria sempre à mercê de permissões e de cada reconstrução da imagem.

A solução usa o mecanismo do Frappe em vez de lutar contra ele. O frontend monta
o caminho do ícone a partir do campo `app` do próprio Desktop Icon:

    assets/<icone.app>/icons/desktop_icons/<estilo>/<nome>.svg
    (frappe/public/js/frappe/utils/utils.js, get_desktop_icon)

Basta então dizer que estes ícones pertencem à app `orbit` — e os ficheiros
passam a ser lidos de `orbit/public/icons/desktop_icons/`, que é nossa, versionada
e reconstruída com a app. Nada é escrito fora daqui, e a marca sobrevive a
qualquer actualização das apps do upstream.

Corre no `after_migrate`, o último passo de qualquer actualização.
"""

import os

import frappe

NOSSOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public", "icons", "desktop_icons")


def _rotulos_que_temos() -> set[str]:
    """Os nomes de ficheiro que trazemos, que são os `scrub` dos rótulos."""
    pasta = os.path.join(NOSSOS, "solid")
    if not os.path.isdir(pasta):
        return set()
    return {f[:-4] for f in os.listdir(pasta) if f.endswith(".svg")}


def repor_icones():
    """Aponta os Desktop Icon que temos desenhados para os ficheiros desta app."""
    nossos = _rotulos_que_temos()
    if not nossos:
        frappe.log_error("Orbit: não há ícones em " + NOSSOS, "Orbit marca")
        return

    mudados, ja_certos = [], 0
    for icone in frappe.get_all("Desktop Icon", fields=["name", "label", "app"]):
        if frappe.scrub(icone.label) not in nossos:
            continue
        if icone.app == "orbit":
            ja_certos += 1
            continue
        frappe.db.set_value("Desktop Icon", icone.name, "app", "orbit", update_modified=False)
        mudados.append(icone.label)

    frappe.db.commit()
    # a lista de ficheiros e os ícones são lidos no arranque e ficam no boot
    frappe.cache.delete_key("desktop_icons")
    frappe.cache.delete_key("bootinfo")
    frappe.clear_cache()

    aviso = (f"Orbit: {len(nossos)} ícones disponíveis, {len(mudados)} apontados agora, "
             f"{ja_certos} já estavam")
    print(aviso)
    frappe.logger().info(aviso)
