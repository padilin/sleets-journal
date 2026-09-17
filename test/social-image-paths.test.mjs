import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";
import { extractSocialImage, resolveSocialImagePath } from "../scripts/social-image-paths.mjs";

const publicDirectory = path.resolve("public");
const socialDirectory = path.join(publicDirectory, "social");

test("extracts a social image from a block mapping", () => {
  const frontmatter = `social:\n  image: "/social/journal/entry.png"\n  image_alt: "Preview"`;
  assert.equal(extractSocialImage(frontmatter), "/social/journal/entry.png");
});

test("extracts a social image from an inline mapping", () => {
  const frontmatter = `social: { image: "/social/journal/entry.png", image_alt: "Preview" }`;
  assert.equal(extractSocialImage(frontmatter), "/social/journal/entry.png");
});

test("resolves canonical social paths inside public/social", () => {
  const resolved = resolveSocialImagePath(publicDirectory, socialDirectory, "/social/journal/entry.png");
  assert.equal(resolved, path.join(socialDirectory, "journal", "entry.png"));
});

test("rejects direct and encoded dot-segment escapes", () => {
  assert.throws(
    () => resolveSocialImagePath(publicDirectory, socialDirectory, "/social/../../other.png"),
    /canonical path/,
  );
  assert.throws(
    () => resolveSocialImagePath(publicDirectory, socialDirectory, "/social/%2e%2e/other.png"),
    /canonical path/,
  );
});
