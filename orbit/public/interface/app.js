// Stratechna Orbit — interface única (20-11-2026). Vue 3 sem compilação (vendor/vue.esm-browser.prod.js, MIT):
// não há passo de construção que uma actualização do Frappe possa partir. Fala só com orbit.interface.api.
import { createApp, reactive, ref, computed, watch, onMounted, nextTick } from "./vendor/vue.esm-browser.prod.js";

// ── API ──────────────────────────────────────────────────────────────────────────────────────────────
async function api(metodo, args = {}, post = false) {
  const url = `/api/method/orbit.interface.api.${metodo}`;
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
  sair: '<path d="M14 4h5v16h-5"/><path d="M10 8l-4 4 4 4M6 12h10"/>', antigo: '<path d="M4 12a8 8 0 108-8"/><path d="M4 4v5h5"/>',
};
const Icone = { props: ["n"], template: `<svg viewBox="0 0 24 24" v-html="html"></svg>`, computed: { html() { return ICONES[this.n] || ""; } } };
const IC_EVENTO = { email: ["mail", "var(--cinza-bg)", "var(--ink-2)"], nota: ["nota", "var(--ambar-bg)", "var(--ambar)"], tarefa: ["tarefa", "var(--ambar-bg)", "var(--ambar)"],
  chamada: ["tel", "var(--verde-bg)", "var(--verde)"], reuniao: ["cal", "var(--azul-bg)", "var(--azul)"], ticket: ["ticket", "var(--cinza-bg)", "var(--ink-2)"] };

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
  contactos: [["full_name", "Nome"], ["company_name", "Empresa"], ["email_id", "Email"], ["mobile_no", "Telemóvel"], ["owner_nome", "Criado por"], ["ultimo_email", "Último email"]],
  empresas: [["organization_name", "Empresa"], ["website", "Site"], ["telefone", "Telefone"], ["industry", "Setor"], ["territory", "Território"], ["estado_conta", "Estado"]],
  negocios: [["titulo", "Negócio"], ["organization", "Empresa"], ["estado", "Fase"], ["deal_value", "Valor"], ["expected_closure_date", "Fecho previsto"], ["deal_owner_nome", "Responsável"]],
  leads: [["lead_name", "Nome"], ["organization", "Empresa"], ["email", "Email"], ["estado", "Estado"], ["source", "Origem"], ["lead_owner_nome", "Responsável"]],
};
const TITULOS = { contactos: "Contactos", empresas: "Empresas", negocios: "Negócios", leads: "Leads" };
const VISTAS = { contactos: [["todos", "Todos"], ["meus", "Os meus"], ["parados", "Sem atividade há 30 dias"]],
  empresas: [["todos", "Todas"], ["meus", "As minhas"], ["parados", "Sem atividade há 30 dias"]],
  negocios: [["abertos", "Em curso"], ["todos", "Todos"], ["meus", "Os meus"], ["parados", "Parados há 30 dias"]],
  leads: [["todos", "Por converter"], ["meus", "As minhas"], ["parados", "Sem atividade há 30 dias"]] };
const DT_LISTA = { contactos: "Contact", empresas: "CRM Organization", negocios: "CRM Deal", leads: "CRM Lead" };

