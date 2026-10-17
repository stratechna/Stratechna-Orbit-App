// Entrada única (17-10-2026): um só ecrã de entrada — o do portal. Com `orbit_entrada_stratechna_auto` ligado
// no tenant, qualquer página de entrada do Orbit (/login ou a raiz, que mostra o mesmo formulário) segue logo
// para o portal; o formulário nem chega a ver-se. Quem já tem sessão no portal entra sem escrever nada.
// `?senha=1` mostra o formulário de sempre (recurso de emergência, durante a transição).
(function () {
  var q = new URLSearchParams(location.search);
  if (q.has("senha")) return;
  function botao() { return document.querySelector("a.btn-stratechna"); }
  function seguir() {
    var a = botao();
    if (!a) return false;
    // esconder já, para não piscar o formulário antes de seguir
    document.documentElement.style.visibility = "hidden";
    fetch("/api/method/orbit.entrada_unica.automatica", { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.message && d.message.auto && a.href) { location.replace(a.href); }
        else { document.documentElement.style.visibility = ""; }
      })
      .catch(function () { document.documentElement.style.visibility = ""; });
    return true;
  }
  if (!seguir()) { document.addEventListener("DOMContentLoaded", seguir); }
})();
