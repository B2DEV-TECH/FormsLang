// Rasterizes the brand SVG at 1024px so `tauri icon` can derive the rest.
import sharp from "sharp";

await sharp("../assets/brand/formslang-app-icon.svg", { density: 300 })
  .resize(1024, 1024)
  .png()
  .toFile("icon-1024.png");
console.log("icon-1024.png ok");
