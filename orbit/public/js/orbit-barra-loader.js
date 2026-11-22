/* Carregador da barra de apps do Orbit para as apps que vivem noutro domínio (Chat, Docs, Meet, Booking, Sign).
 * 22-11-2026. A partir do endereço da app descobre o Orbit do tenant e carrega a barra dele (orbit.barra.barra_js):
 *   <app>.orbit.<domínio>               → orbit.<domínio>                (ex.: chat.orbit.shopinox.eu)
 *   <slug>.<app>.orbit.stratechna.com   → <slug>.orbit.stratechna.com    (ex.: vela.chat.orbit.stratechna.com)
 *   <app>.orbit.stratechna.com, docs/sign/booking.stratechna.com → orbit.stratechna.com
 * `data-app` no <script> diz que app é (fica marcada); `data-sitio` o canto do botão quando a app não tem sítio próprio.
 */
(function () {
  if (window.__orbitBarraLoader) { return; }
  window.__orbitBarraLoader = true;
  var eu = document.currentScript;
  var app = (eu && eu.getAttribute('data-app')) || '';
  var sitio = (eu && eu.getAttribute('data-sitio')) || 'baixo-esquerda';
  var h = location.hostname;
  var casa = 'orbit.stratechna.com', m;
  if ((m = h.match(/^([a-z0-9-]+)\.(chat|docs|meet|sign|booking|mail)\.orbit\.stratechna\.com$/))) { casa = m[1] + '.orbit.stratechna.com'; }
  else if ((m = h.match(/^(chat|docs|meet|sign|booking|mail)\.orbit\.(.+)$/))) { casa = 'orbit.' + m[2]; }
  var s = document.createElement('script');
  s.src = 'https://' + casa + '/api/method/orbit.barra.barra_js?app=' + encodeURIComponent(app) + '&sitio=' + encodeURIComponent(sitio);
  s.async = true;
  (document.head || document.documentElement).appendChild(s);
})();
