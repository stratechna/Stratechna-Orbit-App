"""Faturas de compra do Docs → Orbit, F1: receber, ler com a IA do cliente e conferir (24-11-2026).

docs/PLANO-DOCS-FATURA-COMPRA-ERP.md (D1–D12 aceites a 24-11). Nesta fase nada se cria no ERP: cada fatura fica num
registo «Fatura do Docs» com o que a IA leu e o resultado da conferência. A F2 (rascunho.py) liga-o a fornecedor/artigos e
faz a fatura de compra em rascunho.

Caminho:
1. O Docs tem um fluxo «Fatura → ERP do Orbit» que, ao entrar ou mudar um documento do tipo Fatura / Fatura-recibo /
   Fatura simplificada / Nota de crédito, chama `webhook` com o id do documento e o segredo `orbit_docs_webhook`.
2. Em fila, `processar` vai buscar o PDF original à API do Docs (`orbit_docs_url`, `orbit_docs_token`) e pede à IA
   da conta dona deste Orbit (porta do portal `orbit_ia_url`, chave `orbit_ia_chave`, escopo «ia» — debita os
   créditos de IA dessa conta; sem créditos fica «Sem créditos») os dados da fatura numa estrutura fixa.
3. Confere: soma das linhas = total sem IVA, total sem IVA + IVA = total, NIF com dígito de controlo, ATCUD em
   documentos portugueses, fatura repetida (mesmo NIF e número), emitida pela própria empresa (não é compra).
Um documento lê-se uma vez; volta a ler-se só a pedido (`ler(..., forcar=1)`).
"""
import base64
import hmac
import json
import re

import frappe
from frappe.utils import flt, getdate, now_datetime

FISCAIS = {"Fatura", "Fatura-recibo", "Fatura simplificada", "Nota de crédito"}
AREAS_COMPRA = ("02 ", "03 ", "04 ")
MAX_BYTES = 12 * 1024 * 1024

def _categorias():
    from orbit.compras.preparar import CONTAS
    return ["Mercadoria"] + list(CONTAS)


_CATEGORIAS = _categorias()   # F4 (25-11): a IA classifica cada linha numa conta de gasto (D5)

_FERRAMENTA = {
    "type": "function",
    "function": {
        "name": "registar_fatura",
        "description": "Regista os dados lidos de um documento de compra (fatura de fornecedor).",
        "parameters": {
            "type": "object",
            "properties": {
                "tipo": {"type": "string", "enum": ["Fatura", "Fatura-recibo", "Fatura simplificada", "Nota de crédito",
                                                    "Nota de débito", "Fatura pró-forma", "Recibo", "Orçamento", "Outro"]},
                "emitente": {"type": "object", "properties": {
                    "nome": {"type": "string"}, "nif": {"type": "string", "description": "Só o número, sem prefixo de país"},
                    "pais": {"type": "string", "description": "Código ISO de 2 letras"}, "morada": {"type": "string"}}},
                "destinatario": {"type": "object", "properties": {
                    "nome": {"type": "string"}, "nif": {"type": "string"}}},
                "numero": {"type": "string", "description": "Número do documento, como está escrito"},
                "data": {"type": "string", "description": "AAAA-MM-DD"},
                "vencimento": {"type": "string", "description": "AAAA-MM-DD, se existir"},
                "atcud": {"type": "string"},
                "moeda": {"type": "string", "description": "Código ISO, ex. EUR"},
                "linhas": {"type": "array", "items": {"type": "object", "properties": {
                    "referencia": {"type": "string", "description": "Código/referência do artigo no fornecedor"},
                    "ean": {"type": "string"}, "descricao": {"type": "string"},
                    "quantidade": {"type": "number"}, "unidade": {"type": "string"},
                    "preco_unitario": {"type": "number", "description": "Sem IVA"},
                    "desconto_percentagem": {"type": "number"},
                    "taxa_iva": {"type": "number", "description": "Percentagem, ex. 23; 0 se isento ou autoliquidação"},
                    "total_sem_iva": {"type": "number", "description": "Total da linha sem IVA, depois do desconto"},
                    "categoria": {"type": "string", "enum": _CATEGORIAS,
                                  "description": "«Mercadoria» se é um artigo para revenda/stock; senão a natureza do gasto"}}}},
                "fatura_original": {"type": "string",
                                    "description": "Nas notas de crédito: o número da fatura que corrigem ou anulam"},
                "portes": {"type": "number", "description": "Portes/transporte, se vierem fora das linhas"},
                "iva_por_taxa": {"type": "array", "items": {"type": "object", "properties": {
                    "taxa": {"type": "number"}, "base": {"type": "number"}, "iva": {"type": "number"}}}},
                "total_sem_iva": {"type": "number"}, "total_iva": {"type": "number"}, "total": {"type": "number"},
                "autoliquidacao": {"type": "boolean", "description": "IVA autoliquidado pelo adquirente (intracomunitária)"},
                "observacoes": {"type": "string"},
            },
            "required": ["tipo", "emitente", "numero", "linhas", "total"],
        },
    },
}

