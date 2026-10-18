"""As traduções da app (orbit/translations/*.csv) — 18-10-2026, docs/PLANO-I18N-ORBIT-APPS.md.

Falha se um texto nosso ficar sem as quatro línguas (é isso que faz voltar a mistura de inglês e português),
se um marcador ({0}, %s, HTML) se perder numa tradução, ou se os nomes dos módulos fugirem à regra da marca.
Não precisa de base de dados: lê os ficheiros."""
import csv
import os
import re
import unittest

PASTA = os.path.join(os.path.dirname(__file__), "translations")
LINGUAS = ("pt", "en", "es", "fr")
MARC = re.compile(r"\{[^{}\s]*\}|%\(?\w*\)?[sdf]|<[^>]+>")


def ler(l):
    with open(os.path.join(PASTA, f"{l}.csv"), encoding="utf-8", newline="") as f:
        return {(r[0], r[2] if len(r) > 2 else ""): r[1] for r in csv.reader(f) if r}


class TestLingua(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.t = {l: ler(l) for l in LINGUAS}

    def test_marcadores(self):
        for l, d in self.t.items():
            for (k, _c), v in d.items():
                self.assertEqual(sorted(MARC.findall(k)), sorted(MARC.findall(v)), f"{l}: {k!r} → {v!r}")

    def test_nossos_nas_quatro_linguas(self):
        # en.csv só tem textos de origem portuguesa (os nossos) e os nomes dos módulos: cada um deles tem de
        # existir também em es e fr — senão um espanhol ou um francês vê-o em português.
        from orbit.marca import NOMES
        for chave in self.t["en"]:
            if chave[0] in NOMES:
                continue
            for l in ("es", "fr"):
                self.assertTrue(chave in self.t[l], f"falta {l} para {chave[0]!r}")

    def test_marca(self):
        for l in LINGUAS:
            self.assertEqual(self.t[l].get(("Helpdesk", "")), "Desk", l)
            self.assertEqual(self.t[l].get(("Frappe CRM", "")), "CRM", l)

    def test_pt_europeu(self):
        br = re.compile(r"\b(usuário|usuários|arquivo|arquivos|contato|contatos|equipe|deletar|excluir|tela|celular)\b", re.I)
        for (k, _c), v in self.t["pt"].items():
            self.assertIsNone(br.search(v), f"pt-BR em {k!r} → {v!r}")


if __name__ == "__main__":
    unittest.main()
