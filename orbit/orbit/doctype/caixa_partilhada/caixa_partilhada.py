"""Caixa partilhada — a caixa que aparece na janela de mais do que uma pessoa.

**A configuração vive aqui e o mecanismo vive no portal.**

Aqui decide-se *que* caixa é partilhada e *quem* a vê, porque é aqui que estão
os papéis e as permissões por utilizador — que o portal não tem. O portal
guarda a senha de partilha e sabe escrever no servidor de correio e no webmail,
que é trabalho que exige chaves que o Orbit não deve ter.

**Porque é que se pede a palavra-passe da caixa.**

As permissões dizem quem pode administrar; a palavra-passe diz de quem é a
caixa. Partilhar o `comercial@` é administração; partilhar a caixa pessoal de
alguém é outra coisa. Sem esta prova, quem tivesse o papel podia dar-se acesso
ao correio de qualquer colega.

Pede-se só quando se **dá** acesso — tirar acesso ou deixar de partilhar reduz
o alcance e não precisa de prova.
"""
import json

import frappe
import requests
from frappe import _
from frappe.model.document import Document


def _config():
    url = frappe.conf.get("caixas_portal_url")
    segredo = frappe.conf.get("caixas_portal_segredo")
    if not url or not segredo:
        frappe.throw(_("A ligação ao portal não está configurada neste site."))
    return url, segredo


def _pedir(caminho: str, corpo=None, metodo: str = "post"):
    url, segredo = _config()
    try:
        f = requests.post if metodo == "post" else requests.get
        r = f(f"{url}/{caminho}", json=corpo, headers={"X-Orbit-Segredo": segredo},
              timeout=120)
    except requests.RequestException as e:
        frappe.throw(_("Não consegui falar com o portal: {0}").format(str(e)[:200]))
    if r.status_code >= 300:
        detalhe = ""
        try:
            detalhe = (r.json() or {}).get("detail", "")
        except ValueError:
            detalhe = r.text[:200]
        frappe.throw(_("O portal recusou: {0}").format(detalhe or r.status_code))
    return r.json()


class CaixaPartilhada(Document):

    def validate(self):
        self.caixa = (self.caixa or "").strip().lower()
        if not self.rotulo:
            self.rotulo = self.caixa.split("@")[0]

        pessoas = []
        for p in (self.pessoas or []):
            e = (p.utilizador or "").strip().lower()
            if not e:
                continue
            if e in pessoas:
                frappe.throw(_("{0} está repetido.").format(e))
            pessoas.append(e)
            p.utilizador = e

        # Quem é novo nesta gravação. É só por estes que se pede a prova: uma
        # alteração que não dá acesso a ninguém não tem de a exigir.
        antes = set()
        if not self.is_new():
            antigo = self.get_doc_before_save()
            if antigo:
                antes = {(p.utilizador or "").strip().lower() for p in (antigo.pessoas or [])}
        novos = [e for e in pessoas if e not in antes]

        if novos or self.is_new():
            senha = self.get_password("senha_original", raise_exception=False) \
                if not self.is_new() else self.senha_original
            senha = senha or self.senha_original
            if not senha:
                frappe.throw(_("Escreva a palavra-passe de {0} para dar acesso a mais alguém.")
                             .format(self.caixa))
            if not _pedir("verificar", {"caixa": self.caixa, "senha": senha}).get("ok"):
                frappe.throw(_("A palavra-passe de {0} não está certa. "
                               "É a senha com que se entra nessa caixa — "
                               "não a de quem está a configurar.").format(self.caixa))

        # **Nunca fica guardada.** Foi verificada e o seu trabalho acabou.
        self.senha_original = None

    def on_update(self):
        aplicar_tudo()

    def on_trash(self):
        # A seguir ao apagar, a lista que o portal recebe já não a tem — e é
        # isso que a tira dos servidores. Daí correr depois do commit.
        frappe.enqueue(aplicar_tudo, enqueue_after_commit=True, queue="short")


def aplicar_tudo():
    """Entrega ao portal a lista inteira do que deve valer.

    Inteira e não em diferenças: o que estiver nos servidores passa a ser o que
    o Orbit mandou. Uma caixa que saiu daqui desaparece de lá sem ninguém se
    lembrar de a remover — e era assim que ficavam acessos esquecidos.
    """
    caixas = []
    for nome in frappe.get_all("Caixa Partilhada", filters={"activa": 1}, pluck="name"):
        d = frappe.get_doc("Caixa Partilhada", nome)
        caixas.append({
            "caixa": d.caixa,
            "rotulo": d.rotulo or "",
            "pessoas": [p.utilizador for p in (d.pessoas or []) if p.utilizador],
        })
    return _pedir("aplicar", {"caixas": caixas})


@frappe.whitelist()
def caixas_existentes(doctype=None, txt=None, searchfield=None, start=0,
                      page_len=20, filters=None):
    """As caixas que existem mesmo, para o campo as oferecer.

    **Não se criam caixas aqui.** Uma caixa partilhada é uma caixa normal,
    criada onde todas são criadas; isto é só o mapeamento por cima.
    """
    url, segredo = _config()
    try:
        r = requests.get(f"{url}/existentes", headers={"X-Orbit-Segredo": segredo}, timeout=60)
        r.raise_for_status()
        todas = r.json().get("caixas", [])
    except Exception:                                        # noqa: BLE001
        frappe.log_error(frappe.get_traceback(), "Caixas partilhadas: listar")
        return []
    t = (txt or "").lower()
    return [{"value": c} for c in todas if t in c.lower()][: int(page_len or 20)]
