"""Importar CSV/Excel com correspondência de campos (H8 do plano da interface única, 20-11-2026).

1. `analisar`: lê o ficheiro (CSV com «;» ou «,», UTF-8 ou Latin-1, ou .xlsx), guarda-o 1 h na cache com um código
   e propõe a correspondência coluna → campo pelos nomes (pt/en).
2. `executar(simular=1)`: corre tudo dentro de uma transacção e desfaz no fim — números e erros linha a linha reais.
3. `executar(simular=0)`: importa, gravando de 100 em 100. Registos existentes (mesmo email; nas empresas mesmo NIPC ou
   nome) actualizam-se ou ignoram-se, à escolha. Sempre com as permissões da pessoa (`insert()`/`save()`).
"""
from __future__ import annotations

import csv
import io
import json
import re
import unicodedata

import frappe
from frappe.utils import flt, getdate

MAX_LINHAS = 5000

# lista → [(campo, rótulo, sinónimos)]
CAMPOS = {
    "contactos": [("full_name", "Nome completo", "nome|nome completo|full name|name|contacto|contato"),
                  ("first_name", "Nome próprio", "primeiro nome|nome proprio|first name|firstname"),
                  ("last_name", "Apelido", "apelido|ultimo nome|last name|lastname|sobrenome"),
                  ("email", "Email", "email|e mail|correio|mail|endereco de email"),
                  ("mobile_no", "Telemóvel", "telemovel|mobile|movel|celular|telemovel principal"),
                  ("phone", "Telefone", "telefone|phone|tel|telefone fixo"),
                  ("company_name", "Empresa", "empresa|company|organizacao|organization|entidade"),
                  ("designation", "Cargo", "cargo|funcao|job title|designation|titulo"),
                  ("nif", "NIF", "nif|contribuinte|vat|numero de contribuinte"),
                  ("orbit_responsavel", "Responsável (email)", "responsavel|owner|dono|gestor"),
                  ("orbit_ciclo", "Fase do ciclo de vida", "fase|ciclo de vida|lifecycle stage|fase do ciclo de vida"),
                  ("origem", "Origem", "origem|fonte|source")],
    "empresas": [("organization_name", "Nome da empresa", "empresa|nome|nome da empresa|company|company name|organizacao|organization|entidade|designacao"),
                 ("website", "Site", "site|website|url|web|pagina"), ("telefone", "Telefone", "telefone|phone|tel"),
                 ("email_geral", "Email", "email|e mail|correio"), ("nipc", "NIPC", "nipc|nif|contribuinte|vat"),
                 ("industry", "Setor", "setor|sector|industry|industria|atividade"), ("territory", "Território", "territorio|regiao|zona|distrito"),
                 ("orbit_responsavel", "Responsável (email)", "responsavel|owner|dono|gestor"),
                 ("orbit_ciclo", "Fase do ciclo de vida", "fase|ciclo de vida|lifecycle stage")],
    "leads": [("lead_name", "Nome completo", "nome|nome completo|full name|name|contacto"),
              ("first_name", "Nome próprio", "primeiro nome|nome proprio|first name"), ("last_name", "Apelido", "apelido|last name|sobrenome"),
              ("email", "Email", "email|e mail|correio|mail"), ("mobile_no", "Telemóvel", "telemovel|mobile|telefone|phone|celular"),
              ("organization", "Empresa", "empresa|company|organizacao|organization"), ("job_title", "Cargo", "cargo|funcao|job title"),
              ("source", "Origem", "origem|fonte|source"), ("status", "Estado", "estado|status"),
              ("lead_owner", "Responsável (email)", "responsavel|owner|dono|gestor")],
    "negocios": [("titulo", "Nome do negócio", "negocio|nome do negocio|titulo|deal|deal name|nome|oportunidade"),
                 ("organization", "Empresa", "empresa|company|organizacao|cliente"), ("email", "Email do contacto", "email|e mail|contacto"),
                 ("deal_value", "Valor", "valor|value|montante|amount|total"), ("status", "Fase", "fase|estado|stage|status"),
                 ("expected_closure_date", "Fecho previsto", "fecho|data de fecho|fecho previsto|close date|data prevista"),
                 ("deal_owner", "Responsável (email)", "responsavel|owner|dono|gestor"), ("source", "Origem", "origem|fonte|source")],
}
DT = {"contactos": "Contact", "empresas": "CRM Organization", "leads": "CRM Lead", "negocios": "CRM Deal"}


def _guarda(objeto=None):
    from orbit.interface.api import _guarda as g
    g()
    if objeto and objeto not in DT:
        frappe.throw("Lista desconhecida")


