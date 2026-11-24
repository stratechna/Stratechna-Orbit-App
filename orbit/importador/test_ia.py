"""Testes da IA do importador no Orbit (F5.5). Sem frappe, sem rede: o modelo é simulado.

Correr na raiz da app:  python -m unittest orbit.importador.test_ia
A prova de que as instruções são as do portal, letra a letra, é o guião
orbit-scripts/inventario/portal/comparar_ia.py (corre no portal).
"""
import json
import unittest

from orbit.importador import ia


def resposta(texto, entrada=10, saida=5):
    return {"content": [{"type": "text", "text": texto}], "usage": {"input_tokens": entrada, "output_tokens": saida}}


class Modelo:
    def __init__(self, *respostas):
        self.respostas = list(respostas)
        self.pedidos = []

    def __call__(self, system, mensagem, max_tokens, timeout):
        self.pedidos.append({"system": system, "mensagem": mensagem, "max_tokens": max_tokens, "timeout": timeout})
        r = self.respostas.pop(0)
        return r(mensagem) if callable(r) else r


class Texto(unittest.TestCase):
    def test_titulo_com_glossario_e_tecto(self):
        m = Modelo(resposta("Tronco de talho Fimar CP40 em madeira"))
        texto, uso = ia.tarefa_texto(m, "titulo", "Ceppo macelleria Fimar CP40 legno", "traduzido", "")
        self.assertEqual(texto, "Cepo de talho Fimar CP40 em madeira")
        self.assertEqual(uso["input_tokens"], 10)
        self.assertEqual(m.pedidos[0]["max_tokens"], 800)
        self.assertIn("Glossário obrigatório", m.pedidos[0]["system"])
        self.assertIn("Se o título vier abreviado", m.pedidos[0]["system"])

    def test_resposta_vazia_e_erro(self):
        with self.assertRaises(RuntimeError):
            ia.tarefa_texto(Modelo(resposta("")), "descricao", "Acciaio inox", "traduzido", "")

    def test_comentario_recusado(self):
        with self.assertRaises(ia.RespostaComComentario):
            ia.tarefa_texto(Modelo(resposta("Nota: mantive o código.")), "descricao", "Tavolo inox", "traduzido", "")

    def test_titulo_sem_codigo_recusado(self):
        with self.assertRaises(ia.RespostaComComentario):
            ia.tarefa_texto(Modelo(resposta("Fritadeira eléctrica")), "titulo",
                            "Electrolux E9FRED1HF0 EL.FRYER (Code 391094)", "traduzido", "")

    def test_lingua_estrangeira(self):
        r = ia.executar({"tarefa": "texto", "args": {"campo": "descricao", "valor": "Mesa de acero",
                                                     "como": "traduzido"}},
                        Modelo(resposta("Mesa de acero inoxidable con puerta y cajón para la cocina")))
        self.assertFalse(r["ok"])
        self.assertEqual((r["tipo"], r["lingua"]), ("lingua", "es"))

    def test_html_e_instrucoes_do_lojista(self):
        m = Modelo(resposta("<p>Mesa</p>"))
        ia.tarefa_texto(m, "descricao", "<p>Tavolo</p>", "traduzido_ia", "Nunca usar «top».")
        s = m.pedidos[0]["system"]
        self.assertIn("O texto contém HTML", s)
        self.assertTrue(s.endswith("Instruções do lojista para este fornecedor: Nunca usar «top»."))
        self.assertEqual(m.pedidos[0]["max_tokens"], 2000)

    def test_vitrine_so_na_docriluc(self):
        m = lambda: Modelo(resposta("Armário refrigerado ventilado com porta"))
        t28, _ = ia.tarefa_texto(m(), "descricao", "Refrigerated cabinet with door", "traduzido", "", 28)
        t10, _ = ia.tarefa_texto(m(), "descricao", "Refrigerated cabinet with door", "traduzido", "", 10)
        self.assertEqual(t28, "Vitrine refrigerada ventilada com porta")
        self.assertEqual(t10, "Armário refrigerado ventilado com porta")


