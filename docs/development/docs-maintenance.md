---
title: Documentation maintenance
description: How the F1 StratLab docs site is built, deployed and extended.
---

# Documentation maintenance

This page documents how the documentation site you are reading right now is built, deployed and extended. Read it before adding new pages, changing the theme or pointing the site at a custom domain.

## Stack overview

| Component | Tool | Lives in |
|-----------|------|----------|
| Static site generator | [`mkdocs`](https://www.mkdocs.org/) | `pyproject.toml` indirect (via `requirements-docs.txt`) |
| Theme | [`mkdocs-material`](https://squidfunk.github.io/mkdocs-material/) | `requirements-docs.txt` |
| Source directory | Markdown + assets | `docs/` |
| Config | YAML | `mkdocs.yml` |
| Theme overrides | Custom CSS matching the public landing palette | `docs/stylesheets/extra.css` |
| Deploy workflow | GitHub Actions | `.github/workflows/docs.yml` |
| Hosting | GitHub Pages (`gh-pages` branch) | repo Settings -> Pages |

The brand palette and typography are kept aligned with the public landing at [f1stratlab.com](https://f1stratlab.com/) by mirroring the design tokens declared in `colors_and_type.css` of the `f1stratlab-web` repo. If you change one, change the other.

## Local preview

```bash
# Install once
pip install -r requirements-docs.txt

# Live-reload preview on http://127.0.0.1:8000
mkdocs serve

# Production-equivalent build
mkdocs build
```

The site is written into `site/` (gitignored). `mkdocs serve` auto-reloads on every saved markdown / CSS file under `docs/`.

## Adding a new page

1. Create the markdown file under `docs/` in the section it belongs to (or create a new section folder, see below).
2. Add it to the `nav:` block of `mkdocs.yml` under the right parent. Order matters: each list entry becomes a sidebar item in that order.
3. Cross-link from related pages with relative paths (`[See arcade dashboard](../arcade/dashboard.md)`).
4. Push to `main`. The deploy workflow runs automatically.

### Creating a new top-level section

Each entry in `nav` whose value is a list becomes a section in the top tab bar (because `navigation.tabs` is on). Sections collapse into the side menu on mobile. Add the section like this in `mkdocs.yml`:

```yaml
nav:
  - Home: index.md
  - Architecture:                     # tab label
    - Overview: architecture.md       # first child becomes the tab landing
    - Multi-agent system: agents-api-reference.md
  - Your new tab:                     # NEW
    - Page A: your-section/page-a.md
    - Page B: your-section/page-b.md
```

## Theme and palette

The custom palette lives entirely in `docs/stylesheets/extra.css`. The file is structured into clearly labelled sections (palette, typography, header, code blocks, etc.) and references the same CSS custom-property values the landing site uses (`--purple-600`, `--purple-300`, `--bg-0` and friends).

If you change colours, change them in **both** repos:

- This docs site: `docs/stylesheets/extra.css`
- Public landing: `f1stratlab-web/colors_and_type.css`

The theme scheme is registered as `stratlab-dark` and applied via `palette` in `mkdocs.yml`. The light scheme is a placeholder; the brand is dark-first so most readers will land on the dark variant.

## Deployment

### Automatic on push to `main`

`.github/workflows/docs.yml` watches:

- `docs/**`
- `documents/images/**`
- `mkdocs.yml`
- `requirements-docs.txt`
- `.github/workflows/docs.yml`

When any of these change on `main`, the workflow:

1. Checks out the repo with full history (needed by `mkdocs gh-deploy`).
2. Sets up Python 3.12 and installs `requirements-docs.txt`.
3. Runs `mkdocs gh-deploy --force --clean --verbose` which builds the site and force-pushes the result to the `gh-pages` branch.

GitHub Pages picks up the new `gh-pages` commit and republishes the site, usually within 60 seconds.

### Manual trigger

The workflow also has `workflow_dispatch` enabled so you can re-run it without a push:

```bash
gh workflow run docs.yml --ref main
```

Useful when:

- A previous build failed and you want to retry without pushing a dummy commit.
- You just rotated the custom domain and want to refresh GitHub Pages.

## Custom domain (future)

The site lives at `https://vforvitorio.github.io/F1-StratLab/` by default. To point a custom subdomain at it:

1. In your DNS provider (Namecheap, Cloudflare, etc.), add a `CNAME` record:

    | Field | Value |
    |-------|-------|
    | Type | `CNAME` |
    | Host | `docs` (so the result is `docs.f1stratlab.com`) |
    | Value | `vforvitorio.github.io` (no trailing dot, no path) |
    | TTL | Automatic |

2. Create a file `docs/CNAME` (no extension) with a single line:

    ```
    docs.f1stratlab.com
    ```

3. Repo -> Settings -> Pages -> Custom domain -> `docs.f1stratlab.com` -> Save. GitHub will run a DNS check (5-15 min) and then offer to enforce HTTPS — tick that box.

Reverting is as simple as deleting the `CNAME` file, blanking the custom domain field in Settings, and removing the DNS record.

## Diagrams (`docs/diagrams/*.drawio`)

The repository keeps draw.io sources in `docs/diagrams/`. They are not auto-rendered into the published site by default — early versions tried `mkdocs-drawio-exporter`, but that plugin needs the draw.io binary on the build runner which adds 100+ MB of dependencies. Two cleaner options:

- **Manual export**: open the `.drawio` file in [diagrams.net](https://app.diagrams.net/), export as SVG/PNG, and commit it next to the source. Reference the exported image from a markdown file with the standard image syntax.
- **Inline render via Mermaid**: trivial diagrams can be written directly in markdown using fenced ` ```mermaid ` blocks. Mermaid is enabled out of the box through the `pymdownx.superfences` extension already configured in `mkdocs.yml`.

If you reintroduce `mkdocs-drawio-exporter` in the future, remember to add the draw.io binary install step to `.github/workflows/docs.yml` (apt-get + the official `.deb` from the `jgraph/drawio-desktop` releases). A starter snippet is left commented inside the workflow.

## Versioning (future)

`mike` is already in `requirements-docs.txt`. If you ever ship multiple thesis revisions and want a version dropdown, switch the deploy step to:

```bash
mike deploy --push --update-aliases 1.2 latest
mike set-default --push latest
```

Until then, the workflow runs a single-version `mkdocs gh-deploy` which is enough for a TFG project.

## Common edits checklist

| Change you want | File to edit |
|-----------------|--------------|
| Add a new docs page | new `.md` under `docs/` + `mkdocs.yml` `nav:` |
| Change site title | `mkdocs.yml` `site_name` |
| Change colours / fonts | `docs/stylesheets/extra.css` |
| Add a tab to the top bar | new section under `mkdocs.yml` `nav:` |
| Change the homepage hero | `docs/index.md` |
| Add an icon to a nav item | `mkdocs.yml` via `material/<icon>` syntax |
| Add a social link in the footer | `mkdocs.yml` `extra.social` |
| Override a theme template | new file under `docs/overrides/` mirroring the path |

For anything more involved, the canonical reference is the [Material for MkDocs documentation](https://squidfunk.github.io/mkdocs-material/) — well written and the search there is excellent.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `mkdocs build` fails with "Unresolved tag" | IDE linting only, not mkdocs | Ignore — `!!python/name:` tags are valid mkdocs syntax |
| `gh-deploy` 403 on push to `gh-pages` | Workflow permissions too low | Repo -> Settings -> Actions -> Workflow permissions -> "Read and write permissions" |
| Custom domain says "DNS check unsuccessful" | DNS not propagated yet | Wait 10-30 min; verify with `nslookup docs.f1stratlab.com` |
| Search index empty | Page front matter has `hide: [toc]` | Use `hide: [navigation, toc]` only on landing pages |
| Theme overrides don't apply | Browser cached old CSS | Hard reload (`Ctrl+Shift+R`) or bump query string on the link in `mkdocs.yml` |
