# Sources (PUBLIC DATA)

All collected on **15 Nov 2026** unless stated. Scripts: `src/download_data.py` (automated, polite: one request at a time, ≥ 2 s apart,
neutral User-Agent, only paths allowed by `robots.txt`, no account, nothing bought). Raw snapshots stay in `data/raw/` (git-ignored).

| Source | What | Where in the repo | Terms / notes |
|---|---|---|---|
| appflame.com | Company description, 8 years, 550+ specialists, four products, stated goals | `data/public/company_facts.csv` | Read in a normal browser page view (the site answers 403 to scripts; not forced). Figures *as stated by appflame*. Website figures used, not the job post's (7 years, 500+). No logo used. |
| hily.com | 44M+ downloads, 58M+ mutual matches a year, 11.9B+ likes sent; name origin | `data/public/company_facts.csv` | Same as above; *as stated by Hily*. |
| Product Analyst job post (LinkedIn, view 4490372369) | "Top 5 dating apps in the U.S.", "70M+ users" | `data/public/company_facts.csv` | *As stated by appflame*. |
| taimi.com | — | — | Refuses automated requests (403): not collected. |
| Apple iTunes Lookup API (`itunes.apple.com/lookup`) | Rating, number of ratings, version, release dates, seller, genre for Hily (1250946975), Taimi (1282966364) and 9 peers, storefronts US, GB, CA, AU | `data/public/appstore_lookup.csv` | Public API, no key. |
| Public App Store pages (`apps.apple.com/<cc>/app/id<id>`) | Star distribution and the "In-App Purchases" price list | `appstore_stars.csv`, `appstore_iap_prices.csv` | Paths allowed by robots.txt. Prices as displayed (VAT-inclusive in GB, DE, FR). |
| Apple customer-review RSS feed | Most recent written reviews (≤ 500 per storefront): Hily and Taimi in US, GB, CA, AU; Tinder, Bumble, Hinge in US | text kept local only; aggregates in `data/output/pub_review_*.csv`; 45 hand labels by review id in `review_validation_labels.csv` | Nicknames and profile links dropped while parsing. Only aggregates and themes are published; no quote. |
| Google Trends (via the unofficial `pytrends` client) | Weekly relative interest, 5 years, US and worldwide by country | `trends_weekly.csv`, `trends_by_country.csv` | Values are relative (0-100) inside one request; "Hily" and "Taimi" are also first names. |
| European Central Bank euro reference rates (daily XML) | USD, GBP, CAD, AUD per EUR, 13 Nov 2026 | `fx_ecb.csv` | Public. |
| Match Group investor relations | Payers Q3 2026 (13.8M); Q2 2026 release: RPP $21.13, payers 13.3M | `industry_benchmarks.csv` | Orders of magnitude for the simulation only. ir.mtch.com |
| Bumble Inc. Form 10-Q, quarter ended 30 Sep 2026 (SEC EDGAR) | Bumble App paying users 2.0M, ARPPU $28.02; Badoo & other ARPPU $11.34 | `industry_benchmarks.csv` | sec.gov/Archives/edgar/data/0001830043/000183004326000123/bmbl-20260930.htm |
| Speed Dating Experiment — R. Fisman, S. Iyengar (Columbia Business School); Fisman, Iyengar, Kamenica & Simonson, *Gender Differences in Mate Selection*, QJE 2006 | 8,378 person × date rows, 551 participants, 21 sessions (2002-2004), both decisions and ratings | downloaded to `data/raw/speed_dating/` by the script (not redistributed) | Public CSV distributed by Columbia University (stat.columbia.edu, Gelman's ARM data page). No licence text attached: used for non-commercial educational analysis, with citation. Race, religion, origin, income and gender fields are **not used**. |
