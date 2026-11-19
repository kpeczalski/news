# Changes

Newest first. Each change is applied only if the rule tests in `test_build.py` pass.

## 2026-11-13, 16:00
Towards 10 on all three:
- A named person linked to wrongdoing needs a source or qualifier in the line; "former"/"ex" only
  when most headlines say so.
- Add-ons are trimmed when the shorter headline still carries the story; proper names no longer
  count as Title Case shouting.
- At most 3 lines per world region; common name spellings across languages folded.
- Each line shows countries (what the order uses) and new outlets per hour.

## 2026-11-13, 15:25
- Verdict words ("scandal", "disgraced", "embattled") are refused in any line.

## 2026-11-13, 15:15
After a review of the model setup:
- Pick, don't write: a real headline that passes every check is used as printed; the model only
  writes when none does. (qwen3:4b was tried and dropped: it printed its reasoning instead of a
  sentence; back to qwen3:1.7b with 3 tries.)

## 2026-11-13, 15:00
- Words that only repeat shared names (e.g. "nvidia") no longer link two stories; the biggest
  stories can use a widely printed headline again (support capped at 6 wordings).
- Sport also recognised by GDELT's own topic tags, not only by headline words.

## 2026-11-13, 14:50
- A real headline printed word for word by a third of the outlets is used whole (it is what
  most outlets say), giving lines their context. Retries ask for context instead of fewer words.

## 2026-11-13, 14:40
- Clearer lines: the model is asked for who, what, where and what it is about, in up to 12 words;
  a sentence must carry at least half of the story's shared words, and a retry names them.

## 2026-11-13, 14:30
- Website only from now on. Non-English outlets match a story on two shared main names, one of
  which belongs to the story (was: two uncommon names).

## 2026-11-13, 14:00
After a review of the website (accuracy 4, selection 5, readability 7.5):
- A real headline is used only if every word is common in the story (15% of wordings in big
  stories), so one outlet's colour ("scandal", "worldwide") never reaches the page.
- Header says the order is by spread across countries.

## 2026-11-13, 13:50
- Fragments of one big event (the Microsoft outage was split over 15 stories) are merged before
  ranking; a name found everywhere (EU, a capital) no longer links stories.
- No "Reports:" prefix when the line already hedges ("alleged", "suspected").

## 2026-11-13, 13:35
- "allegations of" / "reports of" count as a kept qualifier; small stories left as counted words
  are not listed.

## 2026-11-13, 13:25
- Model gets a second try that shortens the most printed headline; a qualifier kept in place
  ("suspected spy") counts as attribution; wider cricket filter.
- "How this works" rewritten to match the current rules.

## 2026-11-13, 13:15
- Website live at kpeczalski.github.io/news (GitHub, small model qwen3:1.7b).
- Fragments of one big event fold into one line even when its names are everywhere
  (shared main name plus distinctive shared words).

## 2026-11-13, 09:40
- Renamed to news; the desktop shortcut is now "news" (the old "facts" shortcut is removed).

## 2026-11-13, 09:35
- Fetches 3 minutes after each quarter hour (was 7) and retries every 2 minutes if the batch is late.
- Open page checks every 2 minutes (was 5); status bar shows "news up to HH:MM".

## 2026-11-13, 08:35
- Morning check: ran all night as a single copy, no errors, 15 hours of history.
- Fixed: a fragment of the held-back DC shooting reappeared as counted words; a fragment is now tied
  to its story when one shared place name belongs to that story even if the other is common.

## 2026-11-12, 22:25
- The section title states the real time span ("last 4 hours") until 24 hours have been collected.
- A fallback can use the opening of a real headline, up to its first add-on.
- An accepted sentence is kept for as long as it still passes the checks.

## 2026-11-12, 22:20
- Sources: after the renowned list (now also newspapers of record), outlets are ordered by size;
  a renowned outlet's headline is always kept, even for stories with hundreds of outlets.
- Headlines lose "The Latest:" prefixes and " : NPR" suffixes; question headlines are ignored.
- A story needs a minimum weight to be listed, so the list is short on a quiet night.

## 2026-11-12, 22:10
After the fourth round of grades (accuracy 7, selection 6, readability 8.5):
- A fallback headline must carry at least two thirds of the story's counted words.
- A hedged line with no named speaker opens with "Reports:"; the side label is kept only for counted lines.
- Domestic news is listed only if 50+ outlets in other languages carry it; a remark nobody abroad
  picked up is not listed.
