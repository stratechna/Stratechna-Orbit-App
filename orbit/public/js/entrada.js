// Entrada única (17-10-2026): um só ecrã de entrada — o do portal. Com `orbit_entrada_stratechna_auto` ligado
// no tenant, qualquer página de entrada do Orbit (/login ou a raiz, que mostra o mesmo formulário) segue logo
// para o portal; o formulário nem chega a ver-se. Quem já tem sessão no portal entra sem escrever nada.
// Sem porta alternativa por palavra-passe (decisão do Vítor, 17-10-2026: «não faz sentido, tira»).
(function () {
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
