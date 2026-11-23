"""Fluxos do CRM em português, sobre o motor de automações do próprio Frappe (23-11-2026).

Decisão do Vítor: «não quero nada repetido, quero apenas as funcionalidades das apps que temos sobre uma nova UI».
Por isso não há motor nosso: os fluxos são `Automation Flow` do Frappe (o mesmo que o CRM clássico edita), com as
ações do Frappe e do CRM. Este módulo instala, **desligados**, os 10 fluxos de referência do CRM
(`crm.automation.reference_flows`) adaptados — e 3 que eles não cobrem. Edições face ao original (ver
docs/PLANO-FLUXOS-ORBIT.md §5):

* tudo em português (títulos, textos das tarefas, razões da pontuação, avisos) e modelos de email nossos em PT;
* pessoas de exemplo (`crm.rep1@example.com`…) trocadas pelo **gestor comercial** do tenant (o 1.º System Manager
  humano, ou `orbit_fluxos_gestor` no site_config) — muda-se no ecrã;
* origens reais do Orbit (Formulário do site, Reunião marcada no site, Loja Online, …) em vez de «Website»;
* emails gratuitos portugueses (sapo.pt, iol.pt, …) e cargos em português (diretor, gerente, sócio-gerente, …);
* negócio de valor alto a partir de 5 000 € (o original: 50 000);
* boas-vindas: o seguimento aos 2 dias só sai se a lead ainda não respondeu;
* lead qualificada: só atribui (o original mandava também um email de seguimento à lead);
* novos: «Lead nova — contactar em 24 h», «Negócio ganho — arranque», «Negócio perdido — voltar aos 90 dias».

`instalar()` só cria os que faltam (pelo título): nunca muda um fluxo que alguém já editou.
"""
from __future__ import annotations

import frappe

PREFIXO = "Orbit · "

TEMPLATES = {
    "Orbit · Boas-vindas (pedido pelo site)": (
        "Obrigado pelo seu contacto, {{ doc.first_name }}",
        "<p>Olá {{ doc.first_name }},</p><p>Obrigado por nos ter contactado. Conte-nos o que precisa de resolver e "
        "damos seguimento ainda hoje.</p>",
    ),
    "Orbit · Apresentação (contacto nosso)": (
        "Apresentação, {{ doc.first_name }}",
        "<p>Olá {{ doc.first_name }},</p><p>Trabalhamos com empresas como a {{ doc.organization or 'sua' }} "
        "precisamente nesta área. Tem disponibilidade para uma conversa curta?</p>",
    ),
    "Orbit · Seguimento da lead": (
        "Seguimento, {{ doc.first_name }}",
        "<p>Olá {{ doc.first_name }},</p><p>Volto ao contacto de há dois dias — continuamos ao dispor para ajudar.</p>",
    ),
}

LIVRES = ["gmail.com", "hotmail.com", "outlook.com", "outlook.pt", "live.com", "live.com.pt", "msn.com", "yahoo.com",
          "icloud.com", "sapo.pt", "iol.pt", "clix.pt", "netcabo.pt", "mail.pt", "aol.com"]
CARGOS = ["diretor", "director", "gerente", "administrador", "sócio", "socio", "presidente", "ceo", "fundador",
          "proprietário", "proprietario", "dono", "chief", "head", "founder", "owner", "manager"]
GRANDES = ["201-500", "501-1000", "1000+"]
ENTRADA = ["Website", "Formulário do site", "Reunião marcada no site", "Marcação de reunião", "Loja Online",
           "Proposta Online", "Pesquisa na Internet", "Referência externa", "Reference", "Existing Customer",
           "Email", "Chat", "Caixa de correio", "Telefone", "Web Form", "WebSite Visit"]
QUENTE, MORNA, QUENTE_TOTAL = 45, 25, 50
VALOR_ALTO, CONFIANCA, SILENCIO = 5000, 70, 3


def gestor() -> str:
    g = frappe.conf.get("orbit_fluxos_gestor")
    if g and frappe.db.exists("User", g):
        return g
    for u in frappe.get_all("Has Role", filters={"role": "System Manager", "parenttype": "User"}, pluck="parent"):
        if u not in ("Administrator", "Guest") and "@" in u and frappe.db.get_value("User", u, "enabled"):
            return u
    return "Administrator"


def _h():
    from crm.automation import reference_flows as R
    return R