- Header says the order is by world coverage. A first run now looks back 8 hours.

## 2026-11-12, 22:05
After the third round of grades (accuracy 6, selection 6, readability 8.5):
- A word the headlines qualify ("alleged affair") may only appear with its qualifier.
- Country shares are counted per wording, so agency reprints no longer make a foreign story look
  domestic; stories with no outlet in another language weigh 0.6; company resignations get no bonus.
- Page: "US" spelling; the claim label is not repeated when the line names its source; the unit is
  shown once in the section header.

## 2026-11-12, 21:55
- Numbers inside names (GLP-1, COVID-19, G7) are no longer read as quantities.
- A claim may use 12 words, so its source fits ("Health Ministry says ...").
- A fragment of a story that is held back as domestic is held back too.
- "kills 6" is counted as 6 dead; word forms (warns, warned, warning) support each other; when a
  sentence fails only because of an add-on, the part before the add-on is used if it passes.
- More colour words refused (emotional, beloved, dramatic, historic ...).

## 2026-11-12, 21:50
- Fixed: two copies could run at once on Windows and damage each other's files (the port could be
  bound twice). Only one copy can run now; a new start waits for the old one to finish.
- A damaged memory file is set aside and rebuilt instead of blocking every update.

## 2026-11-12, 21:45
After the second round of grades (accuracy 7, selection 5, readability 8):
- Selection: domestic weight 0.1; international floor; at most 2 lines per country; affairs of state
  weigh 1.5x; agency reprints count 0.3 once in 3+ countries.
- Accuracy: fallback headlines pass the same word and number checks; hedged wording is labelled a
  claim; a source must be named the same way in two headlines.
- Style: numbers as digits; "+14/h".

## 2026-11-12, 21:30
- Sources: renowned agencies and public broadcasters come first (editable list in
  rules/preferred_sources.txt); their headline is preferred as a fallback and is shown first to the model.

## 2026-11-12, 21:25
After three independent grades of the live page (accuracy 4, selection 4, readability 6):
- Accuracy: a sentence may only use numbers the counted line states (spelled-out numbers included);
  one fact per line, at most 10 words, no add-on clause; a claim must name its source up front as
  the headlines do; "toll rises to 8" is counted as 8 dead.
- Selection: domestic news weighs 0.3; sport and entertainment are ignored; outlets in other
  languages now match big events and count 0.5.
- The program now runs with no window (it was being closed by accident; the log recorded
  "the window was closed"). The desktop shortcut starts or restarts it; "Stop facts" is on the
  "how this works" page.
- Page: counts row is outlets and "+N this hour" only; labels are one word; the "new" section is
  hidden when empty.

## 2026-11-12, 21:15
- World weighting: rank now depends on how evenly coverage is shared between countries, not on
  how many countries have at least one outlet; outlets in other languages count 0.3 each.
- "New" section lists a story only once it has real coverage; it can be empty on a quiet evening.
- Stories reprinted by 30 or more outlets can get a sentence even if all use one agency text.

## 2026-11-12, 21:10
- Two sections: stories new in the last 3 hours, and the biggest stories of the last 24 hours
  that began earlier. Ranking now counts the whole 24 hours.

## 2026-11-12, 21:05
- When a sentence is refused for a word the headlines do not support, the second attempt
  is told exactly which words to avoid (fewer lines stuck on counted words).
- One line per event now uses the event's three main names.
- When no model sentence passes, the line shows the plain headline printed word for word by the most outlets.

## 2026-11-12, 21:00
After an independent grade of the live page (5 out of 10):
- One line per event; reactions and follow-ups are counted under it.
- Commentary and explainer headlines are ignored.
- Stories reported from few countries weigh less.

## 2026-11-12, 20:55
- Lines whose sentence was rejected under older rules are retried when the rules change
  (they were stuck on counted words). A second attempt asks for at most 10 words.

## 2026-11-12, 20:50
- Renamed to facts (lowercase). Desktop shortcut "facts" is now created by the program itself and any failure is logged.
- From the first live run with sentences: leftover duplicate lines for one big event are merged
  (four shared names and three shared words suffice); "5 people shot" is counted as a fact about
  "shot"; "U.S." no longer reads as two sentences; the word-order rule applies to names only;
  claims are asked to keep the headline's own attribution word.
