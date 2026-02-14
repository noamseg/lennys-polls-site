---
name: lennys-polls-dashboard
description: Create interactive HTML dashboards for Lenny's Polls survey data. Use when the user provides a CSV of poll/survey responses and wants to produce a Lenny-branded interactive report with quantitative charts and qualitative theme analysis. Follows Lenny's Newsletter visual identity and editorial voice.
---

# Lenny's Polls Dashboard

Create an interactive, single-file HTML dashboard for survey data from Lenny's Polls. The output is a self-contained HTML file that can be embedded in Substack or shared as a standalone page.

## When to use this skill

- User provides a CSV of survey responses (typically from Polly)
- User asks for a "dashboard", "interactive report", or "poll results" for Lenny's Newsletter
- User references "Lenny's Polls" or survey data analysis

## Input expectations

A CSV file with columns typically including:
- A **rating question** (numeric scale, e.g. 1–5)
- An **open-text question** (what people love/hate, or free-form commentary)
- **Demographic columns** (company size, tenure, role/title, etc.)

The exact column names will vary per poll. Inspect the CSV first to understand the schema before proceeding.

---

## Process overview

### Step 1: Data analysis
1. Load the CSV and inspect columns
2. Compute quantitative breakdowns:
   - Overall rating distribution (count and % per rating level)
   - Average rating overall
   - Cross-tabulations: average rating by each demographic dimension (company size, tenure, role level, etc.)
   - Respondent profile: distribution counts for each demographic
3. Qualitative theme extraction from open-text responses:
   - Separate responses by sentiment (e.g. high raters vs low raters)
   - Identify 6 themes per sentiment pole through manual reading of responses
   - Count mentions per theme
   - Select 3 representative quotes per theme

### Step 2: Role categorization (if role/title column exists)
Categorize free-text job titles into standardized role levels. Use this hierarchy with **exact order of matching** to avoid misclassification:

1. **Founder / C-suite**: founder, co-founder, CEO, CTO, COO, CPO, CSO, chief [anything], SVP, owner (but NOT "product owner")
2. **VP / Director / Head**: VP, vice president, director (ALL directors go here, not C-suite), head of [anything]
3. **Group PM / People manager**: group PM, group product, manager of product, senior manager + product
4. **IC**: everything else (PMs, senior PMs, staff PMs, engineers, designers, analysts)

**Critical**: Check for "director" AFTER checking for founder/CxO titles. Directors are NOT C-suite.

### Step 3: Build the HTML dashboard
Follow the structure and design system below exactly.

---

## Dashboard structure (sections in order)

1. **Header** — eyebrow ("LENNY'S POLLS"), title (the poll question), subtitle (one-sentence summary), meta line (response count, date range, survey tool), "Download PDF ↓" button
2. **Sticky section navigation** — pill nav bar that appears after scrolling past the header, with links to each major section (hidden on mobile)
3. **Hero stat** (`id="overview"`) — stacked bar showing the full rating distribution. Above the bar: the survey question in bold (`.bar-question strong`), then the scale description on a separate line in lighter text (`.bar-scale`). Scale labels beneath each segment on desktop; on mobile, endpoint-only labels. No big number or average — let the distribution speak for itself.
4. **The tl;dr** (`id="tldr"`) — insight callout box with prose summary, top 3 love drivers, top 3 hate drivers
5. **What people love vs. hate** (`id="themes"`) — two-column grid of expandable theme cards with ranked themes and quote drawers
6. **Satisfaction by demographics** (`id="breakdowns"`) — two-column layout with horizontal bar charts comparing average rating by each dimension
7. **Patterns worth noting** (`id="patterns"`) — insight callout box with 3–5 cross-cutting observations
8. **Who responded** (`id="respondents"`) — two-column layout showing respondent profile distributions
9. **Newsletter CTA** — "Want more insights like this?" with subscribe button linking to lennysnewsletter.com
10. **Footer** — data collection details and "Research by Noam Segal" credit

### Output file

Produce a single HTML file for each dashboard, named after the poll question in lowercase with spaces replaced by hyphens and punctuation removed.

Example: for the poll "How do you feel about your job?", the file would be `how-do-you-feel-about-your-job.html`.

### Favicon

Every HTML page must include favicon links in the `<head>`:

```html
<link rel="icon" type="image/x-icon" href="/favicon.ico">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
```

