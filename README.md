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
