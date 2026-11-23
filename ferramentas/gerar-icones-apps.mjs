// Gera os ícones de cada app do /orbit (23-11-2026): favicon SVG e PNG 180/192/512 (+ maskable), a partir dos símbolos da
// interface (ICONES em orbit/public/interface/app.js), em branco sobre a cor da app. Correr: node ferramentas/gerar-icones-apps.mjs
import fs from "fs"; import { execFileSync } from "child_process";
const src = fs.readFileSync("orbit/public/interface/app.js", "utf8");
const bloco = src.slice(src.indexOf("const ICONES = {") + "const ICONES = ".length, src.indexOf("};", src.indexOf("const ICONES = {")) + 1);
const ICONES = eval("(" + bloco + ")");
const APPS = { crm: ["pessoa", "#b20009"], desk: ["ticket", "#2563eb"], projetos: ["projeto", "#16a34a"], rh: ["pessoas", "#9333ea"],
  gestao: ["euro", "#d97706"], operacoes: ["cubo", "#0891b2"], marketing: ["megafone", "#db2777"], admin: ["roda", "#475569"] };
const svg = (glifo, cor, cheio, escala) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">` +
  (cheio ? `<rect width="512" height="512" fill="${cor}"/>` : `<rect width="512" height="512" rx="112" fill="${cor}"/>`) +
  `<g transform="translate(${256 - 12 * escala} ${256 - 12 * escala}) scale(${escala})" fill="none" stroke="#fff" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">${glifo}</g></svg>`;
for (const [app, [ic, cor]] of Object.entries(APPS)) {
  const g = ICONES[ic]; if (!g) throw new Error("sem ícone " + ic);
  fs.writeFileSync(`orbit/public/pwa/${app}.svg`, svg(g, cor, false, 13));
  fs.writeFileSync(`/tmp/${app}-cheio.svg`, svg(g, cor, true, 13));
  fs.writeFileSync(`/tmp/${app}-mask.svg`, svg(g, cor, true, 10));
  for (const t of [192, 512]) execFileSync("rsvg-convert", ["-w", String(t), "-h", String(t), "-o", `orbit/public/pwa/${app}-${t}.png`, `orbit/public/pwa/${app}.svg`]);
  execFileSync("rsvg-convert", ["-w", "180", "-h", "180", "-o", `orbit/public/pwa/${app}-180.png`, `/tmp/${app}-cheio.svg`]);
  execFileSync("rsvg-convert", ["-w", "512", "-h", "512", "-o", `orbit/public/pwa/${app}-maskable-512.png`, `/tmp/${app}-mask.svg`]);
}
console.log("ícones gerados:", Object.keys(APPS).join(", "));
