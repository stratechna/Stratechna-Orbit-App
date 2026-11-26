"""Contas das pessoas nas outras apps do Orbit, sem pedir palavras-passe (26-11-2026, pedido do Vítor).

Um cliente pode ter as caixas fora do Orbit Mail (ex.: no Zoho) e deve usar todas as apps do Orbit. O Chat (Zulip)
só aceitava a palavra-passe própria do Chat — que as pessoas criadas pelo bloco Pessoas nem têm — e por isso o /orbit
pedia-a sem resultado. Agora o vigia do Apps02 (/opt/orbit/scripts/orbit-contas-apps.py, de 5 em 5 min) lê a chave
de API de cada pessoa na organização do Chat do tenant e entrega-a aqui, cifrada no User (`orbit_chat_chave`, a mesma
que o «Ligar o Chat» gravava). A chave nunca sai do Apps02 nem passa por um ecrã.

Funções chamadas só pelo vigia, por `bench execute` (sem sessão, sem HTTP).
"""
from __future__ import annotations

import json
import os

import frappe

SERVICO = ("portal@", "suporte@", "it@", "noreply@", "admin@", "calendarios-sync@")


def pessoas():
    """As pessoas deste Orbit (utilizadores de sistema activos com email), para o vigia."""
    us = frappe.get_all("User", filters={"enabled": 1, "user_type": "System User"}, fields=["name", "full_name"])
    return [{"email": u.name.lower(), "nome": u.full_name or u.name}
            for u in us if "@" in u.name and not u.name.lower().startswith(SERVICO)]


def receber_chaves_chat(ficheiro: str):
    """Lê {email: chave} de um ficheiro temporário (apagado logo a seguir) e grava as chaves que mudaram.
    Só para pessoas activas deste Orbit. Devolve só contagens."""
    from frappe.utils.password import get_decrypted_password, set_encrypted_password
    try:
        dados = json.load(open(ficheiro))
    finally:
        try:
            os.remove(ficheiro)
        except OSError:
            pass
    validos = {p["email"] for p in pessoas()}
    gravadas = iguais = 0
    for email, chave in (dados or {}).items():
        email = (email or "").lower()
        if email not in validos or not chave or len(chave) > 64:
            continue
        nome = frappe.db.get_value("User", {"name": email}, "name") or frappe.db.get_value("User", {"email": email}, "name")
        if not nome:
            continue
        if get_decrypted_password("User", nome, "orbit_chat_chave", raise_exception=False) == chave:
            iguais += 1
            continue
        set_encrypted_password("User", nome, chave, "orbit_chat_chave")
        gravadas += 1
    frappe.db.commit()
    return {"gravadas": gravadas, "iguais": iguais}
