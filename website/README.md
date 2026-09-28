# agy-ppt marketing site

This is a small, framework-free GitHub Pages project site. The public pages
are served at `https://sujunmin.github.io/agy-ppt/`; use relative links so
assets also work under the `/agy-ppt/` project base path.

## Build and check

From the repository root:

```bash
python3 website/check_site.py
python3 website/build.py --output-dir /tmp/agy-ppt-pages-preview
python3 website/preview.py --directory /tmp/agy-ppt-pages-preview
```

Open `http://127.0.0.1:8765/agy-ppt/` and
`http://127.0.0.1:8765/agy-ppt/en/`. The preview server maps the project path
to the static artifact, matching GitHub Pages URL behavior.

The build copies only the two HTML pages, shared CSS/JavaScript, and the eight
approved slide previews from `examples/`. It does not copy source decks,
qualification bundles, repository documentation, or engineering artifacts.
No package install, API key, analytics, or external runtime service is needed.

The GitHub Pages workflow validates and builds on pull requests. It deploys
only from `main`, after normal review and merge.
