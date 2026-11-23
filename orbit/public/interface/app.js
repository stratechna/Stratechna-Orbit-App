// Stratechna Orbit — interface única (20-11-2026). Vue 3 sem compilação (vendor/vue.esm-browser.prod.js, MIT):
// não há passo de construção que uma actualização do Frappe possa partir. Fala só com orbit.interface.api.
import { createApp, reactive, ref, computed, watch, onMounted, nextTick } from "./vendor/vue.esm-browser.prod.js";

// ── API ──────────────────────────────────────────────────────────────────────────────────────────────
async function api(metodo, args = {}, post = false) {
  // «erp.meta» → orbit.interface.erp.meta; sem ponto → orbit.interface.api.<metodo>
  const url = metodo.includes(".") ? `/api/method/orbit.interface.${metodo}` : `/api/method/orbit.interface.api.${metodo}`;
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
  if (r.status === 403 || r.status === 401) { location.href = "/login?redirect-to=/orbit"; return; }
  const j = await r.json().catch(() => ({}));
  if (!r.ok) {
    let msg = "Erro";
    try { msg = JSON.parse(JSON.parse(j._server_messages)[0]).message; } catch (e) { msg = j.exception || msg; }
    toast(String(msg).replace(/<[^>]+>/g, ""));
    throw new Error(msg);
  }
  return j.message;
}

// Nomes dos países em PT-PT (o Frappe guarda-os em inglês)
const PAISES_PT = { Portugal: "Portugal", Spain: "Espanha", France: "França", Italy: "Itália", Germany: "Alemanha", Belgium: "Bélgica",
  Netherlands: "Países Baixos", Luxembourg: "Luxemburgo", "United Kingdom": "Reino Unido", Switzerland: "Suíça", Brazil: "Brasil",
  Angola: "Angola", Mozambique: "Moçambique", "Cape Verde": "Cabo Verde" };
// ── Utilitários ──────────────────────────────────────────────────────────────────────────────────────
const estado = reactive({ toast: "" });
let _t;
function toast(m) { estado.toast = m; clearTimeout(_t); _t = setTimeout(() => (estado.toast = ""), 3500); }
const CORES = ["#8a5a44", "#4b7a5a", "#5b6f7a", "#7a4b6e", "#46607e", "#8a7340", "#4f6b6b", "#7a5048"];
function cor(s) { let h = 0; for (const c of String(s || "")) h = (h * 31 + c.charCodeAt(0)) >>> 0; return CORES[h % CORES.length]; }
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
const FAIXA = { gray: "#94a3b8", orange: "#f59e0b", blue: "#60a5fa", yellow: "#facc15", purple: "#a78bfa", green: "#22c55e", red: "#ef4444", black: "#475569" };
const ROTAS_DT = { contacto: "Contact", negocio: "CRM Deal", empresa: "CRM Organization", lead: "CRM Lead" };
const DT_ROTA = Object.fromEntries(Object.entries(ROTAS_DT).map(([k, v]) => [v, k]));
const link = (dt, dn) => `#/${DT_ROTA[dt] || "contacto"}/${encodeURIComponent(dn)}`;