The favicon files (`favicon.ico`, `favicon-32x32.png`, `favicon-16x16.png`, `apple-touch-icon.png`) are generated from `lennylogo.svg` and live at the site root.

### Vercel Analytics

Every HTML page must include the Vercel Web Analytics snippet just before the closing `</body>` tag:

```html
<!-- Vercel Analytics -->
<script>
  window.va = window.va || function () { (window.vaq = window.vaq || []).push(arguments); };
</script>
<script defer src="/_vercel/insights/script.js"></script>
```

This applies to dashboards, the index page, and social cards pages.

### OG meta tags

All public-facing pages (index and dashboards) must include Open Graph and Twitter Card meta tags in the `<head>` for link previews on social media. Social cards pages (internal tool) do NOT get OG tags.

**Index page template:**
```html
<!-- Open Graph -->
<meta property="og:title" content="Lenny's Polls">
<meta property="og:description" content="A pulse on what's happening in your work lives">
<meta property="og:type" content="website">
<meta property="og:url" content="https://lennyspolls.com/">
<meta property="og:image" content="https://lennyspolls.com/apple-touch-icon.png">

<!-- Twitter Card -->
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="Lenny's Polls">
<meta name="twitter:description" content="A pulse on what's happening in your work lives">
<meta name="twitter:image" content="https://lennyspolls.com/apple-touch-icon.png">
```

**Poll page template:**
```html
<!-- Open Graph -->
<meta property="og:title" content="[Poll question] — Lenny's Polls">
<meta property="og:description" content="[Subtitle from dashboard header]">
<meta property="og:type" content="article">
<meta property="og:url" content="https://lennyspolls.com/polls/[slug].html">
<meta property="og:image" content="https://lennyspolls.com/apple-touch-icon.png">

<!-- Twitter Card -->
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="[Poll question] — Lenny's Polls">
<meta name="twitter:description" content="[Subtitle from dashboard header]">
<meta name="twitter:image" content="https://lennyspolls.com/apple-touch-icon.png">
```

Place OG tags after `<title>` and before the favicon links.

### Newsletter subscribe CTA

Every page (index, dashboard, social cards) includes a newsletter subscribe CTA section just above the footer. It links to lennysnewsletter.com — no inline form needed.

```html
<div class="newsletter-cta">
  <p class="newsletter-cta-text">Want more insights like this?</p>
  <a href="https://www.lennysnewsletter.com/" target="_blank" class="newsletter-cta-btn">Subscribe to Lenny's Newsletter →</a>
</div>
```

On the **dashboard page**, place the CTA inside `<main>` before `<footer>`. On the **index page** and **social cards page**, place between `</main>` and `<footer>`.