const Lista = {
  props: ["objeto"],
  setup(props) {
    const chaveVista = () => `orbit.vista.${props.objeto}`;
    let guardada = null; try { guardada = localStorage.getItem(chaveVista()); } catch (e) {}
    const vista = ref(guardada || VISTAS[props.objeto][0][0]);
    const q = ref(""); const linhas = ref([]); const total = ref(0); const mais = ref(false); const pagina = ref(0); const ordem = ref("modified desc"); const a = ref(false);
    let tq;
    const carregar = async (junta = false) => {
      a.value = true;
      const r = await api("lista", { objeto: props.objeto, vista: vista.value, q: q.value, pagina: pagina.value, ordem: ordem.value });
      linhas.value = junta ? linhas.value.concat(r.linhas) : r.linhas; total.value = r.total; mais.value = r.mais; a.value = false;
    };
    watch(vista, (v) => { try { localStorage.setItem(chaveVista(), v); } catch (e) {} pagina.value = 0; carregar(); });
    watch(q, () => { clearTimeout(tq); tq = setTimeout(() => { pagina.value = 0; carregar(); }, 300); });
    watch(() => props.objeto, () => { vista.value = VISTAS[props.objeto][0][0]; q.value = ""; pagina.value = 0; carregar(); });
    onMounted(() => carregar());
    const ordenar = (c) => { ordem.value = ordem.value === `${c} desc` ? `${c} asc` : `${c} desc`; pagina.value = 0; carregar(); };
    const valor = (l, c) => c === "deal_value" ? eur(l[c]) : (c === "ultimo_email" || c === "expected_closure_date") ? data(l[c], false) : l[c];
    const abrir = (l) => (location.hash = link(DT_LISTA[props.objeto], l.name));
    return { vista, q, linhas, total, mais, pagina, carregar, ordenar, valor, abrir, a, VISTAS, COLUNAS, TITULOS, cor, ini, ordem };
  },
  template: `
  <div>
    <div class="pad" style="padding-bottom:12px;display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap">
      <div><h1>{{ TITULOS[objeto] }}</h1><div class="sub">{{ total }} registos</div></div>
      <div style="display:flex;gap:8px"><a class="btn" :href="'/crm/' + ({contactos:'contacts',empresas:'organizations',negocios:'deals',leads:'leads'})[objeto]">Abrir no CRM clássico</a></div>
    </div>
    <div class="vistas"><button v-for="v in VISTAS[objeto]" :key="v[0]" :class="{ativo: vista===v[0]}" @click="vista=v[0]">{{ v[1] }}</button></div>
    <div class="filtros"><input class="filtro" style="border-style:solid;min-width:240px" v-model="q" :placeholder="'Procurar em ' + TITULOS[objeto].toLowerCase() + '…'"></div>
    <div class="tabela-wrap"><table>
      <thead><tr><th v-for="c in COLUNAS[objeto]" :key="c[0]" @click="ordenar(c[0])" style="cursor:pointer">{{ c[1] }}<span v-if="ordem.startsWith(c[0]+' ')">{{ ordem.endsWith('asc') ? ' ↑' : ' ↓' }}</span></th></tr></thead>
      <tbody>
        <tr v-for="l in linhas" :key="l.name" @click="abrir(l)">
          <td v-for="(c,i) in COLUNAS[objeto]" :key="c[0]">
            <div v-if="i===0" class="pessoa"><span class="av" :style="{background:cor(l.name)}">{{ ini(l[c[0]]||l.name) }}</span><a :href="'#'" @click.prevent>{{ l[c[0]] || l.name }}</a></div>
            <span v-else-if="c[0]==='estado'" class="etq">{{ l.estado }}</span>
            <span v-else>{{ valor(l,c[0]) }}</span>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-if="!a && !linhas.length" class="vazio">Nada encontrado.</div>
    <div class="mais-linhas" v-if="mais"><button class="btn sm" @click="pagina++; carregar(true)">Mostrar mais</button></div>
    </div>
  </div>`,
};

