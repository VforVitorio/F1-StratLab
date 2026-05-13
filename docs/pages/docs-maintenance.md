# Documentation maintenance

This page documents how the documentation site you are reading right now is built, deployed and extended. Read it before adding new pages, changing the theme or pointing the site at a custom domain.

## Stack overview

| Component | Tool | Lives in |
|---|---|---|
| Static site generator | [`mkdocs`](https://www.mkdocs.org/) | `pyproject.toml` indirect (via `requirements-docs.txt`) |
| Theme | [`mkdocs-material`](https://squidfunk.github.io/mkdocs-material/) | `requirements-docs.txt` |
| Source directory | Markdown + assets | `docs/` |
| Config | YAML | `mkdocs.yml` |
| Theme overrides | Custom CSS | `docs/stylesheets/extra.css` |
| Deploy workflow | GitHub Actions | `.github/workflows/docs.yml` |
| Hosting | GitHub Pages (`gh-pages` branch) | repo Settings → Pages |

The brand palette and typography are kept aligned with the public landing at [f1stratlab.com](https://f1stratlab.com/) by mirroring the design tokens declared in `colors_and_type.css`.

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

1. Create the markdown file under `docs/` in the section it belongs to (or create a new section folder).
2. Add it to the `nav:` block of `mkdocs.yml` under the right parent. Order matters: each list entry becomes a sidebar item in that order.
3. Cross-link from related pages with relative paths (`[See arcade dashboard](../arcade/dashboard.md)`).
4. Push to `main`. The deploy workflow runs automatically.

### Creating a new top-level section

Each entry in `nav` whose value is a list becomes a section in the top tab bar (because `navigation.tabs` is on). Add the section like this in `mkdocs.yml`:

```yaml
nav:
  - Home: index.md
  - Architecture:
    - Overview: architecture.md
    - Multi-agent system: agents-api-reference.md
  - Your new tab:
    - Page A: your-section/page-a.md
    - Page B: your-section/page-b.md
```

## Theme and palette

The custom palette lives entirely in `docs/stylesheets/extra.css`. The file references the same CSS custom-property values the landing site uses (`--purple-600`, `--purple-300`, `--bg-0` and friends).

If you change colours, change them in **both** repos:

- This docs site: `docs/stylesheets/extra.css`
- Public landing: `f1stratlab-web/colors_and_type.css`

## Deployment

### Automatic on push to `main`

`.github/workflows/docs.yml` watches:

- `docs/**`
- `documents/images/**`
- `mkdocs.yml`
- `requirements-docs.txt`
- `.github/workflows/docs.yml`

When any of these change on `main`, the workflow checks out the repo with full history, sets up Python 3.12 and installs `requirements-docs.txt`, then runs `mkdocs gh-deploy --force --clean --verbose` which builds the site and force-pushes the result to the `gh-pages` branch.

GitHub Pages picks up the new `gh-pages` commit and republishes the site, usually within 60 seconds.

### Manual trigger

```bash
gh workflow run docs.yml --ref main
```

## Custom domain

The site lives at `https://vforvitorio.github.io/F1-StratLab/` by default. To point a custom subdomain at it:

1. Add a `CNAME` DNS record: host `docs`, value `vforvitorio.github.io`.
2. Create a file `docs/CNAME` (no extension) with a single line: `docs.f1stratlab.com`.
3. Repo → Settings → Pages → Custom domain → `docs.f1stratlab.com` → Save.

## Diagrams (`docs/diagrams/*.drawio`)

The repository keeps draw.io sources in `docs/diagrams/`. Two cleaner options than `mkdocs-drawio-exporter`:

- **Manual export**: open the `.drawio` file in [diagrams.net](https://app.diagrams.net/), export as SVG/PNG, and commit it next to the source.
- **Inline Mermaid**: trivial diagrams can be written directly in markdown using fenced ` ```mermaid ` blocks. Mermaid is enabled through the `pymdownx.superfences` extension.

## Common edits checklist

| Change you want | File to edit |
|---|---|
| Add a new docs page | new `.md` under `docs/` + `mkdocs.yml` `nav:` |
| Change site title | `mkdocs.yml` `site_name` |
| Change colours / fonts | `docs/stylesheets/extra.css` |
| Add a tab to the top bar | new section under `mkdocs.yml` `nav:` |
| Change the homepage hero | `docs/index.md` |
| Add an icon to a nav item | `mkdocs.yml` via `material/<icon>` syntax |

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `mkdocs build` fails with "Unresolved tag" | IDE linting only, not mkdocs | Ignore — `!!python/name:` tags are valid mkdocs syntax |
| `gh-deploy` 403 on push to `gh-pages` | Workflow permissions too low | Settings → Actions → Workflow permissions → "Read and write" |
| Custom domain says "DNS check unsuccessful" | DNS not propagated | Wait 10–30 min |
| Search index empty | Page front matter has `hide: [toc]` | Use `hide: [navigation, toc]` only on landing pages |
| Theme overrides don't apply | Browser cached old CSS | Hard reload (`Ctrl+Shift+R`) |
