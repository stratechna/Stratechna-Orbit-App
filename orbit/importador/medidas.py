# Cópia fiel de portal app/importador_medidas.py (21-11-2026, F5.1 do
# docs/PLANO-INVENTARIO-IMPORTADOR-ORBIT.md). Já era Python puro (só stdlib):
# nenhuma linha da lógica foi mudada — qualquer correcção faz-se nos dois sítios.
"""Peso e medidas de transporte (27-10-2026) — docs/AUDITORIA-PESO-MEDIDAS-SHOPINOX.md.

Os scrapers trazem o peso e as medidas em muitos sítios e formatos: no
mapeamento directo (`dados.peso/comprimento/largura/altura`), em atributos
(«Peso bruto (kg)», «Dimensões da embalagem (mm)», «Altura bruta»…) e com
escritas diferentes («1300×800×850mm», «C 1143mm P 607mm A 904mm»,
«1.084 mm», «850/1040», «33 / 29 kg», «1000x587x364h mm»). Para os portes
interessa o que a transportadora cobra: o BRUTO e a EMBALAGEM.

`medidas_transporte()` corre no fim da normalização de cada produto (antes
das correcções manuais, que continuam a mandar) e:
  1. junta todos os candidatos (directos e atributos) e classifica-os:
     embalagem > bruto > produto (líquido ou sem indicação);
  2. peso = o maior valor válido (o bruto é sempre ≥ líquido — decisão M2);
  3. medidas = o conjunto de 3 da melhor classe disponível; a altura é a
     medida marcada como altura (A/H/«h»), nunca adivinhada pela ordem
     quando o nome a diz;
  4. recusa valores impossíveis e regista-os em `dados.medidas_rever`;
  5. diz a origem em `campos_personalizados.medidas_origem` e
     `peso_origem` — a grelha de portes da loja põe a folga de embalagem
     (+5 cm por lado, +10 % de peso, decisão M1) só no que vem do produto.
As medidas reais do equipamento continuam no produto (a ficha mostra-as);
a folga é só para o cálculo dos portes.
"""
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

# ── Leitura de números e unidades ──────────────────────────────────────

_FACTOR_CM = {"mm": 0.1, "cm": 1.0, "m": 100.0}
_FACTOR_KG = {"g": 0.001, "gr": 0.001, "kg": 1.0, "kgs": 1.0, "t": 1000.0}