const ICONES = {
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
  chamada: ["tel", "var(--verde-bg)", "var(--verde)"], reuniao: ["cal", "var(--azul-bg)", "var(--azul)"], ticket: ["ticket", "var(--cinza-bg)", "var(--ink-2)"] };


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
    const equipa = ref([]); let sel0 = []; try { sel0 = JSON.parse(localStorage.getItem("orbit.cal.equipa") || "[]"); } catch (e) {}
    const verEquipa = ref(sel0); const ocupado = ref({});
    const carregarEquipa = async () => {
      try { localStorage.setItem("orbit.cal.equipa", JSON.stringify(verEquipa.value)); } catch (e) {}
      if (!verEquipa.value.length || !d.value?.ligado) { ocupado.value = {}; return; }
      const ini = dias.value[0]; const fim = new Date(dias.value[dias.value.length - 1]); fim.setDate(fim.getDate() + 1);
      const r = await apiCal("disponibilidade", { pessoas: verEquipa.value.join(","), inicio: isoDia(ini) + " 00:00:00", fim: isoDia(fim) + " 00:00:00" });
      ocupado.value = r.ocupado || {};
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
        out.push({ k: em + b.inicio, cor: corDe(em), nome: nomeDe(em), top: Math.max((a - HORA0 * 60) / 60 * ALT, 0), alt: Math.max((z - a) / 60 * ALT - 2, 10), esq: (k / n) * 100, larg: 100 / n });
      }));
      return out;
    };
    watch([semana, diaMovel, estreito], carregar);
    onMounted(async () => { await carregar(); equipa.value = await apiCal("equipa"); if (props.nova) abrirNova(); });
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
    const ligar = async () => { await apiCal("ligar", { pwd: pwd.value }, true); pwd.value = ""; toast("Calendário ligado"); carregar(); };
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
    return { equipa, verEquipa, ocupadoDia, procurar, primeiroLivre, semana, d, pwd, sel, form, aGravar, dias, mover, hoje, titulo, disposicao, diaTodo, agoraTop, ehHoje, ligar, hm, abrirNova, gravar, apagar, horas, ALT, link, data, estreito };
  },
  template: `
  <div class="cal">
    <div class="cal-topo">
      <h1>Calendário</h1>
      <div class="cal-nav"><button class="btn sm" @click="mover(-1)">‹</button><button class="btn sm" @click="hoje">Hoje</button><button class="btn sm" @click="mover(1)">›</button><b>{{ titulo }}</b></div>
      <button class="btn prim" @click="abrirNova()" :disabled="d && !d.ligado">+ Nova reunião</button>
    </div>
    <div class="equipa-cal" v-if="d && d.ligado && equipa.length"><span class="sub">Ver também:</span>
      <label v-for="p in equipa" :key="p.email" class="chip-eq" :style="{borderColor:p.cor, background: verEquipa.includes(p.email) ? p.cor : 'transparent', color: verEquipa.includes(p.email) ? '#fff' : 'var(--ink)'}">
        <input type="checkbox" :value="p.email" v-model="verEquipa" style="display:none">{{ p.nome }}</label>
      <span class="sub" style="font-size:12px" v-if="verEquipa.length">ocupado de cada colega, sem detalhes</span></div>
    <div v-if="d && !d.ligado" class="cartao aviso-cal">
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
        <div v-for="o in ocupadoDia(dia)" :key="o.k" class="cal-ocupado" :title="'Ocupado — ' + o.nome" :style="{top:o.top+'px',height:o.alt+'px',left:'calc('+o.esq+'% + 1px)',width:'calc('+o.larg+'% - 2px)',background:o.cor}"><span>{{ o.nome.split(' ')[0] }}</span></div>
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
    let v0 = "minhas"; try { v0 = localStorage.getItem("orbit.tarefas.vista") || "minhas"; } catch (e) {}
    const vista = ref(v0); const itens = ref(null); const q = ref(""); const nova = ref({ titulo: "", data: "", projeto: "" }); const projs = ref([]);
    let tq;
    const carregar = async () => {
      itens.value = await apiT("tarefas", { vista: vista.value, q: q.value });
      if (vista.value === "minhas" && !itens.value.length && !q.value) { vista.value = "equipa"; }
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
    return { vista, itens, q, grupos, feita, nova, criar, projs, link, data };
  },
  template: `
  <div>
    <div class="pad" style="padding-bottom:12px;display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap">
      <div><h1>Tarefas</h1><div class="sub">Do CRM e dos projetos, num só sítio<template v-if="itens"> · {{ itens.length }} por fazer</template></div></div>
      <div style="display:flex;gap:8px"><a class="btn prim" href="#/fila">▶ Começar as minhas tarefas</a><a class="btn" href="#/projetos">Projetos</a></div>
    </div>
    <div class="vistas"><button :class="{ativo:vista==='minhas'}" @click="vista='minhas'">As minhas</button><button :class="{ativo:vista==='equipa'}" @click="vista='equipa'">Equipa</button></div>
    <div class="filtros"><input class="filtro" style="border-style:solid;min-width:220px" v-model="q" placeholder="Procurar tarefas…"></div>
    <form class="cartao compor" style="margin:0 24px 14px" @submit.prevent="criar">
      <input v-model="nova.titulo" placeholder="Nova tarefa…"><input type="date" v-model="nova.data" style="flex:none;width:150px">
      <select v-model="nova.projeto" class="btn sm" style="max-width:220px"><option value="">Sem projeto (CRM)</option><option v-for="p in projs" :key="p.name" :value="p.name">{{ p.project_name }}</option></select>
      <button class="btn sm prim" :disabled="!nova.titulo.trim()">Criar</button>
    </form>
    <div v-if="!itens" class="carregar">A carregar…</div>
    <div v-else-if="!itens.length" class="vazio">Nada por fazer.</div>
    <div v-for="g in grupos" :key="g.g" class="cartao" style="margin:0 24px 14px">
      <header><h2 :style="g.g==='atrasadas'?{color:'var(--acao)'}:{}">{{ g.r }} <span class="sub" style="font-weight:400">{{ g.itens.length }}</span></h2></header>
      <div class="linha" v-for="t in g.itens" :key="t.tipo+t.id">
        <span class="chk" @click="feita(t)" title="Marcar como concluída" style="cursor:pointer"></span>
        <div class="cresce">{{ t.titulo }}<small>
          <a v-if="t.projeto" :href="'#/projeto/'+encodeURIComponent(t.projeto)">{{ t.projeto_nome || t.projeto }}</a>
          <a v-else-if="t.ref" :href="link(t.ref[0],t.ref[1])">{{ t.ref_titulo }}</a>
          <span v-if="t.dono"> · {{ t.dono }}</span></small></div>
        <span class="etq" :class="t.prioridade==='Alta'||t.prioridade==='Urgente'?'ambar':''" v-if="t.prioridade && t.prioridade!=='Média'">{{ t.prioridade }}</span>
        <span class="sub" v-if="t.data">{{ data(t.data,false) }}</span>
      </div>
    </div>
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
    <div class="pad" style="padding-bottom:12px"><h1>Projetos</h1><div class="sub" v-if="d">{{ d.length }} projetos</div></div>
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
    return { p, arrastar, alvo, largar, nova, novaData, criar, data };
  },
  template: `
  <div v-if="p">
    <div class="pad" style="padding-bottom:10px;display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap">
      <div><div style="font-size:13px"><a href="#/projetos">← Projetos</a></div><h1>{{ p.titulo }}</h1>
        <div class="sub">{{ [p.cliente, p.marca].filter(Boolean).join(' · ') }}<template v-if="p.fim"> · até {{ data(p.fim,false) }}</template> · {{ Math.round(p.progresso) }} %<template v-if="p.horas_orcamento"> · {{ p.horas.toFixed(1) }} h de {{ p.horas_orcamento }} h</template><template v-else-if="p.horas"> · {{ p.horas.toFixed(1) }} h registadas</template></div></div>
      <a class="btn" :href="p.classico">Abrir na secretária</a>
    </div>
    <form class="cartao compor" style="margin:0 24px 14px" @submit.prevent="criar"><input v-model="nova" placeholder="Nova tarefa neste projeto…"><input type="date" v-model="novaData" style="flex:none;width:150px"><button class="btn sm prim" :disabled="!nova.trim()">Criar</button></form>
    <div class="funil" :style="{gridTemplateColumns:'repeat('+p.colunas.length+',minmax(220px,1fr))'}">
      <div class="coluna" v-for="c in p.colunas" :key="c.estado" :class="{alvo:alvo===c.estado}" @dragover.prevent="alvo=c.estado" @dragleave="alvo=''" @drop.prevent="largar(c)">
        <header><b>{{ c.rotulo }} <span class="sub" style="font-weight:500">{{ c.cartoes.length }}</span></b></header>
        <div class="cartao negocio" v-for="t in c.cartoes" :key="t.id" :draggable="p.pode_editar" @dragstart="arrastar={...t, estado:c.estado}">
          <h3 style="font-weight:500">{{ t.titulo }}</h3>
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
function textoChat(t) {
  const esc = String(t || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/:([a-z0-9_+\-]+):/g, (m, n) => EMOJIS[n] || m);
  return esc.replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>").replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>').replace(/\n/g, "<br>");
}
const Chat = {
  setup() {
    const conv = ref(null); const sel = ref(null); const msgs = ref(null); const texto = ref(""); const pwd = ref(""); const novoTopico = ref("");
    const pessoas = ref([]); const novaDm = ref(""); let rel;
    const carregarConv = async () => { conv.value = await apiC("conversas"); };
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
    return { conv, sel, msgs, texto, pwd, abrir, ligar, enviar, hora, titulo, textoChat, cor, ini, novoTopico, pessoas, novaDm, abrirDm };
  },
  template: `
  <div class="caixa chat">
    <aside class="canais">
      <template v-if="conv && conv.ligado">
        <h6>Canais</h6>
        <template v-for="c in conv.canais" :key="c.id">
          <button :class="{ativo: sel && !sel.ids && sel.canal===c.id && !sel.topico}" @click="abrir({canal:c.id, nomeCanal:c.nome})"><span class="ponto" :style="{background:c.cor||'var(--ink-3)'}"></span><span class="txt"># {{ c.nome }}</span><span class="n" v-if="c.por_ler">{{ c.por_ler }}</span></button>
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
    const passo = ref(1); const an = ref(null); const mapa = ref({}); const modo = ref("atualizar"); const res = ref(null); const ocupado = ref(false);
    const POST = async (metodo, args) => {
      const r = await fetch(`/api/method/orbit.interface.importar.${metodo}`, { method: "POST", headers: { "X-Frappe-CSRF-Token": window.csrf_token, "Content-Type": "application/json", Accept: "application/json" }, body: JSON.stringify(args) });
      const j = await r.json().catch(() => ({})); if (!r.ok) { let m = "Erro"; try { m = JSON.parse(JSON.parse(j._server_messages)[0]).message; } catch (e) {} toast(m); throw new Error(m); } return j.message; };
    const enviar = async (ev) => {
      const fd = new FormData(); const f = ev.target.files[0]; if (!f) return; fd.append("ficheiro", f); fd.append("objeto", props.objeto); ocupado.value = true;
      try { const r = await fetch("/api/method/orbit.interface.importar.analisar", { method: "POST", body: fd, headers: { "X-Frappe-CSRF-Token": window.csrf_token } });
        const j = await r.json().catch(() => ({})); if (!r.ok) { let m = "Erro"; try { m = JSON.parse(JSON.parse(j._server_messages)[0]).message; } catch (e) {} toast(m); return; }
        an.value = j.message; mapa.value = { ...an.value.sugestao }; passo.value = 2; } finally { ocupado.value = false; } };
    const correr = async (simular) => { ocupado.value = true;
      try { res.value = await POST("executar", { codigo: an.value.codigo, mapeamento: JSON.stringify(mapa.value), modo: modo.value, simular: simular ? 1 : 0 });
        passo.value = simular ? 3 : 4; if (!simular) emit("feito"); } finally { ocupado.value = false; } };
    const usados = computed(() => Object.values(mapa.value).filter(Boolean));
    return { passo, an, mapa, modo, res, ocupado, enviar, correr, usados, TITULOS };
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
  components: { Compositor }, props: ["doctype", "name", "para"], emits: ["fechar", "enviado"],
  setup(props, { emit }) {
    const caixas = ref(null); const f = ref({ conta: "", para: props.para || "", cc: "", assunto: "", texto: "" }); const aEnviar = ref(false);
    onMounted(async () => { caixas.value = await api("minhas_caixas"); f.value.conta = (caixas.value[0] || {}).conta || ""; });
    const esc = (t) => t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    const enviar = async () => {
      if (!f.value.conta || !f.value.para || !f.value.assunto || !f.value.texto.trim()) { toast("Falta a caixa, o destinatário, o assunto ou o texto"); return; }
      aEnviar.value = true;
      try { const html = f.value.texto.trim().split(/\n{2,}/).map((p) => "<p>" + esc(p).replace(/\n/g, "<br>") + "</p>").join("");
        await api("enviar_email", { doctype: props.doctype, name: props.name, conta: f.value.conta, para: f.value.para, cc: f.value.cc, assunto: f.value.assunto, html }, true);
        toast("Email enviado"); emit("enviado"); emit("fechar"); } finally { aEnviar.value = false; }
    };
    return { caixas, f, aEnviar, enviar };
  },
  template: `<div class="modal-fundo" @click.self="$emit('fechar')"><div class="modal" style="max-width:680px"><header><b>Novo email</b><button class="btn sm" @click="$emit('fechar')">Fechar</button></header>
    <div class="corpo-email form-cal">
      <div v-if="caixas && !caixas.length" class="aviso" style="margin:0">Ainda não há caixas ligadas ao CRM de onde possa escrever (ligam-se no portal, em Stratechna Orbit).</div>
      <label>De<select v-model="f.conta"><option v-for="c in caixas||[]" :key="c.conta" :value="c.conta">{{ c.email }}{{ c.privada ? ' (a sua caixa)' : ' (equipa)' }}</option></select></label>
      <div class="linha3" style="grid-template-columns:1fr 1fr"><label>Para<input v-model="f.para"></label><label>Cc<input v-model="f.cc"></label></div>
      <label>Assunto<input v-model="f.assunto"></label>
      <Compositor v-model="f.texto" :doctype="doctype" :name="name" :para="f.para" :linhas="9" @assunto="(a)=>{ if(!f.assunto) f.assunto=a }" @enviar="enviar"/>
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
    const ir = (n) => { aberto.value = false; if (["Contact", "CRM Deal", "CRM Lead", "CRM Organization"].includes(n.document_type)) location.hash = link(n.document_type, n.document_name); else if (n.document_type === "CRM Task") location.hash = "#/tarefas"; };
    return { d, aberto, abrir, ir, data };
  },
  template: `<span class="sino"><button class="icone-btn" @click="abrir" title="Avisos"><Icone n="sino"/><span v-if="d.por_ler" class="sino-n">{{ d.por_ler }}</span></button>
    <div v-if="aberto" class="cartao sino-lista"><header style="padding:10px 14px"><b>Avisos</b></header>
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
    const opsMassa = computed(() => { const o = [["responsavel", "Atribuir responsável"]]; if (["negocios", "leads"].includes(props.objeto)) o.push(["estado", props.objeto === "negocios" ? "Mudar a fase" : "Mudar o estado"]);
      if (["contactos", "empresas"].includes(props.objeto)) o.push(["ciclo", "Mudar a fase do ciclo de vida"]); if (meta.value?.pode_apagar) o.push(["apagar", "Apagar"]); return o; });
    const opcoesMassa = computed(() => { const m = massa.value.acao; const campo = m === "responsavel" ? (props.objeto === "negocios" ? "deal_owner" : props.objeto === "leads" ? "lead_owner" : "orbit_responsavel") : m === "estado" ? "status" : m === "ciclo" ? "orbit_ciclo" : null;
      return campo ? (campoMeta(campo).opcoes || []) : []; });
    const aplicarMassa = async () => {
      const m = massa.value; if (!m.acao) return;
      if (m.acao === "apagar" && !confirm(`Apagar ${sel.value.length} registo(s)? Não se desfaz.`)) return;
      const r = await apiVis("em_massa", { objeto: props.objeto, nomes: JSON.stringify(sel.value), acao: m.acao, valor: m.valor }, true);
      toast(`${r.feitos} atualizado(s)` + (r.falhas.length ? ` · ${r.falhas.length} falharam` : "")); if (r.falhas.length) console.warn(r.falhas);
      massa.value = { acao: "", valor: "" }; carregar();
    };
    const exportar = (soSel) => { const p = new URLSearchParams({ objeto: props.objeto, vista: vista.value, q: q.value, filtros: JSON.stringify(filtros.value),
      colunas: JSON.stringify(colunas.value.map((c) => c.campo)), nomes: soSel ? JSON.stringify(sel.value) : "" });
      window.location.href = "/api/method/orbit.interface.vistas.exportar?" + p.toString(); };
    return { vista, q, linhas, total, mais, pagina, carregar, ordenar, valor, abrir, a, VISTAS, TITULOS, cor, ini, ordem, meta, salvas, salvaAtiva,
      filtros, colunas, novoF, verCols, sel, massa, escolherFixa, escolherSalva, apagarSalva, guardar, campoMeta, rotuloFiltro, juntarFiltro, tirarFiltro,
      alternarCol, todos, opsMassa, opcoesMassa, aplicarMassa, exportar, OPS_TIPO, importar, marca, escolherMarca };
  },
  template: `
  <div>
    <div class="pad" style="padding-bottom:12px;display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap">
      <div><h1>{{ TITULOS[objeto] }}</h1><div class="sub">{{ total }} registos</div></div>
      <div style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn" @click="importar=true">Importar</button><button class="btn" @click="exportar(false)">Exportar</button><a v-if="objeto==='contactos'||objeto==='empresas'" class="btn" :href="'#/duplicados/'+objeto">Duplicados</a><a class="btn" :href="'/crm/' + ({contactos:'contacts',empresas:'organizations',negocios:'deals',leads:'leads'})[objeto]">CRM clássico</a></div>
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
      <button class="btn sm prim" @click="aplicarMassa" :disabled="!massa.acao">Aplicar</button>
      <button class="btn sm" @click="exportar(true)">Exportar seleção</button>
    </div>
    <div class="tabela-wrap" :style="sel.length?{borderTopLeftRadius:0,borderTopRightRadius:0}:{}"><table>
      <thead><tr><th style="width:34px"><input type="checkbox" v-model="todos"></th><th v-for="c in colunas" :key="c.campo" @click="ordenar(c.campo)" style="cursor:pointer">{{ c.rotulo }}<span v-if="ordem.startsWith(c.campo+' ')">{{ ordem.endsWith('asc') ? ' ↑' : ' ↓' }}</span></th></tr></thead>
      <tbody>
        <tr v-for="l in linhas" :key="l.name">
          <td @click.stop><input type="checkbox" :value="l.name" v-model="sel"></td>
          <td v-for="(c,i) in colunas" :key="c.campo" @click="abrir(l)">
            <div v-if="i===0" class="pessoa"><span class="av" :style="{background:cor(l.name)}">{{ ini(valor(l,c.campo)||l.name) }}</span><a href="#" @click.prevent>{{ valor(l,c.campo) || l.name }}</a></div>
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
  </div>`,
};