- The rule tests now run on Windows (they failed there, which would have blocked every update).

## 2026-11-12, evening
- Sentence checker tightened after an adversarial review: words need two differently worded
  headlines; numbers stay with their word; word order must occur in a headline; attribution kept
  for claims; no model sentence for disputed stories; one sentence only.
- Story grouping: a name counts as evidence only if it belongs to the story; counters follow
  outlets as they expire or merge; small fragments are folded into leading stories;
  acronyms match in any case; "shooting"/"shot" match.
- Non-English outlets: an article now waits up to two hours for its story to form.
- Page: counts first and labels after, one accent colour, story numbers start at 1,
  tighter expanded view, wider text column on phones, 24-hour times.
- Runner: starting again replaces a running copy; desktop shortcut created on first start;
  retries after an error; `out/run.log` and `out/diag.json` record what each run did.

## 2026-11-13, 17:00
- Review: accuracy 6, selection 5, readability 6.5. Counted-word lines ("nvidia: CEO jensen huang chinese") were the main drag.
- A story with no clear sentence or headline is now left off; spare candidates fill its place. Up to 9 day lines.
- Every line shows its hourly rate (+0 included); legend says how lines are ranked.
- Sport/flash filter: "fires back", "nonsense", cricket terms (a cricket spat slipped in as a spare).

## 2026-11-13, 15:10 (Helsinki)
- Why the page was thin: the biggest story (Nvidia) and two Iran stories had good headlines that were refused (Title Case, single print, "disputed" tag), and they used up the country cap before being dropped.
- Title Case headlines are put in sentence case using the story's own lower-case words; "reports" counts as attribution.
- In a big story a headline printed once may be used, since every word is checked against many headlines.
- A disputed story may show a headline that carries the denial; a small story may show a headline that names no person.
- Country and region caps count only lines actually shown.
- Lines that fit on one line (80 characters) are preferred; the page window is wider (880 px).
- "quietly", "bluntly" refused. diag.json lists why candidates were left off.

## 2026-11-13, 15:20 (Helsinki)
- Review: accuracy 5, selection 5, readability 6.5. Main point: a named person tied to an allegation on the front line.
- A headline's "amid ..." add-on, or an allegation about a named person, is cut off when the core fact alone passes ("Nvidia CEO Jensen Huang resigns"). The full headlines stay in the opened line.
- "rekindles", "heartwarming" refused.

## 2026-11-13, 15:10 (Helsinki)
- Bigger model: gpt-oss-120b (Llama 3.3 was not offered) on Groq's free tier writes the sentence when no headline fits (key in the LLM_API_KEY secret). Falls back to the local qwen3:1.7b after 3 failed calls, or when the key is missing.
- Celebrity stories skipped by GDELT topic tags (actors, singers, celebrities), like sport.

## 2026-11-13, 15:40 (Helsinki)
- Learning loop: every sentence the big model writes that passes all checks (and every accepted headline) is kept as an example (last 300, in state). When the small fallback model writes, it is shown the 3 most similar examples first. examples.jsonl is published as a training set for a later fine-tune.

## 2026-11-13, 17:00 (Helsinki)
- Readability: headlines in a plain reading font (the window, numbers and notes stay monospace); line labels simplified to "N countries" plus "rising"; counted words no longer shown when a line is opened.
- Sources: agency copy (AP, Reuters, AFP) reprinted on other sites is recognised from the address and listed first as "AP via wral.com". Reuters, AP and AFP own sites are not in the GDELT feed.
- Sources order (user request): newspapers of record first (NYT, Guardian, FT, WSJ, Washington Post, Economist, Le Monde, El Pais, Spiegel, Bloomberg, SCMP, The Hindu, Japan Times, Straits Times, HS), then agencies and their reprinted copy, then public broadcasters.
- Sources: renowned papers from the country where it happened come first (no home advantage where the press is state-controlled); 30 papers of record by country added.
- Hourly counter coloured by pace: grey under 3, plain 3-9, green 10-29, amber 30+.
- Footprint: the 1.4 GB local model is loaded only when the hosted model does not answer.

