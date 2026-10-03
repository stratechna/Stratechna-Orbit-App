"""O volume de envios do mês, contra o que o plano inclui.

Mede-se aqui porque é aqui que cada mensagem fica registada. Conta o que saiu
ou está na fila para sair (a fila é volume já reservado); não conta a
simulação, que não chega a ninguém nem custa nada.

O tecto vem do portal (`plano_envios_mes`, plano mais suplementos). Zero quer
dizer sem tecto — as contas da casa.
"""

import frappe
from frappe.utils import cint, get_first_day, nowdate

CONTAM = ("Na fila", "Enviado", "Devolvido", "Queixa")


def limite() -> int:
    from orbit.marketing.mensagem import definicoes
    return cint(definicoes().get("plano_envios_mes"))


def usado() -> int:
    return frappe.db.count("Envio de Marketing", {"estado": ("in", CONTAM),
                                                  "creation": (">=", get_first_day(nowdate()))})


def estado() -> dict:
    l, u = limite(), usado()
    return {"limite": l, "usado": u, "livre": (max(0, l - u) if l else None)}


def cabe(quantos: int) -> bool:
    l = limite()
    return not l or usado() + quantos <= l


def recusa(quantos: int) -> str:
    e = estado()
    return (f"O plano inclui {e['limite']} envios por mês; este mês já foram {e['usado']} e esta "
            f"campanha leva {quantos}. Pode pedir à Stratechna um suplemento de envios.")