// ── Separador «Detalhes» da ficha (23-11-2026): todos os campos por secções, em colunas (orbit/interface/detalhes.py) ──
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
  components: { FichaDetalhes, Icone, EmailCorpo, VerDocumento, EnviarAssinatura, NovoEmail },
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
      carregarConv();
    };
    const vendas = ref(null);
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
    const carregarCron = async () => { if (filtro.value === "detalhes") return; cron.value = await api("cronologia", { doctype: props.doctype, name: props.name, tipo: filtro.value }); };
    watch(() => [props.doctype, props.name], () => { f.value = null; cron.value = null; carregar(); });
    watch(filtro, carregarCron);
    onMounted(carregar);
    const editar = (p) => { if (!p.editavel) return; ed.value = p.campo; valorEd.value = p.valor || ""; nextTick(() => document.querySelector(".prop .ed-campo")?.focus()); };
    const gravar = async (p) => {
      if (String(valorEd.value ?? "") === String(p.valor ?? "")) { ed.value = ""; return; }
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
    const mudarFase = async (s) => { await api("guardar", { doctype: "CRM Deal", name: props.name, campo: "status", valor: s }, true); toast("Fase alterada"); carregar(); };
    const NOMES = { "CRM Deal": "Negócios", "Contact": "Contactos", "CRM Organization": "Empresa", "CRM Lead": "Leads" };
    const tit = (dt, r) => dt === "CRM Deal" ? (r.titulo || r.lead_name || r.organization || r.name) : dt === "Contact" ? (r.full_name || r.name) : dt === "CRM Organization" ? (r.organization_name || r.name) : (r.lead_name || r.name);
    const sub = (dt, r) => dt === "CRM Deal" ? [r.estado, r.deal_value ? eur(r.deal_value) : "", r.expected_closure_date ? "fecha a " + data(r.expected_closure_date, false) : ""].filter(Boolean).join(" · ")
      : dt === "Contact" ? [r.designation, r.email_id].filter(Boolean).join(" · ") : dt === "CRM Organization" ? [r.website, r.territory].filter(Boolean).join(" · ") : [r.estado, r.email].filter(Boolean).join(" · ");
    const ic = (t) => IC_EVENTO[t] || IC_EVENTO.nota;
    const marcarEmail = () => { window.__ref_email = (f.value && f.value.email_principal) || ""; };
    const novoEmail = ref(false);
    return { tornarPrincipal, PAISES_PT, alternarCheck, alternarMarca, edMorada, editarMorada, gravarMorada, novoEmail, conv, convForm, aConverter, abrirConversao, converter, pode, assocAberta, assocQ, assocRes, abrirAssoc, procurarAssoc, ligarAssoc, tirarAssoc, vendas, COR_V, tempo, registarTempo, fmtH, assin, assinar, carregarAssin, COR_EST, docs, verDoc, marcarEmail, f, cron, filtro, ed, valorEd, editar, gravar, notaTxt, tarefaTxt, tarefaData, modo, enviarNota, enviarTarefa, procurar, abrirEmail, email,
      grupos, mudarFase, NOMES, tit, sub, link, data, eur, ic, cor, ESTADO_COR };
  },
  template: `
  <div class="ficha" v-if="f">
    <aside class="col-esq">
      <div style="font-size:13px;display:flex;justify-content:space-between"><a href="javascript:history.back()">← Voltar</a><a :href="f.classico">Abrir no CRM clássico</a></div>
      <div class="cabeca">
        <div class="av" :style="{background:cor(f.titulo)}">{{ f.iniciais }}</div>
        <h1>{{ f.titulo }}</h1><div class="sub">{{ f.sub }}</div>
        <div class="acoes-rap">
          <button @click="modo='nota'"><span><Icone n="nota"/></span>Nota</button>
          <button @click="novoEmail=true"><span><Icone n="mail"/></span>Email</button>
          <a v-if="f.telefone" :href="'tel:'+f.telefone" style="all:unset;cursor:pointer;display:flex;flex-direction:column;align-items:center;gap:5px;font-size:12px;color:var(--ink-2)"><span style="width:36px;height:36px;border-radius:50%;border:1px solid var(--line);display:grid;place-items:center;background:var(--surface-2)"><Icone n="tel"/></span>Ligar</a>
          <button @click="modo='tarefa'"><span><Icone n="tarefa"/></span>Tarefa</button>
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
        <button :class="{ativo:filtro==='notas'}" @click="filtro='notas'">Notas</button>
        <button :class="{ativo:filtro==='chamadas'}" @click="filtro='chamadas'">Chamadas</button>
        <button :class="{ativo:filtro==='tarefas'}" @click="filtro='tarefas'">Tarefas</button>
        <button :class="{ativo:filtro==='reunioes'}" @click="filtro='reunioes'">Reuniões</button>
        <button :class="{ativo:filtro==='tickets'}" @click="filtro='tickets'">Tickets</button>
      </div>
      <FichaDetalhes v-if="filtro==='detalhes'" :doctype="doctype" :name="name" :key="doctype+name" @mudou="carregar"/>
      <template v-else>
      <div class="cartao compor" v-if="modo==='nota'"><textarea v-model="notaTxt" rows="1" :placeholder="'Escrever uma nota sobre ' + f.titulo + '…'" @keydown.meta.enter="enviarNota" @keydown.ctrl.enter="enviarNota"></textarea><button class="btn sm prim" @click="enviarNota" :disabled="!notaTxt.trim()">Gravar nota</button></div>
      <div class="cartao compor" v-else><input v-model="tarefaTxt" placeholder="Nova tarefa…" @keyup.enter="enviarTarefa"><input type="date" v-model="tarefaData" style="flex:none;width:150px"><button class="btn sm prim" @click="enviarTarefa" :disabled="!tarefaTxt.trim()">Criar tarefa</button></div>
      <div v-if="!cron" class="carregar">A carregar…</div>
      <template v-else>
        <template v-if="cron.proximos.length"><div class="mes">Próximo</div>
          <div class="evento" v-for="i in cron.proximos" :key="i.tipo+i.id"><div class="ic" :style="{background:ic(i.tipo)[1],color:ic(i.tipo)[2]}"><Icone :n="ic(i.tipo)[0]"/></div>
            <div class="cartao corpo"><header><b>{{ i.titulo }}</b><span :class="i.atrasada?'etq ambar':'sub'">{{ i.atrasada ? 'Atrasada · ' : '' }}{{ data(i.data) }}</span></header><p v-if="i.texto">{{ i.texto }}</p><p v-if="i.quem" class="sub">{{ i.quem }}</p></div></div>
        </template>
        <div v-if="!grupos.length && !cron.proximos.length" class="vazio">Ainda não há atividade.<br><button class="btn sm" style="margin-top:10px" @click="procurar">Procurar emails antigos nas caixas ligadas</button></div>
        <template v-for="g in grupos" :key="g.mes"><div class="mes">{{ g.mes }}</div>
          <div class="evento" v-for="i in g.itens" :key="i.tipo+i.id"><div class="ic" :style="{background:ic(i.tipo)[1],color:ic(i.tipo)[2]}"><Icone :n="ic(i.tipo)[0]"/></div>
            <div class="cartao corpo" :class="{abre:i.tipo==='email'}" @click="abrirEmail(i)">
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
      <template v-for="(lista, dt) in f.assoc" :key="dt">
        <template v-if="lista.length || dt!=='CRM Lead'">
          <div class="bloco-tit">{{ NOMES[dt] }} <span class="sub" style="font-weight:400"><template v-if="pode(dt)"><a href="#" @click.prevent="abrirAssoc(dt)">+ Adicionar</a> · </template>{{ lista.length }}</span></div>
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
      <a v-for="t in f.tickets" :key="t.name" class="assoc" :href="'/helpdesk/tickets/'+t.name" style="display:block;text-decoration:none;color:inherit"><b>#{{ t.name }} {{ t.subject }}</b><small>{{ t.status }} · {{ data(t.modified,false) }}</small></a>
    </aside>

    <NovoEmail v-if="novoEmail" :doctype="doctype" :name="name" :para="f.email_principal" @fechar="novoEmail=false" @enviado="carregarCron()"/>
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
      <div class="modal"><header><div><b>{{ email.assunto }}</b><div class="sub">De {{ email.de }} · para {{ email.para }}<span v-if="email.cc"> · cc {{ email.cc }}</span> · {{ data(email.data) }}</div></div><div style="display:flex;gap:6px"><a class="btn sm prim" :href="'#/caixa/'+encodeURIComponent(email.id)">Responder</a><button class="btn sm" @click="email=null">Fechar</button></div></header>
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
    const carregar = async () => (d.value = await api(tipo.value === "leads" ? "funil_leads" : "funil", { responsavel: resp.value, marca: marca.value }));
    const escolherMarca = (m) => { marca.value = m; gravarLS("orbit.marca." + tipo.value, m); carregar(); };
    const escolherTipo = (t) => { if (t === tipo.value) return; tipo.value = t; gravarLS("orbit.funil.tipo", t); marca.value = ler("orbit.marca." + t, ""); d.value = null; carregar(); };
    watch(resp, carregar); onMounted(carregar);
    const largar = async (col) => {
      const n = arrastar.value; alvo.value = ""; arrastar.value = null;
      if (!n || n.estado === col.estado) return;
      if (tipo.value === "leads") await api("mover_lead", { lead: n.name, estado: col.estado }, true);
      else await api("mover", { negocio: n.name, estado: col.estado }, true);
      toast(`Passou a «${col.rotulo}»`); carregar();
    };
    const total = computed(() => d.value && tipo.value !== "leads" ? d.value.colunas.filter((c) => c.tipo !== "Won").reduce((a, c) => a + c.total, 0) : 0);
    const n = computed(() => d.value ? d.value.colunas.filter((c) => !["Won", "Lost"].includes(c.tipo)).reduce((a, c) => a + c.cartoes.length, 0) : 0);
    return { d, resp, arrastar, alvo, largar, total, n, eur, link, data, FAIXA, marca, escolherMarca, tipo, escolherTipo };
  },
  template: `
  <div>
    <div class="pad" style="padding-bottom:12px;display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap">
      <div><h1>{{ tipo==='leads' ? 'Funil das leads' : 'Funil de negócios' }}</h1><div class="sub" v-if="tipo==='leads'">{{ n }} leads por converter</div><div class="sub" v-else>{{ n }} em curso · {{ eur(total) }} · ganhos dos últimos 30 dias</div></div>
      <div style="display:flex;gap:8px;flex-wrap:wrap"><div class="seg"><button class="btn" :class="{prim: tipo==='leads'}" @click="escolherTipo('leads')">Leads</button><button class="btn" :class="{prim: tipo==='negocios'}" @click="escolherTipo('negocios')">Negócios</button></div>
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
        <header><b>{{ c.rotulo }} <span class="sub" style="font-weight:500">{{ c.cartoes.length }}</span></b><small v-if="tipo!=='leads'">{{ eur(c.total) }}</small><div class="faixa" :style="{background:FAIXA[c.cor]||'#94a3b8'}"></div></header>
        <a class="cartao negocio" v-for="x in c.cartoes" :key="x.name" :href="link(tipo==='leads' ? 'CRM Lead' : 'CRM Deal', x.name)" draggable="true" @dragstart="arrastar={...x, estado:c.estado}" style="display:block;text-decoration:none;color:inherit">
          <h3>{{ x.titulo }}</h3><div class="sub">{{ x.org }}</div>
          <div class="val"><template v-if="tipo!=='leads'">{{ eur(x.valor) }}</template><span v-else class="sub" style="font-size:12px">{{ x.origem }}</span><span class="av" style="width:22px;height:22px;font-size:10px;background:#5b6f7a" :title="x.dono_nome">{{ x.dono }}</span></div>
          <div class="prox" :class="{atraso:x.atraso}" v-if="x.prox">◷ {{ x.prox }}<template v-if="x.prox_data"> · {{ data(x.prox_data,false) }}</template></div>
          <div class="prox" v-else-if="c.tipo!=='Won' && c.tipo!=='Converted'">Sem próxima tarefa<template v-if="x.parado>7"> · {{ x.parado }} dias parado</template></div>
        </a>
      </div>
    </div>
  </div>`,
};

const Caixa = {
  components: { EmailCorpo, Icone, Compositor },
  props: ["abrirId"],
  setup(props) {
    let c0 = { grupo: "equipa", conta: "" }; try { c0 = JSON.parse(localStorage.getItem("orbit.caixa.canal")) || c0; } catch (e) {}
    const canal = ref(c0); const canais = ref(null); const itens = ref(null); const conv = ref(null);
    const resposta = ref(""); const para = ref(""); const cc = ref(""); const aEnviar = ref(false); const verCc = ref(false);
    const carregar = async () => { itens.value = null; itens.value = await api("caixa", { grupo: canal.value.grupo, conta: canal.value.conta }); };
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
    const escolher = (grupo, conta = "") => { canal.value = { grupo, conta }; try { localStorage.setItem("orbit.caixa.canal", JSON.stringify(canal.value)); } catch (e) {} carregar(); };
    const abrirConversa = async (id) => {
      conv.value = null; resposta.value = ""; cc.value = ""; verCc.value = false;
      conv.value = await api("conversa", { nome: id });
      para.value = conv.value.para || "";
      nextTick(() => { const m = document.querySelector(".msgs"); if (m) m.scrollTop = m.scrollHeight; });
    };
    const abrir = (i) => { if (i.tipo === "ticket") { window.open(i.url, "_blank"); return; } location.hash = "#/caixa/" + encodeURIComponent(i.id); };
    watch(() => props.abrirId, (id) => { if (id) abrirConversa(id); });
    onMounted(async () => { canais.value = await api("canais"); carregar(); if (props.abrirId) abrirConversa(props.abrirId); equipa.value = await api("equipa_atribuir"); });
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
      if (c.conta === "minhas") return "Atribuídas a mim";
      if (c.conta) return c.conta.replace("Orbit CRM · ", "");
      return c.grupo === "privado" ? "As minhas conversas" : "Todas as caixas de equipa";
    });
    return { canal, canais, itens, conv, abrir, data, cor, ini, link, resposta, para, cc, verCc, enviar, aEnviar, escolher, ativo, nomeCanal, equipa, atribuir, aAtribuir };
  },
  template: `
  <div class="caixa caixa3" :class="{'com-conv': !!abrirId}">
    <aside class="canais">
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
      <header><div style="display:flex;justify-content:space-between;align-items:center;gap:8px"><h2 style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ nomeCanal }}</h2><span class="sub" v-if="itens">{{ itens.length }}</span></div>
        <div class="sub" style="font-size:12px;margin-top:4px">{{ canal.grupo==='privado' ? 'Conversas da sua caixa com clientes do CRM — só você as vê.' : canal.grupo==='tickets' ? 'Pedidos de suporte em aberto.' : 'Conversas partilhadas — toda a equipa as vê.' }}</div></header>
      <div v-if="!itens" class="carregar">A carregar…</div>
      <div v-else-if="!itens.length" class="vazio">Nada por aqui.</div>
      <div v-for="i in itens || []" :key="i.tipo+i.id" class="conv" :class="{ativo: abrirId===i.id, nova: i.por_responder}" @click="abrir(i)">
        <span class="av" style="width:30px;height:30px;font-size:11px" :style="{background:cor(i.quem)}">{{ ini(i.quem) }}</span>
        <div style="min-width:0"><div class="linha1"><b>{{ i.quem }}</b><time>{{ data(i.data,false) }}</time></div><p>{{ i.titulo }}</p>
          <div class="meta"><span class="etq" :class="i.tipo==='ticket'?'ambar':i.grupo==='privado'?'roxo':'azul'">{{ i.tipo==='ticket' ? 'Ticket · ' + i.estado : i.grupo==='privado' ? 'Privado' : 'Equipa' }}</span>
            <span class="sub" style="font-size:12px" v-if="i.ref_titulo">{{ i.ref_titulo }}</span><span class="sub" style="font-size:12px" v-if="i.n>1">· {{ i.n }}</span>
            <span class="etq" v-if="i.responsavel_nome" :title="'Responsável: ' + i.responsavel_nome">👤 {{ i.responsavel_nome }}</span></div></div>
      </div>
    </div>
    <div class="fio">
      <template v-if="conv">
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
  props: ["gruposApp", "nomeApp"],
  setup(props) {
    const d0 = ref(null); const nat = ref(null);
    onMounted(async () => { [nat.value, d0.value] = await Promise.all([apiDef("indice"), api("definicoes")]); });
    const daApp = (g) => !props.gruposApp || props.gruposApp.includes(g);
    const grupos = computed(() => { const g = {}; (nat.value || []).filter((x) => daApp(x.grupo)).forEach((x) => (g[x.grupo] = g[x.grupo] || []).push(x)); return g; });
    const d = computed(() => d0.value && d0.value.filter((g) => daApp(g.grupo)));
    return { d, nat, grupos };
  },
  template: `
  <div class="pad">
    <div class="ola"><div><h1>Definições{{ nomeApp ? ' — ' + nomeApp : '' }}</h1><div class="sub">{{ gruposApp ? 'Só o que é desta app. O resto está na Administração.' : 'Tudo o que se configura no Orbit, num só sítio.' }}</div></div></div>
    <div v-if="!d" class="carregar">A carregar…</div>
    <template v-else>
      <div class="grelha-def" style="margin-bottom:22px">
        <div class="cartao" v-for="(itens, g) in grupos" :key="g"><header><h2>{{ g }}</h2></header>
          <a class="linha" v-for="i in itens" :key="i.chave" :href="'#/definicoes/'+i.chave" style="text-decoration:none;color:inherit"><div class="cresce">{{ i.titulo }}</div><span class="sub">{{ i.n }} ›</span></a>
          <a v-if="g==='CRM'" class="linha" href="#/definicoes/campos" style="text-decoration:none;color:inherit"><div class="cresce">Campos personalizados</div><span class="sub">›</span></a>
          <a v-if="g==='Correio'" class="linha" href="#/definicoes/caixas" style="text-decoration:none;color:inherit"><div class="cresce">Caixas ligadas ao Orbit</div><span class="sub">›</span></a>
        </div>
        <div class="cartao" v-if="!gruposApp"><header><h2>Pessoas</h2></header>
          <a class="linha" href="#/definicoes/utilizadores" style="text-decoration:none;color:inherit"><div class="cresce">Utilizadores do Orbit</div><span class="sub">›</span></a></div>
      </div>
      <h2 style="margin:0 0 10px">Mais definições <span class="sub" style="font-weight:400">— abrem na secretária</span></h2>
      <div class="grelha-def">
        <div class="cartao" v-for="g in d" :key="g.grupo"><header><h2>{{ g.grupo }}</h2></header>
          <a class="linha" v-for="i in g.itens" :key="i.url" :href="i.url" style="text-decoration:none;color:inherit"><div class="cresce">{{ i.rotulo }}</div><span class="sub">↗</span></a>
        </div>
      </div>
    </template>
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
const DefLista = {
  props: ["chave"],
  setup(props) {
    const d = ref(null); const ed = ref(null); const nova = ref(null); const arr = ref(null);
    const carregar = async () => { d.value = await apiDef("lista", { chave: props.chave }); };
    onMounted(carregar);
    const editar = (l) => { ed.value = { nome: l.name, valores: Object.fromEntries(d.value.campos.map((c) => [c.campo, l[c.campo] ?? ""])) }; };
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
            <input v-else-if="c.tipo==='Check'" type="checkbox" v-model="ed.valores[c.campo]" :true-value="1" :false-value="0"><input v-else v-model="ed.valores[c.campo]" :type="c.tipo==='Int'?'number':'text'" :disabled="d.nome_fixo && c.campo===d.nome" :title="d.nome_fixo && c.campo===d.nome ? 'Nome interno fixo (usado pelo Orbit)' : ''"></td>
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
  return String(v);
}
const ESTADO_DOC = { 0: ["Rascunho", "ambar"], 1: ["Submetido", "verde"], 2: ["Cancelado", ""] };
const irErp = (dt, dn) => `#/erp/${encodeURIComponent(dt)}` + (dn ? `/${encodeURIComponent(dn)}` : "");

