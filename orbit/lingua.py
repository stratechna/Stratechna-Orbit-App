"""A língua de cada pessoa no Orbit (18-10-2026, docs/PLANO-I18N-ORBIT-APPS.md).

**Quem manda é o portal** (decisão L3 do Vítor). A língua de uma pessoa vive na ficha do cliente no portal
(`idioma_pessoa()`); os colaboradores da casa ficam sempre em pt. Chega aqui por três caminhos, e todos
acabam em `definir()`:
  · a entrada única — o id_token do portal traz `locale` (entrada_unica.regresso);
  · a mudança no portal e o acerto nocturno (03:40) — verbo `linguas` da ponte do Apps02
    (/opt/orbit/scripts/linguas.sh + orbit_linguas.py), que corre em TODOS os tenants e também põe o
    SOGoLanguage no webmail; `orbit.portal.definir_lingua`/`acertar_linguas` fazem o mesmo por HTTP.
O campo «Língua» do utilizador fica só de leitura no ecrã: mudá-lo aqui seria desfeito na entrada seguinte.

**As traduções não vivem na base de dados.** Estão em `orbit/translations/{pt,en,es,fr}.csv`, dentro da
imagem: a `orbit` é a última app instalada em todos os tenants, por isso o que ela traz ganha às traduções
do CRM e do Helpdesk, e um tenant novo nasce já com elas. As linhas `Translation` só servem para ajustes de
um tenant — e ganham a tudo, por isso apagamos as que nós próprios lá púnhamos (os nomes dos módulos).
"""
import frappe

# pt/en/es/fr do portal → código de língua do Frappe (são iguais; a tabela existe para o dia em que não forem)
LINGUAS = {"pt": "pt", "en": "en", "es": "es", "fr": "fr"}


def normalizar(lingua: str | None) -> str | None:
    v = (lingua or "").strip().lower().replace("_", "-")[:2]
    return LINGUAS.get(v)


def definir(email: str, lingua: str | None) -> str:
    """Grava a língua de uma pessoa. Devolve «igual», «mudada», «sem utilizador» ou «língua inválida»."""
    lang = normalizar(lingua)
    if not lang:
        return "língua inválida"
    nome = frappe.db.get_value("User", {"name": (email or "").strip().lower()}, "name") \
        or frappe.db.get_value("User", {"email": (email or "").strip()}, "name")
    if not nome or nome in ("Administrator", "Guest"):
        return "sem utilizador"
    if frappe.db.get_value("User", nome, "language") == lang:
        return "igual"
    # set_value directo: não passa pelo validate do User (que não tem nada a dizer sobre a língua) nem
    # muda o `modified` — é uma preferência que vem de fora, não uma edição da ficha.
    frappe.db.set_value("User", nome, "language", lang, update_modified=False)
    frappe.clear_cache(user=nome)
    return "mudada"


# ── after_migrate ────────────────────────────────────────────────────────────

def garantir() -> None:
    try:
        _garantir()
    except Exception:
        frappe.log_error(title="orbit.lingua.garantir")


def _garantir() -> None:
    # 1. as quatro línguas activas (o selector do Frappe só mostra as `enabled`)
    for lang in LINGUAS.values():
        if frappe.db.exists("Language", lang):
            frappe.db.set_value("Language", lang, "enabled", 1, update_modified=False)

    # 2. o sistema fica em pt (é a língua de quem ainda não tem nenhuma, e a dos emails do sistema)
    if not frappe.db.get_single_value("System Settings", "language"):
        frappe.db.set_single_value("System Settings", "language", "pt")
    frappe.db.sql("""UPDATE tabUser SET language = 'pt'
                     WHERE IFNULL(language, '') = '' AND name NOT IN ('Administrator', 'Guest')""")

    # 3. as linhas Translation que o `marca.repor_nomes` gravava até 18-10 — só as nossas (mesma origem e
    #    mesmo texto); uma que alguém tenha mudado à mão no tenant fica.
    from orbit.marca import NOMES
    apagadas = 0
    for origem, texto in NOMES.items():
        for nome in frappe.get_all("Translation", filters={"source_text": origem, "translated_text": texto},
                                   pluck="name"):
            frappe.delete_doc("Translation", nome, ignore_permissions=True, force=True)
            apagadas += 1

    # 4. o campo «Língua» do utilizador: só de leitura no ecrã (L3) — o código continua a poder escrevê-lo
    from frappe.custom.doctype.property_setter.property_setter import make_property_setter
    make_property_setter("User", "language", "read_only", 1, "Check", validate_fields_for_doctype=False)
    make_property_setter("User", "language", "description", "Muda-se no portal Stratechna, em «Os Meus Dados».",
                         "Small Text", validate_fields_for_doctype=False)

    # 5. a moeda do CRM vem em INR (rupia) de fábrica; fica a do tenant (EUR). Só se mexe enquanto for a de
    #    fábrica — quem escolheu outra moeda de propósito não é tocado.
    if frappe.db.exists("DocType", "FCRM Settings") and \
            frappe.db.get_single_value("FCRM Settings", "currency") == "INR":
        moeda = frappe.db.get_single_value("Global Defaults", "default_currency") or "EUR"
        if moeda != "INR" and frappe.db.exists("Currency", moeda):
            frappe.db.set_single_value("FCRM Settings", "currency", moeda)

    frappe.db.commit()
    from frappe.translate import clear_cache
    clear_cache()
    print(f"Orbit: línguas pt/en/es/fr activas; {apagadas} traduções antigas dos módulos retiradas")
