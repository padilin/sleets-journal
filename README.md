# Sleet's Journal

Sleet's Journal is a small, static Astro site for publishing one player character's in-world Dungeons & Dragons journal. Entries are plain Markdown. Astro content collections validate their metadata and generate the journal index and entry pages. Cloudflare Workers Static Assets serves the generated `dist/` directory.

The project deliberately does not use Markdoc, MDX, a database, server-side rendering, or a content management system.

## Architecture

```text
plain Markdown entries
        ↓
Astro content collection and schema validation
        ↓
static index and entry pages
        ↓
dist/
        ↓
Cloudflare Workers Static Assets
```

Important directories:

```text
public/
├── _headers                 Cloudflare static-response headers
├── favicon.svg
├── icons/                   Site-wide icons
└── textures/                Site-wide paper/desk textures

src/
├── assets/journal/
│   └── 001/                 Artwork belonging to entry 001
├── components/              Small site and journal UI components
├── content/journal/         Plain Markdown journal entries
├── layouts/                 Generic site and journal-page shells
├── pages/                   Astro routes
├── styles/
│   ├── global.css           Site-wide layout and utility styles
│   └── journal.css          Journal-entry presentation only
└── content.config.ts        Journal collection metadata schema
```

Entry files and their assets share the same zero-padded entry number:

```text
src/content/journal/007-the-road-south.md
src/assets/journal/007/road-marker.png
src/assets/journal/007/handwritten-note.png
```

Site-wide decorative files belong in `public/`. Entry-specific images belong in `src/assets/journal/<entry-number>/` so Astro can process and fingerprint them.

## Authoring an entry

Copy the sample entry, give the file its next zero-padded number and slug, and update every frontmatter field:

```md
---
title: "The Road South"
summary: "Sleet follows the frost road south and finds a troubling mark carved into an old road marker."
entry: 7
session: 5
date: "1492-10-14"
date_display: "14th of Deepwinter, 1492"
session_date: "2026-09-15"
location: "The Frost Road"
people:
  - Mara
  - Fen
tags:
  - travel
  - mystery
draft: false
---

The mountains are smaller behind us today.

![A strange symbol carved into a road marker.](../../assets/journal/007/road-marker.png)
```

The body uses ordinary Markdown only. Use paragraphs, headings, links, blockquotes, lists, horizontal rules, and images. Do not add Astro components, JSX, Markdoc tags, or MDX imports to an entry.

### Photos and sketches

Images use one of two visual treatments based on their filename:

- Other image names keep the taped photo-paper treatment.
- Names beginning with `sketch-` are rendered like drawings on the journal paper: no photo backing, border, shadow, or tape. At full page width they sit to the right while the text wraps beside them. On narrow screens they return to the normal document flow so the writing stays readable.

Both treatments retain a slight angle. The distinction does not require custom Markdown:

```md
![Sleet standing in a snowy mountain landscape.](../../assets/journal/001/sleet.png)

![A quick sketch of tracks crossing the frozen river.](../../assets/journal/001/sketch-frozen-river.png)
```

Sketch files work best with a transparent background cropped reasonably close to the drawing. Keep meaningful alternative text just as you would for a photo.

### Optional image captions

Add a visible caption with standard Markdown's optional image title. The alternative text should describe the image for someone who cannot see it; the quoted title is the separate caption readers will see:

```md
![A weathered stone marker beside the road.](../../assets/journal/007/road-marker.png "The mark we found before dusk.")
```

An image with a title is rendered as a semantic `<figure>` with a `<figcaption>`. Images without titles keep their existing presentation without an empty caption.

### Reading tools

Journal entries include a thin progress line at the top of the viewport. Long entries also reveal a back-to-top link after the reader has moved meaningfully into the entry. These controls do not alter entry Markdown, and the journal remains fully readable when JavaScript is unavailable.

### Frontmatter fields

| Field | Type | Purpose |
| --- | --- | --- |
| `title` | string | Entry title shown to readers. |
| `summary` | string | Short description used in metadata and social previews. Required for published entries. |
| `entry` | positive integer | Canonical journal order and displayed entry number. |
| `session` | positive integer | Campaign session that produced the entry. |
| `date` | string | Machine-sortable in-world date, normally `YYYY-MM-DD`. |
| `date_display` | string | In-character date shown on the journal page. |
| `session_date` | string | Real-world session date, normally `YYYY-MM-DD`. |
| `location` | string | In-world location shown on the entry and index. |
| `people` | string array | People mentioned; retained for future indexes. Defaults to `[]`. |
| `tags` | string array | Topics retained for future filtering. Defaults to `[]`. |
| `social` | object | Optional explicit social image with `image` and `image_alt`. Images must live under `public/social/`. |
| `draft` | boolean | When `true`, excludes the entry from generated public pages. Defaults to `false`. |

### Social previews

All pages use the artwork-free `public/social/default.png` card unless an entry explicitly provides a custom image:

```yaml
social:
  image: "/social/journal/007-the-road-south.png"
  image_alt: "The title The Road South on a journal card beside an approved illustration."
```

Social images are never selected automatically from entry content. Custom cards must be 1200 by 630 pixels and use PNG, JPEG, or WebP. Run `pnpm generate:social` to rebuild the default card from its SVG source and `pnpm validate:social` to check committed social assets.

The schema validates types at build time. Dates remain strings because the fantasy calendar's display value is intentionally separate from chronology and real-world session metadata.

## Local development

Requirements: a current Node.js release and pnpm.

```sh
pnpm install
pnpm dev
```

Astro prints the local URL. Before committing, run:

```sh
pnpm check
pnpm build
```

The production site is written to `dist/`. To inspect that build locally:

```sh
pnpm preview
```

## Build and deployment

`wrangler.jsonc` configures `dist/` as a Workers Static Assets deployment and assigns the custom domain `sleet.adventure.pub`.

For a manual deployment:

```sh
pnpm install --frozen-lockfile
pnpm check
pnpm deploy
```

For Workers Builds, connect the Git repository and use:

- Build command: `pnpm build`
- Deploy command: `pnpm wrangler deploy`
- Build output directory: `dist`

The site is fully prerendered. It does not require the Cloudflare Astro adapter or a Worker runtime script.

## Cloudflare settings

Configure these in Cloudflare after the `adventure.pub` nameserver move is stable:

- Enable DNSSEC for the `adventure.pub` zone.
- Use `sleet.adventure.pub` as the Worker's Custom Domain. Do not pre-create a conflicting CNAME.
- Enable Always Use HTTPS.
- Set minimum TLS to 1.2 and leave TLS 1.3 enabled.
- Enable HSTS with a six-month max age initially.
- Leave HSTS `includeSubDomains` off.
- Leave HSTS preload off.
- Enable HSTS no-sniff.
- Leave Browser Integrity Check on.
- Leave Always Online off; do not add Bot Fight Mode, WAF rules, rate limiting, Access, Turnstile, or custom cipher suites without a demonstrated need.

`public/_headers` adds the agreed low-risk response headers:

```text
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
```

Content Security Policy is intentionally deferred until the site's actual scripts, fonts, analytics, and image sources are known. Avoid long-lived caching rules for HTML. Astro's fingerprinted `/_astro/*` assets can receive immutable caching later if needed.

## Scope of this scaffold

The index, entry rendering, previous/next navigation, journal/global styling split, client-side journal search, and about page placeholder are present. People/Places pages, page-turn animation, analytics, and custom journal syntax are intentionally left for later work driven by real content.
