"""NIF/NIPC e morada nas fichas do CRM (23-11-2026, pedido do Vítor).

* Contactos têm **NIF** (pessoa); Empresas têm **NIPC** (pessoa colectiva).
* Guarda-se sempre o número limpo (9 dígitos para Portugal; o prefixo «PT» tira-se ANTES de validar). Um número
  estrangeiro fica com o prefixo do país (ES…, FR…).
* Portugal: dígito de controlo verificado aqui; NIPC (e qualquer número estrangeiro) também no VIES da Comissão
  Europeia. Se o VIES disser que não existe, recusa-se; se o VIES não responder, grava-se e avisa-se.
* Na empresa, o VIES devolve nome e morada: preenchem-se o nome (só se estiver vazio), a rua, o código postal e a
  localidade (só os vazios — nunca se troca o que alguém escreveu).
* Morada: a do Frappe (doctype Address, ligado pelo campo `address` do registo e pela ligação dinâmica), com rua,
  segunda linha, código postal, localidade e país.
"""
from __future__ import annotations

import json
import re

import frappe

MORADA = [("address_line1", "Rua"), ("address_line2", "Rua (cont.)"), ("pincode", "Código postal"),
          ("city", "Localidade"), ("country", "País")]
_PAISES_UE = {"AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "EL", "ES", "FI", "FR", "HR", "HU", "IE", "IT", "LT", "LU",
              "LV", "MT", "NL", "PL", "PT", "RO", "SE", "SI", "SK", "XI"}


def limpar(numero: str) -> tuple[str, str]:
    """→ (país, número). «PT 509 123 456» → ("PT", "509123456"); «ESB12345678» → ("ES", "B12345678")."""
    n = re.sub(r"[\s.\-/]", "", (numero or "").upper())
    if n[:2].isalpha() and n[:2] in _PAISES_UE | {"GR"}:
        pais = "EL" if n[:2] == "GR" else n[:2]
        return pais, n[2:]
    return "PT", n


def controlo_pt(n: str) -> bool:
    if not re.fullmatch(r"\d{9}", n or ""):
        return False
    soma = sum(int(d) * (9 - i) for i, d in enumerate(n[:8]))
    r = 11 - soma % 11
    return int(n[8]) == (0 if r >= 10 else r)


def colectivo_pt(n: str) -> bool:
    return bool(n) and n[0] in "5689"


def guardado(pais: str, n: str) -> str:
    return n if pais == "PT" else pais + n


def vies(pais: str, n: str) -> dict | None:
    """Consulta o VIES. → {"valido": bool, "nome", "morada"} ou None se o serviço não respondeu."""
    import requests
    try:
        r = requests.post("https://ec.europa.eu/taxation_customs/vies/rest-api/check-vat-number",
                          json={"countryCode": pais, "vatNumber": n}, timeout=12)
        if r.status_code != 200:
            return None
        j = r.json()
        if j.get("userError") not in (None, "VALID", "INVALID"):
            return None   # MS_UNAVAILABLE, TIMEOUT…: o serviço do país está em baixo
        nome = (j.get("name") or "").strip()
        morada = (j.get("address") or "").strip()
        return {"valido": bool(j.get("valid")), "nome": "" if nome == "---" else nome, "morada": "" if morada == "---" else morada}
    except Exception:
        return None


def partir_morada(texto: str) -> dict:
    """A morada do VIES (uma ou mais linhas, «RUA X 12\\n1234-567 LISBOA») → rua, código postal, localidade."""
    # Formato do VIES para Portugal: «AV 24 DE JULHO N 12\nLISBOA\n1249-300 LISBOA» — rua, freguesia/localidade, CP.
    linhas = [l.strip(" ,") for l in re.split(r"[\n\r]+", texto or "") if l.strip(" ,")]
    out = {}
    if not linhas:
        return out
    i_cp = next((i for i, l in enumerate(linhas) if re.search(r"\b\d{4}\s*-\s*\d{3}\b", l)), None)
    if i_cp is not None:
        m = re.search(r"(\d{4})\s*-\s*(\d{3})\s*(.*)$", linhas[i_cp])
        out["pincode"] = f"{m.group(1)}-{m.group(2)}"
        cidade = (m.group(3) or "").strip(" ,")
        if cidade:
            out["city"] = cidade.title()
        antes = linhas[:i_cp] or [linhas[i_cp][: m.start()].strip(" ,")]
    else:
        antes = linhas[:-1] if len(linhas) > 1 else linhas
        if len(linhas) > 1:
            out["city"] = linhas[-1].title()
    antes = [l for l in antes if l]
    if antes:
        out["address_line1"] = antes[0].title()[:140]
        resto = [l for l in antes[1:] if l.lower() != (out.get("city") or "").lower()]
        if resto:
            out["address_line2"] = " ".join(resto).title()[:140]
    return out


