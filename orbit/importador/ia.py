"""IA do importador no Orbit (F5.5, 21-11-2026).

O Orbit passa a ter a inteligência da IA do importador: as instruções à IA, o glossário, as verificações
das respostas e a leitura delas — copiadas do portal (`routers/importador.py`, cada bloco cita a linha de
origem). O modelo é pedido ao portal pela rota assinada `/api/v1/orbit/ia-modelo`: a chave da Anthropic
nunca sai do portal, e uma conta sem créditos recebe 402 sem a IA ser chamada. Os créditos continuam a ser
debitados pelo portal, uma vez por lote, como sempre.

Tarefas (uma por chamada da ponte `importador-ia <slug>`, pedido e resposta em JSON):

* `texto`        — traduz/optimiza um campo (equivale a `_texto_ia` + glossário + `_confirmar_portugues`);
* `valores`      — valores curtos de atributos e variantes, 60 por chamada (`_valores_ia`);
* `nomes`        — nomes de especificações, 80 por chamada (`_nomes_atributos_ia`);
* `categorizar`  — escolhe categorias/tags REAIS da loja (`_categorizar_produto_ia`);
* `relacionados` — venda cruzada e upgrade entre produtos REAIS (`_gerar_relacionados_ia`).

A memória de tradução, a escolha dos produtos, os créditos e a gravação ficam no portal até à F5.6.
Só biblioteca-padrão (+ frappe/requests só em `_modelo_portal`), para os testes correrem fora do Frappe.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import unicodedata
from contextvars import ContextVar
from typing import Any, Callable, Dict, List, Optional

FICHA_INICIO, FICHA_FIM = "<!--ficha-->", "<!--/ficha-->"

# ── portal routers/importador.py linhas 2231–2259: língua estrangeira (cópia fiel) ──
# Verificação depois da tradução (04-10-2026): se o texto devolvido ainda
# parece castelhano, italiano, inglês ou francês, não se dá como feito —
# volta à fila e conta para o tecto de tentativas. Palavras escolhidas por
# serem frequentes numa língua e raras em português.
_LINGUA_MARCADORES = {
    "es": r"el|los|las|del|y|con|sin|una|puerta|puertas|acero|inoxidable|cajón|cajones|horno|cocina|encimera|estante|negro|blanco|madera|fregadero|campana|también|está|muy",
    "it": r"il|della|delle|degli|dello|gli|per|senza|sono|alla|nel|dei|acciaio|porte|cassetto|cassetti|frigorifero|cucina|tavolo|carrello|ripiano|nero|bianco|legno|lavastoviglie|tritacarne|affettatrice",
    "en": r"the|and|with|without|for|of|is|stainless|steel|door|doors|drawer|drawers|fridge|oven|table|trolley|shelf|black|white|cabinet|dishwasher|wood",
    "fr": r"le|les|avec|pour|des|du|et|est|acier|porte|tiroir|four|noir|blanc|bois",
}
_LINGUA_PT = re.compile(r"\b(de|do|da|dos|das|com|sem|em|uma|um|e|para|ao|à|não|é|são|aço|inoxidável|gaveta|gavetas|forno|mesa|preto|branco|madeira)\b|ção|ções|[ãõç]", re.I)
_LINGUA_RX = {k: re.compile(r"\b(" + v + r")\b", re.I) for k, v in _LINGUA_MARCADORES.items()}


def _lingua_estrangeira(texto: str) -> Optional[str]:
    """Devolve o código da língua estrangeira dominante, ou None quando o
    texto parece português (ou é curto demais para se saber)."""
    t = re.sub(r"<[^>]+>", " ", texto or "")
    if len(t.split()) < 4:
        return None
    pt = len(_LINGUA_PT.findall(t))
    melhor, pontos = None, 0
    for lingua, rx in _LINGUA_RX.items():
        n = len(rx.findall(t))
        if n > pontos:
            melhor, pontos = lingua, n
    if pontos >= 3 and pontos > pt:
        return melhor
    return None

# ── portal routers/importador.py linhas 9364–9442: verificações da resposta (cópia fiel) ──
class TraducaoNaoPortuguesa(RuntimeError):
    def __init__(self, campo: str, lingua: str):
        super().__init__(f"o campo {campo} continua em {lingua} depois de traduzido")
        self.lingua = lingua


# 29-10-2026: títulos abreviados da Maran-Pro («18LT EL.FRYER-1 WELL+2 1/2
# BASKETS», «a Gás SOLID TOP+2 BURNERS») passavam como português — o detector
# precisa de 4 palavras e de palavras comuns do inglês, que um título destes
# não tem. Nos títulos conta também o vocabulário de cozinha profissional
# em inglês: dois termos chegam para recusar.
_RX_TITULO_INGLES = re.compile(
    r"\b(ovens?|fryers?|burners?|baskets?|wells?|boiling|pans?|cookers?|range|plates?|smooth|ribbed|sloped|"
    r"heating|cupb|workt|hob|litres?|liters?|cleaning|brushed|polished|chrome|scratch|resistant|refill|bottom|"
    r"solid|drawers?|with|without|cabinet|hood|griddle|kettle|steamer|automatic)\b",
    re.I,
)


def _confirmar_portugues(campo: str, texto: str) -> None:
    lingua = _lingua_estrangeira(texto)
    if lingua:
        raise TraducaoNaoPortuguesa(campo, lingua)
    if campo == "titulo" and len(_RX_TITULO_INGLES.findall(texto or "")) >= 2:
        raise TraducaoNaoPortuguesa(campo, "en")


# 20-10-2026: 12 títulos (Fimar, UDEX, Tefcold) chegaram à shopinox com a
# conversa da IA dentro — «Preciso de mais contexto: este título está em
# italiano. Vou traduzi-lo…», «Nota: Mantive…», «Se me indicar o texto…».
# A resposta era gravada tal como vinha. Agora uma resposta com comentário
# é recusada (erro → o produto volta à fila, com o tecto de tentativas).
_RX_COMENTARIO_IA = re.compile(
    r"preciso de (mais contexto|esclarecer)|vou traduzi|aqui est[áa] a tradu|segue a tradu|tradu[çc][ãa]o"
    r"( correct?a| para portugu[eê]s europeu)?\s*:|n[ãa]o (foi fornecido|forneceu)|se me indicar|\bnota\s*:|\bmantive\b"
    r"|n[ãa]o foi fornecid|n[ãa]o consigo traduzir|terei todo o gosto|I need more context|here is the translation",
    re.I,
)


# Só nos títulos (numa descrição de fabricante «infelizmente» pode ser texto real).
_RX_COMENTARIO_IA_TITULO = re.compile(
    r"infelizmente|n[ãa]o encontrei|por favor|pretende traduzir|n[ãa]o cont[ée]m palavras|refer[êe]ncia de produto|se me fornecer",
    re.I,
)


class RespostaComComentario(RuntimeError):
    pass


# Medidas («400x600MM», «1200MM», «230V») não são códigos: a IA pode reescrevê-las («400x600 mm»).
_RX_MEDIDA_TITULO = re.compile(r"^\d+(?:[x×]\d+)*(?:mm|cm|m|lt|l|kw|w|v|hz|kg|gn)?$", re.I)
_RX_CODIGO_TITULO = re.compile(r"\b(?=[A-Za-z0-9]*\d)(?=[A-Za-z0-9]*[A-Za-z])[A-Za-z0-9]{6,}\b|\b\d{5,}\b")


def _confirmar_sem_comentario(campo: str, texto: str, original: str) -> None:
    """Recusa uma tradução que traga explicações da IA em vez de só o texto."""
    if _RX_COMENTARIO_IA.search(texto) and not _RX_COMENTARIO_IA.search(original or ""):
        raise RespostaComComentario(f"a IA devolveu um comentário no campo {campo}: {texto[:80]!r}")
    if campo == "titulo":
        if _RX_COMENTARIO_IA_TITULO.search(texto) and not _RX_COMENTARIO_IA_TITULO.search(original or ""):
            raise RespostaComComentario(f"a IA devolveu um comentário no título: {texto[:80]!r}")
        if "\n" in texto.strip() or "**" in texto:
            raise RespostaComComentario(f"título com várias linhas ou markdown: {texto[:80]!r}")
        if len(texto) > max(2 * len(original or ""), len(original or "") + 60):
            raise RespostaComComentario(f"título traduzido muito mais longo do que o original: {texto[:80]!r}")
        # 29-10-2026: a IA tirava marca, modelo e código a títulos abreviados
        # («Marmita a Gás 150 L» em vez de «Electrolux Professional
        # E9BSGHDRF0 … (Código 391107)»). Todo o código do original (letras e
        # algarismos juntos, ou só algarismos com 5+) tem de continuar lá.
        # Só o modelo (1.º código) e os números de 5+ algarismos: abreviaturas
        # coladas («4BUR10KW», «OV800MM», «6KWGAS») têm de poder ser desdobradas.
        codigos = [c for c in _RX_CODIGO_TITULO.findall(original or "") if not _RX_MEDIDA_TITULO.match(c)]
        exigidos = [c for i, c in enumerate(codigos) if i == 0 or c.isdigit()]
        em_falta = [c for c in exigidos if c.lower() not in texto.lower()]
        if em_falta:
            raise RespostaComComentario(f"título sem o código {em_falta[0]!r}: {texto[:80]!r}")


# ── portal routers/importador.py linhas 9444–9660: glossário (cópia fiel) ──
# ── Glossário de termos obrigatórios (23-10-2026) ─────────────────────
# Regra do Vítor: «Ceppo» é «Cepo», nunca «Tronco». A IA traduziu o mesmo
# «Ceppo» da Fimar de cinco maneiras (Tronco, Toco, Bloco, Cepo e por
# traduzir). O glossário entra no pedido à IA (traduções novas) e é
# aplicado DEPOIS de cada tradução — nova ou vinda da memória, que se
# corrige a si própria: se a origem tiver o termo e a tradução trouxer uma
# das formas erradas, troca-se, com as mesmas maiúsculas e o plural.
GLOSSARIO_TRADUCAO = [
    {
        "origem": re.compile(r"\b(ceppo|ceppi|tajos?|chopping[ -]blocks?|butcher[ -]blocks?|billots?|hackkl[oö]tze?)\b", re.I),
        "errados": re.compile(r"\b(?:troncos?|tocos?|blocos?|ceppo|ceppi)\b", re.I),
        "termo": "cepo",
        "instrucao": "«Ceppo» (italiano), «tajo» (castelhano), «chopping block»/«butcher block» (inglês) e «billot» (francês) — "
                     "o bloco de corte de talho — traduzem-se SEMPRE por «cepo», nunca «tronco», «toco» ou «bloco».",
    },
    {
        "origem": re.compile(r"\bsgabell[oi]\b", re.I),
        "errados": re.compile(r"\bsgabell[oi]\b", re.I),
        "termo": "banco",
        "instrucao": "«Sgabello» (italiano) é «banco».",
    },
    # 26-10-2026, regra do Vítor: sempre «vitrine», nunca «vitrina» (a IA
    # alternava entre as duas — 417 títulos com uma, 307 com a outra).
    {
        # Qualquer origem: «vitrina» nunca é a forma pretendida (também vinha
        # de «vetrinetta», «expositor», «sobrevitrina»…).
        "origem": re.compile(r"\S"),
        "errados": re.compile(r"\bvitrinas?\b", re.I),
        "termo": "vitrine",
        "instrucao": "«Vitrina» (castelhano), «vetrina» (italiano), «display cabinet/case» e «showcase» (inglês) "
                     "traduzem-se SEMPRE por «vitrine» (plural «vitrines»), nunca «vitrina».",
    },
    # 26-10-2026, regra do Vítor: a Docriluc só faz vitrines e chama-lhes
    # «Refrigerated Cabinet» — saía «Armário» numas e «Vitrine» noutras do
    # mesmo modelo. Só para a Docriluc (28): o «armadio» da Fimar e o
    # armário de porta de vidro da UDEX são mesmo armários.
    {
        "fornecedores": {28},
        "origem": re.compile(r"\b(cabinets?|armarios?|vitrin[ae]s?)\b", re.I),
        "errados": re.compile(r"\barm[aá]rios?\b", re.I),
        "termo": "vitrine",
        "feminino": True,
        "instrucao": "",
    },
    # 29-10-2026, regra do Vítor: o módulo neutro das linhas de queima
    # («Cocina neutra» da Fainca, «neutral element» em inglês, «elemento
    # neutro» em italiano) é «Elemento neutro», nunca «Fogão neutro».
    {
        "origem": re.compile(r"\b(neutr[oa]s?|neutral|neutre)\b", re.I),
        "errados": re.compile(r"\b(?:fog[ãa]o|fog[õo]es|cozinhas?)\s+neutr[oa]s?\b", re.I),
        "termo": "elemento neutro",
        "plural": "elementos neutros",
        "instrucao": "O módulo neutro de uma linha de cozinha («cocina neutra», «neutral element», «elemento neutro») "
                     "traduz-se SEMPRE por «elemento neutro» (plural «elementos neutros»), nunca «fogão neutro» nem «cozinha neutra».",
    },
    # 11-11-2026, regra do Vítor: «retro banco bar» / «retrobanco» (italiano)
    # é «Backbar» — saía «Traseira banco bar» nos títulos e «Retaguarda de
    # bar» nas descrições (Fimar G-DC210/G-DC310).
    {
        "origem": re.compile(r"\b(retro[ -]?banc(?:o|hi)|back[ -]?bars?)\b", re.I),
        "errados": re.compile(r"\b(?:traseiras?\s+(?:de\s+)?(?:bancos?|balc[ãa]o|balc[õo]es)(?:\s+(?:de\s+)?bar)?|retaguardas?\s+de\s+bar)\b", re.I),
        "termo": "backbar",
        "plural": "backbars",
        "plural_re": re.compile(r"^(?:traseiras|retaguardas)\b", re.I),
        "instrucao": "«Retro banco bar»/«retrobanco» (italiano) e «back bar» (inglês) traduzem-se SEMPRE por «backbar» "
                     "(plural «backbars»), nunca «traseira banco bar» nem «retaguarda de bar».",
    },
    # 11-11-2026, regra do Vítor: «Bottle Cooler» (e a gralha «Bootle
    # Cooler» da Fimar) é «Expositor Refrigerado» — ficava em inglês nos
    # títulos ou virava «armário de refrigeração de garrafas».
    {
        "origem": re.compile(r"\bbo+t+le[ -]?coolers?\b", re.I),
        "errados": re.compile(r"\b(?:bo+t+le[ -]?coolers?(?:\s+refrigerad[oa]s?)?|arm[áa]rios?\s+(?:de\s+)?refrigera[çc][ãa]o\s+(?:de|para)\s+garrafas|arcas?\s+(?:frigor[íi]ficas?\s+)?(?:de|para)\s+garrafas|refrigeradore?s?\s+(?:de|para)\s+garrafas)\b", re.I),
        "termo": "expositor refrigerado",
        "plural": "expositores refrigerados",
        # O plural decide-se pela 1.ª palavra («armário … de garrafas» é singular).
        "plural_re": re.compile(r"^(?:bo+t+le[ -]?coolers|arm[áa]rios|arcas|refrigeradores)\b", re.I),
        "instrucao": "«Bottle cooler» traduz-se SEMPRE por «expositor refrigerado» (plural «expositores refrigerados»), "
                     "nunca fica em inglês nem «armário/refrigerador de garrafas».",
    },
    # 11-11-2026, regra do Vítor: «pensile» (italiano, armário de parede)
    # é «armário» — a IA punha «SUSPENSO ABERTO» em vez de «ARMÁRIO ABERTO»
    # (Forcar, Armários Inox). «Armário suspenso» continua igual.
    {
        "origem": re.compile(r"\bpensil[ei]\b", re.I),
        "errados": re.compile(r"(?<!rio )(?<!rios )\bsuspens[oa]s?\b", re.I),
        "termo": "armário",
        "plural": "armários",
        "plural_re": re.compile(r"s$", re.I),
        "instrucao": "«Pensile»/«pensili» (italiano) é «armário» (de parede), nunca só «suspenso».",
    },
    # 11-11-2026, regra do Vítor: «tavolo» (italiano) das mesas inox é
    # «mesa», nunca «balcão» («Balcão de trabalho», «Balcão fechado» nas
    # Mesas Inox da Forcar). Fora: «tavolo refrigerato», onde «balcão
    # refrigerado» é o termo corrente. «Fechado» passa a «fechada».
    {
        "origem": re.compile(r"^(?!.*refrigerat).*\btavol[oi]\b", re.I | re.S),
        "errados": re.compile(r"\bbalc(?:ão|ao|ões|oes)\s+fechad[oa]s?\b", re.I),
        "termo": "mesa fechada",
        "plural": "mesas fechadas",
        "plural_re": re.compile(r"^balc(?:ões|oes)", re.I),
        "instrucao": "",
    },
    {
        "origem": re.compile(r"^(?!.*refrigerat).*\btavol[oi]\b", re.I | re.S),
        "errados": re.compile(r"\bbalc(?:ão|ao|ões|oes)\b", re.I),
        "termo": "mesa",
        "plural": "mesas",
        "plural_re": re.compile(r"^balc(?:ões|oes)", re.I),
        "instrucao": "«Tavolo» (italiano) é «mesa» (mesa de trabalho, mesa com armário), nunca «balcão» — excepto «tavolo refrigerato».",
    },
    # 11-11-2026, regra do Vítor: «sottovuoto» (máquina de embalar a vácuo)
    # é «Máquina de vácuo» — saía «A VÁCUO CAMPÂNULA…», «A VÁCUO DE BARRA…».
    {
        "origem": re.compile(r"^\s*sottovuoto\b", re.I),
        "errados": re.compile(r"^\s*(?:a|sob|em|(?:embaladoras?|m[áa]quinas?\s+de\s+embalar)\s+(?:a|de|em))\s+v[áa]cuo\b", re.I),
        "termo": "máquina de vácuo",
        "plural": "máquinas de vácuo",
        "plural_re": re.compile(r"^$"),
        "instrucao": "«Sottovuoto» (italiano) no início do nome é «máquina de vácuo», nunca «a vácuo».",
    },
    {
        "origem": re.compile(r"^\s*sottovuoto\s+campana\b", re.I),
        "errados": re.compile(r"\bm[áa]quina de v[áa]cuo\s+camp[âa]nula\b", re.I),
        "termo": "máquina de vácuo de campânula",
        "plural": "máquinas de vácuo de campânula",
        "plural_re": re.compile(r"^$"),
        "instrucao": "",
    },
    # 11-11-2026 (variantes da Fimar que ficavam em italiano/inglês): os
    # títulos destes produtos já dizem «Cortador» e «Lava-mexilhões».
    {
        "origem": re.compile(r"^\s*cutter\b", re.I),
        "errados": re.compile(r"^\s*cutters?\b", re.I),
        "termo": "cortador",
        "plural": "cortadores",
        "plural_re": re.compile(r"s$", re.I),
        "instrucao": "«Cutter» no início do nome de uma máquina é «cortador».",
    },
    {
        "origem": re.compile(r"\blavacozze\b", re.I),
        "errados": re.compile(r"\blavacozze\b", re.I),
        "termo": "lava-mexilhões",
        "plural": "lava-mexilhões",
        "plural_re": re.compile(r"^$"),
        "instrucao": "«Lavacozze» (italiano) é «lava-mexilhões».",
    },
]
# Fornecedor do produto que se está a traduzir — as entradas com
# «fornecedores» só se aplicam a esses.
_GLOSSARIO_FORNECEDOR: ContextVar = ContextVar("glossario_fornecedor", default=None)

# Concordância quando um nome masculino passa a «vitrine» (feminino): artigo
# antes, adjectivos até três palavras depois.
_ARTIGOS_FEM = {"o": "a", "os": "as", "um": "uma", "uns": "umas", "do": "da", "dos": "das", "no": "na",
                "nos": "nas", "ao": "à", "aos": "às", "este": "esta", "estes": "estas", "esse": "essa",
                "pelo": "pela", "pelos": "pelas", "deste": "desta", "neste": "nesta"}
_ADJ_FEM = {"refrigerado": "refrigerada", "refrigerados": "refrigeradas", "congelador": "congeladora",
            "congeladores": "congeladoras", "ventilado": "ventilada", "ventilados": "ventiladas",
            "aquecido": "aquecida", "aquecidos": "aquecidas", "expositor": "expositora",
            "expositores": "expositoras", "estático": "estática", "estáticos": "estáticas",
            "frigorífico": "frigorífica", "frigoríficos": "frigoríficas", "neutro": "neutra", "neutros": "neutras",
            "climatizado": "climatizada", "iluminado": "iluminada", "panorâmico": "panorâmica"}


def _mesma_caixa(modelo: str, novo: str) -> str:
    if modelo.isupper():
        return novo.upper()
    if modelo[:1].isupper():
        return novo[:1].upper() + novo[1:]
    return novo


def _feminino(final: str, errados) -> str:
    padrao = re.compile(r"(?:\b(\w+)(\s+))?(" + errados.pattern + r")((?:\s+[^\s]+){0,3})", re.I)

    def _troca(m):
        artigo, esp, palavra, cauda = m.group(1), m.group(2) or "", m.group(3), m.group(4) or ""
        novo = _mesma_caixa(palavra, "vitrine" + ("s" if palavra.lower().endswith("s") else ""))
        if artigo and artigo.lower() in _ARTIGOS_FEM:
            artigo = _mesma_caixa(artigo, _ARTIGOS_FEM[artigo.lower()])
        cauda = re.sub(r"[^\W\d_]+", lambda w: _mesma_caixa(w.group(0), _ADJ_FEM[w.group(0).lower()])
                       if w.group(0).lower() in _ADJ_FEM else w.group(0), cauda)
        return (artigo or "") + esp + novo + cauda
    return padrao.sub(_troca, final)
GLOSSARIO_INSTRUCOES = " Glossário obrigatório: " + " ".join(g["instrucao"] for g in GLOSSARIO_TRADUCAO if g["instrucao"])


def _aplicar_glossario(origem: str, final: str, fornecedor_id: Optional[int] = None) -> str:
    if not final or not origem:
        return final
    if fornecedor_id is None:
        fornecedor_id = _GLOSSARIO_FORNECEDOR.get()
    for g in GLOSSARIO_TRADUCAO:
        if g.get("fornecedores") and fornecedor_id not in g["fornecedores"]:
            continue
        if not g["origem"].search(origem) or not g["errados"].search(final):
            continue
        if g.get("feminino"):
            final = _feminino(final, g["errados"])
            continue

        def _troca(m, termo=g["termo"]):
            palavra = m.group(0)
            if g.get("plural_re"):
                novo = g["plural"] if g["plural_re"].search(palavra) else termo
            elif g.get("plural"):
                novo = g["plural"] if palavra.lower().endswith("s") else termo
            else:
                novo = termo + ("s" if palavra.lower().endswith(("s", "i")) else "")
            if palavra.isupper():
                return novo.upper()
            if palavra[:1].isupper():
                return novo[:1].upper() + novo[1:]
            return novo
        final = g["errados"].sub(_troca, final)
    return final

# ── portal routers/importador.py linhas 10239–10244: grafia dobrada dos nomes (cópia fiel) ──
def _dobrar_nome_atributo(nome: str) -> str:
    t = unicodedata.normalize("NFKD", nome or "").encode("ascii", "ignore").decode().lower()
    t = t.replace("/", "-")
    t = re.sub(r"\s*([-(),:])\s*", r"\1", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip(" :.")


# ══ Instruções à IA — iguais, letra a letra, às do portal ══════════════════════
# (a igualdade é verificada no portal por `orbit-scripts/inventario/portal/comparar_ia.py`)

def instrucao_texto(campo_woo: str, valor_bruto: str, como_aplicar: str, instrucoes_extra: str) -> str:
    """portal `_texto_ia` (linhas 9663–9706)."""
    if como_aplicar == "traduzido":
        tarefa = "Traduz o texto seguinte para português europeu, preservando o significado e o tom exactos."
    elif como_aplicar == "ia":
        tarefa = ("Reescreve o texto seguinte em português europeu, optimizado para conversão de vendas numa loja "
                  "online — claro e apelativo, sem inventar características que não estejam já implícitas no texto original.")
    else:
        tarefa = ("Traduz o texto seguinte para português europeu E reescreve-o optimizado para conversão de vendas "
                  "numa loja online — claro e apelativo, sem inventar características que não estejam já implícitas no texto original.")

    instrucao = f"És um assistente de catálogo de e-commerce. {tarefa} Campo: {campo_woo}. Responde APENAS com o texto final, sem comentários, sem aspas, sem markdown."
    instrucao += (" O texto pode vir em qualquer língua (castelhano, italiano, inglês, francês…): traduz sempre, nunca "
                  "peças contexto nem expliques o que fizeste. Se for só um código ou referência, devolve-o igual.")
    instrucao += GLOSSARIO_INSTRUCOES
    if campo_woo == "titulo":
        instrucao += (" Se o título vier abreviado ou em maiúsculas (ex.: «EL.», «OV.», «CUPB.», «WORKT.», «BURN.», "
                      "«WELL», «BASKETS»), desdobra as abreviaturas e escreve-o por extenso em português europeu, com "
                      "maiúsculas normais. Mantém SEMPRE a marca, o modelo, os códigos e as medidas, na mesma ordem e "
                      "exactamente como estão (ex.: «Electrolux Professional E9FRED1HF0 18LT EL.FRYER-1 WELL+2 1/2 BASKETS "
                      "(Code 391094)» → «Electrolux Professional E9FRED1HF0 Fritadeira Eléctrica 18 L, 1 Cuba e 2 Meios "
                      "Cestos (Código 391094)»). Termos fixos: «fry top» → «Fry-top», «boiling pan» → «Marmita», "
                      "«solid top» → «Placa Sólida», «pasta cooker» → «Cozedor de Massa»; «Code» → «Código» e «Alias» fica «Alias».")
    if como_aplicar != "ia":
        instrucao += (" Não deixes nenhuma palavra em castelhano, italiano, inglês ou francês que tenha equivalente "
                      "corrente em português europeu (ex.: «Ratón» → «Rato», «Negro» → «Preto», «Táctil» → «Tátil», "
                      "«TPV» → «Terminal POS», «Placa Base» → «Motherboard»). Mantém nomes de marca, modelo e referências.")
    if "<" in valor_bruto and ">" in valor_bruto:
        instrucao += " O texto contém HTML: mantém todas as etiquetas, atributos e URLs exactamente como estão e traduz só o texto visível."
    if instrucoes_extra:
        instrucao += f" Instruções do lojista para este fornecedor: {instrucoes_extra}"
    return instrucao


def max_tokens_texto(campo_woo: str) -> int:
    return 800 if campo_woo == "titulo" else (1000 if campo_woo == "descricao_curta" else 2000)


VALORES_IA_POR_CHAMADA = 60


def instrucao_valores(instrucoes_extra: str) -> str:
    """portal `_valores_ia` (linhas 9771–9779)."""
    instrucao = (
        "És um assistente de catálogo de e-commerce. Recebes um objecto JSON em que cada entrada tem o nome de "
        "uma especificação (ou opção de variante) de um produto e o seu valor. Traduz cada VALOR para português "
        "europeu. Mantém números, unidades, códigos de referência (ex.: 22TSQ0, GN 1/1, 400V 50Hz 3PH) e marcas, mas traduz SEMPRE as palavras comuns, mesmo dentro de nomes de modelo ou de variante (ex.: «TRITACARNE 22 INOX» → «PICADORA DE CARNE 22 INOX», «ABBINATO» → «COMBINADO», «CARRELLO 2 PIANI» → «CARRINHO 2 PRATELEIRAS», «C/INVERSIONE» → «C/INVERSÃO», «SPINA 5 POLI» → «FICHA 5 PÓLOS»). Se um valor já estiver em português, "
        "devolve-o igual. Responde APENAS com um objecto JSON com exactamente as mesmas chaves e, em cada uma, "
        "só o valor traduzido (texto). Sem comentários, sem markdown."
    ) + GLOSSARIO_INSTRUCOES
    if instrucoes_extra:
        instrucao += f" Instruções do lojista para este fornecedor: {instrucoes_extra}"
    return instrucao


NOMES_ATRIBUTO_IA_POR_CHAMADA = 80


def instrucao_nomes() -> str:
    """portal `_nomes_atributos_ia` (linhas 10254–10265)."""
    return (
        "És um assistente de catálogo de e-commerce. Recebes um objecto JSON em que cada valor é o NOME de uma "
        "especificação técnica de um produto (como aparece numa ficha técnica: «Potência (W)», «Altura (cm)»). "
        "Traduz cada nome para português europeu, como um técnico o escreveria numa ficha de loja: primeira letra "
        "maiúscula, o resto em minúsculas salvo siglas, unidades e siglas iguais (mm, cm, kg, W, kW, V, l, m², IP, "
        "TDA, GN), acentuação correcta («Peso liquido» → «Peso líquido»), sem dois pontos no fim. Exemplos: "
        "«Larghezza Macchina (Cm.)» → «Largura (cm)», «Cooling Power (W)» → «Potência frigorífica (W)», «power supply» → "
        "«Alimentação», «Ancho neto (Fondo) (mm)» → «Profundidade líquida (mm)», «Doors (units)» → «Portas (unidades)». "
        "Se já estiver em português europeu, devolve-o só com a acentuação e as maiúsculas acertadas. "
        "Responde APENAS com um objecto JSON com exactamente as mesmas chaves e, em cada uma, só o nome traduzido. "
        "Sem comentários, sem markdown."
    ) + GLOSSARIO_INSTRUCOES


def instrucao_categorizar(instrucoes_extra: str) -> str:
    """portal `_categorizar_produto_ia` (linhas 10559–10567)."""
    return (
        "És um assistente de catalogação de e-commerce. Dado um produto e a lista de categorias e tags REAIS já "
        "existentes nesta loja, escolhe a(s) categoria(s) mais adequada(s) (pelo menos 1) e tags relevantes (podem "
        "ser 0). Responde APENAS com um objecto JSON válido, sem comentários, sem markdown, no formato exacto: "
        '{"categorias": ["Caminho Exacto 1"], "tags": ["Nome Exacto"]}. Cada categoria é o CAMINHO completo tal '
        "e qual vem na lista (níveis separados por \" > \") — usa sempre o texto exacto dado, nunca inventes, "
        "abrevies nem devolvas só o último nível."
        + (f" Instruções do lojista: {instrucoes_extra}" if instrucoes_extra else "")
    )


def instrucao_relacionados(instrucoes_extra: str) -> str:
    """portal `_gerar_relacionados_ia` (linhas 10846–10856)."""
    return (
        "És um assistente de catálogo de e-commerce. Dado um produto e uma lista de OUTROS produtos REAIS já "
        "existentes no mesmo catálogo, escolhe: (a) até 5 produtos que fazem sentido como VENDA CRUZADA "
        "(cross-sell — complementares, comprados juntos), e (b) até 3 produtos que fazem sentido como UPGRADE "
        "(up-sell — uma versão superior/mais cara do mesmo tipo de produto). Podem ser 0 em qualquer um dos dois "
        "casos, se nenhum candidato fizer sentido — nunca forces uma escolha fraca. Responde APENAS com um "
        'objecto JSON válido, sem comentários, sem markdown, no formato exacto: '
        '{"cross_sell": ["ref1", "ref2"], "upsell": ["ref3"]}. Usa SEMPRE a referência exacta da lista dada — '
        "nunca inventes nem alteres uma referência."
        + (f" Instruções do lojista: {instrucoes_extra}" if instrucoes_extra else "")
    )


# ══ Tarefas ═══════════════════════════════════════════════════════════════════
# `modelo(system, mensagem, max_tokens, timeout)` devolve a resposta da Anthropic (content, usage, id).

def _texto_resposta(data: dict) -> str:
    return "".join(b.get("text", "") for b in (data.get("content") or []) if b.get("type") == "text").strip()


def _somar(uso_total: dict, uso: dict) -> None:
    uso_total["input_tokens"] += (uso or {}).get("input_tokens", 0) or 0
    uso_total["output_tokens"] += (uso or {}).get("output_tokens", 0) or 0


def tarefa_texto(modelo: Callable, campo_woo: str, valor_bruto: str, como_aplicar: str, instrucoes_extra: str,
                 fornecedor_id: Optional[int] = None) -> tuple:
    """(texto_final, uso). Erros: RuntimeError (resposta vazia), RespostaComComentario, TraducaoNaoPortuguesa."""
    data = modelo(instrucao_texto(campo_woo, valor_bruto, como_aplicar, instrucoes_extra), valor_bruto,
                  max_tokens_texto(campo_woo), 30)
    texto = _texto_resposta(data)
    if not texto:
        raise RuntimeError(f"Anthropic devolveu resposta vazia para o campo {campo_woo}")
    _confirmar_sem_comentario(campo_woo, texto, valor_bruto)
    texto = _aplicar_glossario(valor_bruto, texto, fornecedor_id)
    _confirmar_portugues(campo_woo, texto)
    return texto, data.get("usage", {})


def tarefa_valores(modelo: Callable, valores: Dict[str, str], instrucoes_extra: str,
                   fornecedor_id: Optional[int] = None) -> tuple:
    """({chave: tradução}, uso). Erro se faltar ou sobrar uma chave — nada se grava."""
    traduzidos: Dict[str, str] = {}
    uso_total = {"input_tokens": 0, "output_tokens": 0}
    chaves = list(valores)
    for i in range(0, len(chaves), VALORES_IA_POR_CHAMADA):
        bloco = {k: valores[k] for k in chaves[i:i + VALORES_IA_POR_CHAMADA]}
        por_indice = {f"v{n}": k for n, k in enumerate(bloco, 1)}
        legivel = {indice: {"atributo": k.split("::")[-1], "valor": bloco[k]} for indice, k in por_indice.items()}
        data = modelo(instrucao_valores(instrucoes_extra), json.dumps(legivel, ensure_ascii=False),
                      1500 + 80 * len(bloco), 90)
        _somar(uso_total, data.get("usage"))
        texto = re.sub(r"^```(?:json)?\s*|\s*```$", "", _texto_resposta(data))
        try:
            resultado = json.loads(texto)
        except Exception:
            raise RuntimeError(f"resposta da IA aos atributos não é JSON: {texto[:120]!r}")
        if not isinstance(resultado, dict) or set(resultado) != set(por_indice):
            raise RuntimeError("resposta da IA aos atributos não traz as mesmas chaves")
        for indice, v in resultado.items():
            if isinstance(v, dict):
                v = v.get("valor")
            if not isinstance(v, str) or not v.strip():
                raise RuntimeError(f"tradução vazia para {por_indice[indice]}")
            traduzidos[por_indice[indice]] = v.strip()
    traduzidos = {k: _aplicar_glossario(valores[k], t, fornecedor_id) for k, t in traduzidos.items()}
    return traduzidos, uso_total


def tarefa_nomes(modelo: Callable, nomes: List[str], fornecedor_id: Optional[int] = None) -> tuple:
    traduzidos: Dict[str, str] = {}
    uso_total = {"input_tokens": 0, "output_tokens": 0}
    for i in range(0, len(nomes), NOMES_ATRIBUTO_IA_POR_CHAMADA):
        bloco = nomes[i:i + NOMES_ATRIBUTO_IA_POR_CHAMADA]
        por_indice = {f"n{n}": k for n, k in enumerate(bloco, 1)}
        data = modelo(instrucao_nomes(), json.dumps(por_indice, ensure_ascii=False), 3000 + 120 * len(bloco), 90)
        _somar(uso_total, data.get("usage"))
        texto = re.sub(r"^```(?:json)?\s*|\s*```$", "", _texto_resposta(data))
        try:
            resultado = json.loads(texto)
        except Exception:
            raise RuntimeError(f"resposta da IA aos nomes de atributos não é JSON: {texto[:120]!r}")
        if not isinstance(resultado, dict) or set(resultado) != set(por_indice):
            raise RuntimeError("resposta da IA aos nomes de atributos não traz as mesmas chaves")
        for indice, v in resultado.items():
            if not isinstance(v, str) or not v.strip() or len(v) > 120 or "\n" in v:
                raise RuntimeError(f"tradução inválida para o nome {por_indice[indice]!r}: {v!r}")
            traduzidos[por_indice[indice]] = v.strip().rstrip(":").strip()
    traduzidos = {k: _aplicar_glossario(k, t, fornecedor_id) for k, t in traduzidos.items()}
    return traduzidos, uso_total


def mensagem_categorizar(dados: dict, categorias_reais: list, tags_reais: list) -> tuple:
    """(mensagem, caminho_para_cat, nome_unico_para_cat, por_id_cat, nomes_tag) — portal linhas 10539–10572."""
    por_id_cat = {c["id"]: c for c in categorias_reais}

    def _caminho(cat: dict) -> str:
        partes, visto, actual = [], set(), cat
        while actual and actual["id"] not in visto:
            visto.add(actual["id"])
            partes.append(actual["name"])
            actual = por_id_cat.get(actual.get("parent"))
        return " > ".join(reversed(partes))

    caminho_para_cat = {_caminho(c): c for c in categorias_reais}
    nomes_cat = sorted(caminho_para_cat.keys())
    nome_unico_para_cat = {}
    for c in categorias_reais:
        nome_unico_para_cat[c["name"]] = None if c["name"] in nome_unico_para_cat else c
    nomes_tag = sorted({t["name"] for t in tags_reais})
    resumo_produto = "\n".join(f"{k}: {v}" for k, v in dados.items() if k in ("titulo", "descricao_curta", "descricao", "marca") and v)
    mensagem = (
        f"Produto:\n{resumo_produto}\n\n"
        f"Categorias disponíveis (caminho completo): {json.dumps(nomes_cat, ensure_ascii=False)}\n"
        f"Tags disponíveis: {json.dumps(nomes_tag, ensure_ascii=False)}"
    )
    return mensagem, caminho_para_cat, nome_unico_para_cat, por_id_cat, nomes_tag


def tarefa_categorizar(modelo: Callable, dados: dict, categorias_reais: list, tags_reais: list,
                       instrucoes_extra: str) -> Optional[dict]:
    """{"categorias", "categorias_ids", "tags", "uso"} só com nomes REAIS, ou None (falha fechada).
    Quando a resposta não valida devolve-se na mesma o uso (a chamada foi paga): {"falhou": True, "uso": …}."""
    mensagem, caminho_para_cat, nome_unico_para_cat, por_id_cat, nomes_tag = mensagem_categorizar(dados, categorias_reais, tags_reais)
    data = modelo(instrucao_categorizar(instrucoes_extra), mensagem, 300, 30)
    uso = data.get("usage", {})
    texto = _texto_resposta(data)
    try:
        parsed = json.loads(texto)
    except Exception:
        return {"falhou": True, "uso": uso}
    escolhidas = []
    for texto_cat in (parsed.get("categorias") or []):
        cat = caminho_para_cat.get(texto_cat) or nome_unico_para_cat.get(texto_cat)
        if cat:
            escolhidas.append(cat)
    ascendentes = set()
    for c in escolhidas:
        actual, visto = por_id_cat.get(c.get("parent")), set()
        while actual and actual["id"] not in visto:
            visto.add(actual["id"])
            ascendentes.add(actual["id"])
            actual = por_id_cat.get(actual.get("parent"))
    folhas = [c for c in escolhidas if c["id"] not in ascendentes]
    if folhas:
        escolhidas = folhas
    tags_validas = [t for t in (parsed.get("tags") or []) if t in nomes_tag]
    if not escolhidas:
        return {"falhou": True, "uso": uso}
    return {"categorias": [c["name"] for c in escolhidas], "categorias_ids": [c["id"] for c in escolhidas],
            "tags": tags_validas, "uso": uso}


def mensagem_relacionados(dados: dict, candidatos: list) -> str:
    resumo_produto = "\n".join(f"{k}: {v}" for k, v in dados.items() if k in ("titulo", "descricao_curta", "marca") and v)
    lista_candidatos = "\n".join(f"- {c['ref']}: {c['titulo']}" for c in candidatos)
    return f"Produto:\n{resumo_produto}\n\nCandidatos disponíveis:\n{lista_candidatos}"


def tarefa_relacionados(modelo: Callable, dados: dict, candidatos: list, instrucoes_extra: str) -> Optional[dict]:
    if not candidatos:
        return {"cross_sell": [], "upsell": [], "uso": {}}
    refs_validos = {c["ref"] for c in candidatos}
    data = modelo(instrucao_relacionados(instrucoes_extra), mensagem_relacionados(dados, candidatos), 300, 30)
    texto = _texto_resposta(data)
    try:
        texto_json = texto[texto.index("{"):texto.rindex("}") + 1]
        resultado = json.loads(texto_json)
        cross_sell = [r for r in (resultado.get("cross_sell") or []) if r in refs_validos][:5]
        upsell = [r for r in (resultado.get("upsell") or []) if r in refs_validos][:3]
        return {"cross_sell": cross_sell, "upsell": upsell, "uso": data.get("usage", {})}
    except Exception:
        return {"falhou": True, "uso": data.get("usage", {})}


# ══ Entrada pela ponte ════════════════════════════════════════════════════════

def executar(pedido: dict, modelo: Callable) -> dict:
    """Corre uma tarefa e devolve sempre um dicionário: {"ok": True, …} ou {"ok": False, "tipo", "erro", "lingua"}."""
    t = pedido.get("tarefa")
    a = pedido.get("args") or {}
    fid = pedido.get("fornecedor_id")
    try:
        if t == "texto":
            texto, uso = tarefa_texto(modelo, a["campo"], a["valor"], a["como"], a.get("instrucoes") or "", fid)
            return {"ok": True, "texto": texto, "uso": uso}
        if t == "valores":
            out, uso = tarefa_valores(modelo, a["valores"], a.get("instrucoes") or "", fid)
            return {"ok": True, "valores": out, "uso": uso}
        if t == "nomes":
            out, uso = tarefa_nomes(modelo, a["nomes"], fid)
            return {"ok": True, "nomes": out, "uso": uso}
        if t == "categorizar":
            return {"ok": True, "resultado": tarefa_categorizar(modelo, a["dados"], a["categorias"], a["tags"], a.get("instrucoes") or "")}
        if t == "relacionados":
            return {"ok": True, "resultado": tarefa_relacionados(modelo, a["dados"], a["candidatos"], a.get("instrucoes") or "")}
        return {"ok": False, "tipo": "pedido", "erro": f"tarefa desconhecida: {t!r}"}
    except TraducaoNaoPortuguesa as e:
        return {"ok": False, "tipo": "lingua", "erro": str(e), "lingua": e.lingua}
    except RespostaComComentario as e:
        return {"ok": False, "tipo": "comentario", "erro": str(e)}
    except SemCreditos as e:
        return {"ok": False, "tipo": "sem_creditos", "erro": str(e)}
    except Exception as e:  # noqa: BLE001 — a resposta leva o erro, o portal decide
        return {"ok": False, "tipo": "erro", "erro": str(e)[:500]}


class SemCreditos(RuntimeError):
    pass


def _modelo_portal(origem: str):
    """Pedido do modelo ao portal (rota assinada). Devolve a função `modelo` para as tarefas."""
    import frappe
    import requests

    base = (frappe.conf.get("orbit_portal_url") or "").rstrip("/")
    seg = frappe.conf.get("orbit_portal_segredo")
    if not base or not seg:
        raise RuntimeError("o Orbit não tem a ligação ao portal (orbit_portal_url/orbit_portal_segredo)")

    def modelo(system: str, mensagem: str, max_tokens: int, timeout: int) -> dict:
        corpo = json.dumps({"site": frappe.local.site, "origem": origem, "system": system, "mensagem": mensagem,
                            "max_tokens": max_tokens, "timeout": timeout}, ensure_ascii=False).encode()
        r = requests.post(f"{base}/api/v1/orbit/ia-modelo", data=corpo, timeout=timeout + 15,
                          headers={"Content-Type": "application/json",
                                   "X-Orbit-Assinatura": hmac.new(seg.encode(), corpo, hashlib.sha256).hexdigest()})
        if r.status_code == 402:
            raise SemCreditos("a conta não tem créditos de IA")
        if r.status_code != 200:
            raise RuntimeError(f"Erro Anthropic ({r.status_code}): {r.text[:200]}")
        return r.json()
    return modelo


def executar_ficheiro(entrada: str, saida: str) -> None:
    """Chamado pela ponte (`importador-ia.sh`): lê o pedido em `entrada`, escreve a resposta em `saida`."""
    with open(entrada, encoding="utf-8") as fh:
        pedido = json.load(fh)
    try:
        modelo = _modelo_portal(pedido.get("origem") or "importador_ia_orbit")
        resposta = executar(pedido, modelo)
    except Exception as e:  # noqa: BLE001
        resposta = {"ok": False, "tipo": "erro", "erro": str(e)[:500]}
    with open(saida, "w", encoding="utf-8") as fh:
        json.dump(resposta, fh, ensure_ascii=False)
    print(json.dumps({"ok": True}))
