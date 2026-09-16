import { defineCollection } from "astro:content";
import { glob } from "astro/loaders";
import { z } from "astro/zod";

const journal = defineCollection({
  loader: glob({
    pattern: "**/*.md",
    base: "./src/content/journal",
  }),
  schema: z.object({
    title: z.string(),
    entry: z.number().int().positive(),
    session: z.number().int().positive(),
    date: z.string(),
    date_display: z.string(),
    session_date: z.string(),
    location: z.string(),
    people: z.array(z.string()).default([]),
    tags: z.array(z.string()).default([]),
    draft: z.boolean().default(false),
  }),
});

export const collections = { journal };
