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
- New blog post: copy `blog/week-1.html`, add an entry to `reports` in `.github/combat_hub/state.json`, then run `python .github/combat_hub/combat_hub.py --render` (it updates the News page, home page and sitemap; don't edit those cards by hand).

## Daily Combat Hub (automatic, free)

Every day at 07:00 IST the GitHub Action `.github/workflows/combat-hub.yml` refreshes the Combat Hub:

- Collects the newest headlines from Google News for MMA, boxing, Muay Thai, kickboxing and Indian
  combat sports (MFN, Indian boxing, Indian MMA), six per sport.
- Publishes them on the News page (`blogs.html`, grouped by sport) and as "Today's headlines" on the
  home page. Every headline links to the original publisher.
- Costs nothing: GitHub Actions is free for public repositories and the feeds are free.

Details:
- Code and data: `.github/combat_hub/`. `state.json` holds the reports, results and headlines shown.
- Run it now: GitHub → Actions → Daily Combat Hub → Run workflow.
- Fight results (`results.html`) and long reports (`blog/`) stay manual: add them to `state.json`,
  then run `python .github/combat_hub/combat_hub.py --render`.
- Pages only change between `<!-- HUB:...:START -->` / `<!-- HUB:...:END -->` markers.
- Optional, paid: adding a repository secret `ANTHROPIC_API_KEY` switches on AI-written daily reports
  and automatic results (Claude, roughly ₹2,000–3,000 per month). Leave it unset to stay free.