_INSTRUCOES = (
    "Lê este documento de compra e regista-o com a ferramenta registar_fatura. Copia os valores exactamente como "
    "estão escritos (números com ponto decimal, sem símbolo de moeda). Uma linha por artigo ou serviço faturado; "
    "portes e descontos globais em campos próprios. Se o documento não for uma fatura de fornecedor (pró-forma, "
    "orçamento, recibo, extrato, guia), indica-o no tipo. Não inventes: o que não estiver no documento fica vazio. "
    "Em cada linha indica a categoria: «Mercadoria» para artigos comprados para revenda ou stock, senão a natureza "
    "do gasto. Numa nota de crédito escreve os valores sem sinal e indica a fatura que ela corrige."
)


# ── receber ──────────────────────────────────────────────────────────────────
@frappe.whitelist(allow_guest=True, methods=["POST"])
def webhook(doc_id=None, **kw):
    segredo = frappe.conf.get("orbit_docs_webhook") or ""
    dado = frappe.get_request_header("X-Orbit-Docs") or ""
    if not segredo or not hmac.compare_digest(segredo, dado):
        frappe.throw("Não autorizado.", frappe.PermissionError)
    try:
        docs_id = int(doc_id or frappe.form_dict.get("doc_id"))
    except (TypeError, ValueError):
        frappe.throw("Falta o documento.")
    frappe.enqueue("orbit.compras.docs.processar", queue="long", timeout=600, docs_id=docs_id,
                   job_id=f"orbit-fatura-docs-{frappe.local.site}-{docs_id}", deduplicate=True)
    return {"ok": True}


@frappe.whitelist(methods=["POST"])
def ler(docs_id, forcar=0):
    """Ler (ou voltar a ler) um documento do Docs, a pedido de quem trata das compras."""
    frappe.has_permission("Fatura do Docs", "write", throw=True)
    processar(int(docs_id), forcar=int(forcar or 0))
    return frappe.db.get_value("Fatura do Docs", {"docs_id": int(docs_id)}, ["name", "estado", "motivo"], as_dict=True)


# ── Docs ─────────────────────────────────────────────────────────────────────
def _docs(caminho: str, binario=False):
    import requests
    base = (frappe.conf.get("orbit_docs_url") or "").rstrip("/")
    token = frappe.conf.get("orbit_docs_token")
    if not base or not token:
        raise RuntimeError("Docs não ligado a este Orbit (orbit_docs_url / orbit_docs_token).")
    r = requests.get(f"{base}{caminho}", headers={"Authorization": f"Token {token}", "Accept": "application/json"},
                     timeout=60, stream=binario)
    r.raise_for_status()
    if binario:
        dados = r.raw.read(MAX_BYTES + 1, decode_content=True)
        if len(dados) > MAX_BYTES:
            raise RuntimeError("Documento demasiado grande para ler (mais de 12 MB).")
        return dados, (r.headers.get("content-type") or "").split(";")[0]
    return r.json()