## 2026-11-13, 17:40 (Helsinki)
- Loss of life weighs more (up to 1.5x when most reports tell of deaths), from GDELT counts or headline words.
- New "ongoing crises" section: crisis coverage added up per country over 7 days (or 4+ separate stories today), largest crises not on the page get one line.
- Two sections (user): "most covered" and "crises" (wars, attacks, disasters by headline words; one line per country; raised by up to 2x for crises covered most days of the week). One-week history backfilled from GDELT, a few past files per run. Individual deaths ("dies") are not crises and do not get the life weight.
- Review fixes: crises section takes events only (not speeches), one line per conflict (Israel/Gaza/West Bank together, Russia/Ukraine together); "most covered" shown in order of countries; "disputed" label now "claims differ"; section labels simplified.
- Model prompt: subject-verb-object, right prepositions, no "-ing" add-ons; "drawing/prompting/sparking..." now cut as add-ons. Rules version 27 (all model lines rewritten).
- Most covered needs score 12 (was 8): drops niche business filler.
- Accidents (collapse, crash, fire, capsizing) count as crises only when covered in 20+ countries.
- Crises limited to known armed conflicts (17, from the list of ongoing wars, incl. the Iran war) plus disasters/attacks covered in 20+ countries; lines labelled with the conflict name.
- Crises ordered by human toll from the headlines (killed, then injured, median across headlines), then latest; not by coverage (user).
- Review round (fairness, editor, design): tolls use the lower end of ranges; a toll most headlines attribute to a party ("military says") counts half in the crisis order; a named person resigning/dying/arrested/ousted is shown as fact only with 2+ papers of record, else marked a claim; "claims differ" -> "reports disagree".
- Crisis lines say who did what: a headline without says/claims comes first; an event most headlines state as fact is not forced to carry attribution. (The Russia line was a Ukrainian strike in Russia; now "Ukrainian strikes kill 9 in Russia".)
- Crises ordered latest first (not by toll or coverage); each conflict shows its most widely reported event of the day.
- Context line under crisis lines of long wars: one dated documented fact on how the war began (Russia–Ukraine: full-scale invasion 24 Feb 2022; Israel–Gaza: Hamas-led attack 7 Oct 2023 and Israel campaign in Gaza).
- Context line removed for Israel and the Palestinian territories (a longer conflict; any single start date frames it). Kept only where the start is undisputed (Russia–Ukraine).
- No background lines: crisis lines show only the day's headline (user: just facts).
- Fix: "TRANSPORT" no longer matches the sport tag (it hid a Russian attack on Ukraine as sport). "attack(s)" count as crisis words again. A crisis falls back to its next event when the first gets no clear line; one line per conflict.
- Crises order: recency (halves after 6 h) x toll (log scale) x reliability (one-side claims half, 2 papers of record +20%). No line numbers on the page (user).
- Crises: an event with no reported toll weighs like ~9 killed (not zero), so a large attack still unfolding is not ranked last.
- Crisis lines: who attacked whom is checked against the headlines (Russia/Ukraine, Israel/Gaza); a story whose headlines point both ways (two events merged) is left off, a line pointing the other way is dropped; "shoots down/intercepts" reverses the actor.
- Crisis lines: sources telling the opposite-direction event are not listed under the line; a headline stating the toll is preferred.
- Crisis lines keep the toll: a line without it is replaced by a passing headline that states the median toll.
- Readability: country/outlet counts smaller and lighter; a little more space between lines.
- Evening review: no labels on lines ("reports disagree" removed, owner rule); the model uses the most-reported number with its source, never a range (rules 28).

