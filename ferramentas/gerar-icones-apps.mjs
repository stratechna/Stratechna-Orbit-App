// Ícones de cada app do /orbit para o browser e o telemóvel (23-11-2026, revisto no mesmo dia: «nós temos ícones próprios
// para cada app») — feitos a partir dos ÍCONES DO ORBIT (orbit/public/icons/apps/<app>.svg, os da grelha de apps), nunca
// de símbolos genéricos. Correr: node ferramentas/gerar-icones-apps.mjs
import fs from "fs"; import { execFileSync } from "child_process";
const APPS = { crm: "crm", desk: "desk", projetos: "erp", rh: "rh", gestao: "erp", operacoes: "erp", marketing: "marketing", admin: "orbit" };
const FUNDO = "#22303d";
for (const [app, ic] of Object.entries(APPS)) {
  const fonte = `orbit/public/icons/apps/${ic}.svg`;
  const corpo = fs.readFileSync(fonte, "utf8").replace(/<\?xml[^>]*>/, "");
  fs.copyFileSync(fonte, `orbit/public/pwa/${app}.svg`);                       // favicon = o próprio ícone
  for (const t of [192, 512]) execFileSync("rsvg-convert", ["-w", String(t), "-h", String(t), "-o", `orbit/public/pwa/${app}-${t}.png`, fonte]);
  // iPhone (180) e «maskable»: quadrado cheio com o fundo do ícone (o sistema arredonda/corta os cantos)
  const cheio = (escala) => `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 512 512"><rect width="512" height="512" fill="${FUNDO}"/>` +
    `<g transform="translate(${256 - 256 * escala} ${256 - 256 * escala}) scale(${escala})">${corpo}</g></svg>`;
  fs.writeFileSync(`/tmp/${app}-cheio.svg`, cheio(1)); fs.writeFileSync(`/tmp/${app}-mask.svg`, cheio(0.8));
  execFileSync("rsvg-convert", ["-w", "180", "-h", "180", "-o", `orbit/public/pwa/${app}-180.png`, `/tmp/${app}-cheio.svg`]);
  execFileSync("rsvg-convert", ["-w", "512", "-h", "512", "-o", `orbit/public/pwa/${app}-maskable-512.png`, `/tmp/${app}-mask.svg`]);
}
console.log("ícones do Orbit:", Object.entries(APPS).map(([a, i]) => a + "←" + i).join(", "));