def _nome(caminho: str, pk) -> str:
    if not pk:
        return ""
    try:
        return _docs(f"{caminho}{pk}/").get("name") or ""
    except Exception:
        return ""


# ── IA do cliente ────────────────────────────────────────────────────────────
class SemCreditos(Exception):
    pass


def _ia(dados: bytes, mime: str) -> dict:
    import requests
    url = (frappe.conf.get("orbit_ia_url") or "").rstrip("/")
    chave = frappe.conf.get("orbit_ia_chave")
    if not url or not chave:
        raise RuntimeError("IA não ligada a este Orbit (orbit_ia_url / orbit_ia_chave).")
    b64 = base64.b64encode(dados).decode()
    if mime == "application/pdf":
        parte = {"type": "file", "file": {"filename": "fatura.pdf", "file_data": f"data:application/pdf;base64,{b64}"}}
    else:
        parte = {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}
    corpo = {"model": "stratechna-ia", "max_tokens": 4000,
             "messages": [{"role": "user", "content": [{"type": "text", "text": _INSTRUCOES}, parte]}],
             "tools": [_FERRAMENTA], "tool_choice": {"type": "function", "function": {"name": "registar_fatura"}}}
    r = requests.post(f"{url}/chat/completions", json=corpo, timeout=200,
                      headers={"Authorization": f"Bearer {chave}", "X-Stratechna-Origem": "fatura_compra"})
    if r.status_code == 402:
        raise SemCreditos()
    if r.status_code >= 300:
        raise RuntimeError(f"IA respondeu {r.status_code}: {r.text[:200]}")
    msg = (r.json().get("choices") or [{}])[0].get("message") or {}
    for tc in msg.get("tool_calls") or []:
        if (tc.get("function") or {}).get("name") == "registar_fatura":
            return json.loads(tc["function"].get("arguments") or "{}")
    raise RuntimeError("A IA não devolveu os dados da fatura.")


# ── conferência ──────────────────────────────────────────────────────────────
def nif_pt_valido(nif: str) -> bool:
    n = re.sub(r"\D", "", nif or "")
    if len(n) != 9 or n[0] not in "123456789":
        return False
    soma = sum(int(n[i]) * (9 - i) for i in range(8))
    dig = 11 - soma % 11
    return int(n[8]) == (0 if dig >= 10 else dig)


def _limpar_nif(nif: str, pais: str) -> str:
    n = re.sub(r"[\s.\-]", "", (nif or "").upper())
    if n[:2].isalpha() and len(n) > 2:
        n = n[2:] if n[:2] == (pais or "PT").upper() or n[:2] == "PT" else n
    return n


def _perto(a, b, tol):
    return abs(flt(a) - flt(b)) <= tol


