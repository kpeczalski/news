# Principles (the owner's decisions; every future change must keep them)

1. Just facts. Lines are what outlets report: no background, no context lines, no labels,
   no categories, no war names on the page. Neutral wording; claims keep who says them.
2. Two sections, plain headings only: `// most covered` and `// crises`. No line numbers.
   (`// new in the last 3 hours` appears only when a fresh story grows fast.)
3. Serious world news only: world impact, not people or popularity; a most-covered line needs 10+ countries.
   Accidents state casualties ("at least 32 injured") or "no injuries reported".
3a. Most covered: ranked by reports weighted by spread across countries (deaths up to 1.5x),
   shown by number of countries. Each line: "N countries · +N outlets/h", counter coloured by pace.
4. Crises: violent events (not accidents, speeches or war politics) in an ongoing armed conflict (public list of 1,000+
   deaths a year), plus disasters or attacks covered in 20+ countries. Speeches, talks and
   sanctions stay in most covered. One line per conflict (countries of one conflict count as one).
5. Crisis order: lives first, then recency and reliability; never press coverage. Toll (killed,
   injured/4) on a log scale; any person harmed outweighs an event with no harm to people reported (deaths outweigh
   damage to things); recency halves after 6 h; a toll only one side claims counts half; two papers
   of record add 20%. Within a conflict, the deadliest event of the day is its line.
6. A crisis line says who did what (checked against the headlines; mixed-direction stories are left off) ("Ukrainian strikes kill 9 in Russia"), not who says it,
   when most headlines state the event as fact. Never invert who attacked whom.
7. Sources when a line is opened: the event country's papers of record first (not for
   state-controlled press), then international papers of record, agencies, broadcasters.
8. Wording: pick a real headline before writing one; the model only fills gaps and every
   line passes the same checks. Refuse clickbait, verdict words, celebrity and sport.
9. It runs without anyone: free GitHub hosting, free Groq model with a small local fallback,
   loaded only when needed. Keep the footprint small.
9b. Selection gives a worldwide perspective, not one country's: never tailor to the owner's country.
10. Reviewers get how.html and this file before grading.
11. Improve continuously with independent reviews; log scores in SCORES.md and changes in
    CHANGES.md. Ask the owner before changing any of the points above.

Working rule (owner): a change agreed in conversation is implemented right away; planned reviews are updated after.
