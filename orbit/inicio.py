"""Números da página inicial do Orbit — «O negócio», «O meu dia», «A precisar de atenção» e «Atividade recente».

22-11-2026 (Vítor, maqueta docs/orbit-interface/inicio/). Uma só chamada (`orbit.inicio.resumo`) devolve tudo o
que a página mostra, já filtrado pelo que a pessoa pode ver:

* os valores em dinheiro (faturação, por receber, valor dos negócios) só vão a quem tem papel de gestão ou de
  contas (`_DINHEIRO`); os outros recebem só «O meu dia», o atendimento e a atividade sem valores;
* a faturação vem do portal no Orbit da casa (o negócio da Stratechna está no Moloni pelo portal — o ERP nunca
  emite documentos fiscais, DP8) e das faturas do próprio ERP nos outros tenants, quando as houver;
* cada bloco é independente: se uma app não está instalada ou falha, esse bloco vem vazio e o resto aparece.
"""
import datetime as _dt
import hashlib
import hmac
import json

import frappe
from frappe.utils import add_days, add_months, cint, flt, get_first_day, getdate, now_datetime, nowdate

_DINHEIRO = {"System Manager", "Accounts Manager", "Accounts User", "Sales Manager"}
_PERIODOS = ("hoje", "semana", "mes", "ano")
_ABERTOS_DESK = ("Open", "Replied", "Paused")


def _pode_dinheiro() -> bool:
	u = frappe.session.user
	return u == "Administrator" or bool(_DINHEIRO & set(frappe.get_roles(u)))


def _existe(dt: str) -> bool:
	try:
		return bool(frappe.db.table_exists(dt)) and frappe.has_permission(dt, "read")
	except Exception:
		return False


def _intervalo(periodo: str):
	"""(início, fim, início anterior, fim anterior) — o anterior é o mesmo troço do período antes."""
	h = getdate(nowdate())
	if periodo == "hoje":
		return h, h, add_days(h, -1), add_days(h, -1)
	if periodo == "semana":
		i = add_days(h, -h.weekday())
		return i, h, add_days(i, -7), add_days(h, -7)
	if periodo == "ano":
		i = h.replace(month=1, day=1)
		return i, h, i.replace(year=i.year - 1), h.replace(year=h.year - 1)
	i = get_first_day(h)
	return i, h, add_months(i, -1), add_months(h, -1)


def _meses(n=6):
	h = getdate(nowdate())
	base = get_first_day(h)
	out = []
	for k in range(n - 1, -1, -1):
		a = add_months(base, -k)
		b = add_days(add_months(a, 1), -1)
		out.append((a, b))
	return out


def _bloco(fn, *a):
	try:
		return fn(*a)
	except Exception:
		frappe.log_error(title=f"orbit.inicio.{fn.__name__}", message=frappe.get_traceback())
		return None


# ── Faturação ────────────────────────────────────────────────────────────────
def _portal_faturacao(periodo: str):
	# O Orbit da casa só tem o endereço do tempo (`…/api/v1/orbit/tempo`); a raiz do portal tira-se dele.
	base = (frappe.conf.get("orbit_portal_url") or (frappe.conf.get("orbit_portal_tempo_url") or "").split("/api/")[0]).rstrip("/")
	seg = frappe.conf.get("orbit_portal_segredo")
	if not base or not seg:
		return None
	chave = f"orbit:inicio:fat:{frappe.local.site}:{periodo}"
	guardado = frappe.cache().get_value(chave)
	if guardado:
		return guardado
	import requests
	corpo = json.dumps({"site": frappe.local.site, "periodo": periodo}).encode()
	r = requests.post(f"{base}/api/v1/orbit/resumo-negocio", data=corpo, timeout=8,
		headers={"Content-Type": "application/json",
			"X-Orbit-Assinatura": hmac.new(seg.encode(), corpo, hashlib.sha256).hexdigest()})
	if r.status_code >= 300:
		return None
	f = (r.json() or {}).get("faturacao")
	if f:
		for v in f.get("vencidas") or []:
			if v.get("crm_account_id"):
				v["cliente"] = frappe.db.get_value("CRM Organization", {"crm_account_id": v["crm_account_id"]}, "name") \
					if frappe.db.has_column("CRM Organization", "crm_account_id") else None
		frappe.cache().set_value(chave, f, expires_in_sec=600)
	return f


