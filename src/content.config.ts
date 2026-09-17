import { defineCollection } from "astro:content";
import { glob } from "astro/loaders";
import { z } from "astro/zod";

const journal = defineCollection({
  loader: glob({
    pattern: "**/*.md",
    base: "./src/content/journal",
  }),
  schema: z
    .object({
      title: z.string(),
      summary: z.string().min(1).optional(),
      entry: z.number().int().positive(),
      session: z.number().int().positive(),
      date: z.string(),
      date_display: z.string(),
      session_date: z.string(),
      location: z.string(),
      people: z.array(z.string()).default([]),
      tags: z.array(z.string()).default([]),
      social: z
        .object({
          image: z.string().regex(/^\/social\/.+\.(?:png|jpe?g|webp)$/i),
          image_alt: z.string().min(1),
        })
        .optional(),
      draft: z.boolean().default(false),
    })
    .superRefine((entry, context) => {
      if (!entry.draft && !entry.summary) {
        context.addIssue({
          code: "custom",
          path: ["summary"],
          message: "Published journal entries require a social preview summary.",
        });
      }
    }),
});

export const collections = { journal };