def conferir(d: dict, empresa_nif: str) -> tuple[str, list, dict]:
    """(estado, motivos, extra) a partir do que a IA leu."""
    motivos, extra = [], {}
    tipo = d.get("tipo") or ""
    em = d.get("emitente") or {}
    pais = (em.get("pais") or "PT").upper()[:2]
    nif = _limpar_nif(em.get("nif"), pais)
    dest = _limpar_nif((d.get("destinatario") or {}).get("nif"), "PT")
    extra.update(nif=nif, pais=pais, dest=dest)
    emp = re.sub(r"\D", "", empresa_nif or "")
    if emp and nif and re.sub(r"\D", "", nif) == emp:
        return "Não é compra", ["Emitida pela própria empresa (é uma venda)."], extra
    if tipo in ("Fatura pró-forma", "Orçamento", "Recibo", "Outro"):
        return "Não é compra", [f"Documento do tipo «{tipo}» — não é uma fatura de compra."], extra
    if emp and dest and re.sub(r"\D", "", dest) != emp:
        motivos.append(f"O destinatário (NIF {dest}) não é a empresa.")
    extra["nif_valido"] = nif_pt_valido(nif) if pais == "PT" else bool(nif)
    if not nif:
        motivos.append("Sem NIF do fornecedor.")
    elif not extra["nif_valido"]:
        motivos.append(f"NIF {nif} com dígito de controlo errado.")
    if pais == "PT" and tipo in FISCAIS and not (d.get("atcud") or "").strip():
        motivos.append("Sem ATCUD (documento português).")
    linhas = d.get("linhas") or []
    soma = sum(flt(l.get("total_sem_iva")) or flt(l.get("quantidade")) * flt(l.get("preco_unitario")) *
               (1 - flt(l.get("desconto_percentagem")) / 100) for l in linhas) + flt(d.get("portes"))
    sem, iva, tot = flt(d.get("total_sem_iva")), flt(d.get("total_iva")), flt(d.get("total"))
    tol = max(0.05, 0.005 * abs(sem or tot))
    certas = True
    if sem and linhas and not _perto(soma, sem, tol):
        certas = False
        motivos.append(f"As linhas somam {soma:.2f} e o total sem IVA é {sem:.2f}.")
    if tot and (sem or iva) and not _perto(sem + iva, tot, 0.05):
        certas = False
        motivos.append(f"Total sem IVA + IVA = {sem + iva:.2f}, mas o total é {tot:.2f}.")
    por_taxa = d.get("iva_por_taxa") or []
    if por_taxa and iva and not _perto(sum(flt(x.get("iva")) for x in por_taxa), iva, 0.05):
        certas = False
        motivos.append("O IVA por taxa não soma o IVA total.")
    if not linhas:
        certas = False
        motivos.append("Nenhuma linha lida.")
    extra["contas_certas"] = certas
    return ("Lida" if not motivos else "Por rever"), motivos, extra


def _sem_sinal(d: dict) -> dict:
    """Nota de crédito: os valores ficam positivos (o sinal é dado pela devolução no ERP, F4)."""
    if (d.get("tipo") or "") != "Nota de crédito":
        return d
    for k in ("total_sem_iva", "total_iva", "total", "portes"):
        if d.get(k) is not None:
            d[k] = abs(flt(d[k]))
    for l in d.get("linhas") or []:
        for k in ("quantidade", "preco_unitario", "total_sem_iva"):
            if l.get(k) is not None:
                l[k] = abs(flt(l[k]))
    for x in d.get("iva_por_taxa") or []:
        for k in ("base", "iva"):
            if x.get(k) is not None:
                x[k] = abs(flt(x[k]))
    return d


def _data(v):
    try:
        return getdate(v) if v else None
    except Exception:
        return None


