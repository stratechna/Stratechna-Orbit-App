"""Testes da marcação de reuniões. Correm no GitHub, em site novo.

Testa-se sobretudo o que não dá erro quando está errado: um iCalendar mal
formado não rebenta — é **recusado em silêncio** pelo cliente de calendário, e
o que se vê é uma agenda que não actualiza, sem nada no log a dizer porquê.
"""

import datetime

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_to_date, now_datetime

from orbit import marcacao


class TestMarcacao(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        marcacao.garantir()
        frappe.clear_cache(doctype="Event")
        frappe.clear_cache(doctype="User")

    # ── fusão de intervalos ────────────────────────────────────────────────

    def test_juntar_funde_sobreposicoes(self):
        junto = marcacao._juntar([
            {"inicio": "2026-10-06T09:00", "fim": "2026-10-06T10:00"},
            {"inicio": "2026-10-06T09:30", "fim": "2026-10-06T11:00"},
        ])
        self.assertEqual(junto, [{"inicio": "2026-10-06T09:00", "fim": "2026-10-06T11:00"}])

    def test_juntar_nao_funde_o_que_nao_toca(self):
        junto = marcacao._juntar([
            {"inicio": "2026-10-06T09:00", "fim": "2026-10-06T10:00"},
            {"inicio": "2026-10-06T11:00", "fim": "2026-10-06T12:00"},
        ])
        self.assertEqual(len(junto), 2)

    def test_juntar_aceita_vazio(self):
        self.assertEqual(marcacao._juntar([]), [])

    def test_juntar_contido_dentro_de_outro(self):
        """O intervalo pequeno dentro do grande não pode encurtar o grande."""
        junto = marcacao._juntar([
            {"inicio": "2026-10-06T09:00", "fim": "2026-10-06T18:00"},
            {"inicio": "2026-10-06T10:00", "fim": "2026-10-06T11:00"},
        ])
        self.assertEqual(junto, [{"inicio": "2026-10-06T09:00", "fim": "2026-10-06T18:00"}])

    # ── iCalendar ──────────────────────────────────────────────────────────

    def test_escapar_virgulas_e_quebras(self):
        self.assertEqual(marcacao._escapar("a, b; c\nd"), "a\\, b\\; c\\nd")

    def test_dobrar_linha_curta_fica_igual(self):
        self.assertEqual(marcacao._dobrar("SUMMARY:curto"), "SUMMARY:curto")

    def test_dobrar_nenhuma_linha_passa_dos_75_octetos(self):
        linha = "SUMMARY:" + ("Reunião de acompanhamento mensal " * 6)
        for pedaco in marcacao._dobrar(linha).split("\r\n"):
            self.assertLessEqual(len(pedaco.encode("utf-8")), 75)

    def test_dobrar_nao_parte_caracteres_acentuados(self):
        """Dobrar por octetos sem olhar ao caracter parte um «ã» em dois."""
        dobrada = marcacao._dobrar("SUMMARY:" + ("ã" * 80))
        # Se partisse um caracter, isto levantava UnicodeDecodeError ou perdia-o.
        self.assertEqual(dobrada.replace("\r\n ", "").replace("\r\n", ""),
                         "SUMMARY:" + ("ã" * 80))

    # ── criar ──────────────────────────────────────────────────────────────

    def test_criar_poe_o_anfitriao_como_dono(self):
        inicio = add_to_date(now_datetime(), days=3)
        r = marcacao.criar(anfitriao="Administrator", assunto="Reunião de teste",
                           inicio=str(inicio), fim=str(add_to_date(inicio, minutes=30)))
        self.assertTrue(r["ok"])
        email = frappe.db.get_value("User", "Administrator", "email")
        self.assertEqual(frappe.db.get_value("Event", r["evento"], "owner"), email)

    def test_criar_com_a_mesma_referencia_nao_duplica(self):
        inicio = add_to_date(now_datetime(), days=4)
        ref = "MARC-TESTE-1"
        um = marcacao.criar(anfitriao="Administrator", assunto="Primeira",
                            inicio=str(inicio), fim=str(add_to_date(inicio, minutes=30)),
                            referencia=ref)
        dois = marcacao.criar(anfitriao="Administrator", assunto="Segunda",
                              inicio=str(inicio), fim=str(add_to_date(inicio, minutes=30)),
                              referencia=ref)
        self.assertEqual(um["evento"], dois["evento"])
        self.assertTrue(dois.get("repetido"))

    def test_criar_recusa_anfitriao_que_nao_existe(self):
        inicio = add_to_date(now_datetime(), days=5)
        with self.assertRaises(frappe.ValidationError):
            marcacao.criar(anfitriao="ninguem@exemplo.invalido", assunto="X",
                           inicio=str(inicio), fim=str(add_to_date(inicio, minutes=30)))

    # ── ocupado ────────────────────────────────────────────────────────────

    def test_ocupado_ve_o_que_foi_criado_no_frappe(self):
        inicio = add_to_date(now_datetime(), days=6).replace(hour=10, minute=0,
                                                             second=0, microsecond=0)
        marcacao.criar(anfitriao="Administrator", assunto="Ocupa esta hora",
                       inicio=str(inicio), fim=str(add_to_date(inicio, minutes=60)))
        r = marcacao.ocupado("Administrator",
                             str(add_to_date(inicio, days=-1)),
                             str(add_to_date(inicio, days=1)))
        self.assertTrue(any(i["inicio"].startswith(inicio.strftime("%Y-%m-%dT%H:%M"))
                            for i in r["ocupado"]))

    def test_ocupado_recusa_janela_invertida(self):
        agora = now_datetime()
        with self.assertRaises(frappe.ValidationError):
            marcacao.ocupado("Administrator", str(agora), str(add_to_date(agora, days=-1)))

    def test_ocupado_recusa_janela_larga_de_mais(self):
        agora = now_datetime()
        with self.assertRaises(frappe.ValidationError):
            marcacao.ocupado("Administrator", str(agora), str(add_to_date(agora, days=200)))

    # ── feed ───────────────────────────────────────────────────────────────

    def test_feed_recusa_segredo_errado(self):
        email = frappe.db.get_value("User", "Administrator", "email")
        marcacao._segredo_do_feed(email, criar_se_faltar=True)
        with self.assertRaises(frappe.DoesNotExistError):
            marcacao.feed(u=email, t="isto-nao-e-o-segredo")

    def test_feed_recusa_sem_segredo(self):
        email = frappe.db.get_value("User", "Administrator", "email")
        with self.assertRaises(frappe.DoesNotExistError):
            marcacao.feed(u=email, t="")

    def test_feed_sai_um_icalendar_valido(self):
        email = frappe.db.get_value("User", "Administrator", "email")
        segredo = marcacao._segredo_do_feed(email, criar_se_faltar=True)
        inicio = add_to_date(now_datetime(), days=7)
        marcacao.criar(anfitriao="Administrator", assunto="Vai ao feed; com vírgula",
                       inicio=str(inicio), fim=str(add_to_date(inicio, minutes=45)),
                       local="https://meet.orbit.stratechna.com/teste")
        marcacao.feed(u=email, t=segredo)
        texto = frappe.response["filecontent"].decode("utf-8")
        self.assertTrue(texto.startswith("BEGIN:VCALENDAR\r\n"))
        self.assertTrue(texto.rstrip().endswith("END:VCALENDAR"))
        self.assertIn("BEGIN:VEVENT", texto)
        self.assertIn("LOCATION:https://meet.orbit.stratechna.com/teste", texto)
        # A vírgula do assunto tem de ir escapada, senão o cliente lê dois campos.
        self.assertIn("SUMMARY:Vai ao feed\\; com vírgula", texto)
        self.assertEqual(frappe.response["content_type"],
                         "text/calendar; charset=utf-8")

    def test_feed_cada_evento_tem_uid_estavel(self):
        """Dois pedidos seguidos têm de dar o mesmo UID.

        Se mudasse, o webmail apagava e recriava tudo a cada sincronização — e o
        telemóvel tocava outra vez com avisos de reuniões já conhecidas.
        """
        email = frappe.db.get_value("User", "Administrator", "email")
        segredo = marcacao._segredo_do_feed(email, criar_se_faltar=True)

        def uids():
            marcacao.feed(u=email, t=segredo)
            texto = frappe.response["filecontent"].decode("utf-8")
            return [l for l in texto.split("\r\n") if l.startswith("UID:")]

        self.assertEqual(uids(), uids())
