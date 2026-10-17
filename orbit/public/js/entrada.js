// Entrada única (17-10-2026): na página de entrada, com `orbit_entrada_stratechna_auto` ligado no tenant,
// segue-se logo para o portal — quem já lá tem sessão entra sem escrever nada. `?senha=1` mostra o
// formulário de sempre (a entrada por palavra-passe continua durante a transição).
(function () {
  if (location.pathname !== "/login") return;
  var q = new URLSearchParams(location.search);
  if (q.has("senha")) return;
  fetch("/api/method/orbit.entrada_unica.automatica", { credentials: "same-origin" })
    .then(function (r) { return r.json(); })
    .then(function (d) {
      if (!d.message || !d.message.auto) return;
      var a = document.querySelector("a.btn-stratechna");
      if (a && a.href) location.replace(a.href);
    })
    .catch(function () {});
})();
