"""Motor determinístico do importador — porte fiel do portal para Python puro.

21-11-2026, F5.1 do docs/PLANO-INVENTARIO-IMPORTADOR-ORBIT.md (§12).

Origem: portal `app/routers/importador.py` (rota `ingerir_linhas_fornecedor`
~4031, `_normalizar_produtos` ~2720–3850 e funções auxiliares) e
`app/importador_medidas.py` (copiado para `medidas.py`). A lógica segue o
portal passo a passo, pela mesma ordem; cada bloco cita a linha de origem
(«portal ~NNNN»). Onde o portal faz uma consulta à base, aqui lê-se do `ctx`.
Nada aqui importa frappe nem sqlalchemy: só a biblioteca-padrão (3.11+).

Fica de fora, de propósito:
  * enriquecimento externo (InTouch/Icecat, HTTP) — sem `ctx["enriquecer"]`
    o motor «não enriquece»: um produto já enriquecido continua a reaplicar o
    que tem gravado (é lógica pura, portal ~3335), um produto por enriquecer
    fica como está e NÃO se marca `enriquecimento_tentado_em` (contado em
    `ignoradas["enriquecimento_por_fazer"]`);
  * a IA (tradução/optimização) — o motor só regista os pendentes
    (`pendente_ia`/`texto_bruto`), como o portal;
  * os efeitos laterais da rota (campos descobertos, exemplos, execuções,
    job de enriquecimento): o resultado diz só se o portal o teria disparado.

Forma do `ctx` (tudo o que o portal lê da base para uma passagem):

    {
      "fornecedor": {"id": int, "crm_account_id": str, "config": dict},
      "agora": datetime com fuso (UTC) — hora da passagem (now() do portal),
      "sync_run_id": str | None,
      "lista_negra": iterável de produto_ref,
      "equivalencias": [[atributo_global, valor_bruto, valor_canonico], ...]
                       (ou dict {(atributo_global, valor_bruto): canonico}),
      "categorias": {categoria_key: {"activo", "modo", "categorias_loja",
                     "categorias_loja_ids", "tags_loja", "enriquecer_traduzir",
                     "enriquecer_optimizar"}},
      "atributos_so_activos": bool  (importador_definicoes_conta),
      "globais_inactivos": iterável de atributo_global (activo = false),
      "globais_activos":   iterável de atributo_global (activo = true),
      "uso_atributos_outros": [[fornecedor_id, atributo, n], ...] — uso dos
                       atributos nos OUTROS fornecedores da conta (a parte
                       deste fornecedor conta-se aqui a partir de `existentes`),
      "total_outros": {fornecedor_id: n_produtos} — idem,
      "uso_atributos_proprio": opcional, [[fornecedor_id, atributo, n], ...] —
                       substitui a contagem deste fornecedor tirada de
                       `existentes` (quem já a tem na base pode dá-la feita),
      "excepcoes_preco": {produto_ref: {"expressao_custo", "expressao_pvp",
                          "expressao_regular", "congelado", "congelado_desde",
                          "congelado_ate"}}  (datas: date ou 'AAAA-MM-DD'),
      "correcoes_categoria": {produto_ref: {"categoria_nova", "categoria_nova_id"}}
                             (só a mais recente por produto),
      "correcoes_campo": {produto_ref: {"<coluna>.<chave>": valor}}
                         (só a mais recente por produto e campo),
      "caracteristicas_fichas": {url_origem: [texto, ...]} (só com
                                config.descricao_da_ficha),
      "existentes": {produto_ref: {"dados", "campos_personalizados",
                     "atributos", "atributos_locais", "documentos",
                     "categorias_loja", "categorias_loja_ids", "tags_loja",
                     "campos_confirmados_ia", "categoria_valor",
                     "produto_pai_ref", "atributos_variacao", "pendente_ia",
                     "texto_bruto", "ultimo_sync_run_id", "ausente_desde"}},
      "enriquecer": opcional, callable(tipo, linha, ref, ean, mpn, config)
                    -> dict | None com a forma de `_enriquecer_via_*` do
                    portal, mas com "documentos" já alojados em vez de
                    "documentos_raw".
    }

As linhas de entrada são as do push depois da conversão da rota (portal
~4050–4060) — ver `converter_linhas_push`.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from html import escape as html_escape
from typing import Any, Dict, List, Optional

try:
    from .medidas import medidas_transporte
except ImportError:  # corrido fora do pacote (guiões de ensaio)
    from medidas import medidas_transporte  # type: ignore


# ── Conversão das linhas do push (portal ~4050–4060) ─────────────────────
def converter_linhas_push(linhas: List[dict]) -> List[dict]:
    """Valores que não são texto passam a texto; listas, dicionários e as duas
    chaves especiais passam tal como vêm; None passa a ""."""
    return [
        {
            str(k): (v if (k in ("_atributos_dinamicos", "_variante_atributos") or isinstance(v, (list, dict)))
                     else ("" if v is None else str(v)))
            for k, v in linha.items()
        }
        for linha in linhas
    ]


def parametros_push(sync_run_id: Optional[str], finalizar: bool, cobertura_completa: bool) -> tuple:
    """Portal ~4064: sem sync_run_id, finalizar e cobertura_completa valem True."""
    if sync_run_id:
        return bool(finalizar), bool(cobertura_completa)
    return True, True


# ── Preços (portal ~2069–2170) ───────────────────────────────────────────
_RE_EXPRESSAO = re.compile(r"([+-])\s*(\d+(?:[.,]\d+)?)\s*(%|€)")
_RE_EXPRESSAO_ABSOLUTA = re.compile(r"^\s*=\s*(\d+(?:[.,]\d+)?)\s*\$")


def _aplicar_expressao(base: Optional[float], expr: Optional[str]) -> Optional[float]:
    # portal ~2078
    if not expr:
        return base
    m_abs = _RE_EXPRESSAO_ABSOLUTA.match(expr)
    if m_abs:
        return float(m_abs.group(1).replace(",", "."))
    if base is None:
        return base
    resultado = base
    for sinal, valor, unidade in _RE_EXPRESSAO.findall(expr):
        v = float(valor.replace(",", "."))
        if sinal == "-":
            v = -v
        resultado = resultado * (1 + v / 100) if unidade == "%" else resultado + v
    return resultado


def _calcular_linha_preco(linha: Dict[str, Any], base_valor: Optional[float]) -> Optional[float]:
    # portal ~2101
    if base_valor is None:
        return None
    if linha.get("modo") == "escaloes" and linha.get("escaloes"):
        escaloes = linha["escaloes"]
        tier = None
        for t in escaloes:
            ate = t.get("ate")
            if ate in (None, ""):
                tier = t
                break
            try:
                if base_valor <= float(ate):
                    tier = t
                    break
            except (TypeError, ValueError):
                continue
        tier = tier or escaloes[-1]
        return _aplicar_expressao(base_valor, tier.get("expressao"))
    return _aplicar_expressao(base_valor, linha.get("expressao"))


def _calcular_precos_produto(precos_cfg: dict, excepcao, preco_base: Optional[float],
                             recargo: Optional[float], congelado: bool,
                             preco_base_venda: Optional[float] = None) -> dict:
    # portal ~2123: base → custo → PVP/regular/promocional
    linha_custo = dict(precos_cfg.get("custo") or {"base": "base", "modo": "unica", "expressao": ""})
    if excepcao and excepcao.get("expressao_custo"):
        linha_custo.update({"modo": "unica", "expressao": excepcao["expressao_custo"]})
    base_do_custo = preco_base_venda if linha_custo.get("base") == "base_venda" else preco_base
    custo_produto = _calcular_linha_preco(linha_custo, base_do_custo)
    if custo_produto is not None:
        custo_produto = round(custo_produto, 4)
    custo = (custo_produto or 0) + recargo if recargo else custo_produto
    out = {"custo_produto": custo_produto, "custo": custo, "pvp": None, "regular": None, "promocional": None}
    if congelado:
        return out
    bases = {"custo": custo, "base": preco_base, "base_venda": preco_base_venda}
    linha_pvp = dict(precos_cfg.get("pvp") or {})
    linha_regular = dict(precos_cfg.get("regular") or {})
    if excepcao and excepcao.get("expressao_pvp"):
        linha_pvp.update({"modo": "unica", "expressao": excepcao["expressao_pvp"]})
    if excepcao and excepcao.get("expressao_regular"):
        linha_regular.update({"modo": "unica", "expressao": excepcao["expressao_regular"]})
    out["pvp"] = _calcular_linha_preco(linha_pvp, bases.get(linha_pvp.get("base")))
    base_regular = out["pvp"] if linha_regular.get("base") == "pvp" else bases.get(linha_regular.get("base"), custo)
    out["regular"] = _calcular_linha_preco(linha_regular, base_regular)
    linha_promo = dict(precos_cfg.get("promocional") or {})
    if linha_promo.get("modo") not in (None, "", "manual"):
        base_promo = {**bases, "pvp": out["pvp"], "regular": out["regular"]}.get(linha_promo.get("base"))
        out["promocional"] = _calcular_linha_preco(linha_promo, base_promo)
    return out


def _parse_numero(valor: Any) -> Optional[float]:
    # portal ~2171
    if valor is None:
        return None
    txt = str(valor).strip().replace("€", "").replace(" ", "")
    if not txt:
        return None
    if "," in txt:
        txt = txt.replace(".", "").replace(",", ".")
    try:
        return float(txt)
    except ValueError:
        return None


# ── Texto, slugs e unidades ──────────────────────────────────────────────
def _slug(s: Optional[str]) -> str:
    # portal ~2185
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def _sem_acentos_minusculas(texto: str) -> str:
    # portal ~503
    base = unicodedata.normalize("NFD", texto or "").encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", base).strip().lower()


def _slugify_atributo(nome: str) -> str:
    # portal ~509
    s = unicodedata.normalize('NFD', nome or '').encode('ascii', 'ignore').decode('ascii').lower()
    s = re.sub(r'[^a-z0-9]+', '_', s).strip('_')
    return 'pa_' + (s or 'atributo')


# portal ~550–585: conversão automática de unidades nos valores de atributo
_REGEX_VALOR_UNIDADE = re.compile(r'^\s*([\d]+(?:[.,]\d+)?)\s*([a-zA-Zµ°%]+)\s*$')
_UNIDADES_CONVERSAO = {
    "memoria":      ("GB", {"TB": 1024.0, "GB": 1.0, "MB": 1.0 / 1024, "KB": 1.0 / (1024 * 1024)}),
    "potencia":     ("kW", {"KW": 1.0, "W": 1.0 / 1000}),
    "peso":         ("kg", {"KG": 1.0, "G": 1.0 / 1000, "T": 1000.0}),
    "comprimento":  ("cm", {"M": 100.0, "CM": 1.0, "MM": 0.1}),
}


def _normalizar_valor_unidade(valor: Optional[str]) -> Optional[str]:
    # portal ~563
    if not valor:
        return valor
    m = _REGEX_VALOR_UNIDADE.match(str(valor))
    if not m:
        return valor
    numero_str, unidade_str = m.groups()
    try:
        numero = float(numero_str.replace(",", "."))
    except ValueError:
        return valor
    unidade_norm = unidade_str.strip().upper()
    for _familia, (unidade_canonica, factores) in _UNIDADES_CONVERSAO.items():
        if unidade_norm in factores:
            resultado = numero * factores[unidade_norm]
            texto = f"{resultado:.3f}".rstrip("0").rstrip(".")
            return f"{texto} {unidade_canonica}"
    return valor


# portal ~2205–2240
LIMITE_TAMANHO_ATRIBUTO_TRADUZIVEL = 300
CAMPOS_TEXTO_TRADUZIVEIS = {"titulo", "descricao_curta", "descricao"}
_RX_CELULA_VAZIA = re.compile(r"^Cell\d+_\d+$", re.I)
_RX_TEM_PALAVRA = re.compile(r"[A-Za-zÀ-ÿ]{3,}")


def _valor_traduzivel(valor: Any) -> bool:
    # portal ~2220
    if not isinstance(valor, str):
        return False
    v = valor.strip()
    return bool(v) and len(v) <= LIMITE_TAMANHO_ATRIBUTO_TRADUZIVEL and bool(_RX_TEM_PALAVRA.search(v))


# portal ~2263
CAMPOS_CANONICOS = {
    "titulo", "descricao_curta", "descricao", "custo", "marca",
    "preco_base_venda",
    "stock", "peso", "dimensoes", "prazo_entrega", "tipo_fornecimento",
    "comprimento", "largura", "altura", "imagem_url", "custo_recargo",
    "imagens_secundarias",
    "data_reposicao",
}


def _chave_override_para_campo_woo(campo_woo: str) -> str:
    # portal ~2310
    if campo_woo.startswith("attr::"):
        _, tipo_destino, chave_attr = campo_woo.split("::", 2)
        alvo = "atributos" if tipo_destino == "global" else "atributos_locais"
        return f"{alvo}.{chave_attr}"
    slug = _slug(campo_woo)
    canonico = slug in CAMPOS_CANONICOS
    destino_key = slug if canonico else campo_woo
    alvo = "dados" if canonico else "campos_personalizados"
    return f"{alvo}.{destino_key}"


def _aplicar_correcoes_campo(overrides: Optional[Dict[str, Any]], dados: dict, campos_personalizados: dict,
                             atributos: dict, atributos_locais: dict, pendente_ia: List[str]) -> List[str]:
    # portal ~2344
    if not overrides:
        return pendente_ia
    pendente_ia_filtrada = [c for c in pendente_ia if _chave_override_para_campo_woo(c) not in overrides]
    destinos = {"dados": dados, "campos_personalizados": campos_personalizados,
                "atributos": atributos, "atributos_locais": atributos_locais}
    for chave_completa, valor in overrides.items():
        alvo, _, chave = chave_completa.partition(".")
        destino = destinos.get(alvo)
        if destino is not None and chave:
            if alvo in ("atributos", "atributos_locais") and (valor is None or str(valor).strip() == ""):
                destino.pop(chave, None)
            else:
                destino[chave] = valor
    return pendente_ia_filtrada


def _como_lista(valor: Any) -> list:
    # portal ~2368
    if isinstance(valor, list):
        return valor
    if valor:
        return [valor]
    return []


def _resolver_identidade(linha: Dict[str, str], mapeamento: Dict[str, Any]):
    # portal ~2385
    sku = linha.get(mapeamento.get("sku") or "")
    ean = linha.get(mapeamento.get("ean") or "")
    mpn = linha.get(mapeamento.get("mpn") or "")
    ref = (sku or ean or mpn or "").strip() or None
    return ref, (ean or None), (mpn or None)


_VALORES_DROPSHIPPING_PROIBIDO = {"no", "não", "nao", "false", "0", "n"}  # portal ~2617


def _dropshipping_proibido(linha: Dict[str, str]) -> bool:
    # portal ~2620
    for campo, valor in linha.items():
        if "dropship" in (campo or "").lower():
            if (valor or "").strip().lower() in _VALORES_DROPSHIPPING_PROIBIDO:
                return True
    return False


def _assinatura_preco_stock(item: dict) -> str:
    # portal ~2633
    partes = [
        item.get("preco_pvp"), item.get("preco_regular"), item.get("preco_promocional"),
        item.get("stock"), item.get("custo"), item.get("estado_stock"),
        bool(item.get("preco_congelado")),
    ]
    if item.get("estado_stock") not in (None, "instock"):
        partes.append("sem-prazo")
    if item.get("preco_congelado") and item.get("estado_stock_com_preco"):
        partes.append("cp:" + str(item.get("estado_stock_com_preco")))
    return hashlib.sha1("|".join("" if p is None else str(p) for p in partes).encode()).hexdigest()


# ── Ficha técnica na descrição (portal ~6780–6830) ───────────────────────
FICHA_INICIO, FICHA_FIM = "<!--ficha-->", "<!--/ficha-->"


def _descricao_com_ficha(descricao: Optional[str], caracteristicas: list) -> str:
    # portal ~6823
    base = re.sub(re.escape(FICHA_INICIO) + r".*?" + re.escape(FICHA_FIM), "", descricao or "", flags=re.S).strip()
    if not caracteristicas:
        return base
    lista = "".join(f"<li>{html_escape(c)}</li>" for c in caracteristicas)
    return f"{FICHA_INICIO}<ul>{lista}</ul>{FICHA_FIM}\n{base}"


# ── Imagens excluídas à mão (portal ~11717–11752) ────────────────────────
def _chave_imagem(url: Any) -> str:
    # portal ~11717
    u = str(url or "").strip()
    if not u:
        return ""
    sem = re.sub(r"[?#].*$", "", u)
    m = re.search(r"/img/[^/]+/(?:[^/]+/)*([A-Za-z0-9_-]{16,})(?:\.[A-Za-z0-9]{2,5})?$", sem)
    if m:
        b = m.group(1).replace("-", "+").replace("_", "/")
        try:
            dec = base64.b64decode(b + "=" * ((4 - len(b) % 4) % 4), validate=True).decode("utf-8")
            if re.match(r"^https?://", dec, re.I):
                sem = re.sub(r"[?#].*$", "", dec)
        except Exception:
            pass
    return re.sub(r"^https?://(www\.)?", "", sem, flags=re.I).lower()


def _filtrar_imagens_excluidas(dados: dict) -> None:
    # portal ~11738
    excl = {_chave_imagem(c) or str(c) for c in _como_lista(dados.get("imagens_excluidas"))}
    excl |= set(str(c) for c in _como_lista(dados.get("imagens_excluidas")))
    if not excl:
        return
    sec = [u for u in _como_lista(dados.get("imagens_secundarias")) if _chave_imagem(u) not in excl]
    if "imagens_secundarias" in dados or sec:
        dados["imagens_secundarias"] = sec
    if dados.get("imagem_url") and _chave_imagem(dados["imagem_url"]) in excl:
        dados["imagem_url"] = sec.pop(0) if sec else ""
        dados["imagens_secundarias"] = sec


# ── Ausentes do feed (portal ~2655–2717) ─────────────────────────────────
LIMIAR_AUSENCIA_SUSPEITA = 0.5


def aplicar_ausencia(registo: dict, agora: datetime) -> dict:
    """O UPDATE de `_marcar_ausentes_do_feed` (portal ~2706) sobre um registo
    gravado: stock "0", assinatura apagada, ausente desde agora (se ainda não)."""
    registo = dict(registo)
    dados = dict(registo.get("dados") or {})
    dados["stock"] = "0"
    registo["dados"] = dados
    registo["hash_preco_stock"] = None
    registo["ausente_desde"] = registo.get("ausente_desde") or agora
    return registo


def _json(v: Any) -> Any:
    """O que o portal grava passa por json.dumps → jsonb → json.loads; fazer o
    mesmo aqui tira as referências partilhadas e iguala os tipos (tuplos →
    listas, chaves → texto)."""
    return json.loads(json.dumps(v))


def _data(v: Any) -> Optional[date]:
    if v is None or isinstance(v, date) and not isinstance(v, datetime):
        return v
    if isinstance(v, datetime):
        return v.date()
    return date.fromisoformat(str(v)[:10])


# ── O núcleo: portal _normalizar_produtos ~2720–3850 ─────────────────────
def normalizar(linhas: List[dict], ctx: dict, *, parcial: bool, finalizar: bool, cobertura_completa: bool) -> dict:
    """Aplica o mapeamento do fornecedor às linhas do push e devolve o que o
    portal gravaria: {"linhas": [registo por produto_ref], "ausentes":
    [produto_ref a esgotar], "ignoradas": {motivo: n}, "resumo": {...}}.
    Cada registo tem as colunas que o UPSERT do portal (~3708) escreve, mais
    `conteudo_mudou` (decide dados_actualizado_em)."""
    fornecedor = ctx["fornecedor"]
    fid = fornecedor["id"]
    sync_run_id = ctx.get("sync_run_id")
    agora: datetime = ctx.get("agora") or datetime.now(timezone.utc)
    if agora.tzinfo is None:
        agora = agora.replace(tzinfo=timezone.utc)
    config = fornecedor.get("config") or {}
    mapeamento_id = config.get("mapeamento_identidade") or {}
    mapeamento_campos = config.get("mapeamento_campos") or []
    mapeamento_atributos = config.get("mapeamento_atributos") or []
    mapeamento_documentos = config.get("mapeamento_documentos") or []
    # portal ~2768
    try:
        rx_imagem_excluir = re.compile(config["imagens_excluir_regex"], re.I) if config.get("imagens_excluir_regex") else None
    except re.error:
        rx_imagem_excluir = None
    # portal ~2773
    cfg_ficha = config.get("descricao_da_ficha") or {}
    caracteristicas_por_ficha = dict(ctx.get("caracteristicas_fichas") or {}) if cfg_ficha else {}
    mapeamento_variacao = config.get("mapeamento_variacao") or {}
    campo_categoria = config.get("campo_categoria")
    precos_cfg = config.get("precos") or {}
    tipo_fornecimento_default = config.get("tipo_fornecimento_default")
    prazo_entrega_default = config.get("prazo_entrega_default")
    transporte_default = config.get("transporte_default")
    origem_stock_default = config.get("origem_stock_default")

    # portal ~2794: lista negra
    lista_negra = set(ctx.get("lista_negra") or ())
    # portal ~2806: equivalências da conta
    eq = ctx.get("equivalencias") or {}
    if isinstance(eq, dict):
        equivalencias = dict(eq)
    else:
        equivalencias = {(a, b): c for a, b, c in eq}

    def _valor_canonico(atributo_global: str, valor: Any) -> Any:
        v = _normalizar_valor_unidade(valor)
        return equivalencias.get((atributo_global, str(v)), v)

    # portal ~2817: categorias do fornecedor
    categorias_map = dict(ctx.get("categorias") or {})
    # portal ~2840: atributos desligados pelo admin
    globais_inactivos = set(ctx.get("globais_inactivos") or ())

    # portal ~2850–2884: regra do volume (contagem feita no início da passagem)
    LIMIAR_ATRIBUTO_GLOBAL = 50
    COBERTURA_FORNECEDOR = 0.5
    uso_conta: Dict[str, int] = {}
    uso_por_fornecedor: Dict[tuple, int] = {}
    total_por_fornecedor: Dict[int, int] = {}
    for f_out, atributo, n in (ctx.get("uso_atributos_outros") or []):
        if int(f_out) == int(fid):
            continue
        uso_conta[atributo] = uso_conta.get(atributo, 0) + n
        uso_por_fornecedor[(int(f_out), atributo)] = n
    for f_out, n in (ctx.get("total_outros") or {}).items():
        if int(f_out) != int(fid):
            total_por_fornecedor[int(f_out)] = n
    existentes_map: Dict[str, dict] = ctx.get("existentes") or {}
    uso_proprio = ctx.get("uso_atributos_proprio")
    if uso_proprio is None:
        uso_proprio = uso_atributos_do_fornecedor(fid, existentes_map)
    for f_out, atributo, n in uso_proprio:
        uso_conta[atributo] = uso_conta.get(atributo, 0) + n
        uso_por_fornecedor[(f_out, atributo)] = n
    if existentes_map:
        total_por_fornecedor[int(fid)] = len(existentes_map)

    # portal ~2890: «Só globais os activos»
    so_activos = bool(ctx.get("atributos_so_activos") or False)
    globais_activos = set(ctx.get("globais_activos") or ()) if so_activos else set()

    def _atributo_e_filtravel(atributo_global: str) -> bool:
        # portal ~2902
        if atributo_global in globais_inactivos:
            return False
        if so_activos:
            return atributo_global in globais_activos
        if uso_conta.get(atributo_global, 0) >= LIMIAR_ATRIBUTO_GLOBAL:
            return True
        for fid_ref, total in total_por_fornecedor.items():
            if total and uso_por_fornecedor.get((fid_ref, atributo_global), 0) / total >= COBERTURA_FORNECEDOR:
                return True
        return False

    # portal ~2912: excepções de preço
    excepcoes_map = dict(ctx.get("excepcoes_preco") or {})

    # portal ~2950: exclusões por título/categoria
    exclusoes_cfg = config.get("exclusoes") if isinstance(config.get("exclusoes"), dict) else {}
    exclusoes_titulo = [_sem_acentos_minusculas(t) for t in ((exclusoes_cfg or {}).get("titulo") or []) if str(t).strip()]
    exclusoes_categoria = [_sem_acentos_minusculas(c) for c in ((exclusoes_cfg or {}).get("categorias") or []) if str(c).strip()]
    campo_titulo_exclusao = next(
        (m.get("campo_fornecedor") for m in mapeamento_campos if (m.get("campo_woo") or "").strip().lower() == "titulo"),
        "name",
    )
    ignorados_exclusao = 0

    # portal ~2959: recategorizações manuais (a mais recente por produto)
    correcoes_manuais = {}
    correcoes_manuais_id = {}
    for ref_c, row in (ctx.get("correcoes_categoria") or {}).items():
        correcoes_manuais[ref_c] = row.get("categoria_nova")
        if row.get("categoria_nova_id"):
            correcoes_manuais_id[ref_c] = int(row["categoria_nova_id"])

    # portal ~2977: edições manuais de campo
    correcoes_campo = ctx.get("correcoes_campo") or {}

    hoje = agora.astimezone(timezone.utc).date()  # portal ~2979 (datetime.utcnow().date())
    processados = ignorados_lista_negra = ignorados_categoria = ignorados_dropshipping = 0
    ignorados_parcial_novo = 0
    ignorados_sem_ref = 0
    enriquecimento_por_fazer = 0
    produtos_alterados = 0
    refs_vistas: set = set()
    gravadas: Dict[str, dict] = {}
    enriquecer_cb = ctx.get("enriquecer")

    for linha in linhas:
        # portal ~2995
        ref, ean, mpn = _resolver_identidade(linha, mapeamento_id)
        if not ref:
            ignorados_sem_ref += 1
            continue
        if ref in lista_negra:
            ignorados_lista_negra += 1
            continue
        # portal ~3011
        if _dropshipping_proibido(linha):
            ignorados_dropshipping += 1
            continue
        # portal ~3015
        if exclusoes_titulo or exclusoes_categoria:
            alvo_titulo = _sem_acentos_minusculas(str(linha.get(campo_titulo_exclusao) or ""))
            alvo_categoria = _sem_acentos_minusculas(str(linha.get(campo_categoria) or "")) if campo_categoria else ""
            bate_titulo = any(
                re.search(t[1:], alvo_titulo) if t.startswith("~") else (t in alvo_titulo)
                for t in exclusoes_titulo
            )
            if bate_titulo or (alvo_categoria and alvo_categoria in exclusoes_categoria):
                ignorados_exclusao += 1
                continue

        # cópia profunda: o portal relê da base, nada do que muda aqui toca no ctx
        existente = copy.deepcopy(existentes_map.get(ref) or {})

        # portal ~3037: a Sync1 nunca cria produtos
        if parcial and not existente:
            ignorados_parcial_novo += 1
            continue

        # portal ~3049: categoria (reusa a gravada se a linha não trouxer a chave)
        if campo_categoria and campo_categoria not in linha and existente.get("categoria_valor"):
            categoria_valor = existente["categoria_valor"]
        else:
            categoria_valor = linha.get(campo_categoria) if campo_categoria else None
        categoria_cfg = categorias_map.get(categoria_valor) if categoria_valor else None
        if campo_categoria and (not categoria_cfg or not categoria_cfg["activo"]):
            ignorados_categoria += 1
            continue

        dados_existentes = existente.get("dados") or {}
        personalizados_existentes = existente.get("campos_personalizados") or {}
        confirmados = dict(existente.get("campos_confirmados_ia") or {})

        dados: Dict[str, Any] = {}
        campos_personalizados: Dict[str, Any] = {}
        pendente_ia: List[str] = []
        texto_bruto: Dict[str, str] = {}
        caracteristicas_linha: list = []
        # portal ~3066: características da ficha técnica
        if caracteristicas_por_ficha:
            tipo_ficha = str(cfg_ficha.get("tipo", "")).strip().lower()
            for d_map in mapeamento_documentos:
                valor_doc = linha.get(d_map.get("campo_fornecedor") or "")
                for it in (valor_doc if isinstance(valor_doc, list) else []):
                    if isinstance(it, dict) and str(it.get("tipo", "")).strip().lower() == tipo_ficha:
                        caracteristicas_linha = caracteristicas_por_ficha.get(it.get("url") or "") or caracteristicas_linha
        categoria_traduz = bool(
            categoria_cfg and (categoria_cfg.get("enriquecer_traduzir") or categoria_cfg.get("enriquecer_optimizar"))
        )
        # portal ~3076: mapeamento de campos
        for m in mapeamento_campos:
            campo_woo = (m.get("campo_woo") or "").strip()
            if not campo_woo:
                continue
            slug = _slug(campo_woo)
            canonico = slug in CAMPOS_CANONICOS
            destino_key = slug if canonico else campo_woo
            if (m.get("origem") or "fornecedor") == "fixo":
                valor_bruto = (m.get("valor_fixo") or "").strip()
            else:
                campo_fornecedor = m.get("campo_fornecedor")
                if not campo_fornecedor:
                    continue
                # portal ~3107: chave ausente da linha → preserva o gravado
                if campo_fornecedor not in linha:
                    valor_existente = (dados_existentes if canonico else personalizados_existentes).get(destino_key)
                    if valor_existente not in (None, ""):
                        if canonico:
                            dados[destino_key] = valor_existente
                        else:
                            campos_personalizados[destino_key] = valor_existente
                    continue
                valor_bruto = linha.get(campo_fornecedor)
            if not valor_bruto:
                continue
            if slug == "descricao" and caracteristicas_linha and isinstance(valor_bruto, str):
                valor_bruto = _descricao_com_ficha(valor_bruto, caracteristicas_linha)
            precisa_ia = m.get("como_aplicar") in ("traduzido", "ia", "traduzido_ia") or (
                categoria_traduz and slug in CAMPOS_TEXTO_TRADUZIVEIS and isinstance(valor_bruto, str)
            )
            if precisa_ia:
                # portal ~3126: nunca reescreve o já semeado/traduzido
                pendente_ia.append(campo_woo)
                texto_bruto[campo_woo] = valor_bruto
                ja_existe = (dados_existentes if canonico else personalizados_existentes).get(destino_key)
                valor_final = ja_existe or valor_bruto
            else:
                valor_final = valor_bruto
            if canonico:
                dados[destino_key] = valor_final
            else:
                campos_personalizados[destino_key] = valor_final

        # portal ~3146: caso fixo da Tefcold (fornecedor 20)
        if fid == 20 and not dados.get("marca"):
            dados["marca"] = "TEFCOLD"

        # portal ~3154: a marca passa pelas equivalências da conta
        if dados.get("marca"):
            _marca_lida = str(dados["marca"]).strip()
            dados["marca"] = equivalencias.get(("marca", _marca_lida), _marca_lida)

        # portal ~3172: atributos
        atributos: Dict[str, Any] = {}
        atributos_locais: Dict[str, Any] = {}
        linha_tem_algum_campo_atributo = any(
            (a.get("campo_fornecedor") in linha) for a in mapeamento_atributos if a.get("campo_fornecedor")
        ) or ("_atributos_dinamicos" in linha)

        def _marcar_atributo_pendente(chave_armazenamento: str, valor_bruto: str, filtravel: bool,
                                      chave_canonica: Optional[str] = None):
            # portal ~3194
            tipo_destino = "global" if filtravel else "local"
            chave_pendente = f"attr::{tipo_destino}::{chave_armazenamento}"
            pendente_ia.append(chave_pendente)
            texto_bruto[chave_pendente] = valor_bruto
            existente_attr = (existente.get("atributos") if filtravel else existente.get("atributos_locais")) or {}
            valor_ja_traduzido = existente_attr.get(chave_armazenamento)
            destino = atributos if filtravel else atributos_locais
            destino[chave_armazenamento] = _valor_canonico(chave_canonica or chave_armazenamento,
                                                           valor_ja_traduzido or valor_bruto)

        # portal ~3207: atributos mapeados
        for a in mapeamento_atributos:
            campo_fornecedor = a.get("campo_fornecedor")
            atributo_global = a.get("atributo_global")
            if not campo_fornecedor or not atributo_global or not linha.get(campo_fornecedor):
                continue
            filtravel = _atributo_e_filtravel(atributo_global)
            valor_bruto_attr = linha[campo_fornecedor]
            if a.get("como_aplicar") == "traduzido" or (categoria_traduz and _valor_traduzivel(valor_bruto_attr)):
                _marcar_atributo_pendente(atributo_global, valor_bruto_attr, filtravel)
            else:
                destino = atributos if filtravel else atributos_locais
                destino[atributo_global] = _valor_canonico(atributo_global, valor_bruto_attr)
        # portal ~3229: atributos dinâmicos
        overrides_dinamicos = {a["campo_fornecedor"]: a for a in mapeamento_atributos if a.get("campo_fornecedor")}
        for nome, valor in (linha.get("_atributos_dinamicos") or {}).items():
            if not nome or valor in (None, ""):
                continue
            if isinstance(valor, str) and _RX_CELULA_VAZIA.match(valor.strip()):
                continue
            override = overrides_dinamicos.get(nome)
            chave = (override.get("atributo_global") if override else None) or nome
            filtravel = _atributo_e_filtravel(chave)
            if chave not in atributos and chave not in atributos_locais:
                chave_canonica = override.get("atributo_global") if override else _slugify_atributo(nome)
                valor_texto = str(valor)
                quer_traduzir = (
                    (override and override.get("como_aplicar") == "traduzido")
                    or (categoria_traduz and _valor_traduzivel(valor_texto))
                )
                if quer_traduzir and len(valor_texto) > LIMITE_TAMANHO_ATRIBUTO_TRADUZIVEL:
                    quer_traduzir = False
                if quer_traduzir:
                    _marcar_atributo_pendente(chave, valor_texto, filtravel, chave_canonica)
                else:
                    destino = atributos if filtravel else atributos_locais
                    destino[chave] = _valor_canonico(chave_canonica, valor)

        # portal ~3266: linha sem nenhuma chave de atributo → preserva os gravados
        if not linha_tem_algum_campo_atributo:
            atributos = dict(existente.get("atributos") or {})
            atributos_locais = dict(existente.get("atributos_locais") or {})

        # portal ~3286: enriquecimento externo
        _documentos_enriquecidos = None
        if confirmados.get("enriquecimento"):
            # portal ~3288: já enriquecido — reaplica o gravado (lógica pura)
            for origem in ("atributos", "atributos_locais"):
                for chave, valor in (existente.get(origem) or {}).items():
                    if chave in atributos or chave in atributos_locais:
                        continue
                    destino_enr = atributos if _atributo_e_filtravel(chave) else atributos_locais
                    destino_enr[chave] = valor
            for k in ("imagem_url", "imagens_secundarias"):
                if not dados.get(k) and dados_existentes.get(k):
                    dados[k] = dados_existentes[k]
            if existente.get("documentos"):
                _documentos_enriquecidos = existente["documentos"]
            for k in ("descricao_curta", "descricao", "especificacoes", "o_que_vem_na_caixa",
                      "relacionados_crosssell", "relacionados_upsell", "_matnr_interno"):
                if not dados.get(k) and dados_existentes.get(k):
                    dados[k] = dados_existentes[k]
        else:
            # portal ~3330
            tipo_enriquecimento = (config.get("enriquecimento") or {}).get("tipo")
            resultado_enriq = None
            tentado_em = confirmados.get("enriquecimento_tentado_em")
            tentado_recente = False
            if tentado_em:
                try:
                    tentado_recente = (agora - datetime.fromisoformat(tentado_em)) < timedelta(days=7)
                except (TypeError, ValueError):
                    tentado_recente = False
            if parcial or tentado_recente:
                tipo_enriquecimento = None
            elif tipo_enriquecimento in ("intouch", "icecat"):
                if enriquecer_cb is None:
                    # Desvio consciente do portal: sem HTTP não se tenta, por
                    # isso também não se marca a tentativa.
                    enriquecimento_por_fazer += 1
                    tipo_enriquecimento = None
                else:
                    confirmados["enriquecimento_tentado_em"] = agora.isoformat()
            if tipo_enriquecimento in ("intouch", "icecat") and enriquecer_cb is not None:
                resultado_enriq = enriquecer_cb(tipo_enriquecimento, linha, ref, ean, mpn, config)
            if resultado_enriq:
                # portal ~3370
                for chave, valor in (resultado_enriq.get("atributos") or {}).items():
                    if chave and valor and chave not in atributos and chave not in atributos_locais:
                        atributos[chave] = equivalencias.get((chave, str(valor)), valor)
                if resultado_enriq.get("imagem_url") and not dados.get("imagem_url"):
                    dados["imagem_url"] = resultado_enriq["imagem_url"]
                if resultado_enriq.get("imagens_secundarias") and not dados.get("imagens_secundarias"):
                    dados["imagens_secundarias"] = resultado_enriq["imagens_secundarias"]
                if resultado_enriq.get("documentos"):
                    _documentos_enriquecidos = list(resultado_enriq["documentos"])
                for k in ("descricao_curta", "descricao", "especificacoes", "o_que_vem_na_caixa"):
                    if resultado_enriq.get(k) and not dados.get(k):
                        dados[k] = resultado_enriq[k]
                for k in ("relacionados_crosssell", "relacionados_upsell"):
                    if resultado_enriq.get(k):
                        dados[k] = resultado_enriq[k]
                if tipo_enriquecimento == "intouch":
                    dados["_matnr_interno"] = linha.get("matnr") or ref
                confirmados["enriquecimento"] = True

        # portal ~3420: variantes
        produto_pai_ref = linha.get("_variante_pai_ref") or None
        atributos_variacao = {
            str(k): str(v) for k, v in (linha.get("_variante_atributos") or {}).items()
            if k and v not in (None, "")
        }
        # portal ~3446: Sync1 sem estrutura de variantes preserva a gravada
        if (parcial and existente and "_variante_pai_ref" not in linha
                and not (mapeamento_variacao.get("campo_produto_pai") and mapeamento_variacao["campo_produto_pai"] in linha)):
            produto_pai_ref = existente.get("produto_pai_ref")
            atributos_variacao = dict(existente.get("atributos_variacao") or {})
            variacao_preservada = True
        else:
            variacao_preservada = False
        # portal ~3454: variantes por configuração (fornecedores pull)
        if not produto_pai_ref and mapeamento_variacao.get("campo_produto_pai"):
            valor_pai = linha.get(mapeamento_variacao["campo_produto_pai"])
            if valor_pai:
                produto_pai_ref = str(valor_pai)
                for attr_cfg in mapeamento_variacao.get("atributos") or []:
                    campo_origem = attr_cfg.get("campo_fornecedor")
                    nome_attr = attr_cfg.get("nome_atributo")
                    if not campo_origem or not nome_attr:
                        continue
                    valor_attr = linha.get(campo_origem)
                    if valor_attr not in (None, ""):
                        atributos_variacao[str(nome_attr)] = str(valor_attr)

        # portal ~3479: tradução dos valores das variantes
        if (categoria_traduz or config.get("traduzir_variacoes")) and produto_pai_ref and not variacao_preservada:
            var_existente = existente.get("atributos_variacao") or {}
            for nome_attr, valor_attr in list(atributos_variacao.items()):
                if not _valor_traduzivel(valor_attr):
                    continue
                chave_var = f"var::{nome_attr}"
                pendente_ia.append(chave_var)
                texto_bruto[chave_var] = valor_attr
                if var_existente.get(nome_attr):
                    atributos_variacao[nome_attr] = var_existente[nome_attr]

        # portal ~3507: documentos
        def _documentos_do_campo(valor, d):
            tipo_omissao = d.get("tipo")
            apres = d.get("apresentacao", "aba")
            itens = valor if isinstance(valor, list) else [valor]
            saida = []
            for it in itens:
                if isinstance(it, dict):
                    url = (it.get("url") or "").strip()
                    tipo = (it.get("tipo") or "").strip() or tipo_omissao
                else:
                    url = str(it or "").strip()
                    tipo = tipo_omissao
                if url:
                    saida.append({"tipo": tipo, "url": url, "apresentacao": apres})
            return saida

        documentos = []
        for d in mapeamento_documentos:
            campo = d.get("campo_fornecedor")
            if campo and linha.get(campo):
                documentos.extend(_documentos_do_campo(linha[campo], d))
        if not documentos and _documentos_enriquecidos:
            documentos = _documentos_enriquecidos
        if not documentos and existente.get("documentos") and not any(
            d.get("campo_fornecedor") in linha for d in mapeamento_documentos if d.get("campo_fornecedor")
        ):
            documentos = existente["documentos"]

        # portal ~3535: fornecimento, prazo, transporte, origem do stock
        tipo_fornecimento = dados.pop("tipo_fornecimento", None) or tipo_fornecimento_default
        prazo_entrega = dados.pop("prazo_entrega", None) or prazo_entrega_default
        transporte = transporte_default
        origem_stock = origem_stock_default or "Stock do fornecedor"
        custo_recargo = _parse_numero(dados.pop("custo_recargo", None))
        # portal ~3549: preço base (nunca aplicar o desconto duas vezes)
        campo_custo_forn = next((m.get("campo_fornecedor") for m in mapeamento_campos
                                 if _slug((m.get("campo_woo") or "").strip()) == "custo"), None)
        if campo_custo_forn and campo_custo_forn in linha:
            preco_base = _parse_numero(dados.get("custo"))
            valor_base_original = dados.get("custo")
        else:
            valor_base_original = dados_existentes.get("preco_base", dados.get("custo"))
            preco_base = _parse_numero(valor_base_original)
        # portal ~3561: preço base de venda
        preco_base_venda = _parse_numero(dados.get("preco_base_venda"))
        custo_de_base_venda = (precos_cfg.get("custo") or {}).get("base") == "base_venda"
        if custo_de_base_venda:
            preco_base = valor_base_original = None

        # portal ~3567: excepção de preço e congelamento
        excepcao = excepcoes_map.get(ref)
        congelado = False
        if excepcao and excepcao.get("congelado"):
            desde, ate = _data(excepcao.get("congelado_desde")), _data(excepcao.get("congelado_ate"))
            if (not desde or desde <= hoje) and (not ate or ate >= hoje):
                congelado = True

        _precos = _calcular_precos_produto(precos_cfg, excepcao, preco_base, custo_recargo, congelado, preco_base_venda)
        # portal ~3577: o que fica gravado em dados.custo/preco_base
        if custo_de_base_venda:
            dados.pop("preco_base", None)
            dados["custo_de_venda"] = True
            if _precos["custo_produto"] is None:
                dados.pop("custo", None)
            elif preco_base_venda is not None and abs(_precos["custo_produto"] - preco_base_venda) <= 1e-9:
                dados["custo"] = dados.get("preco_base_venda")
            else:
                dados["custo"] = _precos["custo_produto"]
        elif preco_base is not None and _precos["custo_produto"] is not None and abs(_precos["custo_produto"] - preco_base) > 1e-9:
            dados.pop("custo_de_venda", None)
            dados["preco_base"] = valor_base_original
            dados["custo"] = _precos["custo_produto"]
        else:
            dados.pop("preco_base", None)
            dados.pop("custo_de_venda", None)
            if valor_base_original is not None:
                dados["custo"] = valor_base_original

        preco_pvp = preco_regular = preco_promocional = None
        if not congelado:
            preco_pvp, preco_regular, preco_promocional = _precos["pvp"], _precos["regular"], _precos["promocional"]

        # portal ~3610: categorias da loja
        if ref in correcoes_manuais:
            categorias_loja_val = [correcoes_manuais[ref]]
            categorias_loja_ids_val = (
                [correcoes_manuais_id[ref]] if ref in correcoes_manuais_id
                else list(existente.get("categorias_loja_ids") or [])
            )
            tags_loja_val = list(existente.get("tags_loja") or [])
        elif (existente.get("campos_confirmados_ia") or {}).get("categoria"):
            categorias_loja_val = list(existente.get("categorias_loja") or [])
            categorias_loja_ids_val = list(existente.get("categorias_loja_ids") or [])
            tags_loja_val = list(existente.get("tags_loja") or [])
        elif parcial:
            categorias_loja_val = list(existente.get("categorias_loja") or [])
            categorias_loja_ids_val = list(existente.get("categorias_loja_ids") or [])
            tags_loja_val = list(existente.get("tags_loja") or [])
        else:
            categorias_loja_val = list(categoria_cfg["categorias_loja"]) if categoria_cfg else []
            categorias_loja_ids_val = list(categoria_cfg["categorias_loja_ids"] or []) if categoria_cfg else []
            tags_loja_val = list(categoria_cfg["tags_loja"]) if categoria_cfg else []
            # portal ~3645: mapeamento sem id não apaga o id que o produto já tem
            if not categorias_loja_ids_val and (existente.get("categorias_loja_ids") or []):
                categorias_loja_ids_val = list(existente["categorias_loja_ids"])
                categorias_loja_val = list(existente.get("categorias_loja") or categorias_loja_val)

        # portal ~3673: imagens excluídas pelo padrão do fornecedor
        if rx_imagem_excluir is not None:
            secundarias_ok = [u for u in _como_lista(dados.get("imagens_secundarias")) if u and not rx_imagem_excluir.search(str(u))]
            if dados.get("imagem_url") and rx_imagem_excluir.search(str(dados["imagem_url"])):
                dados["imagem_url"] = secundarias_ok.pop(0) if secundarias_ok else ""
            if "imagens_secundarias" in dados or secundarias_ok:
                dados["imagens_secundarias"] = secundarias_ok
        # portal ~3686: peso e medidas para os portes
        if (config.get("medidas_transporte") or {}).get("activo"):
            medidas_transporte(dados, atributos, atributos_locais, campos_personalizados, config.get("medidas_transporte"))
            campos_personalizados.setdefault("transporte_rota", config.get("transporte_rota_default") or "directa")
            campos_personalizados.setdefault("gradeamento", config.get("gradeamento_default") or "")
        # portal ~3691: edições manuais (prioridade máxima)
        pendente_ia = _aplicar_correcoes_campo(
            copy.deepcopy(correcoes_campo.get(ref)), dados, campos_personalizados, atributos, atributos_locais, pendente_ia
        )
        # portal ~3696: imagens retiradas à mão
        _filtrar_imagens_excluidas(dados)
        # portal ~3699: origem «manual» do peso/medidas corrigidos à mão
        _manuais = correcoes_campo.get(ref) or {}
        if "dados.peso" in _manuais and "campos_personalizados.peso_origem" not in _manuais:
            campos_personalizados["peso_origem"] = "manual"
        if any(f"dados.{k}" in _manuais for k in ("comprimento", "largura", "altura")) and "campos_personalizados.medidas_origem" not in _manuais:
            campos_personalizados["medidas_origem"] = "manual"
        # portal ~3705
        if "imagens_secundarias" in dados:
            dados["imagens_secundarias"] = _como_lista(dados["imagens_secundarias"])

        # portal ~3712: Sync1 mantém os pendentes e o texto original gravados
        if parcial and existente:
            for k in (existente.get("pendente_ia") or []):
                if k not in pendente_ia:
                    pendente_ia.append(k)
            for k, v in (existente.get("texto_bruto") or {}).items():
                texto_bruto.setdefault(k, v)

        # portal ~3721: «conteúdo alterado» (decide dados_actualizado_em)
        def _conteudo_estavel(d: dict) -> dict:
            return {k: v for k, v in (d or {}).items() if k not in ("stock", "custo", "preco_base_venda", "custo_de_venda")}

        conteudo_relevante = json.dumps({
            "dados": _conteudo_estavel(dados), "campos_personalizados": campos_personalizados, "atributos": atributos,
            "atributos_locais": atributos_locais,
            "categorias_loja": categorias_loja_val, "tags_loja": tags_loja_val,
        }, sort_keys=True)
        conteudo_anterior = json.dumps({
            "dados": _conteudo_estavel(existente.get("dados") or {}), "campos_personalizados": existente.get("campos_personalizados") or {},
            "atributos": existente.get("atributos") or {}, "atributos_locais": existente.get("atributos_locais") or {},
            "categorias_loja": existente.get("categorias_loja") or [],
            "tags_loja": existente.get("tags_loja") or [],
        }, sort_keys=True) if existente else None
        conteudo_mudou = conteudo_anterior is None or conteudo_relevante != conteudo_anterior
        if conteudo_mudou:
            produtos_alterados += 1

        # portal ~3742: o UPSERT. ultimo_sync_run_id = COALESCE(novo, antigo);
        # ausente_desde volta a NULL; texto_bruto_processado não é tocado.
        gravadas[ref] = {
            "produto_ref": ref, "ean": ean, "mpn": mpn,
            "dados": _json(dados), "campos_personalizados": _json(campos_personalizados),
            "atributos": _json(atributos), "atributos_locais": _json(atributos_locais),
            "documentos": _json(documentos),
            "categorias_loja": _json(categorias_loja_val), "categorias_loja_ids": _json(categorias_loja_ids_val),
            "tags_loja": _json(tags_loja_val), "categoria_valor": categoria_valor,
            "preco_pvp": preco_pvp, "preco_regular": preco_regular, "preco_promocional": preco_promocional,
            "preco_congelado": congelado,
            "hash_preco_stock": _assinatura_preco_stock({
                "preco_pvp": preco_pvp, "preco_regular": preco_regular,
                "preco_promocional": preco_promocional, "stock": dados.get("stock"),
                "custo": dados.get("custo"), "estado_stock": None, "preco_congelado": congelado,
            }),
            "pendente_ia": _json(pendente_ia), "texto_bruto": _json(texto_bruto),
            "tipo_fornecimento": tipo_fornecimento, "prazo_entrega": prazo_entrega,
            "transporte": transporte, "origem_stock": origem_stock,
            "ultimo_sync_run_id": sync_run_id if sync_run_id is not None else (existentes_map.get(ref) or {}).get("ultimo_sync_run_id"),
            "produto_pai_ref": produto_pai_ref, "atributos_variacao": _json(atributos_variacao),
            "campos_confirmados_ia": _json(confirmados),
            "ausente_desde": None,
            "conteudo_mudou": conteudo_mudou,
        }
        refs_vistas.add(ref)
        processados += 1

    # portal ~3760–3812: produtos que saíram do feed
    ausentes: List[str] = []
    ausencia_suspeita = None
    ausentes_marcados = 0
    estado_final = {r: dict(existentes_map[r]) for r in existentes_map}
    estado_final.update(gravadas)
    filtro = None
    if sync_run_id is not None:
        if finalizar and cobertura_completa:
            filtro = lambda r, reg: reg.get("ultimo_sync_run_id") != sync_run_id  # noqa: E731 — IS DISTINCT FROM
    elif refs_vistas:
        filtro = lambda r, reg: r not in refs_vistas  # noqa: E731
    if filtro is not None and estado_final:
        total = len(estado_final)
        casam = [r for r, reg in estado_final.items() if filtro(r, reg)]
        if casam:
            if len(casam) > total * LIMIAR_AUSENCIA_SUSPEITA:
                ausencia_suspeita = {"ausentes": len(casam), "total": total}
            else:
                ausentes_marcados = len(casam)
                for r in casam:
                    reg = estado_final[r]
                    stock = (reg.get("dados") or {}).get("stock")
                    stock_txt = "" if stock is None else (stock if isinstance(stock, str) else json.dumps(stock))
                    if reg.get("ausente_desde") is None or stock_txt != "0":
                        ausentes.append(r)

    return {
        "linhas": list(gravadas.values()),
        "ausentes": ausentes,
        "ignoradas": {
            "sem_referencia": ignorados_sem_ref,
            "lista_negra": ignorados_lista_negra,
            "categoria_nao_activa": ignorados_categoria,
            "dropshipping_nao_permitido": ignorados_dropshipping,
            "parcial_produto_novo": ignorados_parcial_novo,
            "exclusao": ignorados_exclusao,
            "enriquecimento_por_fazer": enriquecimento_por_fazer,
        },
        "resumo": {
            "produtos_normalizados": processados,
            "produtos_alterados": produtos_alterados,
            "ausentes_marcados": ausentes_marcados,
            "ausencia_suspeita": ausencia_suspeita,
            # portal ~3830: o portal acordaria o job de enriquecimento
            "disparar_enriquecimento": produtos_alterados > 0 and (sync_run_id is None or finalizar),
        },
    }


def uso_atributos_do_fornecedor(fid: int, existentes: Dict[str, dict]) -> List[list]:
    """A parte de um fornecedor na contagem de uso dos atributos (portal
    ~2858): por produto, as chaves de atributos ∪ atributos_locais."""
    cont: Dict[str, int] = {}
    for reg in existentes.values():
        for k in set((reg.get("atributos") or {}).keys()) | set((reg.get("atributos_locais") or {}).keys()):
            cont[k] = cont.get(k, 0) + 1
    return [[int(fid), k, n] for k, n in cont.items()]