const ErpModulo = {
  props: ["barra"],
  setup(props) {
    const m = ref(null); const nums = ref([]);
    onMounted(async () => { m.value = await api("erp.menu", { barra: props.barra }); nums.value = await api("erp.numeros", { barra: props.barra }).catch(() => []); });
    const href = (i) => i.tipo === "doc" ? irErp(i.doctype, i.single ? i.doctype : null) : i.tipo === "rel" ? "#/erp-rel/" + encodeURIComponent(i.relatorio) : "#/erp-desk/" + encodeURIComponent(i.url);
    const valorN = (n) => n.tipo === "Currency" ? new Intl.NumberFormat("pt-PT", { style: "currency", currency: "EUR" }).format(n.valor || 0) : new Intl.NumberFormat("pt-PT").format(n.valor || 0);
    return { m, href, nums, valorN };
  },
  template: `<div v-if="m" class="pad">
    <h1>{{ m.titulo }}</h1><div class="sub" style="margin-bottom:16px">Documentos, configuração e relatórios deste módulo</div>
    <div v-if="nums.length" class="erp-numeros"><div v-for="n in nums" :key="n.rotulo" class="cartao"><small>{{ n.rotulo }}</small><b>{{ valorN(n) }}</b></div></div>
    <div class="erp-mod">
      <section v-for="s in m.secoes" :key="s.titulo" class="cartao erp-sec-mod">
        <header v-if="s.titulo"><b>{{ s.titulo.charAt(0).toUpperCase() + s.titulo.slice(1) }}</b></header>
        <div class="erp-itens"><a v-for="i in s.itens" :key="i.rotulo" :href="href(i)">{{ i.rotulo }}<span v-if="i.tipo==='desk'" class="fora" title="Ainda no ecrã do ERPNext">↗</span></a></div>
      </section>
    </div></div><div v-else class="vazio">A carregar…</div>`,
};

