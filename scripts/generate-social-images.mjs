import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import sharp from "sharp";

const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const sourcePath = path.join(repositoryRoot, "src", "assets", "social", "default.svg");
const outputDirectory = path.join(repositoryRoot, "public", "social");
const outputPath = path.join(outputDirectory, "default.png");

await mkdir(outputDirectory, { recursive: true });
await sharp(sourcePath)
  .resize(1200, 630)
  .png({ compressionLevel: 9, palette: true, quality: 100 })
  .toFile(outputPath);

console.log(`Generated ${path.relative(repositoryRoot, outputPath)} at 1200x630.`);
