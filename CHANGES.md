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
