# PURECOMBAT

Website for PURECOMBAT — elite MMA, boxing and fitness training in Sector 122, Noida.
Live at https://www.purecombat.in

## Structure

```
index.html          Home (hero, about, programs, gallery, coaches, plans, news, contact)
results.html        Fight results
fighters.html       Fighter spotlight
blogs.html          News & reports listing
blog/week-1.html    Weekly combat report – week 1
404.html            Not-found page (GitHub Pages)
css/style.css       Shared stylesheet (all pages)
js/main.js          Menu, scroll effects, WhatsApp enquiry form
images/             Optimised images, logo, favicons
sitemap.xml, robots.txt
```

## Editing

- Prices, programs and contact details live in `index.html`.
- WhatsApp number for the enquiry form: `WHATSAPP_NUMBER` in `js/main.js`.
- Colours and fonts: CSS variables at the top of `css/style.css`.
- New blog post: copy `blog/week-1.html`, then add a card to `blogs.html` (and optionally the home page news section) and a line to `sitemap.xml`.

## Daily Combat Hub (automatic)

Every day at 07:00 IST the GitHub Action `.github/workflows/combat-hub.yml` publishes a
Daily Combat Report covering MMA, boxing, Muay Thai, kickboxing and Indian combat sports:

1. Collects the latest headlines from Google News.
2. Claude picks the top stories and checks the facts with web search.
3. Claude writes an original report, which becomes `blog/<date>.html`.
4. The News page, the home page news card, `results.html` and `sitemap.xml` are updated and pushed.

- Code and data: `.github/combat_hub/` (`state.json` holds every report, result and headline shown).
- Requires the repository secret `ANTHROPIC_API_KEY`. Without it the job skips generation.
- Optional repository variables: `COMBAT_HUB_MODEL` (default `claude-opus-5-5`) and
  `COMBAT_HUB_MAX_SEARCHES` (default `10`).
- Run it now: GitHub → Actions → Daily Combat Hub → Run workflow.
- Pages only change between `<!-- HUB:...:START -->` / `<!-- HUB:...:END -->` markers. Everything else
  stays hand-edited.
- To remove a bad report: delete its entry from `state.json` and its `blog/<date>.html`, then run
  `python .github/combat_hub/combat_hub.py --render`.