## 2026-11-14, 12:20 (Helsinki)
- Freshness: GitHub starts scheduled runs only about once an hour (gaps of 45-75 min seen); each scheduled run publishes once more about 30 minutes later (news at most ~30 min old; a 15-min loop was judged not worth the footprint).
- Crises: a story belongs to a conflict where it happened OR when most reports name a conflict country (US-Iran clashes over Bahrain = Iran war). Accidents (crash, collision, collapse...) are not crises unless covered in 20+ countries, even in conflict countries. Words of war politics ("war", "military", "ceasefire") no longer make a story a crisis; violent-event words do. Stories that are not crises stay in most covered instead of vanishing.
- "unprecedented" and "another" refused (hype; assumes context).
- Crises: lives first (toll weighted x2 on a log scale; no reported toll = ~1 killed, so deaths outweigh infrastructure); within a conflict the deadliest event is shown (owner).
- Who-attacked-whom check extended to the Iran war (US/Israel vs Iran): a line telling both directions is left off.
- Crises: any person killed or injured (even without a number) ranks above harm to things; "another" is dropped from headlines instead of refusing them (keeps "Former Ukrainian prime minister's adviser injured in Moscow car bombing").
- Exceptional domestic events (1,000+ outlets, e.g. FAA grounding all US flights, 1,550 outlets in 53 countries) are no longer held back as domestic news.
- Crisis lines: tolls in an add-on (", injures 28") are no longer cut off; passive headlines ("6 Palestinians killed in Israeli strikes") read the right attacker; within a conflict, cumulative figures in a few outlets are not taken as the day's event; "injure around 20" parsed.
- Crisis lines add "at least N injured" (the lowest number 2+ headlines give) when outlets disagree on the injured count.
- Crisis lines prefer the headline naming more of the shared specifics ("Nasser hospital").
- Most covered needs 10+ countries (drops soft single-country items like "King Charles jokes with Elton John"); "jokes/laughs" refused. Accidents state casualties ("at least 32 injured") or "no injuries reported" when 2+ headlines say so.
- Accidents: ", no deaths" when 2+ headlines say so explicitly and none reports a death.
- Lines prefer the scale when outlets give it ("FAA lifts nationwide ground stop..."), and short over long ("Tanker collides with cruise ship ..., at least 32 injured, no deaths").
- Bombs, blasts, explosions, shootings, assassinations count as crisis events (the Moscow bombings moved to crises). Stories with 20%+ celebrity-tagged reports are left off (was 40%).
- Survival headlines ("All passengers and crew ... survive") count as stating the toll. "At least N injured" only from headlines with the same death count as the line. News roundups ("..., and other Mideast news") blocked.
- Lines follow the latest development: once 15%+ of headlines report the outcome (lifted, resumed, restored, freed...), a headline with it comes first; then headlines from the last 6 hours ("FAA lifts nationwide ground stop for flights").
- Daily review: a named person resigning/arrested/dying is never in model words: a real passing headline, or the line is left off.

## 2026-11-15 (Helsinki)
- Colon wording for accidents with no deaths ("...in New Orleans: 32 injured, no deaths"); the injured number most headlines give, "at least" the lowest only when they differ.
- Free health check on every build (no model): too few lines, stale news, roundup/analysis wording, long lines, crisis lines missing their toll or in model words; listed as "warnings" in diag.json and read by a morning check.
- App icon (same as the desktop one): favicon, home-screen icon (iOS/Android), web app manifest so "Add to Home Screen" opens it like an app.
- Model prompt: a complete grammatical sentence, never a list of words; rules 29 (model lines rewritten).
- A list of shared words is refused as a line (5+ words, no grammar words, at most one non-shared word: "Kushner says Europe Russia peace talks"). Mine blasts and gas leaks count as accidents (not crises).

## 2026-11-16 (Helsinki), morning check
- Crises exclude stories about a crisis that are not the violent event: visits, speeches, courts ("Harry tells wounded veterans...", "Jordan sentences 3 men..."); crisis lines prefer a headline without such words; "planes collide on taxiway" is an accident (18 countries, not a crisis); the health check reads "kills senior commander" as a toll.
- Daily review 16 Nov: "new" also needs 10+ countries (a Pope farewell in 5 countries showed); royal soft news blocked (prince/princess/duke/duchess, not "crown prince": Harry and William visits).
- Reviewers now read the known limits of the setup (in PRINCIPLES.md) and grade against what is achievable.

## 2026-11-17 (Helsinki), morning check
- A model line must name who or where (a capitalised word after the first): "Police search for missing girls" is left off.

## 2026-11-17 (Helsinki), daily review
- Crisis lines are real headlines only (a model line jammed two events: "Third US carrier arrives ... Iran strike on Bahrain targets").
- A plan is not a fact: when 30%+ of headlines speak of something as coming, a model line must too ("Trump meets Xi and Putin" for a planned meeting is refused).
- Health claims about a named person ("may not return alive") need a real headline.
- Model lines with may/could/might need a source; crisis lines prefer a headline without "as"/"while" (one event, not two).