def verificar(numero: str, colectivo: bool) -> dict:
    """→ {"numero": a gravar, "aviso": texto ou "", "vies": {...} ou None}. Lança erro se o número é inválido."""
    pais, n = limpar(numero)
    if not n:
        return {"numero": "", "aviso": "", "vies": None}
    if pais == "PT":
        if not controlo_pt(n):
            frappe.throw(f"O número {n} não é um {'NIPC' if colectivo else 'NIF'} português válido (o dígito de controlo não bate certo).")
        if colectivo and not colectivo_pt(n):
            frappe.throw(f"{n} é um NIF de pessoa singular — numa empresa vai o NIPC (começa por 5, 6, 8 ou 9).")
    v = None
    if colectivo or pais != "PT":
        v = vies(pais, n)
        if v is not None and not v["valido"]:
            frappe.throw(f"O VIES (Comissão Europeia) diz que {pais}{n} não é um número de IVA válido.")
    aviso = "O VIES não respondeu agora; o número foi gravado sem esta verificação." if (colectivo or pais != "PT") and v is None else ""
    return {"numero": guardado(pais, n), "aviso": aviso, "vies": v}


# ── Morada ──────────────────────────────────────────────────────────────────────────────────────────────
def morada_de(dt: str, nome: str) -> dict:
    a = frappe.db.get_value(dt, nome, "address") if frappe.get_meta(dt).has_field("address") else None
    vals = frappe.db.get_value("Address", a, [c for c, _ in MORADA], as_dict=True) if a and frappe.db.exists("Address", a) else None
    return {c: (vals or {}).get(c) or "" for c, _ in MORADA}


def gravar_morada(dt: str, nome: str, valores: dict, so_vazios: bool = False) -> dict:
    doc = frappe.get_doc(dt, nome)
    doc.check_permission("write")
    valores = {c: (str(valores.get(c) or "").strip()[:140]) for c, _ in MORADA if c in valores}
    if valores.get("country") and not frappe.db.exists("Country", valores["country"]):
        valores.pop("country")
    a_nome = doc.get("address")
    if a_nome and frappe.db.exists("Address", a_nome):
        a = frappe.get_doc("Address", a_nome)
        for c, v in valores.items():
            if so_vazios and a.get(c):
                continue
            a.set(c, v)
        if not a.address_line1:
            a.address_line1 = a.city or "—"
        a.save(ignore_permissions=True)
    else:
        if not any(valores.get(c) for c in ("address_line1", "pincode", "city")):
            return morada_de(dt, nome)
        titulo = doc.get("organization_name") or doc.get("full_name") or nome
        a = frappe.get_doc({"doctype": "Address", "address_title": titulo, "address_type": "Billing",
                            "address_line1": valores.get("address_line1") or valores.get("city") or "—",
                            "address_line2": valores.get("address_line2"), "pincode": valores.get("pincode"),
                            "city": valores.get("city") or "—",
                            "country": valores.get("country") or ("Portugal" if frappe.db.exists("Country", "Portugal") else None),
                            "links": [{"link_doctype": dt, "link_name": nome}]})
        a.insert(ignore_permissions=True)
        frappe.db.set_value(dt, nome, "address", a.name, update_modified=False)
    return morada_de(dt, nome)


@frappe.whitelist(methods=["POST"])
def morada(doctype: str, name: str, valores: str):
    from orbit.interface.api import _guarda
    _guarda()
    if doctype not in ("Contact", "CRM Organization"):
        frappe.throw("Este registo não tem morada.")
    return gravar_morada(doctype, name, json.loads(valores or "{}"))


@frappe.whitelist(methods=["POST"])
def numero_fiscal(doctype: str, name: str, numero: str = ""):
    """Grava o NIF (Contacto) ou o NIPC (Empresa), verificado; na empresa preenche o que o VIES souber."""
    from orbit.interface.api import _guarda
    _guarda()
    campo = {"Contact": "nif", "CRM Organization": "nipc"}.get(doctype)
    if not campo or not frappe.get_meta(doctype).has_field(campo):
        frappe.throw("Este registo não tem número fiscal.")
    doc = frappe.get_doc(doctype, name)
    doc.check_permission("write")
    r = verificar(numero, colectivo=(doctype == "CRM Organization"))
    frappe.db.set_value(doctype, name, campo, r["numero"] or None)
    preenchido = []
    v = r.get("vies")
    if doctype == "CRM Organization" and v and v.get("valido"):
        if v.get("morada"):
            antes = morada_de(doctype, name)
            partes = partir_morada(v["morada"])
            if partes:
                gravar_morada(doctype, name, partes, so_vazios=True)
                depois = morada_de(doctype, name)
                preenchido += [r for c, r in MORADA if depois.get(c) != antes.get(c)]
    return {"numero": r["numero"], "aviso": r["aviso"], "nome_vies": (v or {}).get("nome") or "",
            "valido_vies": bool(v and v.get("valido")), "preenchido": preenchido}


@frappe.whitelist()
def consultar(numero: str, colectivo: int = 1):
    """Só consulta (para o ecrã mostrar o nome antes de gravar)."""
    from orbit.interface.api import _guarda
    _guarda()
    r = verificar(numero, colectivo=bool(int(colectivo or 0)))
    v = r.get("vies") or {}
    return {"numero": r["numero"], "aviso": r["aviso"], "nome": v.get("nome") or "", "morada": partir_morada(v.get("morada") or "")}
