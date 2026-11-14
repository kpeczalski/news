# Principles (the owner's decisions; every future change must keep them)

1. Just facts. Lines are what outlets report: no background, no context lines, no labels,
   no categories, no war names on the page. Neutral wording; claims keep who says them.
2. Two sections, plain headings only: `// most covered` and `// crises`. No line numbers.
   (`// new in the last 3 hours` appears only when a fresh story grows fast.)
3. Most covered: ranked by reports weighted by spread across countries (deaths up to 1.5x),
   shown by number of countries. Each line: "N countries · +N outlets/h", counter coloured by pace.
4. Crises: violent events (not accidents, speeches or war politics) in an ongoing armed conflict (public list of 1,000+
   deaths a year), plus disasters or attacks covered in 20+ countries. Speeches, talks and
   sanctions stay in most covered. One line per conflict (countries of one conflict count as one).
5. Crisis order is a mix of recency, death toll and reliability, never press coverage:
   recency halves after 6 h; toll on a log scale; an unreported toll is not zero (weighs like
   ~9 killed); a toll only one side claims counts half; two papers of record add 20%.
   Example kept as a check: a large Russian attack on Ukraine with no toll yet ranks above a
   one-sided military claim of militants killed.
6. A crisis line says who did what (checked against the headlines; mixed-direction stories are left off) ("Ukrainian strikes kill 9 in Russia"), not who says it,
   when most headlines state the event as fact. Never invert who attacked whom.
7. Sources when a line is opened: the event country's papers of record first (not for
   state-controlled press), then international papers of record, agencies, broadcasters.
8. Wording: pick a real headline before writing one; the model only fills gaps and every
   line passes the same checks. Refuse clickbait, verdict words, celebrity and sport.
9. It runs without anyone: free GitHub hosting, free Groq model with a small local fallback,
   loaded only when needed. Keep the footprint small.
10. Improve continuously with independent reviews; log scores in SCORES.md and changes in
    CHANGES.md. Ask the owner before changing any of the points above.
