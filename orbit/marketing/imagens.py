"""As imagens das mensagens, recortadas à medida.

O motor dos modelos pede cada imagem com a largura e a altura do sítio onde
vai (`modelos._Tema.img`). Aqui faz-se o recorte — «cobrir», nunca esticar —
e guarda-se uma cópia pública do tenant, com nome pelo resumo do pedido: a
mesma imagem no mesmo tamanho é recortada uma vez, e as mensagens seguintes
apontam para a cópia. As fotografias da Pexels recortam-se no endereço.

Não é um intermediário aberto: só se chama do servidor, ao compor uma
mensagem, e recusa endereços de redes internas.
"""
import hashlib
import io
import ipaddress
import os
import socket
from urllib.parse import urlparse

import frappe
from frappe.utils import get_url

from orbit.marketing import modelos

MAXIMO = 12 * 1024 * 1024
_FALHAS: set = set()


def _pasta() -> str:
    p = frappe.get_site_path("public", "files", "mkt")
    os.makedirs(p, exist_ok=True)
    return p


def _publico_seguro(url: str) -> bool:
    try:
        host = urlparse(url).hostname or ""
        for info in socket.getaddrinfo(host, None):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                return False
        return bool(host)
    except Exception:  # noqa: BLE001
        return False


def _ler(url: str) -> bytes | None:
    proprio = get_url("/files/")
    if url.startswith(proprio):
        caminho = frappe.get_site_path("public", "files", url[len(proprio):].split("?")[0])
        if os.path.isfile(caminho):
            with open(caminho, "rb") as f:
                return f.read()
        return None
    if not _publico_seguro(url):
        return None
    import requests
    with requests.get(url, timeout=8, stream=True, headers={"User-Agent": "Orbit-Marketing/1.0"}) as r:
        if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
            return None
        dados = b""
        for parte in r.iter_content(65536):
            dados += parte
            if len(dados) > MAXIMO:
                return None
        return dados


def recortar(url: str, largura: int, altura: int | None = None) -> str:
    """O endereço público da imagem à medida. Se algo falhar, devolve o
    original — uma imagem por recortar nunca impede uma mensagem de sair."""
    if not url:
        return url
    if "images.pexels.com/" in url:
        return modelos._pexels(url, largura, altura)
    if url.lower().endswith(".svg"):
        return url
    chave = hashlib.sha1(f"{url}|{largura}|{altura}".encode()).hexdigest()[:32]
    nome = f"{chave}.jpg"
    destino = os.path.join(_pasta(), nome)
    publico = get_url(f"/files/mkt/{nome}")
    if os.path.isfile(destino):
        return publico
    if chave in _FALHAS:
        return url
    try:
        from PIL import Image, ImageOps
        dados = _ler(url)
        if not dados:
            raise ValueError("sem imagem")
        im = Image.open(io.BytesIO(dados))
        im = ImageOps.exif_transpose(im)
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            fundo = Image.new("RGB", im.size, (255, 255, 255))
            fundo.paste(im, mask=im.split()[-1])
            im = fundo
        else:
            im = im.convert("RGB")
        if altura:
            im = ImageOps.fit(im, (largura, altura), Image.LANCZOS, centering=(0.5, 0.45))
        elif im.width > largura:
            im = im.resize((largura, round(im.height * largura / im.width)), Image.LANCZOS)
        im.save(destino, "JPEG", quality=84, optimize=True, progressive=True)
        return publico
    except Exception:  # noqa: BLE001
        _FALHAS.add(chave)
        return url