def _norm(s):
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return re.sub(r"[^a-z0-9 ]+", " ", "".join(c for c in s if not unicodedata.combining(c))).strip()


def _ler(nome_ficheiro: str, conteudo: bytes):
    if nome_ficheiro.lower().endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(conteudo), read_only=True, data_only=True)
        ws = wb.worksheets[0]
        linhas = [["" if v is None else (v.strftime("%Y-%m-%d") if hasattr(v, "strftime") else str(v)) for v in r]
                  for r in ws.iter_rows(values_only=True)]
    else:
        for enc in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                texto = conteudo.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        try:
            dial = csv.Sniffer().sniff(texto[:5000], delimiters=";,\t|")
        except csv.Error:
            dial = csv.excel
            dial.delimiter = ";" if texto[:2000].count(";") > texto[:2000].count(",") else ","
        linhas = list(csv.reader(io.StringIO(texto), dial))
    linhas = [l for l in linhas if any(str(c).strip() for c in l)]
    if not linhas:
        frappe.throw("O ficheiro está vazio.")
    cab = [str(c).strip() or f"Coluna {i + 1}" for i, c in enumerate(linhas[0])]
    return cab, [[str(c).strip() for c in l] + [""] * (len(cab) - len(l)) for l in linhas[1:MAX_LINHAS + 1]], len(linhas) - 1


@frappe.whitelist(methods=["POST"])
def analisar(objeto: str):
    _guarda(objeto)
    f = frappe.request.files.get("ficheiro") if frappe.request and frappe.request.files else None
    if not f:
        frappe.throw("Falta o ficheiro.")
    conteudo = f.read()
    if len(conteudo) > 15 * 1024 * 1024:
        frappe.throw("O ficheiro passa dos 15 MB.")
    cab, linhas, total = _ler(f.filename or "dados.csv", conteudo)
    codigo = frappe.generate_hash(length=16)
    frappe.cache.set_value(f"orbit:importar:{frappe.session.user}:{codigo}", {"objeto": objeto, "cab": cab, "linhas": linhas},
                           expires_in_sec=3600)
    meta = frappe.get_meta(DT[objeto])
    campos = [{"campo": c, "rotulo": r} for c, r, _s in CAMPOS[objeto] if c in ("email", "phone") or meta.has_field(c)]
    sug = {}
    usados = set()
    disp = [(c, _norm(r), [_norm(x) for x in sin.split("|")]) for c, r, sin in CAMPOS[objeto] if any(x["campo"] == c for x in campos)]
    # 1.ª volta: igual ao rótulo ou a um sinónimo; 2.ª: um sinónimo de várias palavras dentro do cabeçalho
    for volta in (1, 2):
        for i, h in enumerate(cab):
            if str(i) in sug:
                continue
            hn = _norm(h)
            for c, rn, sins in disp:
                if c in usados:
                    continue
                if (volta == 1 and (hn == rn or hn in sins)) or (volta == 2 and any(len(x) > 4 and x in hn for x in sins)):
                    sug[str(i)] = c
                    usados.add(c)
                    break
    return {"codigo": codigo, "cabecalhos": cab, "amostra": linhas[:5], "total": total, "importaveis": len(linhas),
            "campos": campos, "sugestao": sug}


def _user(v):
    v = (v or "").strip().lower()
    if not v:
        return None
    if frappe.db.exists("User", v):
        return v
    return frappe.db.get_value("User", {"full_name": ["like", v], "enabled": 1})


def _existente(objeto, d):
    e = (d.get("email") or "").lower()
    if objeto == "contactos" and e:
        return frappe.db.get_value("Contact Email", {"email_id": e, "parenttype": "Contact"}, "parent")
    if objeto == "leads" and e:
        return frappe.db.get_value("CRM Lead", {"email": e})
    if objeto == "empresas":
        nif = re.sub(r"\D", "", d.get("nipc") or "")[-9:]
        if len(nif) == 9:
            o = frappe.db.get_value("CRM Organization", {"nipc": ["like", f"%{nif}"]})
            if o:
                return o
        n = (d.get("organization_name") or "").strip()
        if n:
            return frappe.db.get_value("CRM Organization", {"organization_name": n})
    if objeto == "negocios" and d.get("titulo"):
        return frappe.db.get_value("CRM Deal", {"titulo": d["titulo"]})
    return None