class Valores(unittest.TestCase):
    def test_chaves_numeradas_e_lotes_de_60(self):
        valores = {f"attr::global::A{n}": f"valore {n}" for n in range(61)}

        def responde(mensagem):
            entrada = json.loads(mensagem)
            return resposta(json.dumps({k: v["valor"].replace("valore", "valor") for k, v in entrada.items()}))
        m = Modelo(responde, responde)
        out, uso = ia.tarefa_valores(m, valores, "")
        self.assertEqual(len(m.pedidos), 2)
        self.assertEqual(m.pedidos[0]["max_tokens"], 1500 + 80 * 60)
        self.assertEqual(out["attr::global::A60"], "valor 60")
        self.assertEqual(uso["input_tokens"], 20)

    def test_chaves_diferentes_falham(self):
        with self.assertRaises(RuntimeError):
            ia.tarefa_valores(Modelo(resposta('{"v1": "a", "v9": "b"}')), {"var::Cor": "Nero", "var::Tam": "Grande"}, "")

    def test_em_bloco_de_codigo(self):
        out, _ = ia.tarefa_valores(Modelo(resposta('```json\n{"v1": {"valor": "Preto"}}\n```')), {"var::Cor": "Nero"}, "")
        self.assertEqual(out, {"var::Cor": "Preto"})


class Nomes(unittest.TestCase):
    def test_tira_dois_pontos_e_recusa_longos(self):
        out, _ = ia.tarefa_nomes(Modelo(resposta('{"n1": "Largura (cm):"}')), ["Larghezza (Cm.)"])
        self.assertEqual(out, {"Larghezza (Cm.)": "Largura (cm)"})
        with self.assertRaises(RuntimeError):
            ia.tarefa_nomes(Modelo(resposta(json.dumps({"n1": "x" * 121}))), ["Peso"])


CATS = [{"id": 1, "name": "Cozinha", "parent": 0}, {"id": 2, "name": "Grelhadores", "parent": 1},
        {"id": 3, "name": "Exterior", "parent": 0}, {"id": 4, "name": "Grelhadores", "parent": 3},
        {"id": 5, "name": "Fornos", "parent": 1}]


class Categorizar(unittest.TestCase):
    def test_caminho_e_folha(self):
        m = Modelo(resposta('{"categorias": ["Cozinha", "Cozinha > Grelhadores"], "tags": ["Inox", "Inventada"]}'))
        r = ia.tarefa_categorizar(m, {"titulo": "Grelhador"}, CATS, [{"name": "Inox"}], "")
        self.assertEqual((r["categorias_ids"], r["tags"]), ([2], ["Inox"]))
        self.assertIn('"Cozinha > Grelhadores"', m.pedidos[0]["mensagem"])
        self.assertEqual(m.pedidos[0]["max_tokens"], 300)

    def test_nome_ambiguo_nao_se_adivinha(self):
        r = ia.tarefa_categorizar(Modelo(resposta('{"categorias": ["Grelhadores"], "tags": []}')), {"titulo": "x"}, CATS, [], "")
        self.assertTrue(r["falhou"])
        self.assertEqual(r["uso"]["input_tokens"], 10)

    def test_nome_unico_aceite(self):
        r = ia.tarefa_categorizar(Modelo(resposta('{"categorias": ["Fornos"]}')), {"titulo": "x"}, CATS, [], "")
        self.assertEqual(r["categorias"], ["Fornos"])


class Relacionados(unittest.TestCase):
    def test_so_refs_reais_e_limites(self):
        cand = [{"ref": f"R{n}", "titulo": f"T{n}"} for n in range(10)]
        m = Modelo(resposta('Aqui: {"cross_sell": ["R1","R2","R3","R4","R5","R6","X"], "upsell": ["R9","Y"]}'))
        r = ia.tarefa_relacionados(m, {"titulo": "A"}, cand, "")
        self.assertEqual((r["cross_sell"], r["upsell"]), (["R1", "R2", "R3", "R4", "R5"], ["R9"]))

    def test_sem_candidatos_nao_chama(self):
        m = Modelo()
        self.assertEqual(ia.tarefa_relacionados(m, {}, [], "")["cross_sell"], [])
        self.assertEqual(m.pedidos, [])


class Executar(unittest.TestCase):
    def test_sem_creditos(self):
        def modelo(*a):
            raise ia.SemCreditos("sem créditos")
        r = ia.executar({"tarefa": "nomes", "args": {"nomes": ["Peso"]}}, modelo)
        self.assertEqual(r["tipo"], "sem_creditos")

    def test_tarefa_desconhecida(self):
        self.assertFalse(ia.executar({"tarefa": "x"}, Modelo())["ok"])


if __name__ == "__main__":
    unittest.main()