def _tarefa(R, idx, key, titulo, dias, doctype, dono, target="trigger", **extra):
    valores = {"title": titulo, "status": "Todo", "priority": "Medium", "assigned_to": dono,
               "reference_doctype": doctype, "reference_docname": "{{ doc.name }}",
               "due_date": f"{{{{ frappe.utils.add_days(frappe.utils.nowdate(), {dias}) }}}}"}
    return R.action(idx, key, "CreateDocument", {"doctype": "CRM Task", "values": valores}, target=target, **extra)


def _pontos(key):
    return f"{key}_pontos"


def fluxos() -> list:
    R = _h()
    G = gestor()
    out = []

    # 1. Boas-vindas pela origem; seguimento aos 2 dias só se não respondeu
    out.append({**R.flow(PREFIXO + "Boas-vindas à lead (pela origem)", "CRM Lead", "Doc Created"), "actions": [
        R.step(1, "pela_origem", "If", condition=f"doc.source in {ENTRADA}"),
        R.email_step(2, "boas_vindas_site", "Orbit · Boas-vindas (pedido pelo site)", parent=1, branch="If"),
        R.email_step(3, "apresentacao", "Orbit · Apresentação (contacto nosso)", parent=1, branch="Else"),
        R.step(4, "esperar_2_dias", "Wait", params={"value": 2, "unit": "Days"}),
        R.quiet_check_step(5, "ainda_sem_resposta"),
        R.email_step(6, "seguimento", "Orbit · Seguimento da lead", parent=5, branch="If"),
    ]})

    # 2. Temperatura pela resposta
    out.append({**R.flow(PREFIXO + "Temperatura da lead pela resposta", "Communication", "Doc Created"),
                "filters": frappe.as_json([["communication_type", "=", "Communication"], ["sent_or_received", "=", "Sent"],
                                           ["reference_doctype", "=", "CRM Lead"]]),
                "relationships": frappe.as_json([{"alias": "lead", "source": "trigger", "relationship": "reference",
                                                  "target_doctype": "CRM Lead"}]),
                "actions": [
                    R.temperature(1, "morna", "Warm"),
                    R.step(2, "esperar_resposta", "WaitForEvent", params={
                        "event_name": "crm.prospect_message_received", "correlation_key": "{{ doc.message_id or doc.name }}",
                        "timeout_value": 3, "timeout_unit": "Days"}),
                    R.step(3, "respondeu", "If", condition=R.EVENT_MATCHED),
                    R.temperature(4, "quente", "Hot", parent=3, branch="If"),
                    R.score(5, "bonus_resposta", 15, "Respondeu em 3 dias", target="lead", parent=3, branch="If"),
                    R.temperature(6, "fria", "Cold", parent=3, branch="Else"),
                    R.score(7, "penalizacao_silencio", -10, "Sem resposta em 3 dias", target="lead", parent=3, branch="Else"),
                ]})

    # 3. Pontuação pelo perfil
    sinais = [("email_empresa", "Email de empresa", f'doc.email and doc.email.split("@")[-1].lower() not in {LIVRES}', 15),
              ("empresa_conhecida", "Empresa indicada", '(doc.organization or "") != ""', 10),
              ("cargo_decisor", "Cargo de decisão", " or ".join(f'"{c}" in (doc.job_title or "").lower()' for c in CARGOS), 15),
              ("empresa_grande", "Empresa grande", f"doc.no_of_employees in {GRANDES}", 10)]
    linhas, idx = [], 1
    for key, rot, cond, pts in sinais:
        linhas.append(R.step(idx, key, "If", condition=cond))
        linhas.append(R.score(idx + 1, _pontos(key), pts, rot, parent=idx, branch="If"))
        idx += 2
    linhas += [R.step(idx, "entrada", "If", condition=f"doc.source in {ENTRADA}"),
               R.score(idx + 1, _pontos("entrada"), 20, "Veio ter connosco", parent=idx, branch="If"),
               R.score(idx + 2, _pontos("saida"), 5, "Contacto nosso", parent=idx, branch="Else")]
    chaves = [_pontos(k[0]) for k in sinais] + [_pontos("entrada"), _pontos("saida")]
    total = " + ".join(f'context["steps"].get("{k}", {{}}).get("delta", 0)' for k in chaves)
    b = idx + 3
    linhas += [R.step(b, "e_quente", "If", condition=f"({total}) >= {QUENTE}"),
               R.temperature(b + 1, "marcar_quente", "Hot", target="trigger", parent=b, branch="If"),
               R.step(b + 2, "e_morna", "If", condition=f"({total}) >= {MORNA}", parent=b, branch="Else"),
               R.temperature(b + 3, "marcar_morna", "Warm", target="trigger", parent=b + 2, branch="If"),
               R.temperature(b + 4, "marcar_fria", "Cold", target="trigger", parent=b + 2, branch="Else")]
    out.append({**R.flow(PREFIXO + "Pontuação da lead pelo perfil", "CRM Lead", "Doc Created"), "actions": linhas})

    # 4. Lead contactada por email → fica com o gestor comercial
    out.append({**R.flow(PREFIXO + "Lead contactada por email — responsável", "Communication", "Doc Created"),
                "filters": frappe.as_json([["communication_type", "=", "Communication"], ["sent_or_received", "=", "Sent"],
                                           ["reference_doctype", "=", "CRM Lead"]]),
                "relationships": frappe.as_json([{"alias": "lead", "source": "trigger", "relationship": "reference",
                                                  "target_doctype": "CRM Lead"}]),
                "actions": [R.assign_step(1, "atribuir", G, "Enviámos um email a esta lead", target="lead")]})

    # 5. Lead quente → gestor
    out.append({**R.flow(PREFIXO + "Lead quente vai para o gestor", "CRM Lead", "Doc Updated"), "actions": [
        R.step(1, "e_quente", "If", condition=f"(doc.lead_score or 0) >= {QUENTE_TOTAL}"),
        R.assign_step(2, "atribuir_quente", G, "Pontuação chegou a {{ doc.lead_score }}", parent=1, branch="If")]})

    # 6. Lead qualificada → responsável (sem email à lead)
    out.append({**R.flow(PREFIXO + "Lead qualificada — responsável", "CRM Lead", "Field Value Changed"),
                "trigger_field": "status", "to_value": "Qualified",
                "actions": [R.assign_step(1, "atribuir_qualificada", G, "A lead foi qualificada")]})

    # 7. Pontuação pelo andamento
    sinais2 = [("contactada", "Contactámos a lead", 'doc.status == "Contacted"', 5),
               ("acompanhamento", "Lead em acompanhamento", 'doc.status == "Nurture"', 10),
               ("qualificada", "Lead qualificada", 'doc.status == "Qualified"', 20),
               ("perdida", "Lead desqualificada", 'doc.status in ["Unqualified", "Junk"]', -30)]
    l2, idx = [], 1
    for key, rot, cond, pts in sinais2:
        l2.append(R.step(idx, key, "If", condition=cond))
        l2.append(R.score(idx + 1, _pontos(key), pts, rot, parent=idx, branch="If"))
        idx += 2
    l2 += [R.step(idx, "agora_quente", "If", condition=f"(doc.lead_score or 0) >= {QUENTE_TOTAL}"),
           R.temperature(idx + 1, "andamento_quente", "Hot", target="trigger", parent=idx, branch="If"),
           R.step(idx + 2, "agora_morna", "If", condition="(doc.lead_score or 0) >= 20", parent=idx, branch="Else"),
           R.temperature(idx + 3, "andamento_morna", "Warm", target="trigger", parent=idx + 2, branch="If"),
           R.temperature(idx + 4, "andamento_fria", "Cold", target="trigger", parent=idx + 2, branch="Else")]
    out.append({**R.flow(PREFIXO + "Pontuação da lead pelo andamento", "CRM Lead", "Field Value Changed"),
                "trigger_field": "status", "actions": l2})

    # 8. Lead qualificada passa a negócio, com tarefa de arranque
    conv = R.convert_step(1, "converter")
    out.append({**R.flow(PREFIXO + "Lead qualificada passa a negócio", "CRM Lead", "Field Value Changed"),
                "trigger_field": "status", "to_value": "Qualified", "condition": "doc.converted == 0",
                "actions": [conv,
                            _tarefa(R, 2, "primeira_reuniao", "Primeira reunião — {{ doc.organization or doc.lead_name }}", 2,
                                    "CRM Deal", "{{ trigger.lead_owner or '' }}", target="deal"),
                            R.score(3, "bonus_qualificada", 25, "Passou a negócio")]})

    # 9. Negócio muda de fase → seguimento; 3 dias sem resposta baixa a pontuação
    seguir = _tarefa(R, 1, "seguimento", "Seguimento — {{ doc.organization or doc.name }}", 3, "CRM Deal", "{{ doc.deal_owner or '' }}")
    seguir["related_condition"] = frappe.as_json({"type": "RelatedNotExists", "source": "trigger", "relationship": "tasks",
                                                  "filters": [["status", "not in", ["Done", "Canceled"]]]})
    out.append({**R.flow(PREFIXO + "Negócio mudou de fase — seguimento", "CRM Deal", "Field Value Changed"),
                "trigger_field": "status",
                "relationships": frappe.as_json([{"alias": "lead", "source": "trigger", "relationship": "lead"}]),
                "actions": [seguir, R.step(2, "esperar_3_dias", "Wait", params={"value": 3, "unit": "Days"}),
                            R.quiet_check_step(3, "sem_resposta"),
                            R.score(4, "ficou_calado", -5, "Sem resposta depois da mudança de fase", target="lead", parent=3, branch="If"),
                            R.score(5, "respondeu", 5, "Respondeu depois da mudança de fase", target="lead", parent=3, branch="Else")]})

    # 10. Negócio de valor alto
    out.append({**R.flow(PREFIXO + "Negócio de valor alto", "CRM Deal", "Doc Updated"),
                "condition": f"(doc.expected_deal_value or doc.deal_value or 0) >= {VALOR_ALTO}",
                "actions": [
                    R.step(1, "vai_fechar", "If", condition=f"(doc.probability or 0) >= {CONFIANCA}"),
                    _tarefa(R, 2, "plano_fecho", "Plano de fecho — {{ doc.organization or doc.name }}", 2, "CRM Deal",
                            "{{ doc.deal_owner or '' }}", parent=1, branch="If"),
                    R.assign_step(3, "revisao", G, "Negócio de valor alto com {{ doc.probability }} % — precisa de revisão",
                                  parent=1, branch="Else"),
                    R.notify_step(4, "aviso_gestor", "System", [G], "Negócio de valor alto mexeu: {{ doc.organization or doc.name }}",
                                  "<p>{{ doc.organization or doc.name }}: {{ doc.expected_deal_value or doc.deal_value }} €, "
                                  "{{ doc.probability }} % de confiança, fecho previsto {{ doc.expected_closure_date }}.</p>"),
                    R.step(5, "esperar", "Wait", params={"value": SILENCIO, "unit": "Days"}),
                    R.quiet_check_step(6, "ninguem_respondeu"),
                    R.notify_step(7, "escalar", "System", [G], f"Sem contacto há {SILENCIO} dias: {{{{ doc.organization or doc.name }}}}",
                                  "<p>Nada voltou num negócio de valor alto. Vale um telefonema antes da data de fecho.</p>",
                                  parent=6, branch="If"),
                    _tarefa(R, 8, "telefonar", "Telefonar — {{ doc.organization or doc.name }}", 0, "CRM Deal",
                            "{{ doc.deal_owner or '' }}", parent=6, branch="If"),
                ]})

    # 11–13 (não existem nos de referência)
    out.append({**R.flow(PREFIXO + "Lead nova — contactar em 24 h", "CRM Lead", "Doc Created"),
                "actions": [_tarefa(R, 1, "contactar", "Contactar {{ doc.lead_name or doc.email }}", 1, "CRM Lead",
                                    "{{ doc.lead_owner or '' }}")]})
    out.append({**R.flow(PREFIXO + "Negócio ganho — arranque com o cliente", "CRM Deal", "Field Value Changed"),
                "trigger_field": "status", "to_value": "Won",
                "actions": [_tarefa(R, 1, "arranque", "Arranque com o cliente — {{ doc.organization or doc.name }}", 2,
                                    "CRM Deal", "{{ doc.deal_owner or '' }}")]})
    out.append({**R.flow(PREFIXO + "Negócio perdido — voltar a contactar aos 90 dias", "CRM Deal", "Field Value Changed"),
                "trigger_field": "status", "to_value": "Lost",
                "actions": [_tarefa(R, 1, "voltar", "Voltar a contactar — {{ doc.organization or doc.name }}", 90,
                                    "CRM Deal", "{{ doc.deal_owner or '' }}")]})
    for f in out:
        f["automation_user"] = "Administrator"
    return out


def _modelos_email():
    for nome, (assunto, corpo) in TEMPLATES.items():
        if not frappe.db.exists("Email Template", nome):
            frappe.get_doc({"doctype": "Email Template", "name": nome, "subject": assunto, "response": corpo,
                            "use_html": 1, "response_html": corpo, "reference_doctype": "CRM Lead"}).insert(ignore_permissions=True)


def instalar():
    """after_migrate: cria os que faltam, desligados. Nunca toca num fluxo que já exista com o mesmo título."""
    if not (frappe.db.exists("DocType", "Automation Flow") and frappe.db.exists("DocType", "CRM Lead")):
        return
    try:
        _h()
    except ImportError:
        return
    _modelos_email()
    for f in fluxos():
        if frappe.db.exists("Automation Flow", {"title": f["title"]}):
            continue
        f["enabled"] = 0
        try:
            frappe.get_doc(f).insert(ignore_permissions=True)
        except Exception:
            frappe.log_error(title=f"Orbit: fluxo {f['title']}")