const ErpLista = {
  props: ["doctype"],
  setup(props) {
    const meta = ref(null); const linhas = ref([]); const mais = ref(false); const q = ref(""); const pagina = ref(0);
    const colunas = ref([]); const titulo = ref(null); const a = ref(false); const ordem = ref("modified desc"); let tq;
    const carregar = async (junta = false) => {
      a.value = true;
      const r = await api("erp.lista", { doctype: props.doctype, q: q.value, pagina: pagina.value, ordem: ordem.value });
      linhas.value = junta ? linhas.value.concat(r.linhas) : r.linhas; mais.value = r.mais; colunas.value = r.colunas; titulo.value = r.titulo; a.value = false;
    };
    onMounted(async () => { meta.value = await metaErp(props.doctype); if (meta.value.single) { location.replace(irErp(props.doctype, props.doctype)); return; } carregar(); });
    watch(q, () => { clearTimeout(tq); tq = setTimeout(() => { pagina.value = 0; carregar(); }, 300); });
    const campo = (f) => (meta.value?.campos || []).find((c) => c.fieldname === f) || { fieldname: f, label: f };
    const ordenar = (f) => { ordem.value = ordem.value === f + " desc" ? f + " asc" : f + " desc"; pagina.value = 0; carregar(); };
    const maisLinhas = () => { pagina.value++; carregar(true); };
    const abrir = (n) => { location.hash = irErp(props.doctype, n); };
    return { meta, linhas, mais, q, colunas, titulo, a, campo, textoValor, ordenar, ordem, maisLinhas, abrir, irErp, ESTADO_DOC, cor, ini };
  },
  template: `<div v-if="meta">
    <div class="pad" style="padding-bottom:12px;display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap">
      <div><h1>{{ meta.rotulo }}</h1><div class="sub">{{ linhas.length }}{{ mais ? '+' : '' }} registos</div></div>
      <div style="display:flex;gap:8px"><a v-if="meta.pode.create" class="btn prim" :href="irErp(doctype,'novo')">+ Novo</a></div>
    </div>
    <div class="filtros"><input class="filtro" style="border-style:solid;min-width:260px" v-model="q" :placeholder="'Procurar em ' + meta.rotulo.toLowerCase() + '…'"></div>
    <div class="tabela-wrap"><table>
      <thead><tr><th @click="ordenar(titulo||'name')" style="cursor:pointer">{{ titulo ? campo(titulo).label : 'Nome' }}</th>
        <th v-for="c in colunas" :key="c" @click="ordenar(c)" style="cursor:pointer">{{ campo(c).label }}<span v-if="ordem.startsWith(c+' ')">{{ ordem.endsWith('asc') ? ' ↑' : ' ↓' }}</span></th>
        <th v-if="meta.submetivel">Estado</th></tr></thead>
      <tbody>
        <tr v-for="l in linhas" :key="l.name" @click="abrir(l.name)">
          <td><div class="pessoa"><span class="av" :style="{background:cor(l.name)}">{{ ini(l[titulo]||l.name) }}</span><a :href="irErp(doctype,l.name)" @click.stop>{{ l[titulo] || l.name }}</a></div><small v-if="titulo && l[titulo] && l[titulo]!==l.name" style="color:var(--ink-3)">{{ l.name }}</small></td>
          <td v-for="c in colunas" :key="c">{{ textoValor(campo(c), l[c]) }}</td>
          <td v-if="meta.submetivel"><span class="etq" :class="ESTADO_DOC[l.docstatus||0][1]">{{ l.status || ESTADO_DOC[l.docstatus||0][0] }}</span></td>
        </tr>
      </tbody></table>
      <div v-if="!linhas.length && !a" class="vazio">Sem registos.</div>
    </div>
    <div v-if="mais" style="text-align:center;margin-bottom:24px"><button class="btn" @click="maisLinhas">Carregar mais</button></div>
  </div><div v-else class="vazio">A carregar…</div>`,
};

const ErpLigacao = {
  props: ["modelValue", "alvo", "ro", "filtros"],
  emits: ["update:modelValue"],
  setup(props, { emit }) {
    const txt = ref(props.modelValue || ""); const ops = ref([]); const aberto = ref(false); const campo = ref(null); const pos = ref({}); let tq;
    watch(() => props.modelValue, (v) => { if (v !== txt.value) txt.value = v || ""; });
    // a lista flutua por cima da página (dentro de uma tabela com deslocamento ficava cortada)
    const posicionar = () => { const r = campo.value?.getBoundingClientRect(); if (r) pos.value = { position: "fixed", left: r.left + "px", top: (r.bottom + 4) + "px", width: Math.max(r.width, 260) + "px", right: "auto" }; };
    const procurar = () => { clearTimeout(tq); tq = setTimeout(async () => { if (!props.alvo) return; ops.value = await api("erp.procurar", { doctype: props.alvo, txt: txt.value }); posicionar(); aberto.value = true; }, 200); };
    const escolher = (o) => { txt.value = o.v; emit("update:modelValue", o.v); aberto.value = false; };
    const sair = () => setTimeout(() => { aberto.value = false; if (txt.value !== (props.modelValue || "")) emit("update:modelValue", txt.value || null); }, 150);
    return { txt, ops, aberto, procurar, escolher, sair, irErp, campo, pos };
  },
  template: `<div class="erp-ligacao">
    <input ref="campo" v-model="txt" :disabled="ro" @focus="procurar" @input="procurar" @blur="sair" autocomplete="off">
    <a v-if="modelValue && alvo" class="ir" :href="irErp(alvo, modelValue)" title="Abrir">↗</a>
    <div v-if="aberto && ops.length" class="cartao erp-ops" :style="pos"><div v-for="o in ops" :key="o.v" class="linha" @mousedown.prevent="escolher(o)"><div class="cresce">{{ o.r }}<small v-if="o.d || o.r!==o.v">{{ o.r!==o.v ? o.v : '' }} {{ o.d }}</small></div></div></div>
  </div>`,
};

