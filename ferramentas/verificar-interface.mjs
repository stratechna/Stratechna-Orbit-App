// Verificação da interface /orbit antes de construir a imagem (20-11-2026).
// Avalia o app.js com um Vue de mentira: apanha erros de sintaxe e, sobretudo, referências a componentes antes de
// estarem definidos (ReferenceError na carga) — que a verificação de sintaxe deixa passar e deixam o /orbit em branco.
import fs from "fs";
import os from "os";
import path from "path";
const fonte = process.argv[2] || "orbit/public/interface/app.js";
let src = fs.readFileSync(fonte, "utf8");
src = src.replace(/^import .*?from "\.\/vendor\/vue\.esm-browser\.prod\.js";/m,
  "const createApp=()=>({mount(){}}),reactive=(x)=>x,ref=(x)=>({value:x}),computed=()=>({}),watch=()=>{},onMounted=()=>{},nextTick=()=>{};");
globalThis.window = { addEventListener() {}, innerWidth: 1400 };
globalThis.document = { documentElement: { dataset: {} }, querySelector() {} };
globalThis.localStorage = { getItem() { return null; }, setItem() {} };
globalThis.matchMedia = () => ({ matches: false });
globalThis.location = { hash: "" };
const tmp = path.join(os.tmpdir(), "orbit-interface-verificar.mjs");
fs.writeFileSync(tmp, src);
await import(tmp);
console.log("interface /orbit: carrega sem erros");
