"""Faturação certificada: o que é comum a todos os programas (DP8, 05-11-2026).

Em Portugal (e em Espanha) uma fatura só vale se for emitida por um programa certificado pela AT. O ERPNext não é.
Por isso o Orbit NUNCA emite documentos fiscais: prepara a venda e pede a emissão a um programa certificado
(Moloni, InvoiceXpress, TOConline, Vendus…), por um adaptador. De volta vêm o número, o ATCUD e o PDF.

Este módulo não sabe nada do Frappe nem de nenhum programa: são os tipos de dados que circulam entre o Orbit e os
adaptadores, a interface que cada adaptador cumpre e as regras que valem para todos (NIF, motivos de isenção).
Assim os adaptadores testam-se sem base de dados e sem rede.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Optional

TIPOS = ("fatura", "fatura_recibo", "nota_credito")

# Motivos de isenção da AT (tabela do SAF-T PT, campo TaxExemptionCode). Uma linha a 0 % sem motivo é recusada.
MOTIVOS_ISENCAO = {
    "M01": "Artigo 16.º, n.º 6 do CIVA",
    "M02": "Artigo 6.º do Decreto-Lei n.º 198/90, de 19 de junho",
    "M04": "Isento artigo 13.º do CIVA",
    "M05": "Isento artigo 14.º do CIVA",
    "M06": "Isento artigo 15.º do CIVA",
    "M07": "Isento artigo 9.º do CIVA",
    "M09": "IVA - não confere direito a dedução",
    "M10": "IVA - regime de isenção (artigo 53.º do CIVA)",
    "M11": "Regime particular do tabaco",
    "M12": "Regime da margem de lucro - Agências de viagens",
    "M13": "Regime da margem de lucro - Bens em segunda mão",
    "M14": "Regime da margem de lucro - Objetos de arte",
    "M15": "Regime da margem de lucro - Objetos de coleção e antiguidades",
    "M16": "Isento artigo 14.º do RITI",
    "M19": "Outras isenções",
    "M20": "IVA - regime forfetário",
    "M21": "IVA - não confere direito à dedução (ou expressão similar)",
    "M25": "Mercadorias à consignação",
    "M26": "Isenção de IVA com direito à dedução no cabaz alimentar",
    "M30": "IVA - autoliquidação (alínea i) do n.º 1 do artigo 2.º do CIVA)",
    "M31": "IVA - autoliquidação (alínea j) do n.º 1 do artigo 2.º do CIVA)",
    "M32": "IVA - autoliquidação (alínea l) do n.º 1 do artigo 2.º do CIVA)",
    "M33": "IVA - autoliquidação (alínea m) do n.º 1 do artigo 2.º do CIVA)",
    "M34": "IVA - autoliquidação (alínea n) do n.º 1 do artigo 2.º do CIVA)",
    "M40": "IVA - autoliquidação (artigo 6.º n.º 6 alínea a) do CIVA, a contrário)",
    "M41": "IVA - autoliquidação (artigo 8.º n.º 3 do RITI)",
    "M42": "IVA - autoliquidação (Decreto-Lei n.º 21/2007, de 29 de janeiro)",
    "M43": "IVA - autoliquidação (Decreto-Lei n.º 362/99, de 16 de setembro)",
    "M99": "Não sujeito ou não tributado",
}

CONSUMIDOR_FINAL = "999999990"


class ErroFaturacao(Exception):
    """Erro de um programa de faturação. `permanente` = erro dos dados (repetir não ajuda); senão é de rede ou do
    serviço, e a fila volta a tentar."""

    def __init__(self, mensagem: str, permanente: bool = True, resposta=None):
        super().__init__(mensagem)
        self.permanente = permanente
        self.resposta = resposta


@dataclass
class Cliente:
    nome: str
    nif: str = ""
    email: str = ""
    morada: str = ""
    cidade: str = ""
    codigo_postal: str = ""
    pais: str = "PT"            # ISO 3166-1 alfa-2
    telefone: str = ""
    id_externo: Optional[str] = None


@dataclass
class Linha:
    codigo: str                 # referência do artigo (item_code)
    nome: str
    quantidade: float
    preco_unitario: float       # sem IVA
    taxa_iva: float             # percentagem: 23, 13, 6, 0…
    desconto_pct: float = 0.0
    motivo_isencao: str = ""    # obrigatório quando taxa_iva == 0 (M01…M99)
    resumo: str = ""
    servico: bool = True
    id_externo: Optional[str] = None


@dataclass
class Pedido:
    tipo: str                   # fatura | fatura_recibo | nota_credito
    referencia: str             # nome interno no Orbit (ex.: ACC-SINV-2026-00012) — chave de idempotência
    data: str                   # AAAA-MM-DD
    vencimento: str
    cliente: Cliente
    linhas: list[Linha]
    notas: str = ""
    rascunho: bool = True
    origem_id_externo: Optional[str] = None   # nota de crédito: o documento certificado que corrige
    origem_valor: float = 0.0
    motivo: str = ""                           # nota de crédito: porquê


@dataclass
class Resultado:
    id_externo: str
    numero: str = ""
    atcud: str = ""
    estado: str = "rascunho"    # rascunho | emitido | anulado
    total: float = 0.0
    pdf_url: str = ""
    ja_existia: bool = False
    bruto: dict = field(default_factory=dict)


def limpar_nif(nif: str, pais: str = "PT") -> str:
    """O NIF guarda-se só com os dígitos. O prefixo do país sai ANTES de validar (regra da casa: «PT123…» chegava
    a passar a validação com 11 caracteres)."""
    n = re.sub(r"[\s.\-]", "", (nif or "").upper())
    if pais and n.startswith(pais.upper()):
        n = n[len(pais):]
    return n


def nif_pt_valido(nif: str) -> bool:
    if not re.fullmatch(r"\d{9}", nif or "") or nif[0] not in "123456789":
        return False
    soma = sum(int(d) * (9 - i) for i, d in enumerate(nif[:8]))
    controlo = 11 - soma % 11
    return int(nif[8]) == (0 if controlo >= 10 else controlo)


def validar_pedido(p: Pedido) -> None:
    """O que vale para qualquer programa: recusa-se aqui, antes de ir à rede, com uma mensagem que se percebe."""
    if p.tipo not in TIPOS:
        raise ErroFaturacao(f"tipo de documento desconhecido: {p.tipo}")
    if not p.linhas:
        raise ErroFaturacao("o documento não tem linhas")
    if p.cliente.pais == "PT" and p.cliente.nif and p.cliente.nif != CONSUMIDOR_FINAL \
            and not nif_pt_valido(p.cliente.nif):
        raise ErroFaturacao(f"NIF português inválido: {p.cliente.nif}")
    for l in p.linhas:
        if l.quantidade <= 0:
            raise ErroFaturacao(f"«{l.nome}»: quantidade tem de ser positiva (as devoluções são notas de crédito)")
        if l.taxa_iva == 0 and l.motivo_isencao not in MOTIVOS_ISENCAO:
            raise ErroFaturacao(f"«{l.nome}» está a 0 % de IVA sem motivo de isenção válido (M01…M99)")
    if p.tipo == "nota_credito" and not p.origem_id_externo:
        raise ErroFaturacao("a nota de crédito tem de indicar o documento certificado que corrige")


class Adaptador:
    """Interface de um programa de faturação certificado. Cada método fala com o programa e devolve dados
    simples; quem grava no Orbit é emissao.py.

    `cfg` traz as credenciais e as predefinições da Ligacao Faturacao (já desencriptadas); `guardar` é chamado
    quando o adaptador renova um token e o quer ver gravado; `transporte` permite testar sem rede."""

    nome = "base"
    rotulo = "Base"

    def __init__(self, cfg: dict, guardar: Optional[Callable[[dict], None]] = None, transporte=None):
        self.cfg = cfg or {}
        self.guardar = guardar or (lambda _d: None)
        self.transporte = transporte

    def testar_ligacao(self) -> dict:                     # {"ok": True, "empresa": "..."}
        raise NotImplementedError

    def opcoes(self) -> dict:                             # séries, taxas, prazos, métodos… para o ecrã de configuração
        raise NotImplementedError

    def garantir_cliente(self, c: Cliente) -> str:        # id externo
        raise NotImplementedError

    def garantir_artigo(self, l: Linha) -> str:           # id externo
        raise NotImplementedError

    def emitir(self, p: Pedido) -> Resultado:
        raise NotImplementedError

    def apagar_rascunho(self, tipo: str, id_externo: str) -> None:
        raise NotImplementedError

    def obter(self, tipo: str, id_externo: str) -> Resultado:
        raise NotImplementedError

    def obter_pdf(self, tipo: str, id_externo: str) -> str:
        raise NotImplementedError

    def registar_pagamento(self, cliente_id: str, data: str, valor: float, documentos: list[tuple[str, float]],
                           referencia: str = "", notas: str = "") -> Resultado:
        raise NotImplementedError

    def alterados_desde(self, desde: str) -> list[Resultado]:
        raise NotImplementedError


_REGISTO: dict[str, type[Adaptador]] = {}


def registar(cls: type[Adaptador]) -> type[Adaptador]:
    _REGISTO[cls.nome] = cls
    return cls


def adaptador(nome: str, cfg: dict, guardar=None, transporte=None) -> Adaptador:
    from orbit.faturacao import adaptadores  # noqa: F401 — regista os adaptadores
    if nome not in _REGISTO:
        raise ErroFaturacao(f"programa de faturação sem adaptador: {nome}")
    return _REGISTO[nome](cfg, guardar=guardar, transporte=transporte)


def programas() -> dict[str, str]:
    from orbit.faturacao import adaptadores  # noqa: F401
    return {n: c.rotulo for n, c in _REGISTO.items()}
