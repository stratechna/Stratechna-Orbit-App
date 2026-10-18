// Entrada única (18-10-2026): dois ecrãs de entrada, a mesma memória — o do portal para o portal, o do Orbit para o
// Orbit e as apps dele (o Mail incluído). Na página de entrada do Orbit pergunta-se primeiro ao portal, sem se ver
// nada (prompt=none), se a pessoa já tem sessão: se tem, entra directo; se não, o portal devolve-a aqui com
// ?nativo=1 e mostra-se o formulário do Orbit. Quem entra pelo formulário fica também com sessão no portal
// (ponte: entrada_unica.ligar_portal). Só com `orbit_entrada_stratechna_auto` ligado no tenant.
(function () {
  var q = new URLSearchParams(location.search);
  if (q.has("nativo")) return;                       // já se perguntou: mostra o formulário do Orbit
  function botao() { return document.querySelector("a.btn-stratechna"); }
  function seguir() {
    var a = botao();
    if (!a) return false;
    // o botão «Entrar com Stratechna» não faz falta: a pergunta ao portal é automática
    a.style.display = "none";
    document.documentElement.style.visibility = "hidden";   // nada pisca enquanto se pergunta
    fetch("/api/method/orbit.entrada_unica.automatica", { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.message && d.message.auto && a.href) {
          location.replace(a.href + (a.href.indexOf("?") >= 0 ? "&" : "?") + "prompt=none");
        } else { document.documentElement.style.visibility = ""; a.style.display = ""; }
      })
      .catch(function () { document.documentElement.style.visibility = ""; a.style.display = ""; });
    return true;
  }
  if (!seguir()) { document.addEventListener("DOMContentLoaded", seguir); }
})();

// No formulário (?nativo=1) o botão «Entrar com Stratechna» também se esconde: a entrada é a do Orbit.
(function () {
  if (!new URLSearchParams(location.search).has("nativo")) return;
  function esconder() {
    var a = document.querySelector("a.btn-stratechna");
    if (a) { a.style.display = "none"; return true; }
    return false;
  }
  if (!esconder()) { document.addEventListener("DOMContentLoaded", esconder); }
})();