def _aplicar(objeto, doc, d, novo):
    for k, v in d.items():
        if v in ("", None):
            continue
        if k in ("orbit_responsavel", "lead_owner", "deal_owner"):
            v = _user(v)
            if not v:
                continue
        if k == "deal_value":
            v = flt(str(v).replace("€", "").replace(" ", "").replace(".", "").replace(",", ".")) if "," in str(v) else flt(v)
        if k == "expected_closure_date":
            v = getdate(v)
        if k in ("email", "phone") and objeto == "contactos":
            continue
        if k == "full_name" and objeto == "contactos":
            if novo and not d.get("first_name"):
                partes = v.split()
                doc.first_name = partes[0]
                doc.last_name = " ".join(partes[1:]) or None
            continue
        if k == "lead_name" and objeto == "leads":
            if not d.get("first_name"):
                partes = v.split()
                doc.first_name = partes[0]
                doc.last_name = " ".join(partes[1:]) or None
            continue
        if k == "email" and objeto == "negocios":
            continue
        if doc.meta.has_field(k):
            doc.set(k, v)
    if objeto == "contactos":
        e = (d.get("email") or "").strip().lower()
        if e and not any((x.email_id or "").lower() == e for x in doc.get("email_ids") or []):
            doc.append("email_ids", {"email_id": e, "is_primary": 0 if doc.get("email_ids") else 1})
        t = (d.get("phone") or "").strip()
        if t and not any(x.phone == t for x in doc.get("phone_nos") or []):
            doc.append("phone_nos", {"phone": t})
    if objeto == "negocios" and novo:
        e = (d.get("email") or "").strip().lower()
        c = frappe.db.get_value("Contact Email", {"email_id": e, "parenttype": "Contact"}, "parent") if e else None
        if c:
            doc.append("contacts", {"contact": c, "is_primary": 1})
        if doc.get("organization") and not frappe.db.exists("CRM Organization", doc.organization):
            doc.organization = None


@frappe.whitelist(methods=["POST"])
def executar(codigo: str, mapeamento: str, modo: str = "atualizar", simular: int = 1, marcador: str = None):
    """`mapeamento` = {índice da coluna: campo}; `modo` = atualizar | ignorar (registos que já existem)."""
    dados = frappe.cache.get_value(f"orbit:importar:{frappe.session.user}:{codigo}")
    if not dados:
        frappe.throw("O ficheiro já não está disponível — carregue-o de novo.")
    objeto = dados["objeto"]
    _guarda(objeto)
    dt = DT[objeto]
    mapa = {int(k): v for k, v in json.loads(mapeamento or "{}").items() if v}
    validos = {c for c, _r, _s in CAMPOS[objeto]}
    if any(v not in validos for v in mapa.values()):
        frappe.throw("Campo desconhecido na correspondência.")
    if not frappe.has_permission(dt, "create"):
        frappe.throw("Sem permissão para criar.", frappe.PermissionError)
    novos, atualizados, ignorados, erros = 0, 0, 0, []
    gravados = []   # 25-11-2026 (segmentação S1–S8): o «Marcador» da importação vai para os importados
    frappe.flags.orbit_sem_recuperar = True
    for n, linha in enumerate(dados["linhas"], start=2):
        d = {campo: (linha[i] if i < len(linha) else "") for i, campo in mapa.items()}
        if not any(str(v).strip() for v in d.values()):
            continue
        frappe.db.savepoint("orbit_importar")
        try:
            nome = _existente(objeto, d)
            if nome and modo == "ignorar":
                ignorados += 1
                continue
            doc = frappe.get_doc(dt, nome) if nome else frappe.new_doc(dt)
            _aplicar(objeto, doc, d, not nome)
            if nome:
                doc.save()
                atualizados += 1
            else:
                doc.insert()
                novos += 1
            gravados.append(doc.name)
        except Exception as e:  # noqa: BLE001
            frappe.db.rollback(save_point="orbit_importar")
            msg = re.sub(r"<[^>]+>", "", str(e))[:160] or e.__class__.__name__
            erros.append({"linha": n, "erro": msg})
        if not int(simular) and (novos + atualizados) % 100 == 0:
            frappe.db.commit()
    if int(simular):
        frappe.db.rollback()
    else:
        frappe.db.commit()
        frappe.cache.delete_value(f"orbit:importar:{frappe.session.user}:{codigo}")
        if (marcador or "").strip() and gravados and dt in ("Contact", "CRM Lead", "CRM Organization"):
            from orbit.marketing.segmentos import marcar
            marcar(dt, gravados, marcador)
            frappe.db.commit()
    return {"simulado": bool(int(simular)), "novos": novos, "atualizados": atualizados, "ignorados": ignorados,
            "erros": erros[:200], "n_erros": len(erros)}