def _sem_acentos(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").lower()


def _texto(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (list, tuple)):
        return " ".join(_texto(x) for x in v)
    if isinstance(v, dict):
        return " ".join(_texto(x) for x in v.values())
    return str(v).replace(" ", " ").strip()


def _numeros(s: str, unidade_mm: bool) -> List[float]:
    """Números de um texto. «1.084» com unidade mm é mil e oitenta e quatro
    (ponto de milhar); «36.1» é decimal; «46,2» é decimal."""
    out = []
    for m in re.finditer(r"\d+(?:[.,]\d+)*", s):
        t = m.group(0)
        if unidade_mm and re.fullmatch(r"\d{1,3}(?:\.\d{3})+", t):
            t = t.replace(".", "")
        elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+,\d+", t):
            t = t.replace(".", "").replace(",", ".")
        else:
            t = t.replace(",", ".")
            if t.count(".") > 1:
                continue
        try:
            out.append(float(t))
        except ValueError:
            pass
    return out


def _unidade(nome: str, valor: str, familia: str) -> Optional[str]:
    """Unidade dita no valor ou, sem ela, no nome do campo."""
    tabela = _FACTOR_CM if familia == "cm" else _FACTOR_KG
    for fonte in (valor, nome):
        f = _sem_acentos(fonte)
        for u in sorted(tabela, key=len, reverse=True):
            if re.search(r"(?<![a-z])" + u + r"(?![a-z])", f) or re.search(r"[-_(\[ ]" + u + r"[)\]]?$", f):
                return u
    return None


def ler_peso(nome: str, valor: Any) -> Tuple[Optional[float], str]:
    """(kg, erro). Pares «33 / 29 kg» ou «60-74» dão o maior (bruto)."""
    v = _texto(valor)
    if not v:
        return None, ""
    fv = _sem_acentos(v)
    if re.search(r"\b(mm|cm)\b", fv) and not re.search(r"\bkg\b", fv):
        return None, "peso com unidade de medida (%s)" % v
    nums = _numeros(v, False)
    if not nums:
        return None, ""
    u = _unidade(nome, v, "kg") or "kg"
    kg = max(nums) * _FACTOR_KG.get(u, 1.0)
    return kg, ""


_PAPEL_LETRA = {"l": "L", "w": "L", "c": "P", "p": "P", "d": "P", "a": "A", "h": "A"}
_PAPEL_PALAVRA = (
    ("altura", "A"), ("alto", "A"), ("height", "A"),
    ("largura", "L"), ("ancho", "L"), ("width", "L"), ("frontal", "L"),
    ("profundidade", "P"), ("fondo", "P"), ("fundo", "P"), ("depth", "P"),
    ("comprimento", "C"), ("length", "C"), ("largo", "L"),
)


def _resolver_c(papeis: List[str]) -> List[str]:
    """«Comprimento» é a largura quando já há profundidade, e a
    profundidade quando já há largura."""
    out = list(papeis)
    for i, p in enumerate(out):
        if p == "C":
            out[i] = "P" if "L" in out else "L"
    return out


def _ordem_do_nome(nome: str) -> Optional[List[str]]:
    """Ordem das três medidas dita no nome do campo: «LxPxA», «LPA»,
    «LxPxH», «Comprimento x altura x profundidade»."""
    f = _sem_acentos(nome)
    m = re.search(r"(?<![a-z])([lcwpdah])\s*[x×*]\s*([lcwpdah])\s*[x×*]\s*([lcwpdah])(?![a-z])", f)
    if m:
        return [_PAPEL_LETRA[g] for g in m.groups()]
    m = re.search(r"\(([lcwpdah]{3})\)|(?<![a-z])(lpa|lca|cpa|lph|lxp)(?![a-z])", f)
    if m:
        s = (m.group(1) or m.group(2)).replace("x", "")
        if len(s) == 3:
            return [_PAPEL_LETRA.get(ch, "?") for ch in s]
    palavras = re.findall(r"altura|alto|height|largura|ancho|width|profundidade|fondo|fundo|depth|comprimento|length", f)
    if len(palavras) >= 3:
        return _resolver_c([dict(_PAPEL_PALAVRA)[p] for p in palavras[:3]])
    return None


def ler_triplo(nome: str, valor: Any) -> Tuple[Optional[Dict[str, float]], str]:
    """{L, P, A} em cm a partir de um texto com três medidas, ou (None, erro)."""
    v = _texto(valor)
    if not v:
        return None, ""
    fv = _sem_acentos(v)
    u = _unidade(nome, v, "cm")
    # «C 1143mm P 607mm A 904mm»
    letras = re.findall(r"(?<![a-z])([clpah])\s*[:=]?\s*(\d+(?:[.,]\d+)?)\s*(mm|cm|m)?", fv)
    if len(letras) >= 3 and len({l[0] for l in letras}) >= 3:
        r = {}
        for l, n, un in letras:
            papel = {"c": "L", "l": "L", "p": "P", "a": "A", "h": "A"}[l]
            r[papel] = float(n.replace(",", ".")) * _FACTOR_CM.get(un or u or "mm", 0.1)
        if len(r) == 3:
            return r, ""
    # Antes de partir em números: «850/1040» e «1.817 (1.882)» são uma medida só.
    limpo = re.sub(r"\(([^)]*)\)", "", v)
    partes = re.split(r"\s*[x×*]\s*|\s*,\s+|\s+-\s+", limpo, flags=re.I)
    partes = [p for p in partes if re.search(r"\d", p)]
    if len(partes) != 3:
        return None, "" if len(partes) < 3 else "mais de três medidas (%s)" % v
    nums = []
    marca_h = None
    for i, p in enumerate(partes):
        ns = _numeros(p, (u or "mm") == "mm")
        if not ns:
            return None, ""
        nums.append(max(ns))  # «850/1040» → 1040 (o maior, mais seguro)
        if re.search(r"\d\s*h\b|\bh\s*$", _sem_acentos(p)):
            marca_h = i
    u = u or ("mm" if max(nums) >= 250 else "cm")
    cm = [n * _FACTOR_CM[u] for n in nums]
    ordem = _ordem_do_nome(nome)
    if marca_h is not None:
        ordem = ["L", "P", "P"]
        ordem[marca_h] = "A"
        restantes = [i for i in range(3) if i != marca_h]
        ordem[restantes[0]] = "L"
        ordem[restantes[1]] = "P"
    ordem = ordem or ["L", "P", "A"]
    if sorted(ordem) != ["A", "L", "P"]:
        ordem = ["L", "P", "A"]
    return dict(zip(ordem, cm)), ""


def ler_medida(nome: str, valor: Any) -> Tuple[Optional[float], str]:
    """Uma medida só, em cm («63 cm», «1.084 mm», «51/60» → 60)."""
    v = _texto(valor)
    if not v:
        return None, ""
    u = _unidade(nome, v, "cm")
    limpo = re.sub(r"\(([^)]*)\)", "", v)
    nums = _numeros(limpo, (u or "") == "mm")
    if not nums:
        return None, ""
    u = u or ("mm" if max(nums) >= 250 else "cm")
    return max(nums) * _FACTOR_CM[u], ""


# ── Classificação dos campos ───────────────────────────────────────────

_FORA = re.compile(
    r"gas|refriger|volume|carga|capacid|intern|interior|cesta|grelha|placa|prateleira|caldeir|util|barra|massa|impasto|"
    r"cozedura|consumo|loica|diametro|encastre|bobina|tabuleiro|bandeja|porta|gaveta|cuba|plano|tampo|forno|camara|"
    r"abertura|boca|saida|entrada|kg/h|por ciclo|producao|rendimento|maxima|minima|recipiente|panela",
)


def _classe(nome: str) -> str:
    f = _sem_acentos(nome)
    if re.search(r"embal|packag|com embalagem|caixa|carton|europa|europe|overseas|exterior do pacote", f) and "sem embal" not in f:
        return "embalagem"
    if re.search(r"bruto|bruta|gross|embalad", f):
        return "bruto"
    return "produto"


def _e_peso(f: str) -> bool:
    return bool(re.search(r"(?<![a-z])(peso|weight|pedo|gewicht|net weight)(?![a-z])", f))


def _e_triplo(f: str) -> bool:
    return bool(re.search(r"dimens|medidas|lxpxa|lxpxh|lpa|outside|dimensions|tamanho|\([clpah]{3}\)", f)) or _ordem_do_nome(f) is not None


def _papel_simples(f: str) -> Optional[str]:
    for palavra, papel in _PAPEL_PALAVRA:
        if re.search(r"(?<![a-z])" + palavra, f):
            return papel
    return None


ORDEM_CLASSES = ("embalagem", "bruto", "produto")

LIMITES = {"cm_min": 1.0, "cm_max": 400.0, "kg_min": 0.05, "kg_max": 3000.0, "dens_max": 2500.0, "dens_min": 3.0}


def _fmt(x: float) -> str:
    return ("%.2f" % x).rstrip("0").rstrip(".")


def medidas_transporte(dados: dict, atributos: dict, atributos_locais: dict, campos_personalizados: dict,
                       config: Optional[dict] = None) -> dict:
    """Preenche/acerta dados.peso/comprimento/largura/altura para os portes.
    Devolve um resumo {mudou, peso_origem, medidas_origem, rever}."""
    cfg = config or {}
    if cfg.get("desligado"):
        return {"mudou": False}
    # (quem chama decide se o fornecedor tem isto ligado — «activo» na config)
    pesos: List[Tuple[float, str, str]] = []           # (kg, classe, campo)
    triplos: Dict[str, List[Tuple[Dict[str, float], str]]] = {c: [] for c in ORDEM_CLASSES}
    simples: Dict[str, Dict[str, float]] = {c: {} for c in ORDEM_CLASSES}
    rever: List[str] = []

    # Directos (mapeamento do fornecedor): contam como «produto», salvo se a
    # config do fornecedor disser que o feed já traz o bruto/embalagem.
    classe_directa = cfg.get("classe_directa", "produto")
    if dados.get("peso") not in (None, ""):
        kg, erro = ler_peso("peso", dados.get("peso"))
        if kg:
            pesos.append((kg, classe_directa, "dados.peso"))
    directo = {}
    for chave, papel in (("largura", "L"), ("comprimento", "P"), ("altura", "A")):
        if dados.get(chave) not in (None, ""):
            cm, _ = ler_medida(chave + " (cm)", dados.get(chave))
            if cm:
                directo[papel] = cm
    if len(directo) == 3:
        triplos[classe_directa].append((directo, "dados"))
    else:
        simples[classe_directa].update(directo)

    for fonte in (atributos or {}, atributos_locais or {}):
        for nome, valor in fonte.items():
            f = _sem_acentos(str(nome))
            if _FORA.search(f):
                continue
            classe = _classe(str(nome))
            if _e_peso(f):
                kg, erro = ler_peso(str(nome), valor)
                if erro:
                    rever.append("%s: %s" % (nome, erro))
                elif kg:
                    if re.search(r"bruto.{0,4}l[ií]quido|l[ií]quido.{0,4}bruto", f):
                        classe = "bruto"
                    pesos.append((kg, classe, str(nome)))
            elif _e_triplo(f) or re.search(r"\d\s*[x×*]\s*\d+(?:[.,]\d+)?\s*[x×*]\s*\d", _texto(valor), re.I):
                t, erro = ler_triplo(str(nome), valor)
                if erro:
                    rever.append("%s: %s" % (nome, erro))
                elif t:
                    triplos[classe].append((t, str(nome)))
            else:
                papel = _papel_simples(f)
                if papel:
                    cm, _ = ler_medida(str(nome), valor)
                    if cm:
                        # «Largura bruta (fundo)» é a profundidade da embalagem.
                        if papel == "L" and re.search(r"fundo|fondo", f):
                            papel = "P"
                        simples[classe].setdefault(papel, cm)

    # «Comprimento» solto: largura se faltar a largura, senão profundidade.
    for classe in ORDEM_CLASSES:
        c = simples[classe].pop("C", None)
        if c is not None:
            if "L" not in simples[classe]:
                simples[classe]["L"] = c
            elif "P" not in simples[classe]:
                simples[classe]["P"] = c

    def ok_cm(t: Dict[str, float]) -> bool:
        return all(LIMITES["cm_min"] <= t[k] <= LIMITES["cm_max"] for k in ("L", "P", "A"))

    # Medidas: a melhor classe com um conjunto de três válido.
    escolhido, origem, campo = None, "", ""
    for classe in ORDEM_CLASSES:
        cands = list(triplos[classe])
        if len(simples[classe]) == 3:
            cands.append((dict(simples[classe]), "medidas separadas"))
        for t, nome in cands:
            if ok_cm(t):
                escolhido, origem, campo = t, classe, nome
                break
            rever.append("%s: medida fora do razoável (%s cm)" % (nome, " × ".join(_fmt(t[k]) for k in ("L", "P", "A"))))
        if escolhido:
            break

    # Peso: o maior válido (bruto ≥ líquido); fora dos limites vai para revisão.
    validos = []
    for kg, classe, nome in pesos:
        if LIMITES["kg_min"] <= kg <= LIMITES["kg_max"]:
            validos.append((kg, classe, nome))
        else:
            rever.append("%s: peso fora do razoável (%s kg)" % (nome, _fmt(kg)))
    peso, peso_origem = None, ""
    if validos:
        kg, classe, nome = max(validos, key=lambda x: x[0])
        if escolhido:
            vol = escolhido["L"] * escolhido["P"] * escolhido["A"] / 1e6
            dens = kg / vol if vol else 0
            if dens > LIMITES["dens_max"]:
                rever.append("%s: %s kg em %.3f m³ é pesado demais — peso ou medidas com a unidade errada" % (nome, _fmt(kg), vol))
                kg = None
            elif vol > 0.05 and dens < LIMITES["dens_min"]:
                rever.append("%s: %s kg em %.3f m³ é leve demais — peso ou medidas com a unidade errada" % (nome, _fmt(kg), vol))
                kg = None
        if kg:
            peso, peso_origem = kg, ("bruto" if classe in ("bruto", "embalagem") else "produto")

    antes = (dados.get("peso"), dados.get("comprimento"), dados.get("largura"), dados.get("altura"))
    if peso:
        dados["peso"] = _fmt(peso)
        campos_personalizados["peso_origem"] = peso_origem
    if escolhido:
        dados["largura"], dados["comprimento"], dados["altura"] = _fmt(escolhido["L"]), _fmt(escolhido["P"]), _fmt(escolhido["A"])
        campos_personalizados["medidas_origem"] = origem
    if rever:
        dados["medidas_rever"] = sorted(set(rever))[:12]
    else:
        dados.pop("medidas_rever", None)
    depois = (dados.get("peso"), dados.get("comprimento"), dados.get("largura"), dados.get("altura"))
    return {"mudou": antes != depois, "peso_origem": peso_origem, "medidas_origem": origem,
            "medidas_campo": campo, "rever": rever}