def _erp_faturacao(periodo: str):
	if not _existe("Sales Invoice") or not frappe.db.count("Sales Invoice", {"docstatus": 1}):
		return None
	i, f, ai, af = _intervalo(periodo)
	soma = lambda a, b: flt(frappe.db.sql("""select coalesce(sum(base_grand_total),0) from `tabSales Invoice`
		where docstatus=1 and posting_date between %s and %s""", (a, b))[0][0])
	aberto = frappe.db.sql("""select coalesce(sum(outstanding_amount),0), count(*) from `tabSales Invoice`
		where docstatus=1 and outstanding_amount > 0""")[0]
	venc = frappe.get_all("Sales Invoice", filters={"docstatus": 1, "outstanding_amount": [">", 0], "due_date": ["<", nowdate()]},
		fields=["name", "customer_name", "outstanding_amount", "due_date"], order_by="due_date asc", limit=20)
	h = getdate(nowdate())
	return {"periodo": periodo, "faturado": soma(i, f), "anterior": soma(ai, af),
		"meses": [{"mes": str(a)[:7], "valor": soma(a, b)} for a, b in _meses()],
		"por_receber": flt(aberto[0]), "por_receber_n": cint(aberto[1]),
		"vencido": sum(flt(v.outstanding_amount) for v in venc),
		"vencidas": [{"numero": v.name, "valor": flt(v.outstanding_amount), "vencimento": str(v.due_date),
			"dias": (h - getdate(v.due_date)).days, "cliente": v.customer_name} for v in venc],
		"fonte": "ERP"}


def _despesas():
	out = []
	tem_pi, tem_ec = _existe("Purchase Invoice"), _existe("Expense Claim")
	if not tem_pi and not tem_ec:
		return None
	total = 0.0
	for a, b in _meses():
		v = 0.0
		if tem_pi:
			v += flt(frappe.db.sql("""select coalesce(sum(base_grand_total),0) from `tabPurchase Invoice`
				where docstatus=1 and posting_date between %s and %s""", (a, b))[0][0])
		if tem_ec:
			v += flt(frappe.db.sql("""select coalesce(sum(total_sanctioned_amount),0) from `tabExpense Claim`
				where docstatus=1 and posting_date between %s and %s""", (a, b))[0][0])
		total += v
		out.append({"mes": str(a)[:7], "valor": v})
	return out if total else None


# ── CRM ──────────────────────────────────────────────────────────────────────
def _crm(periodo: str, dinheiro: bool):
	if not _existe("CRM Deal"):
		return None
	from orbit.interface.api import _rotulo_estado   # 26-11-2026: o nome à vista escolhido nas Definições
	estados = frappe.get_all("CRM Deal Status", fields=["name", "type", "position"], order_by="position asc")
	tipo = {e.name: e.type for e in estados}
	abertos_n = [e.name for e in estados if e.type in ("Open", "Ongoing")]
	ganhos_n = [e.name for e in estados if e.type == "Won"]
	perdidos_n = [e.name for e in estados if e.type == "Lost"]
	valor = "coalesce(nullif(deal_value,0), expected_deal_value, 0)"
	i, f, ai, af = _intervalo(periodo)

	def contar(nomes, a=None, b=None):
		if not nomes:
			return 0, 0.0
		cond, args = "status in %(s)s", {"s": tuple(nomes)}
		if a:
			cond += " and date(coalesce(closed_date, modified)) between %(a)s and %(b)s"
			args.update(a=a, b=b)
		r = frappe.db.sql(f"select count(*), coalesce(sum({valor}),0) from `tabCRM Deal` where {cond}", args)[0]
		return cint(r[0]), flt(r[1])

	ab_n, ab_v = contar(abertos_n)
	g_n, g_v = contar(ganhos_n, i, f)
	ga_n, _ = contar(ganhos_n, ai, af)
	ano = add_days(getdate(nowdate()), -365)
	g12, _ = contar(ganhos_n, ano, nowdate())
	p12, _ = contar(perdidos_n, ano, nowdate())
	funil = []
	try:   # 27-11-2026: vários funis — as etapas são as do funil por omissão (os números somam todos)
		from orbit.funis import fases as _fases_funil
		do_funil = {s.name for s in _fases_funil()}
	except Exception:  # noqa: BLE001
		do_funil = None
	for e in estados:
		if do_funil is not None and e.name not in do_funil:
			continue
		if e.type not in ("Open", "Ongoing"):
			continue
		n, v = contar([e.name])
		funil.append({"etapa": _rotulo_estado(e.name), "n": n, "valor": v if dinheiro else None})
	novos = [cint(frappe.db.count("CRM Deal", {"creation": ["between", [a, add_days(b, 1)]]})) for a, b in _meses(7)]
	parados = frappe.db.sql("""select name, organization, modified from `tabCRM Deal`
		where status in %(s)s and modified < %(d)s order by modified asc limit 5""",
		{"s": tuple(abertos_n) or ("",), "d": add_days(now_datetime(), -30)}, as_dict=True) if abertos_n else []
	return {"abertos": ab_n, "abertos_valor": ab_v if dinheiro else None,
		"ganhos": g_n, "ganhos_valor": g_v if dinheiro else None, "ganhos_anterior": ga_n,
		"taxa_ganho": round(100 * g12 / (g12 + p12)) if (g12 + p12) else None,
		"funil": funil, "serie": novos,
		"parados": [{"nome": p.name, "organizacao": p.organization or frappe._("Negócio {0}").format(p.name),
			"dias": (now_datetime() - p.modified).days} for p in parados],
		"_tipo": tipo}


