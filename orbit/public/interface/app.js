// Stratechna Orbit — interface única (20-11-2026). Vue 3 sem compilação (vendor/vue.esm-browser.prod.js, MIT):
// não há passo de construção que uma actualização do Frappe possa partir. Fala só com orbit.interface.api.
import { createApp, reactive, ref, computed, watch, onMounted, onUnmounted, nextTick } from "./vendor/vue.esm-browser.prod.js";

// ── API ──────────────────────────────────────────────────────────────────────────────────────────────
async function api(metodo, args = {}, post = false) {
  // «erp.meta» → orbit.interface.erp.meta; sem ponto → orbit.interface.api.<metodo>
  const url = metodo.startsWith("orbit.") ? `/api/method/${metodo}` : metodo.includes(".") ? `/api/method/orbit.interface.${metodo}` : `/api/method/orbit.interface.api.${metodo}`;
  const op = { headers: { "X-Frappe-CSRF-Token": window.csrf_token, Accept: "application/json" } };
  let r;
  if (post) {
    op.method = "POST";
    op.headers["Content-Type"] = "application/json";
    op.body = JSON.stringify(args);
    r = await fetch(url, op);
  } else {
    r = await fetch(url + "?" + new URLSearchParams(Object.fromEntries(Object.entries(args).filter(([, v]) => v !== undefined && v !== null))), op);
  }
  // 25-11-2026: só a sessão perdida (401) volta à entrada. Um 403 é falta de permissão com a sessão válida — mandá-lo
  // para /login levava a pessoa para a casa dela (o CRM) sem explicação («algumas opções abrem o CRM»).
  if (r.status === 401) { location.href = "/login?redirect-to=" + encodeURIComponent(location.pathname + location.search + location.hash); return; }
  const j = await r.json().catch(() => ({}));
  if (!r.ok) {
    let msg = "Erro";
    try { msg = JSON.parse(JSON.parse(j._server_messages)[0]).message; } catch (e) { msg = j.exception || msg; }
    if (r.status === 403 && (msg === "Erro" || /PermissionError|Not permitted|Insufficient Permission/i.test(msg)))
      msg = "Sem permissão para isto. Peça a um administrador do Orbit da sua empresa.";
    toast(String(msg).replace(/<[^>]+>/g, ""));
    throw new Error(msg);
  }
  return j.message;
}

// Nomes das listas de configuração do ERP/RH/Desk em PT-PT (24-11-2026, orbit/configuracao_pt.py): os nomes
// internos ficam em inglês (o código das apps usa-os) e aqui mostra-se a tradução.
const TR = reactive({});
api("erp.traducoes").then((m) => Object.assign(TR, m || {})).catch(() => {});
const tr = (dt, v) => (v && dt && TR[dt] && TR[dt][v]) || v;

// Nomes dos países em PT-PT (o Frappe guarda-os em inglês)
const PAISES_PT = { Portugal: "Portugal", Spain: "Espanha", France: "França", Italy: "Itália", Germany: "Alemanha", Belgium: "Bélgica",
  Netherlands: "Países Baixos", Luxembourg: "Luxemburgo", "United Kingdom": "Reino Unido", Switzerland: "Suíça", Brazil: "Brasil",
  Angola: "Angola", Mozambique: "Moçambique", "Cape Verde": "Cabo Verde" };
// ── Utilitários ──────────────────────────────────────────────────────────────────────────────────────
const estado = reactive({ toast: "", erroEcra: "" });
let _t;
function toast(m) { estado.toast = m; clearTimeout(_t); _t = setTimeout(() => (estado.toast = ""), 3500); }
const CORES = ["#8a5a44", "#4b7a5a", "#5b6f7a", "#7a4b6e", "#46607e", "#8a7340", "#4f6b6b", "#7a5048"];
function cor(s) { let h = 0; for (const c of String(s || "")) h = (h * 31 + c.charCodeAt(0)) >>> 0; return CORES[h % CORES.length]; }
// 23-11-2026: um endereço «info@dominio» a partir do site, para a fotografia/logótipo de uma empresa sem email
function emailDoSite(site) {
  const d = String(site || "").trim().toLowerCase().split("//").pop().split("/")[0].replace(/^www\./, "");
  return d && d.includes(".") ? "info@" + d : "";
}
function ini(n) { const p = String(n || "?").trim().split(/\s+/); return ((p[0] || "?")[0] + (p.length > 1 ? p[p.length - 1][0] : "")).toUpperCase(); }
const eur = (v) => new Intl.NumberFormat("pt-PT", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(v || 0);
function data(d, comHora = true) {
  if (!d) return "";
  const x = new Date(String(d).replace(" ", "T"));
  if (isNaN(x)) return d;
  const hoje = new Date(); const ontem = new Date(); ontem.setDate(hoje.getDate() - 1);
  const h = x.toLocaleTimeString("pt-PT", { hour: "2-digit", minute: "2-digit" });
  if (x.toDateString() === hoje.toDateString()) return comHora ? `hoje, ${h}` : "hoje";
  if (x.toDateString() === ontem.toDateString()) return comHora ? `ontem, ${h}` : "ontem";
  const dd = x.toLocaleDateString("pt-PT", { day: "2-digit", month: "2-digit", year: x.getFullYear() === hoje.getFullYear() ? undefined : "numeric" });
  return comHora ? `${dd}, ${h}` : dd;
}
function mes(d) { const x = new Date(String(d).replace(" ", "T")); return isNaN(x) ? "" : x.toLocaleDateString("pt-PT", { month: "long", year: "numeric" }); }
const ESTADO_COR = { gray: "", orange: "ambar", blue: "azul", yellow: "ambar", purple: "roxo", green: "verde", red: "" };
const FAIXA = { gray: "#94a3b8", orange: "#f59e0b", blue: "#60a5fa", yellow: "#facc15", purple: "#a78bfa", green: "#22c55e", red: "#ef4444", black: "#475569",
  cyan: "#22d3ee", teal: "#2dd4bf", amber: "#fbbf24", pink: "#f472b6", violet: "#8b5cf6" };
const ROTAS_DT = { contacto: "Contact", negocio: "CRM Deal", empresa: "CRM Organization", lead: "CRM Lead" };
const DT_ROTA = Object.fromEntries(Object.entries(ROTAS_DT).map(([k, v]) => [v, k])); DT_ROTA["HD Ticket"] = "ticket";
// 25-11-2026 (lote 4): o que não é do CRM/Desk abre na ficha do ERP (antes caía na ficha de contacto)
const link = (dt, dn) => DT_ROTA[dt] ? `#/${DT_ROTA[dt]}/${encodeURIComponent(dn)}` : `#/erp/${encodeURIComponent(dt)}/${encodeURIComponent(dn)}`;

const ICONES = {
  menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
  template: '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M8 9h8M8 13h5"/>',
  megafone: '<path d="M3 10v4h4l6 4V6L7 10z"/><path d="M17 9a4 4 0 0 1 0 6"/>',
  apps: '<rect x="4" y="4" width="6" height="6" rx="1.5"/><rect x="14" y="4" width="6" height="6" rx="1.5"/><rect x="4" y="14" width="6" height="6" rx="1.5"/><rect x="14" y="14" width="6" height="6" rx="1.5"/>',
  euro: '<path d="M17 6a7 7 0 1 0 0 12"/><path d="M4 10h9M4 14h9"/>',
  cubo: '<path d="M21 8 12 3 3 8v8l9 5 9-5z"/><path d="m3 8 9 5 9-5M12 13v8"/>',
  pessoas: '<circle cx="9" cy="8" r="3.5"/><path d="M2 20a7 7 0 0 1 14 0"/><circle cx="17" cy="9" r="2.5"/><path d="M17 14a5 5 0 0 1 5 5"/>',
  relogio: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  projeto: '<rect x="3" y="4" width="5" height="16" rx="1"/><rect x="10" y="4" width="5" height="10" rx="1"/><rect x="17" y="4" width="4" height="13" rx="1"/>',
  assin: '<path d="M3 17c3 0 4-8 7-8s1 8 4 8 3-4 7-4"/><path d="M3 21h18"/>',
  casa: '<path d="M3 11l9-7 9 7"/><path d="M5 10v10h14V10"/>', pessoa: '<circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6"/>',
  empresa: '<rect x="4" y="3" width="16" height="18" rx="1"/><path d="M9 7h2M13 7h2M9 11h2M13 11h2M10 21v-4h4v4"/>',
  negocio: '<path d="M3 7h18v12H3z"/><path d="M8 7V5h8v2"/><path d="M3 12h18"/>', lead: '<path d="M12 3l2.5 5.5L20 9l-4 4 1 6-5-3-5 3 1-6-4-4 5.5-.5z"/>',
  caixa: '<path d="M3 13l3-8h12l3 8v6H3z"/><path d="M3 13h5l1 3h6l1-3h5"/>', ticket: '<path d="M3 8a2 2 0 002-2h14a2 2 0 002 2v2a2 2 0 000 4v2a2 2 0 00-2 2H5a2 2 0 00-2-2v-2a2 2 0 000-4z"/>',
  tarefa: '<rect x="4" y="4" width="16" height="16" rx="3"/><path d="M8 12l3 3 5-6"/>', cal: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
  mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/>', video: '<rect x="3" y="6" width="13" height="12" rx="2"/><path d="M16 10l5-3v10l-5-3"/>',
  chat: '<path d="M4 5h16v11H9l-5 4z"/>', livro: '<path d="M4 4h7a3 3 0 013 3v13a2 2 0 00-2-2H4z"/><path d="M20 4h-4a2 2 0 00-2 2"/>',
  grelha: '<rect x="4" y="4" width="6" height="6"/><rect x="14" y="4" width="6" height="6"/><rect x="4" y="14" width="6" height="6"/><rect x="14" y="14" width="6" height="6"/>',
  lupa: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>', lua: '<path d="M20 14A8 8 0 1110 4a6 6 0 0010 10z"/>',
  tel: '<path d="M5 4h4l2 5-3 2a11 11 0 005 5l2-3 5 2v4a2 2 0 01-2 2A17 17 0 013 6a2 2 0 012-2"/>', nota: '<path d="M4 4h16v12l-4 4H4z"/><path d="M16 20v-4h4M8 9h8M8 13h5"/>',
  roda: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 11-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 110-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 114 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 112.83 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9c.26.6.85 1 1.51 1H21a2 2 0 110 4h-.09a1.65 1.65 0 00-1.51 1z"/>',
  sino: '<path d="M6 16V11a6 6 0 0112 0v5l2 2H4z"/><path d="M10 20a2 2 0 004 0"/>',
  sair: '<path d="M14 4h5v16h-5"/><path d="M10 8l-4 4 4 4M6 12h10"/>', antigo: '<path d="M4 12a8 8 0 108-8"/><path d="M4 4v5h5"/>',
};
const Icone = { props: ["n"], template: `<svg viewBox="0 0 24 24" v-html="html"></svg>`, computed: { html() { return ICONES[this.n] || ""; } } };
const IC_EVENTO = { email: ["mail", "var(--cinza-bg)", "var(--ink-2)"], nota: ["nota", "var(--ambar-bg)", "var(--ambar)"], tarefa: ["tarefa", "var(--ambar-bg)", "var(--ambar)"],
  chamada: ["tel", "var(--verde-bg)", "var(--verde)"], reuniao: ["cal", "var(--azul-bg)", "var(--azul)"], ticket: ["ticket", "var(--cinza-bg)", "var(--ink-2)"],
  comentario: ["chat", "var(--roxo-bg)", "var(--roxo)"] };


// ── Corpo de um email: numa moldura própria (sem scripts), com o histórico citado recolhido ─────────────
const CITACOES = ".gmail_quote, blockquote[type=cite], #divRplyFwdMsg, #appendonsend, .yahoo_quoted, .moz-cite-prefix, div[id^=mail-editor-reference-message], .protonmail_quote, #reply-intro, .OutlookMessageHeader";
function separarCitacao(html) {
  try {
    const doc = new DOMParser().parseFromString(html || "", "text/html");
    const alvo = doc.body.querySelector(CITACOES);
    if (!alvo) return [doc.body.innerHTML, ""];
    let el = alvo; const fora = [];
    // o que vem a seguir ao início da citação, no mesmo nível, também é citação (Outlook: <hr> + cabeçalho + texto)
    const prev = el.previousElementSibling;
    if (prev && prev.tagName === "HR") fora.push(prev);
    while (el) { fora.push(el); el = el.nextElementSibling; }
    const tmp = doc.createElement("div"); fora.forEach((n) => tmp.appendChild(n));
    return [doc.body.innerHTML, tmp.innerHTML];
  } catch (e) { return [html, ""]; }
}
const EST_EMAIL = `<style>html,body{margin:0;padding:0;background:#fff}body{font:14px/1.55 "DM Sans",system-ui,-apple-system,sans-serif;color:#1c2a31;overflow-wrap:anywhere;word-break:break-word}
img{max-width:100%;height:auto}table{max-width:100%}p{margin:0 0 .8em}a{color:#2b3b44}blockquote{margin:0 0 0 .6em;padding-left:.8em;border-left:3px solid #e1e6e9;color:#4a5a63}pre{white-space:pre-wrap}</style><base target="_blank">`;
const EmailCorpo = {
  props: ["html"],
  setup(props) {
    const partes = computed(() => separarCitacao(props.html));
    const verAnterior = ref(false);
    const fonte = computed(() => EST_EMAIL + partes.value[0] + (verAnterior.value ? '<div style="margin-top:12px">' + partes.value[1] + "</div>" : ""));
    const quadro = ref(null);
    const medir = () => { try { const d = quadro.value.contentDocument; quadro.value.style.height = Math.min(Math.max(d.documentElement.scrollHeight, 40), 4000) + "px"; } catch (e) {} };
    return { partes, verAnterior, fonte, quadro, medir };
  },
  template: `<div class="email-corpo"><iframe ref="quadro" class="email-quadro" sandbox="allow-same-origin allow-popups allow-popups-to-escape-sandbox" :srcdoc="fonte" @load="medir" title="Mensagem"></iframe>
    <button v-if="partes[1]" class="citacao-btn" @click="verAnterior=!verAnterior">{{ verAnterior ? 'Esconder a mensagem anterior' : '··· Mostrar a mensagem anterior' }}</button></div>`,
};

// ── Calendário (A1): a agenda da pessoa no Orbit Mail (SOGo) + reuniões do Orbit, por semana ────────────
async function apiCal(metodo, args = {}, post = false) {
  const url = `/api/method/orbit.interface.calendario.${metodo}`;
  const op = { headers: { "X-Frappe-CSRF-Token": window.csrf_token, Accept: "application/json" } };
  let r;
  if (post) { op.method = "POST"; op.headers["Content-Type"] = "application/json"; op.body = JSON.stringify(args); r = await fetch(url, op); }
  else r = await fetch(url + "?" + new URLSearchParams(args), op);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) { let m = "Erro"; try { m = JSON.parse(JSON.parse(j._server_messages)[0]).message; } catch (e) {} toast(String(m).replace(/<[^>]+>/g, "")); throw new Error(m); }
  return j.message;
}
const pad = (n) => String(n).padStart(2, "0");
const isoDia = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const segunda = (d) => { const x = new Date(d); x.setHours(0, 0, 0, 0); const w = (x.getDay() + 6) % 7; x.setDate(x.getDate() - w); return x; };
const HORA0 = 7, HORA1 = 21, ALT = 48;
const Calendario = {
  components: { Icone },
  props: ["nova", "refDt", "refDn"],
  setup(props) {
    const semana = ref(segunda(new Date())); const d = ref(null); const pwd = ref(""); const sel = ref(null);
    const form = ref(null); const aGravar = ref(false); const estreito = ref(window.innerWidth < 900); const diaMovel = ref(new Date());
    window.addEventListener("resize", () => (estreito.value = window.innerWidth < 900));
    const dias = computed(() => {
      if (estreito.value) { const x = new Date(diaMovel.value); x.setHours(0, 0, 0, 0); return [x]; }
      return [...Array(7)].map((_, i) => { const x = new Date(semana.value); x.setDate(x.getDate() + i); return x; });
    });
    const minutos = (iso) => { const t = iso.slice(11, 16).split(":"); return +t[0] * 60 + +t[1]; };
    const equipa = ref([]); let sel0 = null; try { const g = localStorage.getItem("orbit.cal.equipa"); if (g) sel0 = JSON.parse(g); } catch (e) {}
    // 23-11-2026: sem escolha guardada, vêem-se todos os colegas (antes não se via ninguém até tocar nos nomes)
    const semEscolha = !sel0 || !sel0.length; if (semEscolha) sel0 = [];
    const verEquipa = ref(sel0); const ocupado = ref({}); const modos = ref({}); const partilha = ref("livre");
    // 23-11-2026: como a equipa vê a MINHA agenda (sem partilha · livre/ocupado · tudo) — o vigia do servidor aplica-o no Orbit Mail.
    const mudarPartilha = async () => { const r = await apiCal("definir_partilha", { modo: partilha.value }, true); toast(r.aviso || "Guardado"); };
    const carregarEquipa = async () => {
      try { localStorage.setItem("orbit.cal.equipa", JSON.stringify(verEquipa.value)); } catch (e) {}
      if (!verEquipa.value.length || !d.value?.ligado) { ocupado.value = {}; return; }
      const ini = dias.value[0]; const fim = new Date(dias.value[dias.value.length - 1]); fim.setDate(fim.getDate() + 1);
      const r = await apiCal("disponibilidade", { pessoas: verEquipa.value.join(","), inicio: isoDia(ini) + " 00:00:00", fim: isoDia(fim) + " 00:00:00" });
      ocupado.value = r.ocupado || {}; modos.value = r.modos || {};
    };
    watch(verEquipa, carregarEquipa, { deep: true });
    const carregar = async () => {
      const ini = dias.value[0]; const fim = new Date(dias.value[dias.value.length - 1]); fim.setDate(fim.getDate() + 1);
      d.value = await apiCal("eventos", { inicio: isoDia(ini) + " 00:00:00", fim: isoDia(fim) + " 00:00:00" });
      carregarEquipa();
    };
    const corDe = (e) => (equipa.value.find((x) => x.email === e) || {}).cor || "#64748b";
    const nomeDe = (e) => (equipa.value.find((x) => x.email === e) || {}).nome || e;
    const ocupadoDia = (dia) => {
      const out = []; const n = verEquipa.value.length || 1;
      verEquipa.value.forEach((em, k) => (ocupado.value[em] || []).forEach((b) => {
        if (b.inicio.slice(0, 10) !== isoDia(dia)) return;
        const a = minutos(b.inicio), z = Math.max(minutos(b.fim.slice(0, 10) > b.inicio.slice(0, 10) ? b.inicio.slice(0, 11) + "23:59" : b.fim), a + 15);
        out.push({ k: em + b.inicio, cor: corDe(em), nome: nomeDe(em), titulo: b.titulo || "", hora: b.inicio.slice(11, 16) + "–" + b.fim.slice(11, 16), top: Math.max((a - HORA0 * 60) / 60 * ALT, 0), alt: Math.max((z - a) / 60 * ALT - 2, 10), esq: (k / n) * 100, larg: 100 / n });
      }));
      return out;
    };
    watch([semana, diaMovel, estreito], carregar);
    onMounted(async () => { await carregar(); equipa.value = await apiCal("equipa"); if (semEscolha && !verEquipa.value.length) verEquipa.value = equipa.value.map((p) => p.email); try { partilha.value = (await apiCal("minha_partilha")).modo || "livre"; } catch (e) {} if (props.nova) abrirNova(); });
    const mover = (n) => { if (estreito.value) { const x = new Date(diaMovel.value); x.setDate(x.getDate() + n); diaMovel.value = x; } else { const x = new Date(semana.value); x.setDate(x.getDate() + 7 * n); semana.value = x; } };
    const hoje = () => { semana.value = segunda(new Date()); diaMovel.value = new Date(); };
    const titulo = computed(() => {
      const a = dias.value[0], b = dias.value[dias.value.length - 1];
      const f = (x, ano) => x.toLocaleDateString("pt-PT", { day: "numeric", month: "short", year: ano ? "numeric" : undefined });
      return dias.value.length === 1 ? a.toLocaleDateString("pt-PT", { weekday: "long", day: "numeric", month: "long" }) : `${f(a)} – ${f(b, true)}`;
    });
    const doDia = (dia) => (d.value?.eventos || []).filter((e) => !e.dia_todo && e.inicio.slice(0, 10) === isoDia(dia));
    const diaTodo = (dia) => (d.value?.eventos || []).filter((e) => e.dia_todo ? (e.inicio <= isoDia(dia) && e.fim > isoDia(dia)) : (e.inicio.slice(0, 10) < isoDia(dia) && e.fim.slice(0, 10) > isoDia(dia)));

    const disposicao = (dia) => {
      const evs = doDia(dia).map((e) => ({ e, a: minutos(e.inicio), b: Math.max(minutos(e.fim.slice(0, 10) > e.inicio.slice(0, 10) ? e.inicio.slice(0, 11) + "23:59" : e.fim), minutos(e.inicio) + 20) }))
        .sort((x, y) => x.a - y.a || y.b - x.b);
      const cols = []; evs.forEach((x) => { let c = 0; while (cols[c] && cols[c] > x.a) c++; cols[c] = x.b; x.col = c; });
      evs.forEach((x) => { x.n = evs.filter((y) => y.a < x.b && y.b > x.a).reduce((m, y) => Math.max(m, y.col + 1), 1); });
      return evs.map((x) => ({ ...x.e, top: Math.max((x.a - HORA0 * 60) / 60 * ALT, 0), alt: Math.max((x.b - x.a) / 60 * ALT - 2, 18), esq: (x.col / x.n) * 100, larg: 100 / x.n }));
    };
    const agoraTop = computed(() => { const n = new Date(); return ((n.getHours() * 60 + n.getMinutes()) - HORA0 * 60) / 60 * ALT; });
    const ehHoje = (dia) => isoDia(dia) === isoDia(new Date());
    const ligar = async () => { await apiCal(d.value?.fora ? "ligar_fora" : "ligar", { pwd: pwd.value }, true); pwd.value = ""; toast("Calendário ligado"); carregar(); };
    const hm = (iso) => iso.length > 10 ? iso.slice(11, 16) : "";
    const abrirNova = (dia = null, hora = null) => {
      const base = dia ? new Date(dia) : new Date(); const h = hora ?? Math.min(Math.max(new Date().getHours() + 1, 9), 18);
      form.value = { titulo: "", dia: isoDia(base), ini: `${pad(h)}:00`, fim: `${pad(h + 1)}:00`, convidados: props.refDn ? (window.__ref_email || "") : "", meet: true,
        calendario: (d.value?.calendarios || []).find((c) => c.pessoal)?.href || "", descricao: "", local: "", colegas: [...verEquipa.value] };
    };
    const procurar = ref(false);
    const primeiroLivre = async () => {
      const f = form.value; const [h1, m1] = f.ini.split(":").map(Number); const [h2, m2] = f.fim.split(":").map(Number);
      const dur = Math.max((h2 * 60 + m2) - (h1 * 60 + m1), 15); procurar.value = true;
      try {
        const r = await apiCal("primeiro_livre", { pessoas: f.colegas.join(","), duracao: dur, desde: `${f.dia} ${new Date().toISOString().slice(0, 10) === f.dia ? new Date().toTimeString().slice(0, 5) : "00:00"}:00` });
        if (!r.inicio) { toast("Sem horário livre comum nos próximos 10 dias"); return; }
        f.dia = r.inicio.slice(0, 10); f.ini = r.inicio.slice(11, 16); f.fim = r.fim.slice(11, 16); toast("Horário livre para todos encontrado");
      } finally { procurar.value = false; }
    };
    const gravar = async () => {
      const f = form.value; if (!f.titulo.trim()) { toast("Falta o título"); return; }
      aGravar.value = true;
      try {
        const r = await apiCal("criar", { titulo: f.titulo, inicio: `${f.dia} ${f.ini}:00`, fim: `${f.dia} ${f.fim}:00`, calendario: f.calendario,
          convidados: [f.convidados, ...f.colegas].filter(Boolean).join(", "), meet: f.meet ? 1 : 0, descricao: f.descricao, local: f.local, ref_doctype: props.refDt || null, ref_name: props.refDn || null }, true);
        toast(f.convidados.trim() ? "Reunião marcada — o convite segue pelo Orbit Mail" : "Reunião marcada");
        form.value = null; if (props.nova) location.hash = "#/calendario"; carregar();
      } finally { aGravar.value = false; }
    };
    const apagar = async (e) => { if (!confirm("Apagar esta reunião? Os convidados são avisados.")) return; await apiCal("apagar", { href: e.href }, true); sel.value = null; toast("Reunião apagada"); carregar(); };
    const horas = [...Array(HORA1 - HORA0)].map((_, i) => HORA0 + i);
    return { equipa, verEquipa, ocupadoDia, modos, partilha, mudarPartilha, procurar, primeiroLivre, semana, d, pwd, sel, form, aGravar, dias, mover, hoje, titulo, disposicao, diaTodo, agoraTop, ehHoje, ligar, hm, abrirNova, gravar, apagar, horas, ALT, link, data, estreito };
  },
  template: `
  <div class="cal">
    <div class="cal-topo">
      <h1>Calendário</h1>
      <div class="cal-nav"><button class="btn sm" @click="mover(-1)">‹</button><button class="btn sm" @click="hoje">Hoje</button><button class="btn sm" @click="mover(1)">›</button><b>{{ titulo }}</b></div>
      <button class="btn prim" @click="abrirNova()" :disabled="d && !d.ligado">+ Nova reunião</button>
    </div>
    <div class="equipa-cal" v-if="d && d.ligado && !d.fora && equipa.length"><span class="sub">Ver também:</span>
      <label v-for="p in equipa" :key="p.email" class="chip-eq" :style="{borderColor:p.cor, background: verEquipa.includes(p.email) ? p.cor : 'transparent', color: verEquipa.includes(p.email) ? '#fff' : 'var(--ink)'}">
        <input type="checkbox" :value="p.email" v-model="verEquipa" style="display:none">{{ p.nome }}</label>
      <span class="sub" style="font-size:12px" v-for="em in verEquipa.filter(x => modos[x] === 'nenhum')" :key="'n'+em">{{ (equipa.find(p => p.email === em) || {}).nome || em }} não partilha a agenda</span>
      <label class="sub partilha-cal" title="Como os colegas vêem a sua agenda aqui e no Orbit Mail">A minha agenda para a equipa:
        <select v-model="partilha" @change="mudarPartilha"><option value="nenhum">Sem partilha</option><option value="livre">Livre/ocupado</option><option value="tudo">Tudo (com as marcações)</option></select></label></div>
    <div v-if="d && !d.ligado && d.fora" class="cartao aviso-cal">
      <template v-if="d.fora.liga">
        <b>Ligar o calendário do {{ d.fora.nome }}</b>
        <p class="sub">A sua caixa ({{ d.utilizador }}) está no {{ d.fora.nome }}, por isso o calendário lê-se lá. Crie uma <b>palavra-passe de aplicação</b> em {{ d.fora.onde }} e escreva-a aqui — a palavra-passe de entrada no {{ d.fora.nome }} não serve. Fica guardada cifrada no seu Orbit e só serve o seu calendário.</p>
        <form @submit.prevent="ligar" style="display:flex;gap:8px;flex-wrap:wrap"><input type="password" v-model="pwd" autocomplete="off" :placeholder="'Palavra-passe de aplicação do ' + d.fora.nome" class="filtro" style="border-style:solid;min-width:240px"><button class="btn prim" :disabled="!pwd">Ligar</button></form>
      </template>
      <template v-else>
        <b>Calendário do {{ d.fora.nome }}</b>
        <p class="sub">A sua caixa ({{ d.utilizador }}) está no {{ d.fora.nome }}, que não se liga com uma palavra-passe. Peça à Stratechna para ligar o seu calendário.</p>
      </template>
      <p class="sub" style="font-size:12px;margin-bottom:0">Entretanto vê aqui as reuniões do Orbit (CRM e Booking).</p>
    </div>
    <div v-if="d && !d.ligado && !d.fora" class="cartao aviso-cal">
      <b>Ligar o calendário do Orbit Mail</b>
      <p class="sub">Para ver e marcar reuniões na sua agenda, confirme uma vez a palavra-passe da sua caixa de correio ({{ d.utilizador }}). Fica guardada cifrada no seu Orbit e só serve o seu calendário. Quem entra no Orbit com a palavra-passe da caixa fica ligado sozinho.</p>
      <form @submit.prevent="ligar" style="display:flex;gap:8px;flex-wrap:wrap"><input type="password" v-model="pwd" autocomplete="current-password" placeholder="Palavra-passe da caixa" class="filtro" style="border-style:solid;min-width:240px"><button class="btn prim" :disabled="!pwd">Ligar</button></form>
      <p class="sub" style="font-size:12px;margin-bottom:0">Entretanto vê aqui as reuniões do Orbit (CRM e Booking).</p>
    </div>
    <div v-if="!d" class="carregar">A carregar…</div>
    <div v-else class="cal-grelha" :style="{gridTemplateColumns:'52px repeat('+dias.length+',1fr)'}">
      <div class="cal-canto"></div>
      <div v-for="dia in dias" :key="dia" class="cal-cab" :class="{hoje:ehHoje(dia)}">{{ dia.toLocaleDateString('pt-PT',{weekday:'short'}) }} <b>{{ dia.getDate() }}</b></div>
      <div class="cal-canto sub" style="font-size:11px">dia todo</div>
      <div v-for="dia in dias" :key="'t'+dia" class="cal-todo"><div v-for="e in diaTodo(dia)" :key="e.id" class="cal-ev todo" :style="{background:e.cor}" @click="sel=e">{{ e.titulo }}</div></div>
      <div class="cal-horas"><div v-for="h in horas" :key="h" :style="{height:ALT+'px'}">{{ h }}:00</div></div>
      <div v-for="dia in dias" :key="'c'+dia" class="cal-col" :style="{height:(horas.length*ALT)+'px'}" @dblclick="(ev)=>abrirNova(dia, Math.floor(ev.offsetY/ALT)+7)">
        <div v-for="h in horas" :key="h" class="cal-linha" :style="{top:((h-7)*ALT)+'px'}"></div>
        <div v-if="ehHoje(dia) && agoraTop>0" class="cal-agora" :style="{top:agoraTop+'px'}"></div>
        <div v-for="o in ocupadoDia(dia)" :key="o.k" class="cal-ocupado" :title="o.nome + ' · ' + o.hora + (o.titulo ? ' — ' + o.titulo : ' — ocupado')" :style="{top:o.top+'px',height:o.alt+'px',left:'calc('+o.esq+'% + 1px)',width:'calc('+o.larg+'% - 2px)',background:o.cor}"><span>{{ o.nome.split(' ')[0] }}<template v-if="o.titulo"> · {{ o.titulo }}</template></span></div>
        <div v-for="e in disposicao(dia)" :key="e.id" class="cal-ev" :style="{top:e.top+'px',height:e.alt+'px',left:'calc('+e.esq+'% + 2px)',width:'calc('+e.larg+'% - 4px)',borderLeftColor:e.cor}" @click="sel=e">
          <b>{{ e.titulo }}</b><span>{{ hm(e.inicio) }}–{{ hm(e.fim) }}<template v-if="e.local"> · {{ e.local }}</template></span>
        </div>
      </div>
    </div>
    <div class="modal-fundo" v-if="sel" @click.self="sel=null">
      <div class="modal" style="max-width:520px"><header><div><b>{{ sel.titulo }}</b><div class="sub">{{ sel.dia_todo ? data(sel.inicio,false) : data(sel.inicio) + ' – ' + hm(sel.fim) }} · {{ sel.calendario }}</div></div><button class="btn sm" @click="sel=null">Fechar</button></header>
        <div class="corpo-email">
          <p v-if="sel.local"><b>Local:</b> <a v-if="sel.local.startsWith('http')" :href="sel.local" target="_blank">{{ sel.local }}</a><span v-else>{{ sel.local }}</span></p>
          <p v-if="sel.convidados && sel.convidados.length"><b>Convidados:</b> {{ sel.convidados.join(', ') }}</p>
          <p v-if="sel.descricao" style="white-space:pre-wrap">{{ sel.descricao }}</p>
          <p v-if="sel.ref"><a :href="link(sel.ref[0], sel.ref[1])">Abrir o registo no CRM</a></p>
          <div style="display:flex;gap:8px;margin-top:12px"><a v-if="sel.local && sel.local.includes('meet')" class="btn prim sm" :href="sel.local" target="_blank">Entrar na reunião</a><button v-if="sel.origem==='agenda' && sel.href" class="btn sm" @click="apagar(sel)">Apagar</button></div>
        </div></div>
    </div>
    <div class="modal-fundo" v-if="form" @click.self="form=null">
      <div class="modal" style="max-width:560px"><header><b>Nova reunião</b><button class="btn sm" @click="form=null">Fechar</button></header>
        <form class="corpo-email form-cal" @submit.prevent="gravar">
          <label>Título<input v-model="form.titulo" required placeholder="Ex.: Apresentação da proposta"></label>
          <div class="linha3"><label>Dia<input type="date" v-model="form.dia"></label><label>Início<input type="time" v-model="form.ini" step="900"></label><label>Fim<input type="time" v-model="form.fim" step="900"></label></div>
          <div v-if="equipa.length"><div class="sub" style="font-size:13px;margin-bottom:4px">Colegas</div>
            <div style="display:flex;gap:6px;flex-wrap:wrap"><label v-for="p in equipa" :key="p.email" class="chip-eq" :style="{borderColor:p.cor, background: form.colegas.includes(p.email) ? p.cor : 'transparent', color: form.colegas.includes(p.email) ? '#fff' : 'var(--ink)'}"><input type="checkbox" :value="p.email" v-model="form.colegas" style="display:none">{{ p.nome }}</label></div></div>
          <label>Convidados de fora (emails, separados por vírgulas)<input v-model="form.convidados" placeholder="cliente@empresa.pt"></label>
          <button type="button" class="btn sm" @click="primeiroLivre" :disabled="procurar" style="align-self:flex-start">{{ procurar ? 'A procurar…' : '⌕ Primeiro horário livre para todos' }}</button>
          <label class="chk-l"><input type="checkbox" v-model="form.meet"> Reunião no Stratechna Meet (a ligação vai no convite)</label>
          <label v-if="!form.meet">Local<input v-model="form.local"></label>
          <label>Calendário<select v-model="form.calendario"><option v-for="c in (d?.calendarios||[]).filter(c=>c.escreve)" :key="c.href" :value="c.href">{{ c.nome }}</option></select></label>
          <label>Notas para os convidados<textarea v-model="form.descricao" rows="3"></textarea></label>
          <div style="display:flex;justify-content:space-between;align-items:center;gap:8px"><span class="sub" style="font-size:12px">Fica na sua agenda do Orbit Mail<template v-if="refDn"> e na cronologia do cliente</template>.</span><button class="btn prim" :disabled="aGravar">{{ aGravar ? 'A marcar…' : 'Marcar reunião' }}</button></div>
        </form></div>
    </div>
  </div>`,
};


// ── Tarefas e projetos (A2): tarefas do CRM + tarefas dos projetos (ERPNext) num só sítio ───────────────
async function apiT(metodo, args = {}, post = false) {
  const url = `/api/method/orbit.interface.trabalho.${metodo}`;
  const op = { headers: { "X-Frappe-CSRF-Token": window.csrf_token, Accept: "application/json" } };
  let r;
  if (post) { op.method = "POST"; op.headers["Content-Type"] = "application/json"; op.body = JSON.stringify(args); r = await fetch(url, op); }
  else r = await fetch(url + "?" + new URLSearchParams(args), op);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) { let m = "Erro"; try { m = JSON.parse(JSON.parse(j._server_messages)[0]).message; } catch (e) {} toast(String(m).replace(/<[^>]+>/g, "")); throw new Error(m); }
  return j.message;
}
const GRUPOS_T = [["atrasadas", "Atrasadas"], ["hoje", "Hoje"], ["semana", "Esta semana"], ["depois", "Mais tarde"], ["sem_data", "Sem data"]];
const Tarefas = {
  setup() {
    let v0 = null; try { v0 = localStorage.getItem("orbit.tarefas.vista"); } catch (e) {}
    const vista = ref(v0 || "minhas"); const itens = ref(null); const q = ref(""); const nova = ref({ titulo: "", data: "", projeto: "" }); const projs = ref([]);
    let tq; let primeira = !v0;   // 25-11-2026 (Margot): só na 1.ª abertura, sem escolha guardada, se passa à Equipa; nunca depois de a pessoa escolher «As minhas»
    const carregar = async () => {
      itens.value = await apiT("tarefas", { vista: vista.value, q: q.value });
      if (primeira && vista.value === "minhas" && !itens.value.length && !q.value) { primeira = false; vista.value = "equipa"; return; }
      primeira = false;
    };
    watch(vista, (v) => { try { localStorage.setItem("orbit.tarefas.vista", v); } catch (e) {} carregar(); });
    watch(q, () => { clearTimeout(tq); tq = setTimeout(carregar, 300); });
    onMounted(async () => { carregar(); projs.value = await apiT("projetos", {}); });
    const grupos = computed(() => GRUPOS_T.map(([g, r]) => ({ g, r, itens: (itens.value || []).filter((t) => t.grupo === g) })).filter((x) => x.itens.length));
    const feita = async (t) => { await apiT("concluir", { tipo: t.tipo, nome: t.id }, true); itens.value = itens.value.filter((x) => x !== t); toast("Concluída"); };
    const criar = async () => {
      if (!nova.value.titulo.trim()) return;
      await apiT("criar", { titulo: nova.value.titulo, data: nova.value.data || null, projeto: nova.value.projeto || null }, true);
      nova.value = { titulo: "", data: "", projeto: nova.value.projeto }; toast("Tarefa criada"); carregar();
    };
    // lote 2 (25-11): a tarefa abre — do CRM numa janela com todos os campos, do projeto na ficha completa
    const aberta = ref(null);
    const abrir = (t) => { if (t.tipo === "crm") aberta.value = { id: t.id }; else location.hash = irErp("Task", t.id); };
    return { vista, itens, q, grupos, feita, nova, criar, projs, link, data, aberta, abrir, carregar };
  },
  template: `
  <div>
    <div class="pad" style="padding-bottom:12px;display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap">
      <div><h1>Tarefas</h1><div class="sub">Do CRM e dos projetos, num só sítio<template v-if="itens"> · {{ itens.length }} por fazer</template></div></div>
      <div style="display:flex;gap:8px"><a class="btn prim" href="#/fila">▶ Começar as minhas tarefas</a><a class="btn" href="#/projetos">Projetos</a></div>
    </div>
    <div class="vistas"><button :class="{ativo:vista==='minhas'}" @click="vista='minhas'">As minhas</button><button :class="{ativo:vista==='equipa'}" @click="vista='equipa'">Equipa</button></div>
    <div class="filtros"><input class="filtro" style="border-style:solid;min-width:220px" v-model="q" placeholder="Procurar tarefas…"></div>
    <form class="cartao compor compor-tarefa" style="margin:0 24px 14px" @submit.prevent="criar">
      <input v-model="nova.titulo" placeholder="Nova tarefa…"><input type="date" v-model="nova.data" style="flex:none;width:150px">
      <select v-model="nova.projeto" class="btn sm" style="max-width:220px"><option value="">Sem projeto (CRM)</option><option v-for="p in projs" :key="p.name" :value="p.name">{{ p.project_name }}</option></select>
      <button class="btn sm prim" :disabled="!nova.titulo.trim()">Criar</button>
    </form>
    <div v-if="!itens" class="carregar">A carregar…</div>
    <div v-else-if="!itens.length" class="vazio">{{ q ? 'Nenhuma tarefa com esse texto.' : vista==='minhas' ? 'Não tem tarefas atribuídas a si. As tarefas sem responsável estão em «Equipa» — abra uma e atribua-a, ou atribua várias de uma vez na lista de tarefas.' : 'Nada por fazer.' }}</div>
    <div v-for="g in grupos" :key="g.g" class="cartao" style="margin:0 24px 14px">
      <header><h2 :style="g.g==='atrasadas'?{color:'var(--acao)'}:{}">{{ g.r }} <span class="sub" style="font-weight:400">{{ g.itens.length }}</span></h2></header>
      <div class="linha" v-for="t in g.itens" :key="t.tipo+t.id">
        <span class="chk" @click="feita(t)" title="Marcar como concluída" style="cursor:pointer"></span>
        <div class="cresce"><a href="javascript:void 0" class="tarefa-tit" @click="abrir(t)">{{ t.titulo }}</a><small>
          <a v-if="t.projeto" :href="'#/projeto/'+encodeURIComponent(t.projeto)">{{ t.projeto_nome || t.projeto }}</a>
          <a v-else-if="t.ref" :href="link(t.ref[0],t.ref[1])">{{ t.ref_titulo }}</a>
          <span v-if="t.dono"> · {{ t.dono }}</span></small></div>
        <span class="etq" :class="t.prioridade==='Alta'||t.prioridade==='Urgente'?'ambar':''" v-if="t.prioridade && t.prioridade!=='Média'">{{ t.prioridade }}</span>
        <span class="sub" v-if="t.data">{{ data(t.data,false) }}</span>
      </div>
    </div>
    <TarefaForm v-if="aberta" :id="aberta.id" @fechar="aberta=null" @gravado="carregar()"/>
  </div>`,
};

const Projetos = {
  setup() {
    const estado = ref("Open"); const d = ref(null); const q = ref(""); let tq;
    const carregar = async () => (d.value = await apiT("projetos", { estado: estado.value, q: q.value }));
    watch(estado, carregar); watch(q, () => { clearTimeout(tq); tq = setTimeout(carregar, 300); }); onMounted(carregar);
    return { estado, d, q, data };
  },
  template: `
  <div>
    <div class="pad" style="padding-bottom:12px;display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap"><div><h1>Projetos</h1><div class="sub" v-if="d">{{ d.length }} projetos</div></div>
      <div class="acoes-lista"><a class="btn prim" href="#/erp/Project/novo">+ Novo projeto</a><a class="btn" href="#/erp/Task">Todas as tarefas</a></div></div>
    <div class="vistas"><button v-for="e in [['Open','Em curso'],['On hold','Em pausa'],['Completed','Concluídos'],['','Todos']]" :key="e[0]" :class="{ativo:estado===e[0]}" @click="estado=e[0]">{{ e[1] }}</button></div>
    <div class="filtros"><input class="filtro" style="border-style:solid;min-width:220px" v-model="q" placeholder="Procurar projeto ou cliente…"></div>
    <div v-if="!d" class="carregar">A carregar…</div>
    <div class="grelha-proj" v-else>
      <a class="cartao proj" v-for="p in d" :key="p.name" :href="'#/projeto/'+encodeURIComponent(p.name)">
        <b>{{ p.project_name }}</b><div class="sub">{{ p.customer || p.marca || '' }}</div>
        <div class="barra"><i :style="{width:(p.progresso||0)+'%'}"></i></div>
        <div class="proj-n"><span>{{ Math.round(p.progresso||0) }} %</span><span>{{ p.abertas }} por fazer</span><span v-if="p.atrasadas" style="color:var(--acao)">{{ p.atrasadas }} atrasadas</span><span v-if="p.expected_end_date">até {{ data(p.expected_end_date,false) }}</span></div>
      </a>
    </div>
  </div>`,
};

const Projeto = {
  props: ["nome"],
  setup(props) {
    const p = ref(null); const arrastar = ref(null); const alvo = ref(""); const nova = ref(""); const novaData = ref("");
    const carregar = async () => (p.value = await apiT("projeto", { nome: props.nome }));
    onMounted(carregar);
    const largar = async (col) => { const t = arrastar.value; alvo.value = ""; arrastar.value = null; if (!t || t.estado === col.estado) return; await apiT("mover", { nome: t.id, estado: col.estado }, true); carregar(); };
    const criar = async () => { if (!nova.value.trim()) return; await apiT("criar", { titulo: nova.value, data: novaData.value || null, projeto: props.nome }, true); nova.value = ""; novaData.value = ""; carregar(); };
    // lote 6 (25-11): Quadro | Gantt, como as vistas do ecrã antigo; as tarefas abrem na ficha completa
    let m0 = "quadro"; try { m0 = localStorage.getItem("orbit.projeto.vista") || m0; } catch (e) {}
    const vista = ref(m0); watch(vista, (v) => { try { localStorage.setItem("orbit.projeto.vista", v); } catch (e) {} });
    const gantt = computed(() => { if (!p.value) return null; const ts = p.value.colunas.flatMap((c) => c.cartoes.map((t) => ({ ...t, estado: c.estado, rotulo: c.rotulo })));
      const com = ts.filter((t) => t.inicio || t.data); if (!com.length) return { ts: [], dias: 0 };
      const ds = com.flatMap((t) => [t.inicio || t.data, t.data || t.inicio]).sort(); const ini = new Date(ds[0]); const fim = new Date(ds[ds.length - 1]);
      const dias = Math.max(1, Math.round((fim - ini) / 864e5) + 1); const pos = (x) => Math.round((new Date(x) - ini) / 864e5);
      const meses = []; for (let d = new Date(ini.getFullYear(), ini.getMonth(), 1); d <= fim; d = new Date(d.getFullYear(), d.getMonth() + 1, 1)) meses.push({ r: d.toLocaleDateString("pt-PT", { month: "short", year: "2-digit" }), x: Math.max(0, pos(d)) });
      const hoje = pos(new Date().toISOString().slice(0, 10));
      return { dias, meses, hoje, ts: com.map((t) => { const a = pos(t.inicio || t.data), b = pos(t.data || t.inicio); return { ...t, x: Math.min(a, b), w: Math.abs(b - a) + 1 }; }).sort((u, v) => u.x - v.x), sem: ts.length - com.length }; });
    return { p, arrastar, alvo, largar, nova, novaData, criar, data, vista, gantt, irErp };
  },
  template: `
  <div v-if="p">
    <div class="pad" style="padding-bottom:10px;display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap">
      <div><div style="font-size:13px"><a href="#/projetos">← Projetos</a></div><h1>{{ p.titulo }}</h1>
        <div class="sub">{{ [p.cliente, p.marca].filter(Boolean).join(' · ') }}<template v-if="p.fim"> · até {{ data(p.fim,false) }}</template> · {{ Math.round(p.progresso) }} %<template v-if="p.horas_orcamento"> · {{ p.horas.toFixed(1) }} h de {{ p.horas_orcamento }} h</template><template v-else-if="p.horas"> · {{ p.horas.toFixed(1) }} h registadas</template></div></div>
      <a class="btn" :href="'#/erp/Project/'+encodeURIComponent(String(p.classico||'').split('/').pop())">Todos os campos</a>
    </div>
    <form class="cartao compor" style="margin:0 24px 14px" @submit.prevent="criar"><input v-model="nova" placeholder="Nova tarefa neste projeto…"><input type="date" v-model="novaData" style="flex:none;width:150px"><button class="btn sm prim" :disabled="!nova.trim()">Criar</button></form>
    <div class="vistas"><button :class="{ativo: vista==='quadro'}" @click="vista='quadro'">Quadro</button><button :class="{ativo: vista==='gantt'}" @click="vista='gantt'">Gantt</button></div>
    <div v-if="vista==='gantt'" class="cartao gantt">
      <div v-if="!gantt.ts.length" class="vazio">As tarefas ainda não têm datas de início ou de fim.</div>
      <template v-else><div class="gantt-esc"><span v-for="m in gantt.meses" :key="m.r" :style="{left: (m.x/gantt.dias*100)+'%'}">{{ m.r }}</span></div>
        <div v-for="t in gantt.ts" :key="t.id" class="gantt-linha"><a class="gantt-nome" :href="irErp('Task', t.id)" :title="t.titulo">{{ t.titulo }}</a>
          <div class="gantt-pista"><i v-if="gantt.hoje>=0 && gantt.hoje<=gantt.dias" class="gantt-hoje" :style="{left:(gantt.hoje/gantt.dias*100)+'%'}"></i>
            <a class="gantt-barra" :class="'g-'+t.estado" :href="irErp('Task', t.id)" :style="{left:(t.x/gantt.dias*100)+'%', width:Math.max(t.w/gantt.dias*100, 1.2)+'%'}" :title="t.titulo + ' · ' + t.rotulo + (t.dono ? ' · ' + t.dono : '')"><b :style="{width:(t.progresso||0)+'%'}"></b></a></div></div>
        <div v-if="gantt.sem" class="sub" style="font-size:12px;margin-top:8px">{{ gantt.sem }} tarefa(s) sem datas não aparecem aqui.</div></template>
    </div>
    <div v-else class="funil" :style="{gridTemplateColumns:'repeat('+p.colunas.length+',minmax(220px,1fr))'}">
      <div class="coluna" v-for="c in p.colunas" :key="c.estado" :class="{alvo:alvo===c.estado}" @dragover.prevent="alvo=c.estado" @dragleave="alvo=''" @drop.prevent="largar(c)">
        <header><b>{{ c.rotulo }} <span class="sub" style="font-weight:500">{{ c.cartoes.length }}</span></b></header>
        <div class="cartao negocio" v-for="t in c.cartoes" :key="t.id" :draggable="p.pode_editar" @dragstart="arrastar={...t, estado:c.estado}">
          <h3 style="font-weight:500"><a :href="irErp('Task', t.id)" style="color:inherit;text-decoration:none" @click.stop>{{ t.titulo }}</a></h3>
          <div class="prox" :class="{atraso:c.estado==='Overdue'}"><template v-if="t.data">◷ {{ data(t.data,false) }}</template><template v-if="t.dono"> · {{ t.dono }}</template><template v-if="t.prioridade && t.prioridade!=='Média'"> · {{ t.prioridade }}</template></div>
        </div>
      </div>
    </div>
  </div>
  <div v-else class="carregar">A carregar…</div>`,
};


// ── Documentos (A3): o arquivo do Docs (Paperless) como a própria pessoa ─────────────────────────────────
async function apiD(metodo, args = {}) {
  const r = await fetch(`/api/method/orbit.interface.documentos.${metodo}?` + new URLSearchParams(args), { headers: { "X-Frappe-CSRF-Token": window.csrf_token, Accept: "application/json" } });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) { let m = "Erro"; try { m = JSON.parse(JSON.parse(j._server_messages)[0]).message; } catch (e) {} toast(String(m).replace(/<[^>]+>/g, "")); throw new Error(m); }
  return j.message;
}
const LigarConta = {
  emits: ["ligado"],
  setup(_, { emit }) {
    const pwd = ref("");
    const ligar = async () => { await apiCal("ligar", { pwd: pwd.value }, true); pwd.value = ""; toast("Conta ligada"); emit("ligado"); };
    return { pwd, ligar, user: (window.__ctx || {}).utilizador };
  },
  template: `<div class="cartao aviso-cal"><b>Ligar a sua conta</b>
    <p class="sub">Para ver o seu calendário e os seus documentos aqui, confirme uma vez a palavra-passe da sua caixa de correio ({{ user }}). Fica guardada cifrada no seu Orbit e só serve para isto. Quem entra no Orbit com a palavra-passe da caixa fica ligado sozinho.</p>
    <form @submit.prevent="ligar" style="display:flex;gap:8px;flex-wrap:wrap"><input type="password" v-model="pwd" autocomplete="current-password" placeholder="Palavra-passe da caixa" class="filtro" style="border-style:solid;min-width:240px"><button class="btn prim" :disabled="!pwd">Ligar</button></form></div>`,
};
const VerDocumento = {
  props: ["doc"], emits: ["fechar"],
  setup(props) {
    const url = ref(null); const erro = ref("");
    onMounted(async () => {
      try {
        const r = await fetch(`/api/method/orbit.interface.documentos.ver?id=${props.doc.id}`, { headers: { "X-Frappe-CSRF-Token": window.csrf_token } });
        if (!r.ok) throw new Error(); url.value = URL.createObjectURL(await r.blob());
      } catch (e) { erro.value = "Não foi possível mostrar o documento."; }
    });
    return { url, erro };
  },
  template: `<div class="modal-fundo" @click.self="$emit('fechar')"><div class="modal doc-modal">
    <header><div><b>{{ doc.titulo }}</b><div class="sub">{{ [doc.tipo, doc.correspondente, doc.criado].filter(Boolean).join(' · ') }}</div></div>
      <div style="display:flex;gap:6px"><a class="btn sm" :href="'/api/method/orbit.interface.documentos.descarregar?id='+doc.id">Descarregar</a><button class="btn sm" @click="$emit('fechar')">Fechar</button></div></header>
    <div class="doc-ver"><iframe v-if="url" :src="url" title="Documento"></iframe><div v-else class="carregar">{{ erro || 'A carregar…' }}</div></div>
    <div class="doc-meta"><span v-for="t in doc.tags" :key="t.nome" class="etq">{{ t.nome }}</span><span v-for="(v,k) in doc.campos" :key="k" class="sub" style="font-size:12px">{{ k }}: {{ v }}</span></div>
  </div></div>`,
};
const Documentos = {
  components: { LigarConta, VerDocumento },
  setup() {
    const f = ref(null); const d = ref(null); const q = ref(""); const tag = ref(""); const tipo = ref(""); const pagina = ref(1); const ver = ref(null);
    const subir = ref(null); const aSubir = ref(false); let tq;
    const carregar = async (junta = false) => {
      const r = await apiD("lista", { q: q.value, tag: tag.value, tipo: tipo.value, pagina: pagina.value });
      if (junta && d.value && !r.erro) { r.docs = d.value.docs.concat(r.docs); }
      d.value = r;
    };
    const inicio = async () => { f.value = await apiD("filtros"); if (!f.value.erro) carregar(); };
    watch([tag, tipo], () => { pagina.value = 1; carregar(); });
    watch(q, () => { clearTimeout(tq); tq = setTimeout(() => { pagina.value = 1; carregar(); }, 350); });
    onMounted(inicio);
    const areas = computed(() => {
      if (!f.value || f.value.erro) return [];
      const ts = f.value.tags; const filhos = (pai) => ts.filter((t) => (t.pai || null) === pai);
      const out = []; const anda = (pai, nivel) => filhos(pai).forEach((t) => { out.push({ ...t, nivel }); anda(t.id, nivel + 1); });
      anda(null, 0); return out;
    });
    const enviar = async (ev) => {
      const fd = new FormData(ev.target); if (!fd.get("ficheiro") || !fd.get("ficheiro").size) { toast("Escolha um ficheiro"); return; }
      aSubir.value = true;
      try {
        const r = await fetch("/api/method/orbit.interface.documentos.carregar", { method: "POST", body: fd, headers: { "X-Frappe-CSRF-Token": window.csrf_token } });
        const j = await r.json().catch(() => ({}));
        if (!r.ok) { let m = "Erro"; try { m = JSON.parse(JSON.parse(j._server_messages)[0]).message; } catch (e) {} toast(m); return; }
        toast("Carregado — o Docs está a processar (fica pesquisável dentro de instantes)"); subir.value = null;
      } finally { aSubir.value = false; }
    };
    const mini = (id) => `/api/method/orbit.interface.documentos.miniatura?id=${id}`;
    return { f, d, q, tag, tipo, pagina, ver, carregar, inicio, areas, subir, aSubir, enviar, mini, data };
  },
  template: `
  <div>
    <div class="pad" style="padding-bottom:12px;display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap">
      <div><h1>Documentos</h1><div class="sub" v-if="d && !d.erro">{{ d.total }} documentos</div></div>
      <button class="btn prim" @click="subir={}" :disabled="!f || f.erro">Carregar documento</button>
    </div>
    <div v-if="f && f.erro" style="padding:0 24px"><LigarConta v-if="f.erro!=='sem_docs'" @ligado="inicio"/><div v-else class="vazio">Este Orbit ainda não tem o Stratechna Docs.</div></div>
    <div v-else-if="!f" class="carregar">A carregar…</div>
    <div v-else class="docs">
      <aside class="canais">
        <h6>Áreas</h6>
        <button :class="{ativo:!tag}" @click="tag=''">Todos os documentos</button>
        <button v-for="t in areas" :key="t.id" :class="{ativo:tag===String(t.id)}" @click="tag=String(t.id)" :style="{paddingLeft:(10+t.nivel*14)+'px'}"><span class="ponto" :style="{background:t.cor||'var(--ink-3)'}"></span><span class="txt">{{ t.nome }}</span></button>
      </aside>
      <div style="min-width:0">
        <div class="filtros" style="padding-top:0"><input class="filtro" style="border-style:solid;min-width:260px" v-model="q" placeholder="Procurar no texto dos documentos…">
          <select class="filtro" style="border-style:solid" v-model="tipo"><option value="">Todos os tipos</option><option v-for="t in f.tipos" :key="t.id" :value="String(t.id)">{{ t.nome }}</option></select></div>
        <div v-if="!d" class="carregar">A carregar…</div>
        <div v-else-if="d.erro" class="vazio">Não foi possível ler o Docs.</div>
        <div v-else-if="!d.docs.length" class="vazio">Nenhum documento.</div>
        <div class="grelha-docs" v-else>
          <div class="cartao doc" v-for="x in d.docs" :key="x.id" @click="ver=x">
            <img :src="mini(x.id)" loading="lazy" alt="">
            <div class="doc-txt"><b>{{ x.titulo }}</b><div class="sub">{{ [x.tipo, x.correspondente].filter(Boolean).join(' · ') }}</div>
              <div class="sub" style="font-size:12px">{{ data(x.criado,false) }}</div>
              <div style="display:flex;gap:4px;flex-wrap:wrap;margin-top:4px"><span v-for="t in x.tags.slice(0,3)" :key="t.nome" class="etq" style="font-size:11px">{{ t.nome }}</span></div></div>
          </div>
        </div>
        <div class="mais-linhas" v-if="d && d.mais"><button class="btn sm" @click="pagina++; carregar(true)">Mostrar mais</button></div>
      </div>
    </div>
    <VerDocumento v-if="ver" :doc="ver" @fechar="ver=null"/>
    <div class="modal-fundo" v-if="subir" @click.self="subir=null">
      <div class="modal" style="max-width:520px"><header><b>Carregar documento</b><button class="btn sm" @click="subir=null">Fechar</button></header>
        <form class="corpo-email form-cal" @submit.prevent="enviar">
          <label>Ficheiro<input type="file" name="ficheiro" required></label>
          <label>Título (opcional)<input name="titulo"></label>
          <label>Área<select name="tags"><option value="">— o Docs decide pelas regras —</option><option v-for="t in areas" :key="t.id" :value="t.id">{{ '— '.repeat(t.nivel) + t.nome }}</option></select></label>
          <label>Tipo<select name="tipo"><option value="">— o Docs decide —</option><option v-for="t in f.tipos" :key="t.id" :value="t.id">{{ t.nome }}</option></select></label>
          <label>Processo (referência P-/WEB-/SUB-…)<input name="processo"></label>
          <div style="display:flex;justify-content:flex-end"><button class="btn prim" :disabled="aSubir">{{ aSubir ? 'A carregar…' : 'Carregar' }}</button></div>
        </form></div>
    </div>
  </div>`,
};


// ── Assinaturas (A4): pedidos do Sign (DocuSeal) do tenant ────────────────────────────────────────────
async function apiS(metodo, args = {}, post = false) {
  const url = `/api/method/orbit.interface.assinaturas.${metodo}`;
  const op = { headers: { "X-Frappe-CSRF-Token": window.csrf_token, Accept: "application/json" } };
  let r;
  if (post) { op.method = "POST"; op.headers["Content-Type"] = "application/json"; op.body = JSON.stringify(args); r = await fetch(url, op); }
  else r = await fetch(url + "?" + new URLSearchParams(args), op);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) { let m = "Erro"; try { m = JSON.parse(JSON.parse(j._server_messages)[0]).message; } catch (e) {} toast(String(m).replace(/<[^>]+>/g, "")); throw new Error(m); }
  return j.message;
}
const COR_EST = { completed: "verde", declined: "ambar", expired: "", pending: "azul", sent: "azul", opened: "roxo", awaiting: "azul" };
const EnviarAssinatura = {
  props: ["doctype", "name", "emailInicial", "nomeInicial"], emits: ["fechar", "enviado"],
  setup(props, { emit }) {
    const ms = ref(null); const modelo = ref(""); const pessoas = ref([]); const msg = ref(""); const aEnviar = ref(false);
    onMounted(async () => { ms.value = await apiS("modelos"); });
    watch(modelo, (id) => {
      const m = (ms.value || []).find((x) => String(x.id) === String(id)); if (!m) return;
      const papeis = m.papeis.length ? m.papeis : ["Primeira parte"];
      pessoas.value = papeis.map((p, i) => ({ papel: p, email: i === papeis.length - 1 ? (props.emailInicial || "") : "", nome: i === papeis.length - 1 ? (props.nomeInicial || "") : "" }));
    });
    const enviar = async () => {
      aEnviar.value = true;
      try { await apiS("enviar", { modelo: modelo.value, pessoas: JSON.stringify(pessoas.value), mensagem: msg.value, doctype: props.doctype || null, name: props.name || null }, true);
        toast("Enviado — o Sign manda o pedido por email"); emit("enviado"); emit("fechar"); } finally { aEnviar.value = false; }
    };
    return { ms, modelo, pessoas, msg, aEnviar, enviar };
  },
  template: `<div class="modal-fundo" @click.self="$emit('fechar')"><div class="modal" style="max-width:560px"><header><b>Enviar para assinar</b><button class="btn sm" @click="$emit('fechar')">Fechar</button></header>
    <form class="corpo-email form-cal" @submit.prevent="enviar">
      <label>Modelo do Sign<select v-model="modelo" required><option value="" disabled>{{ ms ? 'Escolha um modelo' : 'A carregar…' }}</option><option v-for="m in ms||[]" :key="m.id" :value="m.id">{{ m.nome }}</option></select></label>
      <p class="sub" v-if="ms && !ms.length" style="margin:0">Ainda não há modelos. Crie-os no Sign (carregar o PDF e marcar onde se assina).</p>
      <div v-for="(p,i) in pessoas" :key="i" class="linha3" style="grid-template-columns:1fr 1.4fr 1fr"><label>{{ p.papel }}<input v-model="p.nome" placeholder="Nome"></label><label>Email<input v-model="p.email" type="email" required></label><span></span></div>
      <label>Mensagem (opcional)<textarea v-model="msg" rows="3" placeholder="Junto envio o documento para assinatura."></textarea></label>
      <div style="display:flex;justify-content:space-between;align-items:center;gap:8px"><span class="sub" style="font-size:12px">O pedido segue do Sign por email<template v-if="name">; fica uma nota na cronologia</template>.</span><button class="btn prim" :disabled="!modelo || aEnviar">{{ aEnviar ? 'A enviar…' : 'Enviar' }}</button></div>
    </form></div></div>`,
};
const Assinaturas = {
  components: { EnviarAssinatura },
  setup() {
    const est = ref(""); const q = ref(""); const d = ref(null); const novo = ref(false); const ligado = ref(true); let tq;
    const carregar = async () => { d.value = null; const r = await apiS("lista", { q: q.value, estado_f: est.value }); ligado.value = r.ligado; d.value = r.itens; };
    watch(est, carregar); watch(q, () => { clearTimeout(tq); tq = setTimeout(carregar, 350); }); onMounted(carregar);
    return { est, q, d, novo, ligado, carregar, COR_EST, data };
  },
  template: `
  <div>
    <div class="pad" style="padding-bottom:12px;display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap">
      <div><h1>Assinaturas</h1><div class="sub">Pedidos de assinatura do Stratechna Sign</div></div>
      <button class="btn prim" @click="novo=true" :disabled="!ligado">Enviar para assinar</button>
    </div>
    <div class="vistas"><button v-for="e in [['','Todos'],['pending','À espera'],['completed','Assinados'],['declined','Recusados'],['expired','Expirados']]" :key="e[0]" :class="{ativo:est===e[0]}" @click="est=e[0]">{{ e[1] }}</button></div>
    <div class="filtros"><input class="filtro" style="border-style:solid;min-width:240px" v-model="q" placeholder="Procurar por email ou nome…"></div>
    <div v-if="!ligado" class="vazio">Este Orbit ainda não está ligado ao Sign.</div>
    <div v-else-if="!d" class="carregar">A carregar…</div>
    <div v-else-if="!d.length" class="vazio">Nenhum pedido.</div>
    <div v-else class="tabela-wrap"><table>
      <thead><tr><th>Documento</th><th>Quem assina</th><th>Estado</th><th>Enviado</th><th></th></tr></thead>
      <tbody><tr v-for="x in d" :key="x.id" style="cursor:default">
        <td><b>{{ x.modelo }}</b></td>
        <td><div v-for="p in x.pessoas" :key="p.email" style="white-space:nowrap"><span class="etq" :class="COR_EST[p.estado_c]" style="font-size:11px">{{ p.estado }}</span> {{ p.nome || p.email }} <span class="sub">({{ p.papel }})</span></div></td>
        <td><span class="etq" :class="COR_EST[x.estado_c]">{{ x.estado }}</span></td>
        <td class="sub">{{ data(x.criado) }}</td>
        <td><a v-if="x.estado_c==='completed'" class="btn sm" :href="'/api/method/orbit.interface.assinaturas.documento?id='+x.id" target="_blank">Documento assinado</a></td>
      </tr></tbody></table></div>
    <EnviarAssinatura v-if="novo" @fechar="novo=false" @enviado="carregar"/>
  </div>`,
};



// ── Tempo (A5): registo de horas (Timesheet do ERPNext → livro de horas do cliente no portal) ───────────
async function apiTm(metodo, args = {}, post = false) {
  const url = `/api/method/orbit.interface.tempo.${metodo}`;
  const op = { headers: { "X-Frappe-CSRF-Token": window.csrf_token, Accept: "application/json" } };
  let r;
  if (post) { op.method = "POST"; op.headers["Content-Type"] = "application/json"; op.body = JSON.stringify(args); r = await fetch(url, op); }
  else r = await fetch(url + "?" + new URLSearchParams(args), op);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) { let m = "Erro"; try { m = JSON.parse(JSON.parse(j._server_messages)[0]).message; } catch (e) {} toast(String(m).replace(/<[^>]+>/g, "")); throw new Error(m); }
  return j.message;
}
function lerHoras(t) {
  t = String(t || "").trim().replace(",", ".");
  if (/^\d+:\d{1,2}$/.test(t)) { const [h, m] = t.split(":"); return +h + +m / 60; }
  if (/^\d+(\.\d+)?h?$/.test(t)) return parseFloat(t);
  const m = t.match(/^(\d+)\s*h\s*(\d+)\s*m?$/); if (m) return +m[1] + +m[2] / 60;
  const mm = t.match(/^(\d+)\s*m(in)?$/); if (mm) return +mm[1] / 60;
  return NaN;
}
const fmtH = (h) => { const t = Math.round((h || 0) * 60); return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, "0")}`; };
const Tempo = {
  setup() {
    const semanaIni = ref(isoDia(segunda(new Date()))); const d = ref(null); const op = ref(null); const tarefasP = ref([]);
    const f = ref({ data: isoDia(new Date()), horas: "", descricao: "", cliente: window.__tempo_cliente || "", projeto: "", tarefa: "", atividade: "", faturavel: true });
    window.__tempo_cliente = "";
    const aGravar = ref(false);
    const carregar = async () => (d.value = await apiTm("semana", { inicio: semanaIni.value }));
    watch(semanaIni, carregar);
    onMounted(async () => { carregar(); op.value = await apiTm("opcoes"); });
    watch(() => f.value.projeto, async (p) => { f.value.tarefa = ""; tarefasP.value = p ? await apiTm("tarefas_do_projeto", { projeto: p }) : [];
      const pr = (op.value?.projetos || []).find((x) => x.name === p); if (pr && pr.customer && !f.value.cliente) f.value.cliente = pr.customer; });
    const projetosDoCliente = computed(() => (op.value?.projetos || []).filter((p) => !f.value.cliente || !p.customer || p.customer === f.value.cliente));
    const mover = (n) => { const x = new Date(semanaIni.value); x.setDate(x.getDate() + 7 * n); semanaIni.value = isoDia(x); };
    const dias = computed(() => [...Array(7)].map((_, i) => { const x = new Date(semanaIni.value); x.setDate(x.getDate() + i); return isoDia(x); }));
    const registar = async () => {
      const h = lerHoras(f.value.horas); if (!(h > 0)) { toast("Horas como 1:30, 1,5 ou 45m"); return; }
      aGravar.value = true;
      try {
        await apiTm("registar", { data: f.value.data, horas: h, descricao: f.value.descricao, cliente: f.value.cliente || null, projeto: f.value.projeto || null,
          tarefa: f.value.tarefa || null, atividade: f.value.atividade || null, faturavel: f.value.faturavel ? 1 : 0 }, true);
        toast(`${fmtH(h)} registadas`); f.value.horas = ""; f.value.descricao = ""; semanaIni.value = isoDia(segunda(new Date(f.value.data))); carregar();
      } finally { aGravar.value = false; }
    };
    const anular = async (l) => { if (!confirm("Anular este registo? Sai também do livro de horas do cliente.")) return; await apiTm("anular", { timesheet: l.ts }, true); toast("Anulado"); carregar(); };
    const nomeCliente = (c) => (op.value?.clientes || []).find((x) => x.name === c)?.customer_name || c;
    const isoDiaHoje = () => isoDia(new Date());
    return { d, op, f, tarefasP, projetosDoCliente, mover, dias, registar, anular, aGravar, fmtH, nomeCliente, data, semanaIni, isoDiaHoje };
  },
  template: `
  <div class="pad">
    <div class="ola"><div><h1>Tempo</h1><div class="sub">O que regista aqui entra no livro de horas do cliente, no portal.</div></div>
      <div class="cal-nav"><button class="btn sm" @click="mover(-1)">‹</button><button class="btn sm" @click="semanaIni=isoDiaHoje()">Esta semana</button><button class="btn sm" @click="mover(1)">›</button></div></div>
    <form class="cartao form-tempo" @submit.prevent="registar">
      <div class="linha-t">
        <label>Dia<input type="date" v-model="f.data"></label>
        <label>Horas<input v-model="f.horas" placeholder="1:30" style="width:90px"></label>
        <label style="flex:1;min-width:200px">Cliente<input v-model="f.cliente" list="orbit-clientes" placeholder="Procurar cliente…"><datalist id="orbit-clientes"><option v-for="c in op?.clientes||[]" :key="c.name" :value="c.name">{{ c.customer_name }}</option></datalist></label>
        <label style="min-width:200px">Projeto<select v-model="f.projeto"><option value="">—</option><option v-for="p in projetosDoCliente" :key="p.name" :value="p.name">{{ p.project_name }}</option></select></label>
        <label v-if="tarefasP.length" style="min-width:180px">Tarefa<select v-model="f.tarefa"><option value="">—</option><option v-for="t in tarefasP" :key="t.name" :value="t.name">{{ t.subject }}</option></select></label>
        <label>Atividade<select v-model="f.atividade"><option value="">—</option><option v-for="a in op?.atividades||[]" :key="a" :value="a">{{ a }}</option></select></label>
      </div>
      <div class="linha-t"><label style="flex:1">O que foi feito<input v-model="f.descricao" required placeholder="Ex.: Correção do formulário de contacto e testes"></label>
        <label class="chk-l"><input type="checkbox" v-model="f.faturavel"> Faturável</label>
        <button class="btn prim" :disabled="aGravar">{{ aGravar ? 'A registar…' : 'Registar' }}</button></div>
    </form>
    <div v-if="!d" class="carregar">A carregar…</div>
    <template v-else>
      <div class="semana-t"><div v-for="x in dias" :key="x" class="dia-t" :class="{hoje: x===isoDiaHoje()}"><span>{{ new Date(x).toLocaleDateString('pt-PT',{weekday:'short',day:'numeric'}) }}</span><b>{{ fmtH(d.dias[x]||0) }}</b></div>
        <div class="dia-t total"><span>Semana</span><b>{{ fmtH(d.total) }}</b></div></div>
      <div v-if="!d.linhas.length" class="vazio">Sem registos nesta semana.</div>
      <div class="cartao" v-else>
        <div class="linha" v-for="l in d.linhas" :key="l.name">
          <span class="hora" style="width:56px">{{ fmtH(l.hours) }}</span>
          <div class="cresce">{{ l.description || '—' }}<small>{{ data(l.dia,false) }} · {{ [nomeCliente(l.customer), l.projeto_nome, l.tarefa_nome, l.ticket_nome].filter(Boolean).join(' · ') }}<template v-if="l.activity_type"> · {{ l.activity_type }}</template><template v-if="!l.is_billable"> · não faturável</template></small></div>
          <button class="btn sm" @click="anular(l)">Anular</button>
        </div>
      </div>
    </template>
  </div>`,
};


// ── Propostas e faturas na ficha (A6): ERPNext do tenant e, na casa, o portal ─────────────────────────
async function apiV(metodo, args = {}) {
  const r = await fetch(`/api/method/orbit.interface.vendas.${metodo}?` + new URLSearchParams(args), { headers: { Accept: "application/json" } });
  const j = await r.json().catch(() => ({})); if (!r.ok) throw new Error("vendas"); return j.message;
}
const COR_V = { "Paga": "verde", "Aprovada": "verde", "Encomendada": "verde", "Por pagar": "ambar", "Em atraso": "ambar", "Por emitir": "ambar", "Enviada": "azul", "Vista": "roxo", "Respondida": "roxo" };


// ── Chat (A7): o Stratechna Chat (Zulip) com a chave pessoal de cada um ────────────────────────────────
async function apiC(metodo, args = {}, post = false) {
  const url = `/api/method/orbit.interface.chat.${metodo}`;
  const op = { headers: { "X-Frappe-CSRF-Token": window.csrf_token, Accept: "application/json" } };
  let r;
  if (post) { op.method = "POST"; op.headers["Content-Type"] = "application/json"; op.body = JSON.stringify(args); r = await fetch(url, op); }
  else r = await fetch(url + "?" + new URLSearchParams(args), op);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) { let m = "Erro"; try { m = JSON.parse(JSON.parse(j._server_messages)[0]).message; } catch (e) {} toast(String(m).replace(/<[^>]+>/g, "")); throw new Error(m); }
  return j.message;
}
// Nomes de emoji do Zulip mais usados → caráter (o resto fica como :nome:)
const EMOJIS = { smile: "😄", grinning: "😀", smiley: "😃", laughing: "😆", joy: "😂", rolling_on_the_floor_laughing: "🤣", rofl: "🤣",
  wink: "😉", blush: "😊", innocent: "😇", heart_eyes: "😍", star_struck: "🤩", kissing_heart: "😘", yum: "😋", stuck_out_tongue: "😛",
  thinking: "🤔", neutral: "😐", expressionless: "😑", rolling_eyes: "🙄", smirk: "😏", relieved: "😌", sleeping: "😴", mask: "😷",
  sunglasses: "😎", nerd: "🤓", confused: "😕", slight_frown: "🙁", frown: "☹️", sad: "😢", cry: "😢", sob: "😭", scream: "😱",
  angry: "😠", rage: "😡", exploding_head: "🤯", flushed: "😳", hugging: "🤗", shush: "🤫", zipper_mouth: "🤐", slight_smile: "🙂",
  upside_down: "🙃", sweat_smile: "😅", grimacing: "😬", partying_face: "🥳", wave: "👋", hello: "👋", raised_hand: "✋",
  ok: "👌", ok_hand: "👌", "+1": "👍", thumbs_up: "👍", like: "👍", "-1": "👎", thumbs_down: "👎", clap: "👏", raised_hands: "🙌",
  pray: "🙏", handshake: "🤝", muscle: "💪", point_right: "👉", point_left: "👈", point_up: "☝️", point_down: "👇", fist: "✊",
  v: "✌️", crossed_fingers: "🤞", writing: "✍️", eyes: "👀", brain: "🧠", heart: "❤️", red_heart: "❤️", orange_heart: "🧡",
  yellow_heart: "💛", green_heart: "💚", blue_heart: "💙", purple_heart: "💜", black_heart: "🖤", broken_heart: "💔",
  fire: "🔥", sparkles: "✨", star: "⭐", glowing_star: "🌟", tada: "🎉", party_popper: "🎉", confetti: "🎊", gift: "🎁",
  balloon: "🎈", trophy: "🏆", medal: "🏅", 100: "💯", check: "✅", check_mark: "✔️", white_check_mark: "✅", heavy_check_mark: "✔️",
  x: "❌", cross_mark: "❌", warning: "⚠️", exclamation: "❗", question: "❓", info: "ℹ️", stop_sign: "🛑", no_entry: "⛔",
  rocket: "🚀", light_bulb: "💡", bulb: "💡", idea: "💡", zap: "⚡", boom: "💥", hourglass: "⌛", stopwatch: "⏱️", clock: "🕐",
  calendar: "📅", date: "📅", email: "📧", envelope: "✉️", inbox: "📥", outbox: "📤", phone: "📞", telephone: "☎️",
  mobile_phone: "📱", computer: "💻", keyboard: "⌨️", printer: "🖨️", camera: "📷", video_camera: "📹", link: "🔗",
  lock: "🔒", unlock: "🔓", key: "🔑", pencil: "✏️", memo: "📝", clipboard: "📋", paperclip: "📎", pushpin: "📌",
  bookmark: "🔖", book: "📖", books: "📚", newspaper: "📰", chart: "📈", chart_increasing: "📈", chart_decreasing: "📉",
  bar_chart: "📊", money: "💰", euro: "💶", credit_card: "💳", package: "📦", truck: "🚚", house: "🏠", office: "🏢",
  coffee: "☕", tea: "🍵", beer: "🍺", wine: "🍷", cake: "🎂", pizza: "🍕", sun: "☀️", sunny: "☀️", cloud: "☁️",
  rain: "🌧️", umbrella: "☂️", snowflake: "❄️", rainbow: "🌈", earth_africa: "🌍", globe: "🌐", plant: "🌱", tree: "🌳",
  octopus: "🐙", dog: "🐶", cat: "🐱", robot: "🤖", ghost: "👻", bell: "🔔", speech_bubble: "💬", thought: "💭",
  search: "🔍", gear: "⚙️", wrench: "🔧", hammer: "🔨", tools: "🛠️", shield: "🛡️", recycle: "♻️", soon: "🔜", new: "🆕",
  arrow_right: "➡️", arrow_left: "⬅️", arrow_up: "⬆️", arrow_down: "⬇️", repeat: "🔁", plus: "➕", minus: "➖", heavy_plus_sign: "➕" };
// 27-11-2026: markdown do Chat em texto seguro (nada de HTML do servidor) — ligações [texto](endereço) clicáveis, as
// relativas (/#inbox, /help/…) abrem no Chat da organização, **negrito**, *itálico*, `código`, emojis :nome:
let CHAT_BASE = "";
function textoChat(t, base) {
  base = base || CHAT_BASE;
  const esc = (x) => String(x || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const ligacoes = [];
  const marca = (href, txt) => { ligacoes.push('<a href="' + esc(href) + '" target="_blank" rel="noopener">' + txt + "</a>"); return "\u0000" + (ligacoes.length - 1) + "\u0000"; };
  const url = (u) => { u = u.trim(); if (/^https?:\/\//i.test(u)) return u; if (/^\/|^#/.test(u) && base) return base.replace(/\/$/, "") + (u[0] === "#" ? "/" + u : u); return null; };
  let x = String(t || "");
  x = x.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (m, txt, u) => { const h = url(u); return h ? marca(h, esc(txt)) : esc(txt); });
  x = x.replace(/(https?:\/\/[^\s<)]+)/g, (m) => marca(m, esc(m)));
  x = esc(x).replace(/:([a-z0-9_+\-]+):/g, (m, n) => EMOJIS[n] || m)
    .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>").replace(/(^|[\s(])\*([^*\n]+)\*/g, "$1<i>$2</i>").replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\n/g, "<br>");
  return x.replace(/\u0000(\d+)\u0000/g, (m, i) => ligacoes[+i]);
}
const Chat = {
  setup() {
    const conv = ref(null); const sel = ref(null); const msgs = ref(null); const texto = ref(""); const pwd = ref(""); const novoTopico = ref("");
    const pessoas = ref([]); const novaDm = ref(""); let rel;
    const novoCanal = ref(null); const novaConversa = ref(null);
    const criarCanal = async () => { const n = novoCanal.value; if (!n.nome.trim()) return;
      const r = await apiC("criar_canal", { nome: n.nome, descricao: n.descricao, privado: n.privado ? 1 : 0, pessoas: JSON.stringify(n.pessoas) }, true);
      novoCanal.value = null; toast("Canal criado"); await carregarConv(); if (r.id) abrir({ canal: r.id, nomeCanal: r.nome }); };
    const comecarConversa = async () => { const c = novaConversa.value; if (!c.topico.trim() || !c.texto.trim()) return;
      await apiC("enviar", { texto: c.texto, canal: c.canal, topico: c.topico.trim() }, true);
      novaConversa.value = null; await carregarConv(); abrir({ canal: c.canal, nomeCanal: c.nomeCanal, topico: c.topico.trim() }); };
    const carregarConv = async () => { conv.value = await apiC("conversas"); if (conv.value?.base) CHAT_BASE = conv.value.base; };
    const carregarMsgs = async (rolar = true) => {
      if (!sel.value) return;
      const a = sel.value.ids ? { ids: sel.value.ids.join(",") } : { canal: sel.value.canal, topico: sel.value.topico || "" };
      const r = await apiC("mensagens", a); const novo = !msgs.value || r.mensagens.length !== msgs.value.length; msgs.value = r.mensagens;
      if (rolar && novo) nextTick(() => { const m = document.querySelector(".chat-msgs"); if (m) m.scrollTop = m.scrollHeight; });
    };
    const abrir = (x) => { sel.value = x; msgs.value = null; carregarMsgs(); };
    onMounted(async () => { await carregarConv(); if (conv.value?.ligado) pessoas.value = await apiC("pessoas");
      rel = setInterval(() => { if (document.hidden) return; carregarConv(); carregarMsgs(); }, 15000); });
    const sair = () => clearInterval(rel);
    window.addEventListener("hashchange", sair, { once: true });
    const ligar = async () => { await apiC("ligar", { pwd: pwd.value }, true); pwd.value = ""; toast("Chat ligado"); await carregarConv(); pessoas.value = await apiC("pessoas"); };
    const enviar = async () => {
      if (!texto.value.trim() || !sel.value) return;
      const a = sel.value.ids ? { ids: sel.value.ids.join(",") } : { canal: sel.value.canal, topico: sel.value.topico || novoTopico.value || "geral" };
      await apiC("enviar", { texto: texto.value, ...a }, true); texto.value = "";
      if (!sel.value.ids && !sel.value.topico) sel.value = { ...sel.value, topico: a.topico };
      carregarMsgs(); carregarConv();
    };
    const abrirDm = () => { const p = pessoas.value.find((x) => String(x.id) === novaDm.value); if (p) abrir({ ids: [p.id], nome: p.nome }); novaDm.value = ""; };
    const hora = (ts) => { const d = new Date(ts * 1000); return d.toDateString() === new Date().toDateString() ? d.toLocaleTimeString("pt-PT", { hour: "2-digit", minute: "2-digit" }) : d.toLocaleDateString("pt-PT", { day: "2-digit", month: "2-digit" }) + " " + d.toLocaleTimeString("pt-PT", { hour: "2-digit", minute: "2-digit" }); };
    const titulo = computed(() => !sel.value ? "" : sel.value.ids ? sel.value.nome : `${sel.value.nomeCanal}${sel.value.topico ? " › " + sel.value.topico : ""}`);
    return { conv, sel, msgs, texto, pwd, abrir, ligar, enviar, hora, titulo, textoChat, cor, ini, novoTopico, pessoas, novaDm, abrirDm,
      novoCanal, novaConversa, criarCanal, comecarConversa };
  },
  template: `
  <div class="caixa chat">
    <aside class="canais">
      <template v-if="conv && conv.ligado">
        <h6 class="chat-h6">Canais<button class="chat-mais" title="Criar canal" aria-label="Criar canal" @click="novoCanal={nome:'',descricao:'',privado:false,pessoas:[]}">+</button></h6>
        <template v-for="c in conv.canais" :key="c.id">
          <div class="chat-canal"><button :class="{ativo: sel && !sel.ids && sel.canal===c.id && !sel.topico}" @click="abrir({canal:c.id, nomeCanal:c.nome})"><span class="ponto" :style="{background:c.cor||'var(--ink-3)'}"></span><span class="txt"># {{ c.nome }}</span><span class="n" v-if="c.por_ler">{{ c.por_ler }}</span></button>
            <button class="chat-mais" :title="'Nova conversa em #' + c.nome" :aria-label="'Nova conversa em ' + c.nome" @click="novaConversa={canal:c.id, nomeCanal:c.nome, topico:'', texto:''}">+</button></div>
          <button v-for="t in c.topicos" :key="t.nome" class="topico" :class="{ativo: sel && sel.canal===c.id && sel.topico===t.nome}" @click="abrir({canal:c.id, nomeCanal:c.nome, topico:t.nome})"><span class="txt">{{ t.nome }}</span><span class="n" v-if="t.por_ler">{{ t.por_ler }}</span></button>
        </template>
        <h6>Mensagens diretas</h6>
        <button v-for="d in conv.directas" :key="d.ids.join()" :class="{ativo: sel && sel.ids && sel.ids.join()===d.ids.join()}" @click="abrir({ids:d.ids, nome:d.nome})"><span class="txt">{{ d.nome }}</span><span class="n" v-if="d.por_ler">{{ d.por_ler }}</span></button>
        <select class="filtro" style="margin:6px 8px;border-style:solid;width:calc(100% - 16px)" v-model="novaDm" @change="abrirDm"><option value="">+ Nova mensagem direta</option><option v-for="p in pessoas" :key="p.id" :value="String(p.id)">{{ p.nome }}</option></select>
      </template>
    </aside>
    <div class="fio" style="grid-column: span 2">
      <div v-if="!conv" class="carregar">A carregar…</div>
      <div v-else-if="!conv.ligado" class="vazio" style="max-width:520px;margin:40px auto;text-align:left"><div class="cartao aviso-cal"><b>Ligar o Stratechna Chat</b>
        <p class="sub">Escreva uma vez a palavra-passe do <b>Chat</b> (não é a da caixa). O Orbit troca-a pela sua chave pessoal do Chat, guarda só a chave (cifrada) e esquece a palavra-passe. Vê aqui só o que vê no Chat.</p>
        <form @submit.prevent="ligar" style="display:flex;gap:8px;flex-wrap:wrap"><input type="password" v-model="pwd" autocomplete="current-password" placeholder="Palavra-passe do Chat" class="filtro" style="border-style:solid;min-width:240px"><button class="btn prim" :disabled="!pwd">Ligar</button></form></div></div>
      <template v-else-if="sel">
        <header><div><h2>{{ titulo }}</h2></div></header>
        <div class="msgs chat-msgs">
          <div v-if="!msgs" class="carregar">A carregar…</div>
          <div v-for="m in msgs||[]" :key="m.id" class="chat-msg" :class="{meu:m.meu}">
            <span class="av" :style="{background:cor(m.quem)}">{{ ini(m.quem) }}</span>
            <div><div class="chat-cab"><b>{{ m.quem }}</b><span class="sub">{{ hora(m.quando) }}</span><span v-if="!sel.topico && m.topico && !sel.ids" class="etq" style="font-size:11px">{{ m.topico }}</span></div>
              <div class="chat-txt" v-html="textoChat(m.texto)"></div></div>
          </div>
        </div>
        <div class="cartao resposta">
          <div class="tabs" v-if="!sel.ids && !sel.topico"><span class="sub">Tópico</span><input v-model="novoTopico" placeholder="geral" style="flex:1;border:0;background:none;font:inherit;color:var(--ink);outline:none"></div>
          <textarea v-model="texto" rows="2" placeholder="Escrever uma mensagem…" @keydown.enter.exact.prevent="enviar"></textarea>
          <footer><span class="sub">↵ envia · ⇧↵ nova linha</span><button class="btn prim sm" @click="enviar" :disabled="!texto.trim()">Enviar</button></footer>
        </div>
      </template>
      <div v-else class="vazio">Escolha um canal, um tópico ou uma conversa.</div>
    </div>
    <div v-if="novoCanal" class="modal-fundo" @click.self="novoCanal=null"><div class="modal" style="max-width:480px"><header><b>Criar canal</b><button class="btn sm" @click="novoCanal=null">Fechar</button></header>
      <form class="reg-form" @submit.prevent="criarCanal">
        <label class="erp-campo"><span>Nome<span class="obrig">*</span></span><input v-model="novoCanal.nome" required autofocus placeholder="ex.: vendas"></label>
        <label class="erp-campo"><span>Descrição</span><input v-model="novoCanal.descricao" placeholder="Para que serve o canal"></label>
        <label style="display:flex;gap:8px;align-items:center"><input type="checkbox" v-model="novoCanal.privado">Privado — só quem for convidado o vê</label>
        <label class="erp-campo"><span>Pessoas (além de si)</span><select multiple v-model="novoCanal.pessoas" style="min-height:120px"><option v-for="p in pessoas" :key="p.id" :value="p.id">{{ p.nome }}</option></select><small class="sub">⌘/Ctrl + clique para escolher várias</small></label>
        <div class="reg-botoes"><button class="btn prim" :disabled="!novoCanal.nome.trim()">Criar canal</button></div></form></div></div>
    <div v-if="novaConversa" class="modal-fundo" @click.self="novaConversa=null"><div class="modal" style="max-width:520px"><header><b>Nova conversa em #{{ novaConversa.nomeCanal }}</b><button class="btn sm" @click="novaConversa=null">Fechar</button></header>
      <form class="reg-form" @submit.prevent="comecarConversa">
        <label class="erp-campo"><span>Tópico<span class="obrig">*</span></span><input v-model="novaConversa.topico" required autofocus maxlength="60" placeholder="ex.: encomenda da Casa X"></label>
        <label class="erp-campo"><span>Mensagem<span class="obrig">*</span></span><textarea v-model="novaConversa.texto" rows="4" required></textarea></label>
        <div class="reg-botoes"><button class="btn prim" :disabled="!novaConversa.topico.trim() || !novaConversa.texto.trim()">Começar conversa</button></div></form></div></div>
  </div>`,
};


// ── Duplicados (H6): encontrar e fundir contactos e empresas ─────────────────────────────────────────
async function apiDup(metodo, args = {}, post = false) {
  const url = `/api/method/orbit.interface.duplicados.${metodo}`;
  const op = { headers: { "X-Frappe-CSRF-Token": window.csrf_token, Accept: "application/json" } };
  let r;
  if (post) { op.method = "POST"; op.headers["Content-Type"] = "application/json"; op.body = JSON.stringify(args); r = await fetch(url, op); }
  else r = await fetch(url + "?" + new URLSearchParams(args), op);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) { let m = "Erro"; try { m = JSON.parse(JSON.parse(j._server_messages)[0]).message; } catch (e) {} toast(String(m).replace(/<[^>]+>/g, "")); throw new Error(m); }
  return j.message;
}
const Duplicados = {
  props: ["tipo"],
  setup(props) {
    const g = ref(null); const escolha = ref({}); const aFundir = ref(null);
    const carregar = async () => {
      g.value = await apiDup("grupos", { tipo: props.tipo });
      const e = {}; g.value.forEach((x, i) => { const p = [...x.registos].sort((a, b) => (b.negocios + b.emails) - (a.negocios + a.emails))[0];
        e[i] = { principal: p.name, juntar: x.registos.filter((r) => r.name !== p.name).map((r) => r.name) }; }); escolha.value = e;
    };
    onMounted(carregar);
    const fundir = async (i) => {
      const e = escolha.value[i]; const outros = e.juntar.filter((n) => n !== e.principal);
      if (!outros.length) { toast("Marque o que se funde no principal"); return; }
      if (!confirm(`Fundir ${outros.length} registo(s) no principal? Os negócios, emails, notas e tarefas passam para ele e os duplicados são apagados. Não se desfaz.`)) return;
      aFundir.value = i;
      try { const r = await apiDup("fundir", { tipo: props.tipo, principal: e.principal, outros: JSON.stringify(outros) }, true); toast(`${r.fundidos} fundido(s)`); carregar(); } finally { aFundir.value = null; }
    };
    const dt = props.tipo === "contactos" ? "Contact" : "CRM Organization";
    return { g, escolha, fundir, aFundir, link, dt };
  },
  template: `
  <div class="pad">
    <div class="ola"><div><div style="font-size:13px"><a :href="'#/'+tipo">← {{ tipo==='contactos' ? 'Contactos' : 'Empresas' }}</a></div>
      <h1>Duplicados — {{ tipo==='contactos' ? 'contactos' : 'empresas' }}</h1>
      <div class="sub">Escolha o registo principal (●) e marque os que se fundem nele (☑). Os negócios, emails, notas e tarefas passam para o principal.</div></div></div>
    <div v-if="!g" class="carregar">A procurar…</div>
    <div v-else-if="!g.length" class="vazio">Sem duplicados.</div>
    <div v-for="(x,i) in g||[]" :key="i" class="cartao" style="margin-bottom:12px">
      <header><h2 style="font-weight:500">{{ x.motivo }}</h2><button class="btn sm prim" @click="fundir(i)" :disabled="aFundir===i">{{ aFundir===i ? 'A fundir…' : 'Fundir' }}</button></header>
      <div class="linha" v-for="r in x.registos" :key="r.name">
        <input type="radio" :name="'p'+i" :value="r.name" v-model="escolha[i].principal" title="Registo principal">
        <input type="checkbox" :value="r.name" v-model="escolha[i].juntar" :disabled="escolha[i].principal===r.name" title="Fundir no principal">
        <div class="cresce"><a :href="link(dt,r.name)" target="_blank">{{ r.titulo }}</a><small>{{ r.sub }} · {{ r.negocios }} negócios · {{ r.emails }} emails</small></div>
        <span class="etq verde" v-if="escolha[i].principal===r.name">Principal</span>
      </div>
    </div>
  </div>`,
};


// ── Importar CSV/Excel (H8) ───────────────────────────────────────────────────────────────────────────
const Importar = {
  props: ["objeto"], emits: ["fechar", "feito"],
  setup(props, { emit }) {
    const passo = ref(1); const an = ref(null); const mapa = ref({}); const modo = ref("atualizar"); const res = ref(null); const ocupado = ref(false); const marcador = ref("");
    const POST = async (metodo, args) => {
      const r = await fetch(`/api/method/orbit.interface.importar.${metodo}`, { method: "POST", headers: { "X-Frappe-CSRF-Token": window.csrf_token, "Content-Type": "application/json", Accept: "application/json" }, body: JSON.stringify(args) });
      const j = await r.json().catch(() => ({})); if (!r.ok) { let m = "Erro"; try { m = JSON.parse(JSON.parse(j._server_messages)[0]).message; } catch (e) {} toast(m); throw new Error(m); } return j.message; };
    const enviar = async (ev) => {
      const fd = new FormData(); const f = ev.target.files[0]; if (!f) return; fd.append("ficheiro", f); fd.append("objeto", props.objeto); ocupado.value = true;
      try { const r = await fetch("/api/method/orbit.interface.importar.analisar", { method: "POST", body: fd, headers: { "X-Frappe-CSRF-Token": window.csrf_token } });
        const j = await r.json().catch(() => ({})); if (!r.ok) { let m = "Erro"; try { m = JSON.parse(JSON.parse(j._server_messages)[0]).message; } catch (e) {} toast(m); return; }
        an.value = j.message; mapa.value = { ...an.value.sugestao }; passo.value = 2; } finally { ocupado.value = false; } };
    const correr = async (simular) => { ocupado.value = true;
      try { res.value = await POST("executar", { codigo: an.value.codigo, mapeamento: JSON.stringify(mapa.value), modo: modo.value, simular: simular ? 1 : 0, marcador: marcador.value || null });
        passo.value = simular ? 3 : 4; if (!simular) emit("feito"); } finally { ocupado.value = false; } };
    const usados = computed(() => Object.values(mapa.value).filter(Boolean));
    return { passo, an, mapa, modo, res, ocupado, enviar, correr, usados, TITULOS, marcador };
  },
  template: `<div class="modal-fundo" @click.self="$emit('fechar')"><div class="modal" style="max-width:860px">
    <header><b>Importar {{ TITULOS[objeto].toLowerCase() }}</b><button class="btn sm" @click="$emit('fechar')">Fechar</button></header>
    <div class="corpo-email">
      <template v-if="passo===1"><p>Escolha um ficheiro <b>CSV</b> (separado por «;» ou «,») ou <b>Excel (.xlsx)</b>, com os nomes das colunas na 1.ª linha. Até 5 000 linhas.</p>
        <input type="file" accept=".csv,.txt,.xlsx" @change="enviar" :disabled="ocupado"><p v-if="ocupado" class="sub">A ler…</p></template>
      <template v-if="passo===2 && an"><p class="sub">{{ an.importaveis }} linhas. Confirme a que campo vai cada coluna (as vazias não se importam).</p>
        <div class="tabela-wrap" style="margin:0;max-height:46vh"><table><thead><tr><th>Coluna do ficheiro</th><th>Exemplos</th><th>Campo no Orbit</th></tr></thead><tbody>
          <tr v-for="(h,i) in an.cabecalhos" :key="i"><td><b>{{ h }}</b></td><td class="sub" style="white-space:normal;max-width:260px">{{ an.amostra.map(l=>l[i]).filter(Boolean).slice(0,3).join(' · ') }}</td>
            <td><select v-model="mapa[i]" class="btn sm"><option value="">— não importar —</option><option v-for="c in an.campos" :key="c.campo" :value="c.campo" :disabled="usados.includes(c.campo) && mapa[i]!==c.campo">{{ c.rotulo }}</option></select></td></tr>
        </tbody></table></div>
        <div style="display:flex;gap:14px;align-items:center;margin-top:12px;flex-wrap:wrap"><span class="sub">Se já existir (mesmo email; empresas: mesmo NIPC ou nome):</span>
          <label><input type="radio" value="atualizar" v-model="modo"> atualizar</label><label><input type="radio" value="ignorar" v-model="modo"> ignorar</label>
          <label v-if="objeto!=='negocios'" style="display:flex;gap:6px;align-items:center">Marcador <input class="ed-campo" v-model="marcador" placeholder="(opcional)" style="width:160px"></label>
          <button class="btn prim" style="margin-left:auto" @click="correr(true)" :disabled="ocupado || !usados.length">{{ ocupado ? 'A simular…' : 'Simular' }}</button></div></template>
      <template v-if="(passo===3 || passo===4) && res">
        <p><b>{{ res.simulado ? 'Simulação (nada foi gravado)' : 'Importação feita' }}:</b> {{ res.novos }} novos · {{ res.atualizados }} atualizados · {{ res.ignorados }} ignorados · {{ res.n_erros }} com erro</p>
        <div v-if="res.erros.length" class="tabela-wrap" style="margin:0;max-height:36vh"><table><thead><tr><th>Linha</th><th>Erro</th></tr></thead><tbody><tr v-for="e in res.erros" :key="e.linha"><td>{{ e.linha }}</td><td style="white-space:normal">{{ e.erro }}</td></tr></tbody></table></div>
        <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px">
          <template v-if="passo===3"><button class="btn" @click="passo=2">Voltar à correspondência</button><button class="btn prim" @click="correr(false)" :disabled="ocupado || !(res.novos+res.atualizados)">{{ ocupado ? 'A importar…' : 'Importar ' + (res.novos+res.atualizados) + ' registos' }}</button></template>
          <button v-else class="btn prim" @click="$emit('fechar')">Fechar</button></div></template>
    </div></div></div>`,
};


// ── Compositor com modelos (H9) e email novo a partir da ficha ─────────────────────────────────────────
const Compositor = {
  props: ["modelValue", "doctype", "name", "para", "linhas"], emits: ["update:modelValue", "assunto", "enviar"],
  setup(props, { emit }) {
    const modelos = ref(null); const area = ref(null);
    const abrir = async () => { if (!modelos.value) modelos.value = await api("modelos_email"); };
    const inserir = async (ev) => {
      const m = ev.target.value; ev.target.value = ""; if (!m) return;
      const r = await api("aplicar_modelo", { modelo: m, doctype: props.doctype || "", name: props.name || "", para: props.para || "" });
      const el = area.value; const v = props.modelValue || ""; const pos = el ? el.selectionStart : v.length;
      emit("update:modelValue", v.slice(0, pos) + r.texto + v.slice(pos)); if (r.assunto) emit("assunto", r.assunto);
    };
    return { modelos, area, abrir, inserir };
  },
  template: `<div class="compositor">
    <div class="compositor-barra"><select class="btn sm" @focus="abrir" @mousedown="abrir" @change="inserir"><option value="">Modelos ▾</option><option v-for="m in modelos||[]" :key="m.name" :value="m.name">{{ m.name }}</option></select>
      <span class="sub" style="font-size:12px">os campos ({{ '{' }}{{ '{' }} nome {{ '}' }}{{ '}' }}, empresa…) preenchem-se sozinhos</span></div>
    <textarea ref="area" :value="modelValue" @input="$emit('update:modelValue', $event.target.value)" :rows="linhas || 6" placeholder="Escrever…" @keydown.meta.enter="$emit('enviar')" @keydown.ctrl.enter="$emit('enviar')"></textarea>
  </div>`,
};
const NovoEmail = {
  components: { Compositor }, props: ["doctype", "name", "para", "resposta"], emits: ["fechar", "enviado"],
  setup(props, { emit }) {
    const rr = props.resposta || {};
    const caixas = ref(null); const f = ref({ conta: "", para: rr.para || props.para || "", cc: rr.cc || "", bcc: "", assunto: rr.assunto || "", texto: "", html: rr.citacao || "", rico: !!props.resposta, agendar: "", anexos: [] }); const aEnviar = ref(false);
    const verMais = ref(!!rr.cc); const anexoIn = ref(null);
    const juntarAnexos = async (ev) => { for (const fi of [...(ev.target.files || [])]) {
        const fd = new FormData(); fd.append("file", fi, fi.name); fd.append("is_private", 1); fd.append("doctype", props.doctype); fd.append("docname", props.name);
        const r = await fetch("/api/method/upload_file", { method: "POST", body: fd, headers: { "X-Frappe-CSRF-Token": window.csrf_token, Accept: "application/json" } });
        const j = await r.json().catch(() => ({})); if (j.message) f.value.anexos.push({ id: j.message.name, nome: fi.name }); else toast("Não foi possível anexar " + fi.name); }
      ev.target.value = ""; };
    onMounted(async () => { caixas.value = await api("minhas_caixas"); f.value.conta = (caixas.value[0] || {}).conta || ""; });
    const esc = (t) => t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    const enviar = async () => {
      const temTexto = f.value.rico ? String(f.value.html || "").replace(/<[^>]+>/g, "").trim() : f.value.texto.trim();
      if (!f.value.conta || !f.value.para || !f.value.assunto || !temTexto) { toast("Falta a caixa, o destinatário, o assunto ou o texto"); return; }
      aEnviar.value = true;
      try { const html = f.value.rico ? f.value.html : f.value.texto.trim().split(/\n{2,}/).map((p) => "<p>" + esc(p).replace(/\n/g, "<br>") + "</p>").join("");
        const r = await api("actividades.email_enviar", { doctype: props.doctype, name: props.name, conta: f.value.conta, para: f.value.para, cc: f.value.cc, bcc: f.value.bcc, assunto: f.value.assunto, html,
          anexos: f.value.anexos.length ? JSON.stringify(f.value.anexos.map((x) => x.id)) : null, agendar: f.value.agendar ? f.value.agendar.replace("T", " ") + ":00" : null, responder_a: rr.responder_a || null }, true);
        toast(r.agendado ? "Email agendado para " + data(r.agendado) : "Email enviado"); emit("enviado"); emit("fechar"); } finally { aEnviar.value = false; }
    };
    const passarRico = () => { if (!f.value.rico) { f.value.html = f.value.texto.trim().split(/\n{2,}/).filter(Boolean).map((p) => "<p>" + esc(p).replace(/\n/g, "<br>") + "</p>").join("") + (f.value.html || ""); f.value.rico = true; } };
    return { caixas, f, aEnviar, enviar, verMais, anexoIn, juntarAnexos, passarRico };
  },
  template: `<div class="modal-fundo" @click.self="$emit('fechar')"><div class="modal" style="max-width:680px"><header><b>{{ resposta ? 'Responder' : 'Novo email' }}</b><button class="btn sm" @click="$emit('fechar')">Fechar</button></header>
    <div class="corpo-email form-cal">
      <div v-if="caixas && !caixas.length" class="aviso" style="margin:0">Ainda não há caixas ligadas ao CRM de onde possa escrever (ligam-se no portal, em Stratechna Orbit).</div>
      <label>De<select v-model="f.conta"><option v-for="c in caixas||[]" :key="c.conta" :value="c.conta">{{ c.email }}{{ c.privada ? ' (a sua caixa)' : ' (equipa)' }}</option></select></label>
      <label>Para<input v-model="f.para"></label>
      <a v-if="!verMais" href="javascript:void 0" class="sub" style="font-size:12px" @click="verMais=true">+ Cc / Bcc</a>
      <div v-else class="linha3" style="grid-template-columns:1fr 1fr"><label>Cc<input v-model="f.cc"></label><label>Bcc<input v-model="f.bcc"></label></div>
      <label>Assunto<input v-model="f.assunto"></label>
      <Compositor v-if="!f.rico" v-model="f.texto" :doctype="doctype" :name="name" :para="f.para" :linhas="9" @assunto="(a)=>{ if(!f.assunto) f.assunto=a }" @enviar="enviar"/>
      <EditorRico v-else v-model="f.html"/>
      <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
        <button v-if="!f.rico" type="button" class="btn sm" @click="passarRico">Aa Formatação</button>
        <button type="button" class="btn sm" @click="anexoIn.click()">📎 Anexar</button><input ref="anexoIn" type="file" multiple style="display:none" @change="juntarAnexos">
        <span v-for="(x,k) in f.anexos" :key="x.id" class="reg-chip">{{ x.nome }}<button type="button" @click="f.anexos.splice(k,1)">×</button></span>
        <label class="sub" style="font-size:12px;display:flex;gap:6px;align-items:center;margin-left:auto">Agendar <input type="datetime-local" v-model="f.agendar" style="width:auto"></label>
      </div>
      <div style="display:flex;justify-content:space-between;align-items:center"><span class="sub" style="font-size:12px">Fica nos Enviados da caixa e na cronologia · sabe-se quando é aberto</span><button class="btn prim" @click="enviar" :disabled="aEnviar">{{ aEnviar ? 'A enviar…' : 'Enviar' }}</button></div>
    </div></div></div>`,
};


// ── Fila de tarefas (H10): uma de cada vez, com o cliente ao lado ─────────────────────────────────────
const Fila = {
  components: { NovoEmail, Icone },
  setup() {
    const lista = ref(null); const i = ref(0); const d = ref(null); const nota = ref(""); const email = ref(false); const feitas = ref(0); const ocupado = ref(false);
    const carregar = async () => { d.value = null; nota.value = ""; if (lista.value && i.value < lista.value.length) { const t = lista.value[i.value]; d.value = await apiT("detalhe", { tipo: t.tipo, nome: t.id }); } };
    onMounted(async () => { lista.value = await apiT("fila"); carregar(); });
    const seguinte = () => { i.value++; carregar(); };
    const concluir = async () => { ocupado.value = true; try { await apiT("concluir", { tipo: d.value.tipo, nome: d.value.id }, true); feitas.value++; seguinte(); } finally { ocupado.value = false; } };
    const adiar = async (dias) => { await apiT("adiar", { tipo: d.value.tipo, nome: d.value.id, dias }, true); toast(dias === 1 ? "Passou para amanhã" : "Passou para daqui a uma semana"); seguinte(); };
    const gravarNota = async () => { if (!nota.value.trim() || !d.value.ref) return; await api("nota", { doctype: d.value.ref[0], name: d.value.ref[1], conteudo: nota.value }, true); nota.value = ""; toast("Nota gravada"); };
    const ic = (t) => IC_EVENTO[t] || IC_EVENTO.nota;
    return { lista, i, d, nota, email, feitas, ocupado, seguinte, concluir, adiar, gravarNota, link, data, ic };
  },
  template: `
  <div class="pad">
    <div class="ola"><div><div style="font-size:13px"><a href="#/tarefas">← Tarefas</a></div><h1>Fila de tarefas</h1>
      <div class="sub" v-if="lista">{{ lista.length ? (Math.min(i+1, lista.length) + ' de ' + lista.length + ' · ' + feitas + ' concluídas') : 'Sem tarefas para hoje.' }}</div></div></div>
    <div v-if="lista && lista.length" class="barra" style="margin:-8px 0 16px"><i :style="{width: (100*i/lista.length)+'%'}"></i></div>
    <div v-if="!lista" class="carregar">A carregar…</div>
    <div v-else-if="i >= lista.length" class="vazio" style="font-size:16px">🎉 Fila terminada — {{ feitas }} tarefas concluídas.<br><a href="#/tarefas">Voltar às tarefas</a></div>
    <div v-else-if="!d" class="carregar">A carregar…</div>
    <div v-else class="fila">
      <div class="cartao" style="padding:18px">
        <div class="sub" style="font-size:12px">{{ d.tipo==='crm' ? 'Tarefa do CRM' : 'Tarefa do projeto ' + (d.projeto_nome||'') }} · {{ d.data ? data(d.data) : 'sem data' }}<template v-if="d.prioridade"> · {{ d.prioridade }}</template></div>
        <h2 style="font-size:20px;margin:6px 0 10px">{{ d.titulo }}</h2>
        <div v-if="d.descricao" class="chat-txt sub" v-html="d.descricao"></div>
        <div class="fila-acoes">
          <button class="btn prim" @click="concluir" :disabled="ocupado">✓ Concluir e seguinte</button>
          <button class="btn" @click="seguinte">Saltar</button>
          <button class="btn" @click="adiar(1)">Amanhã</button>
          <button class="btn" @click="adiar(7)">Daqui a uma semana</button>
        </div>
      </div>
      <div class="cartao" style="padding:16px" v-if="d.registo">
        <div style="display:flex;justify-content:space-between;gap:10px;align-items:flex-start"><div><b style="font-size:16px">{{ d.registo.titulo }}</b><div class="sub">{{ d.registo.sub }}</div></div>
          <a class="btn sm" :href="link(d.ref[0], d.ref[1])" target="_blank">Abrir ficha</a></div>
        <div class="fila-acoes" style="margin:12px 0">
          <a v-if="d.registo.telefone" class="btn sm" :href="'tel:'+d.registo.telefone">📞 {{ d.registo.telefone }}</a>
          <button v-if="d.registo.email" class="btn sm" @click="email=true">✉ Email</button></div>
        <div class="compor cartao" style="margin-bottom:12px"><textarea v-model="nota" rows="2" placeholder="Nota rápida sobre este cliente…"></textarea><button class="btn sm prim" @click="gravarNota" :disabled="!nota.trim()">Gravar</button></div>
        <div class="mes" style="margin-top:4px">Últimas interações</div>
        <div v-if="!d.registo.recentes.length" class="sub">—</div>
        <div v-for="r in d.registo.recentes" :key="r.tipo+r.id" class="evento" style="margin-bottom:6px"><div class="ic" :style="{background:ic(r.tipo)[1],color:ic(r.tipo)[2]}"><Icone :n="ic(r.tipo)[0]"/></div>
          <div><b style="font-size:13px">{{ r.titulo }}</b><div class="sub" style="font-size:12px">{{ data(r.data) }}</div></div></div>
      </div>
      <NovoEmail v-if="email" :doctype="d.ref[0]" :name="d.ref[1]" :para="d.registo.email" @fechar="email=false"/>
    </div>
  </div>`,
};
// ── Sino (avisos do Frappe: tarefas, menções, atribuições) ────────────────────────────────────────────
const Sino = {
  components: { Icone },
  setup() {
    const d = ref({ por_ler: 0, itens: [] }); const aberto = ref(false);
    const carregar = async () => { try { d.value = await apiT("notificacoes"); } catch (e) {} };
    onMounted(() => { carregar(); setInterval(() => { if (!document.hidden) carregar(); }, 60000); });
    const abrir = async () => { aberto.value = !aberto.value; if (aberto.value && d.value.por_ler) { await apiT("marcar_lidas", {}, true); setTimeout(carregar, 1500); } };
    const ir = (n) => { aberto.value = false; if (["Contact", "CRM Deal", "CRM Lead", "CRM Organization"].includes(n.document_type)) location.hash = link(n.document_type, n.document_name);
      else if (n.document_type === "HD Ticket") location.href = "/orbit?app=desk#/ticket/" + encodeURIComponent(n.document_name);
      else if (n.document_type === "Communication") location.hash = "#/caixa"; else if (n.document_type === "CRM Task") location.hash = "#/tarefas"; };
    // 23-11-2026: avisos no telemóvel/computador (Web Push). O iPhone só deixa com o Orbit gravado no ecrã principal.
    const push = ref({ suporta: "serviceWorker" in navigator && "PushManager" in window && "Notification" in window, ligado: false, aLigar: false });
    const iosSemApp = /iPhone|iPad/.test(navigator.userAgent) && !(window.navigator.standalone || matchMedia("(display-mode: standalone)").matches);
    const b64 = (s) => { const p = "=".repeat((4 - s.length % 4) % 4); const r = atob((s + p).replace(/-/g, "+").replace(/_/g, "/")); return Uint8Array.from([...r].map((c) => c.charCodeAt(0))); };
    const registo = async () => push.value.suporta ? navigator.serviceWorker.register("/api/method/orbit.interface.push.sw", { scope: "/orbit" }) : null;
    onMounted(async () => { try { const reg = await registo(); const sub = reg && await reg.pushManager.getSubscription(); push.value.ligado = !!sub && Notification.permission === "granted"; } catch (e) {} });
    const ligarAvisos = async () => {
      push.value.aLigar = true;
      try {
        const perm = await Notification.requestPermission();
        if (perm !== "granted") { toast("Os avisos ficaram bloqueados neste aparelho — permita-os nas definições do browser."); return; }
        const reg = await registo(); await navigator.serviceWorker.ready;
        const { publica } = await apiConvPush("chave");
        const sub = (await reg.pushManager.getSubscription()) || await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64(publica) });
        await apiConvPush("subscrever", { sub: JSON.stringify(sub) }, true);
        push.value.ligado = true; toast("Avisos ligados neste aparelho");
      } catch (e) { toast("Não foi possível ligar os avisos: " + (e.message || e)); } finally { push.value.aLigar = false; }
    };
    const desligarAvisos = async () => {
      const reg = await navigator.serviceWorker.getRegistration("/orbit"); const sub = reg && await reg.pushManager.getSubscription();
      if (sub) { await apiConvPush("retirar", { endpoint: sub.endpoint }, true); await sub.unsubscribe(); }
      push.value.ligado = false; toast("Avisos desligados neste aparelho");
    };
    return { d, aberto, abrir, ir, data, push, iosSemApp, ligarAvisos, desligarAvisos };
  },
  template: `<span class="sino"><button class="icone-btn" @click="abrir" title="Avisos"><Icone n="sino"/><span v-if="d.por_ler" class="sino-n">{{ d.por_ler }}</span></button>
    <div v-if="aberto" class="cartao sino-lista"><header style="padding:10px 14px;display:flex;justify-content:space-between;align-items:center;gap:8px"><b>Avisos</b>
        <template v-if="push.suporta && !iosSemApp"><button v-if="!push.ligado" class="btn sm" :disabled="push.aLigar" @click="ligarAvisos">Receber avisos neste aparelho</button>
          <button v-else class="sub" style="all:unset;cursor:pointer;font-size:12px" @click="desligarAvisos" title="Deixar de receber avisos neste aparelho">🔔 ligados aqui</button></template>
        <span v-else-if="iosSemApp" class="sub" style="font-size:11px;max-width:200px;text-align:right">No iPhone: Partilhar › Adicionar ao ecrã principal, e abrir a partir do ícone para ligar os avisos.</span></header>
      <div v-if="!d.itens.length" class="vazio">Sem avisos.</div>
      <div v-for="n in d.itens" :key="n.name" class="linha" style="cursor:pointer" :style="n.read?{}:{background:'var(--azul-bg)'}" @click="ir(n)"><div class="cresce">{{ n.subject }}<small>{{ n.email_content }} · {{ data(n.creation) }}</small></div></div>
    </div></span>`,
};

// ── Ecrãs ────────────────────────────────────────────────────────────────────────────────────────────
const Inicio = {
  components: { Icone },
  props: ["ctx"],
  setup(props) {
    const d = ref(null);
    const carregar = async () => (d.value = await api("inicio"));
    onMounted(carregar);
    const feita = async (t) => { await api("tarefa_feita", { nome: t.name }, true); carregar(); };
    const hora = (x) => new Date(String(x).replace(" ", "T")).toLocaleTimeString("pt-PT", { hour: "2-digit", minute: "2-digit" });
    const hoje = new Date().toLocaleDateString("pt-PT", { weekday: "long", day: "numeric", month: "long" });
    const saud = new Date().getHours() < 13 ? "Bom dia" : new Date().getHours() < 20 ? "Boa tarde" : "Boa noite";
    return { d, feita, hora, hoje, saud, eur, data, link };
  },
  template: `
  <div class="pad" v-if="d">
    <div class="ola"><div><h1>{{ saud }}, {{ (ctx.nome||'').split(' ')[0] }}</h1>
      <div class="sub">{{ hoje }} · {{ d.tarefas.length }} tarefas por fazer, {{ d.eventos.length }} reuniões hoje e amanhã</div></div></div>
    <div class="kpis">
      <div class="cartao kpi"><span class="sub">Negócios abertos</span><b>{{ d.kpis.abertos }} · {{ eur(d.kpis.abertos_valor) }}</b></div>
      <div class="cartao kpi"><span class="sub">Ganhos este mês</span><b>{{ eur(d.kpis.ganhos_valor) }}</b><span class="var">{{ d.kpis.ganhos }} negócios</span></div>
      <div class="cartao kpi"><span class="sub">Tickets em aberto</span><b>{{ ctx.contadores.tickets }}</b></div>
      <div class="cartao kpi"><span class="sub">Tarefas atrasadas</span><b>{{ d.kpis.tarefas_atrasadas }}</b></div>
    </div>
    <div class="grelha2">
      <div class="cartao"><header><h2>As minhas tarefas</h2></header>
        <div v-if="!d.tarefas.length" class="vazio">Sem tarefas por fazer.</div>
        <div class="linha" v-for="t in d.tarefas" :key="t.name">
          <span class="chk" @click="feita(t)" title="Marcar como feita" style="cursor:pointer"></span>
          <div class="cresce">{{ t.title }}<small><a v-if="t.reference_docname" :href="link(t.reference_doctype,t.reference_docname)">{{ t.titulo_ref }}</a></small></div>
          <span class="etq ambar" v-if="t.atrasada">Atrasada</span><span class="etq" v-else-if="t.hoje">Hoje</span>
          <span class="sub" v-else-if="t.due_date">{{ data(t.due_date,false) }}</span>
        </div>
      </div>
      <div class="cartao"><header><h2>Agenda</h2></header>
        <div v-if="!d.eventos.length" class="vazio">Nada marcado para hoje e amanhã.</div>
        <div class="linha" v-for="e in d.eventos" :key="e.name"><span class="hora">{{ hora(e.starts_on) }}</span>
          <div class="cresce">{{ e.subject }}<small>{{ data(e.starts_on,false) }}<span v-if="e.location"> · {{ e.location }}</span></small></div></div>
        <header style="border-top:1px solid var(--line)"><h2>Negócios parados</h2><span class="sub">sem atividade há 14+ dias</span></header>
        <div v-if="!d.parados.length" class="vazio">Nenhum.</div>
        <a class="linha" v-for="n in d.parados" :key="n.name" :href="link('CRM Deal',n.name)" style="text-decoration:none;color:inherit">
          <div class="cresce">{{ n.titulo }}<small>{{ n.estado }} · {{ n.dias }} dias</small></div><b>{{ eur(n.valor) }}</b></a>
      </div>
    </div>
  </div>
  <div v-else class="carregar">A carregar…</div>`,
};

const COLUNAS = {
  contactos: [["full_name", "Nome"], ["company_name", "Empresa"], ["email_id", "Email"], ["mobile_no", "Telemóvel"], ["orbit_ciclo", "Fase"], ["orbit_responsavel_nome", "Responsável"], ["orbit_ultima_atividade", "Última atividade"]],
  empresas: [["organization_name", "Empresa"], ["website", "Site"], ["telefone", "Telefone"], ["orbit_ciclo", "Fase"], ["orbit_responsavel_nome", "Responsável"], ["orbit_ultima_atividade", "Última atividade"]],
  negocios: [["titulo", "Negócio"], ["organization", "Empresa"], ["estado", "Fase"], ["deal_value", "Valor"], ["expected_closure_date", "Fecho previsto"], ["deal_owner_nome", "Responsável"], ["orbit_ultima_atividade", "Última atividade"]],
  leads: [["lead_name", "Nome"], ["organization", "Empresa"], ["email", "Email"], ["estado", "Estado"], ["source", "Origem"], ["lead_owner_nome", "Responsável"], ["orbit_ultima_atividade", "Última atividade"]],
};
const TITULOS = { contactos: "Contactos", empresas: "Empresas", negocios: "Negócios", leads: "Leads" };
const VISTAS = { contactos: [["todos", "Todos"], ["meus", "Os meus"], ["parados", "Sem atividade há 30 dias"]],
  empresas: [["todos", "Todas"], ["meus", "As minhas"], ["parados", "Sem atividade há 30 dias"]],
  negocios: [["abertos", "Em curso"], ["todos", "Todos"], ["meus", "Os meus"], ["parados", "Parados há 30 dias"]],
  leads: [["todos", "Por converter"], ["meus", "As minhas"], ["parados", "Sem atividade há 30 dias"]] };
const DT_LISTA = { contactos: "Contact", empresas: "CRM Organization", negocios: "CRM Deal", leads: "CRM Lead" };

async function apiVis(metodo, args = {}, post = false) {
  const url = `/api/method/orbit.interface.vistas.${metodo}`;
  const op = { headers: { "X-Frappe-CSRF-Token": window.csrf_token, Accept: "application/json" } };
  let r;
  if (post) { op.method = "POST"; op.headers["Content-Type"] = "application/json"; op.body = JSON.stringify(args); r = await fetch(url, op); }
  else r = await fetch(url + "?" + new URLSearchParams(args), op);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) { let m = "Erro"; try { m = JSON.parse(JSON.parse(j._server_messages)[0]).message; } catch (e) {} toast(String(m).replace(/<[^>]+>/g, "")); throw new Error(m); }
  return j.message;
}
const OPS_TIPO = { user: [["igual", "é"], ["diferente", "não é"], ["vazio", "está vazio"], ["preenchido", "está preenchido"]],
  select: [["igual", "é"], ["diferente", "não é"], ["vazio", "está vazio"], ["preenchido", "está preenchido"]],
  link: [["igual", "é"], ["diferente", "não é"], ["vazio", "está vazio"], ["preenchido", "está preenchido"]],
  texto: [["contem", "contém"], ["igual", "é"], ["vazio", "está vazio"], ["preenchido", "está preenchido"]],
  numero: [["maior", "maior que"], ["menor", "menor que"], ["igual", "é"]],
  data: [["depois", "depois de"], ["antes", "antes de"], ["vazio", "está vazio"]] };
const CAMPOS_USER = ["orbit_responsavel", "deal_owner", "lead_owner"];
const CAMPOS_DATA = ["orbit_ultima_atividade", "creation", "expected_closure_date", "ultimo_email"];
const Lista = {
  components: { Importar },
  props: ["objeto"],
  setup(props) {
    const importar = ref(false);
    const vista = ref(VISTAS[props.objeto][0][0]); const q = ref(""); const linhas = ref([]); const total = ref(0); const mais = ref(false);
    // 23-11-2026: separador da marca escolhido, por lista, neste navegador
    const chaveMarca = "orbit.marca." + props.objeto; let m0 = ""; try { m0 = localStorage.getItem(chaveMarca) || ""; } catch (e) {}
    const marca = ref(m0);
    const escolherMarca = (m) => { marca.value = m; try { localStorage.setItem(chaveMarca, m); } catch (e) {} recarregar(); };
    const pagina = ref(0); const ordem = ref("modified desc"); const a = ref(false);
    const meta = ref(null); const salvas = ref([]); const salvaAtiva = ref(null);
    const filtros = ref([]); const colunas = ref(COLUNAS[props.objeto].map((c) => ({ campo: c[0] === "estado" ? "status" : c[0].replace(/_nome$/, ""), rotulo: c[1] })));
    const novoF = ref(null); const verCols = ref(false); const sel = ref([]); const massa = ref({ acao: "", valor: "" });
    let tq;
    const carregar = async (junta = false) => {
      a.value = true;
      const r = await api("lista", { objeto: props.objeto, vista: vista.value, q: q.value, pagina: pagina.value, ordem: ordem.value,
        filtros: JSON.stringify(filtros.value), colunas: JSON.stringify(colunas.value.map((c) => c.campo)), marca: marca.value });
      linhas.value = junta ? linhas.value.concat(r.linhas) : r.linhas; total.value = r.total; mais.value = r.mais; a.value = false;
      if (!junta) sel.value = [];
    };
    const recarregar = () => { pagina.value = 0; carregar(); };
    const carregarSalvas = async () => (salvas.value = await apiVis("vistas", { objeto: props.objeto }));
    onMounted(async () => { meta.value = await apiVis("metadados", { objeto: props.objeto });
      if (marca.value && !(meta.value?.marcas || []).includes(marca.value)) marca.value = "";
      // 25-11-2026: vindo dos Marcadores do Marketing — a lista abre filtrada por esse marcador
      try { const mk = JSON.parse(sessionStorage.getItem("orbit.crm.marcador") || "null"); if (mk) { sessionStorage.removeItem("orbit.crm.marcador"); filtros.value = [["_user_tags", "contem", mk.m]]; } } catch (e) {}
      carregarSalvas(); carregar(); });
    watch(q, () => { clearTimeout(tq); tq = setTimeout(recarregar, 300); });
    const escolherFixa = (v) => { salvaAtiva.value = null; vista.value = v; filtros.value = []; recarregar(); };
    const escolherSalva = (v) => { salvaAtiva.value = v.nome + (v.partilhada ? "*" : ""); const c = v.config || {}; vista.value = c.base || "todos";
      filtros.value = c.filtros || []; if (c.colunas && c.colunas.length) colunas.value = c.colunas.map((x) => ({ campo: x, rotulo: (meta.value?.colunas.find((m) => m.campo === x) || {}).rotulo || x }));
      if (c.ordem) ordem.value = c.ordem; recarregar(); };
    const apagarSalva = async (v) => { if (!confirm(`Apagar a vista «${v.nome}»?`)) return; await apiVis("apagar_vista", { objeto: props.objeto, nome: v.nome, partilhada: v.partilhada ? 1 : 0 }, true); carregarSalvas(); };
    const guardar = async () => {
      const nome = prompt("Nome da vista:"); if (!nome) return;
      const partilhar = meta.value?.pode_partilhar && confirm("Partilhar esta vista com a equipa? (OK = partilhar, Cancelar = só para mim)");
      await apiVis("guardar_vista", { objeto: props.objeto, nome, partilhada: partilhar ? 1 : 0,
        config: JSON.stringify({ filtros: filtros.value, colunas: colunas.value.map((c) => c.campo), ordem: ordem.value, base: vista.value }) }, true);
      toast("Vista guardada"); await carregarSalvas(); salvaAtiva.value = nome + (partilhar ? "*" : "");
    };
    const campoMeta = (c) => (meta.value?.filtraveis || []).find((x) => x.campo === c) || {};
    const rotuloFiltro = (f) => { const m = campoMeta(f[0]); const op = (OPS_TIPO[m.tipo] || []).find((o) => o[0] === f[1]); const val = (m.opcoes || []).find((o) => o.v === f[2]);
      return `${m.rotulo || f[0]} ${op ? op[1] : f[1]}${["vazio", "preenchido"].includes(f[1]) ? "" : " " + (val ? val.r : (f[2] || ""))}`; };
    const juntarFiltro = () => { const f = novoF.value; if (!f.campo || !f.op) return; filtros.value = [...filtros.value, [f.campo, f.op, f.valor || ""]]; novoF.value = null; recarregar(); };
    const tirarFiltro = (i) => { filtros.value = filtros.value.filter((_, k) => k !== i); recarregar(); };
    const alternarCol = (c) => { const i = colunas.value.findIndex((x) => x.campo === c.campo);
      if (i >= 0) { if (colunas.value.length > 1) colunas.value.splice(i, 1); } else colunas.value.push({ campo: c.campo, rotulo: c.rotulo }); recarregar(); };
    const ordenar = (c) => { ordem.value = ordem.value === `${c} desc` ? `${c} asc` : `${c} desc`; recarregar(); };
    const valor = (l, c) => CAMPOS_USER.includes(c) ? (l[c + "_nome"] || l[c] || "") : c === "status" ? (l.estado || l.status) : c === "deal_value" ? eur(l[c]) : CAMPOS_DATA.includes(c) ? data(l[c], false) : (l[c] ?? "");
    const abrir = (l) => (location.hash = link(DT_LISTA[props.objeto], l.name));
    const todos = computed({ get: () => linhas.value.length && sel.value.length === linhas.value.length, set: (v) => (sel.value = v ? linhas.value.map((l) => l.name) : []) });
    const opsMassa = computed(() => { const o = [["responsavel", "Atribuir responsável"], ["marcar", "Pôr marcador…"], ["desmarcar", "Tirar marcador…"]]; if (["negocios", "leads"].includes(props.objeto)) o.push(["estado", props.objeto === "negocios" ? "Mudar a fase" : "Mudar o estado"]);
      if (["contactos", "empresas"].includes(props.objeto)) o.push(["ciclo", "Mudar a fase do ciclo de vida"]); if (meta.value?.pode_apagar) o.push(["apagar", "Apagar"]); return o; });
    const opcoesMassa = computed(() => { const m = massa.value.acao; const campo = m === "responsavel" ? (props.objeto === "negocios" ? "deal_owner" : props.objeto === "leads" ? "lead_owner" : "orbit_responsavel") : m === "estado" ? "status" : m === "ciclo" ? "orbit_ciclo" : null;
      return campo ? (campoMeta(campo).opcoes || []) : []; });
    const aplicarMassa = async () => {
      const m = massa.value; if (!m.acao) return;
      if (m.acao === "apagar" && !confirm(`Apagar ${sel.value.length} registo(s)? Não se desfaz.`)) return;
      if (["marcar", "desmarcar"].includes(m.acao)) { if (!String(m.valor || "").trim()) { toast("Escreva o marcador"); return; }
        const r = await apiSeg("marcar", { doctype: DT_LISTA[props.objeto], nomes: JSON.stringify(sel.value), marcador: m.valor, tirar: m.acao === "desmarcar" ? 1 : 0 }, true);
        toast(`${r.mudados} registo(s) ${m.acao === "marcar" ? "marcados" : "desmarcados"} com «${r.marcador}»`); massa.value = { acao: "", valor: "" }; carregar(); return; }
      // lote 2: passar a «perdido» em massa pede o motivo uma vez e aplica-o a todos
      if (m.acao === "estado" && ["negocios", "leads"].includes(props.objeto)) { const p = await perdidos(); const dtM = props.objeto === "negocios" ? "CRM Deal" : "CRM Lead";
        if ((dtM === "CRM Deal" ? p.negocio : p.lead).includes(m.valor)) { const mot = await pedirMotivo("Motivo de perda para " + sel.value.length + " registo(s)"); if (!mot) return;
          let ok = 0; for (const nm of sel.value) { try { await apiA("marcar_estado", { doctype: dtM, name: nm, estado: m.valor, motivo: mot.motivo, notas: mot.notas }, true); ok++; } catch (e) {} }
          toast(`${ok} atualizado(s)`); massa.value = { acao: "", valor: "" }; carregar(); return; } }
      const r = await apiVis("em_massa", { objeto: props.objeto, nomes: JSON.stringify(sel.value), acao: m.acao, valor: m.valor }, true);
      toast(`${r.feitos} atualizado(s)` + (r.falhas.length ? ` · ${r.falhas.length} falharam` : "")); if (r.falhas.length) console.warn(r.falhas);
      massa.value = { acao: "", valor: "" }; carregar();
    };
    const exportar = (soSel) => { const p = new URLSearchParams({ objeto: props.objeto, vista: vista.value, q: q.value, filtros: JSON.stringify(filtros.value),
      colunas: JSON.stringify(colunas.value.map((c) => c.campo)), nomes: soSel ? JSON.stringify(sel.value) : "" });
      window.location.href = "/api/method/orbit.interface.vistas.exportar?" + p.toString(); };
    // 25-11-2026: «+ Novo» nas listas do CRM (leads, contactos, empresas) — janela curta, depois abre a ficha
    const CAMPOS_NOVO = {
      leads: [["first_name", "Nome", true], ["last_name", "Apelido"], ["organization", "Empresa"], ["email", "Email", false, "email"], ["mobile_no", "Telemóvel", false, "tel"]],
      contactos: [["first_name", "Nome", true], ["last_name", "Apelido"], ["company_name", "Empresa (já registada)"], ["designation", "Cargo"], ["email", "Email", false, "email"], ["mobile_no", "Telemóvel", false, "tel"]],
      empresas: [["organization_name", "Nome da empresa", true], ["website", "Site", false, "url"]],
      negocios: [["titulo", "Nome do negócio", true], ["organization", "Empresa (já registada)"], ["email", "Email do contacto", false, "email"], ["deal_value", "Valor (€)", false, "number"], ["expected_closure_date", "Fecho previsto", false, "date"]],
    };
    const NOME_NOVO = { leads: "Novo lead", contactos: "Novo contacto", empresas: "Nova empresa", negocios: "Novo negócio" };
    const novoReg = ref(null); const aCriar = ref(false);
    const abrirNovo = () => { novoReg.value = props.objeto === "negocios" && marca.value ? { marca: marca.value } : {}; };
    const gravarNovo = async () => {
      aCriar.value = true;
      try { const r = await api("criar_registo", { objeto: props.objeto, dados: JSON.stringify(novoReg.value) }, true);
        novoReg.value = null; toast("Criado."); window.location.hash = link(r.doctype, r.name); }
      catch (e) { toast((e && e.message) || "Não foi possível criar."); }
      finally { aCriar.value = false; }
    };
    const maisAc = ref(false);   // 25-11-2026: Importar/Exportar/Duplicados num «⋯» no telemóvel
    return { maisAc, vista, q, linhas, total, mais, pagina, carregar, ordenar, valor, abrir, a, VISTAS, TITULOS, cor, ini, ordem, meta, salvas, salvaAtiva,
      filtros, colunas, novoF, verCols, sel, massa, escolherFixa, escolherSalva, apagarSalva, guardar, campoMeta, rotuloFiltro, juntarFiltro, tirarFiltro,
      alternarCol, todos, opsMassa, opcoesMassa, aplicarMassa, exportar, OPS_TIPO, importar, marca, escolherMarca,
      CAMPOS_NOVO, NOME_NOVO, novoReg, aCriar, abrirNovo, gravarNovo };
  },
  template: `
  <div>
    <div class="pad" style="padding-bottom:12px;display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap">
      <div><h1>{{ TITULOS[objeto] }}</h1><div class="sub">{{ total }} registos</div></div>
      <div class="acoes-lista" :class="{abertas: maisAc}"><button v-if="CAMPOS_NOVO[objeto]" class="btn prim" @click="abrirNovo">+ Novo</button><button class="btn so-movel" @click="maisAc=!maisAc" title="Mais ações" aria-label="Mais ações">⋯</button><span class="acoes-sec" @click="maisAc=false"><button class="btn" @click="importar=true">Importar</button><button class="btn" @click="exportar(false)">Exportar</button><a v-if="objeto==='contactos'||objeto==='empresas'" class="btn" :href="'#/duplicados/'+objeto">Duplicados</a></span></div>
    </div>
    <div class="vistas marcas-sep" v-if="(meta?.marcas||[]).length > 1">
      <button :class="{ativo: !marca}" @click="escolherMarca('')">Todas as marcas</button>
      <button v-for="m in meta.marcas" :key="m" :class="{ativo: marca===m}" @click="escolherMarca(m)">{{ m }}</button>
    </div>
    <div class="vistas">
      <button v-for="v in VISTAS[objeto]" :key="v[0]" :class="{ativo: !salvaAtiva && vista===v[0]}" @click="escolherFixa(v[0])">{{ v[1] }}</button>
      <button v-for="v in salvas" :key="v.nome+v.partilhada" :class="{ativo: salvaAtiva===v.nome+(v.partilhada?'*':'')}" @click="escolherSalva(v)">{{ v.partilhada ? '👥 ' : '' }}{{ v.nome }} <span class="x-vista" @click.stop="apagarSalva(v)" title="Apagar a vista">×</span></button>
      <button class="mais" @click="guardar">+ Guardar vista</button>
    </div>
    <div class="filtros">
      <input class="filtro" style="border-style:solid;min-width:220px" v-model="q" :placeholder="'Procurar em ' + TITULOS[objeto].toLowerCase() + '…'">
      <span v-for="(f,i) in filtros" :key="i" class="filtro on">{{ rotuloFiltro(f) }} <span style="cursor:pointer" @click="tirarFiltro(i)">✕</span></span>
      <span class="filtro-novo"><button class="filtro" @click="novoF = novoF ? null : {campo:'',op:'',valor:''}">+ Filtro</button>
        <div v-if="novoF" class="cartao pop-filtro">
          <select v-model="novoF.campo" @change="novoF.op=(OPS_TIPO[campoMeta(novoF.campo).tipo]||[[''] ])[0][0]; novoF.valor=''"><option value="" disabled>Campo…</option><option v-for="c in meta?.filtraveis||[]" :key="c.campo" :value="c.campo">{{ c.rotulo }}</option></select>
          <select v-if="novoF.campo" v-model="novoF.op"><option v-for="o in OPS_TIPO[campoMeta(novoF.campo).tipo]||[]" :key="o[0]" :value="o[0]">{{ o[1] }}</option></select>
          <template v-if="novoF.campo && !['vazio','preenchido'].includes(novoF.op)">
            <select v-if="campoMeta(novoF.campo).opcoes" v-model="novoF.valor"><option v-for="o in campoMeta(novoF.campo).opcoes" :key="o.v" :value="o.v">{{ o.r }}</option></select>
            <input v-else v-model="novoF.valor" :type="campoMeta(novoF.campo).tipo==='data'?'date':campoMeta(novoF.campo).tipo==='numero'?'number':'text'">
          </template>
          <button class="btn sm prim" @click="juntarFiltro" :disabled="!novoF.campo">Aplicar</button>
        </div></span>
      <span class="filtro-novo" style="margin-left:auto"><button class="filtro" @click="verCols=!verCols">Colunas ▾</button>
        <div v-if="verCols" class="cartao pop-filtro" style="right:0;left:auto;min-width:220px">
          <label v-for="c in meta?.colunas||[]" :key="c.campo" class="chk-col"><input type="checkbox" :checked="colunas.some(x=>x.campo===c.campo)" @change="alternarCol(c)"> {{ c.rotulo }}</label>
        </div></span>
    </div>
    <div v-if="sel.length" class="selec" style="margin:0 24px;border-radius:10px 10px 0 0;flex-wrap:wrap">
      {{ sel.length }} selecionado(s) ·
      <select class="btn sm" v-model="massa.acao" @change="massa.valor=''"><option value="">Ação…</option><option v-for="o in opsMassa" :key="o[0]" :value="o[0]">{{ o[1] }}</option></select>
      <select v-if="opcoesMassa.length" class="btn sm" v-model="massa.valor"><option value="">— nenhum —</option><option v-for="o in opcoesMassa" :key="o.v" :value="o.v">{{ o.r }}</option></select>
      <input v-if="['marcar','desmarcar'].includes(massa.acao)" class="btn sm" v-model="massa.valor" placeholder="Marcador">
      <button class="btn sm prim" @click="aplicarMassa" :disabled="!massa.acao">Aplicar</button>
      <button class="btn sm" @click="exportar(true)">Exportar seleção</button>
    </div>
    <div class="tabela-wrap cartoes-movel" :style="sel.length?{borderTopLeftRadius:0,borderTopRightRadius:0}:{}"><table>
      <thead><tr><th style="width:34px"><input type="checkbox" v-model="todos"></th><th v-for="c in colunas" :key="c.campo" @click="ordenar(c.campo)" style="cursor:pointer">{{ c.rotulo }}<span v-if="ordem.startsWith(c.campo+' ')">{{ ordem.endsWith('asc') ? ' ↑' : ' ↓' }}</span></th></tr></thead>
      <tbody>
        <tr v-for="l in linhas" :key="l.name">
          <td @click.stop class="cel-sel"><input type="checkbox" :value="l.name" v-model="sel"></td>
          <td v-for="(c,i) in colunas" :key="c.campo" @click="abrir(l)" :class="{'cel-tit': i===0}">
            <div v-if="i===0" class="pessoa"><AvFoto :email="l.email_id || l.email || l.email_geral || emailDoSite(l.website)" :nome="valor(l,c.campo)||l.name" :tam="28"/><a href="#" @click.prevent>{{ valor(l,c.campo) || l.name }}</a></div>
            <span v-else-if="c.campo==='status'" class="etq">{{ valor(l,c.campo) }}</span>
            <span v-else-if="c.campo==='orbit_ciclo' && l.orbit_ciclo" class="etq" :class="{Cliente:'verde',Oportunidade:'roxo',Promotor:'verde','Lead qualificada (vendas)':'azul','Lead qualificada (marketing)':'azul'}[l.orbit_ciclo]">{{ l.orbit_ciclo }}</span>
            <span v-else>{{ valor(l,c.campo) }}</span>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-if="!a && !linhas.length" class="vazio">Nada encontrado.</div>
    <div class="mais-linhas" v-if="mais"><button class="btn sm" @click="pagina++; carregar(true)">Mostrar mais</button></div>
    </div>
    <Importar v-if="importar" :objeto="objeto" @fechar="importar=false" @feito="carregar()"/>
    <div v-if="novoReg" class="modal-fundo" @click.self="novoReg=null"><div class="modal" style="max-width:520px">
      <header><b>{{ NOME_NOVO[objeto] }}</b><button class="btn sm" @click="novoReg=null">Fechar</button></header>
      <form @submit.prevent="gravarNovo" style="display:flex;flex-direction:column;gap:10px;padding:14px 16px">
        <label v-for="c in CAMPOS_NOVO[objeto]" :key="c[0]" class="erp-campo"><span>{{ c[1] }}<span v-if="c[2]" class="obrig">*</span></span>
          <input v-model="novoReg[c[0]]" :type="c[3]||'text'" :required="c[2]" :autofocus="c[2]"></label>
        <p class="sub" style="margin:0">O resto completa-se na ficha, que abre a seguir.</p>
        <div style="display:flex;justify-content:flex-end;gap:8px"><button type="button" class="btn" @click="novoReg=null">Cancelar</button><button type="submit" class="btn prim" :disabled="aCriar">{{ aCriar ? 'A criar…' : 'Criar' }}</button></div>
      </form></div></div>
  </div>`,
};

// ── Separador «Detalhes» da ficha (23-11-2026): todos os campos por secções, em colunas (orbit/interface/detalhes.py) ──
// ── Fotografia de quem escreve (23-11-2026): CRM → equipa → Gravatar/BIMI/site (orbit/avatares.py); senão as iniciais ──
const _semFoto = new Set();
const AvFoto = {
  props: ["email", "nome", "tam"],
  setup(props) {
    const falhou = ref(false);
    const mail = computed(() => { const m = String(props.email || "").match(/[^\s<>"',;]+@[^\s<>"',;]+\.[a-z]{2,}/i); return m ? m[0].toLowerCase() : ""; });
    const src = computed(() => mail.value && !_semFoto.has(mail.value) && !falhou.value ? "/api/method/orbit.avatares.foto?email=" + encodeURIComponent(mail.value) : "");
    const erro = () => { _semFoto.add(mail.value); falhou.value = true; };
    const pronta = ref(false);
    const estilo = computed(() => { const t = props.tam || 32; return { width: t + "px", height: t + "px", minWidth: t + "px", fontSize: Math.round(t * 0.36) + "px", background: cor(props.nome || mail.value || "?") }; });
    return { src, erro, estilo, ini, pronta };
  },
  // as iniciais ficam sempre por baixo; a fotografia aparece por cima só depois de carregada
  template: `<span class="av av-foto" :style="estilo">{{ ini(nome || email || '?') }}<img v-if="src" :src="src" alt="" :class="{pronta}" @load="pronta=true" @error="erro"></span>`,
};
// ── Desk na interface nova (23-11-2026): tickets e ficha do ticket, sobre o Helpdesk (orbit/interface/desk.py) ──
const DeskTickets = {
  setup() {
    let v0 = "abertos"; try { v0 = localStorage.getItem("orbit.desk.vista") || v0; } catch (e) {}
    const vista = ref(v0); const q = ref(""); const f = ref({ equipa: "", estado: "", prioridade: "", marca: "", responsavel: "", tipo: "", desde: "", ate: "", ordem: "atividade" });
    // lote 3 (25-11): selecção e acções em massa, colunas, «Novo ticket», actualização automática, prazos em contagem
    const sel = ref([]); const massa = ref({ acao: "", valor: "" }); const novoT = ref(null); const maisF = ref(false); const verCols = ref(false);
    const COLS = [["cliente", "Cliente"], ["estado", "Estado"], ["prioridade", "Prioridade"], ["equipa", "Equipa"], ["responsavel", "Responsável"], ["prazo", "Prazo"], ["atividade", "Última atividade"]];
    let esc0 = []; try { esc0 = JSON.parse(localStorage.getItem("orbit.desk.cols.escondidas") || "[]"); } catch (e) {}
    const escondidas = ref(esc0); const ver = (c) => !escondidas.value.includes(c);
    const alternarCol = (c) => { escondidas.value = ver(c) ? escondidas.value.concat([c]) : escondidas.value.filter((x) => x !== c); try { localStorage.setItem("orbit.desk.cols.escondidas", JSON.stringify(escondidas.value)); } catch (e) {} };
    const agoraT = ref(Date.now()); let relT = setInterval(() => { agoraT.value = Date.now(); if (!document.hidden && modoRef && modoRef.value === "lista" && !sel.value.length) carregar(); }, 60000);
    onUnmounted(() => clearInterval(relT));
    const falta = (t) => { if (!t.prazo) return ""; const ms = new Date(String(t.prazo).replace(" ", "T")) - agoraT.value; const h = Math.round(Math.abs(ms) / 36e5);
      const txt = h >= 48 ? Math.round(h / 24) + " d" : h >= 1 ? h + " h" : Math.max(1, Math.round(Math.abs(ms) / 6e4)) + " min"; return ms < 0 ? "atrasado " + txt : "faltam " + txt; };
    const todosSel = computed({ get: () => !!(d.value && d.value.linhas.length && sel.value.length === d.value.linhas.length), set: (v) => (sel.value = v ? d.value.linhas.map((x) => x.name) : []) });
    const OPS_MASSA = [["atribuir", "Atribuir a"], ["estado", "Mudar o estado"], ["prioridade", "Mudar a prioridade"], ["equipa", "Mudar a equipa"], ["tipo", "Mudar o tipo"], ["apagar", "Apagar"]];
    const opcoesMassa = computed(() => { const m = meta.value || {}; return { atribuir: m.agentes || [], estado: m.estados || [], prioridade: m.prioridades || [], equipa: (m.equipas || []).map((x) => ({ v: x, r: x })), tipo: m.tipos || [] }[massa.value.acao] || []; });
    const aplicarMassa = async () => { const m = massa.value; if (!m.acao) return; if (m.acao === "apagar" && !confirm(`Apagar ${sel.value.length} ticket(s)? Não se desfaz.`)) return;
      const r = await api("desk_mais.em_massa", { nomes: JSON.stringify(sel.value), acao: m.acao, valor: m.valor }, true);
      toast(`${r.feitos} atualizado(s)` + (r.falhas.length ? ` · ${r.falhas.length} falharam` : "")); sel.value = []; massa.value = { acao: "", valor: "" }; carregar(); };
    const exportar = () => { const esc = (x) => `"${String(x ?? "").replace(/"/g, '""')}"`;
      const t = [["N.º", "Assunto", "Cliente", "Estado", "Prioridade", "Equipa", "Responsável", "Prazo", "Última atividade"].map(esc).join(";")]
        .concat((d.value?.linhas || []).filter((x) => !sel.value.length || sel.value.includes(x.name)).map((x) => [x.name, x.assunto, x.cliente, x.estado_pt, x.prioridade_pt, x.equipa, x.responsavel_nome, x.prazo, x.atividade].map(esc).join(";"))).join("\n");
      const b = new Blob(["\ufeff" + t], { type: "text/csv;charset=utf-8" }); const u = URL.createObjectURL(b); const el = document.createElement("a"); el.href = u; el.download = "tickets.csv"; el.click(); URL.revokeObjectURL(u); };
    const procurarC = ref([]); let tqc;
    const procurarContacto = () => { clearTimeout(tqc); tqc = setTimeout(async () => { procurarC.value = await api("desk_mais.clientes_e_contactos", { q: novoT.value.email }).catch(() => []); }, 250); };
    const criarTicket = async () => { const r = await api("desk_mais.criar", { dados: JSON.stringify(novoT.value) }, true); novoT.value = null; toast("Ticket #" + r.name + " criado"); location.hash = "#/ticket/" + r.name; };
    let modoRef = null;
    const d = ref(null); const meta = ref(null); const pagina = ref(0); let tq;
    const carregar = async (junta = false) => {
      const r = await api("desk.tickets", { vista: vista.value, q: q.value, pagina: pagina.value, ...f.value });
      d.value = junta && d.value ? { ...r, linhas: d.value.linhas.concat(r.linhas) } : r;
    };
    onMounted(async () => { meta.value = await api("desk.metadados"); carregar(); });
    const escolher = (v) => { vista.value = v; pagina.value = 0; try { localStorage.setItem("orbit.desk.vista", v); } catch (e) {} carregar(); };
    watch(q, () => { clearTimeout(tq); tq = setTimeout(() => { pagina.value = 0; carregar(); }, 300); });
    watch(f, () => { pagina.value = 0; carregar(); }, { deep: true });
    const VISTAS_D = [["abertos", "Abertos"], ["meus", "Os meus"], ["sem_resposta", "Sem resposta"], ["fora_prazo", "Fora do prazo"], ["resolvidos", "Resolvidos"], ["todos", "Todos"]];
    const abrir = (t) => { location.hash = "#/ticket/" + encodeURIComponent(t.name); };
    // 23-11-2026 (K1): funil por estado, com arrastar; para Resolvido/Fechado pede-se a resolução
    let m0 = "lista"; try { m0 = localStorage.getItem("orbit.desk.modo") || m0; } catch (e) {}
    const modo = ref(m0); modoRef = modo; const fn = ref(null); const arr = ref(null); const resolver = ref(null);
    const carregarFunil = async () => { fn.value = await api("desk.funil", { q: q.value, ...f.value, meus: vista.value === "meus" ? 1 : 0 }); };
    const mudarModo = (m) => { modo.value = m; try { localStorage.setItem("orbit.desk.modo", m); } catch (e) {} if (m === "funil") carregarFunil(); };
    if (m0 === "funil") onMounted(carregarFunil);
    watch([q, f], () => { if (modo.value === "funil") carregarFunil(); }, { deep: true });
    const largar = async (col) => {
      const t = arr.value; arr.value = null; if (!t || t.estado === col.v) return;
      if (col.cat === "Resolved") { resolver.value = { t, estado: col.v, r: col.r, nota: "" }; return; }
      await api("desk.mudar_estado", { nome: t.name, estado: col.v }, true); toast("#" + t.name + " → " + col.r); carregarFunil();
    };
    const confirmar = async () => {
      if (!resolver.value.nota.trim()) return;
      await api("desk.mudar_estado", { nome: resolver.value.t.name, estado: resolver.value.estado, nota: resolver.value.nota }, true);
      toast("#" + resolver.value.t.name + " → " + resolver.value.r); resolver.value = null; carregarFunil();
    };
    return { vista, q, f, d, meta, pagina, carregar, escolher, VISTAS_D, data, abrir, modo, mudarModo, fn, arr, largar, resolver, confirmar,
      sel, massa, novoT, maisF, verCols, COLS, ver, alternarCol, falta, todosSel, OPS_MASSA, opcoesMassa, aplicarMassa, exportar, procurarC, procurarContacto, criarTicket };
  },
  template: `
  <div>
    <div class="pad" style="padding-bottom:12px;display:flex;justify-content:space-between;align-items:flex-end;gap:12px;flex-wrap:wrap"><div><h1>Tickets</h1><div class="sub">Pedidos de atendimento do Desk.</div></div>
      <div class="acoes-lista"><button class="btn prim" @click="novoT={email:'',assunto:'',descricao:'',prioridade:'',tipo:'',equipa:'',responsavel:''}">+ Novo ticket</button><button class="btn" @click="exportar">Exportar</button></div>
      <div class="vistas" style="padding:0;margin:0"><button :class="{ativo: modo==='lista'}" @click="mudarModo('lista')">Lista</button><button :class="{ativo: modo==='funil'}" @click="mudarModo('funil')">Funil</button></div></div>
    <div class="vistas" v-if="modo==='lista'">
      <button v-for="v in VISTAS_D" :key="v[0]" :class="{ativo: vista===v[0]}" @click="escolher(v[0])">{{ v[1] }}<span v-if="d && d.contagens[v[0]] != null" class="sub"> {{ d.contagens[v[0]] }}</span></button>
    </div>
    <div class="filtros" v-if="meta">
      <input class="filtro" style="border-style:solid;min-width:220px" v-model="q" placeholder="Procurar por assunto, email ou n.º…">
      <select class="filtro" v-model="f.equipa"><option value="">Todas as equipas</option><option v-for="e in meta.equipas" :key="e" :value="e">{{ e }}</option></select>
      <select v-if="meta.marcas.length" class="filtro" v-model="f.marca"><option value="">Todas as marcas</option><option v-for="m in meta.marcas" :key="m" :value="m">{{ m }}</option></select>
      <select class="filtro" v-model="f.estado"><option value="">Todos os estados</option><option v-for="e in meta.estados" :key="e.v" :value="e.v">{{ e.r }}</option></select>
      <select class="filtro" v-model="f.prioridade"><option value="">Todas as prioridades</option><option v-for="e in meta.prioridades" :key="e.v" :value="e.v">{{ e.r }}</option></select>
      <button class="filtro" @click="maisF=!maisF">{{ maisF ? '− Menos filtros' : '+ Filtros' }}</button>
      <template v-if="maisF">
        <select class="filtro" v-model="f.responsavel"><option value="">Qualquer responsável</option><option value="-">Sem responsável</option><option v-for="a in meta.agentes" :key="a.v" :value="a.v">{{ a.r }}</option></select>
        <select class="filtro" v-model="f.tipo"><option value="">Todos os tipos</option><option v-for="e in meta.tipos" :key="e.v" :value="e.v">{{ e.r }}</option></select>
        <label class="filtro" style="display:flex;gap:4px;align-items:center">Aberto de <input type="date" v-model="f.desde" style="border:0;background:none;color:inherit"></label>
        <label class="filtro" style="display:flex;gap:4px;align-items:center">até <input type="date" v-model="f.ate" style="border:0;background:none;color:inherit"></label>
      </template>
      <select class="filtro" v-model="f.ordem" style="margin-left:auto"><option value="atividade">Última atividade</option><option value="abertura">Mais recentes</option><option value="abertura_asc">Mais antigos</option><option value="prazo">Prazo mais próximo</option><option value="prioridade">Prioridade</option></select>
      <span class="filtro-novo"><button class="filtro" @click="verCols=!verCols">Colunas ▾</button>
        <div v-if="verCols" class="cartao pop-filtro" style="right:0;left:auto;min-width:200px"><label v-for="c in COLS" :key="c[0]" class="chk-col"><input type="checkbox" :checked="ver(c[0])" @change="alternarCol(c[0])"> {{ c[1] }}</label></div></span>
    </div>
    <div v-if="sel.length" class="selec" style="margin:0 24px;border-radius:10px 10px 0 0;flex-wrap:wrap">
      {{ sel.length }} selecionado(s) ·
      <select class="btn sm" v-model="massa.acao" @change="massa.valor=''"><option value="">Ação…</option><option v-for="o in OPS_MASSA" :key="o[0]" :value="o[0]">{{ o[1] }}</option></select>
      <select v-if="opcoesMassa.length" class="btn sm" v-model="massa.valor"><option value="">— escolher —</option><option v-for="o in opcoesMassa" :key="o.v" :value="o.v">{{ o.r }}</option></select>
      <button class="btn sm prim" @click="aplicarMassa" :disabled="!massa.acao || (massa.acao!=='apagar' && !massa.valor)">Aplicar</button>
      <button class="btn sm" @click="exportar">Exportar seleção</button>
    </div>
    <div v-if="modo==='funil'" class="funil-desk">
      <div v-if="!fn" class="carregar">A carregar…</div>
      <div v-for="c in fn?.colunas||[]" :key="c.v" class="fd-col" @dragover.prevent @drop="largar(c)">
        <header><b>{{ c.r }}</b><span class="sub">{{ c.tickets.length }}</span></header>
        <div class="fd-cartoes">
          <div v-for="t in c.tickets" :key="t.name" class="cartao fd-cartao" draggable="true" @dragstart="arr = t" @click="abrir(t)" :class="{atrasado: t.atrasado}">
            <div class="sub" style="font-size:11px;display:flex;justify-content:space-between"><span>#{{ t.name }}<template v-if="t.marca"> · {{ t.marca }}</template></span><span :class="{Urgent:'etq ambar',High:'etq ambar'}[t.prioridade] || ''">{{ t.prioridade_pt }}</span></div>
            <b>{{ t.assunto }}</b>
            <div class="sub" style="font-size:12px;display:flex;justify-content:space-between;gap:6px;margin-top:4px"><span class="pessoa"><AvFoto :email="t.email" :nome="t.cliente" :tam="18"/>{{ t.cliente }}</span><span>{{ t.responsavel_nome }}</span></div>
            <div v-if="t.prazo && c.cat !== 'Resolved'" class="sub" style="font-size:11px;margin-top:2px" :style="t.atrasado ? {color:'var(--ambar)'} : {}">{{ t.atrasado ? 'Fora do prazo · ' : 'Prazo ' }}{{ data(t.prazo) }}</div>
          </div>
          <div v-if="!c.tickets.length" class="sub" style="font-size:12px;padding:8px">Vazio</div>
        </div>
      </div>
      <div class="modal-fundo" v-if="resolver" @click.self="resolver=null"><div class="modal" style="max-width:480px"><header><b>#{{ resolver.t.name }} → {{ resolver.r }}</b><button class="btn sm" @click="resolver=null">Cancelar</button></header>
        <div style="padding:16px 20px"><p class="sub" style="font-size:13px;margin:0 0 8px">Descreva a resolução. O cliente recebe o inquérito de satisfação em dia útil.</p>
          <textarea class="ed-campo" v-model="resolver.nota" rows="4" style="width:100%;box-sizing:border-box"></textarea>
          <div style="display:flex;justify-content:flex-end;margin-top:10px"><button class="btn prim" :disabled="!resolver.nota.trim()" @click="confirmar">Confirmar</button></div></div></div></div>
    </div>
    <div class="tabela-wrap cartoes-movel" v-else><table>
      <thead><tr><th style="width:34px"><input type="checkbox" v-model="todosSel"></th><th style="width:70px">N.º</th><th>Assunto</th><th v-if="ver('cliente')">Cliente</th><th v-if="ver('estado')">Estado</th><th v-if="ver('prioridade')">Prioridade</th><th v-if="ver('equipa')">Equipa</th><th v-if="ver('responsavel')">Responsável</th><th v-if="ver('prazo')">Prazo</th><th v-if="ver('atividade')">Última atividade</th></tr></thead>
      <tbody><tr v-for="t in d?.linhas||[]" :key="t.name" @click="abrir(t)" style="cursor:pointer" :class="{'por-ler': t.por_ler}">
        <td @click.stop class="cel-sel"><input type="checkbox" :value="t.name" v-model="sel"></td>
        <td class="sub">#{{ t.name }}</td><td class="cel-tit"><b>{{ t.assunto }}</b><div class="sub" style="font-size:12px" v-if="t.marca">{{ t.marca }}</div></td>
        <td v-if="ver('cliente')"><span class="pessoa"><AvFoto :email="t.email" :nome="t.cliente" :tam="24"/>{{ t.cliente }}</span></td>
        <td v-if="ver('estado')"><span class="etq" :class="{Open:'azul',Replied:'roxo',Paused:'ambar',Resolved:'verde',Closed:''}[t.estado]">{{ t.estado_pt }}</span></td>
        <td v-if="ver('prioridade')"><span class="etq" :class="{Urgent:'ambar',High:'ambar'}[t.prioridade]">{{ t.prioridade_pt }}</span></td>
        <td v-if="ver('equipa')">{{ t.equipa || '—' }}</td><td v-if="ver('responsavel')">{{ t.responsavel_nome || '—' }}</td>
        <td v-if="ver('prazo')"><span v-if="t.pausa" class="etq">Em pausa</span><span v-else-if="t.prazo && !['Resolved','Closed'].includes(t.estado)" :class="t.atrasado || falta(t).startsWith('atrasado') ? 'etq ambar' : 'sub'" :title="data(t.prazo)">{{ falta(t) }}</span><span v-else class="sub">{{ t.sla || '—' }}</span></td>
        <td v-if="ver('atividade')" class="sub">{{ data(t.atividade) }}</td></tr></tbody></table>
      <div v-if="d && !d.linhas.length" class="vazio">Nenhum ticket nesta vista.</div>
      <div v-if="!d" class="carregar">A carregar…</div>
      <div class="mais-linhas" v-if="d && d.mais"><button class="btn sm" @click="pagina++; carregar(true)">Mostrar mais</button></div>
    </div>
    <div v-if="novoT" class="modal-fundo" @click.self="novoT=null"><div class="modal" style="max-width:600px"><header><b>Novo ticket</b><button class="btn sm" @click="novoT=null">Fechar</button></header>
      <form class="reg-form" @submit.prevent="criarTicket">
        <div class="erp-campo" style="position:relative"><span>Email do cliente<span class="obrig">*</span></span><input v-model="novoT.email" type="email" required placeholder="Procurar contacto ou escrever o email" @input="procurarContacto">
          <div v-if="procurarC.length" class="cartao reg-sug"><div v-for="c in procurarC" :key="c.email" @mousedown.prevent="novoT.email=c.email; procurarC=[]">{{ c.nome }} · <span class="sub">{{ c.email }}</span></div></div></div>
        <label class="erp-campo"><span>Assunto<span class="obrig">*</span></span><input v-model="novoT.assunto" required></label>
        <div class="erp-campo"><span>Descrição</span><EditorRico v-model="novoT.descricao"/></div>
        <div class="reg-linha3"><label class="erp-campo"><span>Prioridade</span><select v-model="novoT.prioridade"><option value="">—</option><option v-for="e in meta.prioridades" :key="e.v" :value="e.v">{{ e.r }}</option></select></label>
          <label class="erp-campo"><span>Tipo</span><select v-model="novoT.tipo"><option value="">—</option><option v-for="e in meta.tipos" :key="e.v" :value="e.v">{{ e.r }}</option></select></label>
          <label class="erp-campo"><span>Equipa</span><select v-model="novoT.equipa"><option value="">—</option><option v-for="e in meta.equipas" :key="e" :value="e">{{ e }}</option></select></label></div>
        <label class="erp-campo"><span>Responsável</span><select v-model="novoT.responsavel"><option value="">— ninguém —</option><option v-for="a in meta.agentes" :key="a.v" :value="a.v">{{ a.r }}</option></select></label>
        <div class="reg-botoes"><button type="button" class="btn" @click="novoT=null">Cancelar</button><button class="btn prim">Criar ticket</button></div>
      </form></div></div>
  </div>`,
};
// ── Conversa interna num registo, com @menções (23-11-2026) ──────────────────────────────────────────────────────
// Comentários do Frappe ligados ao registo; «@» abre a lista da equipa e a pessoa escolhida é mencionada — recebe o
// aviso no sino, a notificação no telemóvel (se ligou os avisos) e, se ficar por ver 3 h, o email.
async function apiConv(metodo, args = {}, post = false) {
  const url = `/api/method/orbit.interface.conversa.${metodo}`;
  const op = { headers: { "X-Frappe-CSRF-Token": window.csrf_token, Accept: "application/json" } };
  let r;
  if (post) { op.method = "POST"; op.headers["Content-Type"] = "application/json"; op.body = JSON.stringify(args); r = await fetch(url, op); }
  else r = await fetch(url + "?" + new URLSearchParams(args), op);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) { let m = "Erro"; try { m = JSON.parse(JSON.parse(j._server_messages)[0]).message; } catch (e) {} toast(String(m).replace(/<[^>]+>/g, "")); throw new Error(m); }
  return j.message;
}
let _pessoasConv = null;
async function apiConvPush(metodo, args = {}, post = false) {
  const url = `/api/method/orbit.interface.push.${metodo}`;
  const op = { headers: { "X-Frappe-CSRF-Token": window.csrf_token, Accept: "application/json" } };
  if (post) { op.method = "POST"; op.headers["Content-Type"] = "application/json"; op.body = JSON.stringify(args); }
  const r = await fetch(post ? url : url + "?" + new URLSearchParams(args), op); const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error("o servidor recusou"); return j.message;
}
const ConversaRegisto = {
  props: ["doctype", "nome", "compacto"],
  emits: ["mudou"],
  setup(props, { emit }) {
    const itens = ref(null); const texto = ref(""); const mencoes = ref([]); const pessoas = ref([]); const sug = ref([]); const iSug = ref(0);
    const aEnviar = ref(false); const caixa = ref(null);
    const carregar = async () => { itens.value = await apiConv("lista", { doctype: props.doctype, nome: props.nome }); };
    onMounted(async () => { carregar(); if (!_pessoasConv) _pessoasConv = await apiConv("pessoas"); pessoas.value = _pessoasConv; });
    watch(() => props.nome, carregar);
    const aEscrever = () => {
      const t = caixa.value; const ate = texto.value.slice(0, t ? t.selectionStart : texto.value.length);
      const m = /(^|\s)@([\p{L}\w.\- ]{0,30})$/u.exec(ate);
      if (!m) { sug.value = []; return; }
      const q = m[2].toLowerCase().trim();
      sug.value = pessoas.value.filter((p) => !q || p.nome.toLowerCase().includes(q) || p.email.toLowerCase().startsWith(q)).slice(0, 6); iSug.value = 0;
    };
    const escolher = (p) => {
      const t = caixa.value; const pos = t ? t.selectionStart : texto.value.length;
      const antes = texto.value.slice(0, pos).replace(/@([\p{L}\w.\- ]{0,30})$/u, "@" + p.nome + " ");
      texto.value = antes + texto.value.slice(pos); sug.value = [];
      if (!mencoes.value.find((x) => x.email === p.email)) mencoes.value.push({ email: p.email, nome: p.nome });
      nextTick(() => { if (t) { t.focus(); t.selectionStart = t.selectionEnd = antes.length; } });
    };
    const tecla = (e) => {
      if (sug.value.length) {
        if (e.key === "ArrowDown") { iSug.value = (iSug.value + 1) % sug.value.length; e.preventDefault(); return; }
        if (e.key === "ArrowUp") { iSug.value = (iSug.value - 1 + sug.value.length) % sug.value.length; e.preventDefault(); return; }
        if (e.key === "Enter" || e.key === "Tab") { escolher(sug.value[iSug.value]); e.preventDefault(); return; }
        if (e.key === "Escape") { sug.value = []; return; }
      }
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); enviar(); }
    };
    const enviar = async () => {
      if (!texto.value.trim() || aEnviar.value) return;
      aEnviar.value = true;
      try {
        const usadas = mencoes.value.filter((m) => texto.value.includes("@" + m.nome));
        const r = await apiConv("comentar", { doctype: props.doctype, nome: props.nome, texto: texto.value, mencoes: JSON.stringify(usadas) }, true);
        toast(r.mencionados.length ? "Comentário enviado — " + r.mencionados.length + (r.mencionados.length === 1 ? " pessoa avisada" : " pessoas avisadas") : "Comentário gravado");
        texto.value = ""; mencoes.value = []; await carregar(); emit("mudou");
      } finally { aEnviar.value = false; }
    };
    const apagar = async (c) => { if (!confirm("Apagar este comentário?")) return; await apiConv("apagar", { id: c.id }, true); carregar(); emit("mudou"); };
    const limpo = (h) => String(h || "").replace(/<script[\s\S]*?<\/script>/gi, "").replace(/\son\w+="[^"]*"/gi, "");
    return { itens, texto, sug, iSug, aEnviar, caixa, aEscrever, escolher, tecla, enviar, apagar, limpo, data };
  },
  template: `<div class="conversa-reg">
    <div v-if="!itens" class="carregar">A carregar…</div>
    <p v-else-if="!itens.length && !compacto" class="sub" style="font-size:13px;margin:4px 0 10px">Ainda não há conversa. Escreva e use <b>@</b> para chamar alguém da equipa — recebe o aviso no sino e no telemóvel.</p>
    <div v-for="c in itens || []" :key="c.id" class="comentario" :class="{meu:c.meu}">
      <AvFoto :email="c.email" :nome="c.quem" :tam="28"/>
      <div class="cresce"><div class="chat-cab"><b>{{ c.quem }}</b><span class="sub">{{ data(c.data) }}</span>
        <button v-if="c.meu" class="sub" style="all:unset;cursor:pointer;font-size:12px;margin-left:auto" @click="apagar(c)">apagar</button></div>
        <div class="comentario-txt" v-html="limpo(c.html)"></div></div>
    </div>
    <div class="cartao compor" style="position:relative;flex-direction:column;align-items:stretch">
      <textarea ref="caixa" v-model="texto" rows="2" placeholder="Escrever na conversa… use @ para chamar alguém" @input="aEscrever" @click="aEscrever" @keydown="tecla"></textarea>
      <div v-if="sug.length" class="mencao-sug"><button v-for="(p, k) in sug" :key="p.email" :class="{ativo:k===iSug}" @mousedown.prevent="escolher(p)"><AvFoto :email="p.email" :nome="p.nome" :tam="20"/>{{ p.nome }}</button></div>
      <div style="display:flex;justify-content:space-between;align-items:center;margin-top:6px"><span class="sub" style="font-size:12px">@ menciona · ⌘↵ envia · só a equipa vê</span>
        <button class="btn sm prim" @click="enviar" :disabled="!texto.trim() || aEnviar">{{ aEnviar ? 'A enviar…' : 'Comentar' }}</button></div>
    </div>
  </div>`,
};

// ── Modelos de checklist do Desk (23-11-2026, K4) ─────────────────────────────────────────────────────────────────
const DeskModelos = {
  setup() {
    const d = ref(null); const aGravar = ref(false);
    onMounted(async () => { const r = await api("desk.modelos_checklist"); d.value = { tipos: r.tipos, modelos: r.modelos.map((m) => ({ ...m, texto: m.itens.join("\n") })) }; });
    const novo = () => d.value.modelos.push({ nome: "", tipo: "", texto: "" });
    const gravar = async () => {
      aGravar.value = true;
      try { await api("desk.gravar_modelos_checklist", { modelos: JSON.stringify(d.value.modelos.map((m) => ({ nome: m.nome, tipo: m.tipo, itens: m.texto.split("\n") }))) }, true); toast("Modelos gravados"); }
      finally { aGravar.value = false; }
    };
    return { d, novo, gravar, aGravar };
  },
  template: `<div class="pad" style="max-width:820px"><h1>Modelos de checklist</h1>
    <div class="sub" style="margin-bottom:14px">Listas de pontos a resolver prontas a inserir num ticket. Com um <b>tipo</b>, o modelo entra sozinho nos tickets desse tipo.</div>
    <div v-if="!d" class="carregar">A carregar…</div>
    <template v-else>
      <div v-for="(m, k) in d.modelos" :key="k" class="cartao" style="padding:14px 16px;margin-bottom:12px">
        <div style="display:flex;gap:8px;flex-wrap:wrap"><input class="ed-campo" v-model="m.nome" placeholder="Nome do modelo" style="flex:1;min-width:200px">
          <select class="ed-campo" v-model="m.tipo"><option value="">Sem tipo (só a pedido)</option><option v-for="t in d.tipos" :key="t" :value="t">Automático: {{ t }}</option></select>
          <button class="btn sm" @click="d.modelos.splice(k,1)">Tirar</button></div>
        <textarea class="ed-campo" v-model="m.texto" rows="5" placeholder="Um ponto por linha" style="width:100%;box-sizing:border-box;margin-top:8px"></textarea>
      </div>
      <div style="display:flex;gap:8px"><button class="btn" @click="novo">+ Novo modelo</button><button class="btn prim" @click="gravar" :disabled="aGravar">{{ aGravar ? 'A gravar…' : 'Gravar' }}</button></div>
    </template></div>`,
};
const DeskTicket = {
  // 23-11-2026 (plano do Desk D1–D4): ecrã arrumado como as fichas do CRM — cabeçalho com estado e ações, conversa ao
  // centro, barra direita com propriedades, checklist, tempo, prazos, cliente e avaliação.
  components: { EmailCorpo, ConversaRegisto, Icone },
  props: ["nome"],
  setup(props) {
    const t = ref(null); const meta = ref(null); const modo = ref("responder"); const texto = ref(""); const cc = ref(""); const aEnviar = ref(false);
    // lote 3 (25-11): resposta completa (De, Para, Cc, Bcc, formatação, anexos, acções do modelo, rascunho), responder a um email,
    // dividir, fundir, apagar, assunto/cliente/campos do modelo editáveis, histórico, atribuir a várias pessoas
    const r3 = ref({ conta: "", para: "", bcc: "", html: "", anexos: [], acoes: [], verMais: false, citar: null });
    const contas = ref([]); const ext3 = ref(null); const extR = ref(null); const separ = ref("tudo"); const edAssunto = ref(null); const fundir = ref(null); const anexoIn3 = ref(null);
    const chaveR = () => "orbit.desk.rascunho." + props.nome;
    try { const g = JSON.parse(localStorage.getItem(chaveR()) || "null"); if (g) Object.assign(r3.value, g); } catch (e) {}
    watch(() => [r3.value.html, r3.value.para, r3.value.bcc, cc.value], () => { try { if (String(r3.value.html || "").replace(/<[^>]+>/g, "").trim()) localStorage.setItem(chaveR(), JSON.stringify({ html: r3.value.html, para: r3.value.para, bcc: r3.value.bcc })); else localStorage.removeItem(chaveR()); } catch (e) {} });
    const carregarExt3 = async () => { ext3.value = await api("desk_mais.extra", { nome: props.nome }).catch(() => null); extR.value = await apiR("extras", { doctype: "HD Ticket", name: props.nome }).catch(() => null); };
    onMounted(async () => { contas.value = await api("desk_mais.contas_envio").catch(() => []); r3.value.conta = r3.value.conta || (contas.value[0] || {}).conta || ""; carregarExt3(); });
    const enviar3 = async () => {
      const txt = String(r3.value.html || "").replace(/<[^>]+>/g, "").trim(); if (!txt || aEnviar.value) return; aEnviar.value = true;
      try { const corpo = r3.value.html + (r3.value.citar ? `<br><blockquote type="cite">${r3.value.citar}</blockquote>` : "");
        const r = await api("desk_mais.responder", { nome: props.nome, html: corpo, para: r3.value.para || null, cc: cc.value, bcc: r3.value.bcc, conta: r3.value.conta || null,
          anexos: r3.value.anexos.length ? JSON.stringify(r3.value.anexos.map((x) => x.id)) : null, acoes: r3.value.acoes.length ? JSON.stringify(r3.value.acoes) : null }, true);
        toast("Resposta enviada ao cliente" + (r.acoes && r.acoes.erro ? " — as ações do modelo falharam" : "")); r3.value = { ...r3.value, html: "", anexos: [], acoes: [], citar: null, para: "", bcc: "" }; cc.value = "";
        try { localStorage.removeItem(chaveR()); } catch (e) {} carregar(); carregarExt3(); }
      catch (e) {} finally { aEnviar.value = false; } };
    const juntarAnexos3 = async (ev) => { for (const fi of [...(ev.target.files || [])]) {
        const fd = new FormData(); fd.append("file", fi, fi.name); fd.append("is_private", 1); fd.append("doctype", "HD Ticket"); fd.append("docname", props.nome);
        const rr = await fetch("/api/method/upload_file", { method: "POST", body: fd, headers: { "X-Frappe-CSRF-Token": window.csrf_token, Accept: "application/json" } });
        const j = await rr.json().catch(() => ({})); if (j.message) r3.value.anexos.push({ id: j.message.name, nome: fi.name }); else toast("Não foi possível anexar " + fi.name); }
      ev.target.value = ""; };
    const responderA = (m, todos) => { modo.value = "responder"; const eu = (window.__ctx?.utilizador || "").toLowerCase(); const sep = (x) => String(x || "").split(/[,;]/).map((y) => y.trim()).filter(Boolean);
      r3.value.para = m.enviado ? (m.para || "") : [m.de].concat(todos ? sep(m.para) : []).filter((x) => x && !x.toLowerCase().includes(eu)).join(", ");
      if (todos) { cc.value = m.cc || ""; r3.value.verMais = true; } r3.value.citar = m.html; nextTick(() => document.querySelector(".desk-resposta")?.scrollIntoView({ behavior: "smooth", block: "end" })); };
    const dividir = async (m) => { const a = prompt("Assunto do novo ticket", t.value.assunto); if (!a) return; const r = await api("desk_mais.dividir", { comunicacao: m.id, assunto: a }, true); toast("Novo ticket criado a partir deste email"); if (r.novo) location.hash = "#/ticket/" + (r.novo.name || r.novo); else carregar(); };
    const fazerFundir = async () => { const dst = String(fundir.value.destino || "").replace("#", "").trim(); if (!dst) return;
      if (!confirm(`Fundir o #${props.nome} no #${dst}? As mensagens passam para o #${dst} e este fecha.`)) return;
      await api("desk_mais.fundir", { origem: props.nome, destino: dst }, true); fundir.value = null; toast("Tickets fundidos"); location.hash = "#/ticket/" + dst; };
    const apagarTicket = async () => { if (!confirm(`Apagar o ticket #${props.nome}? Não se desfaz.`)) return; await api("desk_mais.apagar", { nome: props.nome }, true); toast("Ticket apagado"); location.hash = "#/tickets"; };
    const gravarAssunto = async () => { const v = (edAssunto.value || "").trim(); edAssunto.value = null; if (!v || v === t.value.assunto) return; await api("desk_mais.mudar", { nome: props.nome, campo: "subject", valor: v }, true); toast("Assunto mudado"); carregar(); };
    const mudar3 = async (campo, valor) => { await api("desk_mais.mudar", { nome: props.nome, campo, valor }, true); toast("Gravado"); carregar(); carregarExt3(); };
    const linhaVis = computed(() => (t.value?.linha || []).filter((m) => separ.value === "tudo" || (separ.value === "emails" ? m.tipo === "email" : m.tipo === "comentario")));
    const menu3 = ref(false); const fecharMenu3 = () => (menu3.value = false);
    onMounted(() => document.addEventListener("click", fecharMenu3)); onUnmounted(() => document.removeEventListener("click", fecharMenu3));
    const copiar3 = async () => { try { await navigator.clipboard.writeText(location.href); toast("Ligação copiada"); } catch (e) { toast(location.href); } };
    const ck = ref({ itens: [], modelos: [] }); const novoPonto = ref(""); const tm = ref({ total: 0, linhas: [] });
    const resolver = ref(null); const parar = ref(null); const agora = ref(Date.now()); let rel;
    const carregar = async () => { t.value = await api("desk.ticket", { nome: props.nome }); nextTick(() => { const m = document.querySelector(".desk-linha"); if (m) m.scrollTop = m.scrollHeight; }); };
    const carregarCk = async () => { ck.value = await api("desk.checklist", { nome: props.nome }); };
    const carregarTm = async () => { tm.value = await api("desk.tempo", { nome: props.nome }); };
    onMounted(async () => { meta.value = await api("desk.metadados"); carregar(); carregarCk(); carregarTm(); rel = setInterval(() => (agora.value = Date.now()), 1000); });
    onUnmounted(() => clearInterval(rel));
    const esc = (x) => x.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    const html = () => texto.value.trim().split(/\n{2,}/).map((p) => "<p>" + esc(p).replace(/\n/g, "<br>") + "</p>").join("");
    const enviar = async () => {
      if (!texto.value.trim() || aEnviar.value) return; aEnviar.value = true;
      try { await api("desk.responder", { nome: props.nome, html: html(), cc: cc.value }, true); toast("Resposta enviada ao cliente"); texto.value = ""; cc.value = ""; carregar(); }
      catch (e) {} finally { aEnviar.value = false; }
    };
    const mudar = async (campo, valor) => { await api("desk.mudar", { nome: props.nome, campo, valor }, true); toast("Gravado"); carregar(); if (campo === "ticket_type") carregarCk(); };
    const catDe = (e) => ((meta.value?.estados || []).find((x) => x.v === e) || {}).cat;
    const mudarEstado = async (e, ev) => {
      if (catDe(e) === "Resolved") { resolver.value = { estado: e, nota: t.value.resolucao ? t.value.resolucao.replace(/<br>/g, "\n").replace(/<[^>]+>/g, "") : "" }; if (ev) ev.target.value = t.value.estado; return; }
      await api("desk.mudar_estado", { nome: props.nome, estado: e }, true); toast("Estado alterado"); carregar();
    };
    const confirmarResolver = async () => {
      if (!resolver.value.nota.trim()) { toast("Descreva a resolução"); return; }
      await api("desk.mudar_estado", { nome: props.nome, estado: resolver.value.estado, nota: resolver.value.nota }, true);
      resolver.value = null; toast("Ticket resolvido — o cliente recebe o inquérito em dia útil"); carregar();
    };
    const atribuir = async (agente) => { await api("desk.atribuir", { nome: props.nome, agente }, true); toast(agente ? "Atribuído" : "Sem responsável"); carregar(); };
    const modelo = async (r) => { if (!r) return; const x = await api("desk_mais.resposta_modelo", { nome: r, ticket: props.nome });
      r3.value.html = (r3.value.html || "") + ((x && x.message) || ""); r3.value.acoes = (x && x.actions) || []; if (r3.value.acoes.length) toast(r3.value.acoes.length + " ação(ões) do modelo correm ao enviar"); };
    // checklist
    const gravarCk = async () => { ck.value.itens = (await api("desk.gravar_checklist", { nome: props.nome, itens: JSON.stringify(ck.value.itens) }, true)).itens; };
    const marcarPonto = (i) => { i.feito = !i.feito; i.por = i.feito ? (window.__ctx?.utilizador || "") : ""; i.em = i.feito ? new Date().toISOString() : ""; gravarCk(); };
    const juntarPonto = () => { if (!novoPonto.value.trim()) return; ck.value.itens.push({ t: novoPonto.value.trim(), feito: false }); novoPonto.value = ""; gravarCk(); };
    const tirarPonto = (k) => { ck.value.itens.splice(k, 1); gravarCk(); };
    const aplicarModelo = async (m) => { if (!m) return; ck.value.itens = (await api("desk.aplicar_modelo", { nome: props.nome, modelo: m }, true)).itens; toast("Modelo inserido"); };
    const feitos = computed(() => ck.value.itens.filter((i) => i.feito).length);
    // cronómetro (continua se a página fechar: o início fica guardado neste aparelho)
    const chaveCron = () => "orbit.cron." + props.nome;
    const inicio = ref(null); try { inicio.value = Number(localStorage.getItem(chaveCron())) || null; } catch (e) {}
    const decorrido = computed(() => { if (!inicio.value) return ""; const s = Math.max(0, Math.floor((agora.value - inicio.value) / 1000)); const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), x = s % 60; return (h ? h + ":" : "") + String(m).padStart(h ? 2 : 1, "0") + ":" + String(x).padStart(2, "0"); });
    const iniciar = () => { inicio.value = Date.now(); try { localStorage.setItem(chaveCron(), String(inicio.value)); } catch (e) {} };
    const pararCron = () => { const h = Math.max(0.05, Math.round((Date.now() - inicio.value) / 36e5 * 20) / 20); parar.value = { horas: h, descricao: "" }; };
    const registar = async (manual) => {
      const p = parar.value; if (!p.descricao.trim()) { toast("Descreva o que foi feito"); return; }
      await api("desk.registar_tempo", { nome: props.nome, horas: p.horas, descricao: p.descricao }, true);
      if (!manual) { inicio.value = null; try { localStorage.removeItem(chaveCron()); } catch (e) {} }
      parar.value = null; toast("Tempo registado"); carregarTm();
    };
    const fmtH = (h) => { const m = Math.round(Number(h || 0) * 60); return Math.floor(m / 60) + " h " + String(m % 60).padStart(2, "0"); };
    const corEstado = (e) => ({ Open: "azul", Replied: "roxo", Paused: "ambar", Resolved: "verde", Closed: "" })[e] || "";
    const estrelas = (r) => r == null ? "" : r >= 0.9 ? "Bom" : r >= 0.5 ? "Razoável" : "Mau";
    return { r3, contas, ext3, extR, separ, edAssunto, fundir, anexoIn3, enviar3, juntarAnexos3, responderA, dividir, fazerFundir, apagarTicket, gravarAssunto, mudar3, linhaVis, menu3, copiar3, carregarExt3,
      t, meta, modo, texto, cc, aEnviar, enviar, mudar, mudarEstado, resolver, confirmarResolver, atribuir, modelo, data, link,
      ck, novoPonto, marcarPonto, juntarPonto, tirarPonto, aplicarModelo, feitos, inicio, decorrido, iniciar, pararCron, parar, registar, tm, fmtH, corEstado, estrelas, catDe };
  },
  template: `
  <div class="pad desk-ticket" v-if="t && meta">
    <div style="font-size:13px"><a href="#/tickets">← Tickets</a></div>
    <div class="desk-cab">
      <div style="min-width:0"><div class="sub" style="font-size:13px">#{{ t.name }} · aberto {{ data(t.aberto) }} · {{ t.email }}</div>
        <h1 v-if="edAssunto===null" @click="t.pode_editar && (edAssunto=t.assunto)" :title="t.pode_editar ? 'Mudar o assunto' : ''" :style="{cursor: t.pode_editar ? 'text' : 'default'}">{{ t.assunto }}</h1>
        <input v-else class="ed-campo" v-model="edAssunto" style="width:100%;font-size:18px;font-weight:600;margin:4px 0" @keydown.enter="gravarAssunto" @keydown.esc="edAssunto=null" @blur="gravarAssunto" autofocus>
        <div v-if="ext3 && ext3.fundido_em" class="aviso" style="margin:6px 0">Fundido no <a :href="'#/ticket/'+ext3.fundido_em">#{{ ext3.fundido_em }}</a>.</div>
        <div class="desk-chips"><span class="etq" :class="corEstado(t.estado)">{{ (meta.estados.find(e=>e.v===t.estado)||{}).r || t.estado }}</span>
          <span class="etq" :class="{Urgent:'ambar',High:'ambar'}[t.prioridade]">{{ (meta.prioridades.find(e=>e.v===t.prioridade)||{}).r || t.prioridade }}</span>
          <span :class="t.atrasado ? 'etq ambar' : 'etq'">{{ t.sla || 'Sem SLA' }}</span>
          <span v-if="t.inquerito === 'respondido' && t.avaliacao" class="etq" :class="t.avaliacao >= .9 ? 'verde' : t.avaliacao >= .5 ? '' : 'ambar'">Avaliação: {{ estrelas(t.avaliacao) }}</span></div></div>
      <div class="desk-acoes" v-if="t.pode_editar">
        <button v-if="!inicio" class="btn" @click="iniciar"><Icone n="relogio"/> Iniciar cronómetro</button>
        <button v-else class="btn cron-a-correr" @click="pararCron">⏹ {{ decorrido }} · Parar</button>
        <button v-if="t.categoria !== 'Resolved'" class="btn prim" @click="mudarEstado('Resolved')">Resolver</button>
        <button v-else class="btn" @click="mudarEstado('Open')">Reabrir</button>
        <span class="reg-menu" @click.stop><button class="btn" @click="menu3=!menu3" aria-label="Mais ações">⋯</button>
          <div v-if="menu3" class="cartao reg-menu-lista" @click="menu3=false"><button @click="fundir={destino:''}">Fundir noutro ticket…</button><button @click="copiar3">Copiar a ligação</button><button class="perigo" @click="apagarTicket">Apagar o ticket…</button></div></span>
      </div>
    </div>
    <div class="desk-grelha">
      <div class="cartao desk-conversa">
        <div class="vistas" style="padding:0 14px"><button :class="{ativo:separ==='tudo'}" @click="separ='tudo'">Tudo</button><button :class="{ativo:separ==='emails'}" @click="separ='emails'">Emails</button><button :class="{ativo:separ==='comentarios'}" @click="separ='comentarios'">Comentários</button><button :class="{ativo:separ==='historico'}" @click="separ='historico'">Histórico</button></div>
        <div v-if="separ==='historico'" style="padding:14px"><RegistoHistorico doctype="HD Ticket" :name="t.name" :key="'h'+t.name"/></div>
        <div class="desk-linha" v-else>
          <div v-if="!linhaVis.length" class="vazio">Ainda sem mensagens.</div>
          <div v-for="m in linhaVis" :key="m.tipo+m.id" class="cartao msg" :class="{nossa: m.enviado, interno: m.tipo==='comentario'}">
            <header><b>{{ m.tipo==='comentario' ? '🔒 ' + m.quem + ' (interno)' : (m.enviado ? 'Respondemos' : (m.quem || m.de)) }}</b><span>{{ data(m.quando) }}</span></header>
            <div v-if="m.tipo==='email' && t.pode_editar" class="msg-acoes"><button @click="responderA(m,false)">Responder</button><button @click="responderA(m,true)">Responder a todos</button><button v-if="!m.enviado" @click="dividir(m)">Dividir em novo ticket</button></div>
            <div v-if="m.tipo==='email' && !m.enviado" class="sub" style="font-size:12px;margin-bottom:6px">De {{ m.de }}</div>
            <EmailCorpo :html="m.html"/>
            <div v-if="m.anexos && m.anexos.length" class="anexos-mail"><a v-for="a in m.anexos" :key="a.url" class="etq" :href="a.url" target="_blank">📎 {{ a.nome }}</a></div>
          </div>
          <div v-if="t.resolucao" class="cartao msg interno"><header><b>✓ Resolução</b></header><div v-html="t.resolucao"></div></div>
        </div>
        <div class="desk-resposta" v-if="t.pode_editar">
          <div class="vistas" style="padding:0"><button :class="{ativo: modo==='responder'}" @click="modo='responder'">Responder ao cliente</button><button :class="{ativo: modo==='comentar'}" @click="modo='comentar'">Conversa interna</button>
            <select v-if="modo==='responder' && meta.respostas.length" class="btn sm" style="margin-left:auto" @change="modelo($event.target.value); $event.target.value=''"><option value="">Resposta-modelo…</option><option v-for="r in meta.respostas" :key="r.name" :value="r.name">{{ r.title || r.name }}</option></select></div>
          <template v-if="modo==='responder'">
            <div class="desk-env">
              <label v-if="contas.length > 1">De<select v-model="r3.conta"><option v-for="c in contas" :key="c.conta" :value="c.conta">{{ c.email }}</option></select></label>
              <label>Para<input v-model="r3.para" :placeholder="t.email + ' (o cliente do ticket)'"></label>
              <a v-if="!r3.verMais" href="javascript:void 0" class="sub" style="font-size:12px" @click="r3.verMais=true">+ Cc / Bcc</a>
              <template v-else><label>Cc<input v-model="cc"></label><label>Bcc<input v-model="r3.bcc"></label></template>
            </div>
            <div v-if="r3.citar" class="aviso" style="margin:6px 0;display:flex;justify-content:space-between">Com a mensagem citada <a href="javascript:void 0" @click="r3.citar=null">tirar</a></div>
            <EditorRico v-model="r3.html" placeholder="Escreva a resposta ao cliente…"/>
            <div class="fl-linha" style="flex-wrap:wrap;gap:6px">
              <button type="button" class="btn sm" @click="anexoIn3.click()">📎 Anexar</button><input ref="anexoIn3" type="file" multiple style="display:none" @change="juntarAnexos3">
              <span v-for="(x,k) in r3.anexos" :key="x.id" class="reg-chip">{{ x.nome }}<button type="button" @click="r3.anexos.splice(k,1)">×</button></span>
              <span v-if="r3.acoes.length" class="etq" :title="r3.acoes.map(a=>a.action_type+': '+a.label).join('\\n')">{{ r3.acoes.length }} ação(ões) do modelo</span>
              <span class="sub" style="font-size:12px;margin-left:auto">Rascunho guardado neste aparelho</span>
              <button class="btn prim" :disabled="aEnviar" @click="enviar3">{{ aEnviar ? 'A enviar…' : 'Enviar resposta' }}</button></div>
          </template>
          <ConversaRegisto v-else doctype="HD Ticket" :nome="t.name" :key="'cv'+t.name" :compacto="true"/>
        </div>
      </div>
      <aside class="desk-lado">
        <div class="cartao desk-bloco"><div class="bloco-tit" style="margin-top:0">Ticket</div>
          <label class="desk-prop">Estado<select class="ed-campo" :value="t.estado" :disabled="!t.pode_editar" @change="mudarEstado($event.target.value, $event)"><option v-for="e in meta.estados" :key="e.v" :value="e.v">{{ e.r }}</option></select></label>
          <label class="desk-prop">Prioridade<select class="ed-campo" :value="t.prioridade" :disabled="!t.pode_editar" @change="mudar('priority',$event.target.value)"><option v-for="e in meta.prioridades" :key="e.v" :value="e.v">{{ e.r }}</option></select></label>
          <label class="desk-prop">Tipo<select class="ed-campo" :value="t.tipo" :disabled="!t.pode_editar" @change="mudar('ticket_type',$event.target.value)"><option value="">—</option><option v-for="e in meta.tipos" :key="e.v" :value="e.v">{{ e.r }}</option></select></label>
          <label class="desk-prop">Equipa<select class="ed-campo" :value="t.equipa" :disabled="!t.pode_editar" @change="mudar('agent_group',$event.target.value)"><option value="">—</option><option v-for="e in meta.equipas" :key="e" :value="e">{{ e }}</option></select></label>
          <label class="desk-prop" v-if="meta.marcas.length">Marca<select class="ed-campo" :value="t.marca" :disabled="!t.pode_editar" @change="mudar('orbit_marca',$event.target.value)"><option value="">—</option><option v-for="m in meta.marcas" :key="m" :value="m">{{ m }}</option></select></label>
          <label class="desk-prop" v-if="false">Responsável<select class="ed-campo" :value="(t.responsaveis[0]||{}).v || ''" :disabled="!t.pode_editar" @change="atribuir($event.target.value)"><option value="">— ninguém —</option><option v-for="a in meta.agentes" :key="a.v" :value="a.v">{{ a.r }}</option></select></label>
        </div>
        <div class="cartao desk-bloco" v-if="extR"><RegistoLateral doctype="HD Ticket" :name="t.name" :ext="extR" :partes="['atribuir','etiquetas','anexos']" @mudou="carregar"/></div>
        <div class="cartao desk-bloco" v-if="ext3 && ext3.campos.length"><div class="bloco-tit" style="margin-top:0">Campos do ticket</div>
          <label v-for="c in ext3.campos" :key="c.campo" class="desk-prop">{{ c.rotulo }}<span v-if="c.obrigatorio" class="obrig">*</span>
            <select v-if="c.opcoes" class="ed-campo" :value="c.valor||''" :disabled="!t.pode_editar" @change="mudar3(c.campo,$event.target.value)"><option value="">—</option><option v-for="o in c.opcoes" :key="o" :value="o">{{ o }}</option></select>
            <input v-else class="ed-campo" :type="c.tipo==='Date'?'date':['Int','Float','Currency'].includes(c.tipo)?'number':'text'" :value="c.valor||''" :disabled="!t.pode_editar" @change="mudar3(c.campo,$event.target.value)"></label>
        </div>
        <div class="cartao desk-bloco"><div class="bloco-tit" style="margin-top:0;display:flex;justify-content:space-between">Pontos a resolver <span class="sub" v-if="ck.itens.length">{{ feitos }}/{{ ck.itens.length }}</span></div>
          <div v-if="ck.itens.length" class="ck-barra"><i :style="{width: (100*feitos/ck.itens.length)+'%'}"></i></div>
          <div v-for="(i, k) in ck.itens" :key="k" class="ck-linha" :class="{feito:i.feito}"><label><input type="checkbox" :checked="i.feito" :disabled="!t.pode_editar" @change="marcarPonto(i)"> <span>{{ i.t }}</span></label>
            <button v-if="t.pode_editar" class="ck-x" title="Tirar" @click="tirarPonto(k)">×</button></div>
          <div v-if="t.pode_editar" style="display:flex;gap:6px;margin-top:6px"><input class="ed-campo" v-model="novoPonto" placeholder="Novo ponto…" @keyup.enter="juntarPonto" style="flex:1"><button class="btn sm" @click="juntarPonto" :disabled="!novoPonto.trim()">Juntar</button></div>
          <select v-if="t.pode_editar && ck.modelos.length" class="ed-campo" style="margin-top:6px;width:100%" @change="aplicarModelo($event.target.value); $event.target.value=''"><option value="">Inserir modelo…</option><option v-for="m in ck.modelos" :key="m.nome" :value="m.nome">{{ m.nome }} ({{ m.n }})</option></select>
        </div>
        <div class="cartao desk-bloco"><div class="bloco-tit" style="margin-top:0;display:flex;justify-content:space-between">Tempo <span class="sub">{{ fmtH(tm.total) }}</span></div>
          <div v-for="l in tm.linhas.slice(0,4)" :key="l.ts" class="desk-prop" style="font-size:12px"><span class="sub">{{ data(l.from_time,false) }} · {{ l.quem }}</span><span>{{ fmtH(l.hours) }}</span></div>
          <button v-if="t.pode_editar" class="btn sm" style="margin-top:6px" @click="parar = { horas: 0.25, descricao: '', manual: true }">Registar tempo à mão</button>
        </div>
        <div class="cartao desk-bloco"><div class="bloco-tit" style="margin-top:0">Prazos</div>
          <div class="desk-prop"><span class="sub">1.ª resposta</span><span>{{ t.primeira_resposta ? 'feita ' + data(t.primeira_resposta) : (t.resposta_ate ? 'até ' + data(t.resposta_ate) : '—') }}</span></div>
          <div class="desk-prop"><span class="sub">Resolução</span><span>{{ t.resolucao_ate ? 'até ' + data(t.resolucao_ate) : '—' }}</span></div>
          <div class="desk-prop" v-if="t.inquerito"><span class="sub">Inquérito</span><span>{{ {pendente:'por enviar (dia útil)', enviado:'enviado', respondido:'respondido', 'sem-destino':'sem destinatário'}[t.inquerito] || t.inquerito }}</span></div>
          <div v-if="t.avaliacao_texto" class="sub" style="font-size:12px;margin-top:4px">«{{ t.avaliacao_texto }}»</div>
        </div>
        <div class="cartao desk-bloco"><div class="bloco-tit" style="margin-top:0">Cliente</div>
          <template v-if="t.contacto"><a :href="link('Contact', t.contacto.name)" class="pessoa"><AvFoto :email="t.contacto.email_id || t.email" :nome="t.contacto.full_name" :tam="28"/><b>{{ t.contacto.full_name }}</b></a>
            <div class="sub" style="font-size:12px;margin-top:4px">{{ [t.contacto.email_id, t.contacto.mobile_no || t.contacto.phone, t.contacto.company_name].filter(Boolean).join(' · ') }}</div></template>
          <div v-else class="sub">{{ t.email }}</div>
          <label class="desk-prop" style="margin-top:6px">Cliente<select class="ed-campo" :value="t.cliente||''" :disabled="!t.pode_editar" @change="mudar3('customer',$event.target.value)"><option value="">—</option><option v-for="c in (ext3&&ext3.clientes)||[]" :key="c" :value="c">{{ c }}</option></select></label>
          <template v-if="ext3 && ext3.recentes.length"><div class="bloco-tit">Outros tickets deste cliente</div>
            <a v-for="r in ext3.recentes" :key="r.name" :href="'#/ticket/'+r.name" class="reg-anexo"><span><b>#{{ r.name }} {{ r.assunto }}</b><small class="sub">{{ data(r.quando,false) }}</small></span></a></template>
        </div>
      </aside>
    </div>
    <div class="modal-fundo" v-if="resolver" @click.self="resolver=null"><div class="modal" style="max-width:520px"><header><b>Resolver o ticket #{{ t.name }}</b><button class="btn sm" @click="resolver=null">Cancelar</button></header>
      <div style="padding:16px 20px"><p class="sub" style="margin:0 0 8px;font-size:13px">Descreva a resolução (fica no ticket). O cliente recebe depois o inquérito de satisfação, em dia útil, com a opção de reabrir.</p>
        <textarea class="ed-campo" v-model="resolver.nota" rows="5" style="width:100%;box-sizing:border-box" placeholder="O que foi feito para resolver…"></textarea>
        <div style="display:flex;justify-content:flex-end;margin-top:10px"><button class="btn prim" @click="confirmarResolver" :disabled="!resolver.nota.trim()">Marcar como {{ (meta.estados.find(e=>e.v===resolver.estado)||{}).r || 'resolvido' }}</button></div></div></div></div>
    <div class="modal-fundo" v-if="parar" @click.self="parar=null"><div class="modal" style="max-width:460px"><header><b>{{ parar.manual ? 'Registar tempo' : 'Parar o cronómetro' }}</b><button class="btn sm" @click="parar=null">Cancelar</button></header>
      <div style="padding:16px 20px"><label class="desk-prop">Horas<input class="ed-campo" type="number" step="0.05" min="0.05" max="16" v-model.number="parar.horas" style="width:110px"></label>
        <textarea class="ed-campo" v-model="parar.descricao" rows="3" style="width:100%;box-sizing:border-box;margin-top:8px" placeholder="O que foi feito…"></textarea>
        <p class="sub" style="font-size:12px;margin:6px 0 0">Fica no Tempo do Orbit, ligado a este ticket e ao cliente.</p>
        <div style="display:flex;justify-content:flex-end;margin-top:10px"><button class="btn prim" @click="registar(parar.manual)" :disabled="!parar.descricao.trim()">Registar</button></div></div></div></div>
    <div v-if="fundir" class="modal-fundo" @click.self="fundir=null"><div class="modal" style="max-width:440px"><header><b>Fundir o #{{ t.name }} noutro ticket</b><button class="btn sm" @click="fundir=null">Fechar</button></header>
      <form class="reg-form" @submit.prevent="fazerFundir"><label class="erp-campo"><span>N.º do ticket que fica</span><input v-model="fundir.destino" placeholder="ex.: 1234" required autofocus></label>
        <p class="sub" style="font-size:12px;margin:0">As mensagens deste ticket passam para o outro e este fica fechado como «fundido».</p>
        <div class="reg-botoes"><button class="btn prim">Fundir</button></div></form></div></div>
  </div>
  <div v-else class="carregar">A carregar…</div>`,
};
const FichaDetalhes = {
  props: ["doctype", "name"], emits: ["mudou"],
  setup(props, { emit }) {
    const d = ref(null); const ed = ref(""); const valorEd = ref(""); const edMorada = ref(null); const meios = ref(null);
    const carregar = async () => { d.value = await api("detalhes.detalhes", { doctype: props.doctype, name: props.name }); };
    onMounted(carregar);
    const feito = (msg) => { toast(msg || "Gravado"); carregar(); emit("mudou"); };
    const editar = (p) => { if (!p.editavel) return; ed.value = p.campo; valorEd.value = p.valor ?? ""; nextTick(() => document.querySelector(".det .ed-campo")?.focus()); };
    const gravar = async (p) => {
      if (String(valorEd.value ?? "") === String(p.valor ?? "")) { ed.value = ""; return; }
      if (p.campo === "status" && ["CRM Deal", "CRM Lead"].includes(props.doctype)) { const ok = await mudarEstadoCRM(props.doctype, props.name, valorEd.value); ed.value = ""; if (ok) feito(); return; }
      let r; try { r = await api("guardar", { doctype: props.doctype, name: props.name, campo: p.campo, valor: valorEd.value }, true); } catch (e) { return; }
      ed.value = "";
      if (r && r.preenchido && r.preenchido.length) feito("NIPC confirmado no VIES" + (r.nome_vies ? " (" + r.nome_vies + ")" : "") + " — preenchido: " + r.preenchido.join(", ").toLowerCase());
      else if (r && r.valido_vies) feito("NIPC confirmado no VIES" + (r.nome_vies ? ": " + r.nome_vies : ""));
      else feito(r && r.aviso);
    };
    const alternarCheck = async (p) => { if (!p.editavel) return; await api("guardar", { doctype: props.doctype, name: props.name, campo: p.campo, valor: p.valor ? 0 : 1 }, true); feito(); };
    const alternarMarca = async (p, m) => { if (!p.editavel) return; const v = p.valor.includes(m) ? p.valor.filter((x) => x !== m) : p.valor.concat([m]);
      await api("guardar", { doctype: props.doctype, name: props.name, campo: "marcas", valor: JSON.stringify(v) }, true); feito(); };
    const editarMorada = (s) => { if (!d.value.pode_editar) return; edMorada.value = { ...s.morada.valores }; if (!edMorada.value.country) edMorada.value.country = "Portugal"; };
    const gravarMorada = async () => { await api("fiscal.morada", { doctype: props.doctype, name: props.name, valores: JSON.stringify(edMorada.value) }, true); edMorada.value = null; feito("Morada gravada"); };
    const editarMeios = (s) => { if (!d.value.pode_editar) return; const t = (tp) => (s.tabelas.find((x) => x.tipo === tp)?.linhas || []).map((l) => ({ ...l }));
      meios.value = { emails: t("emails"), telefones: t("telefones") }; if (!meios.value.emails.length) meios.value.emails.push({ valor: "", principal: true }); };
    const principal = (lista, i) => lista.forEach((l, j) => (l.principal = j === i));
    const gravarMeios = async () => { try { await api("detalhes.meios", { doctype: props.doctype, name: props.name, emails: JSON.stringify(meios.value.emails), telefones: JSON.stringify(meios.value.telefones) }, true); } catch (e) { return; }
      meios.value = null; feito("Emails e telefones gravados"); };
    const mostra = (p) => {
      if (p.valor === null || p.valor === undefined || p.valor === "") return "—";
      if (p.tipo === "Currency") return eur(p.valor);
      if (p.tipo === "Date" || p.tipo === "Datetime") return data(p.valor, p.tipo === "Datetime");
      if (p.tipo === "Percent") return p.valor + " %";
      return (p.rotulos && p.rotulos[p.valor]) || p.mostra || p.valor;
    };
    return { d, ed, valorEd, edMorada, meios, editar, gravar, alternarCheck, alternarMarca, editarMorada, gravarMorada, editarMeios, principal, gravarMeios, mostra, eur, PAISES_PT };
  },
  template: `
  <div class="det">
    <div v-if="!d" class="carregar">A carregar…</div>
    <section v-else v-for="s in d.secoes" :key="s.titulo" class="cartao det-sec">
      <header><h2>{{ s.titulo }}</h2>
        <button v-if="s.morada && d.pode_editar && !edMorada" class="btn sm" @click="editarMorada(s)">Editar</button>
        <button v-if="s.tabelas.some(t=>t.tipo==='emails') && d.pode_editar && !meios" class="btn sm" @click="editarMeios(s)">Editar</button></header>
      <div class="det-grelha">
        <div v-for="p in s.campos" :key="p.campo" class="det-campo" :class="{largo: p.largo}">
          <label>{{ p.rotulo }}</label>
          <div v-if="p.tipo==='Marcas'" class="marcas-chips"><button v-for="m in p.opcoes" :key="m" class="etq" :class="{on: p.valor.includes(m)}" :disabled="!p.editavel" @click="alternarMarca(p, m)">{{ m }}</button></div>
          <label v-else-if="p.tipo==='Check'" class="det-check"><input type="checkbox" :checked="!!p.valor" :disabled="!p.editavel" @change="alternarCheck(p)"> {{ p.valor ? 'Sim' : 'Não' }}</label>
          <template v-else-if="ed===p.campo">
            <select v-if="p.opcoes" class="ed-campo" v-model="valorEd" @change="gravar(p)" @blur="ed=''"><option v-for="o in p.opcoes" :key="o" :value="o">{{ (p.rotulos && p.rotulos[o]) || o || '—' }}</option></select>
            <textarea v-else-if="p.tipo==='Text'" class="ed-campo" rows="3" v-model="valorEd" @keyup.esc="ed=''" @blur="gravar(p)"></textarea>
            <input v-else class="ed-campo" v-model="valorEd" :type="p.tipo==='Date'?'date':['Currency','Percent','Number'].includes(p.tipo)?'number':'text'" :placeholder="p.tipo==='Fiscal' ? (doctype==='Contact' ? 'NIF (9 dígitos)' : 'NIPC — confirma no VIES') : ''" @keyup.enter="gravar(p)" @keyup.esc="ed=''" @blur="gravar(p)">
          </template>
          <div v-else class="det-valor" :class="{ed: p.editavel, 'det-vazio': mostra(p)==='—'}" @click="editar(p)">{{ mostra(p) }}<span v-if="p.tipo==='Fiscal' && p.valor && doctype==='CRM Organization'" class="sub" style="font-size:11px"> · VIES</span></div>
        </div>
        <template v-if="s.morada">
          <template v-if="edMorada">
            <div v-for="c in s.morada.campos" :key="c.campo" class="det-campo"><label>{{ c.rotulo }}</label>
              <select v-if="c.campo==='country'" class="ed-campo" v-model="edMorada.country"><option v-for="pa in d.paises" :key="pa" :value="pa">{{ PAISES_PT[pa] || pa }}</option></select>
              <input v-else class="ed-campo" v-model="edMorada[c.campo]" :placeholder="c.campo==='pincode' ? '0000-000' : ''" @keyup.enter="gravarMorada" @keyup.esc="edMorada=null"></div>
            <div class="det-campo largo" style="display:flex;gap:6px;justify-content:flex-end"><button class="btn sm" @click="edMorada=null">Cancelar</button><button class="btn sm prim" @click="gravarMorada">Gravar morada</button></div>
          </template>
          <template v-else>
            <div v-for="c in s.morada.campos" :key="c.campo" class="det-campo" :class="{largo: c.campo==='address_line1'}"><label>{{ c.rotulo }}</label>
              <div class="det-valor" :class="{ed: d.pode_editar, 'det-vazio': !s.morada.valores[c.campo]}" @click="editarMorada(s)">{{ c.campo==='country' ? (PAISES_PT[s.morada.valores.country] || s.morada.valores.country || '—') : (s.morada.valores[c.campo] || '—') }}</div></div>
          </template>
        </template>
      </div>
      <template v-for="t in s.tabelas" :key="t.tipo">
        <template v-if="t.tipo==='produtos'">
          <div v-if="!t.linhas.length" class="sub" style="padding:4px 0 8px">Sem produtos.</div>
          <table v-else class="det-tab"><thead><tr><th>Artigo</th><th>Qtd.</th><th>Preço</th><th>Desconto</th><th>Total</th></tr></thead>
            <tbody><tr v-for="(l,i) in t.linhas" :key="i"><td>{{ l.artigo }}</td><td>{{ l.qtd }}</td><td>{{ eur(l.preco||0) }}</td><td>{{ l.desconto ? l.desconto + ' %' : '—' }}</td><td>{{ eur(l.total||0) }}</td></tr></tbody></table>
        </template>
        <div v-else-if="!meios" class="det-meios"><b>{{ t.tipo==='emails' ? 'Emails' : 'Telefones' }}</b>
          <div v-if="!t.linhas.length" class="sub">—</div>
          <div v-for="(l,i) in t.linhas" :key="i" class="det-meio">{{ l.valor }} <span v-if="l.principal" class="etq verde" style="font-size:11px">principal</span><span v-if="t.tipo==='telefones'" class="sub" style="font-size:11px"> · {{ l.movel ? 'telemóvel' : 'fixo' }}</span></div>
        </div>
      </template>
      <div v-if="meios && s.tabelas.some(t=>t.tipo==='emails')" class="det-meios-ed">
        <b>Emails</b>
        <div v-for="(l,i) in meios.emails" :key="'e'+i" class="det-meio-ed"><input class="ed-campo" v-model="l.valor" type="email" placeholder="nome@dominio.pt">
          <label class="sub"><input type="radio" :checked="l.principal" @change="principal(meios.emails, i)"> principal</label><button class="btn sm" @click="meios.emails.splice(i,1)">✕</button></div>
        <button class="btn sm" @click="meios.emails.push({valor:'',principal:!meios.emails.length})">+ Email</button>
        <b style="margin-top:10px">Telefones</b>
        <div v-for="(l,i) in meios.telefones" :key="'t'+i" class="det-meio-ed"><input class="ed-campo" v-model="l.valor" placeholder="+351 …">
          <select class="ed-campo" style="flex:none;width:120px" v-model="l.movel"><option :value="true">Telemóvel</option><option :value="false">Fixo</option></select>
          <label class="sub"><input type="checkbox" v-model="l.principal"> principal</label><button class="btn sm" @click="meios.telefones.splice(i,1)">✕</button></div>
        <button class="btn sm" @click="meios.telefones.push({valor:'',principal:false,movel:true})">+ Telefone</button>
        <div style="display:flex;gap:6px;justify-content:flex-end;margin-top:10px"><button class="btn sm" @click="meios=null">Cancelar</button><button class="btn sm prim" @click="gravarMeios">Gravar</button></div>
      </div>
    </section>
  </div>`,
};
const Ficha = {
  components: { FichaDetalhes, Icone, EmailCorpo, VerDocumento, EnviarAssinatura, NovoEmail, ConversaRegisto },
  props: ["doctype", "name"],
  setup(props) {
    const f = ref(null); const cron = ref(null); const filtro = ref(""); const ed = ref(""); const valorEd = ref("");
    const notaTxt = ref(""); const tarefaTxt = ref(""); const tarefaData = ref(""); const modo = ref("nota"); const email = ref(null);
    const docs = ref(null); const verDoc = ref(null);
    const carregar = async () => {
      f.value = await api("ficha", { doctype: props.doctype, name: props.name });
      carregarCron();
      carregarAssin();
      apiTm("do_registo", { doctype: props.doctype, name: props.name }).then((r) => (tempo.value = r)).catch(() => {});
      apiV("do_registo", { doctype: props.doctype, name: props.name }).then((r) => (vendas.value = r)).catch(() => {});
      if (props.doctype === "CRM Deal") apiP("negocio.do_negocio", { negocio: props.name }).then((r) => (orcs.value = r)).catch(() => {});
      carregarConv();
      carregarExt();
    };
    // lote 1 (25-11): «⋯», atribuir, etiquetas, partilhar, anexos e histórico também no CRM
    const ext = ref(null);
    const carregarExt = async () => { ext.value = await apiR("extras", { doctype: props.doctype, name: props.name }).catch(() => null); };
    const apagarRegisto = async () => { if (!confirm("Apagar definitivamente «" + (f.value?.titulo || props.name) + "»? Não se desfaz.")) return;
      await apiR("apagar", { doctype: props.doctype, name: props.name }, true); toast("Apagado");
      location.hash = "#/" + ({ "CRM Lead": "leads", "CRM Deal": "negocios", "Contact": "contactos", "CRM Organization": "empresas" }[props.doctype] || "inicio"); };
    const vendas = ref(null);
    // 25-11-2026: orçamentos do negócio (docs/PLANO-ORCAMENTO-NEGOCIO-ORBIT.md)
    const orcs = ref(null);
    const criarOrcamento = () => { try { sessionStorage.setItem("orbit.novoOrcamento", props.name); } catch (e) {} location.hash = irErp("Quotation", "novo"); };
    const COR_ORC = { Rascunho: "", Enviado: "azul", Respondido: "azul", Encomendado: "verde", "Parcialmente encomendado": "verde", Perdido: "verm", Anulado: "", Expirado: "" };
    const conv = ref(null); const convForm = ref(null); const aConverter = ref(false);
    const carregarConv = async () => { if (props.doctype === "CRM Lead") conv.value = await api("sugestao_conversao", { lead: props.name }); };
    const abrirConversao = async () => { if (!conv.value) await carregarConv();
      convForm.value = { titulo: f.value.titulo, valor: "", fase: (conv.value.fases[0] || {}).name || "", contacto: (conv.value.contactos[0] || {}).name || "", empresa: (conv.value.empresas[0] || {}).name || "" }; };
    const converter = async () => { aConverter.value = true;
      try { const r = await api("converter", { lead: props.name, valor: convForm.value.valor || null, fase: convForm.value.fase, contacto: convForm.value.contacto, empresa: convForm.value.empresa, titulo: convForm.value.titulo }, true);
        toast("Lead convertida em negócio"); convForm.value = null; location.hash = link("CRM Deal", r.negocio); } finally { aConverter.value = false; } };
    const ASSOC = { "Contact": ["CRM Organization", "CRM Deal"], "CRM Organization": ["Contact", "CRM Deal"], "CRM Deal": ["Contact", "CRM Organization"] };
    const pode = (dt) => !!(f.value && f.value.pode_editar !== false && (ASSOC[props.doctype] || []).includes(dt));
    const assocAberta = ref(null); const assocQ = ref(""); const assocRes = ref([]); let tAssoc;
    const abrirAssoc = (dt) => { assocAberta.value = assocAberta.value === dt ? null : dt; assocQ.value = ""; assocRes.value = [];
      nextTick(() => document.querySelector(".assoc-procura input")?.focus()); };
    const procurarAssoc = () => { clearTimeout(tAssoc); tAssoc = setTimeout(async () => { assocRes.value = await api("candidatos", { tipo: assocAberta.value, q: assocQ.value }); }, 250); };
    const ligarAssoc = async (dt, c) => { await api("associar", { doctype: props.doctype, name: props.name, outro_doctype: dt, outro_name: c.name }, true);
      assocAberta.value = null; toast("Associado"); carregar(); };
    const tirarAssoc = async (dt, r) => { if (!confirm("Tirar esta associação? Nenhum registo é apagado.")) return;
      await api("desassociar", { doctype: props.doctype, name: props.name, outro_doctype: dt, outro_name: r.name }, true); toast("Associação retirada"); carregar(); };
    const tornarPrincipal = async (r) => { await api("contacto_principal", { negocio: props.name, contacto: r.name }, true); toast(`${r.full_name || r.name} é agora o contacto principal`); carregar(); };
    const tempo = ref(null);
    const registarTempo = () => { window.__tempo_cliente = (tempo.value && tempo.value.cliente) || ""; };
    const assin = ref(null); const assinar = ref(false);
    const carregarAssin = () => apiS("do_registo", { doctype: props.doctype, name: props.name }).then((r) => (assin.value = r)).catch(() => (assin.value = { itens: [] }));
    const carregarCron = async () => { if (filtro.value === "detalhes" || filtro.value === "conversa") return; cron.value = await api("cronologia", { doctype: props.doctype, name: props.name, tipo: filtro.value }); };
    watch(() => [props.doctype, props.name], () => { f.value = null; cron.value = null; carregar(); });
    watch(filtro, carregarCron);
    onMounted(carregar);
    const editar = (p) => { if (!p.editavel) return; ed.value = p.campo; valorEd.value = p.valor || ""; nextTick(() => document.querySelector(".prop .ed-campo")?.focus()); };
    const gravar = async (p) => {
      if (String(valorEd.value ?? "") === String(p.valor ?? "")) { ed.value = ""; return; }
      // lote 2: passar a «perdido» pede o motivo (como no CRM original)
      if (p.campo === "status" && ["CRM Deal", "CRM Lead"].includes(props.doctype)) { const ok = await mudarEstadoCRM(props.doctype, props.name, valorEd.value); ed.value = ""; if (ok) { toast("Gravado"); carregar(); } return; }
      let r;
      try { r = await api("guardar", { doctype: props.doctype, name: props.name, campo: p.campo, valor: valorEd.value }, true); }
      catch (e) { return; }   // o erro (NIF inválido, VIES…) já apareceu; fica a editar
      ed.value = "";
      // NIF/NIPC: o que o VIES disse e o que preencheu
      if (r && r.preenchido && r.preenchido.length) toast("NIPC confirmado no VIES" + (r.nome_vies ? " (" + r.nome_vies + ")" : "") + " — preenchido: " + r.preenchido.join(", ").toLowerCase());
      else if (r && r.valido_vies) toast("NIPC confirmado no VIES" + (r.nome_vies ? ": " + r.nome_vies : ""));
      else if (r && r.aviso) toast(r.aviso);
      else toast("Gravado");
      carregar();
    };
    // 23-11-2026: caixa (Sim/Não), marcas do contacto e morada
    const alternarCheck = async (p) => { if (!p.editavel) return; await api("guardar", { doctype: props.doctype, name: props.name, campo: p.campo, valor: p.valor ? 0 : 1 }, true); toast("Gravado"); carregar(); };
    const alternarMarca = async (p, m) => {
      if (!p.editavel) return;
      const v = p.valor.includes(m) ? p.valor.filter((x) => x !== m) : p.valor.concat([m]);
      await api("guardar", { doctype: props.doctype, name: props.name, campo: "marcas", valor: JSON.stringify(v) }, true); toast("Gravado"); carregar();
    };
    const edMorada = ref(null);
    const editarMorada = () => { if (!f.value.pode_editar) return; edMorada.value = { ...f.value.morada.valores }; if (!edMorada.value.country) edMorada.value.country = "Portugal"; };
    const gravarMorada = async () => { await api("fiscal.morada", { doctype: props.doctype, name: props.name, valores: JSON.stringify(edMorada.value) }, true); edMorada.value = null; toast("Morada gravada"); carregar(); };
    const enviarNota = async () => {
      if (!notaTxt.value.trim()) return;
      await api("nota", { doctype: props.doctype, name: props.name, conteudo: notaTxt.value }, true);
      notaTxt.value = ""; toast("Nota gravada"); carregarCron();
    };
    const enviarTarefa = async () => {
      if (!tarefaTxt.value.trim()) return;
      await api("tarefa", { doctype: props.doctype, name: props.name, titulo: tarefaTxt.value, data: tarefaData.value || null }, true);
      tarefaTxt.value = ""; tarefaData.value = ""; toast("Tarefa criada"); carregarCron();
    };
    const procurar = async () => {
      const r = await api("procurar_emails", { doctype: props.doctype, name: props.name }, true);
      toast(r.emails.length ? "A procurar nas caixas ligadas… atualize daqui a um minuto." : "Este registo não tem email.");
    };
    const abrirEmail = async (i) => { if (i.tipo !== "email") return; email.value = await api("email_completo", { nome: i.id }, true); };
    const grupos = computed(() => {
      if (!cron.value) return [];
      const g = []; let atual = null;
      for (const i of cron.value.passado) { const m = mes(i.data); if (!atual || atual.mes !== m) { atual = { mes: m, itens: [] }; g.push(atual); } atual.itens.push(i); }
      return g;
    });
    const mudarFase = async (s) => { if (await mudarEstadoCRM("CRM Deal", props.name, s)) { toast("Fase alterada"); carregar(); } };
    const NOMES = { "CRM Deal": "Negócios", "Contact": "Contactos", "CRM Organization": "Empresa", "CRM Lead": "Leads" };
    const tit = (dt, r) => dt === "CRM Deal" ? (r.titulo || r.lead_name || r.organization || r.name) : dt === "Contact" ? (r.full_name || r.name) : dt === "CRM Organization" ? (r.organization_name || r.name) : (r.lead_name || r.name);
    const sub = (dt, r) => dt === "CRM Deal" ? [r.estado, r.deal_value ? eur(r.deal_value) : "", r.expected_closure_date ? "fecha a " + data(r.expected_closure_date, false) : ""].filter(Boolean).join(" · ")
      : dt === "Contact" ? [r.designation, r.email_id].filter(Boolean).join(" · ") : dt === "CRM Organization" ? [r.website, r.territory].filter(Boolean).join(" · ") : [r.estado, r.email].filter(Boolean).join(" · ");
    const ic = (t) => IC_EVENTO[t] || IC_EVENTO.nota;
    const marcarEmail = () => { window.__ref_email = (f.value && f.value.email_principal) || ""; };
    const novoEmail = ref(false);
    // lote 2 (25-11): tarefas/notas que abrem, chamadas registadas, notas fixadas, responder no registo, criar no contexto, imagem
    const tarefaAberta = ref(null), notaAberta = ref(null), chamada = ref(null), resposta = ref(null), fixadasL = ref([]), agendadosL = ref([]);
    const carregarFix = async () => { fixadasL.value = await apiA("fixadas", { doctype: props.doctype, name: props.name }).catch(() => []);
      agendadosL.value = await apiA("agendados", { doctype: props.doctype, name: props.name }).catch(() => []); };
    onMounted(carregarFix);
    const abrirItem = (i) => { if (i.tipo === "tarefa") tarefaAberta.value = { id: i.id }; else if (i.tipo === "nota") notaAberta.value = { id: i.id }; else abrirEmail(i); };
    const depoisAtividade = () => { carregarCron(); carregarFix(); };
    // «Ligar»: regista a chamada ao tocar e, ao voltar ao Orbit, pergunta «Como correu a chamada?» (orbit/chamadas_crm.py)
    const ligar = async () => {
      const num = f.value.telefone; if (!num) return;
      let nome = null;
      try { nome = await api("orbit.chamadas_crm.iniciar", { chave: Date.now().toString(36) + Math.random().toString(36).slice(2, 8), numero: num, doctype: props.doctype, name: props.name }, true); } catch (e) {}
      if (nome) { const volta = () => { if (document.visibilityState === "visible") { document.removeEventListener("visibilitychange", volta); setTimeout(() => (chamada.value = { pendente: nome }), 400); } };
        document.addEventListener("visibilitychange", volta); setTimeout(() => { if (!chamada.value && document.visibilityState === "visible") { document.removeEventListener("visibilitychange", volta); chamada.value = { pendente: nome }; } }, 4000); }
      location.href = "tel:" + num;
    };
    const responder = (todos) => { const e = email.value; if (!e) return;
      const eu = (window.__ctx?.utilizador || "").toLowerCase(); const sep = (x) => String(x || "").split(/[,;]/).map((y) => y.trim()).filter(Boolean);
      const para = sep(e.de).concat(todos ? sep(e.para) : []).filter((x) => !eu || !x.toLowerCase().includes(eu));
      resposta.value = { para: [...new Set(para)].join(", "), cc: todos ? e.cc || "" : "", assunto: /^re:/i.test(e.assunto || "") ? e.assunto : "Re: " + (e.assunto || ""),
        citacao: `<p></p><blockquote type="cite">${e.html || ""}</blockquote>`, responder_a: e.id }; email.value = null; };
    const agendadoAcao = async (x, acao) => { if (acao === "cancelar" && !confirm("Cancelar o envio deste email?")) return; await apiA("agendado_acao", { id: x.id, acao }, true); toast(acao === "enviar" ? "A enviar" : "Envio cancelado"); carregarFix(); carregarCron(); };
    const novoNegocio = async () => { const t = prompt("Nome do negócio", f.value.titulo || ""); if (t === null) return;
      const r = await apiA("novo_negocio", { doctype: props.doctype, name: props.name, titulo: t }, true); toast("Negócio criado"); location.hash = link("CRM Deal", r.name); };
    const novoContacto = ref(null);
    const gravarContacto = async () => { const c = novoContacto.value; if (!c.nome.trim()) return;
      await apiA("novo_contacto", { negocio: props.name, nome: c.nome, apelido: c.apelido, email: c.email, telemovel: c.telemovel }, true); novoContacto.value = null; toast("Contacto criado e associado"); carregar(); };
    const fotoIn = ref(null);
    const trocarFoto = async (ev) => { const fi = ev.target.files?.[0]; if (!fi) return;
      const url = await carregarFicheiro(fi, { doctype: props.doctype, docname: props.name, privado: 0 }); await apiA("imagem", { doctype: props.doctype, name: props.name, url }, true); toast("Imagem gravada"); ev.target.value = ""; carregar(); };
    const tirarFoto = async () => { await apiA("imagem", { doctype: props.doctype, name: props.name, url: "" }, true); toast("Imagem retirada"); carregar(); };
    return { tarefaAberta, notaAberta, chamada, resposta, fixadasL, agendadosL, abrirItem, depoisAtividade, ligar, responder, agendadoAcao, novoNegocio, novoContacto, gravarContacto, fotoIn, trocarFoto, tirarFoto, ext, carregarExt, apagarRegisto, orcs, criarOrcamento, COR_ORC, irErp, tornarPrincipal, PAISES_PT, alternarCheck, alternarMarca, edMorada, editarMorada, gravarMorada, novoEmail, conv, convForm, aConverter, abrirConversao, converter, pode, assocAberta, assocQ, assocRes, abrirAssoc, procurarAssoc, ligarAssoc, tirarAssoc, vendas, COR_V, tempo, registarTempo, fmtH, assin, assinar, carregarAssin, COR_EST, docs, verDoc, marcarEmail, f, cron, filtro, ed, valorEd, editar, gravar, notaTxt, tarefaTxt, tarefaData, modo, enviarNota, enviarTarefa, procurar, abrirEmail, email,
      grupos, mudarFase, NOMES, tit, sub, link, data, eur, ic, cor, ESTADO_COR };
  },
  template: `
  <div class="ficha" v-if="f">
    <aside class="col-esq">
      <div style="font-size:13px;display:flex;justify-content:space-between;align-items:center"><a href="javascript:history.back()">← Voltar</a>
        <RegistoMenu v-if="ext" :doctype="doctype" :name="name" :ext="ext" :apagar="true" :rota-novo="false" @recarregar="carregarExt" @apagado="apagarRegisto"/></div>
      <div class="cabeca">
        <div class="foto-reg" :class="{editavel: f.pode_editar && doctype!=='CRM Deal'}" @click="f.pode_editar && doctype!=='CRM Deal' && fotoIn.click()" :title="f.pode_editar && doctype!=='CRM Deal' ? 'Trocar a imagem' : ''">
          <img v-if="f.imagem" :src="f.imagem" alt="" class="av-img"><AvFoto v-else :email="f.email_principal || emailDoSite((f.props.find(p=>p.campo==='website') || {}).valor)" :nome="f.titulo" :tam="56"/></div>
        <input ref="fotoIn" type="file" accept="image/*" style="display:none" @change="trocarFoto">
        <a v-if="f.imagem && f.pode_editar" href="javascript:void 0" class="sub" style="font-size:11px" @click="tirarFoto">tirar imagem</a>
        <h1>{{ f.titulo }}</h1><div class="sub">{{ f.sub }}</div>
        <div class="acoes-rap">
          <button @click="modo='nota'"><span><Icone n="nota"/></span>Nota</button>
          <button @click="novoEmail=true"><span><Icone n="mail"/></span>Email</button>
          <a v-if="f.telefone" :href="'tel:'+f.telefone" @click.prevent="ligar" style="all:unset;cursor:pointer;display:flex;flex-direction:column;align-items:center;gap:5px;font-size:12px;color:var(--ink-2)"><span style="width:36px;height:36px;border-radius:50%;border:1px solid var(--line);display:grid;place-items:center;background:var(--surface-2)"><Icone n="tel"/></span>Ligar</a>
          <button @click="modo='tarefa'"><span><Icone n="tarefa"/></span>Tarefa</button>
          <button @click="filtro='conversa'"><span><Icone n="chat"/></span>Conversa</button>
          <a :href="'#/calendario/nova/'+encodeURIComponent(doctype)+'/'+encodeURIComponent(name)" @click="marcarEmail" style="all:unset;cursor:pointer;display:flex;flex-direction:column;align-items:center;gap:5px;font-size:12px;color:var(--ink-2)"><span style="width:36px;height:36px;border-radius:50%;border:1px solid var(--line);display:grid;place-items:center;background:var(--surface-2)"><Icone n="cal"/></span>Reunião</a>
        </div>
      </div>
      <div v-if="doctype==='CRM Lead'" style="margin-top:14px">
        <button class="btn prim" style="width:100%" @click="abrirConversao">{{ conv && conv.negocios && conv.negocios.length ? 'Converter de novo' : 'Converter em negócio' }}</button>
        <div v-if="conv && conv.negocios && conv.negocios.length" class="sub" style="font-size:12px;margin-top:6px">Já convertida: <a v-for="n in conv.negocios" :key="n" :href="link('CRM Deal',n)" style="margin-right:6px">{{ n }}</a></div>
      </div>
      <div v-if="f.estados.length" style="margin-top:14px">
        <label class="sub" style="font-size:12px">Fase do negócio</label>
        <div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:6px">
          <button v-for="s in f.estados" :key="s.name" class="btn sm" :class="{prim: f.props.find(p=>p.campo==='status')?.valor===s.name}" @click="mudarFase(s.name)" :disabled="!f.pode_editar">{{ s.rotulo }}</button>
        </div>
      </div>
      <div class="bloco-tit">Sobre este registo</div>
      <template v-for="(p, i) in f.props" :key="p.campo">
      <template v-if="f.morada && p.secao && !(f.props[i-1] || {}).secao">
        <div class="bloco-tit" style="display:flex;justify-content:space-between;align-items:center">Morada
          <button v-if="f.pode_editar && !edMorada" class="btn sm" @click="editarMorada">Editar</button></div>
        <template v-if="edMorada">
          <div class="prop" v-for="c in f.morada.campos" :key="c.campo"><label>{{ c.rotulo }}</label>
            <select v-if="c.campo==='country'" class="ed-campo" v-model="edMorada.country"><option v-for="pa in f.morada.paises" :key="pa" :value="pa">{{ PAISES_PT[pa] || pa }}</option></select>
            <input v-else class="ed-campo" v-model="edMorada[c.campo]" :placeholder="c.campo==='pincode' ? '0000-000' : ''" @keyup.enter="gravarMorada" @keyup.esc="edMorada=null"></div>
          <div style="display:flex;gap:6px;justify-content:flex-end;margin:6px 0 10px"><button class="btn sm" @click="edMorada=null">Cancelar</button><button class="btn sm prim" @click="gravarMorada">Gravar morada</button></div>
        </template>
        <div v-else class="prop" :class="{ed:f.pode_editar}" @click="editarMorada" style="cursor:pointer">
          <div v-if="f.morada.valores.address_line1 || f.morada.valores.city" style="line-height:1.45">
            <div>{{ f.morada.valores.address_line1 }}</div><div v-if="f.morada.valores.address_line2">{{ f.morada.valores.address_line2 }}</div>
            <div>{{ [f.morada.valores.pincode, f.morada.valores.city].filter(Boolean).join(' ') }}</div>
            <div class="sub">{{ PAISES_PT[f.morada.valores.country] || f.morada.valores.country }}</div></div>
          <div v-else class="sub">Sem morada{{ f.pode_editar ? ' — clique para acrescentar' : '' }}</div>
        </div>
      </template>
      <div v-if="p.secao && p.secao !== (f.props[i-1] || {}).secao" class="bloco-tit">{{ p.secao }}</div>
      <div class="prop">
        <label>{{ p.rotulo }}</label>
        <template v-if="ed===p.campo">
          <select v-if="p.opcoes" class="ed-campo" v-model="valorEd" @change="gravar(p)" @blur="ed=''"><option v-for="o in p.opcoes" :value="o">{{ p.rotulos[o] || o || '—' }}</option></select>
          <textarea v-else-if="p.tipo==='Text'" class="ed-campo" rows="3" v-model="valorEd" @keyup.esc="ed=''" @blur="gravar(p)" style="width:100%"></textarea>
          <input v-else class="ed-campo" v-model="valorEd" :type="p.tipo==='Date'?'date':(p.tipo==='Currency'||p.tipo==='Percent'||p.tipo==='Number')?'number':'text'" :placeholder="p.tipo==='Fiscal' ? (doctype==='Contact' ? 'NIF (9 dígitos)' : 'NIPC — confirma no VIES') : ''" @keyup.enter="gravar(p)" @keyup.esc="ed=''" @blur="gravar(p)">
        </template>
        <div v-else-if="p.tipo==='Marcas'" class="marcas-chips">
          <button v-for="m in p.opcoes" :key="m" class="etq" :class="{on: p.valor.includes(m)}" :disabled="!p.editavel" @click="alternarMarca(p, m)">{{ m }}</button>
          <span v-if="!p.opcoes.length" class="sub">Sem marcas definidas</span>
        </div>
        <div v-else-if="p.tipo==='Check'" :class="{ed:p.editavel}" @click="alternarCheck(p)">{{ p.valor ? 'Sim' : 'Não' }}</div>
        <div v-else :class="{ed:p.editavel}" @click="editar(p)">
          <span v-if="p.tipo==='Currency'">{{ p.valor ? eur(p.valor) : '—' }}</span>
          <span v-else-if="p.tipo==='Fiscal'">{{ p.valor || '—' }}<span v-if="p.valor && doctype==='CRM Organization'" class="sub" style="font-size:11px"> · VIES</span></span>
          <span v-else-if="p.tipo==='Datetime'||p.tipo==='Date'">{{ p.valor ? data(p.valor, p.tipo==='Datetime') : '—' }}</span>
          <span v-else-if="p.tipo==='Percent'">{{ p.valor!=null ? p.valor+' %' : '—' }}</span>
          <span v-else>{{ (p.rotulos && p.rotulos[p.valor]) || p.mostra || p.valor || '—' }}</span>
        </div>
      </div>
      </template>
      <template v-if="f.morada && !f.props.some(x => x.secao)">
        <div class="bloco-tit" style="display:flex;justify-content:space-between;align-items:center">Morada
          <button v-if="f.pode_editar && !edMorada" class="btn sm" @click="editarMorada">Editar</button></div>
        <template v-if="edMorada">
          <div class="prop" v-for="c in f.morada.campos" :key="c.campo"><label>{{ c.rotulo }}</label>
            <select v-if="c.campo==='country'" class="ed-campo" v-model="edMorada.country"><option v-for="pa in f.morada.paises" :key="pa" :value="pa">{{ PAISES_PT[pa] || pa }}</option></select>
            <input v-else class="ed-campo" v-model="edMorada[c.campo]" :placeholder="c.campo==='pincode' ? '0000-000' : ''" @keyup.enter="gravarMorada" @keyup.esc="edMorada=null"></div>
          <div style="display:flex;gap:6px;justify-content:flex-end;margin:6px 0 10px"><button class="btn sm" @click="edMorada=null">Cancelar</button><button class="btn sm prim" @click="gravarMorada">Gravar morada</button></div>
        </template>
        <div v-else class="prop" :class="{ed:f.pode_editar}" @click="editarMorada" style="cursor:pointer">
          <div v-if="f.morada.valores.address_line1 || f.morada.valores.city" style="line-height:1.45">
            <div>{{ f.morada.valores.address_line1 }}</div><div v-if="f.morada.valores.address_line2">{{ f.morada.valores.address_line2 }}</div>
            <div>{{ [f.morada.valores.pincode, f.morada.valores.city].filter(Boolean).join(' ') }}</div>
            <div class="sub">{{ PAISES_PT[f.morada.valores.country] || f.morada.valores.country }}</div></div>
          <div v-else class="sub">Sem morada{{ f.pode_editar ? ' — clique para acrescentar' : '' }}</div>
        </div>
      </template>
    </aside>

    <div class="col-meio">
      <div class="separ">
        <button :class="{ativo:filtro===''}" @click="filtro=''">Atividade</button>
        <button :class="{ativo:filtro==='detalhes'}" @click="filtro='detalhes'">Detalhes</button>
        <button :class="{ativo:filtro==='emails'}" @click="filtro='emails'">Emails <span class="sub">{{ cron?.contagem?.email || '' }}</span></button>
        <button :class="{ativo:filtro==='conversa'}" @click="filtro='conversa'">Conversa <span class="sub">{{ cron?.contagem?.comentario || '' }}</span></button>
        <button :class="{ativo:filtro==='notas'}" @click="filtro='notas'">Notas</button>
        <button :class="{ativo:filtro==='chamadas'}" @click="filtro='chamadas'">Chamadas</button>
        <button :class="{ativo:filtro==='tarefas'}" @click="filtro='tarefas'">Tarefas</button>
        <button :class="{ativo:filtro==='reunioes'}" @click="filtro='reunioes'">Reuniões</button>
        <button :class="{ativo:filtro==='tickets'}" @click="filtro='tickets'">Tickets</button>
        <button :class="{ativo:filtro==='anexos'}" @click="filtro='anexos'">Anexos <span class="sub">{{ ext?.anexos?.length || '' }}</span></button>
        <button :class="{ativo:filtro==='historico'}" @click="filtro='historico'">Histórico</button>
      </div>
      <FichaDetalhes v-if="filtro==='detalhes'" :doctype="doctype" :name="name" :key="doctype+name" @mudou="carregar"/>
      <ConversaRegisto v-else-if="filtro==='conversa'" :doctype="doctype" :nome="name" :key="'c'+doctype+name"/>
      <RegistoHistorico v-else-if="filtro==='historico'" :doctype="doctype" :name="name" :key="'h'+doctype+name"/>
      <div v-else-if="filtro==='anexos'" class="cartao" style="padding:14px"><RegistoLateral v-if="ext" :doctype="doctype" :name="name" :ext="ext" :partes="['anexos']"/></div>
      <template v-else>
      <div class="cartao compor" v-if="modo==='nota'"><textarea v-model="notaTxt" rows="1" :placeholder="'Escrever uma nota sobre ' + f.titulo + '…'" @keydown.meta.enter="enviarNota" @keydown.ctrl.enter="enviarNota"></textarea><button class="btn sm" @click="notaAberta={}" title="Com título e formatação">Aa</button><button class="btn sm prim" @click="enviarNota" :disabled="!notaTxt.trim()">Gravar nota</button></div>
      <div class="cartao compor" v-else><input v-model="tarefaTxt" placeholder="Nova tarefa…" @keyup.enter="enviarTarefa"><input type="date" v-model="tarefaData" style="flex:none;width:150px"><button class="btn sm" @click="tarefaAberta={inicial:{titulo:tarefaTxt,data:tarefaData}}" title="Responsável, prioridade, hora e descrição">Mais…</button><button class="btn sm prim" @click="enviarTarefa" :disabled="!tarefaTxt.trim()">Criar tarefa</button></div>
      <div v-if="filtro==='chamadas'" style="margin:-4px 0 10px"><button class="btn sm" @click="chamada={}">+ Registar chamada</button></div>
      <div v-for="x in agendadosL" :key="x.id" class="aviso" style="margin:0 0 10px;display:flex;gap:8px;align-items:center;flex-wrap:wrap">📅 Email agendado para {{ data(x.quando) }}: <b>{{ x.assunto }}</b><span style="margin-left:auto;display:flex;gap:6px"><button class="btn sm" @click="agendadoAcao(x,'enviar')">Enviar já</button><button class="btn sm" @click="agendadoAcao(x,'cancelar')">Cancelar</button></span></div>
      <div v-for="n in fixadasL" :key="n.id" class="cartao nota-fixa" @click="notaAberta={id:n.id}"><b>📌 {{ n.titulo }}</b><div class="rico-ver" v-html="n.html"></div><small class="sub">{{ n.quem }} · {{ data(n.quando) }}</small></div>
      <div v-if="!cron" class="carregar">A carregar…</div>
      <template v-else>
        <template v-if="cron.proximos.length"><div class="mes">Próximo</div>
          <div class="evento" v-for="i in cron.proximos" :key="i.tipo+i.id"><div class="ic" :style="{background:ic(i.tipo)[1],color:ic(i.tipo)[2]}"><Icone :n="ic(i.tipo)[0]"/></div>
            <div class="cartao corpo abre" @click="abrirItem(i)"><header><b>{{ i.titulo }}</b><span :class="i.atrasada?'etq ambar':'sub'">{{ i.atrasada ? 'Atrasada · ' : '' }}{{ data(i.data) }}</span></header><p v-if="i.texto">{{ i.texto }}</p><p v-if="i.quem" class="sub">{{ i.quem }}</p></div></div>
        </template>
        <div v-if="!grupos.length && !cron.proximos.length" class="vazio">Ainda não há atividade.<br><button class="btn sm" style="margin-top:10px" @click="procurar">Procurar emails antigos nas caixas ligadas</button></div>
        <template v-for="g in grupos" :key="g.mes"><div class="mes">{{ g.mes }}</div>
          <div class="evento" v-for="i in g.itens" :key="i.tipo+i.id"><div class="ic" :style="{background:ic(i.tipo)[1],color:ic(i.tipo)[2]}"><Icone :n="ic(i.tipo)[0]"/></div>
            <div class="cartao corpo" :class="{abre:['email','tarefa','nota'].includes(i.tipo)}" @click="abrirItem(i)">
              <header><b><template v-if="i.tipo==='email'">{{ i.sentido==='Sent' ? 'Email enviado: ' : 'Email recebido: ' }}</template>{{ i.titulo }}</b>
                <span class="sub">{{ data(i.data) }}<template v-if="i.duracao"> · {{ Math.round(i.duracao/60) }} min</template></span></header>
              <p v-if="i.tipo==='email'" class="sub" style="margin-top:2px">{{ i.sentido==='Sent' ? 'Para ' + (i.para||'') : 'De ' + (i.quem||'') }}<template v-if="i.conta"> · {{ i.conta }}</template> <span v-if="i.privado" class="priv">· só para si</span> <span v-if="i.sentido==='Sent' && i.lido" class="etq verde" style="font-size:11px">Aberto</span></p>
              <p v-if="i.texto">{{ i.texto }}</p>
              <p v-if="i.tipo!=='email' && i.quem" class="sub">{{ i.quem }}</p>
              <span v-if="i.tipo==='ticket'" class="etq" :class="i.resolvido?'verde':'ambar'">{{ i.estado }}</span>
            </div></div>
        </template>
        <div v-if="grupos.length" style="text-align:center;margin:16px 0"><button class="btn sm" @click="procurar">Procurar emails antigos nas caixas ligadas</button></div>
      </template>
      </template>
    </div>

    <aside class="col-dir">
      <RegistoLateral v-if="ext" :doctype="doctype" :name="name" :ext="ext" :partes="['atribuir','etiquetas','partilha']" class="reg-crm"/>
      <template v-for="(lista, dt) in f.assoc" :key="dt">
        <template v-if="lista.length || dt!=='CRM Lead'">
          <div class="bloco-tit">{{ NOMES[dt] }} <span class="sub" style="font-weight:400"><template v-if="pode(dt)"><template v-if="(dt==='CRM Deal' && ['Contact','CRM Organization'].includes(doctype)) || (dt==='Contact' && doctype==='CRM Deal')"><a href="#" @click.prevent="dt==='CRM Deal' ? novoNegocio() : (novoContacto={nome:'',apelido:'',email:'',telemovel:''})">+ Novo</a> · </template><a href="#" @click.prevent="abrirAssoc(dt)">+ Associar</a> · </template>{{ lista.length }}</span></div>
          <div v-if="assocAberta===dt" class="assoc-procura">
            <input v-model="assocQ" :placeholder="'Procurar ' + NOMES[dt].toLowerCase() + '…'" @input="procurarAssoc" @keydown.esc="assocAberta=null" ref="assocInput">
            <div v-for="c in assocRes" :key="c.name" class="assoc-op" @click="ligarAssoc(dt,c)"><b>{{ c.titulo }}</b><small>{{ c.sub }}</small></div>
            <div v-if="assocQ.length>=2 && !assocRes.length" class="sub" style="font-size:12px;padding:6px">Nada encontrado.</div>
          </div>
          <div v-if="!lista.length" class="sub" style="font-size:13px">—</div>
          <div v-for="r in lista" :key="r.name" class="assoc assoc-linha">
            <a :href="link(dt,r.name)" style="text-decoration:none;color:inherit;min-width:0;flex:1"><b>{{ tit(dt,r) }}</b><small>{{ sub(dt,r) }}</small>
              <div class="barra" v-if="dt==='CRM Deal' && r.probability"><i :style="{width:r.probability+'%'}"></i></div></a>
            <span v-if="doctype==='CRM Deal' && dt==='Contact' && r.principal" class="etq verde" style="font-size:11px;flex:none">principal</span>
            <button v-else-if="doctype==='CRM Deal' && dt==='Contact' && lista.length > 1 && pode(dt)" class="btn sm" style="flex:none" @click="tornarPrincipal(r)">Tornar principal</button>
            <button v-if="pode(dt)" class="tirar" title="Tirar a associação" @click="tirarAssoc(dt,r)">×</button>
          </div>
        </template>
      </template>
      <template v-if="tempo && tempo.cliente">
        <div class="bloco-tit">Tempo <a class="sub" style="font-weight:400" href="#/tempo" @click="registarTempo">+ Registar</a></div>
        <div class="assoc"><b>{{ fmtH(tempo.mes) }} este mês</b><small>{{ fmtH(tempo.tres_meses) }} nos últimos 3 meses</small></div>
        <div v-for="(u,i) in tempo.ultimos" :key="i" class="sub" style="font-size:12px;margin:2px 0 6px">{{ fmtH(u.hours) }} · {{ data(u.from_time,false) }} — {{ (u.description||'').slice(0,60) }}</div>
      </template>
      <template v-if="doctype==='CRM Deal' && orcs && orcs.erp">
        <div class="bloco-tit">Orçamentos <a v-if="orcs.pode_criar" class="sub" style="font-weight:400" href="javascript:void(0)" @click="criarOrcamento">+ Criar orçamento</a></div>
        <div v-if="!orcs.itens.length" class="sub" style="font-size:13px">—</div>
        <div v-for="x in orcs.itens" :key="x.name" class="assoc"><a :href="irErp('Quotation', x.name)" style="text-decoration:none;color:inherit"><b>{{ x.name }}<span v-if="x.versao"> · {{ x.versao }}</span></b></a><small><span class="etq" :class="COR_ORC[x.estado]" style="font-size:11px">{{ x.estado }}</span> · {{ eur(x.valor_negocio || x.sem_iva) }}<span v-if="x.valor_negocio"> (negócio)</span> · {{ data(x.data,false) }} · <a :href="x.pdf" target="_blank">PDF</a><a v-if="x.link_portal" :href="x.link_portal" target="_blank"> · {{ x.ref_portal }}</a></small></div>
      </template>
      <template v-if="vendas && vendas.tem_cliente">
        <div class="bloco-tit">Propostas <a v-if="vendas.nova_proposta" class="sub" style="font-weight:400" :href="vendas.nova_proposta" target="_blank">+ Nova</a></div>
        <div v-if="!vendas.propostas.length" class="sub" style="font-size:13px">—</div>
        <a v-for="x in vendas.propostas" :key="x.ref" class="assoc" :href="x.url" target="_blank" style="display:block;text-decoration:none;color:inherit"><b>{{ x.ref }}</b><small><span class="etq" :class="COR_V[x.estado]" style="font-size:11px">{{ x.estado }}</span> · {{ x.mensal ? eur(x.mensal)+'/mês' + (x.unico ? ' + '+eur(x.unico) : '') : eur(x.valor) }} · {{ data(x.data,false) }}</small></a>
        <div class="bloco-tit">Faturas <span class="sub" style="font-weight:400" :style="vendas.em_divida>0?{color:'var(--acao)'}:{}">{{ vendas.em_divida>0 ? eur(vendas.em_divida)+' em dívida' : vendas.faturas.length }}</span></div>
        <div v-if="!vendas.faturas.length" class="sub" style="font-size:13px">—</div>
        <a v-for="x in vendas.faturas.slice(0,6)" :key="x.ref" class="assoc" :href="x.url" target="_blank" style="display:block;text-decoration:none;color:inherit"><b>{{ x.ref.startsWith('#') ? (x.periodo || 'Fatura') : x.ref }}</b><small><span class="etq" :class="COR_V[x.estado]" style="font-size:11px">{{ x.estado }}</span> · {{ eur(x.valor) }} · {{ data(x.data,false) }}</small></a>
      </template>
      <div class="bloco-tit">Assinaturas <span class="sub" style="font-weight:400;cursor:pointer" @click="assinar=true">+ Enviar</span></div>
      <div v-if="!assin" class="sub" style="font-size:13px">A procurar…</div>
      <div v-else-if="!assin.itens.length" class="sub" style="font-size:13px">—</div>
      <div v-for="x in (assin && assin.itens) || []" :key="x.id" class="assoc"><b>{{ x.modelo }}</b><small><span class="etq" :class="COR_EST[x.estado_c]" style="font-size:11px">{{ x.estado }}</span> · {{ data(x.criado,false) }}<a v-if="x.estado_c==='completed'" :href="'/api/method/orbit.interface.assinaturas.documento?id='+x.id" target="_blank"> · documento</a></small></div>
      <EnviarAssinatura v-if="assinar" :doctype="doctype" :name="name" :email-inicial="f.email_principal" :nome-inicial="doctype==='Contact'?f.titulo:''" @fechar="assinar=false" @enviado="carregarAssin(); carregarCron()"/>
      <div class="bloco-tit">Tickets <span class="sub" style="font-weight:400">{{ f.tickets.length }}</span></div>
      <div v-if="!f.tickets.length" class="sub" style="font-size:13px">—</div>
      <a v-for="t in f.tickets" :key="t.name" class="assoc" :href="'#/ticket/'+encodeURIComponent(t.name)" style="display:block;text-decoration:none;color:inherit"><b>#{{ t.name }} {{ t.subject }}</b><small>{{ t.status }} · {{ data(t.modified,false) }}</small></a>
    </aside>

    <NovoEmail v-if="novoEmail" :doctype="doctype" :name="name" :para="f.email_principal" @fechar="novoEmail=false" @enviado="depoisAtividade()"/>
    <NovoEmail v-if="resposta" :doctype="doctype" :name="name" :resposta="resposta" @fechar="resposta=null" @enviado="depoisAtividade()"/>
    <TarefaForm v-if="tarefaAberta" :id="tarefaAberta.id" :inicial="tarefaAberta.inicial" :doctype="doctype" :name="name" @fechar="tarefaAberta=null; tarefaTxt=''" @gravado="depoisAtividade()"/>
    <NotaForm v-if="notaAberta" :id="notaAberta.id" :doctype="doctype" :name="name" @fechar="notaAberta=null" @gravado="depoisAtividade()"/>
    <ChamadaForm v-if="chamada" :doctype="doctype" :name="name" :pendente="chamada.pendente" :numero="f.telefone" @fechar="chamada=null" @gravado="depoisAtividade()"/>
    <div v-if="novoContacto" class="modal-fundo" @click.self="novoContacto=null"><div class="modal" style="max-width:480px"><header><b>Novo contacto neste negócio</b><button class="btn sm" @click="novoContacto=null">Fechar</button></header>
      <form class="reg-form" @submit.prevent="gravarContacto"><div class="reg-linha3" style="grid-template-columns:1fr 1fr"><label class="erp-campo"><span>Nome<span class="obrig">*</span></span><input v-model="novoContacto.nome" required autofocus></label><label class="erp-campo"><span>Apelido</span><input v-model="novoContacto.apelido"></label></div>
        <label class="erp-campo"><span>Email</span><input type="email" v-model="novoContacto.email"></label><label class="erp-campo"><span>Telemóvel</span><input type="tel" v-model="novoContacto.telemovel"></label>
        <div class="reg-botoes"><button class="btn prim">Criar e associar</button></div></form></div></div>
    <div class="modal-fundo" v-if="convForm" @click.self="convForm=null">
      <div class="modal" style="max-width:520px"><header><b>Converter «{{ f.titulo }}» em negócio</b><button class="btn sm" @click="convForm=null">Fechar</button></header>
        <form class="corpo-email form-cal" @submit.prevent="converter">
          <label>Nome do negócio<input v-model="convForm.titulo" :placeholder="f.titulo"></label>
          <div class="linha3" style="grid-template-columns:1fr 1fr"><label>Valor (€)<input type="number" step="0.01" v-model="convForm.valor"></label>
            <label>Fase<select v-model="convForm.fase"><option v-for="x in conv.fases" :key="x.name" :value="x.name">{{ x.rotulo }}</option></select></label></div>
          <label>Contacto<select v-model="convForm.contacto"><option value="">Criar um contacto novo a partir da lead</option><option v-for="c in conv.contactos" :key="c.name" :value="c.name">Usar o existente: {{ c.titulo }}</option></select></label>
          <label>Empresa<select v-model="convForm.empresa"><option value="">{{ conv.empresa_texto ? 'Criar «' + conv.empresa_texto + '»' : 'Sem empresa' }}</option><option v-for="e in conv.empresas" :key="e.name" :value="e.name">Usar a existente: {{ e.titulo }}</option></select></label>
          <p class="sub" style="font-size:12px;margin:0">A lead fica marcada como convertida; os emails, notas e tarefas dela aparecem no negócio.</p>
          <div style="display:flex;justify-content:flex-end"><button class="btn prim" :disabled="aConverter">{{ aConverter ? 'A converter…' : 'Converter' }}</button></div>
        </form></div>
    </div>
    <div class="modal-fundo" v-if="email" @click.self="email=null">
      <div class="modal"><header><div><b>{{ email.assunto }}</b><div class="sub">De {{ email.de }} · para {{ email.para }}<span v-if="email.cc"> · cc {{ email.cc }}</span> · {{ data(email.data) }}</div></div><div style="display:flex;gap:6px"><button class="btn sm prim" @click="responder(false)">Responder</button><button class="btn sm" @click="responder(true)">Responder a todos</button><button class="btn sm" @click="email=null">Fechar</button></div></header>
        <div class="corpo-email"><EmailCorpo :html="email.html"/></div></div>
    </div>
  </div>
  <div v-else class="carregar">A carregar…</div>`,
};

const Funil = {
  setup() {
    const d = ref(null); const resp = ref(""); const arrastar = ref(null); const alvo = ref("");
    // 23-11-2026: funil dos negócios ou das leads, cada um com o separador da marca da sua lista (partilham a escolha)
    const ler = (k, v) => { try { return localStorage.getItem(k) || v; } catch (e) { return v; } };
    const gravarLS = (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} };
    const tipo = ref(ler("orbit.funil.tipo", "negocios"));
    const marca = ref(ler("orbit.marca." + tipo.value, ""));
    // 27-11-2026: vários funis — o funil escolhido fica gravado por pessoa (como a marca)
    const funilSel = ref(ler("orbit.funil.escolhido", ""));
    const carregar = async () => {
      const r = await api(tipo.value === "leads" ? "funil_leads" : "funil", { responsavel: resp.value, marca: marca.value, ...(tipo.value === "leads" ? {} : { funil: funilSel.value }) });
      if (r && r.funil) funilSel.value = r.funil;
      d.value = r;
    };
    const escolherFunil = (f) => { funilSel.value = f; gravarLS("orbit.funil.escolhido", f); d.value = null; carregar(); };
    const mudarDeFunil = ref(null);
    const passarFunil = async (f) => { const x = mudarDeFunil.value; mudarDeFunil.value = null; if (!x || f === funilSel.value) return;
      try { await api("mudar_funil", { negocio: x.name, funil: f }, true); toast(`«${x.titulo}» passou para o funil «${f}»`); carregar(); } catch (e) {} };
    const valor = computed(() => !d.value || d.value.mostra_valor !== false);
    const escolherMarca = (m) => { marca.value = m; gravarLS("orbit.marca." + tipo.value, m); carregar(); };
    const escolherTipo = (t) => { if (t === tipo.value) return; tipo.value = t; gravarLS("orbit.funil.tipo", t); marca.value = ler("orbit.marca." + t, ""); d.value = null; carregar(); };
    watch(resp, carregar); onMounted(carregar);
    const largar = async (col) => {
      const n = arrastar.value; alvo.value = ""; arrastar.value = null;
      if (!n || n.estado === col.estado) return;
      // lote 2: largar em «Perdido» pede o motivo de perda
      if (!(await mudarEstadoCRM(tipo.value === "leads" ? "CRM Lead" : "CRM Deal", n.name, col.estado))) return;
      toast(`Passou a «${col.rotulo}»`); carregar();
    };
    const total = computed(() => d.value && tipo.value !== "leads" ? d.value.colunas.filter((c) => c.tipo !== "Won").reduce((a, c) => a + c.total, 0) : 0);
    const n = computed(() => d.value ? d.value.colunas.filter((c) => !["Won", "Lost"].includes(c.tipo)).reduce((a, c) => a + c.cartoes.length, 0) : 0);
    // lote 7: criar na coluna, já nessa fase
    const novoNaColuna = async (c) => { const t = prompt(tipo.value === "leads" ? "Nome da lead" : "Nome do negócio"); if (!t) return;
      const r = await api("criar_registo", { objeto: tipo.value === "leads" ? "leads" : "negocios", dados: JSON.stringify(tipo.value === "leads" ? { first_name: t } : { titulo: t, marca: marca.value || "", orbit_funil: funilSel.value || "" }) }, true);
      await apiA("marcar_estado", { doctype: r.doctype, name: r.name, estado: c.estado }, true).catch(() => {}); toast("Criado em «" + c.rotulo + "»"); carregar(); };
    return { d, resp, arrastar, alvo, largar, total, n, eur, link, data, FAIXA, marca, escolherMarca, tipo, escolherTipo, novoNaColuna,
             funilSel, escolherFunil, mudarDeFunil, passarFunil, valor };
  },
  template: `
  <div>
    <div class="pad" style="padding-bottom:12px;display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap">
      <div><h1>{{ tipo==='leads' ? 'Funil das leads' : (d && (d.funis||[]).length > 1 ? 'Funil — ' + d.funil : 'Funil de negócios') }}</h1><div class="sub" v-if="tipo==='leads'">{{ n }} leads por converter</div><div class="sub" v-else>{{ n }} em curso<template v-if="valor"> · {{ eur(total) }}</template> · ganhos dos últimos 30 dias</div></div>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <select v-if="tipo!=='leads' && d && (d.funis||[]).length > 1" class="btn" :value="funilSel" @change="escolherFunil($event.target.value)" title="Funil"><option v-for="f in d.funis" :key="f.name" :value="f.name">{{ f.name }}</option></select>
        <a v-if="tipo!=='leads' && d && d.pode_configurar" class="btn" href="#/definicoes/funis" title="Funis e fases">⚙ Funis</a>
        <div class="seg"><button class="btn" :class="{prim: tipo==='leads'}" @click="escolherTipo('leads')">Leads</button><button class="btn" :class="{prim: tipo==='negocios'}" @click="escolherTipo('negocios')">Negócios</button></div>
        <select class="btn" v-model="resp"><option value="">Todos os responsáveis</option><option value="eu">Só os meus</option></select><a class="btn" :href="tipo==='leads' ? '#/leads' : '#/negocios'">Lista</a></div>
    </div>
    <div class="vistas marcas-sep" v-if="d && (d.marcas||[]).length > 1">
      <button :class="{ativo: !marca}" @click="escolherMarca('')">Todas as marcas</button>
      <button v-for="m in d.marcas" :key="m" :class="{ativo: marca===m}" @click="escolherMarca(m)">{{ m }}</button>
    </div>
    <div v-if="!d" class="carregar">A carregar…</div>
    <div class="funil" v-else :style="{gridTemplateColumns:'repeat('+d.colunas.length+',minmax(230px,1fr))'}">
      <div class="coluna" v-for="c in d.colunas" :key="c.estado" :class="{alvo: alvo===c.estado}"
           @dragover.prevent="alvo=c.estado" @dragleave="alvo=''" @drop.prevent="largar(c)">
        <header><b>{{ c.rotulo }} <span class="sub" style="font-weight:500">{{ c.cartoes.length }}</span></b><small v-if="tipo!=='leads' && valor">{{ eur(c.total) }}</small>
          <button v-if="!['Won','Lost','Converted'].includes(c.tipo)" class="col-mais" :title="tipo==='leads' ? 'Nova lead nesta coluna' : 'Novo negócio nesta fase'" @click="novoNaColuna(c)">+</button><div class="faixa" :style="{background:FAIXA[c.cor]||'#94a3b8'}"></div></header>
        <a class="cartao negocio" v-for="x in c.cartoes" :key="x.name" :href="link(tipo==='leads' ? 'CRM Lead' : 'CRM Deal', x.name)" draggable="true" @dragstart="arrastar={...x, estado:c.estado}" style="display:block;text-decoration:none;color:inherit">
          <h3>{{ x.titulo }}</h3><div class="sub">{{ x.org }}</div>
          <div class="val"><template v-if="tipo!=='leads'"><span v-if="valor">{{ eur(x.valor) }}</span><span v-else></span></template><span v-else class="sub" style="font-size:12px">{{ x.origem }}</span><span class="av" style="width:22px;height:22px;font-size:10px;background:#5b6f7a" :title="x.dono_nome">{{ x.dono }}</span></div>
          <div class="prox" :class="{atraso:x.atraso}" v-if="x.prox">◷ {{ x.prox }}<template v-if="x.prox_data"> · {{ data(x.prox_data,false) }}</template></div>
          <div class="prox" v-else-if="c.tipo!=='Won' && c.tipo!=='Converted'">Sem próxima tarefa<template v-if="x.parado>7"> · {{ x.parado }} dias parado</template></div>
          <button v-if="tipo!=='leads' && d && (d.funis||[]).length > 1" class="btn sm" style="margin-top:6px;font-size:11px" @click.prevent.stop="mudarDeFunil=x">⇄ Mover para outro funil…</button>
        </a>
      </div>
    </div>
    <div class="modal-fundo" v-if="mudarDeFunil" @click.self="mudarDeFunil=null">
      <div class="modal" style="max-width:420px"><header><div><b>Mover para outro funil</b><div class="sub">{{ mudarDeFunil.titulo }} — passa à 1.ª fase do funil novo e fica registado na cronologia.</div></div><button class="btn sm" @click="mudarDeFunil=null">Fechar</button></header>
        <div style="padding:12px 20px 18px;display:grid;gap:8px"><button class="btn" v-for="f in d.funis.filter((f) => f.name !== funilSel)" :key="f.name" @click="passarFunil(f.name)" style="justify-content:flex-start">{{ f.name }}</button></div>
      </div>
    </div>
  </div>`,
};

const Caixa = {
  components: { EmailCorpo, Icone, Compositor, ConversaRegisto },
  props: ["abrirId"],
  setup(props) {
    let c0 = { grupo: "equipa", conta: "" }; try { c0 = JSON.parse(localStorage.getItem("orbit.caixa.canal")) || c0; } catch (e) {}
    const canal = ref(c0); const canais = ref(null); const itens = ref(null); const conv = ref(null);
    const resposta = ref(""); const para = ref(""); const cc = ref(""); const aEnviar = ref(false); const verCc = ref(false);
    // 23-11-2026 (F1 da caixa única): o correio da pessoa por IMAP — pessoal e partilhadas, «lido» de cada um
    const correio = ref(null); const mail = ref(null); const pwdCaixa = ref(""); const aLigar = ref(false); const imagens = ref(false);
    // F2 (23-11-2026): pastas da caixa, responder/reencaminhar, arquivar, mover, apagar, anexos
    const pastaSel = ref(c0.grupo === "correio" ? (c0.pasta || c0.conta) : ""); const pastasCaixa = ref([]);
    const compor = ref(null); const aEnviarMail = ref(false);
    const carregarPastas = async () => { if (canal.value.grupo !== "correio") { pastasCaixa.value = []; return; }
      try { pastasCaixa.value = (await api("correio.pastas_da_caixa", { pasta: canal.value.conta })).pastas || []; } catch (e) { pastasCaixa.value = []; } };
    const mudarPasta = (p) => { pastaSel.value = p; carregar(); };
    const tirarDaLista = (uid) => { itens.value = (itens.value || []).filter((x) => x.id !== uid); mail.value = null; compor.value = null; };
    const acaoMail = async (acao, extra = {}) => {
      const uid = mail.value.uid, pasta = mail.value.pasta;
      await api("correio." + acao, { pasta, uid, ...extra }, true);
      toast(acao === "arquivar" ? "Arquivada" : acao === "apagar" ? "Enviada para o Lixo" : "Movida");
      tirarDaLista(uid); carregarCorreio();
    };
    const comecar = async (modo) => {
      const r = await api("correio.destinatarios", { pasta: mail.value.pasta, uid: mail.value.uid, modo });
      compor.value = { modo, para: r.para || "", cc: r.cc || "", texto: "" };
      nextTick(() => { const t = document.querySelector(".compor-mail textarea"); if (t) t.focus(); });
    };
    const enviarMail = async () => {
      if (!compor.value || !compor.value.para.trim() || aEnviarMail.value) return;
      aEnviarMail.value = true;
      try {
        const r = await api("correio.enviar", { pasta: mail.value.pasta, uid: mail.value.uid, modo: compor.value.modo, para: compor.value.para, cc: compor.value.cc, texto: compor.value.texto }, true);
        toast("Enviada de " + r.de); compor.value = null;
        const it = (itens.value || []).find((x) => x.id === mail.value.uid); if (it) it.respondida = true;
      } finally { aEnviarMail.value = false; }
    };
    const urlAnexo = (i) => "/api/method/orbit.interface.correio.anexo?" + new URLSearchParams({ pasta: mail.value.pasta, uid: mail.value.uid, i });
    // F3 (23-11-2026): o Chat na caixa — conversas com não lidas e resposta no mesmo sítio
    const chat = ref(null); const chatSel = ref(null); const chatMsgs = ref(null); const chatTexto = ref("");
    const carregarChat = async () => { try { chat.value = await apiC("conversas"); if (chat.value?.base) CHAT_BASE = chat.value.base; } catch (e) { chat.value = { ligado: false }; } };
    const chatLista = computed(() => {
      if (!chat.value || !chat.value.ligado) return [];
      const out = (chat.value.directas || []).map((d) => ({ chave: "d" + d.ids.join(), nome: d.nome, por_ler: d.por_ler, ult: d.ult, sel: { ids: d.ids, nome: d.nome } }));
      (chat.value.canais || []).forEach((c) => (c.topicos || []).forEach((t) => out.push({ chave: "c" + c.id + t.nome, nome: "# " + c.nome + " › " + t.nome, por_ler: t.por_ler, ult: t.ult, sel: { canal: c.id, nomeCanal: c.nome, topico: t.nome } })));
      return out.sort((a, b) => (b.por_ler > 0) - (a.por_ler > 0) || b.ult - a.ult).slice(0, 12);
    });
    const abrirChat = async (x) => {
      canal.value = { grupo: "chat", conta: x.chave }; mail.value = null; conv.value = null; chatSel.value = x.sel; chatMsgs.value = null; itens.value = [];
      if (props.abrirId) location.hash = "#/caixa";
      const a = x.sel.ids ? { ids: x.sel.ids.join(",") } : { canal: x.sel.canal, topico: x.sel.topico || "" };
      chatMsgs.value = (await apiC("mensagens", a)).mensagens; x.por_ler = 0; carregarChat();
      nextTick(() => { const m = document.querySelector(".caixa-chat-msgs"); if (m) m.scrollTop = m.scrollHeight; });
    };
    const enviarChat = async () => {
      if (!chatTexto.value.trim() || !chatSel.value) return;
      const s0 = chatSel.value; const a = s0.ids ? { ids: s0.ids.join(",") } : { canal: s0.canal, topico: s0.topico || "geral" };
      await apiC("enviar", { texto: chatTexto.value, ...a }, true); chatTexto.value = "";
      chatMsgs.value = (await apiC("mensagens", a)).mensagens;
      nextTick(() => { const m = document.querySelector(".caixa-chat-msgs"); if (m) m.scrollTop = m.scrollHeight; });
    };
    const horaChat = (ts) => { const d = new Date(ts * 1000); return d.toDateString() === new Date().toDateString() ? d.toLocaleTimeString("pt-PT", { hour: "2-digit", minute: "2-digit" }) : d.toLocaleDateString("pt-PT", { day: "2-digit", month: "2-digit" }) + " " + d.toLocaleTimeString("pt-PT", { hour: "2-digit", minute: "2-digit" }); };
    const carregarCorreio = async () => { try { correio.value = await api("correio.pastas"); } catch (e) { correio.value = { ligar: false, pastas: [], erro: true }; } };
    const ligarCaixa = async () => { aLigar.value = true; try { await api("calendario.ligar", { pwd: pwdCaixa.value }, true); pwdCaixa.value = ""; toast("Caixa ligada"); await carregarCorreio(); carregar(); } finally { aLigar.value = false; } };
    const carregar = async () => {
      itens.value = null; mail.value = null;
      compor.value = null;
      if (canal.value.grupo === "chat") { itens.value = []; return; }
      if (canal.value.grupo === "correio") {
        const r = await api("correio.lista", { pasta: pastaSel.value || canal.value.conta });
        if (r.ligar) { correio.value = { ligar: true, fora: r.fora || null, pastas: [] }; itens.value = []; return; }
        itens.value = r.itens; return;
      }
      itens.value = await api("caixa", { grupo: canal.value.grupo, conta: canal.value.conta });
    };
    const abrirMail = async (i) => {
      mail.value = { aCarregar: true }; imagens.value = false;
      if (props.abrirId) location.hash = "#/caixa";
      const r = await api("correio.mensagem", { pasta: i.pasta, uid: i.id });
      mail.value = r;
      if (!i.lida) { i.lida = true; i.por_responder = false; const p = (correio.value?.pastas || []).find((x) => x.pasta === i.pasta); if (p && p.por_ler) p.por_ler--; }
    };
    const naoLida = async () => {
      await api("correio.marcar", { pasta: mail.value.pasta, uid: mail.value.uid, lida: 0 }, true);
      const it = (itens.value || []).find((x) => x.id === mail.value.uid); if (it) { it.lida = false; it.por_responder = true; }
      const p = (correio.value?.pastas || []).find((x) => x.pasta === mail.value.pasta); if (p) p.por_ler++;
      mail.value = null; toast("Marcada como não lida");
    };
    const htmlMail = computed(() => !mail.value || !mail.value.html ? "" : (imagens.value ? mail.value.html.replace(/data-orbit-src=/g, "src=") : mail.value.html));
    const tamanho = (b) => b > 1048576 ? (b / 1048576).toFixed(1) + " MB" : Math.max(1, Math.round(b / 1024)) + " KB";
    // 22-11-2026: a atribuição passa do Orbit Mail para aqui — um responsável por conversa, com aviso do Frappe.
    const equipa = ref([]); const aAtribuir = ref(false);
    const atribuir = async (u) => {
      if (!conv.value || aAtribuir.value) return;
      aAtribuir.value = true;
      try {
        const r = await api("atribuir_conversa", { nome: conv.value.responder_a, utilizador: u || "" }, true);
        conv.value.responsavel = r.responsavel; conv.value.responsavel_nome = r.responsavel_nome;
        toast(r.responsavel ? "Atribuída a " + (r.responsavel_nome || r.responsavel) : "Sem responsável");
        carregar();
      } finally { aAtribuir.value = false; }
    };
    const escolher = (grupo, conta = "") => { canal.value = { grupo, conta }; pastaSel.value = grupo === "correio" ? conta : ""; chatSel.value = null; try { localStorage.setItem("orbit.caixa.canal", JSON.stringify(canal.value)); } catch (e) {} carregarPastas(); carregar(); };
    const abrirConversa = async (id) => {
      conv.value = null; resposta.value = ""; cc.value = ""; verCc.value = false;
      conv.value = await api("conversa", { nome: id });
      para.value = conv.value.para || "";
      nextTick(() => { const m = document.querySelector(".msgs"); if (m) m.scrollTop = m.scrollHeight; });
    };
    const abrir = (i) => { if (i.tipo === "mail") { abrirMail(i); return; } if (i.tipo === "ticket") { location.hash = "#/ticket/" + encodeURIComponent(i.id || String(i.url || "").split("/").pop()); return; } location.hash = "#/caixa/" + encodeURIComponent(i.id); };
    watch(() => props.abrirId, (id) => { if (id) abrirConversa(id); });
    let relChat;
    onMounted(async () => { if (canal.value.grupo === "chat") canal.value = { grupo: "equipa", conta: "" };
      canais.value = await api("canais"); carregarCorreio(); carregarPastas(); carregar(); carregarChat(); if (props.abrirId) abrirConversa(props.abrirId); equipa.value = await api("equipa_atribuir");
      relChat = setInterval(() => { if (!document.hidden) carregarChat(); }, 30000); });
    onUnmounted(() => clearInterval(relChat));
    const esc = (t) => t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    const enviar = async () => {
      if (!resposta.value.trim() || aEnviar.value) return;
      aEnviar.value = true;
      try {
        const html = resposta.value.trim().split(/\n{2,}/).map((p) => "<p>" + esc(p).replace(/\n/g, "<br>") + "</p>").join("");
        await api("responder", { nome: conv.value.responder_a, html, para: para.value, cc: cc.value }, true);
        toast("Resposta enviada de " + conv.value.de);
        resposta.value = ""; await abrirConversa(conv.value.responder_a); carregar();
      } finally { aEnviar.value = false; }
    };
    const ativo = (g, c = "") => canal.value.grupo === g && (canal.value.conta || "") === c;
    const nomeCanal = computed(() => {
      const c = canal.value; if (c.grupo === "tickets") return "Tickets do Desk";
      if (c.grupo === "chat") return chatSel.value ? (chatSel.value.ids ? chatSel.value.nome : "# " + chatSel.value.nomeCanal + " › " + chatSel.value.topico) : "Chat";
      if (c.grupo === "correio") { const p = (correio.value?.pastas || []).find((x) => x.pasta === c.conta); return p ? (p.pessoal ? "Entrada · " + p.email : p.email) : "Correio"; }
      if (c.conta === "minhas") return "Atribuídas a mim";
      if (c.conta) return c.conta.replace("Orbit CRM · ", "");
      return c.grupo === "privado" ? "As minhas conversas" : "Todas as caixas de equipa";
    });
    return { canal, canais, itens, conv, abrir, data, cor, ini, link, resposta, para, cc, verCc, enviar, aEnviar, escolher, ativo, nomeCanal, equipa, atribuir, aAtribuir,
      correio, mail, pwdCaixa, aLigar, ligarCaixa, naoLida, htmlMail, imagens, tamanho,
      pastaSel, pastasCaixa, mudarPasta, acaoMail, compor, comecar, enviarMail, aEnviarMail, urlAnexo,
      chat, chatLista, chatSel, chatMsgs, chatTexto, abrirChat, enviarChat, horaChat, textoChat };
  },
  template: `
  <div class="caixa caixa3" :class="{'com-conv': !!abrirId || (!!mail && !mail.aCarregar) || (canal.grupo==='chat' && !!chatSel)}">
    <aside class="canais">
      <h6><span class="ponto-co"></span>Correio <small>como no Orbit Mail</small></h6>
      <template v-if="correio && !correio.ligar">
        <button v-for="p in correio.pastas" :key="p.pasta" :class="{ativo:ativo('correio',p.pasta)}" @click="escolher('correio',p.pasta)" :title="p.email"><span class="txt">{{ p.pessoal ? 'Entrada' : p.nome }}<small v-if="!p.pessoal" class="sub"> · partilhada</small></span><span class="n" v-if="p.por_ler">{{ p.por_ler }}</span></button>
      </template>
      <div v-else-if="correio && correio.ligar && correio.fora && !correio.fora.liga" class="sub" style="font-size:12px;padding:4px 10px">A sua caixa está no {{ correio.fora.nome }}, que não se liga com uma palavra-passe. Peça à Stratechna para a ligar.</div>
      <form v-else-if="correio && correio.ligar" class="ligar-caixa" @submit.prevent="ligarCaixa">
        <p v-if="correio.fora" class="sub" style="font-size:12px;margin:0 0 6px">A sua caixa está no {{ correio.fora.nome }}. Para ver o correio e o calendário aqui, crie uma <b>palavra-passe de aplicação</b> em {{ correio.fora.onde }} e escreva-a aqui (a de entrada no {{ correio.fora.nome }} não serve). Fica guardada cifrada no seu Orbit.</p>
        <p v-else class="sub" style="font-size:12px;margin:0 0 6px">Para ver o seu correio aqui, confirme uma vez a palavra-passe da sua caixa. Fica guardada cifrada no seu Orbit.</p>
        <input type="password" v-model="pwdCaixa" :autocomplete="correio.fora ? 'off' : 'current-password'" :placeholder="correio.fora ? 'Palavra-passe de aplicação do ' + correio.fora.nome : 'Palavra-passe da caixa'" class="filtro" style="border-style:solid;width:100%">
        <button class="btn sm prim" style="margin-top:6px" :disabled="!pwdCaixa || aLigar">{{ aLigar ? 'A ligar…' : 'Ligar a caixa' }}</button>
      </form>
      <div v-else class="sub" style="font-size:12px;padding:4px 10px">A carregar…</div>
      <h6><span class="ponto-ch"></span>Chat <small v-if="chat && chat.ligado"><a href="#/chat" style="color:inherit">abrir</a></small></h6>
      <template v-if="chat && chat.ligado"><button v-for="x in chatLista" :key="x.chave" :class="{ativo:ativo('chat',x.chave)}" @click="abrirChat(x)"><span class="txt">{{ x.nome }}</span><span class="n" v-if="x.por_ler">{{ x.por_ler }}</span></button>
        <p class="sub" v-if="!chatLista.length" style="font-size:12px;padding:0 10px">Sem conversas recentes.</p></template>
      <p class="sub" v-else-if="chat" style="font-size:12px;padding:0 10px">O Chat ainda não está ligado: <a href="#/chat">ligar</a>.</p>
      <h6><span class="ponto-eq"></span>Equipa</h6>
      <button :class="{ativo:ativo('equipa')}" @click="escolher('equipa')">Todas as caixas de equipa</button>
      <button v-for="c in canais?.equipa||[]" :key="c.conta" :class="{ativo:ativo('equipa',c.conta)}" @click="escolher('equipa',c.conta)"><span class="txt">{{ c.email }}</span><span class="n" v-if="c.n">{{ c.n }}</span></button>
      <button :class="{ativo:ativo('tickets','tickets')}" @click="escolher('tickets','tickets')"><span class="txt">Tickets do Desk</span><span class="n" v-if="canais?.tickets">{{ canais.tickets }}</span></button>
      <button :class="{ativo:ativo('todos','minhas')}" @click="escolher('todos','minhas')"><span class="txt">Atribuídas a mim</span></button>
      <h6><span class="ponto-pr"></span>Privado <small>só você vê</small></h6>
      <button :class="{ativo:ativo('privado')}" @click="escolher('privado')">As minhas conversas</button>
      <button v-for="c in canais?.privado||[]" :key="c.conta" :class="{ativo:ativo('privado',c.conta)}" @click="escolher('privado',c.conta)"><span class="txt">{{ c.email }}</span><span class="n" v-if="c.n">{{ c.n }}</span></button>
      <p class="sub" v-if="canais && !canais.privado.length" style="font-size:12px;padding:0 10px">A sua caixa pessoal ainda não está ligada ao CRM («só para mim»): liga-se no portal, em Stratechna Orbit.</p>
    </aside>
    <div class="lista-conv">
      <header><div style="display:flex;justify-content:space-between;align-items:center;gap:8px"><h2 style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ nomeCanal }}</h2><span class="sub" v-if="itens && canal.grupo!=='chat'">{{ itens.length }}</span></div>
        <select v-if="canal.grupo==='correio' && pastasCaixa.length" class="filtro" style="border-style:solid;margin-top:6px;width:100%" :value="pastaSel" @change="mudarPasta($event.target.value)">
          <option v-for="p in pastasCaixa" :key="p.pasta" :value="p.pasta">{{ p.nome }}</option></select>
        <div class="sub" style="font-size:12px;margin-top:4px">{{ canal.grupo==='chat' ? 'Stratechna Chat — o que lê aqui fica lido no Chat.' : canal.grupo==='correio' ? 'Como no Orbit Mail: o que faz aqui fica feito lá.' : canal.grupo==='privado' ? 'Conversas da sua caixa com clientes do CRM — só você as vê.' : canal.grupo==='tickets' ? 'Pedidos de suporte em aberto.' : 'Conversas partilhadas — toda a equipa as vê.' }}</div></header>
      <div v-if="!itens" class="carregar">A carregar…</div>
      <div v-else-if="!itens.length" class="vazio">Nada por aqui.</div>
      <div v-for="i in itens || []" :key="i.tipo+i.id" class="conv" :class="{ativo: abrirId===i.id || (mail && mail.uid===i.id), nova: i.por_responder}" @click="abrir(i)">
        <AvFoto :email="i.email" :nome="i.quem" :tam="30"/>
        <div style="min-width:0"><div class="linha1"><b>{{ i.quem }}</b><time>{{ data(i.data,false) }}</time></div><p>{{ i.titulo }}</p>
          <div class="meta" v-if="i.tipo==='mail'"><span v-if="!i.lida" class="etq azul">Por ler</span><span v-if="i.respondida" class="sub" style="font-size:12px">↩ respondida</span><span v-if="i.anexos" class="sub" style="font-size:12px">📎</span></div>
          <div class="meta" v-else><span class="etq" :class="i.tipo==='ticket'?'ambar':i.grupo==='privado'?'roxo':'azul'">{{ i.tipo==='ticket' ? 'Ticket · ' + i.estado : i.grupo==='privado' ? 'Privado' : 'Equipa' }}</span>
            <span class="sub" style="font-size:12px" v-if="i.ref_titulo">{{ i.ref_titulo }}</span><span class="sub" style="font-size:12px" v-if="i.n>1">· {{ i.n }}</span>
            <span class="etq" v-if="i.responsavel_nome" :title="'Responsável: ' + i.responsavel_nome">👤 {{ i.responsavel_nome }}</span></div></div>
      </div>
    </div>
    <div class="fio">
      <template v-if="mail && !mail.aCarregar && mail.html !== undefined">
        <header><a class="voltar-conv" href="#" @click.prevent="mail=null">← Mensagens</a><div style="min-width:0"><h2>{{ mail.assunto }}</h2><div class="sub">{{ data(mail.data) }}</div></div>
          <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center">
            <button class="btn sm prim" @click="comecar('responder')">Responder</button>
            <button class="btn sm" @click="comecar('todos')">Responder a todos</button>
            <button class="btn sm" @click="comecar('reencaminhar')">Reencaminhar</button>
            <button class="btn sm" @click="acaoMail('arquivar')">Arquivar</button>
            <select class="btn sm" style="padding:4px 6px" @change="$event.target.value && acaoMail('mover', { destino: $event.target.value })">
              <option value="">Mover para…</option><option v-for="p in pastasCaixa.filter(x => x.pasta !== mail.pasta)" :key="p.pasta" :value="p.pasta">{{ p.nome }}</option></select>
            <button class="btn sm" @click="acaoMail('apagar')" title="Para o Lixo desta caixa">Apagar</button>
            <button class="btn sm" @click="naoLida">Marcar como não lida</button></div></header>
        <div class="msgs">
          <div class="cartao msg">
            <header><span style="display:flex;align-items:center;gap:8px"><AvFoto :email="mail.email" :nome="mail.de" :tam="28"/><b>{{ mail.de }}</b> <span class="sub" style="font-size:12px">{{ mail.email }}</span></span><span>{{ data(mail.data) }}</span></header>
            <div class="sub" style="font-size:12px;margin-bottom:8px">Para {{ mail.para }}<template v-if="mail.cc"> · cc {{ mail.cc }}</template></div>
            <div v-if="mail.imagens_externas && !imagens" class="aviso-img"><span class="sub">As imagens externas estão bloqueadas.</span> <button class="btn sm" @click="imagens=true">Mostrar imagens</button></div>
            <EmailCorpo :html="htmlMail"/>
            <div v-if="mail.anexos.length" class="anexos-mail"><span class="sub">Anexos:</span> <a v-for="(a, k) in mail.anexos" :key="k" class="etq" :href="urlAnexo(k)" target="_blank">📎 {{ a.nome }} · {{ tamanho(a.tamanho) }}</a></div>
          </div>
        </div>
        <div class="cartao resposta compor-mail" v-if="compor">
          <div class="tabs" style="flex-wrap:wrap;align-items:center"><span class="sub">{{ compor.modo==='reencaminhar' ? 'Reencaminhar para' : 'Para' }}</span>
            <input v-model="compor.para" style="flex:1;min-width:180px;border:0;background:none;font:inherit;color:var(--ink);outline:none"></div>
          <div class="tabs"><span class="sub">Cc</span><input v-model="compor.cc" style="flex:1;border:0;background:none;font:inherit;color:var(--ink);outline:none"></div>
          <textarea v-model="compor.texto" rows="6" placeholder="Escrever a resposta…" @keydown.meta.enter.prevent="enviarMail" @keydown.ctrl.enter.prevent="enviarMail"></textarea>
          <footer><span class="sub">Sai da caixa da mensagem e fica nos Enviados dela · a mensagem original vai citada<template v-if="compor.modo==='reencaminhar'"> com os anexos</template> · ⌘↵ envia</span>
            <span style="display:flex;gap:6px"><button class="btn sm" @click="compor=null">Cancelar</button><button class="btn prim sm" @click="enviarMail" :disabled="!compor.para.trim() || aEnviarMail">{{ aEnviarMail ? 'A enviar…' : 'Enviar' }}</button></span></footer>
        </div>
      </template>
      <div v-else-if="mail && mail.aCarregar" class="carregar">A carregar…</div>
      <template v-else-if="canal.grupo==='chat' && chatSel">
        <header><a class="voltar-conv" href="#" @click.prevent="chatSel=null">← Voltar</a><div><h2>{{ nomeCanal }}</h2><div class="sub">Stratechna Chat</div></div><a class="btn sm" href="#/chat">Abrir o Chat</a></header>
        <div class="msgs chat-msgs caixa-chat-msgs">
          <div v-if="!chatMsgs" class="carregar">A carregar…</div>
          <div v-for="m in chatMsgs||[]" :key="m.id" class="chat-msg" :class="{meu:m.meu}">
            <AvFoto :email="m.email" :nome="m.quem" :tam="28"/>
            <div><div class="chat-cab"><b>{{ m.quem }}</b><span class="sub">{{ horaChat(m.quando) }}</span></div>
              <div class="chat-txt" v-html="textoChat(m.texto)"></div></div>
          </div>
        </div>
        <div class="cartao resposta">
          <textarea v-model="chatTexto" rows="2" placeholder="Escrever uma mensagem…" @keydown.enter.exact.prevent="enviarChat"></textarea>
          <footer><span class="sub">↵ envia · ⇧↵ nova linha</span><button class="btn prim sm" @click="enviarChat" :disabled="!chatTexto.trim()">Enviar</button></footer>
        </div>
      </template>
      <template v-else-if="conv">
        <header><a class="voltar-conv" href="#/caixa">← Conversas</a><div style="min-width:0"><h2>{{ conv.assunto }}</h2><div class="sub">{{ conv.mensagens.length }} mensagens<template v-if="conv.de"> · caixa {{ conv.de }}</template></div></div>
          <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center">
            <label class="sub" style="display:flex;align-items:center;gap:6px;font-size:12px">Responsável
              <select class="btn sm" style="padding:4px 6px" :value="conv.responsavel || ''" :disabled="aAtribuir" @change="atribuir($event.target.value)">
                <option value="">— ninguém —</option>
                <option v-for="p in equipa" :key="p.email" :value="p.email">{{ p.nome }}</option>
              </select></label>
            <a v-if="conv.ref[0]" class="btn sm" :href="link(conv.ref[0], conv.ref[1])">Abrir {{ conv.ref_titulo }}</a></div></header>
        <div class="msgs">
          <div class="cartao msg" v-for="m in conv.mensagens" :key="m.id" :class="{nossa:m.enviado}">
            <header><b>{{ m.de }}</b><span>{{ data(m.data) }}</span></header>
            <div class="sub" style="font-size:12px;margin-bottom:8px">Para {{ m.para }}<template v-if="m.cc"> · cc {{ m.cc }}</template></div>
            <EmailCorpo :html="m.html"/>
          </div>
        </div>
        <div class="cartao resposta" v-if="conv.pode_responder">
          <div class="tabs" style="flex-wrap:wrap;align-items:center"><span class="sub">De {{ conv.de }} · Para</span>
            <input v-model="para" style="flex:1;min-width:180px;border:0;background:none;font:inherit;color:var(--ink);outline:none">
            <button class="sub" style="all:unset;cursor:pointer;font-size:12px" v-if="!verCc" @click="verCc=true">Cc</button></div>
          <div class="tabs" v-if="verCc"><span class="sub">Cc</span><input v-model="cc" style="flex:1;border:0;background:none;font:inherit;color:var(--ink);outline:none"></div>
          <Compositor v-model="resposta" :doctype="conv.ref[0]" :name="conv.ref[1]" :para="para" :linhas="5" @enviar="enviar"/>
          <footer><span class="sub">Fica nos Enviados de {{ conv.de }} e na cronologia do cliente · ⌘↵ envia</span><button class="btn prim sm" @click="enviar" :disabled="!resposta.trim() || aEnviar">{{ aEnviar ? 'A enviar…' : 'Enviar' }}</button></footer>
        </div>
        <div v-else class="vazio" style="margin:0 20px 20px">Esta conversa é da caixa pessoal de outra pessoa: só ela pode responder.</div>
        <details class="conversa-interna" style="margin:0 20px 20px"><summary class="sub" style="cursor:pointer;font-size:13px">Conversa interna sobre este email (só a equipa vê · @ chama alguém)</summary>
          <ConversaRegisto doctype="Communication" :nome="conv.responder_a" :key="'cv'+conv.responder_a" :compacto="true"/></details>
      </template>
      <div v-else-if="abrirId" class="carregar">A carregar…</div>
      <div v-else class="vazio">Escolha uma conversa.</div>
    </div>
  </div>`,
};


// ── Definições (uma só roda dentada): listas editáveis dentro do Orbit + o resto na secretária ──────────
async function apiDef(metodo, args = {}, post = false) {
  const url = `/api/method/orbit.interface.definicoes.${metodo}`;
  const op = { headers: { "X-Frappe-CSRF-Token": window.csrf_token, Accept: "application/json" } };
  let r;
  if (post) { op.method = "POST"; op.headers["Content-Type"] = "application/json"; op.body = JSON.stringify(args); r = await fetch(url, op); }
  else r = await fetch(url + "?" + new URLSearchParams(args), op);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) { let m = "Erro"; try { m = JSON.parse(JSON.parse(j._server_messages)[0]).message; } catch (e) {} toast(String(m).replace(/<[^>]+>/g, "")); throw new Error(m); }
  return j.message;
}
const Definicoes = {
  // 22-11-2026: cada app mostra só as definições dela (gruposApp = null → todas, na Administração).
  // 23-11-2026 (Vítor): uma só lista, sem repetidos, tudo dentro da interface nova (nada abre no ecrã antigo).
  props: ["gruposApp", "nomeApp"],
  setup(props) {
    const d0 = ref(null); const nat = ref(null);
    onMounted(async () => { [nat.value, d0.value] = await Promise.all([apiDef("indice"), api("definicoes")]); });
    const daApp = (g) => !props.gruposApp || props.gruposApp.includes(g);
    const ORDEM = ["CRM", "Correio", "Atendimento (Desk)", "Marcas e empresa", "Vendas e faturação", "Pessoas e tempo", "Conta e utilizadores", "Avançado"];
    const cartoes = computed(() => {
      if (!nat.value || !d0.value) return null;
      const g = {};
      const junta = (grupo, item) => { (g[grupo] = g[grupo] || []).push(item); };
      nat.value.filter((x) => daApp(x.grupo)).forEach((x) => junta(x.grupo, { href: "#/definicoes/" + x.chave, rotulo: x.titulo, n: x.n }));
      if (daApp("CRM")) { junta("CRM", { href: "#/definicoes/funis", rotulo: "Funis e fases dos negócios" }); junta("CRM", { href: "#/definicoes/fluxos", rotulo: "Fluxos (automatismos)" }); junta("CRM", { href: "#/definicoes/formularios", rotulo: "Formulários (disposição das fichas)" }); junta("CRM", { href: "#/definicoes/campos", rotulo: "Campos personalizados" }); }
      if (daApp("Correio")) junta("Correio", { href: "#/definicoes/caixas", rotulo: "Caixas ligadas ao Orbit" });
      if (!props.gruposApp) junta("Conta e utilizadores", { href: "#/definicoes/utilizadores", rotulo: "Utilizadores do Orbit" });
      if (!props.gruposApp) junta("Conta e utilizadores", { href: "#/definicoes/empresas", rotulo: "Empresas e marcas" });
      d0.value.filter((x) => daApp(x.grupo)).forEach((x) => x.itens.forEach((i) => junta(x.grupo, { href: i.url, rotulo: i.rotulo })));
      return Object.keys(g).sort((a, b) => (ORDEM.indexOf(a) + 99) % 99 - (ORDEM.indexOf(b) + 99) % 99).map((k) => ({ grupo: k, itens: g[k] }));
    });
    return { cartoes };
  },
  template: `
  <div class="pad">
    <div class="ola"><div><h1>Definições{{ nomeApp ? ' — ' + nomeApp : '' }}</h1><div class="sub">{{ gruposApp ? 'Só o que é desta app. O resto está na Administração.' : 'Tudo o que se configura no Orbit, num só sítio.' }}</div></div></div>
    <div v-if="!cartoes" class="carregar">A carregar…</div>
    <div v-else class="grelha-def">
      <div class="cartao" v-for="c in cartoes" :key="c.grupo"><header><h2>{{ c.grupo }}</h2></header>
        <a class="linha" v-for="i in c.itens" :key="i.href" :href="i.href" style="text-decoration:none;color:inherit"><div class="cresce">{{ i.rotulo }}</div><span class="sub">{{ i.n != null ? i.n + ' ' : '' }}›</span></a>
      </div>
    </div>
  </div>`,
};
// ── Campos personalizados do CRM (23-11-2026): criar, mudar o nome/opções, esconder, apagar (orbit/interface/campos.py) ──
const DefCampos = {
  setup() {
    const d = ref(null); const novo = ref(null); const ed = ref(null); const ocupado = ref(false);
    const carregar = async () => { d.value = await api("campos.listar"); };
    onMounted(carregar);
    const porObjeto = computed(() => { const g = {}; (d.value?.objetos || []).forEach((o) => (g[o.v] = [])); (d.value?.campos || []).forEach((c) => (g[c.objeto] = g[c.objeto] || []).push(c)); return g; });
    const rotObj = (v) => (d.value?.objetos.find((o) => o.v === v) || {}).r || v;
    const rotTipo = (v) => (d.value?.tipos.find((o) => o.v === v) || {}).r || v;
    const comecar = (objeto) => { novo.value = { objeto: objeto || "contactos", rotulo: "", tipo: "texto", opcoes: "" }; nextTick(() => document.querySelector(".def-campos input")?.focus()); };
    const linhas = (t) => (t || "").split("\n").map((x) => x.trim()).filter(Boolean);
    const criar = async () => {
      ocupado.value = true;
      try { await api("campos.criar", { objeto: novo.value.objeto, rotulo: novo.value.rotulo, tipo: novo.value.tipo, opcoes: JSON.stringify(linhas(novo.value.opcoes)) }, true);
        toast("Campo criado — já aparece na ficha e nas listas"); novo.value = null; carregar(); } catch (e) {} finally { ocupado.value = false; }
    };
    const editar = (c) => { ed.value = { nome: c.nome, rotulo: c.rotulo, tipo: c.tipo, opcoes: (c.opcoes || []).join("\n") }; };
    const gravar = async () => { try { await api("campos.editar", { nome: ed.value.nome, rotulo: ed.value.rotulo, opcoes: ed.value.tipo === "lista" ? JSON.stringify(linhas(ed.value.opcoes)) : undefined }, true); toast("Gravado"); ed.value = null; carregar(); } catch (e) {} };
    const esconder = async (c) => { await api("campos.editar", { nome: c.nome, oculto: c.oculto ? 0 : 1 }, true); toast(c.oculto ? "Campo visível" : "Campo escondido (os dados ficam)"); carregar(); };
    const apagar = async (c) => { if (!confirm(`Apagar o campo «${c.rotulo}»? Só é possível se nenhum registo o tiver preenchido.`)) return; try { await api("campos.apagar", { nome: c.nome }, true); toast("Apagado"); carregar(); } catch (e) {} };
    return { d, novo, ed, ocupado, porObjeto, rotObj, rotTipo, comecar, criar, editar, gravar, esconder, apagar };
  },
  template: `
  <div class="pad def-campos">
    <div class="ola"><div><div style="font-size:13px"><a href="#/definicoes">← Definições</a></div><h1>Campos personalizados</h1>
      <div class="sub">Campos novos nas Leads, Contactos, Empresas e Negócios. Aparecem na ficha («Sobre este registo») e como colunas e filtros nas listas. Só neste Orbit.</div></div>
      <button class="btn prim" @click="comecar()" v-if="!novo">+ Novo campo</button></div>
    <div v-if="!d" class="carregar">A carregar…</div>
    <template v-else>
      <div class="cartao" v-if="novo" style="margin-bottom:18px;padding:16px">
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px">
          <label class="sub">Em<br><select class="btn" style="width:100%" v-model="novo.objeto"><option v-for="o in d.objetos" :key="o.v" :value="o.v">{{ o.r }}</option></select></label>
          <label class="sub">Nome do campo<br><input class="btn" style="width:100%" v-model="novo.rotulo" placeholder="Ex.: Data de aniversário" @keyup.enter="criar"></label>
          <label class="sub">Tipo<br><select class="btn" style="width:100%" v-model="novo.tipo"><option v-for="t in d.tipos" :key="t.v" :value="t.v">{{ t.r }}</option></select></label>
        </div>
        <label v-if="novo.tipo==='lista'" class="sub" style="display:block;margin-top:12px">Opções (uma por linha)<br><textarea rows="4" style="width:100%" v-model="novo.opcoes"></textarea></label>
        <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px"><button class="btn" @click="novo=null">Cancelar</button><button class="btn prim" :disabled="ocupado || !novo.rotulo.trim()" @click="criar">{{ ocupado ? 'A criar…' : 'Criar campo' }}</button></div>
      </div>
      <div class="grelha-def">
        <div class="cartao" v-for="(lista, obj) in porObjeto" :key="obj"><header style="display:flex;justify-content:space-between;align-items:center"><h2>{{ rotObj(obj) }}</h2><button class="btn sm" @click="comecar(obj)">+ Campo</button></header>
          <div v-if="!lista.length" class="linha sub">Sem campos personalizados.</div>
          <div v-for="c in lista" :key="c.nome" class="linha" style="flex-wrap:wrap;gap:6px">
            <template v-if="ed && ed.nome===c.nome">
              <input class="btn sm" style="flex:1;min-width:140px" v-model="ed.rotulo" @keyup.enter="gravar">
              <textarea v-if="ed.tipo==='lista'" rows="3" style="width:100%" v-model="ed.opcoes"></textarea>
              <button class="btn sm" @click="ed=null">Cancelar</button><button class="btn sm prim" @click="gravar">Gravar</button>
            </template>
            <template v-else>
              <div class="cresce" :style="{opacity: c.oculto ? .5 : 1}">{{ c.rotulo }} <span class="sub">· {{ rotTipo(c.tipo) }}<template v-if="c.opcoes.length"> ({{ c.opcoes.join(', ') }})</template><template v-if="c.oculto"> · escondido</template></span></div>
              <button class="btn sm" @click="editar(c)">Mudar</button><button class="btn sm" @click="esconder(c)">{{ c.oculto ? 'Mostrar' : 'Esconder' }}</button><button class="btn sm" @click="apagar(c)">Apagar</button>
            </template>
          </div>
        </div>
      </div>
    </template>
  </div>`,
};
// ── Funis (27-11-2026): vários funis no CRM, cada um com as suas fases — orbit/interface/funis_api.py ──────────
const DefFunis = {
  setup() {
    const d = ref(null); const aberto = ref(""); const novo = ref(null); const novaFase = ref(null); const ed = ref(null);
    const apagarF = ref(null); const ocupado = ref(false); const arr = ref(null);
    const carregar = async () => { d.value = await api("funis_api.listar"); if (!aberto.value && d.value.funis.length) aberto.value = d.value.funis[0].name; };
    onMounted(carregar);
    const f = computed(() => (d.value?.funis || []).find((x) => x.name === aberto.value));
    const rotTipo = (v) => (d.value?.tipos.find((t) => t.v === v) || {}).r || v;
    const chama = async (metodo, args, msg) => { ocupado.value = true; try { const r = await api("funis_api." + metodo, args, true); if (msg) toast(msg); await carregar(); return r; } catch (e) { return null; } finally { ocupado.value = false; } };
    const comecar = () => { novo.value = { nome: "", modelo: "compras", marcas: [] }; };
    const criar = async () => { const r = await chama("criar", { nome: novo.value.nome, modelo: novo.value.modelo, marcas: JSON.stringify(novo.value.marcas) }, "Funil criado");
      if (r) { aberto.value = r.nome; novo.value = null; } };
    const gravarF = (dados, msg) => chama("gravar", { nome: f.value.name, dados: JSON.stringify(dados) }, msg || "Gravado").then((r) => { if (r && r.nome) aberto.value = r.nome; });
    const mudarNome = () => { const n = prompt("Nome do funil", f.value.name); if (n && n.trim() && n.trim() !== f.value.name) gravarF({ nome: n.trim() }, "Nome mudado"); };
    const alternarMarca = (m) => { const ms = new Set(f.value.marcas); ms.has(m) ? ms.delete(m) : ms.add(m); gravarF({ marcas: [...ms] }, "Marcas gravadas"); };
    const criarFase = async () => { if (await chama("fase_criar", { funil: f.value.name, rotulo: novaFase.value.rotulo, tipo: novaFase.value.tipo, cor: novaFase.value.cor, probabilidade: novaFase.value.prob || 0 }, "Fase criada")) novaFase.value = null; };
    const editar = (x) => { ed.value = { nome: x.name, rotulo: x.rotulo, tipo: x.tipo, cor: x.cor, prob: x.probabilidade }; };
    const gravarFase = async () => { if (await chama("fase_gravar", { nome: ed.value.nome, dados: JSON.stringify({ rotulo: ed.value.rotulo, tipo: ed.value.tipo, cor: ed.value.cor, probabilidade: ed.value.prob }) }, "Fase gravada")) ed.value = null; };
    const apagarFase = (x) => { if (confirm(`Apagar a fase «${x.rotulo}»?`)) chama("fase_apagar", { nome: x.name }, "Fase apagada"); };
    const largar = (alvo) => { const de = arr.value; arr.value = null; if (!de || de === alvo.name) return;
      const nomes = f.value.fases.map((x) => x.name).filter((n) => n !== de); nomes.splice(nomes.indexOf(alvo.name), 0, de);
      chama("fases_ordenar", { funil: f.value.name, nomes: JSON.stringify(nomes) }, "Ordem gravada"); };
    const apagar = async () => { const r = await chama("apagar", { nome: apagarF.value.nome, passar_para: apagarF.value.para || "" });
      if (r) { toast(r.passaram ? `Funil apagado — ${r.passaram} negócio(s) passaram para «${apagarF.value.para}»` : "Funil apagado"); apagarF.value = null; aberto.value = ""; carregar(); } };
    return { d, aberto, f, novo, novaFase, ed, apagarF, ocupado, arr, rotTipo, comecar, criar, gravarF, mudarNome, alternarMarca, criarFase, editar, gravarFase, apagarFase, largar, apagar, FAIXA };
  },
  template: `
  <div class="pad def-funis">
    <div class="ola"><div><div style="font-size:13px"><a href="#/definicoes">← Definições</a></div><h1>Funis</h1>
      <div class="sub">Cada funil tem as suas fases (com uma de ganho e uma de perda). Os negócios das propostas, das lojas e do Booking entram no funil por omissão.</div></div>
      <button class="btn prim" v-if="d && d.pode && !novo" @click="comecar">+ Novo funil</button></div>
    <div v-if="!d" class="carregar">A carregar…</div>
    <template v-else>
      <div v-if="!d.pode" class="sub" style="margin-bottom:12px">Só os administradores do Orbit mudam os funis.</div>
      <div class="cartao" v-if="novo" style="margin-bottom:18px;padding:16px">
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px">
          <label class="sub">Nome do funil<br><input class="btn" style="width:100%" v-model="novo.nome" placeholder="Ex.: Compras" @keyup.enter="criar"></label>
          <label class="sub">Começar a partir de<br><select class="btn" style="width:100%" v-model="novo.modelo"><option v-for="m in d.modelos" :key="m.v" :value="m.v">{{ m.r }}</option></select></label>
        </div>
        <div class="sub" style="margin-top:8px">Fases: {{ (d.modelos.find((m) => m.v===novo.modelo)||{fases:[]}).fases.join(' → ') }} (mudam-se depois)</div>
        <div v-if="d.marcas.length > 1" class="sub" style="margin-top:10px">Marcas (nenhuma = todas):
          <label v-for="m in d.marcas" :key="m" style="margin-left:10px"><input type="checkbox" :value="m" v-model="novo.marcas"> {{ m }}</label></div>
        <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px"><button class="btn" @click="novo=null">Cancelar</button><button class="btn prim" :disabled="ocupado || !novo.nome.trim()" @click="criar">{{ ocupado ? 'A criar…' : 'Criar funil' }}</button></div>
      </div>
      <div class="vistas" style="margin-bottom:14px"><button v-for="x in d.funis" :key="x.name" :class="{ativo: aberto===x.name}" @click="aberto=x.name;ed=null;novaFase=null" :style="{opacity: x.desligado ? .55 : 1}">{{ x.name }}<template v-if="x.por_omissao"> ★</template> <span class="sub">{{ x.abertos }}</span></button></div>
      <div class="cartao" v-if="f" style="padding:0">
        <header style="display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap;padding:14px 16px">
          <div><h2 style="margin:0">{{ f.name }}</h2><div class="sub">{{ f.abertos }} negócio(s) em curso · {{ f.total }} no total<template v-if="f.marcas.length"> · só {{ f.marcas.join(', ') }}</template><template v-else> · todas as marcas</template></div></div>
          <div v-if="d.pode" style="display:flex;gap:6px;flex-wrap:wrap">
            <button class="btn sm" @click="mudarNome">Mudar o nome</button>
            <button class="btn sm" v-if="!f.por_omissao" @click="gravarF({por_omissao:1}, 'Passou a funil por omissão')">Tornar por omissão</button>
            <button class="btn sm" @click="gravarF({mostra_valor: f.mostra_valor ? 0 : 1})">{{ f.mostra_valor ? 'Esconder o valor (€)' : 'Mostrar o valor (€)' }}</button>
            <button class="btn sm" v-if="!f.por_omissao" @click="gravarF({desligado: f.desligado ? 0 : 1}, f.desligado ? 'Funil ligado' : 'Funil desligado (os negócios ficam)')">{{ f.desligado ? 'Ligar' : 'Desligar' }}</button>
            <button class="btn sm" v-if="!f.por_omissao" @click="apagarF={nome:f.name, n:f.total, para:''}">Apagar</button>
          </div>
        </header>
        <div v-if="d.pode && d.marcas.length > 1" class="linha sub" style="flex-wrap:wrap;gap:10px">Marcas:
          <label v-for="m in d.marcas" :key="m"><input type="checkbox" :checked="f.marcas.includes(m)" @change="alternarMarca(m)"> {{ m }}</label><span>(nenhuma = todas)</span></div>
        <div v-for="x in f.fases" :key="x.name" class="linha" style="flex-wrap:wrap;gap:6px" :draggable="d.pode && !ed" @dragstart="arr=x.name" @dragover.prevent @drop.prevent="largar(x)">
          <template v-if="ed && ed.nome===x.name">
            <input class="btn sm" style="flex:1;min-width:140px" v-model="ed.rotulo" @keyup.enter="gravarFase">
            <select class="btn sm" v-model="ed.tipo"><option v-for="t in d.tipos" :key="t.v" :value="t.v">{{ t.r }}</option></select>
            <select class="btn sm" v-model="ed.cor"><option v-for="c in d.cores" :key="c" :value="c">{{ c }}</option></select>
            <label class="sub"><input class="btn sm" type="number" min="0" max="100" style="width:64px" v-model="ed.prob"> %</label>
            <button class="btn sm" @click="ed=null">Cancelar</button><button class="btn sm prim" @click="gravarFase">Gravar</button>
          </template>
          <template v-else>
            <span v-if="d.pode" class="sub" style="cursor:grab" title="Arrastar para mudar a ordem">⋮⋮</span>
            <span style="width:10px;height:10px;border-radius:3px;display:inline-block" :style="{background: FAIXA[x.cor] || '#94a3b8'}"></span>
            <div class="cresce">{{ x.rotulo }} <span class="sub">· {{ rotTipo(x.tipo) }} · {{ x.probabilidade }} % · {{ x.n }} negócio(s)</span></div>
            <template v-if="d.pode"><button class="btn sm" @click="editar(x)">Mudar</button><button class="btn sm" @click="apagarFase(x)" :disabled="x.n > 0" :title="x.n ? 'Tem negócios' : ''">Apagar</button></template>
          </template>
        </div>
        <div class="linha" v-if="d.pode && !novaFase"><button class="btn sm" @click="novaFase={rotulo:'', tipo:'Ongoing', cor:'blue', prob:50}">+ Fase</button></div>
        <div class="linha" v-if="novaFase" style="flex-wrap:wrap;gap:6px">
          <input class="btn sm" style="flex:1;min-width:140px" v-model="novaFase.rotulo" placeholder="Nome da fase" @keyup.enter="criarFase">
          <select class="btn sm" v-model="novaFase.tipo"><option v-for="t in d.tipos" :key="t.v" :value="t.v">{{ t.r }}</option></select>
          <select class="btn sm" v-model="novaFase.cor"><option v-for="c in d.cores" :key="c" :value="c">{{ c }}</option></select>
          <label class="sub"><input class="btn sm" type="number" min="0" max="100" style="width:64px" v-model="novaFase.prob"> %</label>
          <button class="btn sm" @click="novaFase=null">Cancelar</button><button class="btn sm prim" :disabled="ocupado || !novaFase.rotulo.trim()" @click="criarFase">Criar</button>
        </div>
      </div>
      <div class="modal-fundo" v-if="apagarF" @click.self="apagarF=null">
        <div class="modal" style="max-width:460px"><header><b>Apagar o funil «{{ apagarF.nome }}»</b><button class="btn sm" @click="apagarF=null">Fechar</button></header>
          <div style="padding:14px 20px 18px">
            <p v-if="apagarF.n">Tem {{ apagarF.n }} negócio(s). Passam para:</p><p v-else>Não tem negócios. As fases dele também são apagadas.</p>
            <select v-if="apagarF.n" class="btn" style="width:100%" v-model="apagarF.para"><option value="">— escolher —</option><option v-for="x in d.funis.filter((x) => x.name !== apagarF.nome)" :key="x.name" :value="x.name">{{ x.name }}</option></select>
            <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:14px"><button class="btn" @click="apagarF=null">Cancelar</button><button class="btn prim" :disabled="ocupado || (apagarF.n && !apagarF.para)" @click="apagar">Apagar</button></div>
          </div>
        </div>
      </div>
    </template>
  </div>`,
};
// ── Fluxos (23-11-2026): os automatismos do motor do Frappe (Automation Flow) em português — orbit/interface/fluxos_api.py ──
const DefFluxos = {
  setup() {
    const lista = ref(null); const meta = ref(null); const f = ref(null); const mud = ref({}); const runs = ref(null); const aGravar = ref(false);
    const ensaio = ref({ registo: "", res: null, a: false }); const verRuns = ref(false);
    const carregar = async () => { lista.value = await api("fluxos_api.listar"); };
    onMounted(async () => { [meta.value] = await Promise.all([api("fluxos_api.metadados"), carregar()]); });
    const ligar = async (x) => { try { await api("fluxos_api.ligar", { nome: x.name, ativo: x.ativo ? 0 : 1 }, true); toast(x.ativo ? "Fluxo desligado" : "Fluxo ligado"); } catch (e) {} carregar(); if (f.value && f.value.name === x.name) abrir(x); };
    const abrir = async (x) => { mud.value = {}; ensaio.value = { registo: "", res: null, a: false }; f.value = await api("fluxos_api.obter", { nome: x.name }); runs.value = await api("fluxos_api.execucoes", { nome: x.name }); };
    const valor = (p, c) => (mud.value[p.chave] && c.chave in mud.value[p.chave]) ? mud.value[p.chave][c.chave] : c.valor;
    const mudar = (p, c, v) => { mud.value[p.chave] = { ...(mud.value[p.chave] || {}), [c.chave]: v }; };
    const alternarPessoa = (p, c, u) => { const l = [...(valor(p, c) || [])]; const i = l.indexOf(u); if (i >= 0) l.splice(i, 1); else l.push(u); mudar(p, c, l); };
    const gravar = async () => { aGravar.value = true; try { await api("fluxos_api.gravar", { nome: f.value.name, dados: JSON.stringify({ titulo: f.value.titulo, passos: mud.value }) }, true); toast("Fluxo gravado"); await abrir(f.value); carregar(); } catch (e) {} finally { aGravar.value = false; } };
    const experimentar = async () => { ensaio.value.a = true; ensaio.value.res = null; try { ensaio.value.res = await api("fluxos_api.experimentar", { nome: f.value.name, registo: ensaio.value.registo }, true); } catch (e) {} finally { ensaio.value.a = false; } };
    const todosRuns = async () => { f.value = null; verRuns.value = true; runs.value = await api("fluxos_api.execucoes"); };
    const nivel = (p) => { let n = 0, pai = p.pai; while (pai && n < 6) { n++; const q = f.value.passos.find((x) => x.idx === pai); pai = q ? q.pai : 0; } return n; };
    const nomePessoa = (u) => (meta.value?.pessoas.find((x) => x.v === u) || {}).r || u;
    return { lista, meta, f, mud, runs, aGravar, ensaio, verRuns, ligar, abrir, valor, mudar, alternarPessoa, gravar, experimentar, todosRuns, nivel, nomePessoa, data, link };
  },
  template: `
  <div class="pad def-fluxos">
    <div class="ola"><div><div style="font-size:13px"><a href="#/definicoes" v-if="!f && !verRuns">← Definições</a><a href="#" v-else @click.prevent="f=null;verRuns=false">← Fluxos</a></div><h1>{{ f ? f.titulo : 'Fluxos' }}</h1>
      <div class="sub" v-if="!f">Automatismos do CRM: quando algo acontece, se as condições se cumprirem, o Orbit faz os passos. Vêm desligados — ligue os que quer.</div>
      <div class="sub" v-else>{{ f.registo }} · {{ f.quando }}</div></div>
      <button v-if="!f && !verRuns" class="btn" @click="todosRuns">Execuções</button></div>
    <div v-if="!lista || !meta" class="carregar">A carregar…</div>
    <template v-else-if="f">
      <div class="cartao fluxo-ed">
        <div class="fl-linha"><label>Título<input class="ed-campo" v-model="f.titulo"></label>
          <label class="fl-ligado"><span class="interruptor"><input type="checkbox" :checked="f.ativo" @change="ligar(f)"><span></span></span> {{ f.ativo ? 'Ligado' : 'Desligado' }}</label></div>
        <p v-if="f.motivo_desligado" class="sub">Desligado pelo motor: {{ f.motivo_desligado }}</p>
        <p v-if="f.condicao" class="sub" style="font-size:12px">Só corre quando: <code>{{ f.condicao }}</code></p>
        <h3>Passos</h3>
        <div v-for="p in f.passos" :key="p.chave" class="fl-passo" :style="{marginLeft: (nivel(p)*22)+'px'}">
          <div class="fl-linha" style="margin:0"><span v-if="p.ramo" class="etq" :class="p.ramo==='Se sim'?'verde':'ambar'" style="font-size:11px">{{ p.ramo }}</span>
            <b>{{ p.idx }}.</b> <span>{{ p.texto }}</span><span v-if="p.alvo" class="sub" style="font-size:12px">· em «{{ p.alvo }}»</span></div>
          <div v-if="p.tipo==='If' && p.condicao" class="sub" style="font-size:12px;margin-top:2px"><code>{{ p.condicao }}</code></div>
          <div v-for="c in p.campos" :key="c.chave" class="fl-linha" style="margin:6px 0 0">
            <span class="sub" style="min-width:110px">{{ c.rotulo }}</span>
            <div v-if="c.tipo==='pessoas'" class="marcas-chips"><button v-for="u in meta.pessoas" :key="u.v" class="etq" :class="{on:(valor(p,c)||[]).includes(u.v)}" @click="alternarPessoa(p,c,u.v)">{{ u.r }}</button></div>
            <select v-else-if="c.tipo==='modelo'" class="ed-campo" :value="valor(p,c)" @change="mudar(p,c,$event.target.value)"><option v-for="m in meta.modelos_email" :key="m" :value="m">{{ m }}</option></select>
            <select v-else-if="c.tipo==='lista'" class="ed-campo" :value="valor(p,c)" @change="mudar(p,c,$event.target.value)"><option v-for="o in c.opcoes" :key="o.v" :value="o.v">{{ o.r }}</option></select>
            <input v-else class="ed-campo" :type="c.tipo==='numero'?'number':'text'" :value="valor(p,c)" @input="mudar(p,c,$event.target.value)" :style="c.tipo==='numero'?'width:100px':'flex:1'">
          </div>
        </div>
        <div class="fl-linha" style="justify-content:flex-end;margin-top:14px"><button class="btn" @click="f=null">Fechar</button><button class="btn prim" :disabled="aGravar" @click="gravar">{{ aGravar ? 'A gravar…' : 'Gravar' }}</button></div>
        <h3>Experimentar num registo <span class="sub" style="font-weight:400">(corre e desfaz tudo — nada fica gravado nem é enviado)</span></h3>
        <div class="fl-linha"><input class="ed-campo" v-model="ensaio.registo" :placeholder="'Código do registo (ex.: ' + (f.document_type==='CRM Deal' ? 'CRM-DEAL-2026-00111' : 'CRM-LEAD-2026-00125') + ')'" style="flex:1"><button class="btn" :disabled="!ensaio.registo || ensaio.a" @click="experimentar">{{ ensaio.a ? 'A experimentar…' : 'Experimentar' }}</button></div>
        <pre v-if="ensaio.res" class="fl-ensaio">{{ JSON.stringify(ensaio.res, null, 2) }}</pre>
        <h3>Últimas execuções</h3>
        <div v-if="!runs" class="carregar">A carregar…</div><div v-else-if="!runs.length" class="sub">Ainda não correu.</div>
        <div v-for="r in (runs||[]).slice(0,20)" :key="r.name" class="fl-reg"><span :class="r.status==='Success'?'etq verde':r.status==='Skipped'?'etq':'etq ambar'">{{ r.estado }}</span>
          <a :href="link(r.reference_doctype, r.reference_name)">{{ r.reference_name }}</a> <span class="sub">{{ data(r.started_at) }}<template v-if="r.error_summary"> · {{ r.error_summary }}</template></span></div>
      </div>
    </template>
    <template v-else-if="verRuns">
      <div class="cartao" style="padding:14px 18px"><div v-if="!runs" class="carregar">A carregar…</div><div v-else-if="!runs.length" class="sub">Nenhum fluxo correu ainda.</div>
        <div v-for="r in runs||[]" :key="r.name" class="fl-reg"><span :class="r.status==='Success'?'etq verde':r.status==='Skipped'?'etq':'etq ambar'">{{ r.estado }}</span> <b>{{ r.automation_title }}</b> · <a :href="link(r.reference_doctype, r.reference_name)">{{ r.reference_name }}</a> <span class="sub">{{ data(r.started_at) }}<template v-if="r.error_summary"> · {{ r.error_summary }}</template></span></div></div>
    </template>
    <div v-else class="tabela-wrap"><table>
      <thead><tr><th style="width:70px">Ligado</th><th>Fluxo</th><th>Registo</th><th>Quando</th><th>Passos</th><th>Execuções</th></tr></thead>
      <tbody><tr v-for="x in lista" :key="x.name" @click="abrir(x)" style="cursor:pointer">
        <td @click.stop><label class="interruptor"><input type="checkbox" :checked="x.ativo" @change="ligar(x)"><span></span></label></td>
        <td><b>{{ x.titulo }}</b></td><td>{{ x.registo }}</td><td>{{ x.quando }}</td><td>{{ x.passos }}</td><td>{{ x.execucoes }}</td></tr></tbody></table>
      <div v-if="!lista.length" class="vazio">Ainda não há fluxos.</div></div>
  </div>`,
};
// ── Formulários do CRM (23-11-2026): a disposição da ficha — «Detalhes» e o resumo lateral (orbit/interface/formularios.py) ──
const DefFormularios = {
  setup() {
    const dt = ref("CRM Lead"); const parte = ref("detalhes"); const d = ref(null); const aGravar = ref(false); const sujo = ref(false);
    const carregar = async () => { d.value = null; sujo.value = false; d.value = await api("formularios.obter", { doctype: dt.value, parte: parte.value }); };
    onMounted(carregar);
    const escolher = async (novoDt, novaParte) => { if (sujo.value && !confirm("Há alterações por gravar. Continuar sem gravar?")) return; dt.value = novoDt; parte.value = novaParte; carregar(); };
    const usados = computed(() => new Set((d.value?.secoes || []).flatMap((s) => s.campos.map((c) => c.campo))));
    const livres = computed(() => (d.value?.disponiveis || []).filter((c) => !usados.value.has(c.campo)));
    const mexe = () => { sujo.value = true; };
    const moverCampo = (s, i, dir) => { const j = i + dir; if (j < 0 || j >= s.campos.length) return; [s.campos[i], s.campos[j]] = [s.campos[j], s.campos[i]]; mexe(); };
    const passarPara = (s, i, destino) => { const c = s.campos.splice(i, 1)[0]; d.value.secoes[destino].campos.push(c); mexe(); };
    const tirar = (s, i) => { s.campos.splice(i, 1); mexe(); };
    const juntar = (s, campo) => { if (!campo) return; const c = d.value.disponiveis.find((x) => x.campo === campo); s.campos.push({ campo: c.campo, rotulo: c.rotulo }); mexe(); };
    const moverSec = (i, dir) => { const j = i + dir; const l = d.value.secoes; if (j < 0 || j >= l.length) return; [l[i], l[j]] = [l[j], l[i]]; mexe(); };
    const novaSec = () => { d.value.secoes.push({ titulo: "Secção nova", campos: [] }); mexe(); };
    const tirarSec = (i) => { if (d.value.secoes[i].campos.length && !confirm("Os campos desta secção deixam de aparecer na ficha (não se apaga nenhum dado). Continuar?")) return; d.value.secoes.splice(i, 1); mexe(); };
    const gravar = async () => { aGravar.value = true; try { await api("formularios.gravar", { doctype: dt.value, parte: parte.value, secoes_json: JSON.stringify(d.value.secoes.map((s) => ({ titulo: s.titulo, campos: s.campos.map((c) => c.campo) }))) }, true); toast("Formulário gravado — a ficha já o mostra assim"); carregar(); } catch (e) {} finally { aGravar.value = false; } };
    const repor = async () => { if (!confirm("Voltar à disposição de origem do Orbit para este formulário?")) return; await api("formularios.repor", { doctype: dt.value, parte: parte.value }, true); toast("Reposto"); carregar(); };
    return { dt, parte, d, aGravar, sujo, escolher, livres, mexe, moverCampo, passarPara, tirar, juntar, moverSec, novaSec, tirarSec, gravar, repor };
  },
  template: `
  <div class="pad def-form">
    <div class="ola"><div><div style="font-size:13px"><a href="#/definicoes">← Definições</a></div><h1>Formulários</h1>
      <div class="sub">A disposição da ficha de cada registo: as secções e os campos do separador «Detalhes» e do resumo na coluna lateral. Nenhum dado se apaga — só muda o que se mostra e onde.</div></div></div>
    <div class="vistas" style="padding:0;margin-bottom:6px"><button v-for="r in (d?.registos || [{v:'CRM Lead',r:'Leads'},{v:'Contact',r:'Contactos'},{v:'CRM Organization',r:'Empresas'},{v:'CRM Deal',r:'Negócios'}])" :key="r.v" :class="{ativo: dt===r.v}" @click="escolher(r.v, parte)">{{ r.r }}</button></div>
    <div class="vistas" style="padding:0;margin-bottom:14px"><button :class="{ativo: parte==='detalhes'}" @click="escolher(dt,'detalhes')">Separador «Detalhes»</button><button :class="{ativo: parte==='resumo'}" @click="escolher(dt,'resumo')">Resumo lateral («Sobre este registo»)</button></div>
    <div v-if="!d" class="carregar">A carregar…</div>
    <template v-else>
      <div v-for="(s,si) in d.secoes" :key="si" class="cartao form-sec">
        <header class="fl-linha"><input class="ed-campo form-titulo" v-model="s.titulo" @input="mexe">
          <span style="margin-left:auto;display:flex;gap:4px"><button class="btn sm" @click="moverSec(si,-1)" :disabled="si===0" title="Subir a secção">↑</button><button class="btn sm" @click="moverSec(si,1)" :disabled="si===d.secoes.length-1" title="Descer a secção">↓</button><button class="btn sm" @click="tirarSec(si)" title="Tirar a secção">✕</button></span></header>
        <div v-for="(c,ci) in s.campos" :key="c.campo" class="form-campo">
          <span class="cresce">{{ c.rotulo }}</span>
          <button class="btn sm" @click="moverCampo(s,ci,-1)" :disabled="ci===0" title="Subir">↑</button><button class="btn sm" @click="moverCampo(s,ci,1)" :disabled="ci===s.campos.length-1" title="Descer">↓</button>
          <select v-if="d.secoes.length>1" class="btn sm" @change="passarPara(s,ci,+$event.target.value); $event.target.value=''"><option value="">Passar para…</option><option v-for="(o,oi) in d.secoes" :key="oi" v-show="oi!==si" :value="oi">{{ o.titulo }}</option></select>
          <button class="btn sm" @click="tirar(s,ci)" title="Tirar da ficha">✕</button>
        </div>
        <div v-if="!s.campos.length" class="sub" style="padding:6px 0">Secção vazia — junte campos ou tire-a.</div>
        <select class="btn sm" style="margin-top:8px" @change="juntar(s,$event.target.value); $event.target.value=''"><option value="">+ Juntar campo…</option><option v-for="c in livres" :key="c.campo" :value="c.campo">{{ c.rotulo }}</option></select>
      </div>
      <div class="fl-linha" style="margin-top:12px"><button class="btn" @click="novaSec">+ Secção</button><button class="btn" @click="repor">Repor a de origem</button>
        <span style="margin-left:auto" class="sub" v-if="sujo">Alterações por gravar</span><button class="btn prim" :disabled="aGravar || !sujo" @click="gravar">{{ aGravar ? 'A gravar…' : 'Gravar' }}</button></div>
      <p class="sub" style="font-size:12px;margin-top:10px">Campos fora do formulário: {{ livres.length }}. No separador «Detalhes», os que não estiverem em nenhuma secção aparecem em «Outros campos».</p>
    </template>
  </div>`,
};
const DefLista = {
  props: ["chave"],
  setup(props) {
    const d = ref(null); const ed = ref(null); const nova = ref(null); const arr = ref(null);
    const carregar = async () => { d.value = await apiDef("lista", { chave: props.chave }); };
    onMounted(carregar);
    // 26-11-2026: nas fases e nos estados das leads o nome que se escreve é o nome à vista (o interno não muda)
    const editar = (l) => { ed.value = { nome: l.name, valores: Object.fromEntries(d.value.campos.map((c) => [c.campo, (d.value.nome_rotulo && c.campo === d.value.nome && d.value.rotulos[l.name]) || (l[c.campo] ?? "")])) }; };
    const gravar = async () => { await apiDef("gravar", { chave: props.chave, nome: ed.value.nome, valores: JSON.stringify(ed.value.valores) }, true); ed.value = null; toast("Gravado"); carregar(); };
    const comecarNova = () => { nova.value = Object.fromEntries(d.value.campos.map((c) => [c.campo, c.tipo === "Check" ? 0 : (c.opcoes && c.opcoes.length && c.tipo === "Select" ? c.opcoes[0] : "")])); };
    const criar = async () => { await apiDef("criar", { chave: props.chave, valores: JSON.stringify(nova.value) }, true); nova.value = null; toast("Criado"); carregar(); };
    const apagar = async (l) => { if (!confirm(`Apagar «${l.name}»?`)) return; await apiDef("apagar", { chave: props.chave, nome: l.name }, true); toast("Apagado"); carregar(); };
    const largar = async (alvo) => {
      const de = arr.value; arr.value = null; if (!de || de === alvo) return;
      const nomes = d.value.linhas.map((l) => l.name).filter((n) => n !== de); nomes.splice(nomes.indexOf(alvo), 0, de);
      d.value.linhas.sort((a, b) => nomes.indexOf(a.name) - nomes.indexOf(b.name));
      await apiDef("ordenar", { chave: props.chave, nomes: JSON.stringify(nomes) }, true); toast("Ordem gravada");
    };
    const mostra = (l, c) => c.tipo === "Check" ? (l[c.campo] ? "Sim" : "—") : c.campo === "__name" && d.value.rotulos[l.name] ? d.value.rotulos[l.name] : (c.campo === d.value.nome && d.value.rotulos[l.name]) ? d.value.rotulos[l.name] : (l[c.campo] ?? "—");
    return { d, ed, nova, arr, editar, gravar, comecarNova, criar, apagar, largar, mostra };
  },
  template: `
  <div class="pad" v-if="d">
    <div class="ola"><div><div style="font-size:13px"><a href="#/definicoes">← Definições</a></div><h1>{{ d.titulo }}</h1><div class="sub">{{ d.linhas.length }} registos<template v-if="d.ordenavel"> · arraste para mudar a ordem</template></div></div>
      <button class="btn prim" v-if="d.pode_criar && !nova" @click="comecarNova">+ Acrescentar</button></div>
    <div class="tabela-wrap" style="margin:0"><table>
      <thead><tr><th v-if="d.ordenavel" style="width:28px"></th><th v-for="c in d.campos" :key="c.campo">{{ c.rotulo }}</th><th style="width:150px"></th></tr></thead>
      <tbody>
        <tr v-if="nova" class="def-ed"><td v-if="d.ordenavel"></td>
          <td v-for="c in d.campos" :key="c.campo"><select v-if="c.opcoes" v-model="nova[c.campo]"><option v-for="o in c.opcoes" :value="o">{{ o || '—' }}</option></select>
            <input v-else-if="c.tipo==='Check'" type="checkbox" v-model="nova[c.campo]" :true-value="1" :false-value="0"><input v-else v-model="nova[c.campo]" :type="c.tipo==='Int'?'number':'text'"></td>
          <td><button class="btn sm prim" @click="criar">Criar</button> <button class="btn sm" @click="nova=null">Cancelar</button></td></tr>
        <tr v-for="l in d.linhas" :key="l.name" :draggable="d.ordenavel && !ed" @dragstart="arr=l.name" @dragover.prevent @drop.prevent="largar(l.name)" :class="{'def-ed': ed && ed.nome===l.name}">
          <td v-if="d.ordenavel" class="sub" style="cursor:grab">⋮⋮</td>
          <template v-if="ed && ed.nome===l.name"><td v-for="c in d.campos" :key="c.campo"><select v-if="c.opcoes" v-model="ed.valores[c.campo]"><option v-for="o in c.opcoes" :value="o">{{ o || '—' }}</option></select>
            <input v-else-if="c.tipo==='Check'" type="checkbox" v-model="ed.valores[c.campo]" :true-value="1" :false-value="0"><input v-else v-model="ed.valores[c.campo]" :type="c.tipo==='Int'?'number':'text'" :disabled="d.nome_fixo && c.campo===d.nome" :title="d.nome_fixo && c.campo===d.nome ? 'Nome interno fixo (usado pelo Orbit)' : (d.nome_rotulo && c.campo===d.nome ? 'Nome que aparece no Orbit (vazio volta ao de origem)' : '')"></td>
            <td><button class="btn sm prim" @click="gravar">Gravar</button> <button class="btn sm" @click="ed=null">Cancelar</button></td></template>
          <template v-else><td v-for="c in d.campos" :key="c.campo" style="white-space:normal;max-width:360px">{{ mostra(l,c) }}</td>
            <td style="text-align:right"><button class="btn sm" v-if="d.pode_editar" @click="editar(l)">Editar</button> <button class="btn sm" v-if="d.pode_apagar" @click="apagar(l)">Apagar</button></td></template>
        </tr>
      </tbody></table></div>
  </div>
  <div v-else class="carregar">A carregar…</div>`,
};
const DefConsulta = {
  props: ["chave"],
  setup(props) { const d = ref(null); onMounted(async () => (d.value = await apiDef(props.chave === "caixas" ? "caixas" : "utilizadores"))); return { d, data }; },
  template: `
  <div class="pad">
    <div class="ola"><div><div style="font-size:13px"><a href="#/definicoes">← Definições</a></div><h1>{{ chave==='caixas' ? 'Caixas ligadas ao Orbit' : 'Utilizadores do Orbit' }}</h1>
      <div class="sub">{{ chave==='caixas' ? 'Ligar ou desligar caixas faz-se no portal, em Stratechna Orbit.' : 'Dar e tirar acessos faz-se no portal (utilizadores contratados).' }}</div></div></div>
    <div v-if="!d" class="carregar">A carregar…</div>
    <div v-else class="tabela-wrap" style="margin:0"><table>
      <template v-if="chave==='caixas'"><thead><tr><th>Caixa</th><th>Uso</th><th>Entrada</th><th>Envio</th><th>Mensagens no Orbit</th></tr></thead>
        <tbody><tr v-for="c in d" :key="c.email"><td><b>{{ c.email }}</b></td><td>{{ c.uso }}</td><td>{{ c.entrada ? 'Ligada' : '—' }}</td><td>{{ c.envio ? 'Ligado' : '—' }}</td><td>{{ c.mensagens }}</td></tr></tbody></template>
      <template v-else><thead><tr><th>Nome</th><th>Email</th><th>Perfil</th><th>Estado</th><th>Última entrada</th></tr></thead>
        <tbody><tr v-for="u in d" :key="u.name"><td><b>{{ u.full_name }}</b></td><td>{{ u.name }}</td><td>{{ u.perfil }}</td><td><span class="etq" :class="u.enabled?'verde':''">{{ u.enabled ? 'Ativo' : 'Desativado' }}</span></td><td class="sub">{{ u.last_login ? data(u.last_login) : '—' }}</td></tr></tbody></template>
    </table></div>
  </div>`,
};

// ── Definições › Utilizadores (25-11-2026, docs/PLANO-ORBIT-UTILIZADORES-LICENCAS.md): licenças, novo utilizador com
// aviso de custo e desactivar — tudo pelo portal (orbit.interface.licencas → POST /api/v1/orbit/utilizadores).
const PERFIS_ORBIT = { gestao: "Gestão", comercial: "Comercial", apoio: "Apoio ao cliente", rh: "Recursos humanos", contabilidade: "Contabilidade", producao: "Produção", operacoes: "Operações" };
// ── Definições › Empresas (25-11-2026, docs/PLANO-ORBIT-VARIAS-EMPRESAS.md): várias empresas no mesmo Orbit; cada marca
// pertence a uma empresa, que é quem fatura. Só o administrador do Orbit.
const DefEmpresas = {
  setup() {
    const d = ref(null), form = ref(null), aGravar = ref(false), erro = ref("");
    const e = (m, a, post) => api("orbit.empresas." + m, a || {}, !!post);
    const contab = ref(null);
    async function carregar() { try { d.value = await e("lista"); erro.value = ""; contab.value = (await e("contabilidade")).ligada; } catch (x) { erro.value = (x && x.message) || "Sem acesso."; } }
    onMounted(carregar);
    async function mudarContab(v) {
      if (!confirm(v ? "Ligar a contabilidade? Passam a ver-se o plano de contas, os lançamentos e os relatórios financeiros." : "Desligar a contabilidade? Ficam à vista o inventário, as vendas, as compras, as faturas e os pagamentos.")) { contab.value = !v; return; }
      try { const r = await e("mudar_contabilidade", { ligar: v ? 1 : 0 }, true); contab.value = r.ligada; toast(r.ligada ? "Contabilidade ligada." : "Contabilidade desligada."); }
      catch (x) { toast((x && x.message) || "Não foi possível mudar."); contab.value = !v; }
    }
    const abrirNova = () => { form.value = { nome: "", nif: "", pais: "Portugal", moeda: "EUR", abreviatura: "", morada: "", codigo_postal: "", cidade: "", marcas: [] }; };
    const empresaDe = (m) => (m.orbit_empresa || (d.value && d.value.principal));
    async function gravar() {
      if (!form.value.nome.trim() || !form.value.nif.trim()) { toast("Escreva o nome legal e o NIF."); return; }
      aGravar.value = true;
      try {
        const r = await e("criar", { ...form.value, marcas: JSON.stringify(form.value.marcas) }, true);
        toast("Empresa " + r.empresa + " criada."); form.value = null; await carregar();
      } catch (x) { toast((x && x.message) || "Não foi possível criar a empresa."); }
      finally { aGravar.value = false; }
    }
    async function mudar(marca, empresa) {
      if (!confirm("A marca " + marca + " passa a ser faturada por " + empresa + ". Continuar?")) { await carregar(); return; }
      try { const r = await e("associar", { marca, empresa }, true); toast("Marca " + marca + " em " + empresa + (r.armazem ? " · armazém " + r.armazem : "")); }
      catch (x) { toast((x && x.message) || "Não foi possível mudar."); }
      await carregar();
    }
    return { d, form, aGravar, erro, abrirNova, gravar, mudar, empresaDe, contab, mudarContab };
  },
  template: `
  <div class="pad" style="max-width:980px">
    <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:12px">
      <div><h1>Empresas</h1><div class="sub">Cada marca pertence a uma empresa, que é quem fatura. O CRM e o Desk separam-se pela marca.</div></div>
      <button v-if="d" class="btn prim" @click="abrirNova">+ Nova empresa</button>
    </div>
    <div v-if="erro" class="cartao" style="padding:14px">{{ erro }}</div>
    <div v-else-if="!d" class="sub">A carregar…</div>
    <template v-else>
      <div class="cartao" v-for="c in d.empresas" :key="c.name" style="padding:14px 16px;margin-bottom:10px">
        <div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap"><b>{{ c.name }}</b>
          <span class="sub">NIF {{ c.tax_id || '—' }} · {{ c.abbr }} · {{ c.default_currency }}<span v-if="c.principal"> · principal</span></span></div>
        <div class="sub" style="margin-top:6px">Marcas: <span v-if="!c.marcas.length">nenhuma</span><span v-for="(m,i) in c.marcas" :key="m">{{ i ? ', ' : '' }}{{ m }}</span></div>
      </div>
      <div class="cartao" style="padding:14px 16px;margin:14px 0;display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap">
        <div><b>Contabilidade</b><div class="sub">{{ contab ? 'Ligada: plano de contas, lançamentos e relatórios financeiros à vista.' : 'Desligada: inventário, vendas, compras, faturas e pagamentos, sem a contabilidade.' }}</div></div>
        <label style="display:flex;gap:8px;align-items:center;cursor:pointer"><input type="checkbox" :checked="contab" @change="mudarContab($event.target.checked)">{{ contab ? 'Ligada' : 'Desligada' }}</label>
      </div>
      <h2 style="font-size:15px;margin:18px 0 8px">Marcas</h2>
      <div class="cartao" style="padding:6px 16px">
        <div v-for="m in d.marcas" :key="m.name" style="display:flex;justify-content:space-between;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid var(--line)">
          <b>{{ m.name }}</b>
          <select class="btn" :value="empresaDe(m)" @change="mudar(m.name, $event.target.value)"><option v-for="c in d.empresas" :key="c.name" :value="c.name">{{ c.name }}</option></select>
        </div>
      </div>
    </template>
    <div v-if="form" class="modal-fundo" @click.self="form=null"><div class="modal" style="max-width:560px">
      <header><b>Nova empresa</b><button class="btn sm" @click="form=null">Fechar</button></header>
      <form @submit.prevent="gravar" style="display:flex;flex-direction:column;gap:10px;padding:14px 16px">
        <label class="erp-campo"><span>Nome legal<span class="obrig">*</span></span><input v-model="form.nome" required placeholder="Ex.: Talentos Transparentes Unipessoal, Lda."></label>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
          <label class="erp-campo"><span>NIF<span class="obrig">*</span></span><input v-model="form.nif" required inputmode="numeric"></label>
          <label class="erp-campo"><span>Abreviatura</span><input v-model="form.abreviatura" maxlength="10" placeholder="Automática"></label>
          <label class="erp-campo"><span>País</span><input v-model="form.pais"></label>
          <label class="erp-campo"><span>Moeda</span><input v-model="form.moeda" maxlength="3"></label>
        </div>
        <label class="erp-campo"><span>Morada</span><input v-model="form.morada"></label>
        <div style="display:grid;grid-template-columns:1fr 2fr;gap:10px">
          <label class="erp-campo"><span>Código postal</span><input v-model="form.codigo_postal" placeholder="0000-000"></label>
          <label class="erp-campo"><span>Localidade</span><input v-model="form.cidade"></label>
        </div>
        <div><span class="sub">Marcas desta empresa</span><div style="display:flex;flex-wrap:wrap;gap:10px;margin-top:6px">
          <label v-for="m in d.marcas" :key="m.name" style="display:flex;gap:6px;align-items:center"><input type="checkbox" :value="m.name" v-model="form.marcas">{{ m.name }}</label></div></div>
        <p class="sub" style="margin:0">A empresa nasce com o plano de contas, os armazéns e os modelos de IVA da empresa principal. As marcas escolhidas passam a ser faturadas por ela, com o seu armazém.</p>
        <div style="display:flex;justify-content:flex-end;gap:8px"><button type="button" class="btn" @click="form=null">Cancelar</button><button type="submit" class="btn prim" :disabled="aGravar">{{ aGravar ? 'A criar…' : 'Criar empresa' }}</button></div>
      </form></div></div>
  </div>`,
};
const DefUtilizadores = {
  setup() {
    const d = ref(null), cand = ref(null), form = ref(null), custo = ref(null), aGravar = ref(false);
    const eur = (v) => (Number(v || 0)).toLocaleString("pt-PT", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " €";
    const lic = (m) => api("licencas." + m);
    const post = (m, a) => api("licencas." + m, a, true);
    async function carregar() { d.value = await lic("estado"); }
    async function abrirNovo() {
      form.value = { email: "", nome: "", perfil: "operacoes" }; custo.value = null;
      if (!cand.value) { const c = await lic("candidatas"); cand.value = ((c && c.caixas) || []).filter((x) => x.tipo === "caixa"); }
    }
    function escolher(c) { form.value.email = c.endereco; form.value.nome = form.value.nome || c.nome || ""; }
    async function gravar(aceito) {
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/.test(form.value.email || "")) { toast("Escreva um email válido."); return; }
      aGravar.value = true;
      try {
        const r = await post("novo", { pessoa: JSON.stringify(form.value), aceito_custo: aceito ? 1 : 0 });
        if (r.precisa_aceitar) { custo.value = r; return; }
        if (!r.ok) { toast(r.erro || "Não foi possível criar o utilizador."); return; }
        toast(r.aplicado && r.aplicado.ok === false ? "Utilizador registado; a criação no Orbit ficou para a equipa da Stratechna." : "Utilizador criado. Já pode entrar com a palavra-passe da caixa de correio.");
        form.value = null; custo.value = null; cand.value = null; await carregar();
      } finally { aGravar.value = false; }
    }
    async function desactivar(u, reactivar) {
      if (!reactivar && !window.confirm(`Desactivar ${u.nome || u.email}? A pessoa deixa de entrar no Orbit e a licença fica livre. O plano não desce sozinho.`)) return;
      const r = await post("desactivar", { email: u.email, reactivar: reactivar ? 1 : 0 });
      if (!r.ok) { toast(r.erro || "Não foi possível."); return; }
      toast(reactivar ? "Utilizador reactivado." : "Utilizador desactivado. A licença ficou livre."); await carregar();
    }
    onMounted(carregar);
    return { d, cand, form, custo, aGravar, eur, abrirNovo, escolher, gravar, desactivar, PERFIS_ORBIT };
  },
  template: `
  <div class="pad">
    <div class="ola"><div><div style="font-size:13px"><a href="#/definicoes">← Definições</a></div><h1>Utilizadores do Orbit</h1>
      <div class="sub" v-if="d && d.disponivel !== false && d.permitido !== false">Licenças: <b>{{ d.escolhidos }} de {{ d.contratados }}</b> usadas<template v-if="d.preco"> · {{ eur(d.preco) }}/utilizador/{{ d.ciclo || 'mês' }} (sem IVA)</template></div></div>
      <button class="btn prim" v-if="d && d.permitido" @click="abrirNovo">+ Novo utilizador</button></div>
    <div v-if="!d" class="carregar">A carregar…</div>
    <div v-else-if="d.disponivel === false || d.permitido === false" class="cartao" style="padding:18px">{{ d.mensagem }}</div>
    <div v-else class="tabela-wrap" style="margin:0"><table>
      <thead><tr><th>Nome</th><th>Email</th><th>Perfil</th><th>Estado</th><th></th></tr></thead>
      <tbody><tr v-for="u in d.pessoas.filter(x=>!x.servico)" :key="u.email"><td><b>{{ u.nome || '—' }}</b></td><td>{{ u.email }}</td><td>{{ PERFIS_ORBIT[u.perfil] || u.perfil || '—' }}</td>
        <td><span class="etq" :class="u.desactivado?'':'verde'">{{ u.desactivado ? 'Desactivado' : 'Activo' }}</span></td>
        <td style="text-align:right"><button class="btn sm" v-if="!u.desactivado" @click="desactivar(u,false)">Desactivar</button><button class="btn sm" v-else @click="desactivar(u,true)">Reactivar</button></td></tr></tbody>
    </table></div>
    <div class="modal-fundo" v-if="form" @click.self="form=null">
      <div class="modal" style="max-width:560px"><header><b>Novo utilizador</b><button class="btn sm" @click="form=null">Fechar</button></header>
        <div class="corpo-email form-cal" v-if="!custo">
          <div v-if="cand && cand.length"><div class="sub" style="font-size:13px;margin-bottom:6px">Caixas da empresa que ainda não usam o Orbit</div>
            <div style="display:flex;gap:6px;flex-wrap:wrap"><button type="button" v-for="c in cand" :key="c.endereco" class="btn sm" :class="{prim: form.email===c.endereco}" @click="escolher(c)">{{ c.endereco }}</button></div></div>
          <label>Email da pessoa (a caixa de correio dela)<input v-model="form.email" type="email" placeholder="nome@empresa.pt"></label>
          <label>Nome<input v-model="form.nome" placeholder="Nome e apelido"></label>
          <label>Perfil<select v-model="form.perfil"><option v-for="(n,k) in PERFIS_ORBIT" :key="k" :value="k">{{ n }}</option></select></label>
          <div class="sub" style="font-size:12.5px">A pessoa entra no Orbit com o email e a palavra-passe da caixa de correio.</div>
          <div style="display:flex;justify-content:flex-end"><button class="btn prim" :disabled="aGravar" @click="gravar(false)">{{ aGravar ? 'A criar…' : 'Criar utilizador' }}</button></div>
        </div>
        <div class="corpo-email" v-else>
          <p><b>Não há licenças livres.</b> Ao continuar, o plano passa de <b>{{ custo.contratados }}</b> para <b>{{ custo.contratados + (custo.a_mais || 1) }}</b> utilizadores:
            <b>+{{ eur((custo.preco || 0) * (custo.a_mais || 1)) }}/{{ custo.ciclo || 'mês' }}</b> (sem IVA).</p>
          <p v-if="custo.acerto && custo.acerto.valor">Este período paga só a parte proporcional até {{ custo.acerto.ate ? new Date(custo.acerto.ate).toLocaleDateString('pt-PT') : 'à renovação' }}: <b>{{ eur(custo.acerto.valor) }}</b> + IVA. A fatura segue para o email de faturação da empresa.</p>
          <p class="sub" style="font-size:12.5px">A alteração fica registada no portal Stratechna. Desactivar um utilizador mais tarde liberta a licença, mas o plano só desce a pedido.</p>
          <div style="display:flex;justify-content:flex-end;gap:8px"><button class="btn" @click="custo=null">Voltar</button><button class="btn prim" :disabled="aGravar" @click="gravar(true)">{{ aGravar ? 'A criar…' : 'Acrescentar utilizador e continuar' }}</button></div>
        </div>
      </div></div>
  </div>`,
};

// ── Apps dentro da interface (as que o permitem: Meet e Booking) ──────────────────────────────────────
const EMBUTIDAS = ["Meet", "Booking"];
const AppEmbutida = {
  props: ["nome"],
  setup(props) {
    const app = computed(() => ((window.__ctx && window.__ctx.apps) || []).find((a) => a.nome === props.nome));
    return { app };
  },
  template: `<div class="embutida" v-if="app"><iframe :src="app.url" allow="camera; microphone; display-capture; fullscreen; clipboard-write; autoplay" :title="app.nome"></iframe></div><div v-else class="vazio">App desconhecida.</div>`,
};

// ── ERP genérico (U1/U2, 21-11-2026): lista e ficha desenhadas a partir da definição de cada documento ───────
// O motor é o ERPNext (orbit.interface.erp → get_list / get_doc().save() com as permissões da pessoa).
const _metas = {};
async function metaErp(dt) { if (!_metas[dt]) _metas[dt] = await api("erp.meta", { doctype: dt }); return _metas[dt]; }
const ESTRUTURA = ["Section Break", "Column Break", "Tab Break"];
const NUMERICOS = ["Int", "Float", "Currency", "Percent"];
// 25-11-2026: tipos sem valor próprio (não se gravam nem contam como obrigatórios) e tipos de tabela-filha
const SEM_VALOR = ["HTML", "Button", "Heading", "Image", "Fold"];
const FILHAS = ["Table", "Table MultiSelect"];
const MONO = ["Code", "JSON", "Markdown Editor", "HTML Editor", "Geolocation"];
// Carregar um ficheiro como o ecrã antigo (upload_file do Frappe); devolve o endereço do ficheiro.
async function carregarFicheiro(ficheiro, { doctype, docname, fieldname, privado = 1 } = {}) {
  const fd = new FormData(); fd.append("file", ficheiro, ficheiro.name); fd.append("is_private", privado ? 1 : 0);
  if (doctype && docname && !String(docname).startsWith("novo")) { fd.append("doctype", doctype); fd.append("docname", docname); if (fieldname) fd.append("fieldname", fieldname); }
  const r = await fetch("/api/method/upload_file", { method: "POST", body: fd, headers: { "X-Frappe-CSRF-Token": window.csrf_token, Accept: "application/json" } });
  const j = await r.json().catch(() => ({}));
  if (!r.ok || !j.message) throw new Error("Não foi possível carregar o ficheiro.");
  return j.message.file_url;
}
function avaliar(expr, doc) {
  if (!expr) return true;
  if (expr.startsWith("eval:")) { try { return !!new Function("doc", "parent", `return (${expr.slice(5)})`)(doc, doc); } catch (e) { return true; } }
  return !!doc[expr];
}
const vazioV = (v) => v === null || v === undefined || v === "" || (Array.isArray(v) && !v.length);
function textoValor(c, v) {
  if (vazioV(v)) return "";
  if (c.fieldtype === "Check") return v ? "✓" : "";
  if (c.fieldtype === "Select") { const o = (c.opcoes || []).find((x) => x.v === v); return o ? o.r : v; }
  if (c.fieldtype === "Currency") return new Intl.NumberFormat("pt-PT", { style: "currency", currency: "EUR" }).format(v);
  if (c.fieldtype === "Date") return new Date(v).toLocaleDateString("pt-PT");
  if (c.fieldtype === "Datetime") return data(v);
  if (c.fieldtype === "Link") return tr(c.options, String(v));
  return String(v);
}
const ESTADO_DOC = { 0: ["Rascunho", "ambar"], 1: ["Submetido", "verde"], 2: ["Cancelado", ""] };
// 25-11-2026: o estado dos documentos do ERPNext em PT-PT (aparecia «Unpaid», «To Deliver and Bill»…)
const STATUS_PT = { Draft: "Rascunho", Submitted: "Submetido", Cancelled: "Cancelado", Unpaid: "Por pagar", Paid: "Pago", "Partly Paid": "Pago em parte",
  Overdue: "Vencido", Return: "Devolução", "Credit Note Issued": "Com nota de crédito", "Debit Note Issued": "Com nota de débito",
  "Unpaid and Discounted": "Por pagar (descontado)", "Partly Paid and Discounted": "Pago em parte (descontado)", "Overdue and Discounted": "Vencido (descontado)",
  "Internal Transfer": "Transferência interna", "To Deliver and Bill": "Por entregar e faturar", "To Bill": "Por faturar", "To Deliver": "Por entregar",
  "To Receive and Bill": "Por receber e faturar", "To Receive": "Por receber", Completed: "Concluído", Closed: "Fechado", "On Hold": "Em espera",
  Open: "Aberto", Replied: "Respondido", Ordered: "Encomendado", Lost: "Perdido", Expired: "Expirado", Pending: "Pendente", Stopped: "Parado",
  Delivered: "Entregue", "Partly Delivered": "Entregue em parte", "Not Delivered": "Por entregar", Billed: "Faturado", "Partly Billed": "Faturado em parte",
  "Not Billed": "Por faturar", Issued: "Emitido", Transferred: "Transferido", Received: "Recebido", "Partially Ordered": "Encomendado em parte",
  "Partially Received": "Recebido em parte", Approved: "Aprovado", Rejected: "Recusado", Active: "Ativo", Inactive: "Inativo", Left: "Saiu" };
const COR_STATUS = { Paid: "verde", Completed: "verde", Delivered: "verde", Approved: "verde", Active: "verde", Overdue: "ambar", Unpaid: "azul", "Partly Paid": "azul", Draft: "ambar", "On Hold": "ambar", Rejected: "ambar" };
const statusPt = (v) => STATUS_PT[v] || v;
const irErp = (dt, dn) => `#/erp/${encodeURIComponent(dt)}` + (dn ? `/${encodeURIComponent(dn)}` : "");

// ── 25-11-2026 (Vítor): nada abre a secretária antiga — gráficos, painéis e contas a receber/pagar com ecrã próprio ──
const moedaEUR = (v, m) => new Intl.NumberFormat("pt-PT", { style: "currency", currency: m || "EUR" }).format(v || 0);
const GraficoBarras = {
  props: ["labels", "series", "moeda"],
  setup(props) {
    const CORES = ["var(--acao)", "#5b6f7a", "#8a7340"];
    const g = computed(() => { const series = (props.series || []).slice(0, 3); const labels = (props.labels || []).slice(-24);
      const n = labels.length; const corte = (props.labels || []).length - n;
      const sr = series.map((x) => ({ ...x, values: (x.values || []).slice(corte) }));
      const max = Math.max(1, ...sr.flatMap((x) => x.values.map((v) => Math.abs(Number(v) || 0)))); return { labels, series: sr, max }; });
    const fmt = (v) => props.moeda ? moedaEUR(v) : new Intl.NumberFormat("pt-PT").format(v || 0);
    return { g, CORES, fmt };
  },
  template: `<div style="overflow-x:auto"><svg :viewBox="'0 0 ' + Math.max(g.labels.length*48, 300) + ' 170'" preserveAspectRatio="none" :style="{width:'100%',height:'170px',display:'block',minWidth: Math.max(g.labels.length*34, 280)+'px'}">
      <template v-for="(l,i) in g.labels" :key="i"><template v-for="(sr,k) in g.series" :key="k">
        <rect :x="i*48 + 6 + k*(36/g.series.length)" :width="36/g.series.length - 2" :y="140 - Math.abs(Number(sr.values[i])||0)/g.max*130" :height="Math.abs(Number(sr.values[i])||0)/g.max*130" :fill="CORES[k]" rx="2"><title>{{ sr.name ? sr.name + ': ' : '' }}{{ fmt(sr.values[i]) }}</title></rect></template>
        <text :x="i*48+24" y="160" text-anchor="middle" font-size="10" fill="var(--ink-3)">{{ String(l).slice(0,8) }}</text></template></svg>
    <div v-if="g.series.length > 1 || (g.series[0] && g.series[0].name)" class="sub" style="display:flex;gap:14px;flex-wrap:wrap;font-size:12px"><span v-for="(sr,k) in g.series" :key="k"><span :style="{display:'inline-block',width:'10px',height:'10px',borderRadius:'2px',background:CORES[k],marginRight:'5px'}"></span>{{ sr.name }}</span></div></div>`,
};

const ErpPainel = {
  components: { GraficoBarras },
  props: ["nome"],
  setup(props) {
    const p = ref(null);
    onMounted(async () => { p.value = await api("contas.painel", { nome: props.nome }); });
    const valor = (c) => c.tipo === "Currency" ? moedaEUR(c.valor, p.value.moeda) : new Intl.NumberFormat("pt-PT").format(c.valor || 0);
    return { p, valor, irErp };
  },
  template: `<div v-if="p" class="pad">
    <div style="font-size:13px"><a href="javascript:history.back()">← Voltar</a></div>
    <h1>{{ p.titulo }}</h1><div class="sub" style="margin-bottom:16px">Painel do módulo, calculado agora.</div>
    <div v-if="p.cartoes.length" class="erp-numeros"><component :is="c.doctype ? 'a' : 'div'" v-for="c in p.cartoes" :key="c.rotulo" class="cartao" :href="c.doctype ? irErp(c.doctype) : null" style="text-decoration:none;color:inherit"><small>{{ c.rotulo }}</small><b>{{ valor(c) }}</b></component></div>
    <div class="painel-graficos">
      <section v-for="g in p.graficos" :key="g.rotulo" class="cartao erp-grafico" :class="{largo: g.largo}">
        <header style="display:flex;justify-content:space-between;gap:8px;margin-bottom:8px"><b>{{ g.rotulo }}</b>
          <a v-if="g.relatorio" :href="'#/erp-rel/'+encodeURIComponent(g.relatorio)" class="sub" style="font-size:12px">Relatório →</a>
          <a v-else-if="g.doctype" :href="irErp(g.doctype)" class="sub" style="font-size:12px">Ver lista →</a></header>
        <GraficoBarras :labels="g.labels" :series="g.series"/>
      </section>
    </div>
    <div v-if="!p.cartoes.length && !p.graficos.length" class="cartao vazio">Este painel ainda não tem números nem gráficos com dados.</div>
  </div><div v-else class="vazio">A carregar…</div>`,
};

// «A receber» / «A pagar»: o que cada cliente deve e o que se deve a cada fornecedor (orbit/interface/contas.py)
const ErpContas = {
  props: ["lado"],
  setup(props) {
    const r = ref(null), aberto = ref(null), docs = ref({}), q = ref(""), so = ref("todos"), empresa = ref(""), marca = ref("");
    const carregar = async () => { r.value = await api("contas.resumo", { lado: props.lado, empresa: empresa.value || null, marca: marca.value || null }); };
    onMounted(carregar);
    watch([empresa, marca], carregar);
    const m = (v) => moedaEUR(v, r.value?.moeda);
    const lista = computed(() => (r.value?.lista || []).filter((x) => (so.value !== "vencidos" || x.vencido > 0)
      && (!q.value || (x.nome + " " + x.entidade).toLowerCase().includes(q.value.toLowerCase()))));
    const abrir = async (x) => { if (aberto.value === x.entidade) { aberto.value = null; return; } aberto.value = x.entidade;
      if (!docs.value[x.entidade]) docs.value[x.entidade] = await api("contas.documentos", { lado: props.lado, entidade: x.entidade }); };
    const maxFaixa = computed(() => Math.max(1, ...(r.value?.faixas || []).map((f) => f.valor)));
    const receber = (x, fatura) => { try { sessionStorage.setItem("orbit.recibo", JSON.stringify({ cliente: x.entidade, fatura: fatura || null })); } catch (e) {}
      location.hash = irErp("Payment Entry", "novo"); };
    // 25-11-2026: «Pagar» uma fatura de compra (o pagamento do ERPNext já preenchido, como «Criar → Pagamento»)
    const pagar = async (d) => { const r = await api("erp.criar_de", { doctype: "Purchase Invoice", name: d.name, destino: "pe" }, true);
      try { sessionStorage.setItem("orbit.erp.novo", JSON.stringify(r.doc)); } catch (e) {} location.hash = irErp("Payment Entry", "novo") + "/completa"; };
    const csv = () => { const esc = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
      const t = [[r.value.rotulo, "Em dívida", "Vencido", "Faturas", "Dias de atraso", "Vencimento mais antigo"].map(esc).join(";")]
        .concat(lista.value.map((x) => [x.nome, x.divida, x.vencido, x.documentos, x.atraso, x.mais_antiga].map(esc).join(";"))).join("\n");
      const b = new Blob(["﻿" + t], { type: "text/csv;charset=utf-8" }); const u = URL.createObjectURL(b);
      const el = document.createElement("a"); el.href = u; el.download = r.value.titulo + ".csv"; el.click(); URL.revokeObjectURL(u); };
    return { r, lista, aberto, docs, abrir, m, q, so, empresa, marca, maxFaixa, receber, pagar, csv, irErp, data };
  },
  template: `<div v-if="r">
    <div class="pad" style="padding-bottom:12px;display:flex;justify-content:space-between;align-items:flex-end;gap:12px;flex-wrap:wrap">
      <div><h1>{{ r.titulo }}</h1><div class="sub">{{ lado==='receber' ? 'O que cada cliente deve, a começar pelo que já venceu.' : 'O que há a pagar a cada fornecedor, a começar pelo que já venceu.' }}</div></div>
      <div class="acoes-lista"><a v-if="lado==='receber'" class="btn prim" href="javascript:void 0" @click="receber({entidade:''})">+ Receber pagamento</a>
        <a class="btn" :href="irErp(r.doctype)">{{ lado==='receber' ? 'Faturas de venda' : 'Faturas de compra' }}</a><button class="btn" @click="csv" :disabled="!lista.length">Exportar</button></div>
    </div>
    <div class="contas-kpis">
      <div class="cartao"><small>Em dívida</small><b>{{ m(r.totais.divida) }}</b><span class="sub">{{ r.totais.documentos }} {{ r.totais.documentos===1 ? 'fatura' : 'faturas' }}</span></div>
      <div class="cartao" :class="{alerta: r.totais.vencido > 0}"><small>Vencido</small><b>{{ m(r.totais.vencido) }}</b><span class="sub">{{ r.totais.divida ? Math.round(r.totais.vencido/r.totais.divida*100) : 0 }} % do total</span></div>
      <div class="cartao"><small>Vence nos próximos 30 dias</small><b>{{ m(r.totais.a_30) }}</b></div>
    </div>
    <div class="cartao contas-faixas">
      <b style="font-size:13px">Antiguidade</b>
      <div v-for="f in r.faixas" :key="f.rotulo" class="faixa"><span>{{ f.rotulo }}</span>
        <div class="barra"><i :style="{width: (f.valor/maxFaixa*100)+'%'}" :class="{tarde: f.rotulo!=='Por vencer'}"></i></div>
        <b>{{ m(f.valor) }}</b><small class="sub">{{ f.n }}</small></div>
    </div>
    <div class="filtros">
      <input class="filtro" style="border-style:solid;min-width:220px" v-model="q" :placeholder="'Procurar ' + r.rotulo.toLowerCase() + '…'">
      <select class="filtro" v-model="so"><option value="todos">Tudo em dívida</option><option value="vencidos">Só com valores vencidos</option></select>
      <select v-if="r.empresas.length > 1" class="filtro" v-model="empresa"><option value="">Todas as empresas</option><option v-for="e in r.empresas" :key="e" :value="e">{{ e }}</option></select>
      <select v-if="r.marcas.length > 1" class="filtro" v-model="marca"><option value="">Todas as marcas</option><option v-for="x in r.marcas" :key="x" :value="x">{{ x }}</option></select>
    </div>
    <div class="tabela-wrap cartoes-movel contas-tab"><table>
      <thead><tr><th>{{ r.rotulo }}</th><th style="text-align:right">Em dívida</th><th style="text-align:right">Vencido</th><th style="text-align:right">Faturas</th><th>Mais antiga</th><th></th></tr></thead>
      <tbody><template v-for="x in lista" :key="x.entidade">
        <tr @click="abrir(x)" :class="{sel: aberto===x.entidade}">
          <td class="cel-tit"><b>{{ x.nome }}</b><div v-if="x.nome!==x.entidade" class="sub" style="font-size:12px">{{ x.entidade }}</div></td>
          <td style="text-align:right"><b>{{ m(x.divida) }}</b></td>
          <td style="text-align:right"><span v-if="x.vencido" class="etq ambar">{{ m(x.vencido) }} · {{ x.atraso }} d</span><span v-else class="sub">—</span></td>
          <td style="text-align:right">{{ x.documentos }}</td>
          <td class="sub">{{ x.mais_antiga ? data(x.mais_antiga,false) : '—' }}</td>
          <td style="text-align:right" @click.stop><button v-if="lado==='receber'" class="btn sm" @click="receber(x)">Receber</button><button v-else class="btn sm" @click="abrir(x)">Pagar…</button></td>
        </tr>
        <tr v-if="aberto===x.entidade" class="contas-docs"><td colspan="6">
          <div v-if="!docs[x.entidade]" class="sub">A carregar…</div>
          <div v-else class="contas-docs-lista">
            <a v-for="d in docs[x.entidade]" :key="d.name" :href="irErp(r.doctype, d.name)" class="contas-doc">
              <span><b>{{ d.numero }}</b><span v-if="d.devolucao" class="etq">{{ lado==='receber' ? 'Nota de crédito' : 'Nota de débito' }}</span><small class="sub"> · {{ data(d.data,false) }}<template v-if="d.marca"> · {{ d.marca }}</template></small></span>
              <span class="sub">Vence {{ d.vencimento ? data(d.vencimento,false) : '—' }}<span v-if="d.atraso" class="etq ambar" style="margin-left:6px">{{ d.atraso }} d de atraso</span></span>
              <span style="text-align:right"><b>{{ m(d.divida) }}</b><small class="sub"> de {{ m(d.total) }}</small></span>
              <button v-if="lado==='receber' && !d.devolucao" class="btn sm" @click.prevent.stop="receber(x, d.name)">Receber</button>
              <button v-if="lado==='pagar' && !d.devolucao" class="btn sm" @click.prevent.stop="pagar(d)">Pagar</button>
            </a>
            <a :href="irErp(r.entidade_doctype, x.entidade)" class="sub" style="font-size:12px;padding:6px 2px">Ficha de {{ x.nome }} →</a>
          </div>
        </td></tr>
      </template></tbody></table>
      <div v-if="!lista.length" class="vazio">{{ r.totais.documentos ? 'Nada com estes filtros.' : (lado==='receber' ? 'Nenhum cliente com valores em dívida.' : 'Nada por pagar a fornecedores.') }}</div>
    </div>
  </div><div v-else class="vazio">A carregar…</div>`,
};

// Importar dados para qualquer lista do ERP (o Data Import do Frappe, no /orbit) — lote 4, 25-11-2026
const ErpImportar = {
  props: ["doctype"],
  setup(props) {
    const mod = ref(null), escolhidos = ref([]), formato = ref("Excel"), tipo = ref("Insert New Records"), submeter = ref(false);
    const fich = ref(null), nome = ref(null), prev = ref(null), estadoI = ref(null), falhas = ref([]), a = ref(false), entrada = ref(null); let tp;
    onMounted(async () => { mod.value = await apiL("importar_modelo", { doctype: props.doctype }); escolhidos.value = mod.value.campos.slice(); });
    onUnmounted(() => clearInterval(tp));
    const get = async (metodo, dados) => { const r = await fetch("/api/method/" + metodo + "?" + new URLSearchParams(dados), { headers: { Accept: "application/json" } }); const j = await r.json().catch(() => ({}));
      if (!r.ok) { let m = "Erro"; try { m = JSON.parse(JSON.parse(j._server_messages)[0]).message; } catch (e) {} toast(String(m).replace(/<[^>]+>/g, "")); throw new Error(m); } return j.message; };
    const urlModelo = computed(() => "/api/method/frappe.core.doctype.data_import.data_import.download_template?" + new URLSearchParams({ doctype: props.doctype,
      export_fields: JSON.stringify({ [props.doctype]: tipo.value === "Update Existing Records" ? ["name"].concat(escolhidos.value) : escolhidos.value }),
      export_records: tipo.value === "Update Existing Records" ? "all" : "blank_template", file_type: formato.value }).toString());
    const carregar = async (ev) => { const fi = ev.target.files?.[0]; if (!fi) return; a.value = true;
      try { const url = await carregarFicheiro(fi, { privado: 1 }); fich.value = { nome: fi.name, url };
        nome.value = (await apiL("importar_novo", { doctype: props.doctype, ficheiro: url, tipo: tipo.value, submeter: submeter.value ? 1 : 0 }, true)).name;
        prev.value = await get("frappe.core.doctype.data_import.data_import.get_preview_from_template", { data_import: nome.value, import_file: url });
      } finally { a.value = false; ev.target.value = ""; } };
    const post = async (metodo, dados) => { const r = await fetch("/api/method/" + metodo, { method: "POST", headers: { "X-Frappe-CSRF-Token": window.csrf_token, Accept: "application/json", "Content-Type": "application/json" }, body: JSON.stringify(dados) });
      const j = await r.json().catch(() => ({})); if (!r.ok) { let m = "Erro"; try { m = JSON.parse(JSON.parse(j._server_messages)[0]).message; } catch (e) {} toast(String(m).replace(/<[^>]+>/g, "")); throw new Error(m); } return j.message; };
    const importar = async () => { a.value = true;
      try { await post("frappe.core.doctype.data_import.data_import.form_start_import", { data_import: nome.value });
        const ver = async () => { estadoI.value = await get("frappe.core.doctype.data_import.data_import.get_import_status", { data_import_name: nome.value });
          if (["Success", "Partial Success", "Error"].includes(estadoI.value.status)) { clearInterval(tp); a.value = false;
            falhas.value = await get("frappe.core.doctype.data_import.data_import.get_import_logs", { data_import: nome.value, status: "failed" }); } };
        tp = setInterval(ver, 2000); ver(); } catch (e) { a.value = false; } };
    const recomecar = () => { fich.value = null; nome.value = null; prev.value = null; estadoI.value = null; falhas.value = []; };
    const ESTADOS_I = { Pending: "À espera", Success: "Concluída", "Partial Success": "Concluída com erros", Error: "Falhou", Timed_Out: "Excedeu o tempo" };
    const msg = (l) => { try { return JSON.parse(l.messages || "[]").map((m) => String(m.message || m.title || m).replace(/<[^>]+>/g, "")).join(" · "); } catch (e) { return l.exception ? String(l.exception).split("\n").filter(Boolean).pop() : ""; } };
    return { tr, mod, escolhidos, formato, tipo, submeter, fich, prev, estadoI, falhas, a, entrada, urlModelo, carregar, importar, recomecar, ESTADOS_I, msg, irErp, nome };
  },
  template: `<div class="pad" v-if="mod" style="max-width:980px">
    <div style="font-size:13px"><a :href="irErp(doctype)">← Voltar à lista</a></div>
    <h1>Importar — {{ tr(doctype, doctype) }}</h1><div class="sub" style="margin-bottom:16px">Carregue uma folha (Excel ou CSV) e confirme a pré-visualização antes de importar.</div>
    <section class="cartao" style="padding:14px 16px;margin-bottom:12px"><b>1. O que vai fazer</b>
      <div class="reg-linha3" style="margin-top:8px">
        <label class="erp-campo"><span>Tipo</span><select v-model="tipo" :disabled="!!nome"><option value="Insert New Records">Criar registos novos</option><option value="Update Existing Records">Atualizar registos que já existem</option></select></label>
        <label class="erp-campo"><span>Formato do modelo</span><select v-model="formato"><option value="Excel">Excel</option><option value="CSV">CSV</option></select></label>
        <label class="chk-col" style="align-self:end"><input type="checkbox" v-model="submeter" :disabled="!!nome"> Submeter depois de importar</label></div></section>
    <section class="cartao" style="padding:14px 16px;margin-bottom:12px"><b>2. Descarregar o modelo</b> <span class="sub" style="font-size:12px">(opcional — pode usar a sua folha com os mesmos títulos)</span>
      <details style="margin:8px 0"><summary class="sub" style="cursor:pointer">Colunas do modelo ({{ escolhidos.length }})</summary>
        <div class="imp-cols"><label v-for="c in mod.todos" :key="c.campo" class="chk-col"><input type="checkbox" :value="c.campo" v-model="escolhidos" :disabled="!!c.obrigatorio"> {{ c.rotulo }}<span v-if="c.obrigatorio" class="obrig">*</span></label></div></details>
      <a class="btn" :href="urlModelo">Descarregar o modelo</a></section>
    <section class="cartao" style="padding:14px 16px;margin-bottom:12px"><b>3. Carregar a folha</b>
      <div style="margin-top:8px;display:flex;gap:8px;align-items:center;flex-wrap:wrap"><button class="btn" @click="entrada.click()" :disabled="a || !!estadoI">{{ fich ? 'Trocar a folha' : 'Escolher a folha…' }}</button><input ref="entrada" type="file" accept=".csv,.xlsx,.xls" style="display:none" @change="carregar">
        <span v-if="fich" class="sub">{{ fich.nome }}</span><span v-if="a && !estadoI" class="sub">A ler…</span></div>
      <template v-if="prev">
        <div v-for="(w,k) in (prev.warnings||[]).slice(0,8)" :key="k" class="aviso" style="margin:8px 0 0">{{ String(w.message||w).replace(/<[^>]+>/g,'') }}</div>
        <div class="tabela-wrap" style="margin:10px 0 0;max-height:320px"><table><thead><tr><th v-for="(c,i) in (prev.columns||[])" :key="i">{{ c.header_title || (c.df && c.df.label) || '' }}<small v-if="c.skip_import" class="sub"> (ignorada)</small></th></tr></thead>
          <tbody><tr v-for="(r,i) in (prev.data||[]).slice(0,10)" :key="i" style="cursor:default"><td v-for="(v,j) in r" :key="j">{{ v }}</td></tr></tbody></table></div>
        <div class="sub" style="font-size:12px;margin-top:6px">{{ (prev.data||[]).length }} linha(s) na folha{{ (prev.data||[]).length > 10 ? ' — mostram-se as 10 primeiras' : '' }}.</div>
      </template></section>
    <section class="cartao" style="padding:14px 16px" v-if="prev"><b>4. Importar</b>
      <div style="margin-top:8px;display:flex;gap:8px;align-items:center;flex-wrap:wrap">
        <button class="btn prim" @click="importar" :disabled="a || !!estadoI">{{ a ? 'A importar…' : 'Importar' }}</button>
        <template v-if="estadoI"><span class="etq" :class="{Success:'verde','Partial Success':'ambar',Error:'ambar'}[estadoI.status]">{{ ESTADOS_I[estadoI.status] || estadoI.status }}</span>
          <span class="sub">{{ estadoI.success || 0 }} importado(s){{ estadoI.failed ? ' · ' + estadoI.failed + ' com erro' : '' }}{{ estadoI.total_records ? ' de ' + estadoI.total_records : '' }}</span>
          <a v-if="estadoI.failed" class="btn sm" :href="'/api/method/frappe.core.doctype.data_import.data_import.download_errored_template?data_import_name='+encodeURIComponent(nome)">Descarregar as linhas com erro</a>
          <button v-if="!a" class="btn sm" @click="recomecar">Nova importação</button><a v-if="!a" class="btn sm" :href="irErp(doctype)">Ver a lista</a></template></div>
      <div v-if="falhas.length" class="tabela-wrap" style="margin:10px 0 0;max-height:300px"><table><thead><tr><th>Linha(s)</th><th>Erro</th></tr></thead>
        <tbody><tr v-for="(l,i) in falhas" :key="i" style="cursor:default"><td>{{ (JSON.parse(l.row_indexes||'[]')||[]).join(', ') }}</td><td style="white-space:normal">{{ msg(l) }}</td></tr></tbody></table></div>
    </section>
  </div><div v-else class="vazio">A carregar…</div>`,
};

// ── Lote 6 (25-11-2026): RH — «Por aprovar» e calendário de ausências (orbit/interface/rh.py) ──
const RhAprovar = {
  setup() {
    const l = ref(null); const a = ref("");
    const carregar = async () => { l.value = await api("rh.por_aprovar"); }; onMounted(carregar);
    const decidir = async (x, sim) => { const nota = sim ? null : prompt("Motivo da recusa (opcional)") ; if (!sim && nota === null) return; a.value = x.name;
      try { await api("rh.decidir", { doctype: x.doctype, name: x.name, aprovar: sim ? 1 : 0, nota }, true); toast(sim ? "Aprovado" : "Recusado"); carregar(); } finally { a.value = ""; } };
    const eur = (v) => moedaEUR(v);
    return { l, a, decidir, data, irErp, eur };
  },
  template: `<div><div class="pad" style="padding-bottom:12px"><h1>Por aprovar</h1><div class="sub">Pedidos de ausência e despesas à espera da sua decisão.</div></div>
    <div v-if="!l" class="carregar">A carregar…</div><div v-else-if="!l.length" class="vazio">Nada por aprovar.</div>
    <div v-else class="tabela-wrap cartoes-movel"><table><thead><tr><th>Pessoa</th><th>Pedido</th><th>Quando</th><th>Nota</th><th></th></tr></thead><tbody>
      <tr v-for="x in l" :key="x.name" style="cursor:default">
        <td class="cel-tit"><b>{{ x.pessoa }}</b><div class="sub" style="font-size:12px"><a :href="irErp(x.doctype, x.name)">{{ x.name }}</a></div></td>
        <td><span class="etq" :class="x.tipo==='Despesa' ? 'roxo' : 'azul'">{{ x.tipo }}</span> {{ x.titulo }}<template v-if="x.valor"> · <b>{{ eur(x.valor) }}</b></template></td>
        <td>{{ data(x.de,false) }}<template v-if="x.ate && x.ate!==x.de"> → {{ data(x.ate,false) }}</template><span v-if="x.dias" class="sub"> · {{ x.dias }} dia(s){{ x.meio_dia ? ' (meio dia)' : '' }}</span></td>
        <td class="sub" style="white-space:normal;max-width:280px">{{ x.nota }}</td>
        <td @click.stop style="text-align:right;white-space:nowrap"><button class="btn sm" :disabled="a===x.name" @click="decidir(x,false)">Recusar</button> <button class="btn sm prim" :disabled="a===x.name" @click="decidir(x,true)">Aprovar</button></td>
      </tr></tbody></table></div></div>`,
};
const RhAusencias = {
  setup() {
    const hoje = new Date(); const ano = ref(hoje.getFullYear()); const mes = ref(hoje.getMonth() + 1); const d = ref(null);
    const carregar = async () => { d.value = null; d.value = await api("rh.ausencias", { ano: ano.value, mes: mes.value }); }; onMounted(carregar);
    const mudar = (k) => { let m = mes.value + k, a = ano.value; if (m < 1) { m = 12; a--; } if (m > 12) { m = 1; a++; } mes.value = m; ano.value = a; carregar(); };
    const dias = computed(() => { const n = new Date(ano.value, mes.value, 0).getDate(); return Array.from({ length: n }, (_, i) => { const dt = new Date(ano.value, mes.value - 1, i + 1);
      return { n: i + 1, iso: `${ano.value}-${String(mes.value).padStart(2, "0")}-${String(i + 1).padStart(2, "0")}`, fds: [0, 6].includes(dt.getDay()), sem: "dstqqss"[dt.getDay()] }; }); });
    const pessoas = computed(() => [...new Set((d.value?.ausencias || []).map((x) => x.pessoa))].sort());
    const em = (p, dia) => (d.value?.ausencias || []).find((x) => x.pessoa === p && x.de <= dia.iso && x.ate >= dia.iso);
    const feriado = (dia) => (d.value?.feriados || []).find((f) => f.data === dia.iso);
    const titulo = computed(() => new Date(ano.value, mes.value - 1, 1).toLocaleDateString("pt-PT", { month: "long", year: "numeric" }));
    return { ano, mes, d, mudar, dias, pessoas, em, feriado, titulo, irErp };
  },
  template: `<div><div class="pad" style="padding-bottom:12px;display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap">
      <div><h1>Calendário de ausências</h1><div class="sub">Aprovadas a cheio; por aprovar com riscas.</div></div>
      <div style="display:flex;gap:6px;align-items:center"><button class="btn sm" @click="mudar(-1)">‹</button><b style="min-width:150px;text-align:center;text-transform:capitalize">{{ titulo }}</b><button class="btn sm" @click="mudar(1)">›</button>
        <a class="btn sm prim" :href="irErp('Leave Application','novo')">+ Pedir ausência</a></div></div>
    <div v-if="!d" class="carregar">A carregar…</div>
    <div v-else class="cartao aus-quadro"><table><thead><tr><th class="aus-nome">Pessoa</th><th v-for="x in dias" :key="x.n" :class="{fds:x.fds, fer: feriado(x)}" :title="feriado(x) ? feriado(x).nome : ''"><small>{{ x.sem }}</small><br>{{ x.n }}</th></tr></thead>
      <tbody><tr v-if="!pessoas.length"><td :colspan="dias.length+1" class="vazio">Ninguém ausente neste mês.</td></tr>
        <tr v-for="p in pessoas" :key="p"><td class="aus-nome">{{ p }}</td>
          <td v-for="x in dias" :key="x.n" :class="{fds:x.fds, fer: feriado(x)}"><a v-if="em(p,x)" :href="irErp('Leave Application', em(p,x).name)" class="aus-dia" :class="{pend: !em(p,x).aprovada, meio: em(p,x).meio_dia}" :title="em(p,x).tipo + (em(p,x).aprovada ? '' : ' (por aprovar)')"></a></td></tr></tbody></table></div></div>`,
};

// ── Marketing na interface nova (25-11-2026): segmentos, marcadores, modelos, ciclo das campanhas e automações, base legal.
// O motor é o de orbit.marketing.* (segmentação S1–S8, docs/PLANO-SEGMENTACAO-EMAIL-MARKETING.md); aqui só o ecrã.
const apiSeg = (m, a = {}, post = false) => api("orbit.marketing.segmentos." + m, a, post);
const docMetodo = async (doctype, name, method, args = {}) => {
  const r = await fetch("/api/method/run_doc_method", { method: "POST", headers: { "X-Frappe-CSRF-Token": window.csrf_token, Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({ dt: doctype, dn: name, method, args: JSON.stringify(args) }) });
  const j = await r.json().catch(() => ({})); if (!r.ok) { let m = "Erro"; try { m = JSON.parse(JSON.parse(j._server_messages)[0]).message; } catch (e) {} toast(String(m).replace(/<[^>]+>/g, "")); throw new Error(m); }
  return j.message;
};
const MktSegmentos = {
  setup() {
    const l = ref(null), op = ref(null), ed = ref(null), conta = ref(null), verQuem = ref(false), a = ref(false); let tc;
    const carregar = async () => { l.value = await apiSeg("lista"); }; onMounted(async () => { op.value = await apiSeg("opcoes"); carregar(); });
    const tipoDe = (r) => { for (const g of op.value?.grupos || []) { const x = g.regras.find((y) => y.regra === r); if (x) return x.tipo; } return "texto"; };
    const valoresDe = (r) => (op.value?.valores || {})[r] || [];
    const novo = () => { ed.value = { antigo: null, nome: "", descricao: "", logica: "Todas", marcador_auto: "", regras: [{ regra: "", valor: "", negar: 0 }], marca: "" }; contar(); };
    const abrir = async (s) => { const d = await apiSeg("obter", { nome: s.name }); ed.value = { antigo: d.nome, nome: d.nome, descricao: d.descricao || "", logica: d.logica, marcador_auto: d.marcador_auto || "", regras: d.regras.length ? d.regras : [{ regra: "", valor: "", negar: 0 }], marca: "" }; contar(); };
    const contar = () => { clearTimeout(tc); tc = setTimeout(async () => { const e = ed.value; if (!e) return;
      conta.value = await apiSeg("contar", { regras: JSON.stringify(e.regras.filter((r) => r.regra)), logica: e.logica, marca: e.marca || null }).catch(() => null); }, 400); };
    watch(() => ed.value && JSON.stringify([ed.value.regras, ed.value.logica, ed.value.marca]), contar);
    const gravar = async () => { const e = ed.value; a.value = true;
      try { await apiSeg("guardar", { nome: e.nome, regras: JSON.stringify(e.regras.filter((r) => r.regra)), logica: e.logica, descricao: e.descricao, marcador_auto: e.marcador_auto, antigo: e.antigo }, true);
        toast("Segmento gravado"); ed.value = null; carregar(); } finally { a.value = false; } };
    const apagar = async () => { if (!confirm(`Apagar o segmento «${ed.value.antigo}»?`)) return; await apiSeg("apagar", { nome: ed.value.antigo }, true); toast("Apagado"); ed.value = null; carregar(); };
    const desc = (r) => (r.negar ? "não " : "") + r.regra + (r.valor ? ": " + r.valor : "");
    return { l, op, ed, conta, verQuem, a, tipoDe, valoresDe, novo, abrir, gravar, apagar, desc, link };
  },
  template: `<div>
    <div class="pad" style="padding-bottom:12px;display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap"><div><h1>Segmentos</h1><div class="sub">Quem recebe cada campanha, por regras e por marcadores.</div></div>
      <div class="acoes-lista"><button class="btn prim" @click="novo">+ Novo segmento</button><a class="btn" href="#/mkt-marcadores">Marcadores</a></div></div>
    <div v-if="!l" class="carregar">A carregar…</div><div v-else-if="!l.length" class="vazio">Ainda não há segmentos.</div>
    <div v-else class="tabela-wrap cartoes-movel"><table><thead><tr><th>Segmento</th><th>Regras</th><th style="text-align:right">Podem receber</th><th>Marcador automático</th></tr></thead><tbody>
      <tr v-for="s in l" :key="s.name" @click="abrir(s)"><td class="cel-tit"><b>{{ s.name }}</b><div v-if="s.descricao" class="sub" style="font-size:12px">{{ s.descricao }}</div></td>
        <td style="white-space:normal">{{ (s.regras||[]).map(desc).join(s.logica==='Qualquer' ? ' ou ' : ' e ') || 'Todos' }}</td><td style="text-align:right"><b>{{ s.podem_receber }}</b></td><td>{{ s.marcador_auto || '—' }}</td></tr></tbody></table></div>
    <div v-if="ed" class="modal-fundo" @click.self="ed=null"><div class="modal" style="max-width:820px"><header><b>{{ ed.antigo ? 'Segmento' : 'Novo segmento' }}</b><button class="btn sm" @click="ed=null">Fechar</button></header>
      <form class="reg-form" @submit.prevent="gravar">
        <div class="reg-linha3" style="grid-template-columns:1fr 2fr"><label class="erp-campo"><span>Nome<span class="obrig">*</span></span><input v-model="ed.nome" required></label><label class="erp-campo"><span>Descrição</span><input v-model="ed.descricao"></label></div>
        <div class="seg-logica">Entra quem cumpre <select v-model="ed.logica"><option value="Todas">todas</option><option value="Qualquer">qualquer uma</option></select> das regras:</div>
        <div v-for="(r,i) in ed.regras" :key="i" class="seg-regra">
          <select v-model="r.regra" @change="r.valor=''"><option value="" disabled>Regra…</option><optgroup v-for="g in op.grupos" :key="g.titulo" :label="g.titulo"><option v-for="x in g.regras" :key="x.regra" :value="x.regra">{{ x.regra }}</option></optgroup></select>
          <select v-model.number="r.negar" class="seg-neg"><option :value="0">é</option><option :value="1">não é</option></select>
          <template v-if="r.regra && tipoDe(r.regra)!=='nenhum'">
            <select v-if="tipoDe(r.regra)==='lista'" v-model="r.valor"><option value="" disabled>Valor…</option><option v-for="v in valoresDe(r.regra)" :key="v" :value="v">{{ v }}</option></select>
            <input v-else v-model="r.valor" :type="tipoDe(r.regra)==='numero' ? 'number' : 'text'" placeholder="Valor"></template><span v-else></span>
          <button type="button" class="reg-ic" title="Tirar a regra" @click="ed.regras.splice(i,1)">×</button></div>
        <a href="javascript:void 0" class="sub" style="font-size:12px" @click="ed.regras.push({regra:'',valor:'',negar:0})">+ Regra</a>
        <div v-if="op.marcas.length > 1" class="reg-linha3" style="grid-template-columns:1fr 2fr"><label class="erp-campo"><span>Contar para a marca</span><select v-model="ed.marca"><option value="">Todas</option><option v-for="m in op.marcas" :key="m" :value="m">{{ m }}</option></select></label></div>
        <div class="seg-conta" v-if="conta"><b>{{ conta.no_segmento }}</b> no segmento · <b>{{ conta.podem_receber }}</b> podem receber · {{ conta.fora.sem_base }} sem base legal · {{ conta.fora.recusou }} recusaram · {{ conta.fora.saiu }} saíram
          <a v-if="conta.amostra.length" href="javascript:void 0" @click="verQuem=!verQuem">{{ verQuem ? 'Esconder' : 'Ver quem' }}</a></div>
        <div v-if="verQuem && conta" class="tabela-wrap" style="margin:0;max-height:260px"><table><tbody><tr v-for="x in conta.amostra" :key="x.doctype+x.name" style="cursor:default">
          <td><a :href="link(x.doctype,x.name)" target="_blank">{{ x.nome || x.email }}</a><div class="sub" style="font-size:12px">{{ x.email }}<template v-if="x.organizacao"> · {{ x.organizacao }}</template></div></td>
          <td><span class="etq" :class="x.pode ? 'verde' : 'ambar'">{{ x.pode ? 'pode receber' : x.estado }}</span></td><td class="sub">{{ (x.marcadores||[]).join(', ') }}</td></tr></tbody></table></div>
        <label class="erp-campo"><span>Pôr o marcador em quem entrar (opcional)</span><input v-model="ed.marcador_auto" placeholder="ex.: Clientes de 2026" list="marcadores-seg"><datalist id="marcadores-seg"><option v-for="v in (op.valores['Tem o marcador']||[])" :key="v" :value="v"></option></datalist></label>
        <div class="reg-botoes"><button v-if="ed.antigo" type="button" class="btn" style="margin-right:auto" @click="apagar">Apagar</button><button type="button" class="btn" @click="ed=null">Cancelar</button><button class="btn prim" :disabled="a">Gravar</button></div>
      </form></div></div>
  </div>`,
};
const MktMarcadores = {
  setup() { const l = ref(null); onMounted(async () => { l.value = (await apiSeg("marcadores")).marcadores; });
    const ver = (m, dt) => { try { sessionStorage.setItem("orbit.crm.marcador", JSON.stringify({ dt, m })); } catch (e) {} location.href = "/orbit?app=crm#/" + ({ Contact: "contactos", "CRM Lead": "leads", "CRM Organization": "empresas" }[dt]); };
    return { l, ver }; },
  template: `<div><div class="pad" style="padding-bottom:12px"><h1>Marcadores</h1><div class="sub">Etiquetas que se põem nos contactos, leads e organizações — à mão, na importação, em massa ou por um segmento.</div></div>
    <div v-if="!l" class="carregar">A carregar…</div><div v-else-if="!l.length" class="vazio">Ainda não há marcadores. Põem-se na ficha («Marcadores»), nas listas («Pôr marcador») ou na importação.</div>
    <div v-else class="tabela-wrap cartoes-movel"><table><thead><tr><th>Marcador</th><th style="text-align:right">Contactos</th><th style="text-align:right">Leads</th><th style="text-align:right">Organizações</th></tr></thead><tbody>
      <tr v-for="x in l" :key="x.marcador" style="cursor:default"><td class="cel-tit"><span class="etq">{{ x.marcador }}</span></td>
        <td style="text-align:right"><a href="javascript:void 0" @click="ver(x.marcador,'Contact')">{{ x.contactos }}</a></td><td style="text-align:right"><a href="javascript:void 0" @click="ver(x.marcador,'CRM Lead')">{{ x.leads }}</a></td><td style="text-align:right"><a href="javascript:void 0" @click="ver(x.marcador,'CRM Organization')">{{ x.organizacoes }}</a></td></tr></tbody></table></div></div>`,
};
const MktModelos = {
  setup() { const l = ref(null), ver = ref(null); onMounted(async () => { l.value = await api("orbit.marketing.page.modelos_de_email.modelos_de_email.galeria"); });
    const usar = (m) => { try { sessionStorage.setItem("orbit.erp.novo", JSON.stringify({ doctype: "Campanha de Marketing", modelo: m.chave })); } catch (e) {} location.hash = irErp("Campanha de Marketing", "novo"); };
    return { l, ver, usar }; },
  template: `<div><div class="pad" style="padding-bottom:12px"><h1>Modelos de email</h1><div class="sub">Os modelos, já com a sua marca. Escolha a ver.</div></div>
    <div v-if="!l" class="carregar">A carregar…</div>
    <div v-else class="mkt-galeria"><div v-for="m in l" :key="m.chave" class="cartao mkt-modelo"><div class="mkt-mini" @click="ver=m"><iframe sandbox="" :srcdoc="m.html" tabindex="-1"></iframe></div>
      <div style="padding:10px 12px"><b>{{ m.nome }}</b><div class="sub" style="font-size:12px">{{ m.para }}</div>
        <div style="display:flex;gap:6px;margin-top:8px"><button class="btn sm" @click="ver=m">Ver</button><button class="btn sm prim" @click="usar(m)">Usar numa campanha</button></div></div></div></div>
    <div v-if="ver" class="modal-fundo" @click.self="ver=null"><div class="modal" style="max-width:760px"><header><b>{{ ver.nome }}</b><span style="display:flex;gap:6px"><button class="btn sm prim" @click="usar(ver)">Usar</button><button class="btn sm" @click="ver=null">Fechar</button></span></header>
      <iframe sandbox="" :srcdoc="ver.html" style="width:100%;height:75vh;border:0;background:#f2f2f0"></iframe></div></div></div>`,
};
// O ciclo da campanha e da automação (os botões que o ecrã antigo põe pelo script do formulário)
const MktCiclo = {
  props: ["doctype", "doc"], emits: ["recarregar"],
  setup(props, { emit }) {
    const campanha = props.doctype === "Campanha de Marketing"; const vol = ref(null); const prev = ref(null); const a = ref(false);
    onMounted(async () => { if (campanha && props.doc.name) vol.value = await docMetodo(props.doctype, props.doc.name, "volume").catch(() => null); });
    const passo = async (m, args, msg) => { a.value = true; try { await docMetodo(props.doctype, props.doc.name, m, args || {}); if (msg) toast(msg); emit("recarregar"); } finally { a.value = false; } };
    const previsualizar = async () => { prev.value = await docMetodo(props.doctype, props.doc.name, "previsualizar"); };
    const quantos = async () => { const n = await docMetodo(props.doctype, props.doc.name, "contar"); toast("Se saísse agora: " + n + " destinatários"); };
    const rejeitar = () => { const m = prompt("Motivo da rejeição"); if (m) passo("rejeitar", { motivo: m }, "Devolvida a rascunho"); };
    const agendar = () => { const q = prompt("Sair em (AAAA-MM-DD HH:MM)", (props.doc.agendar_para || "").slice(0, 16)); if (q) passo("agendar", { quando: q.length === 16 ? q + ":00" : q }, "Saída marcada"); };
    const teste = () => { const p = prompt("Enviar o teste para (email)", window.__ctx?.utilizador || ""); if (p) passo("enviar_teste", { para: p }, "Teste enviado"); };
    const montar = () => { if ((props.doc.blocos || []).length && !confirm("Os blocos atuais são substituídos pelos do modelo. Continuar?")) return; passo("montar_blocos", {}, "Blocos montados a partir do modelo"); };
    const COR = { Rascunho: "", "Para aprovação": "ambar", Aprovada: "azul", "A enviar": "ambar", Pausada: "ambar", Enviada: "verde", Cancelada: "", Activa: "verde" };
    return { campanha, vol, prev, a, passo, previsualizar, quantos, rejeitar, agendar, teste, montar, COR };
  },
  template: `<div class="mkt-ciclo"><span class="etq" :class="COR[doc.estado]">{{ doc.estado }}</span>
    <span v-if="vol && vol.limite" class="sub" style="font-size:12px">Envios este mês: {{ vol.usado }} de {{ vol.limite }}</span>
    <span class="mkt-botoes">
      <button class="btn sm" @click="previsualizar">Pré-visualizar</button>
      <template v-if="campanha"><button class="btn sm" @click="quantos">Quantos recebem</button>
        <button v-if="doc.estado==='Rascunho'" class="btn sm" @click="montar">Montar a partir do modelo</button>
        <template v-if="['Rascunho','Para aprovação','Aprovada'].includes(doc.estado)"><button class="btn sm" @click="teste">Enviar teste</button><button class="btn sm" @click="agendar">Marcar a saída</button></template></template>
      <button v-if="doc.estado==='Rascunho'" class="btn sm prim" :disabled="a" @click="passo('submeter',null,'Enviada para aprovação')">Enviar para aprovação</button>
      <button v-if="doc.estado==='Para aprovação'" class="btn sm prim" :disabled="a" @click="passo('aprovar',null, campanha ? 'Aprovada' : 'Activa')">{{ campanha ? 'Aprovar' : 'Aprovar e ativar' }}</button>
      <button v-if="(campanha ? ['Para aprovação','Aprovada'] : ['Para aprovação']).includes(doc.estado)" class="btn sm" @click="rejeitar">Rejeitar</button>
      <button v-if="!campanha && doc.estado==='Activa'" class="btn sm" @click="passo('pausar',null,'Pausada')">Pausar</button>
      <button v-if="doc.estado==='Pausada'" class="btn sm" @click="passo('retomar',null,'Retomada')">Retomar</button>
      <button v-if="!campanha && doc.estado==='Pausada'" class="btn sm" @click="passo('editar')">Devolver a rascunho</button>
      <button v-if="campanha && !['Enviada','Cancelada'].includes(doc.estado)" class="btn sm" @click="confirm('Cancelar a campanha?') && passo('cancelar',null,'Cancelada')">Cancelar</button></span>
    <div v-if="prev" class="modal-fundo" @click.self="prev=null"><div class="modal" style="max-width:760px"><header><b>{{ prev.assunto || 'Sem linha de assunto' }}</b><button class="btn sm" @click="prev=null">Fechar</button></header>
      <div v-if="prev.simula" class="aviso" style="margin:10px 16px">Em simulação: nada sai.<template v-if="prev.falta && prev.falta.length"> Falta: {{ prev.falta.join('; ') }}.</template></div>
      <iframe sandbox="" :srcdoc="prev.html" style="width:100%;height:72vh;border:0;background:#f2f2f0"></iframe></div></div></div>`,
};
// A mensagem a desenhar-se enquanto se escreve (como o «Como fica» do ecrã antigo)
const MktComoFica = {
  props: ["doc"],
  setup(props) { const m = ref(null); let t; const desenhar = () => { clearTimeout(t); t = setTimeout(async () => { m.value = await api("orbit.marketing.mensagem.previsualizar_rascunho", { doc: JSON.stringify(props.doc) }, true).catch(() => m.value); }, 700); };
    onMounted(desenhar); watch(() => JSON.stringify(props.doc), desenhar); return { m }; },
  template: `<section class="cartao erp-sec"><header><b>Como fica</b><span class="sub" v-if="m">{{ m.assunto ? 'Assunto: ' + m.assunto : 'Sem linha de assunto' }}</span></header>
    <iframe v-if="m" sandbox="" :srcdoc="m.html" class="mkt-como"></iframe><div v-else class="carregar">A desenhar…</div></section>`,
};
// Base legal automática (Definições do Marketing): ver quem passaria a poder receber, e só depois aplicar
const MktBaseLegal = {
  setup() { const p = ref(null), a = ref(false);
    const ver = async () => { a.value = true; try { p.value = await api("orbit.marketing.base_legal.previsao"); } finally { a.value = false; } };
    const aplicar = async () => { if (!confirm(`Aplicar a ${p.value.total} registo(s)?`)) return; a.value = true; try { const r = await api("orbit.marketing.base_legal.aplicar", {}, true); toast(r.aplicados + " registo(s) atualizados"); p.value = null; } finally { a.value = false; } };
    return { p, a, ver, aplicar, link }; },
  template: `<section class="cartao erp-sec"><header><b>Base legal automática</b></header><div style="padding:0 16px 14px">
    <p class="sub" style="font-size:13px;margin:0 0 8px">Quem é cliente (comprou) ou empresa com NIPC e email profissional pode receber sem consentimento expresso. Veja primeiro quem passaria a poder receber.</p>
    <div style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn" :disabled="a" @click="ver">Ver quem passaria a poder receber</button><button v-if="p && p.total" class="btn prim" :disabled="a" @click="aplicar">Aplicar ({{ p.total }})</button></div>
    <template v-if="p"><div class="sub" style="margin:8px 0">{{ p.total }} registo(s): {{ p.b2b }} por serem empresas (b2b), {{ p.cliente }} por serem clientes.</div>
      <div class="tabela-wrap" style="margin:0;max-height:300px"><table><thead><tr><th>Registo</th><th>Organização</th><th>Base</th><th>Antes</th></tr></thead><tbody>
        <tr v-for="x in p.linhas" :key="x.doctype+x.name" style="cursor:default"><td><a :href="link(x.doctype,x.name)" target="_blank">{{ x.email }}</a></td><td>{{ x.organizacao || '—' }}<span v-if="x.nif" class="sub"> · {{ x.nif }}</span></td><td><span class="etq">{{ x.base }}</span></td><td class="sub">{{ x.antes }}</td></tr></tbody></table></div></template>
  </div></section>`,
};

// ── Lote 7 (25-11-2026): painéis do CRM e do Desk, base de conhecimento; árvore, Kanban e Calendário nas listas ──
const apiP7 = (m, a = {}, post = false) => api("paineis_mais." + m, a, post);
const BarrasH = { props: ["itens", "moeda"], setup(p) { const max = computed(() => Math.max(1, ...(p.itens || []).map((x) => x.n || x.valor || 0))); return { max, moedaEUR }; },
  template: `<div class="barras-h"><div v-for="x in itens" :key="x.r || x.fase" class="bh"><span class="bh-r" :title="x.r || x.fase">{{ x.r || x.fase }}</span><span class="bh-b"><i :style="{width: ((x.n||x.valor||0)/max*100)+'%'}"></i></span><b>{{ moeda ? moedaEUR(x.valor) : x.n }}</b></div><div v-if="!itens || !itens.length" class="sub" style="font-size:13px">Sem dados no período.</div></div>` };
const CrmPainel = {
  components: { GraficoBarras, BarrasH },
  setup() { const per = ref("30"), resp = ref(""), d = ref(null);
    const carregar = async () => { d.value = null; d.value = await apiP7("crm", { periodo: per.value, responsavel: resp.value }); }; onMounted(carregar); watch([per, resp], carregar);
    return { per, resp, d, moedaEUR }; },
  template: `<div class="pad"><div style="display:flex;justify-content:space-between;align-items:flex-end;gap:12px;flex-wrap:wrap;margin-bottom:14px"><div><h1>Painel</h1><div class="sub">Vendas e leads no período.</div></div>
      <div style="display:flex;gap:8px;flex-wrap:wrap"><select class="btn" v-model="per"><option value="7">7 dias</option><option value="30">30 dias</option><option value="90">90 dias</option><option value="365">12 meses</option></select>
        <select class="btn" v-model="resp"><option value="">Todos os responsáveis</option><option v-for="r in (d&&d.responsaveis)||[]" :key="r.v" :value="r.v">{{ r.r }}</option></select></div></div>
    <div v-if="!d" class="carregar">A carregar…</div><template v-else>
    <div class="erp-numeros"><div class="cartao"><small>Leads novas</small><b>{{ d.kpis.leads }}</b></div><div class="cartao"><small>Conversão das leads</small><b>{{ d.kpis.conversao_leads }} %</b></div>
      <div class="cartao"><small>Negócios ganhos</small><b>{{ d.kpis.ganhos }}</b></div><div class="cartao"><small>Valor ganho</small><b>{{ moedaEUR(d.kpis.valor_ganho) }}</b></div>
      <div class="cartao"><small>Taxa de ganho</small><b>{{ d.kpis.taxa_ganho }} %</b></div><div class="cartao"><small>Em aberto</small><b>{{ moedaEUR(d.kpis.em_aberto) }}</b></div><div class="cartao"><small>Previsto (pela probabilidade)</small><b>{{ moedaEUR(d.kpis.previsto) }}</b></div></div>
    <div class="painel-graficos">
      <section class="cartao erp-grafico largo"><header><b>Negócios criados e ganhos</b></header><GraficoBarras :labels="d.serie.labels" :series="d.serie.series"/></section>
      <section class="cartao erp-grafico"><header><b>Funil em aberto (valor por fase)</b></header><BarrasH :itens="d.por_fase" :moeda="true"/></section>
      <section class="cartao erp-grafico"><header><b>Motivos de perda</b></header><BarrasH :itens="d.motivos"/></section>
      <section class="cartao erp-grafico"><header><b>Leads por origem</b></header><BarrasH :itens="d.origens"/></section></div></template></div>`,
};
const DeskPainel = {
  components: { GraficoBarras, BarrasH },
  setup() { const per = ref("30"), eq = ref(""), d = ref(null);
    const carregar = async () => { d.value = null; d.value = await apiP7("desk", { periodo: per.value, equipa: eq.value }); }; onMounted(carregar); watch([per, eq], carregar);
    const h = (x) => x == null ? "—" : x < 1 ? Math.round(x * 60) + " min" : x < 48 ? x + " h" : Math.round(x / 24) + " d";
    return { per, eq, d, h }; },
  template: `<div class="pad"><div style="display:flex;justify-content:space-between;align-items:flex-end;gap:12px;flex-wrap:wrap;margin-bottom:14px"><div><h1>Painel do Desk</h1><div class="sub">Atendimento no período.</div></div>
      <div style="display:flex;gap:8px;flex-wrap:wrap"><select class="btn" v-model="per"><option value="7">7 dias</option><option value="30">30 dias</option><option value="90">90 dias</option><option value="365">12 meses</option></select>
        <select class="btn" v-model="eq"><option value="">Todas as equipas</option><option v-for="e in (d&&d.equipas)||[]" :key="e" :value="e">{{ e }}</option></select><a class="btn prim" href="#/tickets">Tickets</a></div></div>
    <div v-if="!d" class="carregar">A carregar…</div><template v-else>
    <div class="erp-numeros"><a class="cartao" href="#/tickets" style="text-decoration:none;color:inherit"><small>Em aberto</small><b>{{ d.kpis.abertos }}</b></a><div class="cartao"><small>Sem resposta</small><b>{{ d.kpis.sem_resposta }}</b></div>
      <div class="cartao"><small>Fora do prazo</small><b :style="{color: d.kpis.fora_prazo ? 'var(--acao)' : ''}">{{ d.kpis.fora_prazo }}</b></div><div class="cartao"><small>Criados no período</small><b>{{ d.kpis.criados }}</b></div>
      <div class="cartao"><small>1.ª resposta (média)</small><b>{{ h(d.kpis.resp_media_h) }}</b></div><div class="cartao"><small>Resolução (média)</small><b>{{ h(d.kpis.resol_media_h) }}</b></div>
      <div class="cartao"><small>SLA cumprido / falhado</small><b>{{ d.kpis.cumpridos }} / {{ d.kpis.falhados }}</b></div><div class="cartao"><small>Avaliação média</small><b>{{ d.kpis.avaliacao == null ? '—' : d.kpis.avaliacao + ' %' }}</b></div></div>
    <div class="painel-graficos"><section class="cartao erp-grafico largo"><header><b>Tickets por dia</b></header><GraficoBarras :labels="d.serie.labels" :series="d.serie.series"/></section>
      <section class="cartao erp-grafico"><header><b>Por estado</b></header><BarrasH :itens="d.estados"/></section>
      <section class="cartao erp-grafico"><header><b>Por responsável</b></header><BarrasH :itens="d.agentes"/></section></div></template></div>`,
};
const DeskKb = {
  setup() {
    const d = ref(null), cat = ref(""), est = ref(""), q = ref(""), art = ref(null), sel = ref([]), a = ref(false); let tq;
    const carregar = async () => { d.value = await apiP7("kb", { categoria: cat.value, estado: est.value, q: q.value }); sel.value = []; }; onMounted(carregar);
    watch([cat, est], carregar); watch(q, () => { clearTimeout(tq); tq = setTimeout(carregar, 300); });
    const nomeCat = (c) => ((d.value?.categorias || []).find((x) => x.name === c) || {}).nome || c || "Sem categoria";
    const abrir = async (x) => { art.value = x ? await apiP7("kb_artigo", { name: x.name }) : { titulo: "", html: "", estado: "Draft", categoria: cat.value || "", pode: { escrever: true } }; };
    const gravar = async (estado) => { a.value = true; try { art.value = await apiP7("kb_gravar", { name: art.value.name || null, titulo: art.value.titulo, html: art.value.html, categoria: art.value.categoria || null, estado: estado || art.value.estado }, true);
      toast(estado === "Published" ? "Publicado" : "Gravado"); carregar(); } finally { a.value = false; } };
    const apagar = async () => { if (!confirm("Apagar o artigo?")) return; await apiP7("kb_apagar", { name: art.value.name }, true); art.value = null; carregar(); };
    const novaCat = async () => { const n = prompt("Nome da categoria"); if (!n) return; await apiP7("kb_categoria", { nome: n }, true); carregar(); };
    const renomearCat = async (c) => { const n = prompt("Nome da categoria", c.nome); if (!n) return; await apiP7("kb_categoria", { nome: n, name: c.name }, true); carregar(); };
    const apagarCat = async (c) => { if (!confirm(`Apagar a categoria «${c.nome}»?`)) return; await apiP7("kb_categoria", { nome: "", name: c.name, apagar: 1 }, true); if (cat.value === c.name) cat.value = ""; carregar(); };
    const mover = async (campo, valor) => { await apiP7("kb_mover", { nomes: JSON.stringify(sel.value), [campo]: valor }, true); toast("Feito"); carregar(); };
    const EST = { Draft: "Rascunho", Published: "Publicado", Archived: "Arquivado" };
    return { d, cat, est, q, art, sel, a, nomeCat, abrir, gravar, apagar, novaCat, renomearCat, apagarCat, mover, EST, data };
  },
  template: `<div><div class="pad" style="padding-bottom:12px;display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap"><div><h1>Base de conhecimento</h1><div class="sub">Artigos de ajuda para a equipa e para os clientes.</div></div>
      <div class="acoes-lista"><button class="btn prim" @click="abrir(null)">+ Novo artigo</button><button class="btn" @click="novaCat">+ Categoria</button></div></div>
    <div v-if="!d" class="carregar">A carregar…</div>
    <div v-else class="kb-grelha"><aside class="cartao kb-cats"><button :class="{ativo:!cat}" @click="cat=''">Todas</button>
        <div v-for="c in d.categorias" :key="c.name" class="kb-cat" :class="{ativo:cat===c.name}"><button @click="cat=c.name">{{ c.nome }} <span class="sub">{{ c.n }}</span></button>
          <span class="kb-cat-acoes"><button title="Mudar o nome" @click="renomearCat(c)">✎</button><button title="Apagar" @click="apagarCat(c)">×</button></span></div></aside>
      <div><div class="vistas" style="padding:0"><button v-for="e in [['','Todos'],['Published','Publicados'],['Draft','Rascunhos'],['Archived','Arquivados']]" :key="e[0]" :class="{ativo:est===e[0]}" @click="est=e[0]">{{ e[1] }}</button></div>
        <div class="filtros" style="padding-left:0;padding-right:0"><input class="filtro" style="border-style:solid;min-width:220px" v-model="q" placeholder="Procurar no título e no texto…"></div>
        <div v-if="sel.length" class="selec" style="margin:0 0 0;border-radius:10px 10px 0 0;flex-wrap:wrap">{{ sel.length }} selecionado(s) ·
          <select class="btn sm" @change="$event.target.value && mover('categoria',$event.target.value); $event.target.value=''"><option value="">Mover para…</option><option v-for="c in d.categorias" :key="c.name" :value="c.name">{{ c.nome }}</option></select>
          <button class="btn sm" @click="mover('estado','Published')">Publicar</button><button class="btn sm" @click="mover('estado','Archived')">Arquivar</button><button class="btn sm" @click="mover('estado','Draft')">Passar a rascunho</button></div>
        <div class="tabela-wrap cartoes-movel" style="margin:0"><table><thead><tr><th style="width:34px"></th><th>Artigo</th><th>Categoria</th><th>Estado</th><th>Alterado</th></tr></thead><tbody>
          <tr v-for="x in d.artigos" :key="x.name" @click="abrir(x)"><td @click.stop class="cel-sel"><input type="checkbox" :value="x.name" v-model="sel"></td><td class="cel-tit"><b>{{ x.titulo }}</b><div v-if="x.autor" class="sub" style="font-size:12px">{{ x.autor }}</div></td>
            <td>{{ nomeCat(x.categoria) }}</td><td><span class="etq" :class="{Published:'verde',Draft:'ambar'}[x.estado]">{{ EST[x.estado] || x.estado }}</span></td><td class="sub">{{ data(x.quando,false) }}</td></tr></tbody></table>
          <div v-if="!d.artigos.length" class="vazio">Sem artigos.</div></div></div></div>
    <div v-if="art" class="modal-fundo" @click.self="art=null"><div class="modal" style="max-width:860px"><header><b>{{ art.name ? 'Artigo' : 'Novo artigo' }}</b><span style="display:flex;gap:6px"><a v-if="art.name && art.estado==='Published'" class="btn sm" :href="art.publico" target="_blank">Ver como o cliente</a><button class="btn sm" @click="art=null">Fechar</button></span></header>
      <div class="reg-form"><div class="reg-linha3" style="grid-template-columns:2fr 1fr"><label class="erp-campo"><span>Título</span><input v-model="art.titulo" :disabled="!art.pode.escrever"></label>
          <label class="erp-campo"><span>Categoria</span><select v-model="art.categoria" :disabled="!art.pode.escrever"><option value="">—</option><option v-for="c in d.categorias" :key="c.name" :value="c.name">{{ c.nome }}</option></select></label></div>
        <div class="erp-campo"><span>Texto</span><EditorRico v-model="art.html" :ro="!art.pode.escrever"/></div>
        <div class="reg-botoes"><button v-if="art.name && art.pode.apagar" class="btn" style="margin-right:auto" @click="apagar">Apagar</button><span class="etq" style="margin-right:auto" v-if="art.name">{{ EST[art.estado] }}</span>
          <template v-if="art.pode.escrever"><button class="btn" :disabled="a" @click="gravar(art.estado==='Published' ? 'Published' : 'Draft')">Gravar</button>
            <button v-if="art.estado!=='Published'" class="btn prim" :disabled="a" @click="gravar('Published')">Publicar</button><button v-else class="btn" :disabled="a" @click="gravar('Archived')">Arquivar</button></template></div></div></div></div>
  </div>`,
};
// Árvore: as tabelas hierárquicas (plano de contas, grupos de artigos, armazéns…) como a «Tree View» do desk
const ErpArvoreNo = { name: "ErpArvoreNo", props: ["doctype", "no", "nivel"],
  setup(p) { const aberto = ref(p.nivel === 0), filhos = ref(null);
    const alternar = async () => { if (!p.no.grupo) return; aberto.value = !aberto.value; if (aberto.value && !filhos.value) filhos.value = await apiP7("arvore", { doctype: p.doctype, pai: p.no.name }); };
    onMounted(async () => { if (aberto.value && p.no.grupo) filhos.value = await apiP7("arvore", { doctype: p.doctype, pai: p.no.name }); });
    const novoAqui = () => { try { sessionStorage.setItem("orbit.erp.novo", JSON.stringify({ doctype: p.doctype, ["parent_" + p.doctype.toLowerCase().replace(/ /g, "_")]: p.no.name })); } catch (e) {} location.hash = irErp(p.doctype, "novo"); };
    return { aberto, filhos, alternar, novoAqui, irErp }; },
  template: `<div class="arv-no"><div class="arv-linha" :style="{paddingLeft: (nivel*18+8)+'px'}"><button class="arv-seta" @click="alternar" :style="{visibility: no.grupo ? 'visible' : 'hidden'}">{{ aberto ? '▾' : '▸' }}</button>
      <a :href="irErp(doctype, no.name)">{{ no.titulo }}</a><small class="sub" v-if="no.extra"> · {{ no.extra }}</small><button v-if="no.grupo" class="arv-mais" title="Novo dentro deste" @click="novoAqui">+</button></div>
    <template v-if="aberto && filhos"><ErpArvoreNo v-for="f in filhos" :key="f.name" :doctype="doctype" :no="f" :nivel="nivel+1"/><div v-if="!filhos.length" class="sub" :style="{paddingLeft: ((nivel+1)*18+30)+'px', fontSize:'12px'}">Vazio</div></template></div>`,
};
const ErpArvore = { components: { ErpArvoreNo }, props: ["doctype"], setup(p) { const raiz = ref(null); onMounted(async () => { raiz.value = await apiP7("arvore", { doctype: p.doctype }); }); return { raiz }; },
  template: `<div class="cartao arv"><div v-if="!raiz" class="carregar">A carregar…</div><ErpArvoreNo v-for="r in raiz||[]" :key="r.name" :doctype="doctype" :no="r" :nivel="0"/></div>` };
// Kanban por um campo de escolha (como a vista Kanban do desk)
const ErpKanban = { props: ["doctype", "campo", "def", "linhas", "titulo"], emits: ["mudou"],
  setup(p, { emit }) { const arr = ref(null), alvo = ref("");
    // 27-11-2026 (funil do processo): no estado de documentos submetíveis, colunas pela ordem do caminho e sem arrastar
    const processo = computed(() => p.campo === "status" && p.def.processo ? p.def.processo : null);
    const fixo = computed(() => p.campo === "status" && p.def.submetivel);
    const cols = computed(() => { const c = (p.def.campos || []).find((x) => x.campo === p.campo) || {}; const ops = processo.value || c.opcoes || []; return ops.map((o) => ({ v: o, itens: p.linhas.filter((l) => (l[p.campo] || "") === o) })); });
    const largar = async (col) => { const x = arr.value; arr.value = null; alvo.value = ""; if (!x || x[p.campo] === col.v) return;
      if (fixo.value) { toast("O estado muda pelas acções do documento (receber, faturar, pagar…), não arrastando."); return; }
      const r = await apiL("em_massa", { doctype: p.doctype, nomes: JSON.stringify([x.name]), acao: "editar", campo: p.campo, valor: col.v }, true);
      if (r.falhas.length) toast(r.falhas[0].erro); else toast("→ " + col.v); emit("mudou"); };
    return { cols, arr, alvo, largar, irErp, statusPt, fixo }; },
  template: `<div class="funil" :style="{gridTemplateColumns:'repeat('+cols.length+',minmax(220px,1fr))'}"><div v-for="c in cols" :key="c.v" class="coluna" :class="{alvo: alvo===c.v}" @dragover.prevent="alvo=c.v" @dragleave="alvo=''" @drop.prevent="largar(c)">
      <header><b>{{ statusPt(c.v) || '—' }} <span class="sub" style="font-weight:500">{{ c.itens.length }}</span></b></header>
      <a v-for="l in c.itens" :key="l.name" class="cartao negocio" :href="irErp(doctype,l.name)" :draggable="!fixo" @dragstart="arr=l" style="display:block;text-decoration:none;color:inherit"><h3>{{ l[titulo] || l.name }}</h3><div v-if="l[titulo] && l[titulo]!==l.name" class="sub" style="font-size:12px">{{ l.name }}</div></a></div></div>` };
// Calendário do mês por um campo de data
const ErpCalendario = { props: ["doctype", "campo", "titulo"],
  setup(p) { const hoje = new Date(); const ano = ref(hoje.getFullYear()), mes = ref(hoje.getMonth() + 1), itens = ref([]);
    const carregar = async () => { const ini = `${ano.value}-${String(mes.value).padStart(2, "0")}-01`; const fim = new Date(ano.value, mes.value, 0); const f = `${ano.value}-${String(mes.value).padStart(2, "0")}-${String(fim.getDate()).padStart(2, "0")}`;
      itens.value = (await apiL("lista", { doctype: p.doctype, filtros: JSON.stringify([[p.campo, "between", [ini, f + " 23:59:59"]]]), colunas: JSON.stringify([p.campo]), por: 500 })).linhas; };
    onMounted(carregar); watch(() => p.campo, carregar);
    const mudar = (k) => { let m = mes.value + k, a = ano.value; if (m < 1) { m = 12; a--; } if (m > 12) { m = 1; a++; } mes.value = m; ano.value = a; carregar(); };
    const celulas = computed(() => { const p1 = new Date(ano.value, mes.value - 1, 1); const off = (p1.getDay() + 6) % 7; const n = new Date(ano.value, mes.value, 0).getDate(); const out = [];
      for (let i = 0; i < off; i++) out.push(null); for (let d = 1; d <= n; d++) { const iso = `${ano.value}-${String(mes.value).padStart(2, "0")}-${String(d).padStart(2, "0")}`; out.push({ d, iso, itens: itens.value.filter((x) => String(x[p.campo] || "").slice(0, 10) === iso) }); } return out; });
    const nomeMes = computed(() => new Date(ano.value, mes.value - 1, 1).toLocaleDateString("pt-PT", { month: "long", year: "numeric" }));
    return { celulas, mudar, nomeMes, irErp }; },
  template: `<div class="cartao cal-erp"><div style="display:flex;justify-content:space-between;align-items:center;padding:10px 12px"><button class="btn sm" @click="mudar(-1)">‹</button><b style="text-transform:capitalize">{{ nomeMes }}</b><button class="btn sm" @click="mudar(1)">›</button></div>
    <div class="cal-erp-grelha"><div v-for="s in ['seg','ter','qua','qui','sex','sáb','dom']" :key="s" class="cal-erp-sem">{{ s }}</div>
      <div v-for="(c,i) in celulas" :key="i" class="cal-erp-dia" :class="{vazio:!c}"><template v-if="c"><small>{{ c.d }}</small><a v-for="x in c.itens.slice(0,4)" :key="x.name" :href="irErp(doctype,x.name)" class="cal-erp-item">{{ x[titulo] || x.name }}</a><small v-if="c.itens.length>4" class="sub">+{{ c.itens.length-4 }}</small></template></div></div></div>` };

const ErpModulo = {
  props: ["barra"],
  setup(props) {
    const m = ref(null); const nums = ref([]);
    const res = ref({});
    onMounted(async () => { m.value = await api("erp.menu", { barra: props.barra }); nums.value = await api("erp.numeros", { barra: props.barra }).catch(() => []);
      // 25-11-2026: o bloco «A receber»/«A pagar» diz logo quanto está em dívida e quanto já venceu
      for (const l of new Set(m.value.secoes.flatMap((s) => s.resumos || []))) api("contas.resumo", { lado: l }).then((r) => { res.value[l] = r.totais; }).catch(() => {}); });
    const moeda = (v) => moedaEUR(v);
    const href = (i) => i.tipo === "doc" ? irErp(i.doctype, i.single ? i.doctype : null) : i.tipo === "rel" ? "#/erp-rel/" + encodeURIComponent(i.relatorio) : i.tipo === "mod" ? "#/erp-m/" + encodeURIComponent(i.barra) : i.tipo === "painel" ? "#/erp-painel/" + encodeURIComponent(i.painel) : i.tipo === "nativo" ? "#/" + i.rota : "#/";
    const valorN = (n) => n.tipo === "Currency" ? new Intl.NumberFormat("pt-PT", { style: "currency", currency: "EUR" }).format(n.valor || 0) : new Intl.NumberFormat("pt-PT").format(n.valor || 0);
    // 25-11-2026 (Vítor): blocos arrumados — sem título passa a «Principal», os longos dividem-se em 1 e 2 (colunas equilibradas no CSS)
    const secoes = computed(() => { const out = []; for (const sx of (m.value?.secoes || [])) {
        const t = sx.titulo ? sx.titulo.charAt(0).toUpperCase() + sx.titulo.slice(1) : "Principal";
        if (sx.itens.length > 10) { const meio = Math.ceil(sx.itens.length / 2);
          out.push({ ...sx, titulo: t + " · 1", itens: sx.itens.slice(0, meio) }, { ...sx, titulo: t + " · 2", itens: sx.itens.slice(meio), resumos: [] }); }
        else out.push({ ...sx, titulo: t }); } return out; });
    const guardarFiltro = (i) => { try { sessionStorage.setItem("orbit.erp.filtro", JSON.stringify({ doctype: i.doctype, filtros: i.filtros })); } catch (e) {} };
    return { m, href, nums, valorN, res, moeda, secoes, guardarFiltro };
  },
  template: `<div v-if="m" class="pad">
    <h1>{{ m.titulo }}</h1><div class="sub" style="margin-bottom:16px">Documentos, configuração e relatórios deste módulo</div>
    <div v-if="nums.length" class="erp-numeros"><div v-for="n in nums" :key="n.rotulo" class="cartao"><small>{{ n.rotulo }}</small><b>{{ valorN(n) }}</b></div></div>
    <div class="erp-mod">
      <section v-for="s in secoes" :key="s.titulo" class="cartao erp-sec-mod">
        <header><b>{{ s.titulo }}</b><span class="sub" style="font-weight:400;font-size:12px">{{ s.itens.length }}</span></header>
        <a v-for="l in (s.resumos||[])" :key="l" v-show="res[l]" :href="'#/contas/'+l" class="erp-resumo">
          <span><small>Em dívida</small><b>{{ res[l] && moeda(res[l].divida) }}</b></span>
          <span :class="{alerta: res[l] && res[l].vencido > 0}"><small>Vencido</small><b>{{ res[l] && moeda(res[l].vencido) }}</b></span>
          <span><small>{{ l==='receber' ? 'Faturas por receber' : 'Faturas por pagar' }}</small><b>{{ res[l] && res[l].documentos }}</b></span></a>
        <div class="erp-itens"><a v-for="i in s.itens" :key="i.rotulo" :href="href(i)" :class="{destaque: i.tipo==='nativo'}" @click="i.filtros && guardarFiltro(i)">{{ i.rotulo }}</a></div>
      </section>
    </div></div><div v-else class="vazio">A carregar…</div>`,
};

const OPS_ERP = { texto: [["like", "contém"], ["=", "é igual a"], ["!=", "não é"], ["not like", "não contém"], ["is", "preenchido / vazio"]],
  numero: [["=", "="], [">", ">"], ["<", "<"], [">=", "≥"], ["<=", "≤"], ["!=", "≠"]],
  data: [["timespan", "período"], [">=", "a partir de"], ["<=", "até"], ["between", "entre"], ["=", "no dia"], ["is", "preenchido / vazio"]],
  escolha: [["=", "é"], ["!=", "não é"], ["in", "é um de"], ["not in", "não é nenhum de"], ["is", "preenchido / vazio"]],
  ligacao: [["=", "é"], ["!=", "não é"], ["like", "contém"], ["in", "é um de"], ["is", "preenchido / vazio"]] };
const PERIODOS_ERP = [["hoje", "Hoje"], ["ontem", "Ontem"], ["esta_semana", "Esta semana"], ["semana_passada", "Semana passada"], ["este_mes", "Este mês"], ["mes_passado", "Mês passado"],
  ["ultimos_7", "Últimos 7 dias"], ["ultimos_30", "Últimos 30 dias"], ["este_ano", "Este ano"], ["ano_passado", "Ano passado"], ["proxima_semana", "Próxima semana"], ["proximo_mes", "Próximo mês"]];
const tipoOp = (c) => !c ? "texto" : ["Int", "Float", "Currency", "Percent"].includes(c.tipo) ? "numero" : ["Date", "Datetime"].includes(c.tipo) ? "data"
  : (c.tipo === "Select" || c.opcoes_v) ? "escolha" : ["Link", "Dynamic Link"].includes(c.tipo) ? "ligacao" : c.tipo === "Check" ? "escolha" : "texto";
const apiL = (m, a = {}, post = false) => api("erp_listas." + m, a, post);
const ErpLista = {
  props: ["doctype"],
  setup(props) {
    // lote 4 (25-11): a lista do desk inteira — filtros por qualquer campo, contagem, colunas, ordem, vistas guardadas,
    // selecção e acções em massa, PDF em lote e exportar (orbit/interface/erp_listas.py)
    const meta = ref(null); const def = ref(null); const linhas = ref([]); const mais = ref(false); const q = ref(""); const pagina = ref(0); const total = ref(0);
    const colunas = ref([]); const colEscolhidas = ref([]); const titulo = ref(null); const a = ref(false); const ordem = ref("modified desc"); let tq;
    const filtros = ref([]); const novoF = ref(null); const verCols = ref(false); const sel = ref([]); const massa = ref({ acao: "", campo: "", valor: "" });
    const modo = ref("lista"); const campoK = ref(""); const campoC = ref("");
    const vs = ref({ vistas: [], padrao: "" }); const vistaAtiva = ref(""); const menuV = ref(false);
    const chaveLS = () => "orbit.erp.lista." + props.doctype;
    const carregar = async (junta = false) => {
      a.value = true;
      const colsPedidas = modo && modo.value === "kanban" && campoK.value ? [...new Set((colEscolhidas.value.length ? colEscolhidas.value : colunas.value).concat([campoK.value]))] : colEscolhidas.value;
      try { const r = await apiL("lista", { doctype: props.doctype, q: q.value, pagina: pagina.value, ordem: ordem.value, filtros: JSON.stringify(filtros.value), colunas: JSON.stringify(colsPedidas), por: modo && modo.value === "kanban" ? 300 : 50 });
        linhas.value = junta ? linhas.value.concat(r.linhas) : r.linhas; mais.value = r.mais; colunas.value = r.colunas; titulo.value = r.titulo; total.value = r.total;
        if (!junta) sel.value = [];
        try { localStorage.setItem(chaveLS(), JSON.stringify({ filtros: filtros.value, colunas: colEscolhidas.value, ordem: ordem.value, vista: vistaAtiva.value })); } catch (e) {}
      } finally { a.value = false; } };
    onMounted(async () => {
      meta.value = await metaErp(props.doctype); if (meta.value.single) { location.replace(irErp(props.doctype, props.doctype)); return; }
      def.value = await apiL("definicao", { doctype: props.doctype }).catch(() => ({ campos: [], pode: {} }));
      vs.value = await apiL("vistas", { doctype: props.doctype }).catch(() => ({ vistas: [], padrao: "" }));
      let g = null; try { g = JSON.parse(localStorage.getItem(chaveLS()) || "null"); } catch (e) {}
      // lote 6: os atalhos das fichas abrem a lista já filtrada (ex.: faturas deste cliente)
      let pre = null; try { pre = JSON.parse(sessionStorage.getItem("orbit.erp.filtro") || "null"); sessionStorage.removeItem("orbit.erp.filtro"); } catch (e) {}
      if (pre && pre.doctype === props.doctype) g = { filtros: pre.filtros, colunas: (g || {}).colunas || [], ordem: "modified desc", vista: "" };
      const pad = vs.value.vistas.find((v) => v.nome === vs.value.padrao);
      if (g) { filtros.value = g.filtros || []; colEscolhidas.value = g.colunas || []; ordem.value = g.ordem || ordem.value; vistaAtiva.value = g.vista || ""; }
      else if (pad) aplicarVista(pad, false);
      carregar();
    });
    watch(q, () => { clearTimeout(tq); tq = setTimeout(() => { pagina.value = 0; carregar(); }, 300); });
    const doMenu = () => { let pre = null; try { pre = JSON.parse(sessionStorage.getItem("orbit.erp.filtro") || "null"); } catch (e) {}
      if (!pre || pre.doctype !== props.doctype) return; sessionStorage.removeItem("orbit.erp.filtro"); filtros.value = pre.filtros || []; vistaAtiva.value = ""; pagina.value = 0; carregar(); };
    onMounted(() => window.addEventListener("orbit-erp-filtro", doMenu)); onUnmounted(() => window.removeEventListener("orbit-erp-filtro", doMenu));
    // devoluções: nascem sempre de um documento original (como o «Criar › Devolução» do ERPNext)
    const DEVOL = { "Sales Invoice": ["Nova nota de crédito", "Fatura a corrigir"], "Delivery Note": ["Nova guia de devolução", "Guia a devolver"],
      "Purchase Invoice": ["Nova nota de débito", "Fatura de fornecedor a corrigir"], "Purchase Receipt": ["Nova devolução a fornecedor", "Receção a devolver"] };
    const eDevol = computed(() => !!DEVOL[props.doctype] && filtros.value.some((f) => f[0] === "is_return" && Number(f[2]) === 1));
    const rotDevol = computed(() => (DEVOL[props.doctype] || [])[0] || ""); const rotOrig = computed(() => (DEVOL[props.doctype] || [])[1] || "");
    const orig = ref(null);
    const procurarOrig = async () => { const venda = ["Sales Invoice", "Delivery Note"].includes(props.doctype);
      const r = await apiL("lista", { doctype: props.doctype, filtros: JSON.stringify([["docstatus", "=", 1], ["is_return", "=", 0]]), q: orig.value.q || "", ordem: "modified desc", pagina: 0,
        colunas: JSON.stringify([venda ? "customer_name" : "supplier_name", "posting_date", "grand_total"]), por: 30 }).catch(() => null);
      orig.value.lista = ((r && r.linhas) || []).map((x) => ({ name: x.name, parte: x.customer_name || x.supplier_name || "", data: x.posting_date || "", total: x.grand_total })); };
    const abrirOrig = () => { orig.value = { q: "", lista: null }; procurarOrig(); };
    const devolver = async (n) => { const r = await api("erp.criar_de", { doctype: props.doctype, name: n, destino: "devolucao" }, true);
      try { sessionStorage.setItem("orbit.erp.novo", JSON.stringify(r.doc)); } catch (e) {} orig.value = null; location.hash = irErp(props.doctype, "novo"); };
    const campo = (f) => (meta.value?.campos || []).find((c) => c.fieldname === f) || { fieldname: f, label: ((def.value?.campos || []).find((c) => c.campo === f) || {}).rotulo || f };
    const cdef = (f) => (def.value?.campos || []).find((c) => c.campo === f);
    const ordenar = (f) => { ordem.value = ordem.value === f + " desc" ? f + " asc" : f + " desc"; pagina.value = 0; carregar(); };
    const maisLinhas = () => { pagina.value++; carregar(true); };
    const abrir = (n) => { location.hash = irErp(props.doctype, n); };
    // filtros
    const abrirFiltro = () => { novoF.value = { campo: "", op: "", valor: "", valor2: "" }; };
    const opsDe = (f) => OPS_ERP[tipoOp(cdef(f))];
    const juntarFiltro = () => { const n = novoF.value; if (!n.campo || !n.op) return;
      let v = n.valor; if (n.op === "between") v = [n.valor, n.valor2]; if (["in", "not in"].includes(n.op)) v = String(n.valor).split(",").map((x) => x.trim()).filter(Boolean);
      filtros.value = filtros.value.concat([[n.campo, n.op, v]]); novoF.value = null; vistaAtiva.value = ""; pagina.value = 0; carregar(); };
    const tirarFiltro = (i) => { filtros.value = filtros.value.filter((_, k) => k !== i); vistaAtiva.value = ""; pagina.value = 0; carregar(); };
    const limpar = () => { filtros.value = []; q.value = ""; vistaAtiva.value = ""; pagina.value = 0; carregar(); };
    const rotuloOp = (f) => ((opsDe(f[0]) || []).find((o) => o[0] === f[1]) || [, f[1]])[1];
    const rotuloValor = (f) => { const c = cdef(f[0]); if (f[1] === "timespan") return (PERIODOS_ERP.find((p) => p[0] === f[2]) || [, f[2]])[1];
      if (f[1] === "is") return f[2] === "set" ? "preenchido" : "vazio"; if (c && c.opcoes_v) return (c.opcoes_v.find((o) => String(o.v) === String(f[2])) || {}).r || f[2];
      return Array.isArray(f[2]) ? f[2].join(f[1] === "between" ? " e " : ", ") : f[2]; };
    // colunas
    const alternarCol = (c) => { const cur = colEscolhidas.value.length ? colEscolhidas.value : colunas.value.slice();
      colEscolhidas.value = cur.includes(c) ? cur.filter((x) => x !== c) : cur.concat([c]); vistaAtiva.value = ""; carregar(); };
    const moverCol = (c, d) => { const cur = colEscolhidas.value.length ? colEscolhidas.value.slice() : colunas.value.slice(); const i = cur.indexOf(c); const j = i + d;
      if (i < 0 || j < 0 || j >= cur.length) return; [cur[i], cur[j]] = [cur[j], cur[i]]; colEscolhidas.value = cur; carregar(); };
    const colunasPadrao = () => { colEscolhidas.value = []; carregar(); };
    // vistas
    const aplicarVista = (v, recarregar = true) => { const c = v.config || {}; filtros.value = c.filtros || []; colEscolhidas.value = c.colunas || []; ordem.value = c.ordem || "modified desc"; q.value = c.q || "";
      vistaAtiva.value = v.nome + (v.equipa ? "*" : ""); pagina.value = 0; if (recarregar) carregar(); };
    const vistaPorOmissao = () => { filtros.value = []; colEscolhidas.value = []; ordem.value = "modified desc"; q.value = ""; vistaAtiva.value = ""; pagina.value = 0; carregar(); };
    const gravarVista = async (equipa, nomeAtual) => { const nome = prompt(nomeAtual ? "Nome da vista" : "Nome da nova vista", nomeAtual || ""); if (!nome) return;
      vs.value = await apiL("vista_gravar", { doctype: props.doctype, nome, equipa: equipa ? 1 : 0, antigo: nomeAtual || null, config: JSON.stringify({ filtros: filtros.value, colunas: colEscolhidas.value, ordem: ordem.value, q: q.value }) }, true);
      vistaAtiva.value = nome + (equipa ? "*" : ""); toast("Vista gravada"); };
    const vistaAtual = computed(() => vs.value.vistas.find((v) => v.nome + (v.equipa ? "*" : "") === vistaAtiva.value));
    const apagarVista = async () => { const v = vistaAtual.value; if (!v || !confirm(`Apagar a vista «${v.nome}»?`)) return; vs.value = await apiL("vista_apagar", { doctype: props.doctype, nome: v.nome, equipa: v.equipa ? 1 : 0 }, true); vistaPorOmissao(); };
    const porOmissao = async () => { const v = vistaAtual.value; vs.value = await apiL("vista_padrao", { doctype: props.doctype, nome: v && !v.equipa ? v.nome : "" }, true); toast(v ? "Abre sempre com «" + v.nome + "»" : "Sem vista por omissão"); };
    // selecção e massa
    const todos = computed({ get: () => !!linhas.value.length && sel.value.length === linhas.value.length, set: (v) => (sel.value = v ? linhas.value.map((l) => l.name) : []) });
    const opsMassa = computed(() => { const p = def.value?.pode || {}; const o = [];
      if (p.escrever) o.push(["editar", "Alterar um campo"], ["atribuir", "Atribuir a"], ["etiqueta", "Pôr etiqueta"]);
      if (p.submeter) o.push(["submeter", "Submeter"]); if (p.cancelar) o.push(["cancelar", "Cancelar"]); if (p.apagar) o.push(["apagar", "Apagar"]); return o; });
    const camposEditaveis = computed(() => (def.value?.campos || []).filter((c) => !["owner", "creation", "modified", "_assign", "_user_tags", "docstatus"].includes(c.campo)));
    const pessoasL = ref([]); watch(() => massa.value.acao, async (x) => { if (x === "atribuir" && !pessoasL.value.length) pessoasL.value = await apiConv("pessoas").catch(() => []); });
    const aplicarMassa = async () => { const m = massa.value; if (!m.acao) return;
      if (["apagar", "cancelar", "submeter"].includes(m.acao) && !confirm(`${{ apagar: "Apagar", cancelar: "Cancelar", submeter: "Submeter" }[m.acao]} ${sel.value.length} registo(s)?`)) return;
      const r = await apiL("em_massa", { doctype: props.doctype, nomes: JSON.stringify(sel.value), acao: m.acao, campo: m.campo || null, valor: m.valor }, true);
      toast(`${r.feitos} feito(s)` + (r.falhas.length ? ` · ${r.falhas.length} falharam: ${r.falhas[0].erro}` : "")); massa.value = { acao: "", campo: "", valor: "" }; carregar(); };
    const pdfLote = () => { const p = new URLSearchParams({ doctype: props.doctype, name: JSON.stringify(sel.value) }); window.open("/api/method/frappe.utils.print_format.download_multi_pdf?" + p.toString(), "_blank"); };
    const exportar = (soSel) => { const p = new URLSearchParams({ doctype: props.doctype, q: q.value, filtros: JSON.stringify(filtros.value), ordem: ordem.value, colunas: JSON.stringify(colEscolhidas.value), nomes: soSel ? JSON.stringify(sel.value) : "" });
      window.location.href = "/api/method/orbit.interface.erp_listas.exportar?" + p.toString(); };
    const maisAc = ref(false);
    // lote 6/7: Lista | Árvore | Kanban | Calendário (como as vistas do desk)
    let mo0 = "lista"; try { mo0 = localStorage.getItem("orbit.erp.modo." + props.doctype) || mo0; } catch (e) {}
    modo.value = mo0;
    watch(modo, (v) => { if (v === "kanban") setTimeout(() => carregar(), 0); try { localStorage.setItem("orbit.erp.modo." + props.doctype, v); } catch (e) {} if (v === "kanban" && !campoK.value) campoK.value = (def.value?.kanban || [])[0] || ""; if (v === "calendario" && !campoC.value) campoC.value = (def.value?.calendario || [])[0] || ""; });
    watch(def, (d) => { if (!d) return; campoK.value = campoK.value || (d.kanban || [])[0] || ""; campoC.value = campoC.value || (d.calendario || [])[0] || "";
      if ((modo.value === "arvore" && !d.arvore) || (modo.value === "kanban" && !(d.kanban || []).length) || (modo.value === "calendario" && !(d.calendario || []).length)) modo.value = "lista"; });
    const fechar = () => { menuV.value = false; maisAc.value = false; }; onMounted(() => document.addEventListener("click", fechar)); onUnmounted(() => document.removeEventListener("click", fechar));
    // o «Estado» do documento já tem coluna própria (selo); não se repete o campo status
    const colunasVis = computed(() => colunas.value.filter((c) => !(meta.value?.submetivel && c === "status")));
    const TIT_DEVOL = { "Sales Invoice": "Notas de crédito", "Delivery Note": "Guias de devolução", "Purchase Invoice": "Notas de débito", "Purchase Receipt": "Devoluções a fornecedor" };
    return { TIT_DEVOL, eDevol, rotDevol, rotOrig, orig, procurarOrig, abrirOrig, devolver, modo, campoK, campoC, colunasVis, meta, def, linhas, mais, q, colunas, titulo, a, total, campo, cdef, textoValor, ordenar, ordem, maisLinhas, abrir, irErp, ESTADO_DOC, COR_STATUS, statusPt, cor, ini, tr,
      filtros, novoF, abrirFiltro, opsDe, juntarFiltro, tirarFiltro, limpar, rotuloOp, rotuloValor, PERIODOS_ERP, tipoOp, verCols, alternarCol, moverCol, colunasPadrao, colEscolhidas,
      vs, vistaAtiva, menuV, aplicarVista, vistaPorOmissao, gravarVista, vistaAtual, apagarVista, porOmissao, sel, todos, massa, opsMassa, camposEditaveis, pessoasL, aplicarMassa, pdfLote, exportar, maisAc };
  },
  template: `<div v-if="meta">
    <div class="pad" style="padding-bottom:12px;display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap">
      <div><h1>{{ eDevol ? TIT_DEVOL[doctype] : meta.rotulo }}</h1><div class="sub">{{ total }} {{ total===1 ? 'registo' : 'registos' }}<template v-if="filtros.length || q"> com estes filtros</template></div></div>
      <div class="acoes-lista" :class="{abertas: maisAc}" @click.stop><button v-if="meta.pode.create && eDevol" class="btn prim" @click="abrirOrig">+ {{ rotDevol }}</button><a v-else-if="meta.pode.create" class="btn prim" :href="irErp(doctype,'novo')">+ Novo</a>
        <button class="btn so-movel" @click="maisAc=!maisAc" aria-label="Mais ações">⋯</button>
        <span class="acoes-sec" @click="maisAc=false"><button v-if="def && def.pode.exportar" class="btn" @click="exportar(false)">Exportar</button><a v-if="meta.pode.create" class="btn" :href="'#/importar-erp/'+encodeURIComponent(doctype)">Importar</a></span></div>
    </div>
    <div v-if="def && (def.arvore || def.kanban.length || def.calendario.length)" class="vistas modos-erp">
      <button :class="{ativo: modo==='lista'}" @click="modo='lista'">Lista</button><button v-if="def.arvore" :class="{ativo: modo==='arvore'}" @click="modo='arvore'">Árvore</button>
      <button v-if="def.kanban.length" :class="{ativo: modo==='kanban'}" @click="modo='kanban'">{{ def.processo ? 'Funil' : 'Kanban' }}</button><button v-if="def.calendario.length" :class="{ativo: modo==='calendario'}" @click="modo='calendario'">Calendário</button>
      <select v-if="modo==='kanban' && def.kanban.length>1" class="btn sm" v-model="campoK" style="margin-left:auto"><option v-for="c in def.kanban" :key="c" :value="c">{{ campo(c).label }}</option></select>
      <select v-if="modo==='calendario' && def.calendario.length>1" class="btn sm" v-model="campoC" style="margin-left:auto"><option v-for="c in def.calendario" :key="c" :value="c">{{ campo(c).label }}</option></select></div>
    <div v-if="modo==='arvore'" style="padding:0 24px 24px"><ErpArvore :doctype="doctype"/></div>
    <div v-else-if="modo==='calendario' && campoC" style="padding:0 24px 24px"><ErpCalendario :doctype="doctype" :campo="campoC" :titulo="titulo" :key="campoC"/></div>
    <template v-else>
    <div class="vistas">
      <button :class="{ativo: !vistaAtiva}" @click="vistaPorOmissao">Todos</button>
      <button v-for="v in vs.vistas" :key="v.nome+v.equipa" :class="{ativo: vistaAtiva===v.nome+(v.equipa?'*':'')}" @click="aplicarVista(v)">{{ v.equipa ? '👥 ' : '' }}{{ v.nome }}{{ vs.padrao===v.nome && !v.equipa ? ' ★' : '' }}</button>
      <span class="reg-menu" @click.stop><button class="mais" @click="menuV=!menuV">+ Vista ▾</button>
        <div v-if="menuV" class="cartao reg-menu-lista" style="left:0;right:auto" @click="menuV=false">
          <button @click="gravarVista(false)">Guardar como vista minha…</button>
          <button v-if="def && def.pode.escrever" @click="gravarVista(true)">Guardar como vista da equipa…</button>
          <template v-if="vistaAtual"><button @click="gravarVista(vistaAtual.equipa, vistaAtual.nome)">Atualizar «{{ vistaAtual.nome }}» com o que está à vista</button>
            <button v-if="!vistaAtual.equipa" @click="porOmissao">Abrir sempre com esta vista</button>
            <button class="perigo" @click="apagarVista">Apagar a vista</button></template>
          <button v-else-if="vs.padrao" @click="porOmissao">Deixar de abrir com «{{ vs.padrao }}»</button>
        </div></span>
    </div>
    <div class="filtros">
      <input class="filtro" style="border-style:solid;min-width:220px" v-model="q" :placeholder="'Procurar em ' + meta.rotulo.toLowerCase() + '…'">
      <span v-for="(f,i) in filtros" :key="i" class="filtro on">{{ (cdef(f[0])||{}).rotulo || f[0] }} {{ rotuloOp(f) }} {{ rotuloValor(f) }} <span style="cursor:pointer" @click="tirarFiltro(i)">✕</span></span>
      <span class="filtro-novo" @click.stop><button class="filtro" @click="novoF ? novoF=null : abrirFiltro()">+ Filtro</button>
        <div v-if="novoF" class="cartao pop-filtro">
          <select v-model="novoF.campo" @change="novoF.op=(opsDe(novoF.campo)||[[]])[0][0]; novoF.valor=''"><option value="" disabled>Campo…</option>
            <optgroup label="Mais usados"><option v-for="c in (def&&def.campos||[]).filter(x=>x.filtro)" :key="'f'+c.campo" :value="c.campo">{{ c.rotulo }}</option></optgroup>
            <optgroup label="Todos os campos"><option v-for="c in (def&&def.campos||[])" :key="c.campo" :value="c.campo">{{ c.rotulo }}</option></optgroup></select>
          <select v-if="novoF.campo" v-model="novoF.op"><option v-for="o in opsDe(novoF.campo)" :key="o[0]" :value="o[0]">{{ o[1] }}</option></select>
          <template v-if="novoF.campo && novoF.op">
            <select v-if="novoF.op==='is'" v-model="novoF.valor"><option value="set">preenchido</option><option value="not set">vazio</option></select>
            <select v-else-if="novoF.op==='timespan'" v-model="novoF.valor"><option v-for="p in PERIODOS_ERP" :key="p[0]" :value="p[0]">{{ p[1] }}</option></select>
            <select v-else-if="cdef(novoF.campo) && cdef(novoF.campo).opcoes_v" v-model="novoF.valor"><option v-for="o in cdef(novoF.campo).opcoes_v" :key="o.v" :value="o.v">{{ o.r }}</option></select>
            <select v-else-if="cdef(novoF.campo) && cdef(novoF.campo).opcoes && !['in','not in'].includes(novoF.op)" v-model="novoF.valor"><option v-for="o in cdef(novoF.campo).opcoes" :key="o" :value="o">{{ o }}</option></select>
            <select v-else-if="cdef(novoF.campo) && cdef(novoF.campo).tipo==='Check'" v-model="novoF.valor"><option value="1">Sim</option><option value="0">Não</option></select>
            <template v-else><input v-model="novoF.valor" :type="tipoOp(cdef(novoF.campo))==='data' ? 'date' : tipoOp(cdef(novoF.campo))==='numero' ? 'number' : 'text'" :placeholder="['in','not in'].includes(novoF.op) ? 'separe por vírgulas' : ''">
              <input v-if="novoF.op==='between'" v-model="novoF.valor2" type="date"></template>
          </template>
          <button class="btn sm prim" @click="juntarFiltro" :disabled="!novoF.campo || !novoF.op">Aplicar</button>
        </div></span>
      <button v-if="filtros.length || q" class="filtro" @click="limpar">Limpar</button>
      <span class="filtro-novo" style="margin-left:auto" @click.stop><button class="filtro" @click="verCols=!verCols">Colunas ▾</button>
        <div v-if="verCols" class="cartao pop-filtro cols-erp" style="right:0;left:auto;min-width:260px;max-height:360px;overflow:auto">
          <div v-for="c in colunas" :key="'a'+c" class="chk-col col-ord"><input type="checkbox" checked @change="alternarCol(c)"> <span class="cresce">{{ campo(c).label }}</span><button @click="moverCol(c,-1)" title="Para a esquerda">↑</button><button @click="moverCol(c,1)" title="Para a direita">↓</button></div>
          <div class="sub" style="font-size:11px;margin:6px 0 2px">Juntar</div>
          <label v-for="c in (def&&def.campos||[]).filter(x=>!colunas.includes(x.campo))" :key="c.campo" class="chk-col"><input type="checkbox" @change="alternarCol(c.campo)"> {{ c.rotulo }}</label>
          <button class="btn sm" style="margin-top:6px" @click="colunasPadrao">Repor as colunas da lista</button>
        </div></span>
    </div>
    <div v-if="sel.length" class="selec" style="margin:0 24px;border-radius:10px 10px 0 0;flex-wrap:wrap">
      {{ sel.length }} selecionado(s) ·
      <select class="btn sm" v-model="massa.acao" @change="massa.valor=''; massa.campo=''"><option value="">Ação…</option><option v-for="o in opsMassa" :key="o[0]" :value="o[0]">{{ o[1] }}</option></select>
      <template v-if="massa.acao==='editar'"><select class="btn sm" v-model="massa.campo"><option value="">Campo…</option><option v-for="c in camposEditaveis" :key="c.campo" :value="c.campo">{{ c.rotulo }}</option></select>
        <select v-if="massa.campo && cdef(massa.campo) && cdef(massa.campo).opcoes" class="btn sm" v-model="massa.valor"><option v-for="o in cdef(massa.campo).opcoes" :key="o" :value="o">{{ o }}</option></select>
        <input v-else-if="massa.campo" class="btn sm" v-model="massa.valor" :type="tipoOp(cdef(massa.campo))==='data' ? 'date' : 'text'" placeholder="Novo valor"></template>
      <select v-if="massa.acao==='atribuir'" class="btn sm" v-model="massa.valor"><option value="">Pessoa…</option><option v-for="p in pessoasL" :key="p.email" :value="p.email">{{ p.nome }}</option></select>
      <input v-if="massa.acao==='etiqueta'" class="btn sm" v-model="massa.valor" placeholder="Etiqueta">
      <button class="btn sm prim" @click="aplicarMassa" :disabled="!massa.acao || (['atribuir','etiqueta'].includes(massa.acao) && !massa.valor) || (massa.acao==='editar' && !massa.campo)">Aplicar</button>
      <button v-if="def && def.pode.imprimir" class="btn sm" @click="pdfLote">PDF</button>
      <button v-if="def && def.pode.exportar" class="btn sm" @click="exportar(true)">Exportar seleção</button>
    </div>
    <ErpKanban v-if="modo==='kanban' && campoK" :doctype="doctype" :campo="campoK" :def="def" :linhas="linhas" :titulo="titulo" @mudou="carregar()"/>
    <div v-else class="tabela-wrap cartoes-movel" :style="sel.length?{borderTopLeftRadius:0,borderTopRightRadius:0}:{}"><table>
      <thead><tr><th style="width:34px"><input type="checkbox" v-model="todos"></th><th @click="ordenar(titulo||'name')" style="cursor:pointer">{{ titulo ? campo(titulo).label : 'Nome' }}</th>
        <th v-for="c in colunasVis" :key="c" @click="ordenar(c)" style="cursor:pointer">{{ campo(c).label }}<span v-if="ordem.startsWith(c+' ')">{{ ordem.endsWith('asc') ? ' ↑' : ' ↓' }}</span></th>
        <th v-if="meta.submetivel">Estado</th></tr></thead>
      <tbody>
        <tr v-for="l in linhas" :key="l.name" @click="abrir(l.name)">
          <td @click.stop class="cel-sel"><input type="checkbox" :value="l.name" v-model="sel"></td>
          <td class="cel-tit"><div class="pessoa"><span class="av" :style="{background:cor(l.name)}">{{ ini(l[titulo]||l.name) }}</span><a :href="irErp(doctype,l.name)" @click.stop>{{ tr(doctype, l[titulo] || l.name) }}</a></div><small v-if="titulo && l[titulo] && l[titulo]!==l.name" style="color:var(--ink-3)">{{ tr(doctype, l.name) }}</small></td>
          <td v-for="c in colunasVis" :key="c">{{ textoValor(campo(c), l[c]) }}</td>
          <td v-if="meta.submetivel"><span class="etq" :class="COR_STATUS[l.status] || ESTADO_DOC[l.docstatus||0][1]">{{ l.status ? statusPt(l.status) : ESTADO_DOC[l.docstatus||0][0] }}</span></td>
        </tr>
      </tbody></table>
      <div v-if="!linhas.length && !a" class="vazio">{{ filtros.length || q ? 'Nada com estes filtros.' : 'Sem registos.' }}</div>
      <div v-if="a && !linhas.length" class="carregar">A carregar…</div>
    </div>
    <div v-if="mais" style="text-align:center;margin-bottom:24px"><button class="btn" @click="maisLinhas">Carregar mais ({{ linhas.length }} de {{ total }})</button></div>
    </template>
  </div><div v-else class="vazio">A carregar…</div>
    <div v-if="orig" class="modal-fundo" @click.self="orig=null"><div class="modal" style="max-width:620px"><header><b>{{ rotDevol }} — escolher {{ rotOrig.toLowerCase() }}</b><button class="btn sm" @click="orig=null">Fechar</button></header>
      <div class="reg-form"><input v-model="orig.q" placeholder="Procurar pelo número ou pelo nome…" @input="procurarOrig" autofocus>
        <div v-if="orig.lista===null" class="sub">A procurar…</div>
        <div v-else-if="!orig.lista.length" class="sub">Nenhum documento submetido{{ orig.q ? ' com «' + orig.q + '»' : '' }}.</div>
        <div v-else class="cartao" style="padding:0;max-height:55vh;overflow:auto"><button v-for="o in orig.lista" :key="o.name" type="button" class="linha" style="width:100%;text-align:left;background:none;border:0;border-bottom:1px solid var(--line);cursor:pointer" @click="devolver(o.name)">
          <div class="cresce"><b>{{ o.name }}</b><small>{{ o.parte }} · {{ o.data }}</small></div><b>{{ new Intl.NumberFormat('pt-PT',{style:'currency',currency:'EUR'}).format(o.total||0) }}</b></button></div>
        <p class="sub" style="margin:0;font-size:12px">O ERPNext prepara o documento com as linhas do original em negativo; acerta as quantidades e grava.</p></div></div></div>
`,
};

const ErpLigacao = {
  props: ["modelValue", "alvo", "ro", "filtros"],
  emits: ["update:modelValue"],
  setup(props, { emit }) {
    const txt = ref(props.modelValue || ""); const ops = ref([]); const aberto = ref(false); const campo = ref(null); const pos = ref({}); let tq;
    watch(() => props.modelValue, (v) => { if (v !== txt.value) txt.value = v || ""; });
    // a lista flutua por cima da página (dentro de uma tabela com deslocamento ficava cortada)
    // N9 (25-11): a lista nunca sai pela margem (no telemóvel saía pela direita) nem por baixo do ecrã
    const posicionar = () => { const r = campo.value?.getBoundingClientRect(); if (!r) return; const w = Math.min(Math.max(r.width, 260), window.innerWidth - 16);
      const esq = Math.max(8, Math.min(r.left, window.innerWidth - w - 8)); const baixo = window.innerHeight - r.bottom < 240 && r.top > 240;
      pos.value = { position: "fixed", left: esq + "px", width: w + "px", right: "auto", ...(baixo ? { top: "auto", bottom: (window.innerHeight - r.top + 4) + "px" } : { top: (r.bottom + 4) + "px" }) }; };
    const procurar = () => { clearTimeout(tq); tq = setTimeout(async () => { if (!props.alvo) return; ops.value = await api("erp.procurar", props.filtros ? { doctype: props.alvo, txt: txt.value, filtros: props.filtros } : { doctype: props.alvo, txt: txt.value }); posicionar(); aberto.value = true; }, 200); };
    const escolher = (o) => { txt.value = o.v; emit("update:modelValue", o.v); aberto.value = false; };
    const sair = () => setTimeout(() => { aberto.value = false; if (txt.value !== (props.modelValue || "")) emit("update:modelValue", txt.value || null); }, 150);
    const foco = ref(false);
    return { txt, ops, aberto, procurar, escolher, sair, irErp, campo, pos, foco, tr };
  },
  template: `<div class="erp-ligacao">
    <input ref="campo" :value="foco ? txt : tr(alvo, txt)" :disabled="ro" @focus="foco=true; procurar()" @input="txt=$event.target.value; procurar()" @blur="foco=false; sair()" autocomplete="off">
    <a v-if="modelValue && alvo" class="ir" :href="irErp(alvo, modelValue)" title="Abrir">↗</a>
    <div v-if="aberto && ops.length" class="cartao erp-ops" :style="pos"><div v-for="o in ops" :key="o.v" class="linha" @mousedown.prevent="escolher(o)"><div class="cresce">{{ o.r }}<small v-if="o.d || o.r!==o.v">{{ o.r!==o.v ? o.v : '' }} {{ o.d }}</small></div></div></div>
  </div>`,
};

const ErpCampo = {
  components: { ErpLigacao },
  props: ["c", "doc", "ro", "compacto", "botao", "doctype"],
  setup(props) {
    const v = computed({ get: () => props.doc[props.c.fieldname], set: (x) => { props.doc[props.c.fieldname] = x; } });
    const dt = computed({ get: () => (props.doc[props.c.fieldname] || "").replace(" ", "T").slice(0, 16), set: (x) => { props.doc[props.c.fieldname] = x ? x.replace("T", " ") + ":00" : null; } });
    const num = computed({ get: () => props.doc[props.c.fieldname], set: (x) => { props.doc[props.c.fieldname] = x === "" ? null : Number(x); } });
    const editor = ref(null);
    onMounted(() => { if (editor.value) editor.value.innerHTML = props.doc[props.c.fieldname] || ""; });
    const html = (e) => { props.doc[props.c.fieldname] = e.target.innerHTML; };
    // Select: opções escondidas pela interface só aparecem se já estiverem escolhidas
    const opcoes = computed(() => (props.c.opcoes || []).filter((o) => !o.oculta || o.v === v.value));
    // Anexo: carregar, trocar e tirar (como no ecrã antigo)
    const aCarregar = ref(false);
    const anexar = async (e) => {
      const f = e.target.files?.[0]; e.target.value = ""; if (!f) return;
      aCarregar.value = true;
      try { v.value = await carregarFicheiro(f, { doctype: props.doctype || props.doc.doctype, docname: props.doc.name, fieldname: props.c.fieldname, privado: props.c.fieldtype !== "Attach Image" }); }
      catch (err) { toast(err.message); } finally { aCarregar.value = false; }
    };
    // Classificação: o Frappe guarda a fracção (0–1) de N estrelas (options, 5 por omissão)
    const estrelas = computed(() => Number(props.c.options) || 5);
    const nota = computed(() => Math.round((Number(v.value) || 0) * estrelas.value));
    const classificar = (n) => { if (!props.ro) v.value = n === nota.value ? 0 : n / estrelas.value; };
    // Duração: segundos no Frappe; mostra-se em dias/horas/minutos/segundos
    const partes = (t) => { t = Math.max(0, Math.round(Number(t) || 0)); return { d: Math.floor(t / 86400), h: Math.floor(t % 86400 / 3600), m: Math.floor(t % 3600 / 60), s: t % 60 }; };
    const dur = computed(() => partes(v.value));
    const mudarDur = (k, x) => { const p = { ...dur.value, [k]: Math.max(0, Number(x) || 0) }; v.value = p.d * 86400 + p.h * 3600 + p.m * 60 + p.s; };
    // Autocompletar: sugestões das opções do campo
    const sugestoes = computed(() => String(props.c.options || "").split("\n").filter(Boolean));
    const idLista = "ac-" + Math.random().toString(36).slice(2);
    // Assinatura: desenhada num quadro, gravada como imagem (data URL), como o ecrã antigo
    const quadro = ref(null); let aDesenhar = false;
    const ponto = (e) => { const c = quadro.value; const r = c.getBoundingClientRect(); const t = e.touches?.[0] || e; return [(t.clientX - r.left) * c.width / r.width, (t.clientY - r.top) * c.height / r.height]; };
    const comecar = (e) => { if (props.ro) return; aDesenhar = true; const g = quadro.value.getContext("2d"); g.lineWidth = 2; g.lineCap = "round"; g.strokeStyle = "#161a1d"; g.beginPath(); g.moveTo(...ponto(e)); };
    const tracar = (e) => { if (!aDesenhar) return; e.preventDefault(); const g = quadro.value.getContext("2d"); g.lineTo(...ponto(e)); g.stroke(); };
    const acabar = () => { if (!aDesenhar) return; aDesenhar = false; v.value = quadro.value.toDataURL("image/png"); };
    const limparAss = () => { v.value = null; if (quadro.value) quadro.value.getContext("2d").clearRect(0, 0, quadro.value.width, quadro.value.height); };
    return { v, dt, num, editor, html, textoValor, opcoes, aCarregar, anexar, estrelas, nota, classificar, dur, mudarDur, sugestoes, idLista, quadro, comecar, tracar, acabar, limparAss, MONO };
  },
  template: `
    <template v-if="c.fieldtype==='Check'"><label class="erp-chk"><input type="checkbox" :checked="!!v" :disabled="ro" @change="v = $event.target.checked ? 1 : 0"> <span v-if="!compacto">{{ c.label }}</span></label></template>
    <select v-else-if="c.fieldtype==='Select'" v-model="v" :disabled="ro"><option v-for="o in opcoes" :key="o.v" :value="o.v">{{ o.r }}</option></select>
    <ErpLigacao v-else-if="c.fieldtype==='Link'" v-model="v" :alvo="c.options" :ro="ro"/>
    <ErpLigacao v-else-if="c.fieldtype==='Dynamic Link'" v-model="v" :alvo="doc[c.options]" :ro="ro"/>
    <input v-else-if="['Int','Float','Currency','Percent'].includes(c.fieldtype)" type="number" :step="c.fieldtype==='Int'?1:'any'" v-model="num" :disabled="ro">
    <input v-else-if="c.fieldtype==='Date'" type="date" v-model="v" :disabled="ro">
    <input v-else-if="c.fieldtype==='Datetime'" type="datetime-local" v-model="dt" :disabled="ro">
    <input v-else-if="c.fieldtype==='Time'" type="time" step="1" v-model="v" :disabled="ro">
    <input v-else-if="c.fieldtype==='Password'" type="password" v-model="v" :disabled="ro" autocomplete="new-password">
    <input v-else-if="c.fieldtype==='Color'" type="color" v-model="v" :disabled="ro">
    <div v-else-if="c.fieldtype==='Text Editor'" ref="editor" class="erp-editor" :contenteditable="!ro" @input="html"></div>
    <textarea v-else-if="MONO.includes(c.fieldtype) && !compacto" v-model="v" :disabled="ro" rows="6" class="erp-mono" spellcheck="false"></textarea>
    <textarea v-else-if="['Small Text','Text','Long Text'].includes(c.fieldtype) && !compacto" v-model="v" :disabled="ro" rows="3"></textarea>
    <div v-else-if="['Attach','Attach Image'].includes(c.fieldtype)" class="erp-anexo">
      <img v-if="c.fieldtype==='Attach Image' && v" :src="v" class="erp-img" alt="">
      <a v-if="v" :href="v" target="_blank">{{ String(v).split('/').pop() }}</a><span v-else class="sub">{{ aCarregar ? 'A carregar…' : 'sem ficheiro' }}</span>
      <span v-if="!ro" class="erp-anexo-acc"><label class="btn sm">{{ v ? 'Trocar' : 'Carregar' }}<input type="file" hidden :accept="c.fieldtype==='Attach Image' ? 'image/*' : null" @change="anexar"></label><button v-if="v" class="btn sm" type="button" @click="v=null">Tirar</button></span>
    </div>
    <div v-else-if="c.fieldtype==='Read Only'" class="erp-ro">{{ v }}</div>
    <div v-else-if="c.fieldtype==='HTML'" class="erp-html" v-html="c.options"></div>
    <h4 v-else-if="c.fieldtype==='Heading'" class="erp-titulo">{{ c.label }}</h4>
    <button v-else-if="c.fieldtype==='Button'" class="btn sm" type="button" @click="botao && botao(c)">{{ c.label }}</button>
    <img v-else-if="c.fieldtype==='Image'" :src="doc[c.options]" class="erp-img" alt="">
    <div v-else-if="c.fieldtype==='Rating'" class="erp-estrelas"><button v-for="n in estrelas" :key="n" type="button" :class="{on: n<=nota}" :disabled="ro" @click="classificar(n)">★</button></div>
    <div v-else-if="c.fieldtype==='Duration'" class="erp-duracao">
      <label v-for="k in ['d','h','m','s']" :key="k"><input type="number" min="0" :value="dur[k]" :disabled="ro" @change="mudarDur(k, $event.target.value)"><span>{{ {d:'dias',h:'h',m:'min',s:'s'}[k] }}</span></label>
    </div>
    <div v-else-if="c.fieldtype==='Signature'" class="erp-assinatura">
      <img v-if="v && (ro || !quadro)" :src="v" alt="Assinatura">
      <template v-if="!ro"><canvas ref="quadro" width="420" height="140" style="max-width:100%;touch-action:none" @mousedown="comecar" @mousemove="tracar" @mouseup="acabar" @mouseleave="acabar" @touchstart="comecar" @touchmove="tracar" @touchend="acabar"></canvas>
        <div><img v-if="v" :src="v" alt="" class="erp-ass-atual"><button class="btn sm" type="button" @click="limparAss">Limpar</button></div></template>
    </div>
    <template v-else-if="c.fieldtype==='Autocomplete'"><input v-model="v" :disabled="ro" :list="idLista"><datalist :id="idLista"><option v-for="o in sugestoes" :key="o" :value="o"/></datalist></template>
    <input v-else v-model="v" :disabled="ro" :type="c.options==='Email'?'email':c.options==='Phone'?'tel':'text'">`,
};

// Tabela de escolha múltipla (Table MultiSelect): cada linha da tabela-filha guarda uma ligação; mostra-se como etiquetas.
const ErpMulti = {
  components: { ErpLigacao },
  props: ["c", "doc", "filha", "ro"],
  setup(props) {
    const linhas = computed(() => props.doc[props.c.fieldname] || (props.doc[props.c.fieldname] = []));
    const campoLig = computed(() => (props.filha?.campos || []).find((x) => x.fieldtype === "Link"));
    const novo = ref("");
    watch(novo, (x) => {
      if (!x || !campoLig.value) return;
      if (!linhas.value.some((l) => l[campoLig.value.fieldname] === x)) linhas.value.push({ doctype: props.c.options, [campoLig.value.fieldname]: x });
      nextTick(() => { novo.value = ""; });
    });
    const tirar = (i) => linhas.value.splice(i, 1);
    return { linhas, campoLig, novo, tirar, tr };
  },
  template: `<div class="erp-multi">
    <span v-for="(l,i) in linhas" :key="i" class="etq">{{ campoLig ? tr(campoLig.options, l[campoLig.fieldname]) : '' }}<button v-if="!ro" type="button" @click="tirar(i)" title="Tirar">×</button></span>
    <ErpLigacao v-if="!ro && campoLig" v-model="novo" :alvo="campoLig.options"/>
  </div>`,
};

// 27-11-2026 (Vítor: «se eu escrever 205, o 5 não entra»): a resposta do recálculo do ERPNext chegava depois de a pessoa
// ter escrito mais algarismos e repunha o valor que tinha sido enviado. Agora junta-se a resposta sem tocar em nada que
// tenha mudado desde o envio (cabeçalho e linhas, emparelhadas pelo nome); e só a resposta ao último envio conta.
const _igualR = (a, b) => JSON.stringify(a ?? null) === JSON.stringify(b ?? null);
const juntarRecalculo = (alvo, resposta, enviado) => {
  for (const [k, v] of Object.entries(resposta || {})) {
    const atual = alvo[k], antes = enviado[k];
    if (Array.isArray(v) && Array.isArray(atual) && Array.isArray(antes)) {
      // linhas acrescentadas ou apagadas entretanto: fica o que está; o recálculo seguinte trata delas
      if (atual.length !== antes.length || atual.some((l, i) => (l && l.name) !== (antes[i] && antes[i].name))) continue;
      const porNome = (lista) => Object.fromEntries(lista.filter((l) => l && l.name).map((l) => [l.name, l]));
      const A = porNome(atual), E = porNome(antes);
      alvo[k] = v.map((lr) => { const la = lr && A[lr.name], le = lr && E[lr.name]; if (!la || !le) return lr;
        const out = { ...lr }; for (const kk of Object.keys(la)) if (!_igualR(la[kk], le[kk])) out[kk] = la[kk]; return out; });
    } else if (_igualR(atual, antes)) alvo[k] = v;
  }
};
const ErpTabela = {
  components: { ErpCampo },
  props: ["c", "doc", "filha", "ro"],
  setup(props) {
    const linhas = computed(() => props.doc[props.c.fieldname] || (props.doc[props.c.fieldname] = []));
    const cols = computed(() => {
      const cs = (props.filha?.campos || []).filter((x) => !ESTRUTURA.includes(x.fieldtype) && !x.hidden && !FILHAS.includes(x.fieldtype) && !SEM_VALOR.includes(x.fieldtype));
      const lv = cs.filter((x) => x.in_list_view); return (lv.length ? lv : cs).slice(0, 6);
    });
    // 25-11-2026: todos os campos da linha (o «editar linha» do ecrã antigo) — as colunas só mostram até 6
    const todos = computed(() => (props.filha?.campos || []).filter((x) => !ESTRUTURA.includes(x.fieldtype) && !x.hidden));
    const visL = (x, l) => avaliar(x.depends_on, Object.assign({}, l, { parent: props.doc })) && (x.fieldtype !== "HTML" || x.options);
    const aberta = ref(null);
    let n = 0;
    const juntar = () => {
      const l = { name: "novo-" + Date.now() + "-" + (n++), doctype: props.c.options };
      if ((props.filha?.campos || []).some((x) => x.fieldname === "qty")) l.qty = 1;   // como o ecrã do ERPNext
      linhas.value.push(l);
    };
    const tirar = (i) => { linhas.value.splice(i, 1); };
    // lote 5 (25-11): o que a grelha do desk faz — seleccionar, inserir acima/abaixo, duplicar, mover, apagar várias, CSV
    const sel = ref([]); const menuL = ref(null); const csvIn = ref(null);
    const nova = () => { const l = { name: "novo-" + Date.now() + "-" + (n++), doctype: props.c.options }; if ((props.filha?.campos || []).some((x) => x.fieldname === "qty")) l.qty = 1; return l; };
    const inserir = (i, depois) => { linhas.value.splice(depois ? i + 1 : i, 0, nova()); menuL.value = null; };
    const duplicarL = (i) => { const c = JSON.parse(JSON.stringify(linhas.value[i])); c.name = "novo-" + Date.now() + "-" + (n++); delete c.idx; linhas.value.splice(i + 1, 0, c); menuL.value = null; };
    const mover = (i, d) => { const j = i + d; if (j < 0 || j >= linhas.value.length) return; const x = linhas.value.splice(i, 1)[0]; linhas.value.splice(j, 0, x); menuL.value = null; };
    const tirarSel = () => { if (!confirm(`Tirar ${sel.value.length} linha(s)?`)) return; const k = new Set(sel.value); const fic = linhas.value.filter((l, i) => !k.has(i)); linhas.value.splice(0, linhas.value.length, ...fic); sel.value = []; };
    const csvCampos = computed(() => (props.filha?.campos || []).filter((x) => !ESTRUTURA.includes(x.fieldtype) && !x.hidden && !FILHAS.includes(x.fieldtype) && !SEM_VALOR.includes(x.fieldtype) && !x.read_only));
    const descarregar = () => { const cs = csvCampos.value; const esc = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
      const t = [cs.map((x) => esc(x.label)).join(";"), cs.map((x) => esc(x.fieldname)).join(";")].concat(linhas.value.map((l) => cs.map((x) => esc(l[x.fieldname])).join(";"))).join("\n");
      const b = new Blob(["\ufeff" + t], { type: "text/csv;charset=utf-8" }); const u = URL.createObjectURL(b); const el = document.createElement("a"); el.href = u; el.download = (props.c.label || "linhas") + ".csv"; el.click(); URL.revokeObjectURL(u); };
    const carregarCsv = async (ev) => { const fi = ev.target.files?.[0]; if (!fi) return; const txt = (await fi.text()).replace(/^\ufeff/, "");
      const lerLinha = (ln) => { const out = []; let cur = "", q = false; for (let k = 0; k < ln.length; k++) { const ch = ln[k];
          if (q) { if (ch === '"' && ln[k + 1] === '"') { cur += '"'; k++; } else if (ch === '"') q = false; else cur += ch; }
          else if (ch === '"') q = true; else if (ch === ";" || ch === ",") { out.push(cur); cur = ""; } else cur += ch; } out.push(cur); return out; };
      const ls = txt.split(/\r?\n/).filter((x) => x.trim()); if (ls.length < 2) { toast("O ficheiro não tem linhas"); return; }
      const cab = lerLinha(ls[1]).map((x) => x.trim()); const nomes = csvCampos.value.map((x) => x.fieldname);
      const usaNomes = cab.some((x) => nomes.includes(x)); const inicio = usaNomes ? 2 : 1;
      const chaves = (usaNomes ? cab : lerLinha(ls[0]).map((x) => (csvCampos.value.find((c) => c.label === x.trim()) || {}).fieldname));
      let k = 0; for (const ln of ls.slice(inicio)) { const v = lerLinha(ln); const l = nova(); chaves.forEach((c, j) => { if (c && v[j] !== undefined && v[j] !== "") l[c] = v[j]; }); linhas.value.push(l); k++; }
      ev.target.value = ""; toast(k + " linha(s) carregada(s)"); };
    return { linhas, cols, juntar, tirar, todos, visL, aberta, sel, menuL, inserir, duplicarL, mover, tirarSel, descarregar, carregarCsv, csvIn };
  },
  template: `<div class="erp-tabela">
    <div class="tabela-wrap" style="margin:0"><table>
      <thead><tr><th style="width:44px"><span v-if="ro">#</span><input v-else type="checkbox" :checked="linhas.length && sel.length===linhas.length" @change="sel = $event.target.checked ? linhas.map((_,k)=>k) : []"></th><th v-for="x in cols" :key="x.fieldname">{{ x.label }}<span v-if="x.reqd" class="obrig">*</span></th><th style="width:34px"></th><th v-if="!ro" style="width:34px"></th></tr></thead>
      <tbody><template v-for="(l,i) in linhas" :key="l.name||i"><tr style="cursor:default">
        <td class="sub"><label v-if="!ro" class="linha-n"><input type="checkbox" :value="i" v-model="sel">{{ i+1 }}</label><template v-else>{{ i+1 }}</template></td>
        <td v-for="x in cols" :key="x.fieldname"><ErpCampo :c="x" :doc="l" :ro="ro || x.read_only" compacto="1"/></td>
        <td><button class="icone-btn" :title="aberta===i ? 'Fechar a linha' : 'Todos os campos da linha'" @click="aberta = aberta===i ? null : i">{{ aberta===i ? '▴' : '⋯' }}</button></td>
        <td v-if="!ro" class="reg-menu" @click.stop><button class="icone-btn" title="Mais ações da linha" @click="menuL = menuL===i ? null : i">⋮</button>
          <div v-if="menuL===i" class="cartao reg-menu-lista" @click="menuL=null"><button @click="inserir(i,false)">Inserir acima</button><button @click="inserir(i,true)">Inserir abaixo</button><button @click="duplicarL(i)">Duplicar</button>
            <button v-if="i>0" @click="mover(i,-1)">Mover para cima</button><button v-if="i<linhas.length-1" @click="mover(i,1)">Mover para baixo</button><button class="perigo" @click="tirar(i)">Tirar a linha</button></div></td>
      </tr>
      <tr v-if="aberta===i" class="erp-linha-aberta"><td :colspan="cols.length + (ro ? 2 : 3)"><div class="erp-linha-campos">
        <template v-for="x in todos" :key="x.fieldname"><div v-if="visL(x, l)" class="erp-campo">
          <label v-if="!['Check','Button','Heading','HTML'].includes(x.fieldtype)">{{ x.label }}<span v-if="x.reqd" class="obrig">*</span></label>
          <ErpCampo :c="x" :doc="l" :ro="ro || x.read_only" :doctype="c.options"/>
          <small v-if="x.descricao" class="sub">{{ x.descricao }}</small></div></template>
      </div></td></tr></template></tbody></table>
      <div v-if="!linhas.length" class="vazio" style="padding:12px">Sem linhas.</div>
    </div>
    <div class="erp-tab-acoes"><button v-if="!ro" class="btn sm" @click="juntar">+ Linha</button>
      <button v-if="!ro && sel.length" class="btn sm" @click="tirarSel">Tirar {{ sel.length }} linha(s)</button>
      <span style="margin-left:auto;display:flex;gap:6px"><button v-if="linhas.length" class="btn sm" @click="descarregar" title="Descarregar as linhas em CSV">⤓ CSV</button>
        <button v-if="!ro" class="btn sm" @click="csvIn.click()" title="Juntar linhas a partir de um CSV (primeira linha: títulos)">⤒ Carregar CSV</button><input ref="csvIn" type="file" accept=".csv" style="display:none" @change="carregarCsv"></span></div>
  </div>`,
};

// ── Proposta (Orçamento) no layout de 24-11-2026: marca, produtos com imagem e características, versões ──
const apiP = (m, a = {}, post = false) => api("orbit.propostas." + m, a, post);
const caractPares = (t) => (t || "").split("\n").map((l) => l.trim()).filter((l) => l.includes(":")).map((l) => { const i = l.indexOf(":"); return { k: l.slice(0, i).trim(), v: l.slice(i + 1).trim() }; }).filter((x) => x.v);
// ── Texto rico (24-11-2026: «Introdução» da proposta — parágrafos, negrito, centrado…) ──────────────────────────────
// Um editor leve sobre contenteditable: grava HTML limpo (só p, br, b/strong, i/em, u, ul/ol/li e o alinhamento
// em linha), que o PDF da proposta imprime tal como está. O que vinha do editor do Frappe (Quill, `div.ql-editor`)
// abre sem o invólucro e com o alinhamento das classes `ql-align-*` passado a estilo.
const RICO_TAGS = new Set(["P", "BR", "B", "STRONG", "I", "EM", "U", "UL", "OL", "LI", "DIV", "SPAN"]);
function ricoLimpo(html) {
  const caixa = document.createElement("div");
  caixa.innerHTML = String(html || "");
  const qe = caixa.querySelector(":scope > .ql-editor"); if (qe) caixa.innerHTML = qe.innerHTML;
  const passar = (no) => {
    [...no.childNodes].forEach((f) => {
      if (f.nodeType === 3) return;
      if (f.nodeType !== 1 || ["SCRIPT", "STYLE", "TITLE", "HEAD", "META", "LINK"].includes(f.tagName)) { f.remove(); return; }
      passar(f);
      if (!RICO_TAGS.has(f.tagName)) { f.replaceWith(...f.childNodes); return; }
      const al = (f.style && f.style.textAlign) || ([...(f.classList || [])].find((c) => c.startsWith("ql-align-")) || "").replace("ql-align-", "");
      [...f.attributes].forEach((a) => f.removeAttribute(a.name));
      if (["center", "right", "justify"].includes(al)) f.style.textAlign = al;
      if (f.tagName === "SPAN" && !f.getAttribute("style")) f.replaceWith(...f.childNodes);
    });
  };
  passar(caixa);
  return caixa.innerHTML.replace(/<p><br><\/p>$/, "").trim();
}
const EditorRico = {
  props: ["modelValue", "ro", "placeholder"], emits: ["update:modelValue"],
  template: `<div class="rico" :class="{ro}">
    <div class="rico-barra" v-if="!ro" @mousedown.prevent>
      <button type="button" title="Negrito" @click="cmd('bold')"><b>N</b></button>
      <button type="button" title="Itálico" @click="cmd('italic')"><i>I</i></button>
      <button type="button" title="Sublinhado" @click="cmd('underline')"><u>S</u></button>
      <span class="rico-sep"></span>
      <button type="button" title="Alinhar à esquerda" @click="cmd('justifyLeft')">⯇≡</button>
      <button type="button" title="Centrar" @click="cmd('justifyCenter')">≡</button>
      <button type="button" title="Alinhar à direita" @click="cmd('justifyRight')">≡⯈</button>
      <span class="rico-sep"></span>
      <button type="button" title="Lista com marcas" @click="cmd('insertUnorderedList')">•</button>
      <button type="button" title="Lista numerada" @click="cmd('insertOrderedList')">1.</button>
      <span class="rico-sep"></span>
      <button type="button" title="Tirar a formatação" @click="cmd('removeFormat')">⌫</button>
    </div>
    <div ref="caixa" class="rico-texto" :contenteditable="!ro" :data-vazio="placeholder" @input="mudou" @blur="mudou" @paste="colar"></div>
  </div>`,
  mounted() { this.$refs.caixa.innerHTML = ricoLimpo(this.modelValue); this.vazio(); },
  watch: { modelValue(v) { if (document.activeElement !== this.$refs.caixa && ricoLimpo(v) !== this.$refs.caixa.innerHTML) { this.$refs.caixa.innerHTML = ricoLimpo(v); this.vazio(); } } },
  methods: {
    cmd(c) { this.$refs.caixa.focus(); try { document.execCommand("defaultParagraphSeparator", false, "p"); } catch (e) {} document.execCommand(c, false, null); this.mudou(); },
    mudou() { this.vazio(); const h = ricoLimpo(this.$refs.caixa.innerHTML); if (h !== ricoLimpo(this.modelValue)) this.$emit("update:modelValue", h); },
    vazio() { const c = this.$refs.caixa; c.classList.toggle("rico-vazio", !c.textContent.trim()); },
    colar(e) {
      e.preventDefault();
      const html = e.clipboardData.getData("text/html"), txt = e.clipboardData.getData("text/plain");
      const limpo = html ? ricoLimpo(html) : txt.split(/\r?\n\r?\n/).map((par) => "<p>" + par.replace(/[&<>]/g, (x) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[x]).replace(/\r?\n/g, "<br>") + "</p>").join("");
      document.execCommand("insertHTML", false, limpo); this.mudou();
    },
  },
};
// ── Emitir fatura e guia de transporte (25-11-2026, maquete aprovada: docs/orbit-interface/emitir/) ──────────────
// O mesmo desenho da proposta: marca que vende → empresa e série; «Importar de…» outro documento do cliente (as
// funções de conversão do ERPNext); documentos associados nos dois sentidos; pró-forma a partir da fatura em rascunho.
const apiE = (m, a = {}, post = false) => api("emitir." + m, a, post);
const ROT_DT = { "Quotation": "Proposta", "Sales Order": "Encomenda", "Delivery Note": "Guia", "Sales Invoice": "Fatura", "Payment Entry": "Recibo" };
// 27-11-2026 (Vítor: «cada ecrã alterado tem que ter TODOS os campos que existiam originalmente»): os ecrãs próprios
// (proposta, fatura/guia, recibo) mostram aqui, arrumados como na ficha completa, todos os campos do documento que o
// ecrã não desenha — tabelas, campos só de leitura com valor e condições incluídos. Nada fica só na ficha completa.
const ErpRestantes = {
  components: { ErpCampo, ErpTabela, ErpMulti },
  props: ["doctype", "doc", "ro", "excluir", "novo"],
  setup(props) {
    const meta = ref(null);
    onMounted(async () => { meta.value = await metaErp(props.doctype).catch(() => null); });
    const fora = computed(() => new Set(props.excluir || []));
    const ds = computed(() => props.doc?.docstatus || 0);
    const roCampo = (c) => !!props.ro || ds.value === 2 || c.read_only || (ds.value === 1 && !c.allow_on_submit) || (c.read_only_depends_on && avaliar(c.read_only_depends_on, props.doc));
    const obrig = (c) => c.reqd || (c.mandatory_depends_on && avaliar(c.mandatory_depends_on, props.doc));
    const visivel = (c) => {
      if (fora.value.has(c.fieldname) || c.hidden || !avaliar(c.depends_on, props.doc)) return false;
      if (c.fieldtype === "HTML") return !!c.options;
      if (c.fieldtype === "Image") return !!props.doc[c.options];
      if (["Button", "Fold"].includes(c.fieldtype)) return false;
      if (SEM_VALOR.includes(c.fieldtype) || FILHAS.includes(c.fieldtype)) return true;
      if (roCampo(c) && !props.novo && vazioV(props.doc[c.fieldname])) return false;
      return true;
    };
    const blocos = computed(() => { const m = meta.value; if (!m) return [];
      const out = []; let aba = ""; let b = null;
      const novo = (label) => { b = { aba, label: label || "", depends_on: null, campos: [] }; out.push(b); };
      for (const c of m.campos || []) {
        if (c.fieldtype === "Tab Break") { aba = c.label || ""; b = null; continue; }
        if (c.fieldtype === "Section Break") { novo(c.label); b.depends_on = c.depends_on; continue; }
        if (c.fieldtype === "Column Break") continue;
        if (!b) novo("");
        b.campos.push(c);
      }
      return out.filter((x) => avaliar(x.depends_on, props.doc) && x.campos.some(visivel)); });
    const n = computed(() => blocos.value.reduce((k, b) => k + b.campos.filter(visivel).length, 0));
    return { meta, blocos, n, visivel, roCampo, obrig };
  },
  template: `<details v-if="n" class="cartao prop-mais"><summary>Todos os outros campos <span class="sub">({{ n }})</span></summary>
    <div v-for="(b, bi) in blocos" :key="bi" class="prop-mais-bloco"><h3>{{ [b.aba, b.label].filter(Boolean).join(' › ') || 'Geral' }}</h3>
      <div class="prop-mais-grelha"><template v-for="c in b.campos" :key="c.fieldname"><div v-if="visivel(c)" class="erp-campo" :class="{'prop-mais-largo': ['Table','Table MultiSelect','Text Editor','Small Text','Text','Long Text','HTML'].includes(c.fieldtype)}">
        <label v-if="!['Check','Button','Heading','HTML'].includes(c.fieldtype)">{{ c.label }}<span v-if="obrig(c)" class="obrig">*</span></label>
        <ErpTabela v-if="c.fieldtype==='Table'" :c="c" :doc="doc" :filha="meta.filhas[c.options]" :ro="roCampo(c)"/>
        <ErpMulti v-else-if="c.fieldtype==='Table MultiSelect'" :c="c" :doc="doc" :filha="meta.filhas[c.options]" :ro="roCampo(c)"/>
        <ErpCampo v-else :c="c" :doc="doc" :ro="roCampo(c)" :doctype="doctype"/>
        <small v-if="c.descricao" class="sub">{{ c.descricao }}</small></div></template></div></div>
  </details>`,
};
// Os campos de uma linha que o ecrã próprio não desenha (proposta, fatura/guia)
const ErpLinhaCampos = {
  components: { ErpCampo },
  props: ["doctype", "linha", "parent", "ro", "excluir"],
  setup(props) {
    const meta = ref(null);
    onMounted(async () => { const m = await metaErp(props.doctype.replace(/ Item$/, "") ).catch(() => null); meta.value = m && m.filhas ? m.filhas[props.doctype] : null; });
    const fora = computed(() => new Set(props.excluir || []));
    const ctx = computed(() => Object.assign({}, props.linha, { parent: props.parent }));
    const ds = computed(() => props.parent?.docstatus || 0);
    const roCampo = (c) => !!props.ro || c.read_only || (ds.value === 1 && !c.allow_on_submit) || (c.read_only_depends_on && avaliar(c.read_only_depends_on, ctx.value));
    const campos = computed(() => ((meta.value && meta.value.campos) || []).filter((c) => !fora.value.has(c.fieldname) && !["Section Break", "Column Break", "Tab Break", "Button", "Fold", "Table", "Table MultiSelect"].includes(c.fieldtype)
      && !c.hidden && avaliar(c.depends_on, ctx.value) && !(c.fieldtype === "HTML" && !c.options) && !(roCampo(c) && vazioV(props.linha[c.fieldname]))));
    return { campos, roCampo };
  },
  template: `<div class="prop-mais-grelha prop-linha-mais"><div v-for="c in campos" :key="c.fieldname" class="erp-campo"><label v-if="!['Check','Heading','HTML'].includes(c.fieldtype)">{{ c.label }}</label><ErpCampo :c="c" :doc="linha" :ro="roCampo(c)" compacto="1"/></div>
    <div v-if="!campos.length" class="sub">Sem mais campos nesta linha.</div></div>`,
};
const ErpEmitir = {
  // ClienteProcura/ContactoProcura vêm mais abaixo no ficheiro: getters para não as ler antes de existirem
  components: { ErpLigacao, ErpRestantes, ErpLinhaCampos, get ClienteProcura() { return ClienteProcura; }, get ContactoProcura() { return ContactoProcura; } },
  props: ["dt", "name"],
  setup(props) {
    const fatura = props.dt === "Sales Invoice";
    const doc = ref(null), novo = ref(false), sujo = ref(false), a = ref(false), aviso = ref(""), podeGravar = ref(true);
    const marcas = ref([]), assoc = ref([]), imp = ref(null), novaLinha = ref("");
    const moeda = (v) => new Intl.NumberFormat("pt-PT", { style: "currency", currency: doc.value?.currency || "EUR" }).format(v || 0);
    const carregar = async () => {
      const [r, ms] = await Promise.all([api("erp.documento", { doctype: props.dt, name: props.name === "novo" ? undefined : props.name }), apiP("versoes.marcas").catch(() => [])]);
      marcas.value = ms || []; doc.value = r.doc; novo.value = r.novo; podeGravar.value = r.novo ? true : r.pode_gravar;
      if (r.novo) { let p = null; try { p = JSON.parse(sessionStorage.getItem("orbit.erp.novo") || "null"); sessionStorage.removeItem("orbit.erp.novo"); } catch (e) {}
        if (p && p.doctype === props.dt) { doc.value = p; (doc.value.items || []).forEach((l, i) => { if (!l.name) l.name = "novo-" + i; }); } }
      assoc.value = r.novo ? [] : (await apiE("associados", { doctype: props.dt, name: props.name }).catch(() => [])) || [];
      await nextTick(); sujo.value = false; ultima = assin();
    };
    onMounted(carregar);
    watch(doc, (n, o) => { if (o) sujo.value = true; }, { deep: true });
    const ro = computed(() => !podeGravar.value || (doc.value?.docstatus || 0) !== 0);
    const docstatus = computed(() => doc.value?.docstatus || 0);
    let ultima = "", tr0;
    const assin = () => { const d = doc.value; if (!d) return ""; return JSON.stringify([d.customer, d.orbit_marca, d.taxes_and_charges, (d.items || []).map((l) => [l.item_code, l.qty, l.rate, l.discount_percentage, l.warehouse])]); };
    let nRec = 0;
    const recalcular = async () => { if (ro.value) return; const n = ++nRec; const enviado = JSON.parse(JSON.stringify(doc.value));
      const r = await api("erp.recalcular", { doctype: props.dt, dados: JSON.stringify(enviado) }, true).catch(() => null);
      if (!r || n !== nRec) return; aviso.value = r.aviso || ""; if (!r.doc) return;
      const nomes = (enviado.items || []).map((l) => l.name);
      r.doc.items = (r.doc.items || []).map((l, i) => (!l.name && nomes[i] ? { ...l, name: nomes[i] } : l));
      juntarRecalculo(doc.value, r.doc, enviado); ultima = assin(); };
    watch(() => assin(), (s) => { if (s === ultima) return; ultima = s; clearTimeout(tr0); tr0 = setTimeout(recalcular, 450); });
    const acrescentar = (codigo) => { if (!codigo) return; doc.value.items = doc.value.items || [];
      doc.value.items.push({ name: "novo-" + Math.random().toString(36).slice(2, 9), doctype: props.dt + " Item", item_code: codigo, qty: 1 }); novaLinha.value = ""; };
    watch(novaLinha, (v) => { if (v) acrescentar(v); });
    const remover = (l) => { doc.value.items = doc.value.items.filter((x) => x !== l); };
    const gravar = async () => {
      if (!doc.value.customer) { toast("Escolha o cliente"); return null; }
      if (!(doc.value.items || []).length) { toast("Acrescente pelo menos uma linha"); return null; }
      a.value = true;
      try { const r = await api("erp.gravar", { doctype: props.dt, dados: JSON.stringify(doc.value) }, true); toast("Gravado");
        if (novo.value || r.doc.name !== props.name) { location.hash = irErp(props.dt, r.doc.name); return r.doc; }
        doc.value = r.doc; await nextTick(); sujo.value = false; ultima = assin(); return r.doc; } finally { a.value = false; }
    };
    const emitir = async () => {
      const txt = fatura ? "Emitir esta fatura? Depois de emitida já não se altera (corrige-se com nota de crédito)." : "Emitir esta guia? O stock sai do armazém e a guia segue para comunicação à AT.";
      if (!confirm(txt)) return;
      if (sujo.value || novo.value) { const g = await gravar(); if (!g || novo.value) return; }
      a.value = true; try { const r = await api("erp.submeter", { doctype: props.dt, name: doc.value.name }, true); doc.value = r.doc; await nextTick(); sujo.value = false; toast(fatura ? "Fatura emitida" : "Guia emitida"); await carregar(); } finally { a.value = false; }
    };
    const proforma = async () => {
      if (sujo.value || novo.value) { toast("Grave a fatura primeiro"); return; }
      a.value = true; try { const r = await apiE("emitir_proforma", { name: doc.value.name }, true);
        toast("Pró-forma " + r.numero + (r.certificado && r.certificado.erro ? " (o programa certificado falhou: " + r.certificado.erro + ")" : ""));
        window.open((r.certificado && r.certificado.pdf) || r.pdf, "_blank"); await carregar(); } finally { a.value = false; }
    };
    const converter = async (destino) => { const r = await api("erp.criar_de", { doctype: props.dt, name: doc.value.name, destino }, true);
      try { sessionStorage.setItem("orbit.erp.novo", JSON.stringify(r.doc)); } catch (e) {} location.hash = irErp(destino, "novo"); };
    const receber = () => { try { sessionStorage.setItem("orbit.recibo", JSON.stringify({ cliente: doc.value.customer, fatura: doc.value.name })); } catch (e) {} location.hash = irErp("Payment Entry", "novo"); };
    // «Importar de…»
    const abrirImportar = async () => { if (!doc.value.customer) { toast("Escolha primeiro o cliente"); return; }
      imp.value = { filtro: "", lista: null, escolhido: null, linhas: [], marcadas: {}, aImportar: false };
      imp.value.lista = await apiE("importaveis", { destino: props.dt, cliente: doc.value.customer }); };
    const tiposImp = computed(() => [...new Set((imp.value?.lista || []).map((x) => x.tipo))]);
    const listaImp = computed(() => (imp.value?.lista || []).filter((x) => !imp.value.filtro || x.tipo === imp.value.filtro));
    const escolherImp = async (x) => { imp.value.escolhido = x; imp.value.linhas = await apiE("linhas_de", { doctype: x.doctype, name: x.name, destino: props.dt });
      imp.value.marcadas = Object.fromEntries(imp.value.linhas.map((l) => [l.i, true])); };
    const importar = async () => { const x = imp.value.escolhido; if (!x) return;
      const linhas = imp.value.linhas.filter((l) => imp.value.marcadas[l.i]).map((l) => l.i);
      if (!linhas.length) { toast("Escolha pelo menos uma linha"); return; }
      imp.value.aImportar = true;
      try { const r = await apiE("importar", { destino: props.dt, fontes: JSON.stringify([{ doctype: x.doctype, name: x.name, linhas }]), dados: JSON.stringify(doc.value) }, true);
        Object.assign(doc.value, r.doc); ultima = assin(); toast(linhas.length + " linha(s) importada(s) de " + x.name); imp.value = null; }
      finally { if (imp.value) imp.value.aImportar = false; } };
    const origens = computed(() => (doc.value?.orbit_origens || "").split("\n").filter(Boolean).map((o) => { const [dt, n] = o.split("|"); return { dt, n }; }));
    const marcaSel = computed(() => marcas.value.find((m) => m.name === doc.value?.orbit_marca));
    const devol = computed(() => !!doc.value?.is_return);
    const titulo = computed(() => { const t = devol.value ? (fatura ? "Nota de crédito" : "Guia de devolução") : (fatura ? "Fatura" : "Guia de transporte");
      return novo.value ? (devol.value ? "Nova " + t.toLowerCase() : (fatura ? "Nova fatura" : "Nova guia de transporte")) : t + " " + (doc.value?.orbit_numero_certificado || doc.value?.name); });
    const pdf = computed(() => doc.value && !novo.value ? `/api/method/frappe.utils.print_format.download_pdf?doctype=${encodeURIComponent(props.dt)}&name=${encodeURIComponent(doc.value.name)}` : "");
    // números de série e lotes: pedidos na linha quando o artigo os exige
    const sl = ref({});
    const nSeries = (l) => (l.serial_no || "").split(/[\n,]+/).map((x) => x.trim()).filter(Boolean).length;
    watch(() => doc.value ? (doc.value.items || []).map((l) => l.item_code).join("|") + "@" + (doc.value.set_warehouse || "") : "", async (k) => {
      const cods = [...new Set((doc.value?.items || []).map((l) => l.item_code).filter(Boolean))]; if (!cods.length) { sl.value = {}; return; }
      sl.value = await api("clientes_venda.serie_lote", { codigos: JSON.stringify(cods), armazem: doc.value.set_warehouse || "" }).catch(() => ({})) || {}; });
    const linhaMais = ref({});
    return { devol, linhaMais, sl, nSeries, fatura, doc, novo, sujo, a, aviso, ro, docstatus, marcas, marcaSel, assoc, imp, novaLinha, moeda, remover, gravar, emitir, proforma, converter, receber,
      abrirImportar, tiposImp, listaImp, escolherImp, importar, origens, titulo, pdf, irErp, link, ESTADO_DOC, statusPt, ROT_DT };
  },
  template: `<div v-if="doc" class="pad prop">
    <div class="sub"><a :href="irErp(dt)">← {{ fatura ? (devol ? 'Notas de crédito' : 'Faturas') : (devol ? 'Guias de devolução' : 'Guias de transporte') }}</a> · <a v-if="!novo" :href="irErp(dt, doc.name) + '/completa'">ficha completa</a><template v-if="devol && doc.return_against"> · corrige <a :href="irErp(dt, doc.return_against)">{{ doc.return_against }}</a></template></div>
    <div class="prop-topo">
      <div><div class="prop-tit"><h1>{{ titulo }}</h1><span class="etq" :class="ESTADO_DOC[docstatus][1]">{{ docstatus===0 ? 'Rascunho' : (doc.status ? statusPt(doc.status) : ESTADO_DOC[docstatus][0]) }}</span><span v-if="sujo" class="etq ambar">Por gravar</span><span v-if="doc.orbit_proforma_numero" class="etq">Pró-forma {{ doc.orbit_proforma_numero }}</span></div>
        <div class="sub" v-if="!novo">{{ doc.name }} · {{ doc.company }}</div></div>
      <div class="prop-accoes">
        <a v-if="pdf" class="btn" :href="pdf" target="_blank">PDF</a>
        <button v-if="!ro && (novo || sujo)" class="btn" :disabled="a" @click="gravar">Guardar rascunho</button>
        <button v-if="fatura && !novo && docstatus===0 && !ro" class="btn" :disabled="a" @click="proforma">{{ doc.orbit_proforma_numero ? 'Nova pró-forma' : 'Emitir pró-forma' }}</button>
        <button v-if="docstatus===0 && !ro" class="btn prim" :disabled="a" @click="emitir">{{ fatura ? (doc.orbit_proforma_numero ? 'Converter em fatura' : 'Emitir fatura') : 'Emitir e comunicar à AT' }}</button>
        <button v-if="!fatura && docstatus===1" class="btn prim" @click="converter('Sales Invoice')">Converter em fatura</button>
        <button v-if="fatura && docstatus===1 && doc.outstanding_amount > 0" class="btn prim" @click="receber">Receber pagamento</button>
        <button v-if="fatura && docstatus===1 && !doc.update_stock" class="btn" @click="converter('Delivery Note')">Criar guia</button>
      </div>
    </div>
    <div v-if="aviso" class="aviso">{{ aviso }}</div>
    <div class="prop-corpo">
      <div class="prop-principal">
        <section class="cartao prop-dados" :aria-label="fatura ? 'Dados da fatura' : 'Dados da guia'">
          <div class="prop-marcas" v-if="marcas.length"><div class="sub">Marca que {{ fatura ? 'vende' : 'envia' }}</div>
            <div class="prop-chips"><button v-for="m in marcas" :key="m.name" type="button" :disabled="ro" :class="{ativo: doc.orbit_marca===m.name}" @click="doc.orbit_marca=m.name"><span :style="{background: m.orbit_cor || '#5b6470'}"></span>{{ m.name }}</button></div>
            <div class="sub">{{ fatura ? 'Faturada' : 'Emitida' }} por <b>{{ doc.company }}</b><template v-if="doc.orbit_marca"> · série da marca {{ doc.orbit_marca }} no programa certificado</template></div></div>
          <div class="prop-campos">
            <label>Empresa/Cliente<ClienteProcura v-model="doc.customer" :ro="ro" @contacto="(c)=>{ if(!doc.contact_person) doc.contact_person=c }"/></label>
            <label>Ao cuidado de<ContactoProcura v-model="doc.contact_person" :parte="doc.customer" tipo="Customer" :ro="ro"/></label>
            <label>Data<input type="date" v-model="doc.posting_date" :disabled="ro"></label>
            <label v-if="fatura">Vencimento<input type="date" v-model="doc.due_date" :disabled="ro"></label>
            <template v-else>
              <label>Início do transporte<input type="datetime-local" :value="(doc.orbit_inicio_transporte||'').replace(' ','T').slice(0,16)" @input="doc.orbit_inicio_transporte=$event.target.value.replace('T',' ')+':00'" :disabled="ro"></label>
              <label>Matrícula<input v-model="doc.vehicle_no" :disabled="ro" placeholder="AA-00-AA"></label>
              <label>Armazém de carga<ErpLigacao v-model="doc.set_warehouse" alvo="Warehouse" :ro="ro" :filtros="JSON.stringify({is_group: 0, company: doc.company})"/></label>
              <label>Morada de descarga<ErpLigacao v-model="doc.shipping_address_name" alvo="Address" :ro="ro"/></label>
            </template>
          </div>
        </section>
        <section class="cartao" aria-label="Linhas" style="display:flex;flex-direction:column;gap:10px">
          <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
            <label v-if="!ro" class="cresce" style="min-width:220px"><span class="so-leitor">Adicionar artigo</span><ErpLigacao v-model="novaLinha" alvo="Item"/></label>
            <button v-if="!ro" type="button" class="btn" @click="abrirImportar">Importar de {{ fatura ? 'proposta, encomenda ou guia' : 'encomenda ou fatura' }}…</button>
          </div>
          <div v-if="origens.length" class="sub" style="background:var(--surface-2,#f6f8f9);border-radius:10px;padding:8px 12px">Linhas importadas de <template v-for="(o, i) in origens" :key="o.n">{{ i ? ', ' : '' }}<a :href="irErp(o.dt, o.n)">{{ ROT_DT[o.dt] || o.dt }} {{ o.n }}</a></template></div>
          <div style="overflow-x:auto;border:1px solid var(--line);border-radius:10px">
            <table class="tab-emitir" style="width:100%;border-collapse:collapse;min-width:620px;font-size:13px">
              <thead><tr><th style="text-align:left">Artigo</th><th>Qtd</th><th>Preço</th><th v-if="fatura">Desc. %</th><th style="text-align:left">Armazém</th><th>Total</th><th v-if="!ro"></th></tr></thead>
              <tbody>
                <template v-for="l in doc.items || []" :key="l.name"><tr>
                  <td><b>{{ l.item_name || l.item_code }}</b><div class="sub" style="font-size:12px">{{ l.item_code }} · <button type="button" class="link" @click="linhaMais[l.name] = !linhaMais[l.name]">{{ linhaMais[l.name] ? 'menos campos' : 'todos os campos' }}</button></div>
                    <div v-if="sl[l.item_code] && sl[l.item_code].lote" class="sl-campo"><label>Lote<span class="obrig">*</span>
                      <select v-model="l.batch_no" :disabled="ro" @change="l.use_serial_batch_fields=1"><option value="">— escolher —</option><option v-for="b in sl[l.item_code].lotes" :key="b.lote" :value="b.lote">{{ b.lote }}{{ b.validade ? ' · val. ' + b.validade : '' }}</option></select></label></div>
                    <div v-if="sl[l.item_code] && sl[l.item_code].serie" class="sl-campo"><label>N.º de série <span class="sub">({{ nSeries(l) }} de {{ l.qty || 0 }})</span><span class="obrig">*</span>
                      <textarea rows="2" v-model="l.serial_no" :disabled="ro" @input="l.use_serial_batch_fields=1" :placeholder="'Um por linha' + (sl[l.item_code].series.length ? ' — disponíveis: ' + sl[l.item_code].series.slice(0,5).join(', ') + (sl[l.item_code].series.length>5?'…':'') : '')"></textarea></label></div></td>
                  <td style="text-align:right"><input type="number" min="0" step="any" v-model.number="l.qty" :disabled="ro" style="width:90px;text-align:right"></td>
                  <td style="text-align:right"><input type="number" min="0" step="0.01" v-model.number="l.rate" :disabled="ro" style="width:118px;text-align:right"></td>
                  <td v-if="fatura" style="text-align:right"><input type="number" min="0" max="100" step="0.01" v-model.number="l.discount_percentage" :disabled="ro" style="width:80px;text-align:right"></td>
                  <td class="sub" style="font-size:12px">{{ l.warehouse || '—' }}</td>
                  <td style="text-align:right;font-weight:600">{{ moeda(l.amount) }}</td>
                  <td v-if="!ro"><button type="button" class="btn sm" @click="remover(l)" aria-label="Remover linha">×</button></td>
                </tr>
                <tr v-if="linhaMais[l.name]"><td :colspan="(fatura ? 6 : 5) + (ro ? 0 : 1)" style="padding:0"><ErpLinhaCampos :doctype="dt + ' Item'" :linha="l" :parent="doc" :ro="ro" :excluir="['item_code','item_name','qty','rate','discount_percentage','amount','serial_no','batch_no']"/></td></tr></template>
                <tr v-if="!(doc.items||[]).length"><td :colspan="fatura ? 7 : 6" class="sub" style="text-align:center;padding:14px">Sem linhas — acrescente um artigo ou importe de outro documento.</td></tr>
              </tbody>
            </table>
          </div>
          <label class="sub" style="display:flex;flex-direction:column;gap:4px">Observações<textarea rows="2" v-model="doc.remarks" :disabled="ro"></textarea></label>
        </section>
        <ErpRestantes :doctype="dt" :doc="doc" :ro="ro" :novo="novo" :excluir="['customer','contact_person','posting_date','due_date','remarks','set_warehouse','shipping_address_name','vehicle_no','items','orbit_marca']"/>
      </div>
      <aside class="prop-lado" aria-label="Resumo">
        <section class="cartao" aria-label="Documentos associados">
          <h2>Documentos associados</h2>
          <div v-if="!assoc.length && !origens.length" class="sub">Nenhum.</div>
          <a v-for="x in assoc" :key="x.doctype+x.name" :href="irErp(x.doctype, x.name)" class="prop-tot" style="text-decoration:none;color:inherit"><span><b>{{ x.tipo }}</b> {{ x.name }}</span><span class="etq">{{ x.docstatus===0 ? 'Rascunho' : statusPt(x.estado) }}</span></a>
        </section>
        <section class="cartao">
          <h2>Resumo</h2>
          <div class="prop-tot"><span>Total sem IVA</span><span>{{ moeda(doc.net_total) }}</span></div>
          <div class="prop-tot" v-for="t in doc.taxes || []" :key="t.name || t.idx"><span>{{ t.description }}</span><span>{{ moeda(t.tax_amount) }}</span></div>
          <div class="prop-tot" style="border-top:2px solid var(--ink);padding-top:8px"><b>Total</b><b style="font-size:20px">{{ moeda(doc.grand_total) }}</b></div>
          <div class="prop-tot" v-if="fatura && docstatus===1"><span>Em dívida</span><span>{{ moeda(doc.outstanding_amount) }}</span></div>
        </section>
        <section class="cartao" aria-label="Programa certificado">
          <h2>{{ fatura ? 'Documento certificado' : 'Comunicação à AT' }}</h2>
          <div class="prop-tot"><span>N.º certificado</span><span>{{ doc.orbit_numero_certificado || '—' }}</span></div>
          <div class="prop-tot" v-if="!fatura"><span>Código AT</span><span>{{ doc.orbit_codigo_at || '—' }}</span></div>
          <div class="prop-tot"><span>Estado</span><b>{{ doc.orbit_documento_certificado ? 'Enviado ao programa' : (docstatus===1 ? 'Sem programa certificado ligado' : 'Por emitir') }}</b></div>
          <p class="sub" style="margin:4px 0 0;font-size:12px">{{ fatura ? 'Ao emitir, o número, o ATCUD e o PDF vêm do programa certificado.' : 'O programa certificado comunica a guia à AT; o código AT fica aqui e sai no PDF que acompanha a mercadoria.' }}</p>
        </section>
      </aside>
    </div>
    <div v-if="imp" class="modal-fundo" @click.self="imp=null"><div class="modal" style="max-width:860px">
      <header><b>Importar para a {{ fatura ? 'fatura' : 'guia' }}</b><button class="btn sm" @click="imp=null">Fechar</button></header>
      <div style="padding:14px 16px;display:flex;flex-direction:column;gap:12px">
        <div class="sub">Documentos de {{ doc.customer_name || doc.customer }} que ainda têm alguma coisa por {{ fatura ? 'faturar' : 'enviar' }}.</div>
        <div style="display:flex;gap:6px;flex-wrap:wrap"><button class="btn sm" :class="{prim: !imp.filtro}" @click="imp.filtro=''">Todos</button><button v-for="t in tiposImp" :key="t" class="btn sm" :class="{prim: imp.filtro===t}" @click="imp.filtro=t">{{ t }}</button></div>
        <div v-if="!imp.lista" class="sub">A procurar…</div>
        <div v-else-if="!listaImp.length" class="sub">Não há nada por {{ fatura ? 'faturar' : 'enviar' }} deste cliente.</div>
        <div v-else style="overflow-x:auto;border:1px solid var(--line);border-radius:10px"><table class="tab-emitir" style="width:100%;border-collapse:collapse;min-width:560px;font-size:13px">
          <thead><tr><th></th><th style="text-align:left">Documento</th><th style="text-align:left">Data</th><th style="text-align:left">Estado</th><th>Valor</th></tr></thead>
          <tbody><tr v-for="x in listaImp" :key="x.doctype+x.name" :style="imp.escolhido===x ? {background:'var(--surface-2,#f6f8f9)'} : {}">
            <td><input type="radio" name="imp" :checked="imp.escolhido===x" @change="escolherImp(x)" :aria-label="'Importar '+x.name"></td>
            <td><b>{{ x.tipo }} {{ x.name }}</b><div v-if="x.marca" class="sub" style="font-size:12px">marca {{ x.marca }}</div></td><td>{{ x.data }}</td><td>{{ statusPt(x.estado) }}</td><td style="text-align:right">{{ moeda(x.total) }}</td></tr></tbody></table></div>
        <fieldset v-if="imp.escolhido" style="border:1px solid var(--line);border-radius:10px;padding:10px 12px;margin:0">
          <legend class="sub" style="padding:0 6px">Linhas de {{ imp.escolhido.name }}</legend>
          <div v-if="!imp.linhas.length" class="sub">Já está tudo {{ fatura ? 'faturado' : 'enviado' }}.</div>
          <label v-for="l in imp.linhas" :key="l.i" style="display:flex;gap:10px;align-items:center;padding:4px 0"><input type="checkbox" v-model="imp.marcadas[l.i]"><span class="cresce">{{ l.item_name }}</span><span class="sub">{{ l.qty }} {{ l.uom }}</span><span style="min-width:90px;text-align:right">{{ moeda(l.amount) }}</span></label>
        </fieldset>
        <p class="sub" style="margin:0;font-size:12px">As linhas vêm com o preço e o desconto do documento de origem e os dois documentos ficam associados.</p>
        <div style="display:flex;justify-content:flex-end;gap:8px"><button class="btn" @click="imp=null">Cancelar</button><button class="btn prim" :disabled="!imp.escolhido || imp.aImportar" @click="importar">{{ imp.aImportar ? 'A importar…' : 'Importar' }}</button></div>
      </div></div></div>
    <div style="padding:0 24px 24px"><RegistoArea v-if="name && name!=='novo'" :doctype="dt" :name="name" :key="'ra'+name"/></div>
  </div>`,
};

// ── Receber pagamento (recibo) ─────────────────────────────────────────────────────────────────────────────
const ErpRecibo = {
  components: { ErpLigacao, ErpRestantes },
  props: ["name"],
  setup(props) {
    const novo = props.name === "novo";
    const f = ref({ cliente: "", valor: 0, data: new Date().toISOString().slice(0, 10), modo: "", referencia: "" });
    const faturas = ref(null), modos = ref([]), doc = ref(null), assoc = ref([]), a = ref(false);
    const moeda = (v) => new Intl.NumberFormat("pt-PT", { style: "currency", currency: "EUR" }).format(v || 0);
    const carregarFaturas = async (marcar) => { if (!f.value.cliente) { faturas.value = null; return; }
      const l = await apiE("em_aberto", { cliente: f.value.cliente }); faturas.value = l.map((x) => ({ ...x, pagar: marcar ? x.name === marcar : false, valor: marcar && x.name === marcar ? x.divida : 0 }));
      if (marcar) f.value.valor = faturas.value.filter((x) => x.pagar).reduce((s, x) => s + x.valor, 0); };
    onMounted(async () => {
      if (novo) { modos.value = ((await apiE("contas_recebimento").catch(() => ({}))) || {}).modos || [];
        f.value.modo = modos.value.find((m) => /transfer/i.test(m)) || modos.value[0] || "";
        let p = null; try { p = JSON.parse(sessionStorage.getItem("orbit.recibo") || "null"); sessionStorage.removeItem("orbit.recibo"); } catch (e) {}
        if (p) { f.value.cliente = p.cliente; await carregarFaturas(p.fatura); } }
      else { const r = await api("erp.documento", { doctype: "Payment Entry", name: props.name }); doc.value = r.doc;
        assoc.value = (await apiE("associados", { doctype: "Payment Entry", name: props.name }).catch(() => [])) || []; }
    });
    watch(() => f.value.cliente, (v, o) => { if (novo && v !== o) carregarFaturas(); });
    const marcar = (x) => { x.valor = x.pagar ? x.divida : 0; };
    const liquidado = computed(() => (faturas.value || []).filter((x) => x.pagar).reduce((s, x) => s + (Number(x.valor) || 0), 0));
    const diferenca = computed(() => (Number(f.value.valor) || 0) - liquidado.value);
    const distribuir = () => { let resto = Number(f.value.valor) || 0;
      for (const x of faturas.value || []) { const v = Math.min(resto, x.divida); x.pagar = v > 0; x.valor = Math.round(v * 100) / 100; resto -= v; } };
    const emitir = async () => {
      const lista = (faturas.value || []).filter((x) => x.pagar && x.valor > 0).map((x) => ({ name: x.name, valor: x.valor }));
      if (!lista.length) { toast("Escolha pelo menos uma fatura"); return; }
      if (diferenca.value < -0.004) { toast("O valor recebido é menor do que o liquidado"); return; }
      if (!confirm("Emitir o recibo de " + moeda(f.value.valor) + "?")) return;
      a.value = true;
      try { const r = await apiE("gravar_recibo", { cliente: f.value.cliente, data: f.value.data, valor: f.value.valor, modo: f.value.modo, referencia: f.value.referencia, faturas: JSON.stringify(lista), submeter: 1 }, true);
        toast(r.recibos.length > 1 ? r.recibos.length + " recibos emitidos (um por marca)" : "Recibo emitido"); location.hash = irErp("Payment Entry", r.recibos[0].name); }
      finally { a.value = false; } };
    const hoje = new Date().toISOString().slice(0, 10);
    return { novo, f, faturas, modos, doc, assoc, a, moeda, marcar, liquidado, diferenca, distribuir, emitir, irErp, statusPt, ESTADO_DOC, hoje };
  },
  template: `<div class="pad prop">
    <div class="sub"><a :href="irErp('Payment Entry')">← Recibos</a><template v-if="!novo"> · <a :href="irErp('Payment Entry', name) + '/completa'">ficha completa</a></template></div>
    <template v-if="novo">
      <div class="prop-topo"><div class="prop-tit"><h1>Receber pagamento</h1></div><div class="prop-accoes"><button class="btn prim" :disabled="a" @click="emitir">Emitir recibo</button></div></div>
      <div class="prop-corpo">
        <div class="prop-principal">
          <section class="cartao prop-dados" aria-label="Pagamento"><div class="prop-campos">
            <label>Cliente<ErpLigacao v-model="f.cliente" alvo="Customer"/></label>
            <label>Valor recebido<input type="number" min="0" step="0.01" v-model.number="f.valor"></label>
            <label>Data<input type="date" v-model="f.data"></label>
            <label>Meio de pagamento<select v-model="f.modo"><option v-for="m in modos" :key="m" :value="m">{{ m }}</option></select></label>
            <label>Referência do pagamento<input v-model="f.referencia" placeholder="Ex.: TRF 25/11"></label>
          </div></section>
          <section class="cartao" aria-label="Faturas em aberto" style="display:flex;flex-direction:column;gap:10px">
            <div style="display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;align-items:center"><h2 style="margin:0;font-size:15px">Faturas em aberto deste cliente</h2><button v-if="faturas && faturas.length" class="btn sm" @click="distribuir">Distribuir pelas mais antigas</button></div>
            <div v-if="!f.cliente" class="sub">Escolha o cliente.</div>
            <div v-else-if="!faturas" class="sub">A procurar…</div>
            <div v-else-if="!faturas.length" class="sub">Este cliente não tem faturas em aberto.</div>
            <div v-else style="overflow-x:auto;border:1px solid var(--line);border-radius:10px"><table class="tab-emitir" style="width:100%;border-collapse:collapse;min-width:560px;font-size:13px">
              <thead><tr><th>Pagar</th><th style="text-align:left">Fatura</th><th style="text-align:left">Vencimento</th><th>Em dívida</th><th>A liquidar</th></tr></thead>
              <tbody><tr v-for="x in faturas" :key="x.name">
                <td style="text-align:center"><input type="checkbox" v-model="x.pagar" @change="marcar(x)" :aria-label="'Pagar '+x.numero"></td>
                <td><b>{{ x.numero }}</b><div v-if="x.marca" class="sub" style="font-size:12px">marca {{ x.marca }}</div></td>
                <td :style="x.vencida ? {color:'var(--acao)',fontWeight:600} : {}">{{ x.vencimento }}<template v-if="x.vencida"> · vencida</template></td>
                <td style="text-align:right">{{ moeda(x.divida) }}</td>
                <td style="text-align:right"><input type="number" min="0" :max="x.divida" step="0.01" v-model.number="x.valor" :disabled="!x.pagar" style="width:100px;text-align:right"></td></tr></tbody></table></div>
          </section>
        </div>
        <aside class="prop-lado" aria-label="Resumo">
          <section class="cartao"><h2>Resumo</h2>
            <div class="prop-tot"><span>Recebido</span><span>{{ moeda(f.valor) }}</span></div>
            <div class="prop-tot"><span>Liquidado</span><span>{{ moeda(liquidado) }}</span></div>
            <div class="prop-tot" style="border-top:1px solid var(--line);padding-top:8px"><b>Diferença</b><b :style="diferenca < -0.004 ? {color:'var(--acao)'} : {}">{{ moeda(diferenca) }}</b></div>
            <p class="sub" style="margin:4px 0 0;font-size:12px">O que sobra fica como adiantamento do cliente. Faturas de marcas diferentes saem em recibos separados, cada um na série da sua marca.</p></section>
        </aside>
      </div>
    </template>
    <template v-else-if="doc">
      <div class="prop-topo"><div><div class="prop-tit"><h1>Recibo {{ doc.name }}</h1><span class="etq" :class="ESTADO_DOC[doc.docstatus||0][1]">{{ ESTADO_DOC[doc.docstatus||0][0] }}</span></div><div class="sub">{{ doc.party_name || doc.party }} · {{ doc.posting_date }} · {{ doc.mode_of_payment }}</div></div>
        <div class="prop-accoes"><a class="btn" :href="'/api/method/frappe.utils.print_format.download_pdf?doctype=Payment%20Entry&name='+encodeURIComponent(doc.name)" target="_blank">PDF</a></div></div>
      <div class="prop-corpo">
        <div class="prop-principal"><section class="cartao"><h2 style="font-size:15px;margin:0 0 8px">Faturas liquidadas</h2>
          <a v-for="r in doc.references || []" :key="r.name" class="prop-tot" :href="irErp(r.reference_doctype, r.reference_name)" style="text-decoration:none;color:inherit"><span>{{ r.reference_name }}</span><span>{{ moeda(r.allocated_amount) }}</span></a>
          <div class="prop-tot" style="border-top:2px solid var(--ink);padding-top:8px"><b>Recebido</b><b>{{ moeda(doc.paid_amount) }}</b></div></section></div>
      <ErpRestantes doctype="Payment Entry" :doc="doc" :ro="true" :novo="false" :excluir="['references']" style="margin-top:14px"/>
        <aside class="prop-lado"><section class="cartao"><h2>Documentos associados</h2>
          <div v-if="!assoc.length" class="sub">Nenhum.</div>
          <a v-for="x in assoc" :key="x.doctype+x.name" :href="irErp(x.doctype, x.name)" class="prop-tot" style="text-decoration:none;color:inherit"><span><b>{{ x.tipo }}</b> {{ x.name }}</span><span class="etq">{{ statusPt(x.estado) }}</span></a></section>
          <section class="cartao"><h2>Recibo certificado</h2><div class="prop-tot"><span>Estado</span><b>{{ doc.orbit_documento_certificado ? 'Enviado ao programa' : 'Sem programa certificado ligado' }}</b></div></section></aside>
      </div>
    </template>
    <div style="padding:0 24px 24px"><RegistoArea v-if="name && name!=='novo'" doctype="Payment Entry" :name="name" :key="'ra'+name"/></div>
  </div>`,
};
// 26-11-2026 (Vítor): o cliente da proposta procura-se em todo o lado (clientes do ERP e CRM) e cria-se quando falta
const ClienteProcura = {
  props: ["modelValue", "ro", "modo"], emits: ["update:modelValue", "contacto"],
  setup(props, { emit }) {
    const lead = computed(() => props.modo === "lead");
    const txt = ref(props.modelValue || ""), ops = ref([]), aberto = ref(false), campo = ref(null), pos = ref({}), novo = ref(null), a = ref(false); let tq;
    watch(() => props.modelValue, (v) => { if (v !== txt.value) txt.value = v || ""; });
    const posicionar = () => { const r = campo.value?.getBoundingClientRect(); if (!r) return; const w = Math.min(Math.max(r.width, 320), window.innerWidth - 16);
      pos.value = { position: "fixed", left: Math.max(8, Math.min(r.left, window.innerWidth - w - 8)) + "px", width: w + "px", top: (r.bottom + 4) + "px", maxHeight: Math.max(200, window.innerHeight - r.bottom - 20) + "px" }; };
    const aProcurar = ref(false); let nP = 0;
    const procurar = () => { clearTimeout(tq); aProcurar.value = true; posicionar(); aberto.value = true;
      tq = setTimeout(async () => { const n = ++nP; const r = await api("clientes_venda.procurar", { q: txt.value, modo: props.modo || "cliente" }).catch(() => []); if (n !== nP) return; ops.value = r; aProcurar.value = false; posicionar(); }, 200); };
    const escolher = async (o) => { aberto.value = false;
      if (o.tipo === "cliente") { txt.value = o.name; emit("update:modelValue", o.name); return; }
      a.value = true; try { const r = await api("clientes_venda.usar", { doctype: o.doctype, name: o.name, modo: props.modo || "cliente" }, true); txt.value = r.customer; emit("update:modelValue", r.customer); if (r.contacto) emit("contacto", r.contacto); toast("Cliente «" + r.customer + "» pronto"); } finally { a.value = false; } };
    const criar = async () => { a.value = true; try { const r = await api("clientes_venda.usar", { dados: JSON.stringify(novo.value), modo: props.modo || "cliente" }, true); txt.value = r.customer; emit("update:modelValue", r.customer); novo.value = null; toast("Cliente criado"); } finally { a.value = false; } };
    const sair = () => setTimeout(() => { aberto.value = false; }, 180);
    return { lead, aProcurar, txt, ops, aberto, campo, pos, novo, a, procurar, escolher, criar, sair, irErp };
  },
  template: `<div class="erp-ligacao">
    <input ref="campo" v-model="txt" :disabled="ro" :placeholder="lead ? 'Procurar lead…' : 'Procurar empresa, cliente ou contacto…'" @focus="procurar" @input="procurar" @blur="sair" @keydown.esc="aberto=false" autocomplete="off">
    <a v-if="modelValue" class="ir" :href="irErp(lead ? 'Lead' : 'Customer', modelValue)" :title="lead ? 'Abrir a lead' : 'Abrir o cliente'">↗</a>
    <div v-if="aberto" class="cartao erp-ops cli-ops" :style="pos">
      <div v-if="aProcurar && !ops.length" class="sub" style="padding:8px 10px;font-size:13px">A procurar…</div>
      <div v-if="!txt && ops.length" class="sub cli-grupo">{{ lead ? 'Leads mais recentes' : 'Clientes e contactos mais recentes' }} — escreva para procurar</div>
      <div v-for="o in ops" :key="o.doctype+o.name" class="linha" @mousedown.prevent="escolher(o)"><div class="cresce"><b>{{ o.titulo }}</b><small>{{ o.sub }}<template v-if="o.tipo==='crm'"> · {{ lead ? 'passa a lead do ERP' : 'passa a cliente' }} ao escolher</template></small></div></div>
      <div v-if="!ops.length && !aProcurar" class="sub" style="padding:8px 10px;font-size:13px">{{ txt ? (lead ? 'Nenhuma lead com «' : 'Nenhum cliente, empresa ou contacto com «') + txt + '».' : 'Escreva para procurar.' }}</div>
      <div class="linha cli-novo" @mousedown.prevent="novo={nome:txt,tipo:'Empresa',nif:'',email:'',telefone:'',empresa:''}; aberto=false">+ {{ lead ? 'Criar lead' : 'Criar cliente' }}{{ txt ? ' «' + txt + '»' : '' }}</div>
    </div>
    <div v-if="novo" class="modal-fundo" @click.self="novo=null"><div class="modal" style="max-width:460px"><header><b>{{ lead ? 'Nova lead' : 'Novo cliente' }}</b><button class="btn sm" @click="novo=null">Fechar</button></header>
      <form class="reg-form" @submit.prevent="criar"><label class="erp-campo"><span>{{ lead ? 'Nome da pessoa' : 'Nome' }}<span class="obrig">*</span></span><input v-model="novo.nome" required autofocus></label>
        <label v-if="lead" class="erp-campo"><span>Empresa</span><input v-model="novo.empresa"></label>
        <div v-if="!lead" class="reg-linha3" style="grid-template-columns:1fr 1fr"><label class="erp-campo"><span>Tipo</span><select v-model="novo.tipo"><option>Empresa</option><option>Particular</option></select></label><label class="erp-campo"><span>NIF</span><input v-model="novo.nif"></label></div>
        <div class="reg-linha3" style="grid-template-columns:1fr 1fr"><label class="erp-campo"><span>Email</span><input type="email" v-model="novo.email"></label><label class="erp-campo"><span>Telemóvel</span><input type="tel" v-model="novo.telefone"></label></div>
        <div class="reg-botoes"><button class="btn prim" :disabled="a">Criar e usar</button></div></form></div></div>
  </div>`,
};
// «Ao cuidado de» (27-11-2026): procura os contactos — primeiro os da empresa/cliente, depois os outros — e cria um novo já ligado
const ContactoProcura = {
  props: ["modelValue", "ro", "parte", "tipo"], emits: ["update:modelValue"],
  setup(props, { emit }) {
    const txt = ref(props.modelValue || ""), ops = ref([]), aberto = ref(false), campo = ref(null), pos = ref({}), novo = ref(null), a = ref(false), aProcurar = ref(false); let tq, nP = 0;
    watch(() => props.modelValue, (v) => { if (v !== txt.value) txt.value = v || ""; });
    const posicionar = () => { const r = campo.value?.getBoundingClientRect(); if (!r) return; const w = Math.min(Math.max(r.width, 300), window.innerWidth - 16);
      pos.value = { position: "fixed", left: Math.max(8, Math.min(r.left, window.innerWidth - w - 8)) + "px", width: w + "px", top: (r.bottom + 4) + "px", maxHeight: Math.max(200, window.innerHeight - r.bottom - 20) + "px" }; };
    const procurar = () => { clearTimeout(tq); aProcurar.value = true; posicionar(); aberto.value = true;
      tq = setTimeout(async () => { const n = ++nP; const r = await api("clientes_venda.contactos", { q: txt.value === props.modelValue ? "" : txt.value, parte: props.parte || "", tipo: props.tipo || "Customer" }).catch(() => []);
        if (n !== nP) return; ops.value = r; aProcurar.value = false; posicionar(); }, 200); };
    const escolher = (o) => { aberto.value = false; txt.value = o.name; emit("update:modelValue", o.name); };
    const limpar = () => { txt.value = ""; emit("update:modelValue", ""); };
    const criar = async () => { a.value = true; try { const r = await api("clientes_venda.criar_contacto", { dados: JSON.stringify(novo.value), parte: props.parte || "", tipo: props.tipo || "Customer" }, true);
      txt.value = r.name; emit("update:modelValue", r.name); novo.value = null; toast("Contacto criado"); } finally { a.value = false; } };
    const sair = () => setTimeout(() => { aberto.value = false; if (!txt.value && props.modelValue) emit("update:modelValue", ""); }, 180);
    const daParte = computed(() => ops.value.filter((o) => o.da_parte)), outros = computed(() => ops.value.filter((o) => !o.da_parte));
    return { txt, ops, aberto, campo, pos, novo, a, aProcurar, procurar, escolher, limpar, criar, sair, daParte, outros, irErp };
  },
  template: `<div class="erp-ligacao">
    <input ref="campo" v-model="txt" :disabled="ro" placeholder="Procurar contacto…" @focus="procurar" @input="procurar" @blur="sair" @keydown.esc="aberto=false" autocomplete="off">
    <a v-if="modelValue" class="ir" :href="irErp('Contact', modelValue)" title="Abrir o contacto">↗</a>
    <div v-if="aberto" class="cartao erp-ops cli-ops" :style="pos">
      <div v-if="aProcurar && !ops.length" class="sub" style="padding:8px 10px;font-size:13px">A procurar…</div>
      <div v-if="daParte.length" class="sub cli-grupo">Contactos de {{ parte }}</div>
      <div v-for="o in daParte" :key="o.name" class="linha" @mousedown.prevent="escolher(o)"><div class="cresce"><b>{{ o.titulo }}</b><small>{{ o.sub }}</small></div></div>
      <div v-if="outros.length" class="sub cli-grupo">{{ daParte.length ? 'Outros contactos' : (parte ? 'Sem contactos ligados a ' + parte + ' — outros contactos' : 'Contactos') }}</div>
      <div v-for="o in outros" :key="o.name" class="linha" @mousedown.prevent="escolher(o)"><div class="cresce"><b>{{ o.titulo }}</b><small>{{ o.sub }}</small></div></div>
      <div v-if="!ops.length && !aProcurar" class="sub" style="padding:8px 10px;font-size:13px">{{ txt ? 'Nenhum contacto com «' + txt + '».' : 'Escreva para procurar.' }}</div>
      <div class="linha cli-novo" @mousedown.prevent="novo={nome:txt,email:'',telefone:''}; aberto=false">+ Criar contacto{{ txt ? ' «' + txt + '»' : '' }}{{ parte ? ' em ' + parte : '' }}</div>
    </div>
    <div v-if="novo" class="modal-fundo" @click.self="novo=null"><div class="modal" style="max-width:460px"><header><b>Novo contacto</b><button class="btn sm" @click="novo=null">Fechar</button></header>
      <form class="reg-form" @submit.prevent="criar"><label class="erp-campo"><span>Nome<span class="obrig">*</span></span><input v-model="novo.nome" required autofocus></label>
        <div class="reg-linha3" style="grid-template-columns:1fr 1fr"><label class="erp-campo"><span>Email</span><input type="email" v-model="novo.email"></label><label class="erp-campo"><span>Telemóvel</span><input type="tel" v-model="novo.telefone"></label></div>
        <p v-if="parte" class="sub" style="margin:0;font-size:12px">Fica ligado a {{ parte }}.</p>
        <div class="reg-botoes"><button class="btn prim" :disabled="a">Criar e usar</button></div></form></div></div>
  </div>`,
};
// O produto lido de uma página (ou da IA) para rever antes de criar o artigo
const ProdutoRever = {
  props: ["p", "marca"], emits: ["fechar", "criado", "ia"],
  setup(props, { emit }) {
    const d = ref({ referencia: props.p.referencia || "", titulo: props.p.titulo || "", descricao: props.p.descricao || "",
      caracteristicas: (props.p.caracteristicas || []).map((x) => Array.isArray(x) ? (x[0] ? x[0] + ": " : "") + x[1] : x).join("\n"), imagem: (props.p.imagens || [])[0] || "", preco: props.p.preco || 0 });
    const a = ref(false);
    const criar = async () => { if (!d.value.referencia.trim()) { toast("Indique a referência do artigo"); return; } a.value = true;
      try { const g = await api("orbit.propostas.referencia.gravar_artigo", { dados: JSON.stringify({ ...d.value, marca: props.marca, fonte: props.p.fonte }) }, true);
        emit("criado", { ...g, preco: Number(d.value.preco) || 0, caracteristicas: g.orbit_caracteristicas }); } finally { a.value = false; } };
    const usarExistente = () => emit("criado", { item_code: props.p.existente.artigo, item_name: props.p.existente.titulo, image: (props.p.existente.imagens || [])[0], preco: props.p.existente.preco, caracteristicas: (props.p.existente.caracteristicas || []).map((x) => (x[0] ? x[0] + ": " : "") + x[1]).join("\n") });
    return { d, a, criar, usarExistente };
  },
  template: `<div class="modal-fundo" @click.self="$emit('fechar')"><div class="modal" style="max-width:820px"><header><b>Produto {{ p.ia ? 'lido pela IA' : 'lido da página' }}</b><button class="btn sm" @click="$emit('fechar')">Fechar</button></header>
    <div class="reg-form">
      <div v-if="!p.lido" class="aviso" style="margin:0">Não foi possível ler a página ({{ (p.falta||[]).join(', ') }}).</div>
      <div v-else-if="(p.falta||[]).length && !p.ia" class="aviso" style="margin:0">A página não diz: {{ p.falta.join(', ') }}. Pode completar à mão ou pedir à IA.</div>
      <div v-if="p.existente" class="aviso" style="margin:0;display:flex;gap:8px;align-items:center;flex-wrap:wrap">Já existe o artigo «{{ p.existente.titulo }}» com esta referência. <button class="btn sm prim" @click="usarExistente">Usar o que existe</button></div>
      <div class="prod-rever"><div class="prod-imgs"><img v-if="d.imagem" :src="d.imagem" alt=""><div class="prod-mini"><img v-for="i in p.imagens||[]" :key="i" :src="i" :class="{ativo: i===d.imagem}" @click="d.imagem=i" alt=""></div></div>
        <div style="display:flex;flex-direction:column;gap:8px;min-width:0">
          <div class="reg-linha3" style="grid-template-columns:1fr 2fr"><label class="erp-campo"><span>Referência<span class="obrig">*</span></span><input v-model="d.referencia"></label><label class="erp-campo"><span>Nome</span><input v-model="d.titulo"></label></div>
          <label class="erp-campo"><span>Descrição</span><textarea v-model="d.descricao" rows="3"></textarea></label>
          <label class="erp-campo"><span>Características (uma por linha, «nome: valor»)</span><textarea v-model="d.caracteristicas" rows="5"></textarea></label>
          <div class="reg-linha3" style="grid-template-columns:1fr 2fr"><label class="erp-campo"><span>Preço de venda (€)</span><input type="number" step="0.01" v-model.number="d.preco"></label><span class="sub" style="font-size:12px;align-self:end">{{ p.fabricante ? 'Fabricante: ' + p.fabricante : '' }}<template v-if="p.preco"> · preço na página: {{ p.preco }} {{ p.moeda || '' }}</template></span></div>
        </div></div>
      <div class="reg-botoes"><button v-if="!p.ia" class="btn" style="margin-right:auto" @click="$emit('ia')">Completar com a IA · créditos</button>
        <button class="btn" @click="$emit('fechar')">Cancelar</button><button class="btn prim" :disabled="a" @click="criar">Criar o artigo e acrescentar</button></div>
    </div></div></div>`,
};

const ErpProposta = {
  components: { ErpLigacao, ErpCampo, ErpRestantes, ErpLinhaCampos, EditorRico, ClienteProcura, ContactoProcura, ProdutoRever },
  props: ["name"],
  setup(props) {
    const doc = ref(null); const novo = ref(false); const sujo = ref(false); const a = ref(false); const aviso = ref("");
    const marcas = ref([]); const versoes = ref([]); const podeGravar = ref(true);
    const q = ref(""); const sug = ref([]); const procurando = ref(false); const fab = ref(""); let tq;
    const abertas = ref({}); const envio = ref(null);
    const carregar = async () => {
      const [r, ms] = await Promise.all([api("erp.documento", { doctype: "Quotation", name: props.name === "novo" ? undefined : props.name }), apiP("versoes.marcas")]);
      marcas.value = ms || []; doc.value = r.doc; novo.value = r.novo; podeGravar.value = r.novo ? true : r.pode_gravar;
      if (novo.value) { doc.value.quotation_to = doc.value.quotation_to || "Customer"; if (doc.value.orbit_imprimir_total == null) doc.value.orbit_imprimir_total = 1;
        // 25-11-2026: «Criar orçamento» na ficha do negócio — vem com o negócio, o cliente, o contacto e a marca
        let ng = null; try { ng = sessionStorage.getItem("orbit.novoOrcamento"); sessionStorage.removeItem("orbit.novoOrcamento"); } catch (e) {}
        if (ng) { const d = await apiP("negocio.dados_para_orcamento", { negocio: ng }).catch(() => null);
          if (d) Object.keys(d).forEach((k) => { if (d[k]) doc.value[k] = d[k]; }); } }
      versoes.value = r.novo ? [] : (await apiP("versoes.versoes", { name: props.name }) || []);
      await nextTick(); sujo.value = false; ultima = assin();
    };
    onMounted(carregar);
    watch(doc, (n, o) => { if (o) sujo.value = true; }, { deep: true });
    const linhas = computed(() => (doc.value?.items || []).filter((l) => !l.orbit_de));
    const docstatus = computed(() => doc.value?.docstatus || 0);
    const ro = computed(() => !podeGravar.value || docstatus.value !== 0);
    const moeda = (v) => new Intl.NumberFormat("pt-PT", { style: "currency", currency: doc.value?.currency || "EUR" }).format(v || 0);
    const soma = (cod) => (doc.value?.items || []).filter((l) => l.orbit_de && l.item_code === cod).reduce((s, l) => s + (l.amount || 0), 0);
    const totais = computed(() => { const d = doc.value || {}; const t = soma("TRANSPORTE"), m = soma("MONTAGEM");
      return { equip: (d.total || 0) - t - m, transporte: t, montagem: m, sem: d.net_total || 0, iva: d.total_taxes_and_charges || 0, com: d.rounded_total || d.grand_total || 0 }; });
    const marcaSel = computed(() => marcas.value.find((m) => m.name === doc.value?.orbit_marca));
    const corMarca = (m) => m?.orbit_cor || "#5b6470";
    // recálculo pelo ERP (preço, impostos, transporte/montagem, características) — nada é gravado
    let ultima = ""; let tr0;
    const assin = () => { const d = doc.value; if (!d) return ""; return JSON.stringify([d.party_name, d.orbit_marca, d.orbit_transporte_modo, d.orbit_transporte_total, d.orbit_montagem_total, d.taxes_and_charges,
      (d.items || []).filter((l) => !l.orbit_de).map((l) => [l.item_code, l.qty, l.rate, l.orbit_transporte, l.orbit_montagem])]); };
    let nRec = 0;
    const recalcular = async () => {
      if (ro.value) return; const n = ++nRec; const enviado = JSON.parse(JSON.stringify(doc.value));
      const r = await api("erp.recalcular", { doctype: "Quotation", dados: JSON.stringify(enviado) }, true).catch(() => null);
      if (!r || n !== nRec) return; aviso.value = r.aviso || ""; if (!r.doc) return;
      const nomes = (enviado.items || []).filter((l) => !l.orbit_de).map((l) => l.name);
      r.doc.items = (r.doc.items || []).map((l, i) => (!l.orbit_de && i < nomes.length && !l.name ? { ...l, name: nomes[i] } : l));
      juntarRecalculo(doc.value, r.doc, enviado); ultima = assin();
    };
    watch(() => assin(), (s) => { if (s === ultima) return; ultima = s; clearTimeout(tr0); tr0 = setTimeout(recalcular, 450); });
    // procurar produtos: ERP primeiro; internet só a pedido
    const rever = ref(null); const eUrl = computed(() => /^https?:\/\//i.test(q.value.trim()));
    const lerPagina = async () => { procurando.value = true; try { rever.value = await apiP("url_produto.ler", { url: q.value.trim() }); } finally { procurando.value = false; } };
    const lerComIa = async () => { const u = (rever.value && rever.value.url) || q.value.trim(); if (!confirm("A IA lê a página e preenche o que falta. Gasta créditos de IA da conta.")) return; procurando.value = true;
      try { const r = await apiP("url_produto.ler_com_ia", { url: u, marca: doc.value?.orbit_marca }); const ant = rever.value || {};
        rever.value = { ...r, referencia: r.referencia || ant.referencia, titulo: r.titulo || ant.titulo, imagens: (r.imagens && r.imagens.length ? r.imagens : ant.imagens) || [], caracteristicas: (r.caracteristicas && r.caracteristicas.length ? r.caracteristicas : ant.caracteristicas) || [] }; } finally { procurando.value = false; } };
    const depoisDeCriar = (g) => { acrescentar(g); rever.value = null; toast("Artigo criado e acrescentado"); };
    // 27-11-2026: aviso enquanto procura, e só conta a resposta do último texto (as antigas chegavam depois e trocavam a lista)
    const aSugerir = ref(false); const sugDe = ref(""); let nSug = 0;
    watch(q, () => { clearTimeout(tq); const t = q.value.trim(); if (t.length < 2 || eUrl.value) { sug.value = []; aSugerir.value = false; if (eUrl.value) tq = setTimeout(lerPagina, 400); return; }
      aSugerir.value = true; tq = setTimeout(async () => { const n = ++nSug;
        try { const r = await apiP("versoes.sugestoes", { txt: t, marca: doc.value?.orbit_marca }) || []; if (n === nSug) { sug.value = r; sugDe.value = t; } }
        finally { if (n === nSug) aSugerir.value = false; } }, 200); });
    const acrescentar = (p) => {
      doc.value.items = doc.value.items || [];
      const n = linhas.value.length;
      doc.value.items.splice(n, 0, { name: "novo-" + Math.random().toString(36).slice(2, 9), doctype: "Quotation Item", item_code: p.item_code, item_name: p.item_name, qty: 1,
        rate: p.preco || 0, image: p.image, uom: p.uom, orbit_caracteristicas: p.caracteristicas || p.orbit_caracteristicas || "", brand: doc.value.orbit_marca, orbit_fonte: p.orbit_fonte || "" });
      q.value = ""; sug.value = [];
    };
    const internet = async () => {
      if (!q.value.trim()) { toast("Escreva a referência"); return; }
      if (!confirm("Procurar " + (fab.value.trim() ? "«" + fab.value.trim() + " " + q.value.trim() + "»" : "«" + q.value + "»") + " na internet? Gasta créditos de IA da conta.")) return;
      procurando.value = true;
      try {
        const r = await apiP("referencia.procurar_internet", { referencia: q.value.trim(), fabricante: fab.value.trim(), marca: doc.value?.orbit_marca });
        const p = r?.produto; if (!p) { toast("Não encontrado na internet"); return; }
        // 26-11-2026 (Vítor): nada se cria sem a pessoa ver — abre a revisão com «Criar o artigo e acrescentar»
        rever.value = { lido: true, ia: true, referencia: q.value.trim(), titulo: p.titulo, descricao: p.descricao, caracteristicas: p.caracteristicas || [], imagens: p.imagens || [], preco: p.preco, fabricante: p.fabricante || fab.value.trim(), fonte: p.fonte, falta: [], existente: r.existente };
      } finally { procurando.value = false; }
    };
    const remover = (l) => { doc.value.items = doc.value.items.filter((x) => x !== l); };
    const gravar = async () => {
      // 27-11-2026 (Vítor): sem marca não se grava — a marca dá o logótipo, a série, as condições e o rodapé
      if (marcas.value.length && !doc.value.orbit_marca) { toast("Escolha a marca que envia a proposta"); aviso.value = "Escolha a marca que envia a proposta (em cima, «Marca que envia»)."; window.scrollTo({ top: 0, behavior: "smooth" }); return; }
      if (!doc.value.party_name) { toast("Escolha o cliente"); return; }
      if (!linhas.value.length) { toast("Acrescente pelo menos um produto"); return; }
      a.value = true;
      try { const r = await api("erp.gravar", { doctype: "Quotation", dados: JSON.stringify(doc.value) }, true); toast("Gravado");
        if (novo.value || r.doc.name !== props.name) { location.hash = irErp("Quotation", r.doc.name); return; }
        doc.value = r.doc; await nextTick(); sujo.value = false; ultima = assin(); } finally { a.value = false; }
    };
    const alternativa = async () => {
      if (sujo.value || novo.value) { toast("Grave a proposta primeiro"); return; }
      const r = await apiP("versoes.criar_alternativa", { name: doc.value.name }, true);
      toast("Versão nova criada — troque o produto"); location.hash = irErp("Quotation", r.name);
    };
    const submeter = async () => { if (!confirm("Fechar esta versão da proposta? Depois de fechada já não se altera (pode criar outra versão).")) return;
      a.value = true; try { const r = await api("erp.submeter", { doctype: "Quotation", name: doc.value.name }, true); doc.value = r.doc; await nextTick(); sujo.value = false; toast("Proposta fechada"); } finally { a.value = false; } };
    const encomenda = async () => { const r = await api("erp.criar_de", { doctype: "Quotation", name: doc.value.name, destino: "Sales Order" }, true);
      try { sessionStorage.setItem("orbit.erp.novo", JSON.stringify(r.doc)); } catch (e) {} location.hash = irErp("Sales Order", "novo"); };
    const pdf = computed(() => doc.value && !novo.value ? `/api/method/frappe.utils.print_format.download_pdf?doctype=Quotation&name=${encodeURIComponent(doc.value.name)}&format=${encodeURIComponent("Proposta Orbit")}&no_letterhead=1` : "");
    const abrirEnvio = () => { if (sujo.value) { toast("Grave a proposta primeiro"); return; }
      const m = marcaSel.value?.name || ""; envio.value = { para: doc.value.contact_email || "", assunto: `Proposta ${doc.value.name}${m ? " — " + m : ""}`,
        mensagem: `Bom dia,\n\nEnviamos em anexo a nossa proposta ${doc.value.name}.\n\nFicamos ao dispor para qualquer esclarecimento.\n\nCom os melhores cumprimentos,` }; };
    const enviar = async () => { a.value = true; try { await apiP("versoes.enviar", { name: doc.value.name, ...envio.value }, true); toast("Proposta enviada"); envio.value = null; } finally { a.value = false; } };
    const titulo = computed(() => doc.value?.customer_name || doc.value?.party_name || "Nova proposta");
    const curtas = (l) => caractPares(l.orbit_caracteristicas).slice(0, 6);
    const nCaract = (l) => caractPares(l.orbit_caracteristicas).length;
    // 27-11-2026: todos os campos do Orçamento e da linha que este ecrã não desenha aparecem em «Todos os outros campos»
    const linhaMais = ref({});
    const NA_PROPOSTA = ["quotation_to", "party_name", "contact_person", "valid_till", "orbit_negocio", "orbit_marca", "orbit_texto_intro", "orbit_garantia",
      "orbit_pagamento", "orbit_prazo", "orbit_anexar_condicoes", "orbit_imprimir_total", "orbit_mostrar_iva", "orbit_proposta_base", "orbit_transporte_modo",
      "orbit_transporte_total", "orbit_montagem_total", "items"];
    const NA_LINHA = ["item_code", "item_name", "qty", "rate", "orbit_caracteristicas", "orbit_transporte", "orbit_montagem", "orbit_observacoes", "orbit_de"];
    return { NA_PROPOSTA, NA_LINHA, linhaMais, aSugerir, sugDe, fab, rever, eUrl, lerPagina, lerComIa, depoisDeCriar, statusPt, link, doc, novo, sujo, a, aviso, marcas, versoes, ro, linhas, docstatus, moeda, totais, marcaSel, corMarca, q, sug, procurando, acrescentar, internet, remover,
      gravar, alternativa, submeter, encomenda, pdf, envio, abrirEnvio, enviar, titulo, curtas, nCaract, abertas, irErp, ESTADO_DOC };
  },
  template: `<div v-if="doc" class="pad prop">
    <div class="sub"><a :href="irErp('Quotation')">← Propostas</a> · <a v-if="!novo" :href="irErp('Quotation', doc.name) + '/completa'">ficha completa</a></div>
    <div class="prop-topo">
      <div>
        <div class="prop-tit"><h1>{{ titulo }}</h1><span v-if="!novo" class="etq" :class="ESTADO_DOC[docstatus][1]">{{ docstatus===0 ? 'Rascunho' : (doc.status ? statusPt(doc.status) : ESTADO_DOC[docstatus][0]) }}</span><span v-if="sujo" class="etq ambar">Por gravar</span></div>
        <div class="sub" v-if="!novo">{{ doc.name }}<template v-if="doc.orbit_versao"> · versão {{ doc.orbit_versao }}</template> · {{ doc.transaction_date }}</div>
        <div v-if="versoes.length" class="prop-versoes" role="tablist" aria-label="Versões desta proposta">
          <a v-for="v in versoes" :key="v.name" role="tab" :aria-selected="v.name===doc.name" :class="{ativo: v.name===doc.name}" :href="irErp('Quotation', v.name)">{{ v.versao }} · {{ v.principal || v.name }} — {{ moeda(v.total) }}</a>
        </div>
      </div>
      <div class="prop-accoes">
        <a v-if="pdf" class="btn" :href="pdf" target="_blank">Pré-visualizar PDF</a>
        <button v-if="!ro && (novo || sujo)" class="btn prim" :disabled="a" @click="gravar">Gravar</button>
        <button v-if="!novo && !sujo && docstatus===0 && !ro" class="btn" :disabled="a" @click="submeter">Fechar proposta</button>
        <button v-if="docstatus===1" class="btn" @click="encomenda">Criar encomenda</button>
        <button v-if="!novo" class="btn prim" :disabled="a || sujo" @click="abrirEnvio">Enviar ao cliente</button>
      </div>
    </div>
    <div v-if="aviso" class="aviso">{{ aviso }}</div>
    <div class="prop-corpo">
      <div class="prop-principal">
        <section class="cartao prop-dados" aria-label="Dados da proposta">
          <div class="prop-marcas" v-if="marcas.length"><div class="sub">Marca que envia</div>
            <div class="prop-chips"><button v-for="m in marcas" :key="m.name" type="button" :disabled="ro" :class="{ativo: doc.orbit_marca===m.name}" :style="doc.orbit_marca===m.name ? {borderColor: corMarca(m)} : {}" @click="doc.orbit_marca=m.name"><span :style="{background: corMarca(m)}"></span>{{ m.name }}</button></div></div>
          <div class="prop-campos">
            <label>Proposta para<select v-model="doc.quotation_to" :disabled="ro" @change="doc.party_name=''"><option value="Customer">Empresa/Cliente</option><option value="Lead">Lead / potencial cliente</option><option v-if="doc.quotation_to==='Prospect'" value="Prospect">Potencial cliente (antigo)</option></select></label>
            <label>{{ doc.quotation_to==='Lead' ? 'Lead / potencial cliente' : doc.quotation_to==='Prospect' ? 'Potencial cliente' : 'Empresa/Cliente' }}<ClienteProcura v-if="doc.quotation_to!=='Prospect'" :key="doc.quotation_to" :modo="doc.quotation_to==='Lead' ? 'lead' : 'cliente'" v-model="doc.party_name" :ro="ro" @contacto="(c)=>{ if(!doc.contact_person) doc.contact_person=c }"/><ErpLigacao v-else v-model="doc.party_name" alvo="Prospect" :ro="ro"/></label>
            <label>Ao cuidado de<ContactoProcura v-model="doc.contact_person" :parte="doc.party_name" :tipo="doc.quotation_to" :ro="ro"/></label>
            <label>Válida até<input type="date" v-model="doc.valid_till" :disabled="ro"></label>
            <label>Negócio<ErpLigacao v-model="doc.orbit_negocio" alvo="CRM Deal" :ro="ro || !!doc.orbit_proposta_base" :filtros="JSON.stringify({status: ['not in', ['Won','Lost']]})"/><small class="sub" v-if="!doc.orbit_negocio && !ro">Vazio = nasce um negócio novo ao gravar</small><a v-else-if="doc.orbit_negocio" class="sub" :href="link('CRM Deal', doc.orbit_negocio)">Abrir o negócio</a></label>
            <div class="larga prop-intro"><span class="rotulo-campo">Introdução</span><EditorRico v-model="doc.orbit_texto_intro" :ro="ro" placeholder="Na sequência do seu pedido, apresentamos…"/></div>
          </div>
        </section>
        <ErpRestantes doctype="Quotation" :doc="doc" :ro="ro" :novo="novo" :excluir="NA_PROPOSTA"/>
        <section v-if="!ro" class="cartao prop-procura" aria-label="Adicionar produto">
          <div class="prop-procura-linha">
            <label class="cresce"><span class="so-leitor">Referência, EAN ou nome</span><input v-model="q" placeholder="Adicionar produto — referência, EAN ou nome…" autocomplete="off"></label>
            <button v-if="eUrl" type="button" class="btn prim" :disabled="procurando" @click="lerPagina">{{ procurando ? 'A ler a página…' : 'Ler o produto desta página' }}</button>
            <label v-if="!eUrl" class="prop-fab"><span class="so-leitor">Marca do produto</span><input v-model="fab" placeholder="Marca do produto (opcional)" autocomplete="off"></label>
            <button v-if="!eUrl" type="button" class="btn" :disabled="procurando" @click="internet">{{ procurando ? 'A procurar…' : 'Procurar na internet · créditos de IA' }}</button>
          </div>
          <div v-if="aSugerir && !eUrl" class="sub prop-a-procurar"><span class="roda" aria-hidden="true"></span>A procurar «{{ q.trim() }}» nos artigos…</div>
          <div v-if="sug.length" class="prop-sug">
            <button v-for="s in sug" :key="s.item_code" type="button" class="prop-sug-item" @click="acrescentar(s)">
              <span class="prop-sug-img"><img v-if="s.image" :src="s.image" alt=""></span>
              <span class="cresce"><b>{{ s.item_name }}</b><small>{{ s.item_code }}<template v-if="s.fabricante"> · {{ s.fabricante }}</template><template v-if="s.n_caracteristicas"> · {{ s.n_caracteristicas }} características</template><template v-if="s.inactivo"> · inactivo</template></small></span>
              <span v-if="s.preco" class="prop-sug-preco">{{ moeda(s.preco) }}</span>
            </button>
          </div>
          <div v-else-if="eUrl" class="sub">{{ procurando ? 'A ler a página do produto…' : 'Endereço colado: lê-se a página (sem custos) e revê-se antes de criar o artigo.' }}</div>
          <div v-else-if="aSugerir"></div>
          <div v-else-if="q.trim().length>=2" class="sub">Nada nos artigos do ERP com «{{ q }}». Pode procurar na internet ou colar o endereço da página do produto.</div>
          <div v-else class="sub">Procura nos artigos do ERP pela referência (nossa ou do fornecedor), EAN ou nome — com a imagem e as características.</div>
        </section>
        <article v-for="(l, i) in linhas" :key="l.name || i" class="cartao prop-linha" :aria-label="'Linha ' + (i+1)">
          <div class="prop-linha-corpo">
            <div class="prop-n">{{ i + 1 }}</div>
            <div class="prop-img"><img v-if="l.image" :src="l.image" :alt="l.item_name"><span v-else>Sem imagem</span></div>
            <div class="prop-info">
              <div class="prop-ref" :style="{color: corMarca(marcaSel)}">Ref. {{ l.item_code }}<span v-if="l.is_alternative" class="etq ambar" style="margin-left:6px">alternativa antiga</span></div>
              <input class="prop-nome" v-model="l.item_name" :disabled="ro" aria-label="Designação">
              <div v-if="curtas(l).length" class="prop-specs"><div v-for="c in curtas(l)" :key="c.k"><small>{{ c.k }}</small><b>{{ c.v }}</b></div></div>
              <button v-if="nCaract(l) || !ro" type="button" class="link" @click="abertas[i] = !abertas[i]">{{ abertas[i] ? 'Fechar as características' : (nCaract(l) ? 'Ver e editar as ' + nCaract(l) + ' características' : 'Acrescentar características') }}</button>
              <label v-if="abertas[i]" class="prop-caract">Uma por linha, «Nome: valor»<textarea rows="8" v-model="l.orbit_caracteristicas" :disabled="ro"></textarea></label>
            </div>
            <div class="prop-valores">
              <div class="prop-qp"><label>Qtd.<input type="number" min="0" step="any" v-model.number="l.qty" :disabled="ro"></label><label>Preço unitário<input type="number" min="0" step="0.01" v-model.number="l.rate" :disabled="ro"></label></div>
              <div class="prop-total"><b>{{ moeda(l.amount != null ? l.amount : (l.qty||0)*(l.rate||0)) }}</b><small v-if="doc.orbit_mostrar_iva">+ IVA</small></div>
            </div>
          </div>
          <div class="prop-linha-pe">
            <template v-if="(doc.orbit_transporte_modo||'Por produto')==='Por produto'">
              <label>Transporte<input type="number" min="0" step="0.01" v-model.number="l.orbit_transporte" :disabled="ro"></label>
              <label>Montagem<input type="number" min="0" step="0.01" v-model.number="l.orbit_montagem" :disabled="ro"></label>
            </template>
            <label class="cresce">Observações<input v-model="l.orbit_observacoes" :disabled="ro" placeholder="Ex.: precisa de tomada 230 V a menos de 1,5 m"></label>
            <button type="button" class="btn sm" @click="linhaMais[i] = !linhaMais[i]">{{ linhaMais[i] ? 'Menos campos' : 'Todos os campos da linha' }}</button>
            <button v-if="!novo && i===0 && !ro" type="button" class="btn sm" @click="alternativa">Criar proposta alternativa com outro produto</button>
            <button v-if="!ro" type="button" class="btn sm" @click="remover(l)">Remover</button>
          </div>
          <ErpLinhaCampos v-if="linhaMais[i]" doctype="Quotation Item" :linha="l" :parent="doc" :ro="ro" :excluir="NA_LINHA"/>
        </article>
        <div v-if="!linhas.length" class="cartao vazio">Ainda sem produtos — procure acima pela referência ou pelo nome.</div>
      </div>
      <aside class="prop-lado" aria-label="Resumo">
        <section class="cartao">
          <h2>Resumo</h2>
          <div class="prop-tot"><span>Equipamentos e serviços</span><span>{{ moeda(totais.equip) }}</span></div>
          <div class="prop-tot" v-if="totais.transporte"><span>Transporte</span><span>{{ moeda(totais.transporte) }}</span></div>
          <div class="prop-tot" v-if="totais.montagem"><span>Montagem</span><span>{{ moeda(totais.montagem) }}</span></div>
          <div class="prop-tot forte"><span>Total sem IVA</span><span>{{ moeda(totais.sem) }}</span></div>
          <div class="prop-tot"><span>IVA</span><span>{{ moeda(totais.iva) }}</span></div>
          <div class="prop-tot final"><span>Total com IVA</span><b>{{ moeda(totais.com) }}</b></div>
          <fieldset :disabled="ro"><legend class="sub">Transporte e montagem</legend>
            <div class="prop-chips"><button v-for="o in ['Por produto','No total','Não incluir']" :key="o" type="button" :class="{ativo: (doc.orbit_transporte_modo||'Por produto')===o}" @click="doc.orbit_transporte_modo=o">{{ o }}</button></div>
            <div v-if="doc.orbit_transporte_modo==='No total'" class="prop-qp" style="margin-top:8px"><label>Transporte<input type="number" min="0" step="0.01" v-model.number="doc.orbit_transporte_total"></label><label>Montagem<input type="number" min="0" step="0.01" v-model.number="doc.orbit_montagem_total"></label></div>
          </fieldset>
          <label class="prop-check"><input type="checkbox" :true-value="1" :false-value="0" v-model="doc.orbit_imprimir_total" :disabled="ro">Imprimir o total na proposta</label>
          <label class="prop-check"><input type="checkbox" :true-value="1" :false-value="0" v-model="doc.orbit_mostrar_iva" :disabled="ro">Mostrar o IVA</label>
        </section>
        <section class="cartao prop-cond">
          <h2>Condições</h2>
          <label>Garantia<input v-model="doc.orbit_garantia" :disabled="ro"></label>
          <label>Pagamento<textarea rows="2" v-model="doc.orbit_pagamento" :disabled="ro"></textarea></label>
          <label>Prazo de entrega<input v-model="doc.orbit_prazo" :disabled="ro"></label>
          <label class="prop-check"><input type="checkbox" :true-value="1" :false-value="0" v-model="doc.orbit_anexar_condicoes" :disabled="ro">Anexar as condições comerciais<template v-if="doc.orbit_marca"> da {{ doc.orbit_marca }}</template></label>
        </section>
      </aside>
    </div>
    <div v-if="envio" class="modal-fundo" @click.self="envio=null"><div class="modal" style="max-width:560px">
      <header><b>Enviar a proposta {{ doc.name }}</b><button class="btn sm" @click="envio=null">Fechar</button></header>
      <div class="prop-envio">
        <label>Para<input v-model="envio.para" placeholder="email do cliente"></label>
        <label>Assunto<input v-model="envio.assunto"></label>
        <label>Mensagem<textarea rows="7" v-model="envio.mensagem"></textarea></label>
        <div class="sub">Segue com o PDF da proposta em anexo e fica registado na cronologia do cliente.</div>
        <div style="text-align:right"><button class="btn prim" :disabled="a" @click="enviar">Enviar</button></div>
      </div>
    </div></div>
    <div style="padding:0 24px 24px"><RegistoArea v-if="name && name!=='novo'" doctype="Quotation" :name="name" :key="'ra'+name"/></div>
    <ProdutoRever v-if="rever" :p="rever" :marca="doc.orbit_marca" @fechar="rever=null" @criado="depoisDeCriar" @ia="lerComIa"/>
  </div><div v-else class="vazio">A carregar…</div>`,
};

// ── Lote 1 (25-11-2026): o que qualquer registo tem no ecrã antigo — menu «⋯», atribuir, etiquetas, partilhar,
// anexos, histórico e ligações (orbit/interface/registo.py). Registados em _app.component para servirem também a ficha do CRM.
const ROTAS_INV = Object.fromEntries(Object.entries(ROTAS_DT).map(([k, v]) => [v, k]));
const apiR = (m, a = {}, post = false) => api("registo." + m, a, post);
const tamanho = (b) => !b ? "" : b < 1024 ? b + " B" : b < 1048576 ? Math.round(b / 1024) + " KB" : (b / 1048576).toFixed(1) + " MB";
const RegistoMenu = {
  props: ["doctype", "name", "ext", "apagar", "rotaNovo"],
  emits: ["recarregar", "apagado"],
  setup(props, { emit }) {
    const aberto = ref(false), imp = ref(null), mail = ref(null), ren = ref(null), a = ref(false);
    const fechar = () => { aberto.value = false; };
    onMounted(() => document.addEventListener("click", fechar)); onUnmounted(() => document.removeEventListener("click", fechar));
    const abrirNovo = (doc) => { try { sessionStorage.setItem("orbit.erp.novo", JSON.stringify(doc)); } catch (e) {} location.hash = irErp(props.doctype, "novo"); };
    const duplicar = async () => { const r = await apiR("duplicar", { doctype: props.doctype, name: props.name }, true); abrirNovo(r.doc); };
    const corrigir = async () => { const r = await apiR("corrigir", { doctype: props.doctype, name: props.name }, true); abrirNovo(r.doc); };
    const copiar = async () => { try { await navigator.clipboard.writeText(location.href); toast("Ligação copiada"); } catch (e) { toast(location.href); } };
    const seguir = async () => { const r = await apiR("seguir", { doctype: props.doctype, name: props.name, seguir: props.ext.seguir ? 0 : 1 }, true);
      props.ext.seguir = r.seguir; toast(r.seguir ? "Passa a receber as alterações por email" : "Deixou de seguir"); };
    const abrirImp = () => { const i = props.ext.impressao; imp.value = { formato: i.padrao, cabecalho: i.cabecalho, lingua: i.lingua }; };
    const urlImp = (pdf) => { const i = imp.value; const p = new URLSearchParams({ doctype: props.doctype, name: props.name, format: i.formato,
        no_letterhead: i.cabecalho ? 0 : 1, letterhead: i.cabecalho || "", _lang: i.lingua });
      return (pdf ? "/api/method/frappe.utils.print_format.download_pdf?" : "/printview?") + p.toString(); };
    const abrirMail = async () => { const s = await apiR("email_sugestao", { doctype: props.doctype, name: props.name });
      const i = props.ext.impressao;
      mail.value = { para: s.para, cc: "", bcc: "", verCc: false, assunto: s.assunto, mensagem: "", pdf: true, formato: i.padrao, cabecalho: i.cabecalho, lingua: i.lingua, anexos: [] }; };
    const enviar = async () => { const m = mail.value; a.value = true;
      try { await apiR("enviar_email", { doctype: props.doctype, name: props.name, para: m.para, cc: m.cc, bcc: m.bcc, assunto: m.assunto, mensagem: m.mensagem,
        anexar_pdf: m.pdf ? 1 : 0, formato: m.formato, cabecalho: m.cabecalho, lingua: m.lingua, anexos: JSON.stringify(m.anexos) }, true);
        toast("Email enviado"); mail.value = null; emit("recarregar"); } finally { a.value = false; } };
    const renomear = async () => { a.value = true;
      try { const r = await apiR("renomear", { doctype: props.doctype, name: props.name, novo: ren.value.novo, juntar: ren.value.juntar ? 1 : 0 }, true);
        ren.value = null; toast("Nome mudado"); location.hash = irErp(props.doctype, r.name); } finally { a.value = false; } };
    return { aberto, imp, mail, ren, a, duplicar, corrigir, copiar, seguir, abrirImp, urlImp, abrirMail, enviar, renomear, emit };
  },
  template: `<span class="reg-menu" @click.stop>
    <button class="btn" @click="aberto=!aberto" title="Mais ações" aria-label="Mais ações">⋯</button>
    <div v-if="aberto && ext" class="cartao reg-menu-lista" @click="aberto=false">
      <button v-if="ext.pode.imprimir" @click="abrirImp">Imprimir…</button>
      <button v-if="ext.pode.email" @click="abrirMail">Enviar por email…</button>
      <button v-if="ext.pode.criar && rotaNovo !== false" @click="duplicar">Duplicar</button>
      <button v-if="ext.pode.corrigir" @click="corrigir">Corrigir (nova versão)</button>
      <button v-if="ext.pode.renomear" @click="ren={novo:name, juntar:false}">Mudar o nome…</button>
      <button @click="copiar">Copiar a ligação</button>
      <button @click="seguir">{{ ext.seguir ? 'Deixar de seguir' : 'Seguir (alterações por email)' }}</button>
      <button v-if="apagar && ext.pode.apagar" class="perigo" @click="emit('apagado')">Apagar…</button>
    </div>
    <div v-if="imp" class="modal-fundo" @click.self="imp=null"><div class="modal" style="max-width:460px">
      <header><b>Imprimir</b><button class="btn sm" @click="imp=null">Fechar</button></header>
      <div class="reg-form">
        <label class="erp-campo"><span>Formato</span><select v-model="imp.formato"><option v-for="f in ext.impressao.formatos" :key="f" :value="f">{{ f==='Standard' ? 'Padrão' : f }}</option></select></label>
        <label class="erp-campo"><span>Papel timbrado</span><select v-model="imp.cabecalho"><option value="">Sem papel timbrado</option><option v-for="c in ext.impressao.cabecalhos" :key="c" :value="c">{{ c }}</option></select></label>
        <label class="erp-campo"><span>Língua</span><select v-model="imp.lingua"><option v-for="l in ext.impressao.linguas" :key="l.v" :value="l.v">{{ l.r }}</option></select></label>
        <div class="reg-botoes"><a class="btn" :href="urlImp(false)" target="_blank">Pré-visualizar</a><a class="btn prim" :href="urlImp(true)" target="_blank">Descarregar PDF</a></div>
      </div></div></div>
    <div v-if="mail" class="modal-fundo" @click.self="mail=null"><div class="modal" style="max-width:640px">
      <header><b>Enviar por email</b><button class="btn sm" @click="mail=null">Fechar</button></header>
      <form class="reg-form" @submit.prevent="enviar">
        <label class="erp-campo"><span>Para<span class="obrig">*</span></span><input v-model="mail.para" required placeholder="email@exemplo.pt, outro@exemplo.pt"></label>
        <a v-if="!mail.verCc" href="javascript:void 0" class="sub" style="font-size:12px" @click="mail.verCc=true">+ Cc / Bcc</a>
        <template v-else><label class="erp-campo"><span>Cc</span><input v-model="mail.cc"></label><label class="erp-campo"><span>Bcc</span><input v-model="mail.bcc"></label></template>
        <label class="erp-campo"><span>Assunto</span><input v-model="mail.assunto"></label>
        <div class="erp-campo"><span>Mensagem</span><EditorRico v-model="mail.mensagem"/></div>
        <label class="chk-col"><input type="checkbox" v-model="mail.pdf"> Anexar o documento em PDF</label>
        <div v-if="mail.pdf" class="reg-linha3">
          <select v-model="mail.formato"><option v-for="f in ext.impressao.formatos" :key="f" :value="f">{{ f==='Standard' ? 'Padrão' : f }}</option></select>
          <select v-model="mail.cabecalho"><option value="">Sem papel timbrado</option><option v-for="c in ext.impressao.cabecalhos" :key="c" :value="c">{{ c }}</option></select>
          <select v-model="mail.lingua"><option v-for="l in ext.impressao.linguas" :key="l.v" :value="l.v">{{ l.r }}</option></select></div>
        <template v-if="ext.anexos.length"><span class="sub" style="font-size:12px">Anexar também:</span>
          <label v-for="x in ext.anexos" :key="x.id" class="chk-col"><input type="checkbox" :value="x.id" v-model="mail.anexos"> {{ x.nome }}</label></template>
        <div class="reg-botoes"><button type="button" class="btn" @click="mail=null">Cancelar</button><button class="btn prim" :disabled="a">{{ a ? 'A enviar…' : 'Enviar' }}</button></div>
      </form></div></div>
    <div v-if="ren" class="modal-fundo" @click.self="ren=null"><div class="modal" style="max-width:440px">
      <header><b>Mudar o nome</b><button class="btn sm" @click="ren=null">Fechar</button></header>
      <form class="reg-form" @submit.prevent="renomear"><label class="erp-campo"><span>Novo nome</span><input v-model="ren.novo" required></label>
        <label class="chk-col"><input type="checkbox" v-model="ren.juntar"> Juntar a um registo que já tenha esse nome</label>
        <div class="reg-botoes"><button class="btn prim" :disabled="a">Mudar</button></div></form></div></div>
  </span>`,
};

const RegistoLateral = {
  props: { doctype: String, name: String, ext: Object, partes: { type: Array, default: () => ["atribuir", "etiquetas", "anexos", "partilha"] } },
  emits: ["mudou"],
  setup(props, { emit }) {
    const pessoas = ref([]), escolher = ref(null), tag = ref(""), sug = ref([]), part = ref(null), a = ref(false);
    const eu = () => window.__ctx?.utilizador || window.__ctx?.email || "";
    const carregarPessoas = async () => { if (!pessoas.value.length) pessoas.value = await apiConv("pessoas"); };
    const aplicar = (r) => { Object.assign(props.ext, r); emit("mudou"); };
    const atribuir = async (lista) => { if (!lista.length) return; aplicar(await apiR("atribuir", { doctype: props.doctype, name: props.name, utilizadores: JSON.stringify(lista) }, true)); escolher.value = null; };
    const desatribuir = async (u) => aplicar(await apiR("desatribuir", { doctype: props.doctype, name: props.name, utilizador: u }, true));
    let tq; const procurarTag = () => { clearTimeout(tq); tq = setTimeout(async () => { sug.value = tag.value.trim() ? await apiR("etiquetas_sugeridas", { doctype: props.doctype, q: tag.value }) : []; }, 200); };
    const porTag = async (t, tirar) => { t = (t || "").trim(); if (!t) return; aplicar(await apiR("etiqueta", { doctype: props.doctype, name: props.name, etiqueta: t, tirar: tirar ? 1 : 0 }, true)); tag.value = ""; sug.value = []; };
    const partilhar = async () => { const p = part.value; aplicar(await apiR("partilhar", { doctype: props.doctype, name: props.name, utilizador: p.todos ? null : p.utilizador, todos: p.todos ? 1 : 0, ler: 1, escrever: p.escrever ? 1 : 0, partilhar: p.partilhar ? 1 : 0 }, true)); part.value = null; };
    const tirarPartilha = async (s) => aplicar(await apiR("partilhar", { doctype: props.doctype, name: props.name, utilizador: s.todos ? null : s.utilizador, tirar: 1 }, true));
    const entrada = ref(null);
    const carregar = async (ev) => { const fs = [...(ev.target.files || [])]; if (!fs.length) return; a.value = true;
      try { for (const f of fs) await carregarFicheiro(f, { doctype: props.doctype, docname: props.name, privado: 1 });
        aplicar(await apiR("extras", { doctype: props.doctype, name: props.name })); toast(fs.length > 1 ? fs.length + " ficheiros anexados" : "Ficheiro anexado"); }
      finally { a.value = false; ev.target.value = ""; } };
    const privado = async (x) => { props.ext.anexos = await apiR("anexo_privado", { id: x.id, privado: x.privado ? 0 : 1 }, true); };
    const tirarAnexo = async (x) => { if (!confirm(`Apagar o anexo «${x.nome}»?`)) return; props.ext.anexos = await apiR("anexo_apagar", { id: x.id }, true); emit("mudou"); };
    const largar = (ev) => { const fs = ev.dataTransfer?.files; if (fs?.length) carregar({ target: { files: fs, value: "" } }); };
    const ver = (x) => props.partes.includes(x);
    return { ver, pessoas, escolher, carregarPessoas, atribuir, desatribuir, eu, tag, sug, procurarTag, porTag, part, partilhar, tirarPartilha, entrada, carregar, privado, tirarAnexo, largar, a, data, tamanho, ini, cor };
  },
  template: `<div class="reg-lateral">
    <section v-if="ver('atribuir')"><div class="bloco-tit">Atribuído a
      <span class="sub" style="font-weight:400" v-if="ext.pode.escrever"><a href="javascript:void 0" @click="atribuir([eu()])" v-if="eu() && !ext.atribuidos.some(x=>x.utilizador===eu())">a mim</a><template v-if="eu() && !ext.atribuidos.some(x=>x.utilizador===eu())"> · </template><a href="javascript:void 0" @click="carregarPessoas(); escolher=[]">+ Atribuir</a></span></div>
      <div v-if="!ext.atribuidos.length" class="sub" style="font-size:13px">Ninguém</div>
      <div class="reg-chips"><span v-for="x in ext.atribuidos" :key="x.utilizador" class="reg-chip"><span class="av" :style="{background:cor(x.nome),width:'20px',height:'20px',fontSize:'10px'}">{{ ini(x.nome) }}</span>{{ x.nome }}<button v-if="ext.pode.escrever" @click="desatribuir(x.utilizador)" title="Tirar">×</button></span></div>
      <div v-if="escolher" class="reg-escolha cartao">
        <label v-for="p in pessoas" :key="p.email" class="chk-col"><input type="checkbox" :value="p.email" v-model="escolher" :disabled="ext.atribuidos.some(x=>x.utilizador===p.email)"> {{ p.nome }}</label>
        <div class="reg-botoes"><button class="btn sm" @click="escolher=null">Cancelar</button><button class="btn sm prim" :disabled="!escolher.length" @click="atribuir(escolher)">Atribuir</button></div></div>
    </section>
    <section v-if="ver('etiquetas')"><div class="bloco-tit">{{ ['Contact','CRM Lead','CRM Organization'].includes(doctype) ? 'Marcadores' : 'Etiquetas' }}</div>
      <div class="reg-chips"><span v-for="t in ext.etiquetas" :key="t" class="reg-chip etq">{{ t }}<button v-if="ext.pode.escrever" @click="porTag(t,true)" title="Tirar">×</button></span></div>
      <div v-if="ext.pode.escrever" class="reg-tag"><input v-model="tag" :placeholder="['Contact','CRM Lead','CRM Organization'].includes(doctype) ? '+ Marcador' : '+ Etiqueta'" @input="procurarTag" @keydown.enter.prevent="porTag(tag)">
        <div v-if="sug.length" class="cartao reg-sug"><div v-for="s in sug" :key="s" @mousedown.prevent="porTag(s)">{{ s }}</div></div></div>
    </section>
    <section v-if="ver('anexos')" @dragover.prevent @drop.prevent="largar"><div class="bloco-tit">Anexos <span class="sub" style="font-weight:400">{{ ext.anexos.length }}<template v-if="ext.pode.escrever"> · <a href="javascript:void 0" @click="entrada.click()">{{ a ? 'A carregar…' : '+ Anexar' }}</a></template></span></div>
      <input ref="entrada" type="file" multiple style="display:none" @change="carregar">
      <div v-if="!ext.anexos.length" class="sub reg-largar" style="font-size:13px">{{ ext.pode.escrever ? 'Largue aqui os ficheiros ou use «+ Anexar».' : '—' }}</div>
      <div v-for="x in ext.anexos" :key="x.id" class="reg-anexo">
        <a :href="x.url" target="_blank" :title="x.nome"><b>{{ x.nome }}</b><small class="sub">{{ tamanho(x.tamanho) }} · {{ data(x.quando,false) }}<template v-if="x.campo"> · campo da ficha</template></small></a>
        <button v-if="ext.pode.escrever" class="reg-ic" :title="x.privado ? 'Privado — só quem entra no Orbit. Tornar público' : 'Público — qualquer pessoa com a ligação. Tornar privado'" @click="privado(x)">{{ x.privado ? '🔒' : '🌐' }}</button>
        <button v-if="ext.pode.escrever" class="reg-ic" title="Apagar o anexo" @click="tirarAnexo(x)">×</button>
      </div>
    </section>
    <section v-if="ver('partilha') && (ext.pode.partilhar || ext.partilhas.length)"><div class="bloco-tit">Partilhado com <a v-if="ext.pode.partilhar" class="sub" style="font-weight:400" href="javascript:void 0" @click="carregarPessoas(); part={utilizador:'',escrever:false,partilhar:false,todos:false}">+ Partilhar</a></div>
      <div v-if="!ext.partilhas.length" class="sub" style="font-size:13px">Só quem tem acesso pelo perfil.</div>
      <div v-for="s in ext.partilhas" :key="s.utilizador||'todos'" class="reg-anexo"><span><b>{{ s.nome }}</b><small class="sub">{{ s.escrever ? 'pode alterar' : 'só ler' }}{{ s.partilhar ? ' · pode partilhar' : '' }}</small></span>
        <button v-if="ext.pode.partilhar" class="reg-ic" title="Deixar de partilhar" @click="tirarPartilha(s)">×</button></div>
      <div v-if="part" class="reg-escolha cartao">
        <label class="chk-col"><input type="checkbox" v-model="part.todos"> Toda a equipa</label>
        <select v-if="!part.todos" v-model="part.utilizador"><option value="" disabled>Pessoa…</option><option v-for="p in pessoas" :key="p.email" :value="p.email">{{ p.nome }}</option></select>
        <label class="chk-col"><input type="checkbox" v-model="part.escrever"> Pode alterar</label>
        <label class="chk-col"><input type="checkbox" v-model="part.partilhar"> Pode partilhar</label>
        <div class="reg-botoes"><button class="btn sm" @click="part=null">Cancelar</button><button class="btn sm prim" :disabled="!part.todos && !part.utilizador" @click="partilhar">Partilhar</button></div></div>
    </section>
  </div>`,
};

const RegistoHistorico = {
  props: ["doctype", "name"],
  setup(props) { const h = ref(null); onMounted(async () => { h.value = await apiR("historico", { doctype: props.doctype, name: props.name }); }); return { h, data, statusPt }; },
  template: `<div class="reg-hist"><div v-if="!h" class="carregar">A carregar…</div>
    <div v-for="(v,i) in h||[]" :key="i" class="reg-versao">
      <div class="sub" style="font-size:12px"><b style="color:var(--ink)">{{ v.quem }}</b> · {{ data(v.quando) }}</div>
      <div v-if="v.criado" style="font-size:13px">criou este registo</div>
      <div v-for="(x,k) in v.alteracoes" :key="k" class="reg-alt"><span class="campo">{{ x.campo }}</span>
        <template v-if="x.acao"> <span class="sub">{{ x.acao }}</span></template>
        <template v-else><span class="de">{{ statusPt(x.de) }}</span> → <span class="para">{{ statusPt(x.para) }}</span></template></div>
    </div></div>`,
};

const RegistoLigacoes = {
  props: ["doctype", "name"],
  setup(props) { const l = ref(null); onMounted(async () => { l.value = await apiR("ligacoes", { doctype: props.doctype, name: props.name }); });
    const ir = (dt, n) => (ROTAS_INV[dt] ? "#/" + ROTAS_INV[dt] + "/" + encodeURIComponent(n) : irErp(dt, n)); return { l, ir, data, statusPt }; },
  template: `<div class="reg-lig"><div v-if="!l" class="carregar">A carregar…</div><template v-else>
    <template v-if="l.origem.length"><div class="bloco-tit">Ligado a</div>
      <div class="reg-chips"><a v-for="o in l.origem" :key="o.doctype+o.name" class="reg-chip" :href="ir(o.doctype,o.name)"><small class="sub">{{ o.rotulo }}</small> {{ o.name }}</a></div></template>
    <div class="bloco-tit" style="margin-top:12px">Nasceu deste registo ou aponta para ele</div>
    <div v-if="!l.ligados.length" class="sub" style="font-size:13px">Nenhum documento ligado.</div>
    <details v-for="g in l.ligados" :key="g.doctype" class="reg-grupo" open><summary><b>{{ g.rotulo }}</b> <span class="sub">{{ g.n }}</span>
      <a class="sub" style="font-size:12px;margin-left:auto" :href="irErp(g.doctype)">lista →</a></summary>
      <a v-for="x in g.itens" :key="x.name" :href="ir(g.doctype,x.name)" class="reg-anexo"><span><b>{{ x.titulo }}</b><small class="sub" v-if="x.titulo!==x.name">{{ x.name }}</small></span><span class="etq" v-if="x.estado">{{ statusPt(x.estado) }}</span></a>
    </details></template></div>`,
};

// ── Lote 2 (25-11-2026): actividades do CRM como no original — tarefas, notas, chamadas, motivo de perda (orbit/interface/actividades.py)
const apiA = (m, a = {}, post = false) => api("actividades." + m, a, post);
const ESTADOS_T = [["Backlog", "Por planear"], ["Todo", "Por fazer"], ["In Progress", "Em curso"], ["Done", "Feita"], ["Canceled", "Cancelada"]];
const PRIOR_T = [["Low", "Baixa"], ["Medium", "Média"], ["High", "Alta"]];
let _perdidos = null;
async function perdidos() { if (!_perdidos) _perdidos = await apiA("motivos_perda").catch(() => ({ motivos: [], negocio: [], lead: [] })); return _perdidos; }
// Pede o motivo de perda (janela no App); devolve {motivo, notas} ou null se cancelar
function pedirMotivo(titulo) { return new Promise(async (resolve) => { const p = await perdidos(); estado.perda = { titulo, motivos: p.motivos, motivo: "", notas: "", resolve }; }); }
async function mudarEstadoCRM(doctype, name, novo) {
  const p = await perdidos(); const lista = doctype === "CRM Deal" ? p.negocio : p.lead;
  let extra = {};
  if (lista.includes(novo)) { const r = await pedirMotivo(doctype === "CRM Deal" ? "Negócio perdido" : "Lead perdida"); if (!r) return false; extra = r; }
  await apiA("marcar_estado", { doctype, name, estado: novo, motivo: extra.motivo || null, notas: extra.notas || null }, true); return true;
}
const dtLocal = (v) => v ? String(v).replace(" ", "T").slice(0, 16) : "";

const TarefaForm = {
  props: ["id", "doctype", "name", "inicial"], emits: ["fechar", "gravado"],
  setup(props, { emit }) {
    const t = ref(null), pessoas = ref([]), a = ref(false), verDesc = ref(false);
    onMounted(async () => {
      pessoas.value = await apiConv("pessoas").catch(() => []);
      if (props.id) { const r = await apiA("tarefa_obter", { id: props.id }); r.data = dtLocal(r.data); t.value = r; verDesc.value = !!r.descricao; }
      else t.value = { titulo: (props.inicial || {}).titulo || "", descricao: "", estado: "Todo", prioridade: "Medium", data: dtLocal((props.inicial || {}).data), responsavel: window.__ctx?.utilizador || "", pode_escrever: true };
    });
    const gravar = async () => { a.value = true;
      try { await apiA("tarefa_gravar", { dados: JSON.stringify({ ...t.value, doctype: props.doctype, name: props.name, data: t.value.data ? t.value.data.replace("T", " ") + ":00" : null }) }, true);
        toast(props.id ? "Tarefa gravada" : "Tarefa criada"); emit("gravado"); emit("fechar"); } finally { a.value = false; } };
    const apagar = async () => { if (!confirm("Apagar esta tarefa?")) return; await apiA("tarefa_apagar", { id: props.id }, true); toast("Tarefa apagada"); emit("gravado"); emit("fechar"); };
    return { t, pessoas, a, verDesc, gravar, apagar, ESTADOS_T, PRIOR_T };
  },
  template: `<div class="modal-fundo" @click.self="$emit('fechar')"><div class="modal" style="max-width:560px">
    <header><b>{{ id ? 'Tarefa' : 'Nova tarefa' }}</b><button class="btn sm" @click="$emit('fechar')">Fechar</button></header>
    <form v-if="t" class="reg-form" @submit.prevent="gravar">
      <label class="erp-campo"><span>Título<span class="obrig">*</span></span><input v-model="t.titulo" required autofocus :disabled="!t.pode_escrever"></label>
      <div class="reg-linha3">
        <label class="erp-campo"><span>Estado</span><select v-model="t.estado" :disabled="!t.pode_escrever"><option v-for="e in ESTADOS_T" :key="e[0]" :value="e[0]">{{ e[1] }}</option></select></label>
        <label class="erp-campo"><span>Prioridade</span><select v-model="t.prioridade" :disabled="!t.pode_escrever"><option v-for="e in PRIOR_T" :key="e[0]" :value="e[0]">{{ e[1] }}</option></select></label>
        <label class="erp-campo"><span>Responsável</span><select v-model="t.responsavel" :disabled="!t.pode_escrever"><option v-for="p in pessoas" :key="p.email" :value="p.email">{{ p.nome }}</option></select></label>
      </div>
      <label class="erp-campo"><span>Prazo (dia e hora)</span><input type="datetime-local" v-model="t.data" :disabled="!t.pode_escrever"></label>
      <a v-if="!verDesc" href="javascript:void 0" class="sub" style="font-size:12px" @click="verDesc=true">+ Descrição</a>
      <div v-else class="erp-campo"><span>Descrição</span><EditorRico v-model="t.descricao" :ro="!t.pode_escrever"/></div>
      <div class="reg-botoes"><button v-if="id && t.pode_apagar" type="button" class="btn" style="margin-right:auto" @click="apagar">Apagar</button>
        <button type="button" class="btn" @click="$emit('fechar')">Cancelar</button><button v-if="t.pode_escrever" class="btn prim" :disabled="a">{{ id ? 'Gravar' : 'Criar' }}</button></div>
    </form></div></div>`,
};

const NotaForm = {
  props: ["id", "doctype", "name"], emits: ["fechar", "gravado"],
  setup(props, { emit }) {
    const n = ref(null), a = ref(false);
    onMounted(async () => { n.value = props.id ? await apiA("nota_obter", { id: props.id }) : { titulo: "", html: "", fixada: 0, pode_escrever: true }; });
    const gravar = async () => { a.value = true;
      try { await apiA("nota_gravar", { dados: JSON.stringify({ id: props.id, doctype: props.doctype, name: props.name, titulo: n.value.titulo, html: n.value.html }) }, true);
        toast("Nota gravada"); emit("gravado"); emit("fechar"); } finally { a.value = false; } };
    const fixar = async () => { n.value = await apiA("nota_fixar", { id: props.id, fixar: n.value.fixada ? 0 : 1 }, true); toast(n.value.fixada ? "Nota fixada no topo" : "Nota solta"); emit("gravado"); };
    const apagar = async () => { if (!confirm("Apagar esta nota?")) return; await apiA("nota_apagar", { id: props.id }, true); toast("Nota apagada"); emit("gravado"); emit("fechar"); };
    return { n, a, gravar, fixar, apagar };
  },
  template: `<div class="modal-fundo" @click.self="$emit('fechar')"><div class="modal" style="max-width:640px">
    <header><b>{{ id ? 'Nota' : 'Nova nota' }}</b><span style="display:flex;gap:6px"><button v-if="id && n && n.pode_escrever" class="btn sm" @click="fixar">{{ n.fixada ? 'Soltar' : '📌 Fixar no topo' }}</button><button class="btn sm" @click="$emit('fechar')">Fechar</button></span></header>
    <form v-if="n" class="reg-form" @submit.prevent="gravar">
      <label class="erp-campo"><span>Título</span><input v-model="n.titulo" :disabled="!n.pode_escrever" placeholder="(opcional)"></label>
      <div class="erp-campo"><span>Texto</span><EditorRico v-model="n.html" :ro="!n.pode_escrever"/></div>
      <div class="reg-botoes"><button v-if="id && n.pode_apagar" type="button" class="btn" style="margin-right:auto" @click="apagar">Apagar</button>
        <button type="button" class="btn" @click="$emit('fechar')">Cancelar</button><button v-if="n.pode_escrever" class="btn prim" :disabled="a">Gravar</button></div>
    </form></div></div>`,
};

// «Registar chamada» à mão e «Como correu a chamada?» depois de «Ligar» (orbit/chamadas_crm.py)
const ChamadaForm = {
  props: ["doctype", "name", "pendente", "numero"], emits: ["fechar", "gravado"],
  setup(props, { emit }) {
    const agora = new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16);
    const c = ref({ sentido: "Outgoing", estado: props.pendente ? "atendida" : "Completed", inicio: agora, duracao: props.pendente ? 5 : 5, nota: "", tarefa: "", tarefa_data: "", numero: props.numero || "" });
    const a = ref(false);
    const gravar = async () => { a.value = true;
      try {
        if (props.pendente) await api("orbit.chamadas_crm.comentar", { nome: props.pendente, estado: c.value.estado, duracao: Math.round((Number(c.value.duracao) || 0) * 60), nota: c.value.nota, tarefa: c.value.tarefa, tarefa_data: c.value.tarefa_data }, true);
        else await apiA("chamada_registar", { doctype: props.doctype, name: props.name, sentido: c.value.sentido, estado: c.value.estado, inicio: c.value.inicio.replace("T", " ") + ":00", duracao_min: c.value.duracao, numero: c.value.numero, nota: c.value.nota }, true);
        toast("Chamada registada"); emit("gravado"); emit("fechar"); } finally { a.value = false; } };
    const naoLiguei = async () => { await api("orbit.chamadas_crm.anular", { nome: props.pendente }, true).catch(() => {}); emit("fechar"); };
    return { c, a, gravar, naoLiguei };
  },
  template: `<div class="modal-fundo"><div class="modal" style="max-width:520px">
    <header><b>{{ pendente ? 'Como correu a chamada?' : 'Registar chamada' }}</b><button v-if="!pendente" class="btn sm" @click="$emit('fechar')">Fechar</button></header>
    <form class="reg-form" @submit.prevent="gravar">
      <template v-if="pendente">
        <div class="reg-chips"><label v-for="e in [['atendida','Atendeu'],['nao_atendeu','Não atendeu'],['ocupado','Ocupado'],['numero_errado','Número errado']]" :key="e[0]" class="reg-chip" :class="{ativo: c.estado===e[0]}"><input type="radio" v-model="c.estado" :value="e[0]" style="display:none">{{ e[1] }}</label></div>
      </template>
      <template v-else>
        <div class="reg-linha3">
          <label class="erp-campo"><span>Sentido</span><select v-model="c.sentido"><option value="Outgoing">Efetuada</option><option value="Incoming">Recebida</option></select></label>
          <label class="erp-campo"><span>Resultado</span><select v-model="c.estado"><option value="Completed">Atendida</option><option value="No Answer">Não atendida</option><option value="Busy">Ocupado</option><option value="Failed">Falhou</option></select></label>
          <label class="erp-campo"><span>Número</span><input v-model="c.numero" type="tel"></label>
        </div>
        <label class="erp-campo"><span>Quando</span><input type="datetime-local" v-model="c.inicio"></label>
      </template>
      <label v-if="(pendente ? c.estado==='atendida' : c.estado==='Completed')" class="erp-campo"><span>Duração (minutos)</span><input type="number" min="0" step="1" v-model="c.duracao"></label>
      <label class="erp-campo"><span>Nota</span><textarea v-model="c.nota" rows="3" placeholder="O que se falou…"></textarea></label>
      <div v-if="pendente" class="reg-linha3" style="grid-template-columns:2fr 1fr"><label class="erp-campo"><span>Próxima tarefa</span><input v-model="c.tarefa" placeholder="(opcional)"></label><label class="erp-campo"><span>Até</span><input type="date" v-model="c.tarefa_data"></label></div>
      <div class="reg-botoes"><button v-if="pendente" type="button" class="btn" style="margin-right:auto" @click="naoLiguei">Não cheguei a ligar</button><button class="btn prim" :disabled="a">Gravar</button></div>
    </form></div></div>`,
};

const RegistoArea = {
  props: ["doctype", "name"],
  setup(props) {
    const ext = ref(null), sep = ref("conversa");
    const carregar = async () => { ext.value = await apiR("extras", { doctype: props.doctype, name: props.name }).catch(() => null); };
    onMounted(carregar);
    return { ext, sep, carregar };
  },
  template: `<div v-if="ext" class="erp-registo">
    <div class="cartao erp-registo-principal">
      <div class="vistas" style="padding:0 14px;align-items:center"><button :class="{ativo: sep==='conversa'}" @click="sep='conversa'">Comentários</button><button :class="{ativo: sep==='historico'}" @click="sep='historico'">Histórico</button><button :class="{ativo: sep==='ligacoes'}" @click="sep='ligacoes'">Ligações</button>
        <span style="margin-left:auto;flex:none"><RegistoMenu :doctype="doctype" :name="name" :ext="ext" @recarregar="carregar"/></span></div>
      <div style="padding:12px 14px">
        <ConversaRegisto v-if="sep==='conversa'" :doctype="doctype" :nome="name" :key="'c'+name"/>
        <RegistoHistorico v-else-if="sep==='historico'" :doctype="doctype" :name="name"/>
        <RegistoLigacoes v-else :doctype="doctype" :name="name"/>
      </div>
    </div>
    <aside class="cartao"><RegistoLateral :doctype="doctype" :name="name" :ext="ext"/></aside>
  </div>`,
};

const ErpFicha = {
  components: { ErpCampo, ErpTabela, ErpMulti },
  props: ["doctype", "name"],
  setup(props) {
    const meta = ref(null); const doc = ref(null); const novo = ref(false); const podeGravar = ref(true); const sujo = ref(false); const a = ref(false);
    const aba = ref(0); const fechadas = ref({}); const nomeNovo = ref(""); const criarOps = ref([]); const aviso = ref("");
    // lote 1 (25-11): anexos, atribuir, etiquetas, partilhar, histórico, ligações, «⋯», anterior/seguinte
    const ext = ref(null); const viz = ref({}); const separador = ref("conversa");
    // lote 6 (25-11): atalhos para o que está ligado a este registo (como os «Connections»/«View» do ecrã antigo)
    const ATALHOS = { Customer: [["Propostas", "Quotation", "party_name"], ["Encomendas", "Sales Order", "customer"], ["Faturas", "Sales Invoice", "customer"], ["Guias", "Delivery Note", "customer"], ["Recibos", "Payment Entry", "party"], ["Em dívida", "#/contas/receber"]],
      Supplier: [["Encomendas", "Purchase Order", "supplier"], ["Receções", "Purchase Receipt", "supplier"], ["Faturas de compra", "Purchase Invoice", "supplier"], ["Pagamentos", "Payment Entry", "party"], ["Em dívida", "#/contas/pagar"]],
      Item: [["Stock e movimentos", "#/erp-stock/"], ["Preços", "Item Price", "item_code"]],
      Employee: [["Ausências", "Leave Application", "employee"], ["Despesas", "Expense Claim", "employee"], ["Assiduidade", "Attendance", "employee"], ["Horas", "Timesheet", "employee"]],
      Project: [["Quadro e Gantt", "#/projeto/"], ["Tarefas", "Task", "project"], ["Horas", "Timesheet", "parent_project"], ["Encomendas", "Sales Order", "project"]],
      Warehouse: [["Stock", "#/erp-stock"], ["Movimentos", "Stock Ledger Entry", "warehouse"]] };
    const STOCK_DOCS = ["Stock Entry", "Delivery Note", "Purchase Receipt", "Stock Reconciliation"];
    const atalhos = computed(() => { if (!doc.value || novo.value) return []; const out = (ATALHOS[props.doctype] || []).slice();
      // lote 6: a razão a partir do documento (só submetido), como «Ver → Razão» do ecrã antigo
      if (doc.value.docstatus === 1 && (STOCK_DOCS.includes(props.doctype) || (["Sales Invoice", "Purchase Invoice"].includes(props.doctype) && doc.value.update_stock))) out.push(["Razão de stock", "rel:Stock Ledger"]);
      if (doc.value.docstatus === 1 && ["Sales Invoice", "Purchase Invoice", "Payment Entry", "Journal Entry", "Delivery Note", "Purchase Receipt", "Stock Entry"].includes(props.doctype) && window.__ctx?.contabilidade !== false) out.push(["Razão geral", "rel:General Ledger"]);
      return out; });
    const irAtalho = (a) => { if (a[1].startsWith("rel:")) { const d = doc.value; const dia = (d.posting_date || d.transaction_date || "").slice(0, 10);
        try { sessionStorage.setItem("orbit.rel.filtros", JSON.stringify({ nome: a[1].slice(4), v: { voucher_no: d.name, from_date: dia, to_date: dia, company: d.company, group_by: "Group by Voucher (Consolidated)" } })); } catch (e) {}
        location.hash = "#/erp-rel/" + encodeURIComponent(a[1].slice(4)); return; }
      if (a[1].startsWith("#")) { location.hash = a[1].endsWith("/") ? a[1] + encodeURIComponent(doc.value.name) : a[1]; return; }
      try { sessionStorage.setItem("orbit.erp.filtro", JSON.stringify({ doctype: a[1], filtros: [[a[2], "=", doc.value.name]] })); } catch (e) {} location.hash = irErp(a[1]); };
    // lote 5 (25-11): «Obter artigos de», estados (Fechar/Em espera/Reabrir/Parar), «Atualizar artigos», fluxo de aprovação
    const bt = ref({ obter: [], estados: [], atualizar_artigos: false, fluxo: null }); const obterM = ref(null); const atualM = ref(null); const menuObter = ref(false);
    const carregarBt = async () => { bt.value = await api("documentos_erp.botoes", { doctype: props.doctype, name: props.name === "novo" ? null : props.name }).catch(() => bt.value); };
    onMounted(carregarBt);
    const PARTE = { "Sales Invoice": "customer", "Delivery Note": "customer", "Sales Order": "customer", "Purchase Invoice": "supplier", "Purchase Receipt": "supplier", "Purchase Order": "supplier", "Supplier Quotation": "supplier" };
    const abrirObter = async (o) => { menuObter.value = false; const parte = doc.value[PARTE[props.doctype]] || "";
      obterM.value = { origem: o.doctype, rotulo: o.rotulo, parte, q: "", lista: null, sel: [] }; obterM.value.lista = await api("documentos_erp.candidatos", { doctype: props.doctype, origem: o.doctype, parte }); };
    const procurarObter = async () => { obterM.value.lista = await api("documentos_erp.candidatos", { doctype: props.doctype, origem: obterM.value.origem, parte: obterM.value.parte, q: obterM.value.q }); };
    const fazerObter = async () => { const r = await api("documentos_erp.obter", { doctype: props.doctype, dados: JSON.stringify(doc.value), origem: obterM.value.origem, nomes: JSON.stringify(obterM.value.sel) }, true);
      doc.value = Object.assign(doc.value, r.doc); obterM.value = null; toast("Artigos acrescentados"); };
    const mudarEstadoDoc = async (e) => { if (!confirm(e.rotulo + "?")) return; await api("documentos_erp.mudar_estado", { doctype: props.doctype, name: doc.value.name, estado: e.valor }, true); toast("Feito"); carregar(); carregarBt(); };
    const abrirAtual = () => { atualM.value = (doc.value.items || []).map((l) => ({ name: l.name, item_code: l.item_code, item_name: l.item_name, qty: l.qty, rate: l.rate, uom: l.uom, conversion_factor: l.conversion_factor,
      data: l.delivery_date || l.schedule_date || "", entregue: l.delivered_qty || l.received_qty || 0, faturado: l.billed_amt || 0 })); };
    const gravarAtual = async () => { await api("documentos_erp.atualizar_artigos", { doctype: props.doctype, name: doc.value.name, linhas: JSON.stringify(atualM.value) }, true); atualM.value = null; toast("Artigos atualizados"); carregar(); };
    const fluxo = async (x) => { if (!confirm(x.acao + " → " + x.para + "?")) return; await api("documentos_erp.aplicar_fluxo", { doctype: props.doctype, name: doc.value.name, acao: x.acao }, true); toast(x.para); carregar(); carregarBt(); };
    const carregarExt = async () => { if (props.name === "novo" || !props.name) return;
      ext.value = await apiR("extras", { doctype: props.doctype, name: props.name }).catch(() => null);
      viz.value = await apiR("vizinhos", { doctype: props.doctype, name: props.name }).catch(() => ({})); };
    const teclaS = (e) => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") { e.preventDefault(); if (!soLeitura.value && (novo.value || sujo.value) && !a.value) gravar(); } };
    onMounted(() => { window.addEventListener("keydown", teclaS); carregarExt(); }); onUnmounted(() => window.removeEventListener("keydown", teclaS));
    const carregar = async () => {
      meta.value = await metaErp(props.doctype);
      const r = await api("erp.documento", { doctype: props.doctype, name: props.name === "novo" ? undefined : props.name });
      // U3: «Criar →» deixa o documento seguinte preparado (ex.: encomenda → fatura)
      let preparado = null; try { preparado = JSON.parse(sessionStorage.getItem("orbit.erp.novo") || "null"); } catch (e) {}
      if (props.name === "novo" && preparado && preparado.doctype === props.doctype) { r.doc = Object.assign(r.doc || {}, preparado); sessionStorage.removeItem("orbit.erp.novo"); }
      doc.value = r.doc; novo.value = r.novo; podeGravar.value = r.novo ? meta.value.pode.create : r.pode_gravar; sujo.value = !!(preparado && r.novo);
      memoItens = Object.fromEntries((doc.value.items || []).map((l) => [l.name, l.item_code]));
      ultimaAss = assinatura();
      if (!r.novo && meta.value.submetivel && doc.value.docstatus === 1) criarOps.value = await api("erp.criar_opcoes", { doctype: props.doctype, name: props.name });
    };
    onMounted(carregar);
    watch(doc, (n, o) => { if (o) sujo.value = true; }, { deep: true });
    // U3: recálculo pelo ERPNext (preço da lista, nome, unidade, impostos, totais) — nada é gravado
    let memoItens = {}; let ultimaAss = ""; let tRec; let nRec = 0;
    const DERIVADOS = ["item_name", "description", "uom", "stock_uom", "conversion_factor", "rate", "price_list_rate", "base_rate", "amount", "base_amount", "image", "item_group", "brand"];
    // o que, ao mudar, pede um novo cálculo ao ERPNext (vendas/compras, stock e RH — U3/U4)
    const CAB = ["customer", "party_name", "supplier", "company", "currency", "selling_price_list", "buying_price_list", "taxes_and_charges",
      "transaction_date", "posting_date", "posting_time", "additional_discount_percentage", "discount_amount", "apply_discount_on",
      "stock_entry_type", "purpose", "from_warehouse", "to_warehouse", "employee", "leave_type", "from_date", "to_date", "half_day", "half_day_date"];
    const LIN = { items: ["item_code", "qty", "rate", "uom", "discount_percentage", "warehouse", "s_warehouse", "t_warehouse", "basic_rate", "valuation_rate"],
      taxes: ["charge_type", "account_head", "rate", "tax_amount"], time_logs: ["activity_type", "from_time", "to_time", "hours", "billing_rate", "costing_rate", "is_billable", "project", "task"],
      expenses: ["expense_type", "amount", "sanctioned_amount"] };
    const assinatura = () => { const d = doc.value; if (!d || !meta.value?.transacao) return "";
      return JSON.stringify([CAB.map((k) => d[k]), Object.entries(LIN).map(([t, ks]) => (d[t] || []).map((l) => ks.map((k) => l[k])))]); };
    const recalcular = async () => {
      const d = doc.value; if (!d || soLeitura.value || (d.docstatus || 0) !== 0) return;
      for (const l of d.items || []) if (l.item_code && memoItens[l.name] !== l.item_code) { for (const k of DERIVADOS) l[k] = null; }
      const n = ++nRec; const enviado = JSON.parse(JSON.stringify(d));
      const r = await api("erp.recalcular", { doctype: props.doctype, dados: JSON.stringify(enviado) }, true).catch(() => null);
      if (!r || n !== nRec) return;
      aviso.value = r.aviso || "";
      if (!r.doc) return;
      juntarRecalculo(doc.value, r.doc, enviado);
      memoItens = Object.fromEntries((doc.value.items || []).map((l) => [l.name, l.item_code])); ultimaAss = assinatura();
    };
    watch(() => assinatura(), (a) => { if (!meta.value?.transacao || a === ultimaAss) return; ultimaAss = a; clearTimeout(tRec); tRec = setTimeout(recalcular, 500); });
    const criarDe = async (o) => {
      // lote 5: pagamento de uma fatura de venda abre o recibo; o resto abre o documento preparado
      if (o.chave === "pe" && ["Sales Invoice", "Sales Order"].includes(props.doctype)) { try { sessionStorage.setItem("orbit.recibo", JSON.stringify({ cliente: doc.value.customer, fatura: props.doctype === "Sales Invoice" ? doc.value.name : null })); } catch (e) {} location.hash = irErp("Payment Entry", "novo"); return; }
      const r = await api("erp.criar_de", { doctype: props.doctype, name: doc.value.name, destino: o.chave || o.doctype }, true);
      try { sessionStorage.setItem("orbit.erp.novo", JSON.stringify(r.doc)); } catch (e) {}
      if (o.doctype === "Payment Entry") { location.hash = irErp("Payment Entry", "novo") + "/completa"; return; }
      location.hash = irErp(o.doctype, "novo");
    };
    const moeda = (v) => new Intl.NumberFormat("pt-PT", { style: "currency", currency: doc.value?.currency || "EUR" }).format(v || 0);
    const pdf = computed(() => doc.value && !novo.value ? `/api/method/frappe.utils.print_format.download_pdf?doctype=${encodeURIComponent(props.doctype)}&name=${encodeURIComponent(doc.value.name)}` : "");
    const abas = computed(() => {
      if (!meta.value) return [];
      const out = []; let ab = { label: "Detalhes", secoes: [], implicita: true }; let sec = null; let col = null;
      const novaSec = (c) => { sec = { label: c?.label || "", collapsible: c?.collapsible, depends_on: c?.depends_on, colunas: [] }; col = []; sec.colunas.push(col); ab.secoes.push(sec); };
      for (const c of meta.value.campos) {
        if (c.fieldtype === "Tab Break") {
          if ((c.label || "Detalhes") === ab.label && !c.depends_on) { sec = null; continue; }   // separador com o mesmo nome: é o mesmo (campos acrescentados antes do 1.º)
          if (ab.secoes.some((s) => s.colunas.some((x) => x.length))) out.push(ab); ab = { label: c.label || "Detalhes", secoes: [], depends_on: c.depends_on }; sec = null; continue; }
        if (c.fieldtype === "Section Break") { novaSec(c); continue; }
        if (c.fieldtype === "Column Break") { if (!sec) novaSec(null); col = []; sec.colunas.push(col); continue; }
        if (!sec) novaSec(null);
        col.push(c);
      }
      if (ab.secoes.some((s) => s.colunas.some((x) => x.length))) out.push(ab);
      // campos soltos antes do 1.º separador (acrescentados pelo Orbit): vão para o fim do separador com o mesmo nome
      if (out[0]?.implicita) { const i = out.findIndex((t, k) => k > 0 && t.label === out[0].label); if (i > 0) { out[i].secoes.push(...out[0].secoes); out.shift(); } }
      return out;
    });
    const docstatus = computed(() => doc.value?.docstatus || 0);
    // Marketing: campanha/automação só se editam em rascunho (como o script do ecrã antigo)
    const MKT = ["Campanha de Marketing", "Automacao de Marketing"];
    const soLeitura = computed(() => !podeGravar.value || docstatus.value === 2 || (MKT.includes(props.doctype) && !novo.value && doc.value && doc.value.estado && doc.value.estado !== "Rascunho"));
    const roCampo = (c) => soLeitura.value || c.read_only || (docstatus.value === 1 && !c.allow_on_submit) || (c.read_only_depends_on && avaliar(c.read_only_depends_on, doc.value));
    const obrig = (c) => c.reqd || (c.mandatory_depends_on && avaliar(c.mandatory_depends_on, doc.value));
    const visivel = (c) => {
      if (c.hidden || !avaliar(c.depends_on, doc.value)) return false;
      if (c.fieldtype === "HTML") return !!c.options;   // HTML preenchido só pelo script do ecrã antigo: nada a mostrar
      if (c.fieldtype === "Image") return !!doc.value[c.options];
      if (SEM_VALOR.includes(c.fieldtype) || FILHAS.includes(c.fieldtype)) return true;
      if (roCampo(c) && !novo.value && vazioV(doc.value[c.fieldname])) return false;   // como no ERPNext: só-leitura vazio não aparece
      return true;
    };
    const secVisivel = (s) => avaliar(s.depends_on, doc.value) && s.colunas.some((col) => col.some(visivel));
    const abaVisivel = (t) => avaliar(t.depends_on, doc.value) && t.secoes.some(secVisivel);
    // 25-11-2026: separadores e secções escondidos por uma condição que a pessoa pode mudar na ficha (ex.: «Ativar
    // receção» na Conta de e-mail) já não desaparecem sem aviso — mostram-se apagados, a dizer o que os abre.
    const temCampos = (s) => s.colunas.some((col) => col.some((c) => !c.hidden));
    const condTexto = (expr) => {
      if (!expr || !meta.value) return "";
      const nomes = expr.startsWith("eval:") ? [...new Set([...expr.matchAll(/doc\.(\w+)/g)].map((m) => m[1]))] : [expr];
      const cs = nomes.map((n) => meta.value.campos.find((c) => c.fieldname === n));
      if (!cs.length || cs.some((c) => !c || c.hidden || roCampo(c) || !["Check", "Select"].includes(c.fieldtype) || !visivel(c))) return "";
      const rot = cs.map((c) => "«" + c.label + "»").join(", ");
      return cs.length === 1 && cs[0].fieldtype === "Check" && !/!/.test(expr.replace(/!=/g, "")) ? "Aparece com " + rot + " ligado" : "Depende de " + rot;
    };
    const abasBarra = computed(() => abas.value.filter((t) => abaVisivel(t) || (t.secoes.some(temCampos) && !avaliar(t.depends_on, doc.value) && condTexto(t.depends_on))));
    const abasVis = abasBarra;
    const secEscondida = (s) => s.label && temCampos(s) && !avaliar(s.depends_on, doc.value) && condTexto(s.depends_on);
    const escolherAba = (t, i) => { if (abaVisivel(t)) aba.value = i; else toast(condTexto(t.depends_on) + "."); };
    watch(abasBarra, (l) => { if (!l[aba.value] || !abaVisivel(l[aba.value])) aba.value = Math.max(0, l.findIndex(abaVisivel)); });
    // Botões: correm no script do ecrã antigo — abre-se o mesmo registo lá, dentro do Orbit
    const botao = (c) => {
      if (novo.value || sujo.value) { toast("Grave primeiro e depois use «" + c.label + "»."); return; }
      location.hash = "#/erp-desk/" + encodeURIComponent(meta.value.desk + (meta.value.single ? "" : "/" + encodeURIComponent(doc.value.name)));
    };
    // Comportamentos do ecrã antigo que a ficha genérica repete (o script de cada tipo não corre aqui)
    const COMPORT = {
      "Email Account": {
        service: async (x) => { if (!x) return; Object.assign(doc.value, await api("orbit.correio_servicos.valores", { service: x, use_imap: doc.value.use_imap ? 1 : 0 })); },
        use_imap: async (x) => { if (!doc.value.service) return; Object.assign(doc.value, await api("orbit.correio_servicos.valores", { service: doc.value.service, use_imap: x ? 1 : 0 })); },
        domain: async (x) => { if (!x) return; Object.assign(doc.value, await api("orbit.correio_servicos.valores_dominio", { domain: x })); },
      },
    };
    for (const [campo, fn] of Object.entries(COMPORT[props.doctype] || {})) {
      watch(() => doc.value?.[campo], (n, o) => { if (o !== undefined && n !== o) fn(n); });
    }
    const tituloDoc = computed(() => { const t = meta.value?.titulo; if (meta.value?.single) return meta.value.rotulo; return tr(props.doctype, (t && doc.value?.[t]) || (novo.value ? "Novo — " + meta.value?.rotulo : doc.value?.name)); });
    const precisaNome = computed(() => novo.value && meta.value && (!meta.value.nomeacao || meta.value.nomeacao.toLowerCase() === "prompt"));
    const gravar = async () => {
      const falta = meta.value.campos.filter((c) => !ESTRUTURA.includes(c.fieldtype) && !SEM_VALOR.includes(c.fieldtype) && visivel(c) && obrig(c) && vazioV(doc.value[c.fieldname]));
      if (falta.length) { toast("Falta preencher: " + falta.map((c) => c.label).join(", ")); return; }
      a.value = true;
      try {
        const dados = { ...doc.value }; if (precisaNome.value) dados.__nome = nomeNovo.value;
        const r = await api("erp.gravar", { doctype: props.doctype, dados: JSON.stringify(dados) }, true);
        toast("Gravado");
        if (novo.value || r.doc.name !== props.name) { location.hash = irErp(props.doctype, r.doc.name); return; }
        doc.value = r.doc; await nextTick(); sujo.value = false;
      } finally { a.value = false; }
    };
    const accao = async (m, pergunta) => {
      if (pergunta && !confirm(pergunta)) return;
      a.value = true;
      try { const r = await api("erp." + m, { doctype: props.doctype, name: doc.value.name }, true);
        if (m === "apagar") { toast("Apagado"); location.hash = irErp(props.doctype); return; }
        carregarBt(); carregarExt(); doc.value = r.doc; await nextTick(); sujo.value = false; toast(m === "submeter" ? "Submetido" : "Cancelado");
      } finally { a.value = false; }
    };
    const aberta = (s, i) => !(s.collapsible && !fechadas.value[i + ":" + s.label]);
    const alternar = (s, i) => { fechadas.value[i + ":" + s.label] = !fechadas.value[i + ":" + s.label]; };
    return { atalhos, irAtalho, bt, obterM, atualM, menuObter, abrirObter, procurarObter, fazerObter, mudarEstadoDoc, abrirAtual, gravarAtual, fluxo, ext, viz, separador, carregarExt, statusPt, meta, doc, novo, sujo, a, aba, abasVis, abasBarra, abaVisivel, escolherAba, condTexto, secEscondida, botao, visivel, roCampo, obrig, secVisivel, tituloDoc, gravar, accao, docstatus, soLeitura, aberta, alternar, ESTADO_DOC, irErp, precisaNome, nomeNovo, cor, ini, criarOps, criarDe, moeda, pdf, aviso, tr };
  },
  template: `<div v-if="meta && doc" class="erp-ficha">
    <div class="erp-topo">
      <div class="erp-nav" v-if="!meta.single"><a class="sub" :href="irErp(doctype)">← {{ meta.rotulo }}</a>
        <span v-if="!novo" class="erp-viz"><a v-if="viz.anterior" :href="irErp(doctype, viz.anterior)" title="Anterior na lista" class="btn sm">‹</a><a v-if="viz.seguinte" :href="irErp(doctype, viz.seguinte)" title="Seguinte na lista" class="btn sm">›</a></span></div>
      <div class="erp-tit"><span class="av" :style="{background:cor(doc.name||'n')}">{{ ini(tituloDoc) }}</span>
        <div class="cresce"><h1>{{ tituloDoc }}</h1><div class="sub">{{ meta.rotulo }}<span v-if="!novo && !meta.single && tituloDoc!==tr(doctype, doc.name)"> · {{ tr(doctype, doc.name) }}</span></div></div>
        <span v-if="meta.submetivel && !novo" class="etq" :class="ESTADO_DOC[docstatus][1]">{{ doc.status ? statusPt(doc.status) : ESTADO_DOC[docstatus][0] }}</span>
        <span v-if="sujo" class="etq ambar">Por gravar</span>
        <span v-if="bt.fluxo && bt.fluxo.estado" class="etq azul" title="Estado do fluxo de aprovação">{{ bt.fluxo.estado }}</span>
        <div class="erp-accoes">
          <button v-if="!soLeitura && (novo || sujo)" class="btn prim" :disabled="a" @click="gravar">Gravar</button>
          <button v-if="meta.pode.submit && docstatus===0 && !novo && !sujo" class="btn" :disabled="a" @click="accao('submeter', ['Sales Invoice','Purchase Invoice'].includes(doctype) ? 'Submeter esta fatura? O documento fiscal certificado é emitido pelo programa de faturação ligado (o Orbit nunca o emite). Depois de submetida só se altera cancelando.' : 'Submeter este documento? Depois de submetido só se altera cancelando.')">Submeter</button>
          <button v-if="meta.pode.cancel && docstatus===1" class="btn" :disabled="a" @click="accao('cancelar','Cancelar este documento?')">Cancelar</button>
          <button v-if="meta.pode.delete && !novo && docstatus!==1 && !meta.single" class="btn" :disabled="a" @click="accao('apagar','Apagar definitivamente este registo?')">Apagar</button>
          <a v-if="meta.transacao && pdf" class="btn" :href="pdf" target="_blank">PDF</a>
          <button v-for="o in criarOps" :key="o.chave||o.doctype" class="btn" :disabled="a" @click="criarDe(o)">{{ o.rotulo }} →</button>
          <span v-if="bt.obter.length && docstatus===0 && !soLeitura" class="reg-menu" @click.stop><button class="btn" @click="menuObter=!menuObter">Obter artigos de ▾</button>
            <div v-if="menuObter" class="cartao reg-menu-lista"><button v-for="o in bt.obter" :key="o.doctype" @click="abrirObter(o)">{{ o.rotulo }}</button></div></span>
          <button v-if="bt.atualizar_artigos" class="btn" @click="abrirAtual">Atualizar artigos</button>
          <button v-for="e in bt.estados" :key="e.valor" class="btn" @click="mudarEstadoDoc(e)">{{ e.rotulo }}</button>
          <button v-for="x in (bt.fluxo && bt.fluxo.acoes) || []" :key="x.acao" class="btn prim" @click="fluxo(x)">{{ x.acao }}</button>
          <RegistoMenu v-if="ext && !novo && !meta.single" :doctype="doctype" :name="doc.name" :ext="ext" @recarregar="carregarExt"/>
        </div>
      </div>
      <div v-if="meta.transacao && doc.grand_total !== undefined" class="erp-totais cartao">
        <div><small>Total sem impostos</small><b>{{ moeda(doc.net_total) }}</b></div>
        <div><small>Impostos</small><b>{{ moeda(doc.total_taxes_and_charges) }}</b></div>
        <div v-if="doc.discount_amount"><small>Desconto</small><b>− {{ moeda(doc.discount_amount) }}</b></div>
        <div class="total"><small>Total</small><b>{{ moeda(doc.rounded_total || doc.grand_total) }}</b></div>
        <div v-if="docstatus===1 && doc.outstanding_amount !== undefined"><small>Em dívida</small><b>{{ moeda(doc.outstanding_amount) }}</b></div>
      </div>
      <MktCiclo v-if="['Campanha de Marketing','Automacao de Marketing'].includes(doctype) && !novo" :doctype="doctype" :doc="doc" :key="'mc'+doc.modified" @recarregar="carregar"/>
      <div v-if="atalhos.length" class="erp-atalhos"><button v-for="x in atalhos" :key="x[0]" class="reg-chip" @click="irAtalho(x)">{{ x[0] }} →</button></div>
      <div v-if="aviso" class="aviso" style="margin-top:8px">{{ aviso }}</div>
      <div v-if="precisaNome" class="erp-campo" style="max-width:420px;margin-top:10px"><label>Nome do registo<span class="obrig">*</span></label><input v-model="nomeNovo"></div>
      <div class="vistas" v-if="abasBarra.length>1" style="padding:12px 0 0"><button v-for="(t,i) in abasBarra" :key="t.label+i" :class="{ativo: aba===i, inativo: !abaVisivel(t)}" :title="abaVisivel(t) ? '' : condTexto(t.depends_on)" @click="escolherAba(t,i)">{{ t.label }}</button></div>
    </div>
    <div class="erp-corpo" v-if="abasVis[aba] && abaVisivel(abasVis[aba])">
      <template v-for="(s,si) in abasVis[aba].secoes" :key="si">
        <section v-if="!secVisivel(s) && secEscondida(s)" class="cartao erp-sec erp-sec-oculta"><header><b>{{ s.label }}</b><span class="sub">{{ condTexto(s.depends_on) }}</span></header></section>
        <section v-if="secVisivel(s)" class="cartao erp-sec">
          <header v-if="s.label" @click="s.collapsible && alternar(s,si)" :style="{cursor: s.collapsible?'pointer':'default'}"><b>{{ s.label }}</b><span v-if="s.collapsible" class="sub">{{ aberta(s,si) ? '▾' : '▸' }}</span></header>
          <div v-show="aberta(s,si)" class="erp-cols" :style="{gridTemplateColumns: 'repeat(' + s.colunas.filter(c=>c.some(visivel)).length + ', minmax(0,1fr))'}">
            <div v-for="(col,ci) in s.colunas.filter(c=>c.some(visivel))" :key="ci">
              <template v-for="c in col" :key="c.fieldname">
                <div v-if="visivel(c)" class="erp-campo" :class="{largo: c.fieldtype==='Table'}">
                  <label v-if="!['Check','Button','Heading','HTML'].includes(c.fieldtype)">{{ c.label }}<span v-if="obrig(c)" class="obrig">*</span></label>
                  <ErpTabela v-if="c.fieldtype==='Table'" :c="c" :doc="doc" :filha="meta.filhas[c.options]" :ro="roCampo(c)"/>
                  <ErpMulti v-else-if="c.fieldtype==='Table MultiSelect'" :c="c" :doc="doc" :filha="meta.filhas[c.options]" :ro="roCampo(c)"/>
                  <ErpCampo v-else :c="c" :doc="doc" :ro="roCampo(c)" :botao="botao" :doctype="doctype"/>
                  <small v-if="c.descricao" class="sub">{{ c.descricao }}</small>
                </div>
              </template>
            </div>
          </div>
        </section>
      </template>
    </div>
    <div class="erp-corpo" v-if="doctype==='Campanha de Marketing'"><MktComoFica :doc="doc"/></div>
    <div class="erp-corpo" v-if="doctype==='Definicoes de Marketing'"><MktBaseLegal/></div>
    <div v-if="ext && !novo && !meta.single" class="erp-registo">
      <div class="cartao erp-registo-principal">
        <div class="vistas" style="padding:0 14px"><button :class="{ativo: separador==='conversa'}" @click="separador='conversa'">Comentários</button><button :class="{ativo: separador==='historico'}" @click="separador='historico'">Histórico</button><button :class="{ativo: separador==='ligacoes'}" @click="separador='ligacoes'">Ligações</button></div>
        <div style="padding:12px 14px">
          <ConversaRegisto v-if="separador==='conversa'" :doctype="doctype" :nome="doc.name" :key="'c'+doc.name"/>
          <RegistoHistorico v-else-if="separador==='historico'" :doctype="doctype" :name="doc.name" :key="'h'+doc.modified"/>
          <RegistoLigacoes v-else :doctype="doctype" :name="doc.name" :key="'l'+doc.name"/>
        </div>
      </div>
      <aside class="cartao"><RegistoLateral :doctype="doctype" :name="doc.name" :ext="ext"/></aside>
    </div>
    <div v-if="obterM" class="modal-fundo" @click.self="obterM=null"><div class="modal" style="max-width:640px"><header><b>Obter artigos de: {{ obterM.rotulo }}</b><button class="btn sm" @click="obterM=null">Fechar</button></header>
      <div class="reg-form"><div style="display:flex;gap:8px"><input v-model="obterM.q" placeholder="Procurar n.º ou nome…" @keyup.enter="procurarObter" style="flex:1"><button class="btn" @click="procurarObter">Procurar</button></div>
        <div v-if="obterM.parte" class="sub" style="font-size:12px">Só os de {{ obterM.parte }} <a href="javascript:void 0" @click="obterM.parte=''; procurarObter()">· ver de todos</a></div>
        <div v-if="!obterM.lista" class="carregar">A carregar…</div><div v-else-if="!obterM.lista.length" class="vazio">Nada por faturar/entregar.</div>
        <label v-for="x in obterM.lista||[]" :key="x.name" class="chk-col reg-anexo"><input type="checkbox" :value="x.name" v-model="obterM.sel"> <span><b>{{ x.name }}</b><small class="sub">{{ [x.parte, x.data, x.total ? x.total.toFixed(2)+' €' : '', statusPt(x.estado)].filter(Boolean).join(' · ') }}</small></span></label>
        <div class="reg-botoes"><button class="btn prim" :disabled="!obterM.sel.length" @click="fazerObter">Acrescentar os artigos</button></div></div></div></div>
    <div v-if="atualM" class="modal-fundo" @click.self="atualM=null"><div class="modal" style="max-width:760px"><header><b>Atualizar artigos</b><button class="btn sm" @click="atualM=null">Fechar</button></header>
      <div class="reg-form"><div class="tabela-wrap" style="margin:0"><table><thead><tr><th>Artigo</th><th>Quantidade</th><th>Preço</th><th>Data</th></tr></thead>
        <tbody><tr v-for="l in atualM" :key="l.name" style="cursor:default"><td style="white-space:normal">{{ l.item_name || l.item_code }}<small v-if="l.entregue" class="sub"> · {{ l.entregue }} já entregue/recebida</small></td>
          <td><input type="number" step="any" v-model.number="l.qty" style="width:90px"></td><td><input type="number" step="any" v-model.number="l.rate" style="width:100px"></td><td><input type="date" v-model="l.data"></td></tr></tbody></table></div>
        <p class="sub" style="font-size:12px;margin:0">O ERPNext não deixa baixar abaixo do que já foi entregue, recebido ou faturado.</p>
        <div class="reg-botoes"><button class="btn prim" @click="gravarAtual">Atualizar</button></div></div></div></div>
  </div><div v-else class="vazio">A carregar…</div>`,
};

const ErpStock = {
  components: { ErpLigacao },
  props: ["artigo"],
  setup(props) {
    const escolhido = ref(props.artigo || ""); const r = ref(null); const resumo = ref([]); const a = ref(false);
    const carregar = async () => {
      if (!escolhido.value) { resumo.value = await api("erp.stock_resumo"); r.value = null; return; }
      a.value = true; try { r.value = await api("erp.stock_artigo", { item_code: escolhido.value }); } finally { a.value = false; }
    };
    onMounted(carregar);
    watch(escolhido, (v) => { const alvo = "#/erp-stock" + (v ? "/" + encodeURIComponent(v) : ""); if (location.hash !== alvo) location.hash = alvo; });
    const num = (v) => new Intl.NumberFormat("pt-PT", { maximumFractionDigits: 2 }).format(v || 0);
    const eur2 = (v) => new Intl.NumberFormat("pt-PT", { style: "currency", currency: "EUR" }).format(v || 0);
    const abrir = (m) => { location.hash = irErp(m.voucher_type, m.voucher_no); };
    return { escolhido, r, resumo, a, num, eur2, irErp, data, abrir };
  },
  template: `<div class="pad">
    <div style="display:flex;justify-content:space-between;align-items:flex-end;gap:12px;flex-wrap:wrap;margin-bottom:16px">
      <div><h1>Stock</h1><div class="sub">Por artigo: armazéns, movimentos e stock dos fornecedores</div></div>
      <div class="erp-campo" style="min-width:320px;margin:0"><label>Artigo</label><ErpLigacao v-model="escolhido" alvo="Item"/></div>
    </div>
    <template v-if="r">
      <div class="erp-totais cartao" style="margin:0 0 16px">
        <div><small>Artigo</small><b><a :href="irErp('Item', r.artigo.item_code)">{{ r.artigo.item_name }}</a></b></div>
        <div><small>Em armazém</small><b>{{ num(r.total) }} {{ r.artigo.stock_uom }}</b></div>
        <div><small>Valor</small><b>{{ eur2(r.valor) }}</b></div>
      </div>
      <div class="cartao" style="margin-bottom:16px"><header><b>Por armazém</b></header>
        <div class="tabela-wrap" style="margin:0;border:0"><table><thead><tr><th>Armazém</th><th>Em stock</th><th>Reservado</th><th>Encomendado</th><th>Previsto</th><th>Valor</th></tr></thead>
          <tbody><tr v-for="b in r.armazens" :key="b.warehouse" style="cursor:default"><td>{{ b.warehouse }}</td><td>{{ num(b.actual_qty) }}</td><td>{{ num(b.reserved_qty) }}</td><td>{{ num(b.ordered_qty) }}</td><td>{{ num(b.projected_qty) }}</td><td>{{ eur2(b.stock_value) }}</td></tr></tbody></table>
          <div v-if="!r.armazens.length" class="vazio">Sem stock próprio em nenhum armazém.</div></div></div>
      <div class="cartao" style="margin-bottom:16px" v-if="r.ofertas.length"><header><b>Armazéns dos fornecedores</b><span class="sub">virtuais — não contabilizados, vêm do importador</span></header>
        <div class="tabela-wrap" style="margin:0;border:0"><table><thead><tr><th>Armazém</th><th>Estado</th><th>Quantidade</th><th>Custo</th><th>Lido em</th></tr></thead>
          <tbody><tr v-for="o in r.ofertas" :key="o.supplier" style="cursor:default"><td>{{ o.armazem || o.supplier }}</td><td><span class="etq" :class="{verde:o.estado_stock==='Em stock', ambar:o.estado_stock==='Sob encomenda'}">{{ o.ausente_desde ? 'Fora do fornecedor' : (o.estado_stock || '—') }}</span></td><td>{{ o.quantidade_conhecida ? num(o.quantidade) : '—' }}</td><td>{{ eur2(o.custo) }}</td><td>{{ data(o.lida_em) }}</td></tr></tbody></table></div></div>
      <div class="cartao"><header><b>Últimos movimentos</b></header>
        <div class="tabela-wrap" style="margin:0;border:0"><table><thead><tr><th>Data</th><th>Documento</th><th>Armazém</th><th>Quantidade</th><th>Fica</th></tr></thead>
          <tbody><tr v-for="m in r.movimentos" :key="m.voucher_no+m.warehouse+m.actual_qty" @click="abrir(m)"><td>{{ data(m.posting_date, false) }}</td><td>{{ m.voucher_rotulo }} {{ m.voucher_no }}</td><td>{{ m.warehouse }}</td><td :style="{color: m.actual_qty<0?'var(--acao)':'inherit'}">{{ m.actual_qty>0?'+':'' }}{{ num(m.actual_qty) }}</td><td>{{ num(m.qty_after_transaction) }}</td></tr></tbody></table>
          <div v-if="!r.movimentos.length" class="vazio">Sem movimentos.</div></div></div>
    </template>
    <div v-else-if="!a" class="cartao"><header><b>Stock por armazém</b><span class="sub">escolha um artigo para ver o detalhe</span></header>
      <div class="tabela-wrap" style="margin:0;border:0"><table><thead><tr><th>Armazém</th><th>Artigos com stock</th><th>Valor</th></tr></thead>
        <tbody><tr v-for="w in resumo" :key="w.warehouse" style="cursor:default"><td>{{ w.warehouse }}</td><td>{{ num(w.artigos) }}</td><td>{{ eur2(w.valor) }}</td></tr></tbody></table>
        <div v-if="!resumo.length" class="vazio">Ainda não há stock próprio registado (inventário inicial por fazer).</div></div></div>
  </div>`,
};

const ErpPessoas = {
  setup() {
    const r = ref(null); const q = ref("");
    onMounted(async () => { r.value = await api("erp.pessoas"); });
    const lista = computed(() => (r.value?.equipa || []).filter((p) => !q.value || (p.employee_name + " " + (p.designacao || "") + " " + (p.department || "")).toLowerCase().includes(q.value.toLowerCase())));
    return { r, q, lista, irErp, cor, ini, data };
  },
  template: `<div class="pad" v-if="r">
    <div style="display:flex;justify-content:space-between;align-items:flex-end;gap:12px;flex-wrap:wrap;margin-bottom:16px">
      <div><h1>Pessoas</h1><div class="sub">Equipa, ausências de hoje e o seu saldo de férias</div></div>
      <div style="display:flex;gap:8px;flex-wrap:wrap"><a class="btn" :href="irErp('Leave Application','novo')">Pedir férias / ausência</a><a class="btn" :href="irErp('Expense Claim','novo')">Nova despesa</a><a class="btn" :href="irErp('Timesheet','novo')">Nova folha de horas</a></div>
    </div>
    <div v-if="r.sem_rh" class="vazio cartao">O módulo de Recursos Humanos não está disponível para si.</div>
    <template v-else>
      <div class="erp-mod" style="margin-bottom:16px">
        <section class="cartao"><header><b>Ausentes hoje</b></header>
          <div class="erp-itens"><a v-for="a in r.ausentes_hoje" :key="a.employee+a.from_date" :href="irErp('Employee', a.employee)">{{ a.employee_name }}<span class="sub">{{ a.tipo }} · até {{ data(a.to_date, false) }}</span></a>
            <div v-if="!r.ausentes_hoje.length" class="vazio" style="padding:12px">Ninguém ausente hoje.</div></div></section>
        <section class="cartao"><header><b>O meu saldo</b></header>
          <div class="erp-itens"><div v-for="s in r.saldo" :key="s.tipo" style="padding:8px 16px;display:flex;justify-content:space-between"><span>{{ s.tipo }}</span><b>{{ s.restam }} dias</b></div>
            <div v-if="!r.saldo.length" class="vazio" style="padding:12px">{{ r.eu ? 'Sem dias atribuídos.' : 'A sua conta não está ligada a uma ficha de colaborador.' }}</div></div></section>
      </div>
      <div class="filtros" style="padding:0 0 12px"><input class="filtro" style="border-style:solid;min-width:260px" v-model="q" placeholder="Procurar na equipa…"></div>
      <div class="erp-pessoas">
        <a v-for="p in lista" :key="p.name" class="cartao" :href="irErp('Employee', p.name)">
          <span class="av" :style="{background:cor(p.name)}">{{ ini(p.employee_name) }}</span>
          <div class="cresce"><b>{{ p.employee_name }}</b><small>{{ [p.designacao, p.department].filter(Boolean).join(' · ') }}</small><small>{{ p.company_email || '' }} {{ p.cell_number || '' }}</small></div>
        </a>
      </div>
      <div v-if="!lista.length" class="vazio cartao">Ainda não há fichas de colaboradores.</div>
    </template>
  </div><div v-else class="vazio">A carregar…</div>`,
};

// U5: os filtros de cada relatório estão no script dele (como no ERPNext). Avaliam-se num ambiente mínimo,
// só com o que os scripts usam (datas, valores por omissão, $.extend); tudo o resto é inerte.
function filtrosDoRelatorio(nome, m) {
  const o = m.omissao || {}; const hoje = o.today || new Date().toISOString().slice(0, 10);
  const d0 = (s) => new Date(String(s || hoje).slice(0, 10) + "T00:00:00");
  const iso = (x) => x.toISOString().slice(0, 10);
  const dt = { get_today: () => hoje, nowdate: () => hoje, now_date: () => hoje, now_datetime: () => hoje + " 00:00:00", get_time: () => "00:00:00",
    add_months: (s, n) => { const x = d0(s); x.setMonth(x.getMonth() + Number(n)); return iso(x); },
    add_days: (s, n) => { const x = d0(s); x.setDate(x.getDate() + Number(n)); return iso(x); },
    month_start: (s) => (s || hoje).slice(0, 8) + "01", month_end: (s) => { const x = d0(s); return iso(new Date(x.getFullYear(), x.getMonth() + 1, 0, 12)); },
    year_start: (s) => (s || hoje).slice(0, 4) + "-01-01", year_end: (s) => (s || hoje).slice(0, 4) + "-12-31",
    str_to_user: (x) => x, user_to_str: (x) => x, get_diff: (a, b) => Math.round((d0(a) - d0(b)) / 864e5) };
  const omissao = (k) => ({ company: o.company, Company: o.company, fiscal_year: o.fiscal_year, "Fiscal Year": o.fiscal_year, currency: o.currency, Currency: o.currency })[k] ?? "";
  const inerte = new Proxy(function () {}, { get: (t, k) => (k === Symbol.toPrimitive ? () => "" : inerte), apply: () => inerte });
  const comFolga = (obj) => new Proxy(obj, { get: (t, k) => (k in t ? t[k] : inerte), set: (t, k, v) => { t[k] = v; return true; } });
  const frappe = comFolga({ query_reports: {}, datetime: dt, defaults: { get_user_default: omissao, get_default: omissao, get_global_default: omissao },
    boot: comFolga({ sysdefaults: { company: o.company, currency: o.currency }, party_account_types: {} }), sys_defaults: { company: o.company },
    user: comFolga({ has_role: () => true }), session: { user: "" } });
  const anoFiscal = (d, comDatas) => (comDatas ? [o.fiscal_year, o.ano_inicio, o.ano_fim] : o.fiscal_year);
  const erpnext = comFolga({ utils: comFolga({ get_fiscal_year: anoFiscal, add_dimensions: () => {} }) });
  const $ = { extend: (...a) => Object.assign(...a) };
  const __ = (t) => (m.traducoes && m.traducoes[t]) || t;
  new Function("frappe", "erpnext", "__", "$", "moment", "window", "document", (m.partilhado || "") + "\n;\n" + (m.script || ""))(frappe, erpnext, __, $, inerte, inerte, inerte);
  const rep = frappe.query_reports[nome];
  if (!rep || !Array.isArray(rep.filters)) throw new Error("sem filtros");
  return rep.filters.filter((f) => f && f.fieldname).map((f) => {
    let def = f.default; if (typeof def === "function") { try { def = def(); } catch (e) { def = undefined; } }
    if (Array.isArray(def)) def = def[0];   // «default: ["Fiscal Year"]» nas demonstrações financeiras
    // o ERPNext preenche estes ao abrir o ecrã (onload); aqui ficam com o ano fiscal corrente
    if (def === undefined || def === "") def = ({ fiscal_year: o.fiscal_year, from_fiscal_year: o.fiscal_year, to_fiscal_year: o.fiscal_year,
      period_start_date: o.ano_inicio, period_end_date: o.ano_fim })[f.fieldname] ?? def;
    let opcoes = null;
    if (f.fieldtype === "Select") { const ops = Array.isArray(f.options) ? f.options : String(f.options || "").split("\n");
      opcoes = ops.map((x) => (typeof x === "object" && x ? { v: x.value, r: __(x.label || x.value) } : { v: x, r: __(x) })); }
    return { fieldname: f.fieldname, label: __(f.label || f.fieldname), fieldtype: ["MultiSelectList", "Autocomplete", "Dynamic Link"].includes(f.fieldtype) ? "Data" : f.fieldtype,
      options: typeof f.options === "string" ? f.options : null, opcoes, reqd: f.reqd, depends_on: typeof f.depends_on === "string" ? f.depends_on : null,
      mandatory_depends_on: typeof f.mandatory_depends_on === "string" ? f.mandatory_depends_on : null,
      default: def === inerte ? undefined : def, hidden: f.hidden };
  });
}

const ErpRelatorio = {
  components: { ErpCampo },
  props: ["nome"],
  setup(props) {
    const m = ref(null); const filtros = ref([]); const val = ref({}); const r = ref(null); const a = ref(false); const falhou = ref(false); const erro = ref("");
    onMounted(async () => {
      m.value = await api("erp.relatorio_meta", { nome: props.nome });
      if (m.value.tipo === "builder") { location.replace(irErp(m.value.doctype)); return; }
      try { filtros.value = filtrosDoRelatorio(props.nome, m.value); } catch (e) { falhou.value = true; return; }
      const v = {}; for (const f of filtros.value) if (f.default !== undefined && f.default !== null && f.default !== "") v[f.fieldname] = f.default;
      // lote 6: vindo de um documento, já com o documento e a data (ex.: razão de stock/geral)
      try { const pre = JSON.parse(sessionStorage.getItem("orbit.rel.filtros") || "null"); if (pre && pre.nome === props.nome) { sessionStorage.removeItem("orbit.rel.filtros");
        for (const [k, x] of Object.entries(pre.v)) if (x && filtros.value.some((f) => f.fieldname === k)) v[k] = x; } } catch (e) {}
      val.value = v;
      if (filtros.value.every((f) => !f.reqd || !vazioV(v[f.fieldname]))) correr();
    });
    const visivel = (f) => !f.hidden && avaliar(f.depends_on, val.value);
    const correr = async () => {
      const obrigF = (f) => f.reqd || (f.mandatory_depends_on && avaliar(f.mandatory_depends_on, val.value));
      const falta = filtros.value.filter((f) => obrigF(f) && visivel(f) && vazioV(val.value[f.fieldname]));
      if (falta.length) { toast("Falta preencher: " + falta.map((f) => f.label).join(", ")); return; }
      a.value = true; erro.value = "";
      try { const limpos = Object.fromEntries(Object.entries(val.value).filter(([k, x]) => !vazioV(x)));
        r.value = await api("erp.relatorio", { nome: props.nome, filtros: JSON.stringify(limpos) }, true); }
      catch (e) { erro.value = String(e.message || e); } finally { a.value = false; }
    };
    const moedaR = (x) => new Intl.NumberFormat("pt-PT", { style: "currency", currency: m.value?.omissao?.currency || "EUR" }).format(x || 0);
    const fmt = (c, x) => { if (x === null || x === undefined || x === "") return "";
      if (["Currency"].includes(c.fieldtype)) return moedaR(x);
      if (["Float", "Int", "Percent"].includes(c.fieldtype)) return new Intl.NumberFormat("pt-PT", { maximumFractionDigits: 2 }).format(x) + (c.fieldtype === "Percent" ? " %" : "");
      if (c.fieldtype === "Date") return new Date(x).toLocaleDateString("pt-PT");
      if (c.fieldtype === "Check") return x ? "✓" : "";
      if (c.fieldtype === "Link") return tr(c.options, String(x));
      if (/^(account|parent_account)$/.test(c.fieldname || "")) return tr("Account", String(x).replace(/<[^>]+>/g, ""));
      return String(x).replace(/<[^>]+>/g, ""); };
    const numerica = (c) => ["Currency", "Float", "Int", "Percent"].includes(c.fieldtype);
    const ligacao = (c, x) => (c.fieldtype === "Link" && c.options && x ? irErp(c.options, x) : null);
    // gráfico simples (barras) com os dados que o relatório já devolve
    const grafico = computed(() => {
      const g = r.value?.grafico; const dd = g?.data; if (!dd?.labels?.length || !dd.datasets?.length) return null;
      const series = dd.datasets.slice(0, 3); const max = Math.max(1, ...series.flatMap((s) => (s.values || []).map((v) => Math.abs(Number(v) || 0))));
      return { labels: dd.labels.slice(0, 24), series, max };
    });
    const CORES_G = ["var(--acao)", "#5b6f7a", "#8a7340"];
    const csv = () => {
      const cs = r.value.colunas; const esc = (x) => `"${String(x ?? "").replace(/<[^>]+>/g, "").replace(/"/g, '""')}"`;
      const txt = [cs.map((c) => esc(c.label)).join(";")].concat(r.value.linhas.map((l) => cs.map((c) => esc(l[c.fieldname])).join(";"))).join("\n");
      const b = new Blob(["\ufeff" + txt], { type: "text/csv;charset=utf-8" }); const u = URL.createObjectURL(b);
      const el = document.createElement("a"); el.href = u; el.download = (m.value.rotulo || props.nome) + ".csv"; el.click(); URL.revokeObjectURL(u);
    };
    const desk = computed(() => "#/erp-desk/" + encodeURIComponent("/desk/query-report/" + props.nome));
    // lote 7: Excel (o exportador do próprio Frappe) e imprimir só o relatório
    const excel = async () => { const fd = new FormData(); fd.append("report_name", props.nome); fd.append("file_format_type", "Excel"); fd.append("filters", JSON.stringify(val.value)); fd.append("visible_idx", "[]"); fd.append("include_indentation", "0");
      const rr = await fetch("/api/method/frappe.desk.query_report.export_query", { method: "POST", body: fd, headers: { "X-Frappe-CSRF-Token": window.csrf_token } });
      if (!rr.ok) { toast("Não foi possível gerar o Excel"); return; } const b = await rr.blob(); const u = URL.createObjectURL(b); const el = document.createElement("a"); el.href = u; el.download = (m.value.rotulo || props.nome) + ".xlsx"; el.click(); URL.revokeObjectURL(u); };
    const imprimir = () => { document.body.classList.add("imprimir-rel"); window.print(); setTimeout(() => document.body.classList.remove("imprimir-rel"), 500); };
    return { excel, imprimir, m, filtros, val, r, a, falhou, erro, visivel, correr, fmt, numerica, ligacao, grafico, CORES_G, csv, desk, moedaR };
  },
  template: `<div class="pad" v-if="m">
    <div style="display:flex;justify-content:space-between;align-items:flex-end;gap:12px;flex-wrap:wrap;margin-bottom:14px">
      <div><h1>{{ m.rotulo }}</h1><div class="sub">Relatório</div></div>
      <div style="display:flex;gap:8px"><button class="btn prim" :disabled="a" @click="correr">{{ a ? 'A gerar…' : 'Gerar' }}</button><button v-if="r && r.linhas.length" class="btn" @click="csv">Exportar CSV</button><button v-if="r && r.linhas.length" class="btn" @click="excel">Excel</button><button v-if="r && r.linhas.length" class="btn" @click="imprimir">Imprimir</button></div>
    </div>
    <div v-if="falhou" class="cartao vazio">Este relatório ainda não abre aqui.</div>
    <template v-else>
      <div class="cartao erp-filtros" v-if="filtros.length"><template v-for="f in filtros" :key="f.fieldname">
        <div v-if="visivel(f)" class="erp-campo"><label v-if="f.fieldtype!=='Check'">{{ f.label }}<span v-if="f.reqd" class="obrig">*</span></label><ErpCampo :c="f" :doc="val"/></div></template></div>
      <div v-if="erro" class="aviso" style="margin:12px 0">{{ erro }}</div>
      <template v-if="r">
        <div v-if="r.resumo.length" class="erp-totais cartao" style="margin:14px 0"><div v-for="s in r.resumo" :key="s.rotulo"><small>{{ s.rotulo }}</small><b :style="{color: s.cor==='Red'?'var(--acao)':s.cor==='Green'?'var(--verde)':'inherit'}">{{ s.tipo==='Currency' ? moedaR(s.valor) : s.valor }}</b></div></div>
        <div v-if="grafico" class="cartao erp-grafico">
          <svg :viewBox="'0 0 ' + Math.max(grafico.labels.length*48, 300) + ' 170'" preserveAspectRatio="none" :style="{minWidth: Math.max(grafico.labels.length*34, 280)+'px'}">
            <template v-for="(l,i) in grafico.labels" :key="i"><template v-for="(sr,k) in grafico.series" :key="k">
              <rect :x="i*48 + 6 + k*(36/grafico.series.length)" :width="36/grafico.series.length - 2" :y="140 - Math.abs(Number(sr.values[i])||0)/grafico.max*130" :height="Math.abs(Number(sr.values[i])||0)/grafico.max*130" :fill="CORES_G[k]" rx="2"><title>{{ sr.name }}: {{ sr.values[i] }}</title></rect></template>
              <text :x="i*48+24" y="160" text-anchor="middle" font-size="10" fill="var(--ink-3)">{{ String(l).slice(0,8) }}</text></template>
          </svg>
          <div class="sub" style="display:flex;gap:14px;flex-wrap:wrap"><span v-for="(sr,k) in grafico.series" :key="k"><span :style="{display:'inline-block',width:'10px',height:'10px',borderRadius:'2px',background:CORES_G[k],marginRight:'5px'}"></span>{{ sr.name }}</span></div>
        </div>
        <div class="tabela-wrap" style="margin:14px 0 0"><table>
          <thead><tr><th v-for="c in r.colunas" :key="c.fieldname" :style="{textAlign: numerica(c)?'right':'left'}">{{ c.label }}</th></tr></thead>
          <tbody><tr v-for="(l,i) in r.linhas" :key="i" style="cursor:default" :class="{'erp-grupo': l.is_group || (r.total && i===r.linhas.length-1)}">
            <td v-for="(c,ci) in r.colunas" :key="c.fieldname" :style="{textAlign: numerica(c)?'right':'left', paddingLeft: ci===0 && l.indent ? (12 + l.indent*16)+'px' : null}">
              <a v-if="ligacao(c, l[c.fieldname])" :href="ligacao(c, l[c.fieldname])">{{ fmt(c, l[c.fieldname]) }}</a><span v-else>{{ fmt(c, l[c.fieldname]) }}</span></td></tr></tbody></table>
          <div v-if="!r.linhas.length" class="vazio">Sem dados para estes filtros.</div></div>
        <div v-if="r.cortado" class="sub" style="margin-top:8px">Mostram-se as primeiras 3000 linhas — exporte ou afine os filtros para ver o resto.</div>
      </template>
    </template>
  </div><div v-else class="vazio">A carregar…</div>`,
};

const ErpDesk = {
  props: ["url"],
  template: `<div class="embutida"><iframe :src="url" title="ERPNext"></iframe></div>`,
};

// ── Faturas de compra (F3, 24-11-2026; docs/PLANO-DOCS-FATURA-COMPRA-ERP.md) ─────────────────────────────
// As faturas do Docs que a F2 deixou em rascunho: o PDF de um lado, as linhas do outro; ligar cada linha (artigo, sugestão,
// artigo novo ou custo) e Confirmar (submete, aprende a referência do fornecedor e devolve ao Docs), Devolver ao Docs ou
// «Não é uma compra». Fala com orbit.compras.rever.
const apiCo = (m, a = {}, post = false) => api("orbit.compras.rever." + m, a, post);
const COR_ESTADO = { "Em rascunho": "azul", "Por rever": "ambar", "Confirmada": "verde", "Devolvida": "roxo", "Erro": "ambar", "Sem créditos": "ambar" };
const COR_LIGACAO = { "Referência do fornecedor": "verde", "EAN": "verde", "Referência do importador": "verde", "Escolhido": "verde", "Criado": "verde",
  "Custo": "azul", "Sugerido": "ambar", "Por ligar": "ambar" };
const Compras = {
  components: { ErpLigacao },
  props: ["nome"],
  setup(props) {
    const filtro = ref("abertas"); const lista = ref(null); const d = ref(null); const a = ref(false);
    const escolha = reactive({}); const criar = ref(null); const fechar = ref(null);
    const eur = (v) => new Intl.NumberFormat("pt-PT", { style: "currency", currency: "EUR" }).format(v || 0);
    const num = (v) => new Intl.NumberFormat("pt-PT", { maximumFractionDigits: 3 }).format(v || 0);
    const carregarLista = async () => { lista.value = await apiCo("lista", { filtro: filtro.value }); };
    const carregar = async () => { if (props.nome) d.value = await apiCo("detalhe", { nome: props.nome }); };
    onMounted(() => { if (props.nome) carregar(); else carregarLista(); });
    watch(filtro, carregarLista);
    const fazer = async (fn, ok) => {
      a.value = true;
      try { const r = await fn(); if (r && r.registo) d.value = r; if (ok) toast(ok); return r; } finally { a.value = false; }
    };
    const linha = (l, acao, extra = {}) => fazer(() => apiCo("linha", { nome: props.nome, linha: l.name, acao, ...extra }, true));
    const escolher = (l) => { if (!escolha[l.name]) { toast("Escolha primeiro o artigo."); return; } linha(l, "artigo", { item_code: escolha[l.name] }); };
    const abrirCriar = (l) => { criar.value = { l, nome: l.item_name || l.description, stock: true, marca: "" }; };
    const gravarCriar = async () => {
      const c = criar.value; await linha(c.l, "criar", { novo: JSON.stringify({ nome: c.nome, stock: c.stock ? 1 : 0, marca: c.marca || "" }) }); criar.value = null;
    };
    const pendentes = computed(() => (d.value?.linhas || []).filter((l) => ["Por ligar", "Sugerido"].includes(l.ligacao)).length);
    const confirmar = () => fazer(() => apiCo("confirmar", { nome: props.nome }, true), "Confirmada e lançada no ERP.");
    const fecharFatura = async () => {
      const f = fechar.value;
      await fazer(() => apiCo(f.acao, { nome: props.nome, motivo: f.motivo }, true), f.acao === "devolver" ? "Devolvida ao Docs." : "Fechada: não é uma compra.");
      fechar.value = null;
    };
    const forcar = () => fazer(() => apiCo("preparar_mesmo_assim", { nome: props.nome }, true), "Rascunho preparado.");
    const lerDeNovo = () => fazer(async () => { await api("orbit.compras.docs.ler", { docs_id: d.value.registo.docs_id, forcar: 1 }, true); return apiCo("detalhe", { nome: props.nome }); }, "Lida de novo.");
    const repetirDocs = () => fazer(() => apiCo("repetir_docs", { nome: props.nome }, true), "Docs actualizado.");
    const pdf = computed(() => props.nome ? "/api/method/orbit.compras.rever.pdf?nome=" + encodeURIComponent(props.nome) : "");
    const aberta = computed(() => d.value?.fatura && d.value.fatura.docstatus === 0);
    const notas = computed(() => (d.value?.registo.motivo || "").split("\n").filter((x) => x.trim()));
    const abrir = (f) => { location.hash = "#/compras/" + encodeURIComponent(f.name); };
    return { abrir, filtro, lista, d, a, escolha, criar, fechar, eur, num, data, irErp, COR_ESTADO, COR_LIGACAO, linha, escolher, abrirCriar, gravarCriar,
      pendentes, confirmar, fecharFatura, forcar, lerDeNovo, repetirDocs, pdf, aberta, notas };
  },
  template: `<div class="pad" v-if="!nome">
    <div style="margin-bottom:16px"><h1>Faturas de compra</h1><div class="sub">Do Docs para o ERP: rever as linhas, confirmar e devolver ao Docs o processo e o vencimento</div></div>
    <div class="vistas" style="padding:0;margin-bottom:12px" v-if="lista">
      <button v-for="v in [['abertas','Por rever'],['confirmadas','Confirmadas'],['outras','Outras']]" :key="v[0]" :class="{ativo: filtro===v[0]}" @click="filtro=v[0]">{{ v[1] }} <span class="sub">{{ lista.contagens[v[0]] }}</span></button>
    </div>
    <div class="tabela-wrap" style="margin:0" v-if="lista"><table>
      <thead><tr><th>Fornecedor</th><th>N.º</th><th>Data</th><th>Vencimento</th><th style="text-align:right">Total</th><th>Linhas ligadas</th><th>Estado</th></tr></thead>
      <tbody><tr v-for="f in lista.linhas" :key="f.name" @click="abrir(f)">
        <td><b>{{ f.fornecedor || f.fornecedor_nome || '—' }}</b><small class="sub" style="display:block">{{ f.tipo_documento }} · Docs n.º {{ f.docs_id }}</small></td>
        <td>{{ f.numero || '—' }}</td><td>{{ f.data_fatura ? data(f.data_fatura, false) : '—' }}</td><td>{{ f.vencimento ? data(f.vencimento, false) : '—' }}</td>
        <td style="text-align:right">{{ eur(f.total) }}</td>
        <td>{{ f.linhas_total ? f.linhas_ligadas + ' / ' + f.linhas_total : '—' }}</td>
        <td><span class="etq" :class="COR_ESTADO[f.estado]">{{ f.estado }}</span></td></tr></tbody></table>
      <div v-if="!lista.linhas.length" class="vazio">{{ filtro==='abertas' ? 'Nenhuma fatura de compra por rever.' : 'Nada aqui.' }}</div></div>
    <div v-else class="vazio">A carregar…</div>
  </div>
  <div class="compras-rever" v-else-if="d">
    <div class="compras-pdf"><iframe :src="pdf" title="Documento do Docs"></iframe><a class="sub" :href="pdf" target="_blank">Abrir o documento noutro separador ↗</a></div>
    <div class="compras-dados">
      <a href="#/compras" class="sub" style="text-decoration:none">← Faturas de compra</a>
      <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;margin:6px 0 12px;flex-wrap:wrap">
        <div><h1 style="margin:0">{{ d.fatura?.supplier_name || d.registo.fornecedor_nome || 'Fornecedor por ler' }}</h1>
          <div class="sub">{{ d.registo.tipo_documento }} {{ d.registo.numero }} · {{ d.registo.data_fatura ? data(d.registo.data_fatura, false) : 'sem data' }}
            · NIF {{ d.registo.fornecedor_nif || '—' }}<template v-if="d.fatura && !d.fatura.supplier_nif && d.registo.fornecedor_nif"> (grava-se no fornecedor ao confirmar)</template></div></div>
        <div style="display:flex;gap:6px;flex-wrap:wrap"><span v-if="d.fatura?.is_return || d.registo.tipo_documento==='Nota de crédito'" class="etq roxo">Nota de crédito</span>
          <span class="etq" :class="COR_ESTADO[d.registo.estado]">{{ d.registo.estado }}</span></div>
      </div>
      <div v-if="d.fatura?.is_return || d.registo.fatura_original" class="sub" style="margin:-6px 0 12px">Corrige a fatura {{ d.registo.fatura_original || '(não indicada)' }}<template v-if="d.fatura?.return_against"> — devolução da <a :href="irErp('Purchase Invoice', d.fatura.return_against)">{{ d.fatura.return_against }}</a></template><template v-else-if="d.fatura"> — sem ligação a uma fatura de compra do ERP</template></div>
      <div class="erp-totais cartao" style="margin:0 0 12px">
        <div><small>Total da fatura</small><b>{{ eur(d.registo.total) }}</b></div>
        <div v-if="d.fatura"><small>Total no ERP</small><b :style="{color: Math.abs(Math.abs(d.fatura.grand_total||0)-(d.registo.total||0))>0.05 ? 'var(--acao)' : 'inherit'}">{{ eur(d.fatura.grand_total) }}</b></div>
        <div v-if="!d.fatura?.is_return && d.registo.tipo_documento!=='Nota de crédito'"><small>Vencimento</small><b>{{ (d.fatura?.due_date || d.registo.vencimento) ? data(d.fatura?.due_date || d.registo.vencimento, false) : '—' }}</b></div>
        <div v-if="d.fatura"><small>Stock</small><b>{{ d.fatura.update_stock ? (d.fatura.is_return ? 'Sai do armazém' : 'Entra em armazém') : (d.fatura.is_return ? 'Sem saída' : 'Sem entrada') }}</b></div>
        <div v-if="d.fatura && !d.fatura.is_return"><small>Pagamento</small><b>{{ d.fatura.is_paid ? 'Já paga' : 'Por pagar' }}</b></div>
      </div>
      <div v-if="notas.length" class="cartao compras-notas"><div v-for="(n,i) in notas" :key="i">{{ n }}</div></div>

      <template v-if="d.fatura">
        <div class="compras-linha cartao" v-for="l in d.linhas" :key="l.name" :class="{pendente: ['Por ligar','Sugerido'].includes(l.ligacao)}">
          <div style="display:flex;justify-content:space-between;gap:10px;align-items:flex-start">
            <div style="min-width:0"><b>{{ l.description || l.item_name }}</b>
              <div class="sub">{{ l.ref ? 'Ref. ' + l.ref + ' · ' : '' }}{{ num(l.qty) }} {{ l.uom }} × {{ eur(l.rate) }} = <b>{{ eur(l.amount) }}</b></div></div>
            <span class="etq" :class="COR_LIGACAO[l.ligacao]">{{ l.ligacao || '—' }}</span>
          </div>
          <div class="sub" style="margin-top:4px" v-if="l.item_code">Artigo: <a :href="irErp('Item', l.item_code)">{{ l.item_code }}</a> {{ l.item_name !== l.item_code ? '— ' + l.item_name : '' }}
            <template v-if="l.warehouse"> · {{ l.warehouse }}</template><template v-if="l.purchase_order"> · encomenda <a :href="irErp('Purchase Order', l.purchase_order)">{{ l.purchase_order }}</a></template></div>
          <div class="sub" style="margin-top:4px" v-else-if="l.ligacao==='Custo'">Custo: {{ l.expense_account }}<template v-if="l.categoria && l.categoria!=='Mercadoria'"> · lida como «{{ l.categoria }}»</template></div>
          <div class="compras-acoes" v-if="aberta">
            <button v-if="l.sugestao" class="btn" :disabled="a" @click="linha(l,'sugestao')">Usar a sugestão: {{ l.sugestao_nome || l.sugestao }}</button>
            <div class="erp-campo" style="margin:0;min-width:220px;flex:1"><ErpLigacao v-model="escolha[l.name]" alvo="Item"/></div>
            <button class="btn" :disabled="a" @click="escolher(l)">Escolher artigo</button>
            <button class="btn" :disabled="a" @click="abrirCriar(l)">Criar artigo</button>
            <button class="btn" :disabled="a || l.ligacao==='Custo'" @click="linha(l,'custo')">É um custo</button>
          </div>
          <div v-if="criar && criar.l.name===l.name" class="compras-criar">
            <div class="erp-campo" style="margin:0;flex:1;min-width:220px"><label>Nome do artigo novo</label><input v-model="criar.nome"></div>
            <div class="erp-campo" style="margin:0;min-width:160px"><label>Marca (opcional)</label><ErpLigacao v-model="criar.marca" alvo="Brand"/></div>
            <label style="display:flex;gap:6px;align-items:center"><input type="checkbox" v-model="criar.stock"> Artigo de stock</label>
            <button class="btn prim" :disabled="a || !criar.nome" @click="gravarCriar">Criar e ligar</button><button class="btn" @click="criar=null">Cancelar</button>
          </div>
        </div>
      </template>
      <div v-else-if="d.lidas.length" class="tabela-wrap" style="margin:0 0 12px"><table>
        <thead><tr><th>Ref.</th><th>Descrição</th><th>Qtd.</th><th style="text-align:right">Total s/ IVA</th><th>IVA</th></tr></thead>
        <tbody><tr v-for="(l,i) in d.lidas" :key="i" style="cursor:default"><td>{{ l.referencia || '—' }}</td><td>{{ l.descricao }}</td><td>{{ num(l.quantidade) }}</td><td style="text-align:right">{{ eur(l.total_sem_iva) }}</td><td>{{ l.taxa_iva ?? '—' }} %</td></tr></tbody></table></div>

      <div v-if="fechar" class="cartao compras-criar" style="margin-top:12px">
        <div class="erp-campo" style="margin:0;flex:1;min-width:260px"><label>{{ fechar.acao==='devolver' ? 'O que está mal (fica como nota no Docs)' : 'Porquê (opcional, fica como nota no Docs)' }}</label><input v-model="fechar.motivo"></div>
        <button class="btn prim" :disabled="a || (fechar.acao==='devolver' && !fechar.motivo)" @click="fecharFatura">{{ fechar.acao==='devolver' ? 'Devolver ao Docs' : 'Não é uma compra' }}</button><button class="btn" @click="fechar=null">Cancelar</button>
      </div>
      <div class="compras-botoes">
        <template v-if="aberta">
          <button class="btn prim" :disabled="a || pendentes>0 || !d.pode_submeter" @click="confirmar" :title="pendentes ? 'Faltam ' + pendentes + ' linha(s) por ligar' : ''">{{ a ? 'A gravar…' : 'Confirmar' }}</button>
          <span v-if="pendentes" class="sub">Faltam {{ pendentes }} linha(s) por ligar.</span>
          <span v-else-if="!d.pode_submeter" class="sub">Sem permissão para submeter faturas de compra.</span>
        </template>
        <button v-if="!d.fatura && d.pode_forcar" class="btn prim" :disabled="a" @click="forcar">Preparar rascunho mesmo assim</button>
        <button v-if="['Erro','Sem créditos','Devolvida'].includes(d.registo.estado)" class="btn" :disabled="a" @click="lerDeNovo">Ler de novo</button>
        <template v-if="d.registo.estado!=='Confirmada' && d.registo.estado!=='Não é compra'">
          <button class="btn" :disabled="a" @click="fechar={acao:'devolver', motivo:''}">Devolver ao Docs</button>
          <button class="btn" :disabled="a" @click="fechar={acao:'nao_compra', motivo:''}">Não é uma compra</button>
        </template>
        <button v-if="d.registo.estado==='Confirmada' && !d.registo.docs_actualizado" class="btn" :disabled="a" @click="repetirDocs">Escrever de novo no Docs</button>
        <a v-if="d.fatura" class="btn" :href="irErp('Purchase Invoice', d.fatura.name)">Fatura de compra {{ d.fatura.name }}</a>
      </div>
    </div>
  </div>
  <div v-else class="vazio">A carregar…</div>`,
};

// ── As apps do Orbit (22-11-2026, maqueta docs/orbit-interface/apps/) ────────────────────────────────────────
// Uma app por área, cada uma no seu separador (/orbit?app=<chave>), com a mesma barra de cima: seletor de apps, nome da
// app, pesquisa, sino, claro/escuro e a roda dentada só com as definições dessa app. Os ecrãs são os mesmos de sempre.
const APP_ATUAL = (new URLSearchParams(location.search).get("app") || "crm").toLowerCase();
const APPS = {
  crm: { nome: "CRM", sub: "Clientes e atendimento", ic: "pessoa", inicio: "inicio",
    // 23-11-2026 (Vítor): a caixa de entrada (correio por IMAP, partilhadas, conversas do CRM, tickets) e o Chat na barra
    nav: [["inicio", "casa", "Início"], ["caixa", "caixa", "Caixa de entrada"], ["chat", "chat", "Chat"], ["sec", "CRM"], ["leads", "lead", "Leads"], ["contactos", "pessoa", "Contactos"], ["empresas", "empresa", "Empresas"],
      ["negocios", "negocio", "Negócios"], ["funil", "negocio", "Funil"], ["crm-painel", "grelha", "Painel"],
      ["sec", "O meu dia"], ["calendario", "cal", "Calendário"], ["tarefas", "tarefa", "Tarefas"],
      ["erp/FCRM%20Note", "nota", "Notas"], ["erp/CRM%20Call%20Log", "tel", "Chamadas"], ["app/Booking", "relogio", "Marcar reuniões"],
      ["sec", "Documentos"], ["assinaturas", "assin", "Assinaturas"]],
    modulos: [], defs: ["CRM", "Correio"] },
  // 22-11-2026 (Vítor): o Desk separado do CRM — quem só faz atendimento tem a sua app.
  desk: { nome: "Desk", sub: "Atendimento", ic: "ticket", inicio: "tickets",
    nav: [["sec", "Atendimento"], ["tickets", "ticket", "Tickets"], ["desk-painel", "grelha", "Painel"], ["caixa", "caixa", "Caixa de entrada"],
      ["sec", "Clientes"], ["contactos", "pessoa", "Contactos"], ["erp/HD%20Customer", "empresa", "Clientes do Desk"],
      ["sec", "Conhecimento"], ["desk-kb", "livro", "Base de conhecimento"], ["erp/HD%20Saved%20Reply", "template", "Respostas-modelo"],
      ["desk-checklists", "tarefa", "Modelos de checklist"],
      ["sec", "Configuração"], ["erp/HD%20Team", "pessoas", "Equipas"], ["erp/HD%20Service%20Level%20Agreement", "relogio", "Prazos (SLA)"],
      ["erp/HD%20Service%20Holiday%20List", "cal", "Feriados"], ["erp/Assignment%20Rule", "tarefa", "Regras de atribuição"], ["erp/HD%20Settings", "roda", "Definições do Desk"]],
    modulos: [], defs: ["Atendimento (Desk)", "Correio"] },
  projetos: { nome: "Projetos", sub: "Projetos, tarefas e tempo", ic: "projeto", inicio: "projetos",
    nav: [["sec", "Trabalho"], ["projetos", "projeto", "Projetos"], ["tarefas", "tarefa", "Tarefas"], ["calendario", "cal", "Calendário"], ["sec", "Tempo"], ["tempo", "relogio", "Registo de horas"]],
    modulos: ["Projects"], defs: ["Pessoas e tempo"] },
  rh: { nome: "RH", sub: "Pessoas e equipa", ic: "pessoas", inicio: "pessoas",
    nav: [["sec", "Pessoas"], ["pessoas", "pessoas", "Colaboradores"], ["rh-aprovar", "tarefa", "Por aprovar"], ["rh-ausencias", "cal", "Calendário de ausências"],
      ["erp/Leave Application", "nota", "Ausências"], ["erp/Expense Claim", "euro", "Despesas"]],
    modulos: ["Frappe HR", "Recruitment", "Leaves", "Shift & Attendance", "Performance", "Tenure", "Payroll", "Expenses", "Tax & Benefits"], defs: ["Pessoas e tempo"] },
  gestao: { nome: "Gestão", sub: "Dinheiro e obrigações", ic: "euro", inicio: "",
    nav: [], modulos: ["Invoicing", "Payments", "Banking", "Accounting", "Financial Reports", "Subscription"], defs: ["Vendas e faturação", "Marcas e empresa"] },
  operacoes: { nome: "Operações", sub: "Comprar, produzir, vender", ic: "cubo", inicio: "",
    // 27-11-2026 (Vítor: «têm que existir todo o tipo de documentos… devoluções, notas de crédito»): cada tipo com a sua
    // lista (o 4.º elemento são os filtros com que abre) e o seu «+ Nova…» a partir do documento original
    nav: [["sec", "Vendas"], ["erp/Quotation", "nota", "Propostas"], ["erp/Sales Order", "nota", "Encomendas"], ["erp/Sales Invoice", "euro", "Faturas", [["is_return", "=", 0]]],
      ["erp/Sales Invoice", "euro", "Notas de crédito", [["is_return", "=", 1]]], ["erp/Delivery Note", "cubo", "Guias de transporte", [["is_return", "=", 0]]],
      ["erp/Delivery Note", "cubo", "Guias de devolução", [["is_return", "=", 1]]], ["erp/Payment Entry", "euro", "Recibos", [["payment_type", "=", "Receive"]]], ["erp/Customer", "pessoas", "Clientes"],
      ["sec", "Compras"], ["compras", "euro", "Faturas de compra"], ["erp/Purchase Invoice", "euro", "Faturas de fornecedor", [["is_return", "=", 0]]],
      ["erp/Purchase Invoice", "euro", "Notas de débito", [["is_return", "=", 1]]], ["erp/Material Request", "nota", "Pedidos de material"], ["erp/Supplier Quotation", "nota", "Cotações de fornecedor"],
      ["erp/Purchase Order", "nota", "Encomendas a fornecedor"], ["erp/Purchase Receipt", "cubo", "Receções", [["is_return", "=", 0]]],
      ["erp/Purchase Receipt", "cubo", "Devoluções a fornecedor", [["is_return", "=", 1]]], ["erp/Payment Entry", "euro", "Pagamentos", [["payment_type", "=", "Pay"]]], ["erp/Supplier", "pessoas", "Fornecedores"],
      ["sec", "Stock"], ["erp-stock", "cubo", "Inventário"], ["erp/Stock Entry", "cubo", "Movimentos de stock"], ["erp/Stock Reconciliation", "cubo", "Acertos de inventário"], ["erp/Item", "cubo", "Artigos"]],
    modulos: ["Selling", "Buying", "Stock", "Assets", "Manufacturing", "Subcontracting", "Quality"], defs: ["Vendas e faturação"] },
  // 22-11-2026: o Marketing com o mesmo aspecto das outras apps (os ecrãs dele são da secretária, mostrados cá dentro).
  marketing: { nome: "Marketing", sub: "Campanhas e envios", ic: "megafone", inicio: "erp/Campanha de Marketing",
    // 25-11-2026: tudo no ecrã novo (antes era a secretária antiga dentro do Orbit)
    nav: [["sec", "Campanhas"], ["erp/Campanha de Marketing", "megafone", "Campanhas"], ["erp/Automacao de Marketing", "relogio", "Automações"], ["mkt-modelos", "mail", "Modelos de email"],
      ["sec", "Público"], ["mkt-segmentos", "pessoas", "Segmentos"], ["mkt-marcadores", "nota", "Marcadores"], ["erp/Assunto de Marketing", "livro", "Assuntos de interesse"],
      ["sec", "Envios"], ["erp/Envio de Marketing", "caixa", "Envios"], ["erp/Supressao de Marketing", "nota", "Supressões"], ["erp/Definicoes de Marketing", "roda", "Definições"]],
    modulos: [], defs: null },
  admin: { nome: "Administração", sub: "Só administradores", ic: "roda", inicio: "definicoes",
    nav: [["sec", "Plataforma"], ["definicoes", "roda", "Definições do Orbit"], ["definicoes/utilizadores", "pessoas", "Utilizadores"], ["definicoes/empresas", "grelha", "Empresas"]],
    modulos: ["ERPNext Settings", "Users", "Website", "Integrations", "Automation", "Data", "Email", "Printing", "System"], defs: null },
};
const APP = APPS[APP_ATUAL] || APPS.crm;
// 23-11-2026 (Vítor): os ícones de cada app são os do Orbit (os da grelha), nunca símbolos genéricos
// 25-11-2026 (Vítor): Projetos, Gestão, Operações e Administração com o desenho próprio (o mesmo da página inicial),
// não o edifício genérico do ERP; o Portal com o dele; «Início» (orbit.<domínio>) com o símbolo do Orbit.
const ICONE_APP = { crm: "crm", desk: "desk", projetos: "projetos", rh: "rh", gestao: "gestao", operacoes: "operacoes", marketing: "marketing", admin: "admin",
  mail: "mail", meet: "meet", chat: "chat", docs: "docs", sign: "sign", booking: "booking", wiki: "wiki", propostas: "propostas",
  events: "events", social: "social", portal: "portal", inicio: "orbit" };
const srcApp = (chave) => "/assets/orbit/icons/apps/" + (ICONE_APP[(chave || "").toLowerCase()] || "orbit") + ".svg";
// Abrir uma app: volta ao separador onde já está (se foi o Orbit a abri-lo), senão abre um novo.
// 23-11-2026: no telemóvel (ecrã táctil, estreito ou app instalada) abre-se na MESMA janela, como numa app nativa — os
// separadores com nome («orbit-mail») eram reaproveitados mesmo depois de já mostrarem outra app (o Mail abria o CRM).
const NO_TELEMOVEL = () => /iPhone|iPad|Android|Mobile/i.test(navigator.userAgent || "") || window.innerWidth < 760
  || (window.matchMedia && matchMedia("(display-mode: standalone)").matches) || !!navigator.standalone;
const abrirApp = (chave, url) => {
  const destino = url || ("/orbit?app=" + chave);
  if (NO_TELEMOVEL()) { location.href = destino; return; }
  const w = window.open(destino, "orbit-" + chave); if (w) w.focus();
};

// ── Aplicação ────────────────────────────────────────────────────────────────────────────────────────
const App = {
  components: { Icone, Inicio, Lista, Ficha, Funil, Caixa, Definicoes, AppEmbutida, ErpModulo, ErpPainel, ErpContas, ErpImportar, RhAprovar, RhAusencias, CrmPainel, DeskPainel, DeskKb, MktSegmentos, MktMarcadores, MktModelos, ErpLista, ErpFicha, ErpProposta, ErpEmitir, ErpRecibo, ErpDesk, ErpStock, ErpPessoas, ErpRelatorio, Compras, Calendario, DefLista, DefCampos, DefFluxos, DefFunis, DefFormularios, DeskTickets, DeskTicket, DeskModelos, DefConsulta, DefUtilizadores, DefEmpresas, Tarefas, Projetos, Projeto, Documentos, Assinaturas, Tempo, Chat, Duplicados, Fila, Sino },
  setup() {
    const ctx = ref(null); const rota = ref(location.hash || "#/inicio");
    const q = ref(""); const res = ref([]); const selRes = ref(0); let tq;
    const gaveta = ref(false);   // 25-11-2026: menu ☰ abaixo de 1100 px (no telemóvel só se navegava no CRM)
    window.addEventListener("hashchange", () => { gaveta.value = false; rota.value = location.hash || "#/inicio"; estado.erroEcra = ""; document.querySelector(".ecra")?.scrollTo(0, 0); });
    onMounted(async () => { ctx.value = await api("contexto"); window.__ctx = ctx.value; contarChat(); setInterval(() => { if (!document.hidden) contarChat(); }, 60000); });
    // 23-11-2026: as não lidas do Chat no menu (mensagens diretas e tópicos dos canais)
    const contarChat = async () => {
      try {
        // sem toast: um Orbit sem Chat (ou com o Chat em baixo) não pode encher o ecrã de avisos de minuto a minuto
        const rr = await fetch("/api/method/orbit.interface.chat.conversas", { headers: { Accept: "application/json" } });
        const c = rr.ok ? (await rr.json()).message : null; if (!c || !c.ligado) { estado.chat = 0; return; }
        estado.chat = (c.directas || []).reduce((a, d) => a + (d.por_ler || 0), 0) + (c.canais || []).reduce((a, k) => a + (k.por_ler || 0), 0);
      } catch (e) { estado.chat = 0; }
    };
    const partes = computed(() => rota.value.replace(/^#\/?/, "").split("/").map(decodeURIComponent));
    const ecra = computed(() => partes.value[0] || "inicio");
    watch(q, (v) => { clearTimeout(tq); if (v.trim().length < 2) { res.value = []; return; } tq = setTimeout(async () => { res.value = await api("pesquisa", { q: v }); selRes.value = 0; }, 200); });
    const irRes = (r) => { location.hash = link(r.doctype, r.name); q.value = ""; res.value = []; };
    const teclaPesq = (e) => {
      if (e.key === "ArrowDown") { selRes.value = Math.min(selRes.value + 1, res.value.length - 1); e.preventDefault(); }
      else if (e.key === "ArrowUp") { selRes.value = Math.max(selRes.value - 1, 0); e.preventDefault(); }
      else if (e.key === "Enter" && res.value[selRes.value]) irRes(res.value[selRes.value]);
      else if (e.key === "Escape") { q.value = ""; e.target.blur(); }
    };
    window.addEventListener("keydown", (e) => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); document.querySelector("#pesq")?.focus(); } });
    let tema0 = null; try { tema0 = localStorage.getItem("orbit.tema"); } catch (e) {}
    if (tema0) document.documentElement.dataset.theme = tema0;
    const tema = () => {
      const r = document.documentElement;
      const escuro = r.dataset.theme ? r.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
      r.dataset.theme = escuro ? "light" : "dark"; try { localStorage.setItem("orbit.tema", r.dataset.theme); } catch (e) {}
    };
    const NAV = APP.nav;
    window.name = window.name || ("orbit-" + APP_ATUAL);
    document.title = APP.nome + " — Stratechna Orbit";
    // 25-11-2026: só módulos com ecrã na interface (um módulo sem barra abria a secretária antiga)
    const modulosApp = computed(() => (ctx.value?.modulos || []).filter((m) => APP.modulos.includes(m.chave) && m.barra));
    // Sem rota: a 1.ª secção da app (o Início no CRM; o 1.º módulo na Gestão e nas Operações).
    watch(ctx, (c) => {
      if (!c || (location.hash && location.hash !== "#/")) return;
      if (APP.inicio) { location.hash = "#/" + APP.inicio; return; }
      const m = modulosApp.value[0]; if (m) location.hash = m.barra ? "#/erp-m/" + encodeURIComponent(m.barra) : "#/" + (APP.nav.find((n) => n[0] !== "sec") || ["inicio"])[0];
    });
    const seletor = ref(false);
    // 26-11-2026: a conta no fundo da barra abre um menu (era só texto, sem nada ao clicar)
    const menuConta = ref(false);
    window.addEventListener("click", (e) => { if (menuConta.value && !e.target.closest(".fim, .menu-conta")) menuConta.value = false; });
    window.addEventListener("keydown", (e) => { if (e.key === "Escape") menuConta.value = false; });
    // 26-11-2026: no Frappe 16 sair só se faz por POST (o «/?cmd=web_logout» por GET dava 403 «Não permitido»)
    const sair = () => { menuConta.value = false;
      fetch("/api/method/logout", { method: "POST", credentials: "same-origin", headers: { "X-Frappe-CSRF-Token": window.csrf_token || "", Accept: "application/json" } })
        .finally(() => location.replace("/login")); };
    const LISTA_APPS = computed(() => [
      { chave: "inicio", nome: "Início", url: "/" },   // 25-11-2026: a página inicial do Orbit (orbit.<domínio>)
      ...Object.entries(APPS).filter(([k]) => k !== "admin" || ctx.value?.admin !== false).map(([k, a]) => ({ chave: k, nome: a.nome, ic: a.ic })),
      ...((ctx.value?.apps) || []).map((a) => ({ chave: a.nome.toLowerCase(), nome: a.nome, ic: a.icone, url: a.url })),
    ].filter((a, i, l) => l.findIndex((b) => b.chave === a.chave) === i));   // sem repetidos (o Marketing vinha duas vezes)
    const irApp = (a) => { seletor.value = false; if (a.chave === APP_ATUAL) return; abrirApp(a.chave, a.url); };
    // 27-11-2026: itens do menu com filtros (Faturas / Notas de crédito…) — a lista abre já filtrada e só o escolhido fica activo
    const navEscolhido = ref(null);
    const irNav = (n) => { navEscolhido.value = n; if (!n[3]) { if (NAV.some((x) => x !== n && x[0] === n[0] && x[3])) n = [n[0], n[1], n[2], []]; else return; }
      try { sessionStorage.setItem("orbit.erp.filtro", JSON.stringify({ doctype: decodeURIComponent(n[0].split("/")[1] || ""), filtros: n[3] })); } catch (e) {}
      window.dispatchEvent(new Event("orbit-erp-filtro")); };
    const _ativoBase = (n) => { const e = ecra.value; const r = partes.value.join("/"); return n[0] === r || decodeURIComponent(n[0]) === r || e === n[0] || (n[0]==='contactos'&&e==='contacto') || (n[0]==='negocios'&&e==='negocio') || (n[0]==='empresas'&&e==='empresa') || (n[0]==='leads'&&e==='lead') || (n[0]==='projetos'&&e==='projeto') || (n[0]==='tarefas'&&e==='fila'); };
    const ativoNav = (n) => { if (!_ativoBase(n)) return false; const irmaos = NAV.filter((x) => x[0] === n[0]); if (irmaos.length < 2) return true;
      return navEscolhido.value ? navEscolhido.value === n : n === irmaos[0]; };
    const rotaCal = computed(() => partes.value.join("/"));
    // 25-11-2026: a barra de baixo do telemóvel é a de cada app (era a do CRM em todas): 4 destinos + «Menu»
    const MOVEL = computed(() => {
      const curto = { "Caixa de entrada": "Caixa", "Calendário": "Agenda", "Base de conhecimento": "Artigos", "Faturas de compra": "A rever", "Definições do Orbit": "Definições", "Registo de horas": "Horas" };
      let l = NAV.filter((n) => n[0] !== "sec").map((n) => ({ n, rota: n[0], ic: n[1], r: curto[n[2]] || n[2] }));
      if (l.length < 4) l = l.concat(modulosApp.value.filter((m) => m.barra).map((m) => ({ n: ["erp-m/" + encodeURIComponent(m.barra)], rota: "erp-m/" + encodeURIComponent(m.barra), ic: "grelha", r: m.nome })));
      return l.slice(0, 4);
    });
    return { irNav, gaveta, MOVEL, ctx, ecra, partes, q, res, selRes, irRes, teclaPesq, tema, NAV, estado, ROTAS_DT, EMBUTIDAS, rotaCal, APP, APP_ATUAL, modulosApp, seletor, LISTA_APPS, irApp, ativoNav, srcApp, menuConta, sair };
  },
  template: `
  <div class="app" v-if="ctx">
    <div class="gaveta-fundo" v-if="gaveta" @click="gaveta=false"></div>
    <nav class="nav" :class="{aberta: gaveta}" aria-label="Navegação principal">
      <div class="marca"><div class="logo logo-app"><img :src="srcApp(APP_ATUAL)" alt=""></div><div>{{ APP.nome }}<small>{{ APP.sub }}</small></div></div>
      <template v-for="(n,i) in NAV" :key="i">
        <h6 v-if="n[0]==='sec'">{{ n[1] }}</h6>
        <a v-else :href="'#/'+n[0]" style="text-decoration:none" @click="irNav(n)"><button :class="{ativo: ativoNav(n)}" tabindex="-1"><Icone :n="n[1]"/>{{ n[2] }}<span class="conta" v-if="n[0]==='caixa' && ctx.contadores.tickets">{{ ctx.contadores.tickets }}</span><span class="conta" v-if="n[0]==='compras' && ctx.contadores.compras" title="Faturas de compra por rever">{{ ctx.contadores.compras }}</span><span class="conta" v-if="n[0]==='chat' && estado.chat" title="Mensagens por ler no Chat">{{ estado.chat }}</span></button></a>
      </template>
      <template v-if="modulosApp.length"><h6>{{ APP_ATUAL==='admin' ? 'Sistema' : 'Módulos' }}</h6>
      <a v-for="m in modulosApp" :key="m.url" :href="m.barra ? '#/erp-m/'+encodeURIComponent(m.barra) : m.url" :target="m.barra ? null : '_blank'" style="text-decoration:none"><button tabindex="-1" :class="{ativo: ecra==='erp-m' && partes[1]===m.barra}"><Icone n="grelha"/>{{ m.nome }}<span class="fora" v-if="!m.barra">↗</span></button></a></template>

      <div class="so-gaveta"><h6>Conta</h6>
        <a :href="'#/definicoes'" style="text-decoration:none"><button tabindex="-1"><Icone n="roda"/>Definições — {{ APP.nome }}</button></a>
        <button @click="tema"><Icone n="lua"/>Claro / escuro</button></div>
      <div class="cartao menu-conta" v-if="menuConta" role="menu">
        <div class="menu-conta-quem"><b>{{ ctx.nome }}</b><small>{{ ctx.utilizador }}</small></div>
        <a role="menuitem" :href="'/desk/user/' + encodeURIComponent(ctx.utilizador)" target="_blank"><Icone n="pessoas"/>A minha conta</a>
        <a role="menuitem" href="#/definicoes" @click="menuConta=false"><Icone n="roda"/>Definições — {{ APP.nome }}</a>
        <a role="menuitem" href="javascript:void 0" @click="tema(); menuConta=false"><Icone n="lua"/>Claro / escuro</a>
        <a role="menuitem" href="/"><Icone n="grelha"/>Início do Orbit</a>
        <a role="menuitem" href="javascript:void 0" class="sair" @click="sair">Sair</a>
      </div>
      <button type="button" class="fim" :class="{ativo: menuConta}" @click="menuConta=!menuConta" :aria-expanded="menuConta" aria-haspopup="menu" title="A sua conta"><span class="av" style="background:#5b6f7a">{{ ctx.iniciais }}</span><span class="fim-nome">{{ ctx.nome }}<small>A sua conta</small></span></button>
    </nav>
    <div class="main">
      <header class="topo">
        <button class="icone-btn btn-gaveta" @click="gaveta=true" title="Menu" aria-label="Abrir o menu"><Icone n="menu"/></button>
        <div style="position:relative">
          <button class="icone-btn" :class="{ativo: seletor}" @click="seletor=!seletor" title="Todas as apps"><Icone n="apps"/></button>
          <div class="cartao seletor-apps" v-if="seletor" @click.self="seletor=false">
            <h6>As suas apps</h6>
            <div class="seletor-grelha">
              <button v-for="a in LISTA_APPS" :key="a.chave" class="seletor-app" :class="{atual: a.chave===APP_ATUAL}" @click="irApp(a)"><span class="q q-app"><img :src="srcApp(a.chave)" alt=""></span>{{ a.nome }}</button>
            </div>
            <div class="sub" style="font-size:12px;margin-top:8px">Cada app abre no seu separador; se já estiver aberta, volta a ele.</div>
          </div>
        </div>
        <div class="pesquisa"><Icone n="lupa"/><input id="pesq" v-model="q" placeholder="Pesquisar contactos, empresas, negócios, tickets…" @keydown="teclaPesq" autocomplete="off"><kbd>⌘K</kbd>
          <div class="cartao resultados" v-if="res.length">
            <div class="linha" v-for="(r,i) in res" :key="r.doctype+r.name" :class="{sel:i===selRes}" @mousedown.prevent="irRes(r)">
              <span class="etq">{{ r.tipo }}</span><div class="cresce">{{ r.titulo }}<small>{{ r.sub }}</small></div></div>
          </div>
        </div>
        <div style="margin-left:auto;display:flex;gap:6px;align-items:center">
          <Sino/>
          <button class="icone-btn fora-gaveta" @click="tema" title="Claro / escuro"><Icone n="lua"/></button>
          <a class="icone-btn fora-gaveta" :href="'#/definicoes'" :title="'Definições — ' + APP.nome" :class="{ativo: ecra==='definicoes'}"><Icone n="roda"/></a>
        </div>
      </header>
      <main class="ecra">
        <div v-if="APP_ATUAL==='admin' && ctx.admin === false" class="vazio">A Administração é só para os administradores do Orbit da sua empresa.<br><a href="/">Voltar ao início</a></div>
        <div v-else-if="estado.erroEcra" class="vazio">{{ estado.erroEcra }}<br><a href="javascript:history.back()">Voltar</a></div>
        <template v-else>
        <Inicio v-if="ecra==='inicio'" :ctx="ctx"/>
        <Lista v-else-if="['contactos','empresas','negocios','leads'].includes(ecra)" :objeto="ecra" :key="ecra"/>
        <Ficha v-else-if="ROTAS_DT[ecra]" :doctype="ROTAS_DT[ecra]" :name="partes[1]" :key="ecra+partes[1]"/>
        <Funil v-else-if="ecra==='funil'"/>
        <Caixa v-else-if="ecra==='caixa'" :abrir-id="partes[1]"/>
        <Definicoes v-else-if="ecra==='definicoes' && !partes[1]" :grupos-app="APP.defs" :nome-app="APP.nome"/>
        <DefCampos v-else-if="ecra==='definicoes' && partes[1]==='campos'" key="campos"/>
        <DeskTickets v-else-if="ecra==='tickets'" key="tickets"/>
        <DeskTicket v-else-if="ecra==='ticket'" :nome="partes[1]" :key="'t'+partes[1]"/>
        <DeskModelos v-else-if="ecra==='desk-checklists'"/>
        <DefFluxos v-else-if="ecra==='definicoes' && partes[1]==='fluxos'" key="fluxos"/>
        <DefFunis v-else-if="ecra==='definicoes' && partes[1]==='funis'" key="funis"/>
        <DefFormularios v-else-if="ecra==='definicoes' && partes[1]==='formularios'" key="formularios"/>
        <DefUtilizadores v-else-if="ecra==='definicoes' && partes[1]==='utilizadores'" key="utilizadores"/>
        <DefEmpresas v-else-if="ecra==='definicoes' && partes[1]==='empresas'" key="empresas"/>
        <DefConsulta v-else-if="ecra==='definicoes' && partes[1]==='caixas'" :chave="partes[1]" :key="partes[1]"/>
        <DefLista v-else-if="ecra==='definicoes'" :chave="partes[1]" :key="partes[1]"/>
        <Tarefas v-else-if="ecra==='tarefas'"/>
        <Assinaturas v-else-if="ecra==='assinaturas'"/>
        <Tempo v-else-if="ecra==='tempo'"/>
        <Chat v-else-if="ecra==='chat'"/>
        <Duplicados v-else-if="ecra==='duplicados'" :tipo="partes[1]" :key="partes[1]"/>
        <Fila v-else-if="ecra==='fila'"/>
        <Projetos v-else-if="ecra==='projetos'"/>
        <Projeto v-else-if="ecra==='projeto'" :nome="partes[1]" :key="partes[1]"/>
        <Calendario v-else-if="ecra==='calendario'" :nova="partes[1]==='nova'" :ref-dt="partes[2]" :ref-dn="partes[3]" :key="rotaCal"/>
        <AppEmbutida v-else-if="ecra==='app'" :nome="partes[1]" :key="partes[1]"/>
        <ErpModulo v-else-if="ecra==='erp-m'" :barra="partes[1]" :key="'m'+partes[1]"/>
        <ErpPainel v-else-if="ecra==='erp-painel'" :nome="partes[1]" :key="'pn'+partes[1]"/>
        <ErpContas v-else-if="ecra==='contas'" :lado="partes[1]==='pagar' ? 'pagar' : 'receber'" :key="'ct'+partes[1]"/>
        <ErpImportar v-else-if="ecra==='importar-erp'" :doctype="partes[1]" :key="'im'+partes[1]"/>
        <ErpLista v-else-if="ecra==='erp' && !partes[2]" :doctype="partes[1]" :key="'l'+partes[1]"/>
        <ErpProposta v-else-if="ecra==='erp' && partes[1]==='Quotation' && partes[3]!=='completa'" :name="partes[2]" :key="'p'+partes[2]"/>
        <ErpEmitir v-else-if="ecra==='erp' && (partes[1]==='Sales Invoice' || partes[1]==='Delivery Note') && partes[3]!=='completa'" :dt="partes[1]" :name="partes[2]" :key="'e'+partes[1]+'/'+partes[2]"/>
        <ErpRecibo v-else-if="ecra==='erp' && partes[1]==='Payment Entry' && partes[3]!=='completa'" :name="partes[2]" :key="'r'+partes[2]"/>
        <ErpFicha v-else-if="ecra==='erp'" :doctype="partes[1]" :name="partes[2]" :key="'f'+partes[1]+'/'+partes[2]"/>
        <ErpStock v-else-if="ecra==='erp-stock'" :artigo="partes[1]" :key="'s'+(partes[1]||'')"/>
        <ErpPessoas v-else-if="ecra==='pessoas'"/>
        <RhAprovar v-else-if="ecra==='rh-aprovar'"/>
        <CrmPainel v-else-if="ecra==='crm-painel'"/>
        <DeskPainel v-else-if="ecra==='desk-painel'"/>
        <DeskKb v-else-if="ecra==='desk-kb'"/>
        <MktSegmentos v-else-if="ecra==='mkt-segmentos'"/>
        <MktMarcadores v-else-if="ecra==='mkt-marcadores'"/>
        <MktModelos v-else-if="ecra==='mkt-modelos'"/>
        <RhAusencias v-else-if="ecra==='rh-ausencias'"/>
        <Compras v-else-if="ecra==='compras'" :nome="partes[1]" :key="'c'+(partes[1]||'')"/>
        <ErpRelatorio v-else-if="ecra==='erp-rel'" :nome="partes[1]" :key="'r'+partes[1]"/>
        <ErpDesk v-else-if="ecra==='erp-desk'" :url="partes.slice(1).join('/')" :key="'d'+partes.slice(1).join('/')"/>
        <div v-else class="vazio">Página desconhecida. <a href="#/inicio">Início</a></div>
        </template>
      </main>
    </div>
    <nav class="menu-movel" aria-label="Navegação">
      <a v-for="m in MOVEL" :key="m.rota" :href="'#/'+m.rota" style="text-decoration:none"><button :class="{ativo: ativoNav(m.n)}" tabindex="-1"><Icone :n="m.ic"/><span>{{ m.r }}</span></button></a>
      <button @click="gaveta=true" :class="{ativo: gaveta}"><Icone n="menu"/><span>Menu</span></button>
    </nav>
    <div class="toast" v-if="estado.toast">{{ estado.toast }}</div>
    <div v-if="estado.perda" class="modal-fundo"><div class="modal" style="max-width:460px">
      <header><b>{{ estado.perda.titulo }}</b><button class="btn sm" @click="estado.perda.resolve(null); estado.perda=null">Cancelar</button></header>
      <form class="reg-form" @submit.prevent="estado.perda.resolve({motivo: estado.perda.motivo, notas: estado.perda.notas}); estado.perda=null">
        <label class="erp-campo"><span>Motivo de perda<span class="obrig">*</span></span><select v-model="estado.perda.motivo" required><option value="" disabled>Escolher…</option><option v-for="m in estado.perda.motivos" :key="m.v" :value="m.v">{{ m.r }}</option></select></label>
        <label class="erp-campo"><span>Notas<span v-if="['Other','Outro'].includes(estado.perda.motivo)" class="obrig">*</span></span><textarea v-model="estado.perda.notas" rows="3" :required="['Other','Outro'].includes(estado.perda.motivo)"></textarea></label>
        <div class="reg-botoes"><button class="btn prim" :disabled="!estado.perda.motivo">Confirmar</button></div></form></div></div>
  </div>
  <div v-else class="arranque">Stratechna Orbit</div>`,
};

const _app = createApp(App).component("AvFoto", AvFoto).component("RegistoMenu", RegistoMenu).component("RegistoLateral", RegistoLateral)
  .component("RegistoHistorico", RegistoHistorico).component("RegistoLigacoes", RegistoLigacoes).component("RegistoArea", RegistoArea).component("TarefaForm", TarefaForm).component("NotaForm", NotaForm).component("ChamadaForm", ChamadaForm).component("ErpArvore", ErpArvore).component("ErpArvoreNo", ErpArvoreNo).component("ErpKanban", ErpKanban).component("ErpCalendario", ErpCalendario).component("MktCiclo", MktCiclo).component("MktComoFica", MktComoFica).component("MktBaseLegal", MktBaseLegal).component("EditorRico", EditorRico).component("ConversaRegisto", ConversaRegisto);
_app.config.globalProperties.emailDoSite = emailDoSite;
// 25-11-2026: um ecrã que falha a carregar (ex.: sem permissão) deixava «A carregar…» para sempre — passa a dizer porquê.
// Só falhas ao ABRIR (setup/mounted): uma falha ao gravar já mostra o aviso e não pode tirar o formulário do ecrã.
_app.config.errorHandler = (err, inst, info) => {
  console.error(err);
  // no Vue de produção o `info` é «…#runtime-<código>»: 0 = setup, m/bm = (before)mounted
  const i = String(info || ""); const cod = (i.match(/#runtime-(\w+)$/) || [])[1];
  const aoAbrir = cod ? ["0", "m", "bm"].includes(cod) : /setup function|mounted hook/i.test(i);
  if (aoAbrir) estado.erroEcra = (err && err.message) || "Não foi possível abrir este ecrã.";
};
_app.mount("#app");
