import { defineConfig } from "astro/config";
import { unified } from "@astrojs/markdown-remark";
import { rehypeFigureCaptions } from "./scripts/rehype-figure-captions.mjs";

export default defineConfig({
  output: "static",
  site: "https://sleet.adventure.pub",
  markdown: {
    processor: unified({
      rehypePlugins: [rehypeFigureCaptions],
    }),
  },
});