CSS for the CTA (add to each page's `<style>`):
```css
.newsletter-cta {
  max-width: 880px;
  margin: 0 auto;
  padding: 32px 24px;
  text-align: center;
}

.newsletter-cta-text {
  font-family: 'Source Serif 4', Georgia, serif;
  font-size: 18px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 12px;
}

.newsletter-cta-btn {
  display: inline-block;
  padding: 12px 28px;
  background: var(--orange);
  color: white;
  border-radius: 8px;
  text-decoration: none;
  font-size: 14px;
  font-weight: 600;
  transition: background 0.15s;
}

.newsletter-cta-btn:hover {
  background: var(--orange-dark);
}
```

### Sticky section navigation (dashboard only)

Dashboards include a sticky pill nav that appears when the user scrolls past the header. It shows section links as horizontal pills and highlights the active section. Hidden on mobile (screen too narrow for useful section names).

**Requirements:**
- Add `id` attributes to each major dashboard section: `overview` (hero stat), `tldr` (tl;dr insight box), `themes` (love/hate section header — NOT linked in ToC, covered by "Key findings"), `breakdowns` (demographics section header), `patterns` (patterns insight box), `respondents` (respondent profile section header)
- The ToC has 5 pills: Overview, Key findings, Breakdowns, Patterns, Respondents. "Key findings" covers both the tl;dr and love/hate sections.
- Add the sticky ToC HTML between `</nav>` and `<main>`
- Add CSS for `.sticky-toc`, `.toc-link`, etc. (see reference files)
- Add JavaScript before `</body>` that uses IntersectionObserver to show/hide the ToC and highlight the active section
- The ToC is hidden on mobile with `@media (max-width: 768px) { .sticky-toc { display: none !important; } }`

### Download as PDF (dashboard only)

Dashboards include a "Download PDF ↓" button in the header that triggers `window.print()`. A `@media print` stylesheet cleans up the output by hiding nav, ToC, CTA, and disabling animations.

**HTML** (add after `.meta` div in `.header`):
```html
<div class="header-actions">
  <button class="pdf-btn" onclick="window.print()">Download PDF ↓</button>
</div>
```

**Print stylesheet** (add at end of `<style>`):
```css
@media print {
  .site-nav, .sticky-toc, .header-actions, .newsletter-cta { display: none; }
  .animate-in { animation: none; opacity: 1; transform: none; }
  .theme-item.open .quote-drawer { max-height: none; opacity: 1; }
  body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  main.container { padding-top: 0; }
}
```

### Site navigation bar

Every dashboard includes a top nav bar linking back to the index page. This is already present in the reference files — preserve it exactly:

```html
<nav class="site-nav">
  <a href="/" class="nav-brand">
    <img src="/lennylogo.svg" alt="Lenny's Newsletter" class="nav-logo">
  </a>
  <a href="/" class="nav-back">← All Polls</a>
  <a href="https://www.lennysnewsletter.com/" class="nav-link" target="_blank">Lenny's Newsletter ↗</a>
</nav>
```

The nav uses Lenny's campfire logo (stored as `lennylogo.svg` at the site root), links the logo back to the index, includes a "← All Polls" back link to the index, and a "Lenny's Newsletter ↗" link to lennysnewsletter.com.

### Site structure

Dashboards live in a static site with this folder structure:

```
/index.html                                          (landing page listing all polls)
/polls/how-do-you-feel-about-your-job.html           (dashboard)
/polls/how-do-you-feel-about-your-job-social.html    (social cards page)
/polls/next-poll-title.html                          (dashboard)
/polls/next-poll-title-social.html                   (social cards page)
```

The index page (`index.html`) includes:
- A hero section with title, tagline, and intro paragraph ("Survey insights from Lenny's Newsletter's community.")
- A polls grid with card entries for each poll
- A "Next poll coming soon" dashed-border card after the last poll entry
- A newsletter subscribe CTA above the footer

When a new poll is created, add a poll card entry to the index page with the poll title, response count, date range, and link to the dashboard file in `/polls/`. Remove the "coming soon" card if there are enough polls, or keep it as a teaser.

### Social cards page

Every poll gets a companion social cards page for sharing individual insights on Twitter/X and LinkedIn. The social cards page is an **internal tool** — there is no link to it from the main dashboard. Lenny accesses it directly by URL.

**File naming:** `[poll-slug]-social.html` (e.g., `how-do-you-feel-about-your-job-social.html`)

**Page structure:**
- Nav bar with back link to the poll results page (not index)
- Page header: eyebrow "Social Cards", poll title, instruction text
- Grid of card wrappers, each containing a 1200×675 card
- Site footer: "Lenny's Polls · Internal sharing tool"
- Vercel Analytics snippet

**Card design rules:**
- Each card is a `1200×675px` div (standard social media image size)
- CSS-scaled down to fit the 880px container using `transform: scale()` with `transform-origin: top left`
- Card wrapper uses `padding-bottom: 56.25%` for correct aspect ratio
- 4px orange accent bar at the top of every card (via `::before` pseudo-element)
- **Lenny logo** (`lennylogo.svg`) in the top-left corner of every card, positioned absolutely at `top: 18px; left: 48px` with `width: 112px; height: 112px; border-radius: 12px`
- Branded footer on every card: "LENNY'S POLLS" (left, 14px) and "lennyspolls.com" (right, 14px)
- White background, clean typography matching the dashboard design system
- **Fill the space** — use large font sizes to minimize whitespace. Headlines 34–48px, big numbers 100–120px, body text 17–20px. The card is 1200px wide so text should be bold and readable at thumbnail size.
- **Chart-first cards** (hero stat, comparison) should let the data speak for itself — no half-baked summary lines. Either give a clear, compelling insight or just show the chart.
- **Always show the scale** on rating numbers. Append a lighter, smaller "/5" (or whatever the scale is) directly after the number so the value has context without explanation. Style the suffix in `var(--text-light)` at roughly 40% the size of the main number.
- **No orphan words.** Never let a single word sit alone on the last line of a text block. Rewrite copy or widen `max-width` to prevent it. Use generous `max-width` values (900px+ for finding text, 860px+ for context) on the 1200px-wide cards.

**Card types (~10-12 per poll):**
1. **Hero stat** — distribution bar with scale labels and summary line
2. **Key finding (×2-3)** — big number centered, finding text, context line
3. **Quote card — positive** — warm orange-bg background, quote in italic serif, attribution
4. **Quote card — negative** — light red background, quote in italic serif, attribution
5. **Comparison card** — horizontal bars showing a demographic breakdown (e.g., company size)
6. **Theme summary: Love** — top 3 love drivers, ranked with mention counts
7. **Theme summary: Hate** — top 3 hate drivers, ranked with mention counts
8. **Pattern card (×2)** — bold headline, data points side by side, context line

**Mobile UX:**
On mobile (≤768px), the hover overlay doesn't work on touch devices. Instead, the overlay converts to a visible 48px button bar below each card:
```css
@media (max-width: 768px) {
  .cards-grid { gap: 24px; }
  .card-wrapper { padding-bottom: calc(56.25% + 48px); }
  .card-overlay {
    opacity: 1;
    top: auto;
    bottom: 0;
    height: 48px;
    background: var(--bg);
    border-top: 1px solid var(--border);
    border-radius: 0 0 12px 12px;
  }
  .overlay-btn { padding: 10px 18px; font-size: 13px; }
  .page-header { padding: 24px 24px 12px; }
  .page-header h1 { font-size: 22px; }
}
```
The card-wrapper's extra `48px` padding creates space for the always-visible button bar. The overlay pins to the bottom 48px instead of covering the full card.

**Hover overlay and interactions (desktop):**
- Each card wrapper has an overlay that appears on hover with two buttons:
  - **"Copy to clipboard"** (orange button) — uses `html2canvas` + `navigator.clipboard.write()` to copy at native 1200×675 resolution
  - **"Download PNG"** (white button) — uses `html2canvas` + download link
- Capture works by temporarily removing the CSS transform, rendering at native resolution, then restoring the transform
- Toast notification appears at the bottom of the screen on successful copy
- Falls back to download if clipboard API is not supported

**Tech dependencies:**
- `html2canvas` loaded from CDN: `https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js`
- Google Fonts (same as dashboard): Source Serif 4 + Inter

**Content guidelines:**
- Use the same data and quotes from the dashboard — do not invent new data
- Key findings should highlight the most shareable, surprising insights
- Quote cards should use vivid, concise quotes that stand alone without context
- Pattern cards should tell a mini-story with their headline + data points
- All text should be readable at social media thumbnail size (keep it large and sparse)

---

## Brand and design system

### Color palette
```css
:root {
  --bg: #FFFFFF;
  --card: #FFFFFF;
  --text: #1A1A1A;
  --text-secondary: #6B6B6B;
  --text-light: #767676;
  --border: #E8E5E0;

  /* Lenny orange — the only accent color */
  --orange: #EF7B4E;
  --orange-dark: #D96A3E;
  --orange-light: #F5B07A;
  --orange-gradient: linear-gradient(to right, #EF7B4E, #F5B88A);
  --orange-bg: #FEF8F4;

  /* Neutral surfaces */
  --neutral-surface: #F7F6F4;
  --neutral-track: #EDECEA;

  /* Semantic (love/hate only — used sparingly for theme cards) */
  --love: #0a9396;
  --love-light: #E6F4F4;
  --love-bg: #F2F9F9;
  --hate: #ae2012;
  --hate-light: #F6E8E7;
  --hate-bg: #FAF3F3;
}
```

### Critical color rules
- **Restrained palette.** Lenny's Substack is clean white with minimal color. Orange is the accent, not the surface.
- **No rainbow charts.** Stacked bars use a **tonal orange range** (lighter to darker shades of orange), NOT 5 different hue colors.
- **Rating card numbers** are all `var(--text)` (dark), NOT individually colored per rating level.
- **Card and hero backgrounds** are white with `1px solid var(--border)`, NOT beige/tan fill.
- **Respondent profile bars** have no background track — the orange bar floats in a transparent flex container. Compare bars and theme mini-bars still use `var(--neutral-track)` where applicable.
- **Green and red** are used ONLY for love/hate theme cards (border-top and small UI elements). They never appear in the main charts.
- **Section dividers and borders** are `1px solid var(--border)` (neutral gray), NOT orange-tinted.

### Typography
- **Headings**: `'Source Serif 4', Georgia, serif` — weight 700
- **Body**: `'Inter', -apple-system, sans-serif` — weight 400/500/600
- **Section titles**: 22px serif with a small 32px-wide orange underline accent
- **Insight box titles**: 21px serif, color `var(--orange-dark)`
- **Card headings**: 16px serif with 24px orange underline accent
- Import: `https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,opsz,wght@0,8..60,300;0,8..60,400;0,8..60,600;0,8..60,700;1,8..60,400&family=Inter:wght@400;500;600;700&display=swap`

### Layout
- Max width: 880px, centered
- Cards: white background, 12px border-radius, 1px border, 28px padding
- Spacing between sections: 48px
- Two-column grids: `1fr 1fr` with 24px gap
- Responsive: collapses to single column at 768px

### Charts
- **Stacked bar** (hero): tonal orange range, 44px height, 8px border-radius. Above the bar: bold question (`.bar-question strong`, 22px, font-weight 600, `var(--text)`) and scale on a separate line (`.bar-scale`, 12px, `var(--text-light)`). Per-segment labels beneath on desktop; on mobile (≤768px), hide per-segment labels and show endpoint-only labels (`.bar-labels-mobile`, `justify-content: space-between`). On mobile, reduce hero-stat padding to `24px 16px` and set `align-items: stretch` so the bar fills the full card width.
- **Horizontal bars** (respondent profile): orange gradient fill, **no background track** (use `.h-bar-container` with `flex:1; display:flex` instead of a gray `.h-bar-track`), 32px height, 8px border-radius. **Bar widths must be relative to the largest category in each group** (largest = 100%, others proportional). Never use raw counts or absolute values as percentages — this creates a false ceiling.
- **Compare bars** (satisfaction by X): orange gradient, sorted by value descending, with rating value inside bar and `n=X` outside
- **Theme mini-bars**: 50px wide, 5px height, love=green / hate=red fill on neutral track

### Stacked bar segment colors (tonal orange, light to dark)
```css
.stacked-bar .s1 { background: #D4926A; }
.stacked-bar .s2 { background: #E09060; }
.stacked-bar .s3 { background: #E8A46E; }
.stacked-bar .s4 { background: #EF7B4E; }
.stacked-bar .s5 { background: #D96535; }
```

### Interactive elements
- Theme items toggle open/closed on click (`onclick="this.classList.toggle('open')"`)
- Quote drawers animate with `max-height` and `opacity` transitions
- Rating cards have subtle `translateY(-2px)` hover effect
- Fade-in animations on scroll with staggered delays

---

## Writing rules — THIS IS CRITICAL

The dashboard text must read like it was written by a sharp editorial writer, not generated by AI. Follow these rules strictly:

### Voice and tone
- Write like a smart colleague sharing findings over coffee. Direct, specific, occasionally witty.
- Lead with the most interesting or surprising finding, not the most obvious one.
- Use concrete numbers and specifics. "27% are actively unhappy" not "a significant portion expressed dissatisfaction."
- One quote per theme insight max. Use it to illustrate, not to pad.
- Avoid obvious statements. If the reader can infer it from the data you just showed, don't spell it out. State the surprising part and move on.

### Banned AI writing patterns
Never use any of these in the dashboard text:

**Filler phrases to cut:**
- "It's worth noting that…" / "It's interesting to note…" / "Interestingly…"
- "Let's dive in" / "Let's explore" / "Let's unpack"
- "In today's [landscape/environment/world]"
- "This raises an important question"
- "At the end of the day"
- "Overall" as a sentence opener

**Banned adjectives and verbs:**
- "Navigate" (as metaphor) / "Landscape" / "Harness" / "Leverage" (as verb)
- "Empower" / "Elevate" / "Unlock" / "Foster" / "Streamline"
- "Robust" / "Holistic" / "Comprehensive" / "Dynamic"
- "Pivotal" / "Crucial" / "Transformative" / "Game-changing"
- "Seamless" / "Cutting-edge" / "Groundbreaking"

**Structural patterns to avoid:**
- "Not just X, but Y" constructions
- Ending with an inspirational call to action
- Tricolon escalation ("X, Y, and most importantly Z")
- Starting paragraphs with "When it comes to…"
- Using "while" to create false balance ("While some love X, others hate Y")
- Overuse of em-dashes for dramatic pause

### Taglines and subtitles
- Keep taglines short and catchy — one punchy phrase, not a full sentence.
- Do NOT append trailing explanatory clauses (e.g. "— tracking what operators and leaders like you are experiencing on the ground"). Cut after the hook.
- Good: "A pulse on what's happening in your work lives"
- Bad: "A pulse on what's happening in your work lives — tracking what operators and leaders like you are experiencing on the ground."
- Dashboard subtitles follow the pattern: "[N] [audience] shared [what they shared], and why." Keep it tight.
- Good: "323 product and tech professionals shared how they really feel about their jobs, and why."
- Bad: "323 product and tech professionals shared how they really feel about their jobs, and what drives their feelings."

### What good writing looks like in this context

**The tl;dr section:**
- Open with the most striking distribution insight (e.g. "13% truly love their jobs. 27% are actively unhappy in their job (rating 1 or 2).") — do NOT lead with an average
- Keep insights short and focused. State the surprising finding, then stop. Don't follow up with obvious takeaways or restatements — the reader can draw their own conclusions.
- Use bullet points for top 3 love/hate drivers, each with a bold label and 1–2 sentences of grounded explanation
- Close with the most surprising cross-cut finding
- Keep it to ~250 words total

**Patterns worth noting section:**
- 3–5 observations, each a short paragraph (2–4 sentences)
- Each starts with a **bold observation** as a mini-headline
- Support with specific numbers from the data
- Offer a plausible "why" without overclaiming
- Example: "**The honeymoon is real.** People under 1 year at their company rate satisfaction highest (3.55). At 1–5 years, it drops to about 3.1. The novelty wears off, the frustrations accumulate, and the things you accepted on the way in become harder to tolerate."

### Quote selection rules
- Select 3 quotes per theme
- Each quote must be **thematically pure** — it should only speak to the theme it's filed under, not mix multiple themes
- Example: "Great people, aligned leadership, no BS, clear vision" is NOT a pure "Team & People" quote because it mixes team + leadership + strategy. Use a quote that's specifically about the people.
- Include the respondent's title and company size as attribution
- Prefer quotes that are vivid and specific over generic ones
- Mix company sizes and seniority levels across quotes

---

## Reference implementation

The live site is the source of truth. Read these files to see the exact implementation of every component before building a new dashboard or social cards page:

- **`lennys-polls-site/index.html`** — landing page listing all polls, with Lenny's branding and nav
- **`lennys-polls-site/polls/how-do-you-feel-about-your-job.html`** — publication-ready dashboard (deployed to site)
- **`lennys-polls-site/polls/how-do-you-feel-about-your-job-social.html`** — social cards page with copy-to-clipboard and download PNG functionality

---

## Checklist before delivering

- [ ] All numbers verified against source data
- [ ] Rating distributions sum to total N
- [ ] Cross-tab averages are weighted correctly
- [ ] Role categorization follows the exact hierarchy (directors → VP/Director/Head, NOT C-suite)
- [ ] All quotes are thematically pure (only about their assigned theme)
- [ ] No AI writing patterns in any prose text
- [ ] Hero stat shows distribution bar only (NO big average number)
- [ ] tl;dr opens with a distribution insight, NOT an average
- [ ] Stacked bar uses tonal orange (NOT rainbow colors)
- [ ] Rating card numbers are all dark text (NOT per-rating colors)
- [ ] Card/hero backgrounds are white with border (NOT beige fill)
- [ ] Respondent profile bars have no background track (orange bar in transparent container)
- [ ] Dashboard deployed to site
- [ ] Site nav bar present with Lenny's logo and back link
- [ ] Index page updated with new poll card entry
- [ ] Responsive layout works at 768px breakpoint
- [ ] File is self-contained single HTML (no external dependencies except Google Fonts)
- [ ] Favicon links included in `<head>` of all HTML files
- [ ] Vercel Analytics snippet included before `</body>` in all HTML files
- [ ] OG meta tags added to index.html and dashboard page
- [ ] Social cards page created (`[poll-slug]-social.html`)
- [ ] All social cards are 1200×675px at native resolution
- [ ] Copy to clipboard and Download PNG work on all cards
- [ ] Social cards page has no link from the main dashboard (access by URL only)
- [ ] Newsletter subscribe CTA present above footer on all pages (index, dashboard, social cards)
- [ ] Sticky section navigation present on dashboard with correct section IDs
- [ ] Download PDF button present in dashboard header, print stylesheet hides nav/ToC/CTA
- [ ] Social cards page has mobile button bar (visible below each card on ≤768px)
