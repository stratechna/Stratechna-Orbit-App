// Ícones das apps do Orbit para instalar (computador e telemóvel) e para o separador do browser.
// 23-11-2026: feitos a partir dos ÍCONES DO ORBIT (orbit/public/icons/apps/<app>.svg, os da grelha de apps).
// 25-11-2026 (Vítor, maquete docs/orbit-interface/icones-app/ do stratechna-work, opção «A · Fundo branco»): o símbolo
// passa a ocupar ~75 % do quadrado, traço mais grosso, em ardósia com o pormenor no vermelho da marca, sobre BRANCO.
// Para instalar o quadrado é cheio (o sistema arredonda os cantos); para o separador do browser leva cantos próprios.
//
// Correr: node ferramentas/gerar-icones-apps.mjs                → as apps do /orbit em orbit/public/pwa/
//         node ferramentas/gerar-icones-apps.mjs mail <pasta>   → o Mail (para o Stratechna-Mail, marca/app/)
import fs from "fs"; import { execFileSync } from "child_process";

const ARDOSIA = "#22303d", VERMELHO = "#d4151f", FUNDO = "#ffffff";
const APPS = { crm: "crm", desk: "desk", projetos: "erp", rh: "rh", gestao: "erp", operacoes: "erp", marketing: "marketing", admin: "orbit", orbit: "orbit" };

function desenho(ic) {
  const svg = fs.readFileSync(`orbit/public/icons/apps/${ic}.svg`, "utf8");
  const m = svg.match(/<g[^>]*>([\s\S]*?)<\/g>\s*<\/svg>/);
  if (!m) throw new Error(`sem desenho em ${ic}.svg`);
  return m[1]
    .replace(/#8a9bab/gi, ARDOSIA)
    .replace(/#ea5c55|#f2564a/gi, VERMELHO)
    .replace(/stroke-width="32"/g, 'stroke-width="38"');
}
// escala ~1.18 = o desenho passa de ~47 % para ~75 % do quadrado; no «maskable» fica dentro da zona segura (80 %)
function svg(corpo, { escala = 1.18, cantos = 0 } = {}) {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" fill="none">`
    + `<rect width="512" height="512"${cantos ? ` rx="${cantos}"` : ""} fill="${FUNDO}"/>`
    + `<g transform="translate(256 256) scale(${escala}) translate(-264 -256)" stroke-linecap="round" stroke-linejoin="round">${corpo}</g></svg>`;
}
function png(svgTexto, tamanho, destino) {
  const tmp = `/tmp/orbit-icone-${process.pid}.svg`;
  fs.writeFileSync(tmp, svgTexto);
  execFileSync("rsvg-convert", ["-w", String(tamanho), "-h", String(tamanho), "-o", destino, tmp]);
}

if (process.argv[2] === "mail") {
  const pasta = process.argv[3]; if (!pasta) throw new Error("falta a pasta de saída");
  const c = desenho("mail");
  png(svg(c), 192, `${pasta}/icone-192.png`);
  png(svg(c), 512, `${pasta}/icone-512.png`);
  png(svg(c, { escala: 0.95 }), 512, `${pasta}/icone-maskable-512.png`);
  png(svg(c), 180, `${pasta}/apple-touch-icon.png`);
  fs.writeFileSync(`${pasta}/icone.svg`, svg(c, { cantos: 96 }));          // separador do browser
  for (const t of [16, 32, 48]) png(svg(c, { cantos: 96 }), t, `/tmp/orbit-mail-fav-${t}.png`);
  execFileSync("magick", ["/tmp/orbit-mail-fav-16.png", "/tmp/orbit-mail-fav-32.png", "/tmp/orbit-mail-fav-48.png", `${pasta}/favicon.ico`]);
  console.log("ícones do Mail em", pasta);
} else {
  for (const [app, ic] of Object.entries(APPS)) {
    const c = desenho(ic);
    fs.writeFileSync(`orbit/public/pwa/${app}.svg`, svg(c, { cantos: 96 }));   // separador do browser
    png(svg(c), 192, `orbit/public/pwa/${app}-192.png`);
    png(svg(c), 512, `orbit/public/pwa/${app}-512.png`);
    png(svg(c), 180, `orbit/public/pwa/${app}-180.png`);
    png(svg(c, { escala: 0.95 }), 512, `orbit/public/pwa/${app}-maskable-512.png`);
  }
  console.log("ícones do Orbit:", Object.keys(APPS).join(", "));
}