const ErpCampo = {
  components: { ErpLigacao },
  props: ["c", "doc", "ro", "compacto"],
  setup(props) {
    const v = computed({ get: () => props.doc[props.c.fieldname], set: (x) => { props.doc[props.c.fieldname] = x; } });
    const dt = computed({ get: () => (props.doc[props.c.fieldname] || "").replace(" ", "T").slice(0, 16), set: (x) => { props.doc[props.c.fieldname] = x ? x.replace("T", " ") + ":00" : null; } });
    const num = computed({ get: () => props.doc[props.c.fieldname], set: (x) => { props.doc[props.c.fieldname] = x === "" ? null : Number(x); } });
    const editor = ref(null);
    onMounted(() => { if (editor.value) editor.value.innerHTML = props.doc[props.c.fieldname] || ""; });
    const html = (e) => { props.doc[props.c.fieldname] = e.target.innerHTML; };
    return { v, dt, num, editor, html, textoValor };
  },
  template: `
    <template v-if="c.fieldtype==='Check'"><label class="erp-chk"><input type="checkbox" :checked="!!v" :disabled="ro" @change="v = $event.target.checked ? 1 : 0"> <span v-if="!compacto">{{ c.label }}</span></label></template>
    <select v-else-if="c.fieldtype==='Select'" v-model="v" :disabled="ro"><option v-for="o in c.opcoes" :key="o.v" :value="o.v">{{ o.r }}</option></select>
    <ErpLigacao v-else-if="c.fieldtype==='Link'" v-model="v" :alvo="c.options" :ro="ro"/>
    <ErpLigacao v-else-if="c.fieldtype==='Dynamic Link'" v-model="v" :alvo="doc[c.options]" :ro="ro"/>
    <input v-else-if="['Int','Float','Currency','Percent'].includes(c.fieldtype)" type="number" :step="c.fieldtype==='Int'?1:'any'" v-model="num" :disabled="ro">
    <input v-else-if="c.fieldtype==='Date'" type="date" v-model="v" :disabled="ro">
    <input v-else-if="c.fieldtype==='Datetime'" type="datetime-local" v-model="dt" :disabled="ro">
    <input v-else-if="c.fieldtype==='Time'" type="time" step="1" v-model="v" :disabled="ro">
    <input v-else-if="c.fieldtype==='Password'" type="password" v-model="v" :disabled="ro" autocomplete="new-password">
    <input v-else-if="c.fieldtype==='Color'" type="color" v-model="v" :disabled="ro">
    <div v-else-if="c.fieldtype==='Text Editor'" ref="editor" class="erp-editor" :contenteditable="!ro" @input="html"></div>
    <textarea v-else-if="['Small Text','Text','Long Text'].includes(c.fieldtype) && !compacto" v-model="v" :disabled="ro" rows="3"></textarea>
    <div v-else-if="['Attach','Attach Image'].includes(c.fieldtype)" class="erp-anexo"><a v-if="v" :href="v" target="_blank">{{ String(v).split('/').pop() }}</a><span v-else class="sub">sem ficheiro</span></div>
    <div v-else-if="c.fieldtype==='Read Only'" class="erp-ro">{{ v }}</div>
    <input v-else v-model="v" :disabled="ro" :type="c.options==='Email'?'email':c.options==='Phone'?'tel':'text'">`,
};

const ErpTabela = {
  components: { ErpCampo },
  props: ["c", "doc", "filha", "ro"],
  setup(props) {
    const linhas = computed(() => props.doc[props.c.fieldname] || (props.doc[props.c.fieldname] = []));
    const cols = computed(() => {
      const cs = (props.filha?.campos || []).filter((x) => !ESTRUTURA.includes(x.fieldtype) && !x.hidden && x.fieldtype !== "Table");
      const lv = cs.filter((x) => x.in_list_view); return (lv.length ? lv : cs).slice(0, 6);
    });
    let n = 0;
    const juntar = () => {
      const l = { name: "novo-" + Date.now() + "-" + (n++), doctype: props.c.options };
      if ((props.filha?.campos || []).some((x) => x.fieldname === "qty")) l.qty = 1;   // como o ecrã do ERPNext
      linhas.value.push(l);
    };
    const tirar = (i) => { linhas.value.splice(i, 1); };
    return { linhas, cols, juntar, tirar };
  },
  template: `<div class="erp-tabela">
    <div class="tabela-wrap" style="margin:0"><table>
      <thead><tr><th style="width:34px">#</th><th v-for="x in cols" :key="x.fieldname">{{ x.label }}<span v-if="x.reqd" class="obrig">*</span></th><th v-if="!ro" style="width:34px"></th></tr></thead>
      <tbody><tr v-for="(l,i) in linhas" :key="l.name||i" style="cursor:default">
        <td class="sub">{{ i+1 }}</td>
        <td v-for="x in cols" :key="x.fieldname"><ErpCampo :c="x" :doc="l" :ro="ro || x.read_only" compacto="1"/></td>
        <td v-if="!ro"><button class="icone-btn" title="Tirar linha" @click="tirar(i)">×</button></td>
      </tr></tbody></table>
      <div v-if="!linhas.length" class="vazio" style="padding:12px">Sem linhas.</div>
    </div>
    <button v-if="!ro" class="btn sm" style="margin-top:8px" @click="juntar">+ Linha</button>
  </div>`,
};

