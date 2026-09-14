"""Repõe os ícones dos módulos nas pastas onde o Frappe os vai buscar.

Porque é preciso: o frontend procura primeiro
`assets/<app>/icons/desktop_icons/<estilo>/<nome>.svg` e só cai no `logo_url` da
base de dados se esse ficheiro não existir (frappe/public/js/frappe/utils/utils.js,
get_desktop_icon). Como o ERPNext, o HR e o próprio Frappe trazem essa pasta cheia,
os módulos deles ignoram tudo o que se grave na base de dados.

Escrever por cima é a única forma — e significa que a marca não sobrevive a uma
reconstrução da imagem. Esta função corre no `after_migrate`, que é o último passo
de qualquer actualização: a marca volta sozinha, sem depender de ninguém se
lembrar nem de um cron a verificar de hora a hora.

Os nossos ficheiros vivem em orbit/public/icons/modulos/<app>/<estilo>/.
"""

import os
import shutil

import frappe

NOSSOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public", "icons", "modulos")
ESTILOS = ("subtle", "solid")


def repor_icones():
    """Copia os nossos ícones para dentro das apps donas das pastas."""
    if not os.path.isdir(NOSSOS):
        frappe.log_error("Orbit: pasta de ícones em falta", NOSSOS)
        return

    copiados, saltados = 0, []
    for app in sorted(os.listdir(NOSSOS)):
        try:
            base = frappe.get_app_path(app)
        except Exception:
            saltados.append(f"{app} (não instalada)")
            continue

        for estilo in ESTILOS:
            origem = os.path.join(NOSSOS, app, estilo)
            destino = os.path.join(base, "public", "icons", "desktop_icons", estilo)
            if not os.path.isdir(origem):
                continue
            if not os.path.isdir(destino):
                saltados.append(f"{app}/{estilo} (a app já não tem essa pasta)")
                continue
            for ficheiro in os.listdir(origem):
                if not ficheiro.endswith(".svg"):
                    continue
                shutil.copyfile(os.path.join(origem, ficheiro), os.path.join(destino, ficheiro))
                copiados += 1

    # A lista de ficheiros é lida no arranque e fica em cache com o boot.
    frappe.cache.delete_key("desktop_icons")
    frappe.cache.delete_key("bootinfo")
    frappe.clear_cache()

    aviso = f"Orbit: {copiados} ícones de módulo repostos"
    if saltados:
        aviso += " — saltados: " + ", ".join(saltados)
    print(aviso)
    frappe.logger().info(aviso)