# ── o trabalho ───────────────────────────────────────────────────────────────
def processar(docs_id: int, forcar: int = 0):
    nome = frappe.db.get_value("Fatura do Docs", {"docs_id": docs_id})
    if nome and not forcar and frappe.db.get_value("Fatura do Docs", nome, "estado") not in ("Por ler", "Erro", "Sem créditos", "Devolvida"):
        return   # já lida: só a pedido (a devolvida ao Docs volta a ler-se quando o documento muda lá — F3)
    doc = frappe.get_doc("Fatura do Docs", nome) if nome else frappe.new_doc("Fatura do Docs")
    doc.docs_id = docs_id
    try:
        meta = _docs(f"/api/documents/{docs_id}/")
        tipo = _nome("/api/document_types/", meta.get("document_type"))
        etiquetas = [_nome("/api/tags/", t) for t in meta.get("tags") or []]
        if tipo not in FISCAIS and not forcar:
            return   # o fluxo do Docs só chama para estes tipos; mudou entretanto
        doc.titulo = (meta.get("title") or "")[:140]
        doc.tipo_documento = tipo
        doc.area = ", ".join(e for e in etiquetas if e[:3] in AREAS_COMPRA or e[:3] in ("01 ",))[:140]
        if any(e.startswith("01 ") for e in etiquetas) and not forcar:
            doc.estado, doc.motivo = "Não é compra", "No Docs está na Área 01 (vendas)."
            doc.save(ignore_permissions=True)
            frappe.db.commit()
            return
        mime = (meta.get("mime_type") or "").lower()
        caminho = f"/api/documents/{docs_id}/download/?original=true"
        if mime not in ("application/pdf",) and not mime.startswith("image/"):
            caminho = f"/api/documents/{docs_id}/download/"   # email/office: o PDF arquivado pelo Docs
        dados, tipo_ficheiro = _docs(caminho, binario=True)
        if tipo_ficheiro not in ("application/pdf",) and not tipo_ficheiro.startswith("image/"):
            tipo_ficheiro = "application/pdf" if dados[:4] == b"%PDF" else tipo_ficheiro
        doc.estado = "A ler"
        lido = _sem_sinal(_ia(dados, tipo_ficheiro))
        # 25-11-2026 (várias empresas, D5): a empresa é a do NIF do adquirente na fatura; emitida por uma empresa do
        # tenant → é dessa (o conferir vê que é uma venda); sem NIF conhecido → a principal, e o conferir avisa
        from orbit.empresas import por_nif, principal
        empresa = por_nif((lido.get("emitente") or {}).get("nif")) or por_nif((lido.get("destinatario") or {}).get("nif")) \
            or principal()
        estado, motivos, extra = conferir(lido, frappe.db.get_value("Company", empresa, "tax_id") if empresa else "")
        em = lido.get("emitente") or {}
        doc.update({
            "estado": estado, "motivo": "\n".join(motivos), "fornecedor_nome": (em.get("nome") or "")[:140],
            "fornecedor_nif": extra.get("nif") or "", "fornecedor_pais": extra.get("pais") or "",
            "nif_valido": 1 if extra.get("nif_valido") else 0, "destinatario_nif": extra.get("dest") or "",
            "numero": (lido.get("numero") or "")[:140], "data_fatura": _data(lido.get("data")),
            "fatura_original": (lido.get("fatura_original") or "")[:140],
            "vencimento": _data(lido.get("vencimento")), "atcud": (lido.get("atcud") or "")[:140],
            "moeda": (lido.get("moeda") or "EUR")[:3].upper(), "total_sem_iva": flt(lido.get("total_sem_iva")),
            "total_iva": flt(lido.get("total_iva")), "total": flt(lido.get("total")),
            "contas_certas": 1 if extra.get("contas_certas") else 0,
            "linhas": json.dumps(lido.get("linhas") or [], ensure_ascii=False, indent=1),
            "resposta": json.dumps(lido, ensure_ascii=False, indent=1), "lida_em": now_datetime(),
        })
        if doc.fornecedor_nif:
            fornecedor = frappe.db.get_value("Supplier", {"tax_id": doc.fornecedor_nif}, "name")
            if fornecedor:
                doc.fornecedor = fornecedor
        if doc.fornecedor_nif and doc.numero and estado in ("Lida", "Por rever"):
            outra = frappe.db.get_value("Fatura do Docs", {"fornecedor_nif": doc.fornecedor_nif, "numero": doc.numero,
                                                           "docs_id": ["!=", docs_id]}, "name")
            if outra:
                doc.duplicada_de = outra
                doc.estado = "Por rever"
                doc.motivo = ((doc.motivo + "\n") if doc.motivo else "") + f"Repetida: a mesma fatura já está em {outra}."
        if doc.estado in ("Lida", "Por rever"):
            # F2: fornecedor, artigos, encomenda e fatura de compra em rascunho (orbit/compras/rascunho.py)
            from orbit.compras.rascunho import para_registo
            para_registo(doc, etiquetas, dados)
    except SemCreditos:
        doc.estado, doc.motivo = "Sem créditos", "A conta não tem créditos de IA. Volta a ler quando houver créditos."
    except Exception as e:  # noqa: BLE001
        doc.estado, doc.motivo = "Erro", str(e)[:500]
        frappe.log_error(f"Fatura do Docs {docs_id}: {e}", "orbit compras F1")
    doc.save(ignore_permissions=True)
    frappe.db.commit()