const ErpFicha = {
  components: { ErpCampo, ErpTabela },
  props: ["doctype", "name"],
  setup(props) {
    const meta = ref(null); const doc = ref(null); const novo = ref(false); const podeGravar = ref(true); const sujo = ref(false); const a = ref(false);
    const aba = ref(0); const fechadas = ref({}); const nomeNovo = ref(""); const criarOps = ref([]); const aviso = ref("");
    const carregar = async () => {
      meta.value = await metaErp(props.doctype);
      const r = await api("erp.documento", { doctype: props.doctype, name: props.name === "novo" ? undefined : props.name });
      // U3: «Criar →» deixa o documento seguinte preparado (ex.: encomenda → fatura)
      let preparado = null; try { preparado = JSON.parse(sessionStorage.getItem("orbit.erp.novo") || "null"); } catch (e) {}
      if (props.name === "novo" && preparado && preparado.doctype === props.doctype) { r.doc = preparado; sessionStorage.removeItem("orbit.erp.novo"); }
      doc.value = r.doc; novo.value = r.novo; podeGravar.value = r.novo ? meta.value.pode.create : r.pode_gravar; sujo.value = !!(preparado && r.novo);
      memoItens = Object.fromEntries((doc.value.items || []).map((l) => [l.name, l.item_code]));
      ultimaAss = assinatura();
      if (!r.novo && meta.value.submetivel && doc.value.docstatus === 1) criarOps.value = await api("erp.criar_opcoes", { doctype: props.doctype });
    };
    onMounted(carregar);
    watch(doc, (n, o) => { if (o) sujo.value = true; }, { deep: true });
    // U3: recálculo pelo ERPNext (preço da lista, nome, unidade, impostos, totais) — nada é gravado
    let memoItens = {}; let ultimaAss = ""; let tRec;
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
      const r = await api("erp.recalcular", { doctype: props.doctype, dados: JSON.stringify(d) }, true).catch(() => null);
      if (!r) return;
      aviso.value = r.aviso || "";
      if (!r.doc) return;
      memoItens = Object.fromEntries((r.doc.items || []).map((l) => [l.name, l.item_code]));
      doc.value = Object.assign(doc.value, r.doc); ultimaAss = assinatura();
    };
    watch(() => assinatura(), (a) => { if (!meta.value?.transacao || a === ultimaAss) return; ultimaAss = a; clearTimeout(tRec); tRec = setTimeout(recalcular, 500); });
    const criarDe = async (o) => {
      const r = await api("erp.criar_de", { doctype: props.doctype, name: doc.value.name, destino: o.doctype }, true);
      try { sessionStorage.setItem("orbit.erp.novo", JSON.stringify(r.doc)); } catch (e) {}
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
    const soLeitura = computed(() => !podeGravar.value || docstatus.value === 2);
    const roCampo = (c) => soLeitura.value || c.read_only || (docstatus.value === 1 && !c.allow_on_submit) || (c.read_only_depends_on && avaliar(c.read_only_depends_on, doc.value));
    const obrig = (c) => c.reqd || (c.mandatory_depends_on && avaliar(c.mandatory_depends_on, doc.value));
    const visivel = (c) => {
      if (c.hidden || !avaliar(c.depends_on, doc.value)) return false;
      if (roCampo(c) && !novo.value && vazioV(doc.value[c.fieldname]) && c.fieldtype !== "Table") return false;   // como no ERPNext: só-leitura vazio não aparece
      return true;
    };
    const secVisivel = (s) => avaliar(s.depends_on, doc.value) && s.colunas.some((col) => col.some(visivel));
    const abaVisivel = (t) => avaliar(t.depends_on, doc.value) && t.secoes.some(secVisivel);
    const abasVis = computed(() => abas.value.filter(abaVisivel));
    const tituloDoc = computed(() => { const t = meta.value?.titulo; return (t && doc.value?.[t]) || (novo.value ? "Novo — " + meta.value?.rotulo : doc.value?.name); });
    const precisaNome = computed(() => novo.value && meta.value && (!meta.value.nomeacao || meta.value.nomeacao.toLowerCase() === "prompt"));
    const gravar = async () => {
      const falta = meta.value.campos.filter((c) => !ESTRUTURA.includes(c.fieldtype) && visivel(c) && obrig(c) && vazioV(doc.value[c.fieldname]));
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
        doc.value = r.doc; await nextTick(); sujo.value = false; toast(m === "submeter" ? "Submetido" : "Cancelado");
      } finally { a.value = false; }
    };
    const aberta = (s, i) => !(s.collapsible && !fechadas.value[i + ":" + s.label]);
    const alternar = (s, i) => { fechadas.value[i + ":" + s.label] = !fechadas.value[i + ":" + s.label]; };
    return { meta, doc, novo, sujo, a, aba, abasVis, visivel, roCampo, obrig, secVisivel, tituloDoc, gravar, accao, docstatus, soLeitura, aberta, alternar, ESTADO_DOC, irErp, precisaNome, nomeNovo, cor, ini, criarOps, criarDe, moeda, pdf, aviso };
  },
  template: `<div v-if="meta && doc" class="erp-ficha">
    <div class="erp-topo">
      <a class="sub" :href="irErp(doctype)" v-if="!meta.single">← {{ meta.rotulo }}</a>
      <div class="erp-tit"><span class="av" :style="{background:cor(doc.name||'n')}">{{ ini(tituloDoc) }}</span>
        <div class="cresce"><h1>{{ tituloDoc }}</h1><div class="sub">{{ meta.rotulo }}<span v-if="!novo && tituloDoc!==doc.name"> · {{ doc.name }}</span></div></div>
        <span v-if="meta.submetivel && !novo" class="etq" :class="ESTADO_DOC[docstatus][1]">{{ doc.status || ESTADO_DOC[docstatus][0] }}</span>
        <span v-if="sujo" class="etq ambar">Por gravar</span>
        <div class="erp-accoes">
          <button v-if="!soLeitura && (novo || sujo)" class="btn prim" :disabled="a" @click="gravar">Gravar</button>
          <button v-if="meta.pode.submit && docstatus===0 && !novo && !sujo" class="btn" :disabled="a" @click="accao('submeter', ['Sales Invoice','Purchase Invoice'].includes(doctype) ? 'Submeter esta fatura? O documento fiscal certificado é emitido pelo programa de faturação ligado (o Orbit nunca o emite). Depois de submetida só se altera cancelando.' : 'Submeter este documento? Depois de submetido só se altera cancelando.')">Submeter</button>
          <button v-if="meta.pode.cancel && docstatus===1" class="btn" :disabled="a" @click="accao('cancelar','Cancelar este documento?')">Cancelar</button>
          <button v-if="meta.pode.delete && !novo && docstatus!==1 && !meta.single" class="btn" :disabled="a" @click="accao('apagar','Apagar definitivamente este registo?')">Apagar</button>
          <a v-if="meta.transacao && pdf" class="btn" :href="pdf" target="_blank">PDF</a>
          <button v-for="o in criarOps" :key="o.doctype" class="btn" :disabled="a" @click="criarDe(o)">Criar {{ o.rotulo }} →</button>
        </div>
      </div>
      <div v-if="meta.transacao && doc.grand_total !== undefined" class="erp-totais cartao">
        <div><small>Total sem impostos</small><b>{{ moeda(doc.net_total) }}</b></div>
        <div><small>Impostos</small><b>{{ moeda(doc.total_taxes_and_charges) }}</b></div>
        <div v-if="doc.discount_amount"><small>Desconto</small><b>− {{ moeda(doc.discount_amount) }}</b></div>
        <div class="total"><small>Total</small><b>{{ moeda(doc.rounded_total || doc.grand_total) }}</b></div>
        <div v-if="docstatus===1 && doc.outstanding_amount !== undefined"><small>Em dívida</small><b>{{ moeda(doc.outstanding_amount) }}</b></div>
      </div>
      <div v-if="aviso" class="aviso" style="margin-top:8px">{{ aviso }}</div>
      <div v-if="precisaNome" class="erp-campo" style="max-width:420px;margin-top:10px"><label>Nome do registo<span class="obrig">*</span></label><input v-model="nomeNovo"></div>
      <div class="vistas" v-if="abasVis.length>1" style="padding:12px 0 0"><button v-for="(t,i) in abasVis" :key="t.label+i" :class="{ativo: aba===i}" @click="aba=i">{{ t.label }}</button></div>
    </div>
    <div class="erp-corpo" v-if="abasVis[aba]">
      <template v-for="(s,si) in abasVis[aba].secoes" :key="si">
        <section v-if="secVisivel(s)" class="cartao erp-sec">
          <header v-if="s.label" @click="s.collapsible && alternar(s,si)" :style="{cursor: s.collapsible?'pointer':'default'}"><b>{{ s.label }}</b><span v-if="s.collapsible" class="sub">{{ aberta(s,si) ? '▾' : '▸' }}</span></header>
          <div v-show="aberta(s,si)" class="erp-cols" :style="{gridTemplateColumns: 'repeat(' + s.colunas.filter(c=>c.some(visivel)).length + ', minmax(0,1fr))'}">
            <div v-for="(col,ci) in s.colunas.filter(c=>c.some(visivel))" :key="ci">
              <template v-for="c in col" :key="c.fieldname">
                <div v-if="visivel(c)" class="erp-campo" :class="{largo: c.fieldtype==='Table'}">
                  <label v-if="c.fieldtype!=='Check'">{{ c.label }}<span v-if="obrig(c)" class="obrig">*</span></label>
                  <ErpTabela v-if="c.fieldtype==='Table'" :c="c" :doc="doc" :filha="meta.filhas[c.options]" :ro="roCampo(c)"/>
                  <ErpCampo v-else :c="c" :doc="doc" :ro="roCampo(c)"/>
                  <small v-if="c.descricao" class="sub">{{ c.descricao }}</small>
                </div>
              </template>
            </div>
          </div>
        </section>
      </template>
    </div>
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
      <div class="cartao" style="margin-bottom:16px" v-if="r.ofertas.length"><header><b>Stock dos fornecedores</b><span class="sub">não entra no livro de stock</span></header>
        <div class="tabela-wrap" style="margin:0;border:0"><table><thead><tr><th>Fornecedor</th><th>Estado</th><th>Quantidade</th><th>Custo</th><th>Lido em</th></tr></thead>
          <tbody><tr v-for="o in r.ofertas" :key="o.supplier" style="cursor:default"><td>{{ o.supplier }}</td><td><span class="etq" :class="{verde:o.estado_stock==='Em stock', ambar:o.estado_stock==='Sob encomenda'}">{{ o.ausente_desde ? 'Fora do fornecedor' : (o.estado_stock || '—') }}</span></td><td>{{ o.quantidade_conhecida ? num(o.quantidade) : '—' }}</td><td>{{ eur2(o.custo) }}</td><td>{{ data(o.lida_em) }}</td></tr></tbody></table></div></div>
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
    return { m, filtros, val, r, a, falhou, erro, visivel, correr, fmt, numerica, ligacao, grafico, CORES_G, csv, desk, moedaR };
  },
  template: `<div class="pad" v-if="m">
    <div style="display:flex;justify-content:space-between;align-items:flex-end;gap:12px;flex-wrap:wrap;margin-bottom:14px">
      <div><h1>{{ m.rotulo }}</h1><div class="sub">Relatório</div></div>
      <div style="display:flex;gap:8px"><button class="btn prim" :disabled="a" @click="correr">{{ a ? 'A gerar…' : 'Gerar' }}</button><button v-if="r && r.linhas.length" class="btn" @click="csv">Exportar CSV</button><a class="btn" :href="desk">Ecrã do ERPNext</a></div>
    </div>
    <div v-if="falhou" class="cartao vazio">Este relatório ainda não abre aqui. <a :href="desk">Abri-lo no ecrã do ERPNext</a>.</div>
    <template v-else>
      <div class="cartao erp-filtros" v-if="filtros.length"><template v-for="f in filtros" :key="f.fieldname">
        <div v-if="visivel(f)" class="erp-campo"><label v-if="f.fieldtype!=='Check'">{{ f.label }}<span v-if="f.reqd" class="obrig">*</span></label><ErpCampo :c="f" :doc="val"/></div></template></div>
      <div v-if="erro" class="aviso" style="margin:12px 0">{{ erro }}</div>
      <template v-if="r">
        <div v-if="r.resumo.length" class="erp-totais cartao" style="margin:14px 0"><div v-for="s in r.resumo" :key="s.rotulo"><small>{{ s.rotulo }}</small><b :style="{color: s.cor==='Red'?'var(--acao)':s.cor==='Green'?'var(--verde)':'inherit'}">{{ s.tipo==='Currency' ? moedaR(s.valor) : s.valor }}</b></div></div>
        <div v-if="grafico" class="cartao erp-grafico">
          <svg :viewBox="'0 0 ' + Math.max(grafico.labels.length*48, 300) + ' 170'" preserveAspectRatio="none">
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

// ── As apps do Orbit (22-11-2026, maqueta docs/orbit-interface/apps/) ────────────────────────────────────────
// Uma app por área, cada uma no seu separador (/orbit?app=<chave>), com a mesma barra de cima: seletor de apps, nome da
// app, pesquisa, sino, claro/escuro e a roda dentada só com as definições dessa app. Os ecrãs são os mesmos de sempre.
const APP_ATUAL = (new URLSearchParams(location.search).get("app") || "crm").toLowerCase();
const APPS = {
  crm: { nome: "CRM", sub: "Clientes e atendimento", ic: "pessoa", inicio: "inicio",
    nav: [["inicio", "casa", "Início"], ["sec", "CRM"], ["leads", "lead", "Leads"], ["contactos", "pessoa", "Contactos"], ["empresas", "empresa", "Empresas"],
      ["negocios", "negocio", "Negócios"], ["funil", "negocio", "Funil"],
      ["sec", "O meu dia"], ["calendario", "cal", "Calendário"], ["tarefas", "tarefa", "Tarefas"], ["app/Booking", "relogio", "Marcar reuniões"],
      ["sec", "Documentos"], ["assinaturas", "assin", "Assinaturas"]],
    modulos: [], defs: ["CRM", "Correio"] },
  // 22-11-2026 (Vítor): o Desk separado do CRM — quem só faz atendimento tem a sua app.
  desk: { nome: "Desk", sub: "Atendimento", ic: "ticket", inicio: "caixa",
    nav: [["sec", "Atendimento"], ["caixa", "caixa", "Caixa de entrada"]],
    modulos: [], defs: ["Atendimento (Desk)", "Correio"] },
  projetos: { nome: "Projetos", sub: "Projetos, tarefas e tempo", ic: "projeto", inicio: "projetos",
    nav: [["sec", "Trabalho"], ["projetos", "projeto", "Projetos"], ["tarefas", "tarefa", "Tarefas"], ["calendario", "cal", "Calendário"], ["sec", "Tempo"], ["tempo", "relogio", "Registo de horas"]],
    modulos: ["Projects"], defs: ["Pessoas e tempo"] },
  rh: { nome: "RH", sub: "Pessoas e equipa", ic: "pessoas", inicio: "pessoas",
    nav: [["sec", "Pessoas"], ["pessoas", "pessoas", "Colaboradores"]],
    modulos: ["Frappe HR", "Recruitment", "Leaves", "Shift & Attendance", "Performance", "Tenure", "Payroll", "Expenses", "Tax & Benefits"], defs: ["Pessoas e tempo"] },
  gestao: { nome: "Gestão", sub: "Dinheiro e obrigações", ic: "euro", inicio: "",
    nav: [], modulos: ["Invoicing", "Payments", "Banking", "Accounting", "Financial Reports", "Subscription"], defs: ["Vendas e faturação", "Marcas e empresa"] },
  operacoes: { nome: "Operações", sub: "Comprar, produzir, vender", ic: "cubo", inicio: "",
    nav: [["sec", "Stock"], ["erp-stock", "cubo", "Inventário"]],
    modulos: ["Selling", "Buying", "Stock", "Assets", "Manufacturing", "Subcontracting", "Quality"], defs: ["Vendas e faturação"] },
  // 22-11-2026: o Marketing com o mesmo aspecto das outras apps (os ecrãs dele são da secretária, mostrados cá dentro).
  marketing: { nome: "Marketing", sub: "Campanhas e envios", ic: "megafone", inicio: "erp-desk/%2Fdesk%2Fcampanha-de-marketing",
    nav: [["sec", "Campanhas"], ["erp-desk/%2Fdesk%2Fcampanha-de-marketing", "megafone", "Campanhas"], ["erp-desk/%2Fdesk%2Fsegmento-de-marketing", "pessoas", "Segmentos"],
      ["erp-desk/%2Fdesk%2Fmodelos-de-email", "mail", "Modelos de email"], ["sec", "Envios"], ["erp-desk/%2Fdesk%2Fenvio-de-marketing", "caixa", "Envios"],
      ["erp-desk/%2Fdesk%2Fsupressao-de-marketing", "nota", "Supressões"]],
    modulos: [], defs: null },
  admin: { nome: "Administração", sub: "Só administradores", ic: "roda", inicio: "definicoes",
    nav: [["sec", "Plataforma"], ["definicoes", "roda", "Definições do Orbit"], ["definicoes/utilizadores", "pessoas", "Utilizadores"]],
    modulos: ["ERPNext Settings", "Users", "Website", "Integrations", "Automation", "Data", "Email", "Printing", "System"], defs: null },
};
const APP = APPS[APP_ATUAL] || APPS.crm;
// Abrir uma app: volta ao separador onde já está (se foi o Orbit a abri-lo), senão abre um novo.
const abrirApp = (chave, url) => { const w = window.open(url || ("/orbit?app=" + chave), "orbit-" + chave); if (w) w.focus(); };