# ── Desk ─────────────────────────────────────────────────────────────────────
def _desk():
	if not _existe("HD Ticket"):
		return None
	abertos = cint(frappe.db.count("HD Ticket", {"status": ["in", _ABERTOS_DESK]}))
	fora = frappe.db.sql("""select name, subject, customer, resolution_by from `tabHD Ticket`
		where status in %(s)s and resolution_by is not null and resolution_by < %(n)s
		order by resolution_by asc""", {"s": _ABERTOS_DESK, "n": now_datetime()}, as_dict=True)
	r = frappe.db.sql("""select avg(timestampdiff(minute, coalesce(opening_date, creation), first_responded_on))
		from `tabHD Ticket` where first_responded_on is not null and creation > %s""", (add_days(now_datetime(), -30),))[0][0]
	meus = cint(frappe.db.sql("""select count(*) from `tabHD Ticket` where status in %(s)s and _assign like %(u)s""",
		{"s": _ABERTOS_DESK, "u": f'%"{frappe.session.user}"%'})[0][0])
	serie = [cint(frappe.db.count("HD Ticket", {"creation": ["between", [a, add_days(b, 1)]]})) for a, b in _meses(7)]
	return {"abertos": abertos, "fora_prazo": len(fora), "meus": meus,
		"primeira_resposta_h": round(flt(r) / 60, 1) if r else None, "serie": serie,
		"fora_lista": [{"nome": t.name, "assunto": t.subject, "cliente": t.customer} for t in fora[:3]]}


# ── Stock ────────────────────────────────────────────────────────────────────
def _stock():
	if not _existe("Item Reorder") or not _existe("Bin"):
		return []
	return frappe.db.sql("""select b.item_code, i.item_name, b.warehouse, b.projected_qty, r.warehouse_reorder_level
		from `tabBin` b join `tabItem Reorder` r on r.parent = b.item_code and r.warehouse = b.warehouse
		join `tabItem` i on i.name = b.item_code
		where b.projected_qty < r.warehouse_reorder_level order by b.projected_qty asc limit 5""", as_dict=True)


# ── O meu dia ────────────────────────────────────────────────────────────────
def _meu_dia():
	u = frappe.session.user
	hoje = nowdate()
	out = {}
	# 23-11-2026: as tarefas são as da interface (CRM Task e tarefas de projeto, como em #/tarefas) — não os ToDo, que são
	# sobretudo avisos de atribuição automática («Assignment for CRM Lead…») e davam 194 «atrasadas» que não o eram.
	try:
		from orbit.interface.trabalho import tarefas as _tarefas
		lista = _tarefas("minhas")
	except Exception:
		lista = []
	out["atrasadas"] = sum(1 for t in lista if t["grupo"] == "atrasadas")
	out["hoje"] = sum(1 for t in lista if t["grupo"] == "hoje")
	out["abertas"] = len(lista)
	out["tarefas"] = [{"name": t["id"], "description": t["titulo"], "date": t["data"], "atrasada": t["grupo"] == "atrasadas",
	                   "reference_type": (t.get("ref") or [None, None])[0], "reference_name": (t.get("ref") or [None, None])[1]}
	                  for t in sorted(lista, key=lambda t: (t["data"] is None, t["data"] or ""))[:4]]
	if _existe("Timesheet"):
		seg = add_days(getdate(hoje), -getdate(hoje).weekday())
		emp = frappe.db.get_value("Employee", {"user_id": u}, "name") if _existe("Employee") else None
		cond = "(employee=%(e)s or owner=%(u)s)" if emp else "owner=%(u)s"
		out["horas"] = flt(frappe.db.sql(f"""select coalesce(sum(total_hours),0) from `tabTimesheet`
			where docstatus<2 and {cond} and start_date between %(a)s and %(b)s""",
			{"e": emp, "u": u, "a": seg, "b": add_days(seg, 6)})[0][0])
		out["horas_objetivo"] = 40
	return out