const Ficha = {
  components: { Icone },
  props: ["doctype", "name"],
  setup(props) {
    const f = ref(null); const cron = ref(null); const filtro = ref(""); const ed = ref(""); const valorEd = ref("");
    const notaTxt = ref(""); const tarefaTxt = ref(""); const tarefaData = ref(""); const modo = ref("nota"); const email = ref(null);
    const carregar = async () => {
      f.value = await api("ficha", { doctype: props.doctype, name: props.name });
      carregarCron();
    };
    const carregarCron = async () => (cron.value = await api("cronologia", { doctype: props.doctype, name: props.name, tipo: filtro.value }));
    watch(() => [props.doctype, props.name], () => { f.value = null; cron.value = null; carregar(); });
    watch(filtro, carregarCron);
    onMounted(carregar);
    const editar = (p) => { if (!p.editavel) return; ed.value = p.campo; valorEd.value = p.valor || ""; nextTick(() => document.querySelector(".prop .ed-campo")?.focus()); };
    const gravar = async (p) => {
      if (valorEd.value === (p.valor || "")) { ed.value = ""; return; }
      await api("guardar", { doctype: props.doctype, name: props.name, campo: p.campo, valor: valorEd.value }, true);
      ed.value = ""; toast("Gravado"); carregar();
    };
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
    return { f, cron, filtro, ed, valorEd, editar, gravar, notaTxt, tarefaTxt, tarefaData, modo, enviarNota, enviarTarefa, procurar, abrirEmail, email,
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
          <a v-if="f.email_principal" :href="'mailto:'+f.email_principal" style="all:unset;cursor:pointer;display:flex;flex-direction:column;align-items:center;gap:5px;font-size:12px;color:var(--ink-2)"><span style="width:36px;height:36px;border-radius:50%;border:1px solid var(--line);display:grid;place-items:center;background:var(--surface-2)"><Icone n="mail"/></span>Email</a>
          <a v-if="f.telefone" :href="'tel:'+f.telefone" style="all:unset;cursor:pointer;display:flex;flex-direction:column;align-items:center;gap:5px;font-size:12px;color:var(--ink-2)"><span style="width:36px;height:36px;border-radius:50%;border:1px solid var(--line);display:grid;place-items:center;background:var(--surface-2)"><Icone n="tel"/></span>Ligar</a>
          <button @click="modo='tarefa'"><span><Icone n="tarefa"/></span>Tarefa</button>
        </div>
      </div>
      <div v-if="f.estados.length" style="margin-top:14px">
        <label class="sub" style="font-size:12px">Fase do negócio</label>
        <div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:6px">
          <button v-for="s in f.estados" :key="s.name" class="btn sm" :class="{prim: f.props.find(p=>p.campo==='status')?.valor===s.name}" @click="mudarFase(s.name)" :disabled="!f.pode_editar">{{ s.rotulo }}</button>
        </div>
      </div>
      <div class="bloco-tit">Sobre este registo</div>
      <div class="prop" v-for="p in f.props" :key="p.campo">
        <label>{{ p.rotulo }}</label>
        <template v-if="ed===p.campo">
          <select v-if="p.opcoes" class="ed-campo" v-model="valorEd" @change="gravar(p)" @blur="ed=''"><option v-for="o in p.opcoes" :value="o">{{ p.rotulos[o] || o || '—' }}</option></select>
          <input v-else class="ed-campo" v-model="valorEd" :type="p.tipo==='Date'?'date':(p.tipo==='Currency'||p.tipo==='Percent')?'number':'text'" @keyup.enter="gravar(p)" @keyup.esc="ed=''" @blur="gravar(p)">
        </template>
        <div v-else :class="{ed:p.editavel}" @click="editar(p)">
          <span v-if="p.tipo==='Currency'">{{ p.valor ? eur(p.valor) : '—' }}</span>
          <span v-else-if="p.tipo==='Datetime'||p.tipo==='Date'">{{ p.valor ? data(p.valor, p.tipo==='Datetime') : '—' }}</span>
          <span v-else-if="p.tipo==='Percent'">{{ p.valor!=null ? p.valor+' %' : '—' }}</span>
          <span v-else>{{ (p.rotulos && p.rotulos[p.valor]) || p.mostra || p.valor || '—' }}</span>
        </div>
      </div>
    </aside>

    <div class="col-meio">
      <div class="separ">
        <button :class="{ativo:filtro===''}" @click="filtro=''">Atividade</button>
        <button :class="{ativo:filtro==='emails'}" @click="filtro='emails'">Emails <span class="sub">{{ cron?.contagem?.email || '' }}</span></button>
        <button :class="{ativo:filtro==='notas'}" @click="filtro='notas'">Notas</button>
        <button :class="{ativo:filtro==='chamadas'}" @click="filtro='chamadas'">Chamadas</button>
        <button :class="{ativo:filtro==='tarefas'}" @click="filtro='tarefas'">Tarefas</button>
        <button :class="{ativo:filtro==='reunioes'}" @click="filtro='reunioes'">Reuniões</button>
        <button :class="{ativo:filtro==='tickets'}" @click="filtro='tickets'">Tickets</button>
      </div>
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
              <p v-if="i.tipo==='email'" class="sub" style="margin-top:2px">{{ i.sentido==='Sent' ? 'Para ' + (i.para||'') : 'De ' + (i.quem||'') }}<template v-if="i.conta"> · {{ i.conta }}</template> <span v-if="i.privado" class="priv">· só para si</span></p>
              <p v-if="i.texto">{{ i.texto }}</p>
              <p v-if="i.tipo!=='email' && i.quem" class="sub">{{ i.quem }}</p>
              <span v-if="i.tipo==='ticket'" class="etq" :class="i.resolvido?'verde':'ambar'">{{ i.estado }}</span>
            </div></div>
        </template>
        <div v-if="grupos.length" style="text-align:center;margin:16px 0"><button class="btn sm" @click="procurar">Procurar emails antigos nas caixas ligadas</button></div>
      </template>
    </div>

    <aside class="col-dir">
      <template v-for="(lista, dt) in f.assoc" :key="dt">
        <template v-if="lista.length || dt!=='CRM Lead'">
          <div class="bloco-tit">{{ NOMES[dt] }} <span class="sub" style="font-weight:400">{{ lista.length }}</span></div>
          <div v-if="!lista.length" class="sub" style="font-size:13px">—</div>
          <a v-for="r in lista" :key="r.name" class="assoc" :href="link(dt,r.name)" style="display:block;text-decoration:none;color:inherit">
            <b>{{ tit(dt,r) }}</b><small>{{ sub(dt,r) }}</small>
            <div class="barra" v-if="dt==='CRM Deal' && r.probability"><i :style="{width:r.probability+'%'}"></i></div>
          </a>
        </template>
      </template>
      <div class="bloco-tit">Tickets <span class="sub" style="font-weight:400">{{ f.tickets.length }}</span></div>
      <div v-if="!f.tickets.length" class="sub" style="font-size:13px">—</div>
      <a v-for="t in f.tickets" :key="t.name" class="assoc" :href="'/helpdesk/tickets/'+t.name" style="display:block;text-decoration:none;color:inherit"><b>#{{ t.name }} {{ t.subject }}</b><small>{{ t.status }} · {{ data(t.modified,false) }}</small></a>
    </aside>

    <div class="modal-fundo" v-if="email" @click.self="email=null">
      <div class="modal"><header><div><b>{{ email.assunto }}</b><div class="sub">De {{ email.de }} · para {{ email.para }}<span v-if="email.cc"> · cc {{ email.cc }}</span> · {{ data(email.data) }}</div></div><div style="display:flex;gap:6px"><a class="btn sm prim" :href="'#/caixa/'+encodeURIComponent(email.id)">Responder</a><button class="btn sm" @click="email=null">Fechar</button></div></header>
        <div class="corpo-email" v-html="email.html"></div></div>
    </div>
  </div>
  <div v-else class="carregar">A carregar…</div>`,
};

const Funil = {
  setup() {
    const d = ref(null); const resp = ref(""); const arrastar = ref(null); const alvo = ref("");
    const carregar = async () => (d.value = await api("funil", { responsavel: resp.value }));
    watch(resp, carregar); onMounted(carregar);
    const largar = async (col) => {
      const n = arrastar.value; alvo.value = ""; arrastar.value = null;
      if (!n || n.estado === col.estado) return;
      await api("mover", { negocio: n.name, estado: col.estado }, true); toast(`Passou a «${col.rotulo}»`); carregar();
    };
    const total = computed(() => d.value ? d.value.colunas.filter((c) => c.tipo !== "Won").reduce((a, c) => a + c.total, 0) : 0);
    const n = computed(() => d.value ? d.value.colunas.filter((c) => c.tipo !== "Won").reduce((a, c) => a + c.cartoes.length, 0) : 0);
    return { d, resp, arrastar, alvo, largar, total, n, eur, link, data, FAIXA };
  },
  template: `
  <div>
    <div class="pad" style="padding-bottom:12px;display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap">
      <div><h1>Funil de negócios</h1><div class="sub">{{ n }} em curso · {{ eur(total) }} · ganhos dos últimos 30 dias</div></div>
      <div style="display:flex;gap:8px"><select class="btn" v-model="resp"><option value="">Todos os responsáveis</option><option value="eu">Só os meus</option></select><a class="btn" href="#/negocios">Lista</a></div>
    </div>
    <div v-if="!d" class="carregar">A carregar…</div>
    <div class="funil" v-else :style="{gridTemplateColumns:'repeat('+d.colunas.length+',minmax(230px,1fr))'}">
      <div class="coluna" v-for="c in d.colunas" :key="c.estado" :class="{alvo: alvo===c.estado}"
           @dragover.prevent="alvo=c.estado" @dragleave="alvo=''" @drop.prevent="largar(c)">
        <header><b>{{ c.rotulo }} <span class="sub" style="font-weight:500">{{ c.cartoes.length }}</span></b><small>{{ eur(c.total) }}</small><div class="faixa" :style="{background:FAIXA[c.cor]||'#94a3b8'}"></div></header>
        <a class="cartao negocio" v-for="x in c.cartoes" :key="x.name" :href="link('CRM Deal',x.name)" draggable="true" @dragstart="arrastar={...x, estado:c.estado}" style="display:block;text-decoration:none;color:inherit">
          <h3>{{ x.titulo }}</h3><div class="sub">{{ x.org }}</div>
          <div class="val">{{ eur(x.valor) }}<span class="av" style="width:22px;height:22px;font-size:10px;background:#5b6f7a" :title="x.dono_nome">{{ x.dono }}</span></div>
          <div class="prox" :class="{atraso:x.atraso}" v-if="x.prox">◷ {{ x.prox }}<template v-if="x.prox_data"> · {{ data(x.prox_data,false) }}</template></div>
          <div class="prox" v-else-if="c.tipo!=='Won'">Sem próxima tarefa<template v-if="x.parado>7"> · {{ x.parado }} dias parado</template></div>
        </a>
      </div>
    </div>
  </div>`,
};

const Caixa = {
  props: ["abrirId"],
  setup(props) {
    let g0 = "todos"; try { g0 = localStorage.getItem("orbit.caixa.grupo") || "todos"; } catch (e) {}
    const grupo = ref(g0); const itens = ref(null); const sel = ref(null); const conv = ref(null);
    const resposta = ref(""); const para = ref(""); const cc = ref(""); const aEnviar = ref(false); const verCc = ref(false);
    const carregar = async () => { itens.value = await api("caixa", { grupo: grupo.value }); };
    watch(grupo, (v) => { try { localStorage.setItem("orbit.caixa.grupo", v); } catch (e) {} sel.value = null; conv.value = null; carregar(); });
    const abrirConversa = async (id) => {
      conv.value = null; resposta.value = ""; cc.value = ""; verCc.value = false;
      conv.value = await api("conversa", { nome: id });
      para.value = conv.value.para || "";
      nextTick(() => { const m = document.querySelector(".msgs"); if (m) m.scrollTop = m.scrollHeight; });
    };
    const abrir = async (i) => {
      if (i.tipo === "ticket") { window.open(i.url, "_blank"); return; }
      sel.value = i; location.hash = "#/caixa/" + encodeURIComponent(i.id);
    };
    watch(() => props.abrirId, (id) => { if (id) abrirConversa(id); });
    onMounted(() => { carregar(); if (props.abrirId) abrirConversa(props.abrirId); });
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
    const mailUrl = ((window.__ctx && window.__ctx.apps) || []).find((a) => a.nome === "Mail")?.url || "#";
    return { grupo, itens, sel, conv, abrir, data, cor, ini, link, mailUrl, resposta, para, cc, verCc, enviar, aEnviar };
  },
  template: `
  <div class="caixa">
    <div class="lista-conv">
      <header><div style="display:flex;justify-content:space-between;align-items:center"><h2>Caixa de entrada</h2><span class="sub" v-if="itens">{{ itens.length }}</span></div>
        <div style="display:flex;gap:6px;margin-top:10px;flex-wrap:wrap">
          <button class="etq" :class="{azul:grupo==='todos'}" @click="grupo='todos'" style="border:0">Todas</button>
          <button class="etq" :class="{azul:grupo==='equipa'}" @click="grupo='equipa'" style="border:0">Equipa</button>
          <button class="etq" :class="{azul:grupo==='privado'}" @click="grupo='privado'" style="border:0">Privado</button>
        </div></header>
      <div v-if="!itens" class="carregar">A carregar…</div>
      <div v-else-if="!itens.length" class="vazio">Nada por aqui.</div>
      <div v-for="i in itens || []" :key="i.tipo+i.id" class="conv" :class="{ativo: (sel && sel.id===i.id) || abrirId===i.id, nova: i.por_responder}" @click="abrir(i)">
        <span class="av" style="width:30px;height:30px;font-size:11px" :style="{background:cor(i.quem)}">{{ ini(i.quem) }}</span>
        <div style="min-width:0"><div class="linha1"><b>{{ i.quem }}</b><time>{{ data(i.data,false) }}</time></div><p>{{ i.titulo }}</p>
          <div class="meta"><span class="etq" :class="i.tipo==='ticket'?'ambar':i.grupo==='privado'?'roxo':'azul'">{{ i.tipo==='ticket' ? 'Ticket · ' + i.estado : i.grupo==='privado' ? 'Privado' : 'Equipa' }}</span>
            <span class="sub" style="font-size:12px" v-if="i.conta">{{ i.conta }}</span><span class="sub" style="font-size:12px" v-if="i.n>1">{{ i.n }} mensagens</span></div></div>
      </div>
    </div>
    <div class="fio">
      <template v-if="conv">
        <header><div style="min-width:0"><h2>{{ conv.assunto }}</h2><div class="sub">{{ conv.mensagens.length }} mensagens<template v-if="conv.de"> · caixa {{ conv.de }}</template></div></div>
          <div style="display:flex;gap:6px;flex-wrap:wrap"><a v-if="conv.ref[0]" class="btn sm" :href="link(conv.ref[0], conv.ref[1])">Abrir {{ conv.ref_titulo }}</a></div></header>
        <div class="msgs">
          <div class="cartao msg" v-for="m in conv.mensagens" :key="m.id" :class="{nossa:m.enviado}">
            <header><b>{{ m.de }}</b><span>{{ data(m.data) }}</span></header>
            <div class="sub" style="font-size:12px;margin-bottom:8px">Para {{ m.para }}<template v-if="m.cc"> · cc {{ m.cc }}</template></div>
            <div v-html="m.html"></div>
          </div>
        </div>
        <div class="cartao resposta" v-if="conv.pode_responder">
          <div class="tabs" style="flex-wrap:wrap;align-items:center"><span class="sub">De {{ conv.de }} · Para</span>
            <input v-model="para" style="flex:1;min-width:180px;border:0;background:none;font:inherit;color:var(--ink);outline:none">
            <button class="sub" style="all:unset;cursor:pointer;font-size:12px" v-if="!verCc" @click="verCc=true">Cc</button></div>
          <div class="tabs" v-if="verCc"><span class="sub">Cc</span><input v-model="cc" style="flex:1;border:0;background:none;font:inherit;color:var(--ink);outline:none"></div>
          <textarea v-model="resposta" rows="5" placeholder="Escrever a resposta…" @keydown.meta.enter="enviar" @keydown.ctrl.enter="enviar"></textarea>
          <footer><span class="sub">Fica nos Enviados de {{ conv.de }} e na cronologia do cliente · ⌘↵ envia</span><button class="btn prim sm" @click="enviar" :disabled="!resposta.trim() || aEnviar">{{ aEnviar ? 'A enviar…' : 'Enviar' }}</button></footer>
        </div>
        <div v-else class="vazio" style="margin:0 20px 20px">Esta conversa é de uma caixa pessoal de outra pessoa ou de uma caixa sem ligação ao CRM. <a :href="mailUrl" target="_blank">Abrir o Mail</a></div>
      </template>
      <div v-else-if="abrirId" class="carregar">A carregar…</div>
      <div v-else class="vazio">Escolha uma conversa.<br><span class="sub">Equipa = caixas partilhadas e tickets. Privado = as suas conversas com clientes, só visíveis para si.</span></div>
    </div>
  </div>`,
};

// ── Aplicação ────────────────────────────────────────────────────────────────────────────────────────
const App = {
  components: { Icone, Inicio, Lista, Ficha, Funil, Caixa },
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
    const NAV = [["inicio", "casa", "Início"], ["sec", "CRM"], ["contactos", "pessoa", "Contactos"], ["empresas", "empresa", "Empresas"], ["leads", "lead", "Leads"],
      ["negocios", "negocio", "Negócios"], ["funil", "negocio", "Funil"], ["sec", "Atendimento"], ["caixa", "caixa", "Caixa de entrada"]];
    return { ctx, ecra, partes, q, res, selRes, irRes, teclaPesq, tema, NAV, estado, ROTAS_DT };
  },
  template: `
  <div class="app" v-if="ctx">
    <nav class="nav" aria-label="Navegação principal">
      <div class="marca"><div class="logo">O</div><div>Stratechna Orbit<small>{{ ctx.tenant }}</small></div></div>
      <template v-for="(n,i) in NAV" :key="i">
        <h6 v-if="n[0]==='sec'">{{ n[1] }}</h6>
        <a v-else :href="'#/'+n[0]" style="text-decoration:none"><button :class="{ativo: ecra===n[0] || (n[0]==='contactos'&&ecra==='contacto') || (n[0]==='negocios'&&ecra==='negocio') || (n[0]==='empresas'&&ecra==='empresa') || (n[0]==='leads'&&ecra==='lead')}" tabindex="-1"><Icone :n="n[1]"/>{{ n[2] }}<span class="conta" v-if="n[0]==='caixa' && ctx.contadores.tickets">{{ ctx.contadores.tickets }}</span></button></a>
      </template>
      <h6>Apps</h6>
      <a v-for="a in ctx.apps" :key="a.nome" :href="a.url" style="text-decoration:none"><button tabindex="-1"><Icone :n="a.icone"/>{{ a.nome }}</button></a>
      <a href="/crm" style="text-decoration:none"><button tabindex="-1"><Icone n="antigo"/>CRM clássico</button></a>
      <div class="fim"><div class="av" style="background:#5b6f7a">{{ ctx.iniciais }}</div><div style="min-width:0">{{ ctx.nome }}<br><a href="/?cmd=web_logout" style="color:#7f939d;font-size:12px">Sair</a></div></div>
    </nav>
    <div class="main">
      <header class="topo">
        <div class="pesquisa"><Icone n="lupa"/><input id="pesq" v-model="q" placeholder="Pesquisar contactos, empresas, negócios, tickets…" @keydown="teclaPesq" autocomplete="off"><kbd>⌘K</kbd>
          <div class="cartao resultados" v-if="res.length">
            <div class="linha" v-for="(r,i) in res" :key="r.doctype+r.name" :class="{sel:i===selRes}" @mousedown.prevent="irRes(r)">
              <span class="etq">{{ r.tipo }}</span><div class="cresce">{{ r.titulo }}<small>{{ r.sub }}</small></div></div>
          </div>
        </div>
        <div style="margin-left:auto;display:flex;gap:6px;align-items:center">
          <button class="icone-btn" @click="tema" title="Claro / escuro"><Icone n="lua"/></button>
        </div>
      </header>
      <main class="ecra">
        <Inicio v-if="ecra==='inicio'" :ctx="ctx"/>
        <Lista v-else-if="['contactos','empresas','negocios','leads'].includes(ecra)" :objeto="ecra"/>
        <Ficha v-else-if="ROTAS_DT[ecra]" :doctype="ROTAS_DT[ecra]" :name="partes[1]" :key="ecra+partes[1]"/>
        <Funil v-else-if="ecra==='funil'"/>
        <Caixa v-else-if="ecra==='caixa'" :abrir-id="partes[1]"/>
        <div v-else class="vazio">Página desconhecida. <a href="#/inicio">Início</a></div>
      </main>
    </div>
    <nav class="menu-movel" aria-label="Navegação">
      <a v-for="m in [['inicio','Início'],['contactos','Contactos'],['negocios','Negócios'],['funil','Funil'],['caixa','Caixa']]" :key="m[0]" :href="'#/'+m[0]" style="text-decoration:none"><button :class="{ativo: ecra===m[0]}" tabindex="-1">{{ m[1] }}</button></a>
    </nav>
    <div class="toast" v-if="estado.toast">{{ estado.toast }}</div>
  </div>
  <div v-else class="arranque">Stratechna Orbit</div>`,
};

createApp(App).mount("#app");