// ── Aplicação ────────────────────────────────────────────────────────────────────────────────────────
const App = {
  components: { Icone, Inicio, Lista, Ficha, Funil, Caixa, Definicoes, AppEmbutida, ErpModulo, ErpLista, ErpFicha, ErpDesk, ErpStock, ErpPessoas, ErpRelatorio, Calendario, DefLista, DefCampos, DefConsulta, Tarefas, Projetos, Projeto, Documentos, Assinaturas, Tempo, Chat, Duplicados, Fila, Sino },
  setup() {
    const ctx = ref(null); const rota = ref(location.hash || "#/inicio");
    const q = ref(""); const res = ref([]); const selRes = ref(0); let tq;
    window.addEventListener("hashchange", () => { rota.value = location.hash || "#/inicio"; document.querySelector(".ecra")?.scrollTo(0, 0); });
    onMounted(async () => { ctx.value = await api("contexto"); window.__ctx = ctx.value; });
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
    const modulosApp = computed(() => (ctx.value?.modulos || []).filter((m) => APP.modulos.includes(m.chave)));
    // Sem rota: a 1.ª secção da app (o Início no CRM; o 1.º módulo na Gestão e nas Operações).
    watch(ctx, (c) => {
      if (!c || (location.hash && location.hash !== "#/")) return;
      if (APP.inicio) { location.hash = "#/" + APP.inicio; return; }
      const m = modulosApp.value[0]; if (m) location.hash = m.barra ? "#/erp-m/" + encodeURIComponent(m.barra) : "#/" + (APP.nav.find((n) => n[0] !== "sec") || ["inicio"])[0];
    });
    const seletor = ref(false);
    const LISTA_APPS = computed(() => [
      ...Object.entries(APPS).filter(([k]) => k !== "admin" || ctx.value?.admin !== false).map(([k, a]) => ({ chave: k, nome: a.nome, ic: a.ic })),
      ...((ctx.value?.apps) || []).map((a) => ({ chave: a.nome.toLowerCase(), nome: a.nome, ic: a.icone, url: a.url })),
    ]);
    const irApp = (a) => { seletor.value = false; if (a.chave === APP_ATUAL) return; abrirApp(a.chave, a.url); };
    const ativoNav = (n) => { const e = ecra.value; const r = partes.value.join("/"); return n[0] === r || decodeURIComponent(n[0]) === r || e === n[0] || (n[0]==='contactos'&&e==='contacto') || (n[0]==='negocios'&&e==='negocio') || (n[0]==='empresas'&&e==='empresa') || (n[0]==='leads'&&e==='lead') || (n[0]==='projetos'&&e==='projeto') || (n[0]==='tarefas'&&e==='fila'); };
    const rotaCal = computed(() => partes.value.join("/"));
    return { ctx, ecra, partes, q, res, selRes, irRes, teclaPesq, tema, NAV, estado, ROTAS_DT, EMBUTIDAS, rotaCal, APP, APP_ATUAL, modulosApp, seletor, LISTA_APPS, irApp, ativoNav };
  },
  template: `
  <div class="app" v-if="ctx">
    <nav class="nav" aria-label="Navegação principal">
      <div class="marca"><div class="logo"><Icone :n="APP.ic"/></div><div>{{ APP.nome }}<small>{{ APP.sub }}</small></div></div>
      <template v-for="(n,i) in NAV" :key="i">
        <h6 v-if="n[0]==='sec'">{{ n[1] }}</h6>
        <a v-else :href="'#/'+n[0]" style="text-decoration:none"><button :class="{ativo: ativoNav(n)}" tabindex="-1"><Icone :n="n[1]"/>{{ n[2] }}<span class="conta" v-if="n[0]==='caixa' && ctx.contadores.tickets">{{ ctx.contadores.tickets }}</span></button></a>
      </template>
      <template v-if="modulosApp.length"><h6>{{ APP_ATUAL==='admin' ? 'Sistema' : 'Módulos' }}</h6>
      <a v-for="m in modulosApp" :key="m.url" :href="m.barra ? '#/erp-m/'+encodeURIComponent(m.barra) : m.url" :target="m.barra ? null : '_blank'" style="text-decoration:none"><button tabindex="-1" :class="{ativo: ecra==='erp-m' && partes[1]===m.barra}"><Icone n="grelha"/>{{ m.nome }}<span class="fora" v-if="!m.barra">↗</span></button></a></template>
      <a v-if="APP_ATUAL==='crm'" href="/crm" style="text-decoration:none"><button tabindex="-1"><Icone n="antigo"/>CRM clássico</button></a>
      <div class="fim"><div class="av" style="background:#5b6f7a">{{ ctx.iniciais }}</div><div style="min-width:0">{{ ctx.nome }}<br><a href="/?cmd=web_logout" style="color:#7f939d;font-size:12px">Sair</a></div></div>
    </nav>
    <div class="main">
      <header class="topo">
        <div style="position:relative">
          <button class="icone-btn" :class="{ativo: seletor}" @click="seletor=!seletor" title="Todas as apps"><Icone n="apps"/></button>
          <div class="cartao seletor-apps" v-if="seletor" @click.self="seletor=false">
            <h6>As suas apps</h6>
            <div class="seletor-grelha">
              <button v-for="a in LISTA_APPS" :key="a.chave" class="seletor-app" :class="{atual: a.chave===APP_ATUAL}" @click="irApp(a)"><span class="q"><Icone :n="a.ic"/></span>{{ a.nome }}</button>
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
          <button class="icone-btn" @click="tema" title="Claro / escuro"><Icone n="lua"/></button>
          <a class="icone-btn" :href="'#/definicoes'" :title="'Definições — ' + APP.nome" :class="{ativo: ecra==='definicoes'}"><Icone n="roda"/></a>
        </div>
      </header>
      <main class="ecra">
        <Inicio v-if="ecra==='inicio'" :ctx="ctx"/>
        <Lista v-else-if="['contactos','empresas','negocios','leads'].includes(ecra)" :objeto="ecra" :key="ecra"/>
        <Ficha v-else-if="ROTAS_DT[ecra]" :doctype="ROTAS_DT[ecra]" :name="partes[1]" :key="ecra+partes[1]"/>
        <Funil v-else-if="ecra==='funil'"/>
        <Caixa v-else-if="ecra==='caixa'" :abrir-id="partes[1]"/>
        <Definicoes v-else-if="ecra==='definicoes' && !partes[1]" :grupos-app="APP.defs" :nome-app="APP.nome"/>
        <DefCampos v-else-if="ecra==='definicoes' && partes[1]==='campos'" key="campos"/>
        <DefConsulta v-else-if="ecra==='definicoes' && ['caixas','utilizadores'].includes(partes[1])" :chave="partes[1]" :key="partes[1]"/>
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
        <ErpLista v-else-if="ecra==='erp' && !partes[2]" :doctype="partes[1]" :key="'l'+partes[1]"/>
        <ErpFicha v-else-if="ecra==='erp'" :doctype="partes[1]" :name="partes[2]" :key="'f'+partes[1]+'/'+partes[2]"/>
        <ErpStock v-else-if="ecra==='erp-stock'" :artigo="partes[1]" :key="'s'+(partes[1]||'')"/>
        <ErpPessoas v-else-if="ecra==='pessoas'"/>
        <ErpRelatorio v-else-if="ecra==='erp-rel'" :nome="partes[1]" :key="'r'+partes[1]"/>
        <ErpDesk v-else-if="ecra==='erp-desk'" :url="partes.slice(1).join('/')" :key="'d'+partes.slice(1).join('/')"/>
        <div v-else class="vazio">Página desconhecida. <a href="#/inicio">Início</a></div>
      </main>
    </div>
    <nav class="menu-movel" aria-label="Navegação">
      <a v-for="m in [['inicio','Início'],['contactos','Contactos'],['negocios','Negócios'],['caixa','Caixa'],['calendario','Agenda']]" :key="m[0]" :href="'#/'+m[0]" style="text-decoration:none"><button :class="{ativo: ecra===m[0]}" tabindex="-1">{{ m[1] }}</button></a>
    </nav>
    <div class="toast" v-if="estado.toast">{{ estado.toast }}</div>
  </div>
  <div v-else class="arranque">Stratechna Orbit</div>`,
};

createApp(App).mount("#app");