# ── Atividade ────────────────────────────────────────────────────────────────
def _atividade(dinheiro: bool, tipo_deal: dict):
	itens = []
	if _existe("CRM Deal"):
		ganhos = [k for k, v in (tipo_deal or {}).items() if v == "Won"]
		if ganhos:
			for d in frappe.get_all("CRM Deal", filters={"status": ["in", ganhos]},
					fields=["name", "organization", "deal_owner", "modified", "deal_value"], order_by="modified desc", limit=4):
				itens.append({"quando": str(d.modified), "app": "CRM", "selo": "Ganho",
					"texto": (f"{_nome(d.deal_owner)} ganhou «{d.organization}»" if d.deal_owner and d.organization
						else f"Negócio ganho — {d.organization or d.name}"),
					"valor": flt(d.deal_value) if dinheiro and d.deal_value else None, "ligacao": f"/crm/deals/{d.name}"})
		for l in frappe.get_all("CRM Lead", fields=["name", "lead_name", "organization", "creation"],
				order_by="creation desc", limit=3) if _existe("CRM Lead") else []:
			itens.append({"quando": str(l.creation), "app": "CRM", "selo": "Lead",
				"texto": f"Novo lead — {l.organization or l.lead_name or l.name}", "ligacao": f"/crm/leads/{l.name}"})
	if _existe("HD Ticket"):
		for t in frappe.get_all("HD Ticket", filters={"status": ["in", ["Resolved", "Closed"]]},
				fields=["name", "subject", "modified"], order_by="modified desc", limit=3):
			itens.append({"quando": str(t.modified), "app": "Desk", "selo": "Resolvido",
				"texto": f"#{t.name} {t.subject or ''}".strip(), "ligacao": f"/helpdesk/tickets/{t.name}"})
	if dinheiro and _existe("Sales Invoice"):
		for s in frappe.get_all("Sales Invoice", filters={"docstatus": 1}, fields=["name", "customer_name", "modified", "base_grand_total"],
				order_by="modified desc", limit=3):
			itens.append({"quando": str(s.modified), "app": "Gestão", "selo": None,
				"texto": f"Fatura {s.name} — {s.customer_name}", "valor": flt(s.base_grand_total), "ligacao": f"/app/sales-invoice/{s.name}"})
	itens.sort(key=lambda x: x["quando"], reverse=True)
	return itens[:6]


def _nome(u):
	if not u:
		return "A equipa"
	return (frappe.db.get_value("User", u, "first_name") or u.split("@")[0]).strip()


@frappe.whitelist()
def resumo(periodo: str = "mes"):
	if frappe.session.user == "Guest":
		frappe.throw("Sem sessão", frappe.PermissionError)
	periodo = periodo if periodo in _PERIODOS else "mes"
	dinheiro = _pode_dinheiro()
	crm = _bloco(_crm, periodo, dinheiro)
	tipo = (crm or {}).pop("_tipo", {}) if crm else {}
	fat = None
	if dinheiro:
		fat = _bloco(_portal_faturacao, periodo) or _bloco(_erp_faturacao, periodo)
	atencao = []
	if fat:
		for v in (fat.get("vencidas") or [])[:2]:
			atencao.append({"titulo": f"{v['numero']}" + (f" — {v['cliente']}" if v.get("cliente") else ""),
				"nota": f"{v['valor']:.2f} € · vencida há {v['dias']} dias", "selo": "Cobrar", "tom": "ambar"})
	if crm:
		for p in crm.get("parados", [])[:2]:
			atencao.append({"titulo": p["organizacao"], "nota": f"Negócio parado há {p['dias']} dias", "selo": "Parado",
				"tom": "ambar", "ligacao": f"/crm/deals/{p['nome']}"})
	for s in _bloco(_stock) or []:
		atencao.append({"titulo": s.item_name or s.item_code, "nota": f"{flt(s.projected_qty):g} previstos · mínimo {flt(s.warehouse_reorder_level):g}",
			"selo": "Comprar", "tom": "azul", "ligacao": f"/app/item/{s.item_code}"})
	desk = _bloco(_desk)
	if desk:
		for t in desk.get("fora_lista", [])[:2]:
			atencao.append({"titulo": f"#{t['nome']} {t['assunto'] or ''}".strip(), "nota": f"{t['cliente'] or ''} · fora do prazo".strip(" ·"),
				"selo": "Desk", "tom": "ambar", "ligacao": f"/helpdesk/tickets/{t['nome']}"})
	return {
		"periodo": periodo, "dinheiro": dinheiro,
		"faturacao": fat, "despesas": _bloco(_despesas) if dinheiro else None,
		"crm": crm, "desk": desk, "atencao": atencao[:6],
		"meu_dia": _bloco(_meu_dia) or {},
		"atividade": _bloco(_atividade, dinheiro, tipo) or [],
	}
