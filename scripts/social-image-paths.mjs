import path from "node:path";
import { parse } from "yaml";

export function extractSocialImage(frontmatter) {
  const data = parse(frontmatter);
  const image = data?.social?.image;
  return typeof image === "string" ? image : undefined;
}

export function resolveSocialImagePath(publicDirectory, socialDirectory, image) {
  const parsedUrl = new URL(image, "https://sleet.adventure.pub");
  if (
    parsedUrl.pathname !== image ||
    !parsedUrl.pathname.startsWith("/social/") ||
    parsedUrl.search ||
    parsedUrl.hash
  ) {
    throw new Error("social image path must be a canonical path under /social/");
  }

  const imagePath = path.resolve(publicDirectory, ...parsedUrl.pathname.split("/").filter(Boolean));
  const relativeToSocial = path.relative(socialDirectory, imagePath);

  if (relativeToSocial.startsWith(`..${path.sep}`) || relativeToSocial === ".." || path.isAbsolute(relativeToSocial)) {
    throw new Error("social image path resolves outside public/social");
  }

  return imagePath;
}
