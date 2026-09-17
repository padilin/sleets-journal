import { access, readdir, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import sharp from "sharp";
import { extractSocialImage, resolveSocialImagePath } from "./social-image-paths.mjs";

const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const publicDirectory = path.join(repositoryRoot, "public");
const socialDirectory = path.join(publicDirectory, "social");
const journalDirectory = path.join(repositoryRoot, "src", "content", "journal");
const supportedFormats = new Set(["png", "jpeg", "webp"]);
const expectedWidth = 1200;
const expectedHeight = 630;
const errors = [];

async function collectFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = [];

  for (const entry of entries) {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...(await collectFiles(entryPath)));
    if (entry.isFile()) files.push(entryPath);
  }

  return files;
}

async function validateImage(imagePath) {
  const relativePath = path.relative(repositoryRoot, imagePath);

  try {
    const metadata = await sharp(imagePath).metadata();
    if (!metadata.format || !supportedFormats.has(metadata.format)) {
      errors.push(`${relativePath}: expected PNG, JPEG, or WebP.`);
    }
    if (metadata.width !== expectedWidth || metadata.height !== expectedHeight) {
      errors.push(`${relativePath}: expected ${expectedWidth}x${expectedHeight}, found ${metadata.width}x${metadata.height}.`);
    }
  } catch (error) {
    errors.push(`${relativePath}: could not read image metadata (${error.message}).`);
  }
}

try {
  await access(path.join(socialDirectory, "default.png"));
} catch {
  errors.push("public/social/default.png: required fallback image is missing. Run pnpm generate:social.");
}

let socialImages = [];
try {
  socialImages = (await collectFiles(socialDirectory)).filter((file) => /\.(?:png|jpe?g|webp)$/i.test(file));
} catch {
  errors.push("public/social: social image directory is missing. Run pnpm generate:social.");
}

for (const imagePath of socialImages) await validateImage(imagePath);

for (const entryPath of await collectFiles(journalDirectory)) {
  if (!entryPath.endsWith(".md")) continue;

  const source = await readFile(entryPath, "utf8");
  const frontmatter = source.match(/^---\s*\r?\n([\s\S]*?)\r?\n---/)?.[1];
  if (!frontmatter) continue;

  let image;
  try {
    image = extractSocialImage(frontmatter);
  } catch (error) {
    errors.push(`${path.relative(repositoryRoot, entryPath)}: could not parse frontmatter (${error.message}).`);
    continue;
  }
  if (!image) continue;

  let imagePath;
  try {
    imagePath = resolveSocialImagePath(publicDirectory, socialDirectory, image);
  } catch (error) {
    errors.push(`${path.relative(repositoryRoot, entryPath)}: ${error.message}.`);
    continue;
  }

  try {
    await access(imagePath);
  } catch {
    errors.push(`${path.relative(repositoryRoot, entryPath)}: ${image} does not exist under public/.`);
  }
}

if (errors.length) {
  console.error(errors.map((error) => `- ${error}`).join("\n"));
  process.exitCode = 1;
} else {
  console.log(`Validated ${socialImages.length} social image${socialImages.length === 1 ? "" : "s"}.`);
}
