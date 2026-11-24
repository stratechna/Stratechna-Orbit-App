"""Características de um artigo para a proposta, em «Nome: valor» (24-11-2026).

Os artigos que vieram do importador (espelho) trazem os atributos da loja com o nome técnico do WooCommerce
(«pa_potencia_w: 550/370», «pa_capacidade_da_cuba: 10 L»); aqui passam a «Potência (W): 550/370». Os que foram
revistos numa proposta trazem já `orbit_caracteristicas` — esses mandam.
"""
import re

import frappe

# palavras sem acento no nome técnico → como se escrevem
_PALAVRAS = {
    "potencia": "potência", "alimentacao": "alimentação", "pais": "país", "codigo": "código", "protecao": "proteção",
    "dimensoes": "dimensões", "dimensao": "dimensão", "tensao": "tensão", "frequencia": "frequência",
    "refrigeracao": "refrigeração", "eletrica": "elétrica", "eletrico": "elétrico", "producao": "produção",
    "energetica": "energética", "descongelacao": "descongelação", "iluminacao": "iluminação", "numero": "número",
    "maxima": "máxima", "minima": "mínima", "maximo": "máximo", "minimo": "mínimo", "util": "útil", "agua": "água",
    "gas": "gás", "liquido": "líquido", "camara": "câmara", "rotacao": "rotação", "tamanho": "tamanho",
    "espessura": "espessura", "construcao": "construção", "instalacao": "instalação", "ligacao": "ligação",
    "regulacao": "regulação", "exposicao": "exposição", "conservacao": "conservação", "climatica": "climática",
    "termostato": "termóstato", "graus": "graus", "aco": "aço", "pressao": "pressão", "valvula": "válvula",
    "tabuleiros": "tabuleiros", "nivel": "nível", "ruido": "ruído", "area": "área", "util": "útil",
}
_UNIDADES = {"w": "W", "kw": "kW", "kg": "kg", "g": "g", "mm": "mm", "cm": "cm", "m": "m", "l": "l", "v": "V",
             "hz": "Hz", "rpm": "rpm", "m3": "m³", "m2": "m²", "c": "°C", "a": "A", "kwh": "kWh", "h": "h", "db": "dB"}
# nunca na proposta: dados internos da loja
_IGNORAR = {"category_key", "codigo_hs", "marca", "brand", "supplier", "fornecedor", "ean", "gtin", "sku",
            "tipo_de_fornecimento", "fabricante", "modelo_pai", "origem_stock"}


def rotulo(chave: str) -> str | None:
    k = re.sub(r"^pa_", "", (chave or "").strip().lower())
    if not k or k in _IGNORAR:
        return None
    if not chave.lower().startswith("pa_") and " " in chave.strip():
        return chave.strip()   # já é um nome escrito por alguém («Características», «Reserva refrigerada»)
    partes = [p for p in k.split("_") if p]
    unidade = None
    if len(partes) > 1 and partes[-1] in _UNIDADES:
        unidade = _UNIDADES[partes.pop()]
    texto = " ".join(_PALAVRAS.get(p, p) for p in partes)
    texto = texto[:1].upper() + texto[1:]
    return f"{texto} ({unidade})" if unidade else texto


def _pares(texto: str):
    for bruto in (texto or "").splitlines():
        bruto = bruto.strip().lstrip("•-– ").strip()
        if ":" not in bruto:
            continue
        k, v = bruto.split(":", 1)
        if v.strip():
            yield k.strip(), v.strip()


def do_artigo(item) -> str:
    """O texto «Nome: valor» por linha para a proposta (vazio se o artigo não tiver nada)."""
    if isinstance(item, str):
        item = frappe.db.get_value("Item", item, ["orbit_caracteristicas", "orbit_atributos", "orbit_atributos_locais"],
                                   as_dict=True) if frappe.db.exists("Item", item) else None
    if not item:
        return ""
    if (item.get("orbit_caracteristicas") or "").strip():
        return item.get("orbit_caracteristicas").strip()
    linhas, vistos = [], set()
    for origem in ("orbit_atributos", "orbit_atributos_locais"):
        for k, v in _pares(item.get(origem) or ""):
            r = rotulo(k)
            if not r or r.lower() in vistos:
                continue
            vistos.add(r.lower())
            linhas.append(f"{r}: {v}")
    return "\n".join(linhas[:24])
