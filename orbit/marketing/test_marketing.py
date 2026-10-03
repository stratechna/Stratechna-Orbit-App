"""Testes do módulo Marketing. Correm no GitHub (workflow «Testes do Orbit»),
num site novo, sem tocar em nenhum tenant."""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_to_date, now_datetime

from orbit.marketing import consentimento, destinatarios, envio, modelos, publico


def _contacto(email, estado="Pode receber", base="consentimento", assuntos=None, nome="Ana"):
    existente = frappe.db.get_value("Contact Email", {"email_id": email}, "parent")
    if existente:
        return frappe.get_doc("Contact", existente)
    return frappe.get_doc({"doctype": "Contact", "first_name": nome,
                           "email_ids": [{"email_id": email, "is_primary": 1}],
                           "mkt_estado": estado, "mkt_base_legal": base if estado == "Pode receber" else None,
                           "mkt_assuntos": assuntos}).insert(ignore_permissions=True)


def _passado():
    return str(add_to_date(now_datetime(), minutes=-1))


class TestMarketing(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        consentimento.garantir()
        frappe.clear_cache(doctype="Contact")
        for nome in ("Novidades", "Promoções"):
            if not frappe.db.exists("Assunto de Marketing", nome):
                frappe.get_doc({"doctype": "Assunto de Marketing", "nome": nome}).insert()
        _contacto("pode@exemplo.invalid", assuntos="Promoções, Novidades")
        _contacto("pode2@exemplo.invalid", assuntos="Novidades", nome="Rui")
        _contacto("semregisto@exemplo.invalid", estado="Sem registo")
        _contacto("retirou@exemplo.invalid", estado="Retirou")
        if not frappe.db.exists("Segmento de Marketing", "Todos"):
            frappe.get_doc({"doctype": "Segmento de Marketing", "nome": "Todos"}).insert()
        if not frappe.db.exists("Segmento de Marketing", "Promoções"):
            frappe.get_doc({"doctype": "Segmento de Marketing", "nome": "Promoções",
                            "regras": [{"regra": "Assunto de interesse", "valor": "Promoções"}]}).insert()
        frappe.db.commit()

    def setUp(self):
        frappe.set_user("Administrator")

    def _campanha(self, **kw):
        return frappe.get_doc({"doctype": "Campanha de Marketing", "titulo": "Teste", "modelo": "Novidades",
                               "linha_assunto": "Olá {{nome}}", "texto": "{{nome}}, isto é um teste.",
                               "cta_texto": "Ver", "cta_url": "https://exemplo.invalid/a",
                               "segmentos": [{"segmento": "Todos"}], **kw}).insert()

    def _sair(self, c):
        c.submeter()
        c.aprovar()
        c.agendar(_passado())
        envio.processar()

    def test_campos_de_consentimento(self):
        meta = frappe.get_meta("Contact")
        for campo in consentimento.NOMES:
            self.assertTrue(meta.has_field(campo), campo)
        self.assertTrue(meta.track_changes)

    def test_entrada_no_ecra_de_apps(self):
        from orbit import apps, marca
        marca.repor_atalhos()
        icone = frappe.db.get_value("Desktop Icon", {"label": "Marketing"},
                                    ["link", "logo_url", "hidden"], as_dict=True)
        self.assertEqual(icone.link, "/app/campanha-de-marketing")
        self.assertEqual(icone.logo_url, "/assets/orbit/icons/apps/marketing.svg")
        self.assertFalse(icone.hidden)
        self.assertIn("marketing", apps.activas())

    def test_ponte_do_portal(self):
        from orbit.marketing import mensagem, ponte
        r = ponte.definicoes({"marca_nome": "Exemplo", "cor_primaria": "#0b3d91", "plano_contactos": 1000,
                              "redes": {"facebook": "https://facebook.com/x"}, "chave_desconhecida": "x"})
        self.assertTrue(r["ok"])
        frappe.clear_document_cache("Definicoes de Marketing", "Definicoes de Marketing")
        d = mensagem.definicoes()
        self.assertEqual((d.marca_nome, d.cor_primaria, d.plano_contactos), ("Exemplo", "#0b3d91", 1000))
        self.assertFalse(d.get("chave_desconhecida"))
        ponte.definicoes({"plano_contactos": 0})

        o = ponte.opcoes({})
        self.assertIn("Todos", [s["nome"] for s in o["segmentos"]])
        self.assertIn("Novidades", o["assuntos"])

        pedido = {"portal_ref": "portal-teste-1", "titulo": "Do portal", "modelo": "Promoção",
                  "linha_assunto": "Só esta semana", "texto": "Texto da IA.", "segmentos": ["Todos", "Não existe"],
                  "assunto": "Novidades", "estado": "Enviada", "aprovada_por": "admin@stratechna.com",
                  "itens": [{"titulo": "A", "texto": "b"}], "produtos": [{"nome": "P", "preco": "1 €"}]}
        r = ponte.campanha(pedido)
        self.assertTrue(r["ok"], r)
        c = frappe.get_doc("Campanha de Marketing", r["nome"])
        self.assertEqual((c.estado, c.origem), ("Para aprovação", "Portal"))
        self.assertEqual([s.segmento for s in c.segmentos], ["Todos"])
        self.assertTrue(ponte.campanha(pedido)["repetido"])
        self.assertFalse(ponte.campanha({**pedido, "portal_ref": "portal-teste-2", "segmentos": ["Não existe"]})["ok"])
        self.assertFalse(ponte.campanha({**pedido, "portal_ref": "portal-teste-3", "modelo": "Inventado"})["ok"])
        self.assertIn("portal-teste-1", [x.portal_ref for x in ponte.resultados({})["campanhas"]])

    def test_campanha_nova_nasce_sempre_em_rascunho(self):
        c = self._campanha(estado="Enviada", origem="Portal")
        self.assertEqual((c.estado, c.origem), ("Rascunho", "Orbit"))

    def test_devolucao_e_queixa_suprimem(self):
        from orbit.marketing import ponte
        _contacto("devolve@exemplo.invalid", nome="Dev")
        _contacto("queixa@exemplo.invalid", nome="Que")
        self.assertTrue(ponte.evento({"tipo": "devolvido", "emails": ["devolve@exemplo.invalid"],
                                      "detalhe": "550 5.1.1 user unknown"})["ok"])
        self.assertTrue(ponte.evento({"tipo": "queixa", "emails": ["queixa@exemplo.invalid"]})["ok"])
        self.assertFalse(ponte.evento({"tipo": "outro"})["ok"])
        emails = {r["email"] for r in destinatarios.contactaveis()}
        self.assertNotIn("devolve@exemplo.invalid", emails)
        self.assertNotIn("queixa@exemplo.invalid", emails)
        nome = frappe.db.get_value("Contact Email", {"email_id": "queixa@exemplo.invalid"}, "parent")
        self.assertEqual(frappe.db.get_value("Contact", nome, "mkt_estado"), "Retirou")
        nome = frappe.db.get_value("Contact Email", {"email_id": "devolve@exemplo.invalid"}, "parent")
        self.assertEqual(frappe.db.get_value("Contact", nome, "mkt_estado"), "Pode receber")

    def test_travao_para_a_campanha(self):
        c = self._campanha()
        c.submeter()
        c.aprovar()
        c.agendar(_passado())
        envio.processar()
        c.reload()
        for n in range(envio.AMOSTRA):
            frappe.get_doc({"doctype": "Envio de Marketing", "campanha": c.name, "email": f"t{n}@exemplo.invalid",
                            "estado": "Devolvido" if n < 10 else "Enviado", "token": f"{n:032d}"}).insert(ignore_permissions=True)
        frappe.get_doc({"doctype": "Envio de Marketing", "campanha": c.name, "email": "fila@exemplo.invalid",
                        "estado": "Na fila", "token": "f" * 32}).insert(ignore_permissions=True)
        c.db_set("estado", "A enviar")
        self.assertIn("devoluções", envio.travao(c.name))
        envio.despachar(c)
        c.reload()
        self.assertEqual(c.estado, "Pausada")
        self.assertEqual(frappe.db.get_value("Envio de Marketing", {"token": "f" * 32}, "estado"), "Na fila")

    def test_automacoes_com_loja_simulada(self):
        from unittest.mock import patch
        from frappe.utils import add_days, nowdate
        from orbit.marketing import automacoes, loja
        _contacto("cliente@exemplo.invalid", base="cliente", nome="Cli")
        encomenda = {"name": "SO-1", "email": "cliente@exemplo.invalid", "data": add_days(nowdate(), -20),
                     "creation": add_days(nowdate(), -20),
                     "itens": [{"item_code": "FORNO", "item_name": "Forno", "item_group": "Fornos", "qty": 1}]}
        produtos = [{"item_code": "LUVAS", "nome": "Luvas", "url": "https://loja.invalid/?post_type=product&p=7",
                     "preco": "9,90 €", "imagem": None}]
        a = frappe.get_doc({"doctype": "Automacao de Marketing", "tipo": "Venda cruzada", "dias_apos": 14,
                            "linha_assunto": "Para acompanhar", "texto": "{{nome}}, veja isto."}).insert()
        a.submeter()
        a.aprovar()
        a.db_set("activa_desde", add_days(nowdate(), -30))
        a.reload()
        with patch.object(loja, "encomendas", return_value=[encomenda]), \
                patch.object(loja, "mais_vendidos", return_value=produtos):
            r = automacoes.correr_uma(a)
            self.assertEqual(r["entraram"], 1, r)
            self.assertEqual(automacoes.correr_uma(a)["entraram"], 0)        # uma vez por motivo
        e = frappe.get_all("Envio de Marketing", filters={"automacao": a.name}, fields=["ref", "estado", "dados", "token"])[0]
        self.assertEqual((e.ref, e.estado), ("venda_cruzada:SO-1", "Na fila"))
        envio.processar()                                                   # simulação
        self.assertEqual(frappe.db.get_value("Envio de Marketing", {"token": e.token}, "estado"), "Simulado")
        # a ligação do produto DELE: a posição vem da própria mensagem, que
        # põe o botão primeiro quando o há (esta automação não tem)
        import json as _json
        from orbit.marketing import mensagem
        lig = modelos.ligacoes(mensagem.conteudo(a, _json.loads(e.dados)))
        publico.ir(e.token, lig.index(produtos[0]["url"]))
        self.assertEqual(frappe.local.response.get("location"), produtos[0]["url"])
        # o tecto de frequência: outra automação não lhe escreve na mesma semana
        b = frappe.get_doc({"doctype": "Automacao de Marketing", "tipo": "Depois da compra", "dias_apos": 7,
                            "linha_assunto": "Obrigado", "texto": "Obrigado."}).insert()
        b.submeter()
        b.aprovar()
        b.db_set("activa_desde", add_days(nowdate(), -30))
        b.reload()
        with patch.object(loja, "encomendas", return_value=[encomenda]):
            self.assertEqual(automacoes.correr_uma(b)["entraram"], 0)
        a.pausar()
        a.reload()
        self.assertEqual(a.estado, "Pausada")

    def test_automacao_fora_do_plano(self):
        from orbit.marketing import ponte
        ponte.definicoes({"plano_automacoes": "boas_vindas"})
        frappe.clear_document_cache("Definicoes de Marketing", "Definicoes de Marketing")
        try:
            with self.assertRaises(frappe.ValidationError):
                frappe.get_doc({"doctype": "Automacao de Marketing", "tipo": "Reactivação",
                                "linha_assunto": "x", "texto": "y"}).insert()
        finally:
            ponte.definicoes({"plano_automacoes": ""})
            frappe.clear_document_cache("Definicoes de Marketing", "Definicoes de Marketing")

    def test_menu_e_galeria(self):
        from orbit.marketing import menu
        from orbit.marketing.page.modelos_de_email.modelos_de_email import galeria
        menu.garantir()
        itens = [i.link_to for i in frappe.get_doc("Workspace Sidebar", "Marketing").items]
        for alvo in ("Campanha de Marketing", "Automacao de Marketing", "Segmento de Marketing",
                     "Supressao de Marketing", "Definicoes de Marketing", "modelos-de-email"):
            self.assertIn(alvo, itens)
        g = galeria()
        self.assertEqual(len(g), 12)
        self.assertTrue(all("<mj-" not in m["html"] for m in g))

    def test_aprovada_no_portal_entra_aprovada(self):
        from orbit.marketing import ponte
        r = ponte.campanha({"portal_ref": "portal-aprovada-1", "titulo": "Do portal", "modelo": "Novidades",
                            "linha_assunto": "x", "texto": "y", "segmentos": ["Todos"],
                            "aprovada_pelo_cliente": "cliente@exemplo.invalid", "aprovada_pelo_cliente_em": "2026-10-03"})
        self.assertEqual(frappe.db.get_value("Campanha de Marketing", r["nome"], "estado"), "Aprovada")

    def test_volume_do_plano(self):
        from orbit.marketing import ponte, volume
        ponte.definicoes({"plano_envios_mes": 1})
        frappe.clear_document_cache("Definicoes de Marketing", "Definicoes de Marketing")
        try:
            frappe.get_doc({"doctype": "Envio de Marketing", "email": "vol@exemplo.invalid", "estado": "Enviado",
                            "token": "v" * 32}).insert(ignore_permissions=True)
            self.assertFalse(volume.cabe(1))
            c = self._campanha()
            with self.assertRaises(frappe.ValidationError):
                c.submeter()
            r = ponte.resumo_mes({})
            self.assertTrue(r["ok"])
            self.assertEqual(r["volume"]["limite"], 1)
        finally:
            ponte.definicoes({"plano_envios_mes": 0})
            frappe.clear_document_cache("Definicoes de Marketing", "Definicoes de Marketing")

    def test_so_quem_pode_receber(self):
        emails = {r["email"] for r in destinatarios.contactaveis()}
        self.assertIn("pode@exemplo.invalid", emails)
        self.assertNotIn("semregisto@exemplo.invalid", emails)
        self.assertNotIn("retirou@exemplo.invalid", emails)

    def test_segmento_por_assunto(self):
        self.assertEqual({r["email"] for r in destinatarios.do_segmento("Promoções")}, {"pode@exemplo.invalid"})

    def test_previsualizar_rascunho_sem_gravar(self):
        from orbit.marketing.mensagem import previsualizar_rascunho
        r = previsualizar_rascunho({"modelo": "Promoção", "titulo_email": "Olá {{nome}}", "linha_assunto": "Saldos",
                                    "destaque_texto": "-30%", "produtos": [{"nome": "Cadeira", "preco": "49 €"}]})
        self.assertEqual(r["assunto"], "Saldos")
        self.assertIn("Olá Maria", r["html"])
        self.assertIn("-30%", r["html"])
        self.assertIn("Cadeira", r["html"])

    def test_doze_modelos(self):
        for chave in modelos.MODELOS:
            html = modelos.gerar(modelos.exemplo(chave), {}, ir=lambda u: u or "#", remover="#",
                                 motivo="m", legal_texto="L")
            self.assertNotIn("<mj-", html, chave)

    def test_ciclo_em_simulacao(self):
        c = self._campanha(assunto_marketing="Novidades")
        self.assertEqual(c.estado, "Rascunho")
        c.submeter()
        self.assertEqual(c.estado, "Para aprovação")
        with self.assertRaises(frappe.ValidationError):
            c.rejeitar("")
        c.aprovar()
        self.assertEqual(c.estado, "Aprovada")
        c.agendar(_passado())
        envio.processar()
        envio.processar()
        c.reload()
        self.assertEqual(c.estado, "Enviada")
        self.assertTrue(c.simulada)
        estados = frappe.get_all("Envio de Marketing", filters={"campanha": c.name}, pluck="estado")
        self.assertTrue(estados and set(estados) == {"Simulado"}, estados)

    def test_fora_de_rascunho_nao_se_altera(self):
        c = self._campanha()
        c.submeter()
        c.reload()
        c.linha_assunto = "Outra coisa"
        with self.assertRaises(frappe.ValidationError):
            c.save()

    def test_envio_real_leva_remocao_num_clique(self):
        if not frappe.db.exists("Email Account", "Marketing Teste"):
            frappe.get_doc({"doctype": "Email Account", "email_account_name": "Marketing Teste",
                            "email_id": "novidades@exemplo.invalid", "enable_outgoing": 1,
                            "smtp_server": "localhost", "smtp_port": "25", "no_smtp_authentication": 1,
                            "awaiting_password": 0}).insert(ignore_permissions=True)
        d = frappe.get_single("Definicoes de Marketing")
        d.update({"email_account": "Marketing Teste", "legal_texto": "Exemplo, Lda\nRua X\nNIF 500000000",
                  "modo": "Real", "limite_hora": 600})
        d.save()
        frappe.clear_document_cache("Definicoes de Marketing", "Definicoes de Marketing")
        try:
            c = self._campanha()
            self._sair(c)
            envios = frappe.get_all("Envio de Marketing", filters={"campanha": c.name},
                                    fields=["estado", "email_queue", "erro"])
            self.assertTrue(envios and all(x.estado == "Enviado" and x.email_queue for x in envios), envios)
            m = frappe.db.get_value("Email Queue", envios[0].email_queue, "message")
            self.assertIn("List-Unsubscribe: <", m)
            self.assertIn("List-Unsubscribe-Post: List-Unsubscribe=One-Click", m)
            self.assertIn("orbit.marketing.publico.aberto", m)
            self.assertNotIn("X-List-Unsubscribe", m)
            self.assertIn("X-Orbit-Envio:", m)
            self.assertIn("X-Orbit-Tenant:", m)
        finally:
            d.reload()
            d.modo = "Simular"
            d.save()
            frappe.clear_document_cache("Definicoes de Marketing", "Definicoes de Marketing")

    def test_remover_escreve_no_crm(self):
        c = self._campanha(assunto_marketing="Novidades")
        self._sair(c)
        t = frappe.get_all("Envio de Marketing", filters={"campanha": c.name, "email": "pode2@exemplo.invalid"},
                           pluck="token")[0]
        self.assertEqual(publico.remover(t, tudo=False)["saiu_de"], "Novidades")
        self.assertNotIn("pode2@exemplo.invalid", {r["email"] for r in destinatarios.contactaveis("Novidades")})
        self.assertIn("pode2@exemplo.invalid", {r["email"] for r in destinatarios.contactaveis()})
        publico.remover(t, tudo=True)
        nome = frappe.db.get_value("Contact Email", {"email_id": "pode2@exemplo.invalid"}, "parent")
        self.assertEqual(frappe.db.get_value("Contact", nome, "mkt_estado"), "Retirou")
        self.assertNotIn("pode2@exemplo.invalid", {r["email"] for r in destinatarios.contactaveis()})

    def test_clique_so_por_indice(self):
        c = self._campanha()
        self._sair(c)
        t = frappe.get_all("Envio de Marketing", filters={"campanha": c.name}, pluck="token")[0]
        publico.ir(t, 0)
        self.assertEqual(frappe.local.response.get("location"), "https://exemplo.invalid/a")
        with self.assertRaises(frappe.DoesNotExistError):
            publico.ir(t, 7)
