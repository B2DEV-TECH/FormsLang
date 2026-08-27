// Renders the FormsLang brand mark into the five icon PNGs the APEX
// application template ships (same filenames the .apx files reference).
// Run from desktop/: node scripts/render-apex-icons.mjs
import sharp from "sharp";

const SRC = "../assets/brand/formslang-app-icon.svg";
const OUT = "../formslang/templates/apexlang26/shared-components/static-files/icons/";

const square = (px, name) =>
  sharp(SRC, { density: 300 }).resize(px, px).png().toFile(OUT + name);

// APEX touch icons use a rounded-rect silhouette; ~18% corner radius.
const rounded = async (px, name) => {
  const r = Math.round(px * 0.18);
  const mask = Buffer.from(
    `<svg width="${px}" height="${px}"><rect width="${px}" height="${px}" rx="${r}" ry="${r}"/></svg>`
  );
  const base = await sharp(SRC, { density: 300 }).resize(px, px).png().toBuffer();
  await sharp(base).composite([{ input: mask, blend: "dest-in" }]).png().toFile(OUT + name);
};

await square(32, "app-icon-32.png");
await square(192, "app-icon-192.png");
await square(512, "app-icon-512.png");
await rounded(144, "app-icon-144-rounded.png");
await rounded(256, "app-icon-256-rounded.png");
console.log("5 APEX template icons rendered from the brand mark");