## 2026-11-18 (Helsinki), morning check
- "pogrom" refused as a loaded word: the line falls back to a plainer headline of the same event.
- Totals keep their time frame: "Drone strikes killed more than 1,630 civilians in Sudan this year" (frame taken from the headlines with the same figure). "pogrom" refused.
- From a 6-day pattern review (3 analysts): every name in a line must appear in the headlines of 2+ outlets (stops "UK" when sources say Australia); sources under a line sorted by closeness to it (no topic drift); soft items blocked (word of the year, dictionaries, exam cheating); a time frame is only added to a line with a figure, from headlines with that figure.
- At most 2 tech or company stories in most covered (TECH words in half the sources), leaving room for world news. Re-grade after the pattern fixes: accuracy 7, selection 5, readability 7.
- Yesterday's news counts half: a story first seen 30+ hours ago that fewer than 3 outlets joined in the last hour.
- Round 1 of the improvement loop: a headline printed word for word by many outlets (a wire) counts as shared wording; "2-month lull" is a span of time, not a figure to check (the Iran-Bahrain strike was lost to these two); emotional words refused (heartbroken, devastated, tragic).
- Round 2: a company's own affairs (board, product) with no state or market-wide actor count 0.6x (not a CEO resigning or being arrested). Scores round 2: accuracy 8, selection 6, readability 7.
- Big stories no longer lost for "no clear sentence" when outlets disagree: a disputed story shows its most shared denial headline ("Nvidia chairman says board does not intend to reinstate Jensen Huang", 36 countries); "not" counts as a denial.
- Thin pages (nights, weekends) fill up to 7 most-covered lines with stories down to score 8 (still 10+ countries).
- Foreign stories (owner-approved): translated-feed articles that match no English story are grouped by shared names; at 15+ outlets in 10+ countries, up to 10 headlines are machine-translated and the line is picked from them with the usual checks.
- Foreign stories, fix: version 1 linked articles on common names (one 247-outlet blob of "United States/Beijing" stories); now only names in under 0.2% of all articles link, and clusters start over. Clickbait guides and video games blocked ("everything you need to know", GTA VI).
- People stories left off: a story whose reports mostly name one person and that involves no public office (GDELT office tag, titles, known leaders), no business impact, no crime or death ("David Beckham sues after fragrance sold in gas stations").
- Foreign stories, fix 2: clusters were topic blobs (EU affairs, Spanish politics) linked by generic organisation names; now only people and places link, and clusters start over.

## 2026-11-18 (Helsinki), daily review
- Crises: sanctions and threats are not violent events ("Australia sanctions Israeli settlers..." and "Iran threatens to strike..." left off); an injured count is only added to a line that tells the violent event or accident itself.
- Foreign stories: a cluster now needs three shared names (two only for an article naming two); the translated "Trump, Putin and Xi meet in Shenzhen" repeated the English top line and had merged the Crimean bridge attack. Foreign lines whose translated headlines share 3 of the top 8 words with a big English story are left off. Clusters restart (fx_v 4).

## 2026-11-19 (Helsinki), daily review
- A forecast keeps its target year ("Muslims projected to outnumber Christians" -> "... by 2035") when 30%+ of headlines give one year.
- World page: at most 3 US-centred most-covered lines (US as event country, or most headlines about US actors); a day's stock-index move ("Dow takes major hit") is left off unless 40+ countries carry it; a headline led by a quote ranks after one that states the news; question headlines go last among sources. Owner gave carte blanche (19 Nov).
- Crises: an event with 10+ killed needs 3 countries instead of 5 (lives first; conflicts in Africa and Asia get fewer foreign outlets).
- Headline cut: never inside a list of names ("Trump says summit with Xi, Putin ..." was cut to "Trump says summit with Xi"); the quote rule is judged on the printed headline, so cutting a quote off no longer wins.
- Phone: larger tap targets for sources and copy link (about 41px), opened sources 16px, narrower empty gutter; the counter stays small (owner asked) but at full opacity.

## 2026-11-19 (Helsinki), selection review
- Stories are ranked from the 150 largest by outlets plus the 100 carried in most countries: syndicated US/UK local news no longer crowds out events that 30 outlets carry in 12+ countries (the Gaza ground operation was never ranked).
- Crises reach more conflicts: tanks, incursions and raids are violent events; "killed 22 militants" is read as a toll; a deadly event (10+ killed, 3+ countries) needs no coverage weight and may be a claimed toll (shown with its source, half weight); up to 6 crisis lines.
- Lives first, strictly: any event with people killed or injured is ordered before one with no harm to people reported.
- One event once: a most-covered story of the same conflict at the same places as a crisis line is left off.
- A leader's statement about violence with no one harmed ("Trump says US will strike...") is a speech, not a crisis event.
