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
    // o contentor inteiro, e não só o botão: escondido só o botão, deixava um espaço vazio por baixo de «Continuar»
    if (a) { (a.closest(".social-logins") || a).style.display = "none"; return true; }
    return false;
  }
  if (!esconder()) { document.addEventListener("DOMContentLoaded", esconder); }
})();

// Vindo do portal com uma sessão de alguém que não tem conta neste Orbit (?sem_conta=1, 19-10-2026): uma nota
// por cima do formulário, para se perceber porque não entrou sozinho.
(function () {
  if (!new URLSearchParams(location.search).has("sem_conta")) return;
  var pt = (document.documentElement.lang || "pt").slice(0, 2);
  var txt = {
    pt: "A sua sessão Stratechna não tem conta neste Orbit. Entre com uma conta deste Orbit.",
    en: "Your Stratechna session has no account in this Orbit. Sign in with an account from this Orbit.",
    es: "Su sesión Stratechna no tiene cuenta en este Orbit. Entre con una cuenta de este Orbit.",
    fr: "Votre session Stratechna n’a pas de compte dans cet Orbit. Connectez-vous avec un compte de cet Orbit."
  }[pt] || "";
  function nota() {
    var f = document.querySelector("section.for-login form.form-login");
    if (!f) return false;
    var d = document.createElement("div");
    d.className = "orbit-sem-conta";
    d.textContent = txt;
    f.parentNode.insertBefore(d, f);
    return true;
  }
  if (!nota()) { document.addEventListener("DOMContentLoaded", nota); }
})();
