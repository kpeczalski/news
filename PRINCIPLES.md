# Principles (the owner's decisions; every future change must keep them)

1. Just facts. Lines are what outlets report: no background, no context lines, no labels,
   no categories, no war names on the page. Neutral wording; claims keep who says them.
2. Three sections, plain headings only: `// most covered`, `// crises` and `// around the world`. No line numbers.
   (`// new in the last 3 hours` appears only when a fresh story grows fast.)
3. Serious world news only: world impact, not people or popularity (a story about a famous person shows
   only if it involves public office, business with impact, a crime or a death); a most-covered line needs 10+ countries.
   Accidents state casualties ("at least 32 injured") or "no injuries reported".
3a. Most covered: ranked by reports weighted by spread across countries (deaths up to 1.5x),
   shown by number of countries. Each line: "N countries · +N outlets/h", counter coloured by pace.
4. Crises: violent events (not accidents, speeches or war politics) in an ongoing armed conflict (public list of 1,000+
   deaths a year), plus disasters or attacks covered in 20+ countries. Speeches, talks and
   sanctions stay in most covered. One line per conflict (countries of one conflict count as one), up to 6. A most-covered story that is the same event as a crisis line is left off.
5. Crisis order: lives first, then recency and reliability; never press coverage. Toll (killed,
   injured/4) on a log scale; any person harmed outweighs an event with no harm to people reported (deaths outweigh
   damage to things); recency halves after 6 h; a toll only one side claims counts half; two papers
   of record add 20%. Within a conflict, the deadliest event of the day is its line. A crisis event needs 5+ countries, or 3+ when 10 or more were killed, or 10+ when no one is reported harmed (lives first; Africa and Asia get fewer foreign outlets).
6. A crisis line says who did what (checked against the headlines; mixed-direction stories are left off) ("Ukrainian strikes kill 9 in Russia"), not who says it,
   when three quarters of headlines state the event as fact; otherwise the line keeps who says it. Never invert who attacked whom.
7. Sources when a line is opened: the event country's papers of record first (not for
   state-controlled press), then international papers of record, agencies, broadcasters.
8. Wording: pick a real headline before writing one (for a story told mostly in other languages, a
   machine translation of real headlines, owner-approved 18 Nov); the model only fills gaps and every
   line passes the same checks. Refuse clickbait, verdict words, celebrity and sport.
9. It runs without anyone: free GitHub hosting, free Groq model with a small local fallback,
   loaded only when needed. Keep the footprint small.
4a. Around the world: the biggest story of each region (Africa, Asia-Pacific, Latin America, Europe,
   the Middle East) not already on the page, carried in 3+ countries (2+ for Africa and Latin America), same
   checks as most covered, no ceremonies or index moves; up to 5 lines (owner, 19 Nov).
9b. Selection gives a worldwide perspective, not one country's: never tailor to the owner's country.
   At most 2 US-centred most-covered lines (none in around the world); no daily stock-index moves unless covered in 40+ countries
   (owner gave carte blanche for score improvements, 19 Nov).
10. Reviewers get how.html and this file before grading.
11. Improve continuously with independent reviews; log scores in SCORES.md and changes in
    CHANGES.md. Ask the owner before changing any of the points above.

Working rule (owner): a change agreed in conversation is implemented right away; planned reviews are updated after.

## Known limits of this setup (reviewers: grade against what is achievable here)
- Input is headlines only (GDELT): no article text, no wire services' own sites (Reuters, AP, AFP
  appear only as reprints). The site cannot check facts; it can only report what most outlets say.
- English plus machine-translated outlets; English-language media are over-represented, so regions
  with little coverage (Sudan, Myanmar, DR Congo) appear only when outlets report them.
- Death tolls and claims are whatever headlines state, often early and from one side.
- A small free model (Groq) writes a line only when no real headline passes the checks; it has no web.
- Updates about every 30 minutes (GitHub runs about hourly, plus one refresh).
- On quiet days (weekends, nights) fewer outlets publish, so smaller stories reach the page.
- Grade only problems a fixed rule in this code could solve; name a limit as a limit, not a fault.
