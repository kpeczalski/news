"""Run with: python3 -m unittest -v test_build   (no network needed)"""
import gzip, json, os, pathlib, shutil, tempfile, unittest, zipfile
import build as B

os.environ["BACKFILL"] = "0"
B.CRISIS_SECTION = False          # most test stories are disasters; the crises section has its own test
B.AI = "off"                       # tests never call a model; the writer is tested with a stub
B.NEW_MIN_SCORE = 0                # most tests use tiny stories; the threshold has its own test
B.MIN_SPREAD = 0                   # likewise the international floor
B.DAY_MIN_SCORE = 0
B.AI_TRIES = 4                     # tests do not depend on the deployment's settings
B.COUNTED_MIN_SCORE = 0


def art(domain, title, loc="", persons="", translated=False):
    f = [""] * 27
    f[9], f[11] = loc, persons
    return {"domain": domain, "url": "https://%s/x" % domain, "title": title, "slug": False,
            "ents": B.entities(f), "toks": [] if translated else B.tokenise(title)}


def run(batches, **over):
    """batches: list of (slot, [english arts], [translated arts]). Returns (state, payload)."""
    st = B.new_state()
    last = 0
    for slot, en, tr in batches:
        B.cluster_slot(st, en, slot)
        B.attach_translated(st, tr, slot)
        last = slot
    st["last"] = last
    B.prune(st, last)
    return st, B.render(st, last, over.get("cmap", {}), 0)


class Text(unittest.TestCase):
    def keys(self, t):
        return [k for k, _ in B.tokenise(t)]

    def test_negation_survives(self):
        self.assertIn("not", self.keys("Minister not charged in fraud case"))
        self.assertIn("not", self.keys("Minister wasn't charged in fraud case"))
        self.assertIn("never", self.keys("Minister never charged"))
        self.assertIn("no", self.keys("Talks end with no breakthrough"))

    def test_modals_survive(self):
        self.assertIn("could", self.keys("Storm could hit coast Friday"))
        self.assertIn("may", self.keys("Bank may raise rates"))

    def test_hedges_flagged_not_printed(self):
        self.assertNotIn("say", self.keys("Officials say 40 dead"))
        self.assertEqual(B.title_flags("Hamas says 40 dead"), (True, False, False))
        self.assertEqual(B.title_flags("Minister denies fraud"), (False, False, True))
        self.assertEqual(B.title_flags("Minister didn't resign"), (False, True, False))

    def test_synonyms_numbers_acronyms(self):
        self.assertEqual(self.keys("Eight killed, 17 hurt as US envoys arrive"),
                         ["8", "dead", "17", "injured", "us", "envoy", "arrive"])

    def test_clean_title(self):
        self.assertEqual(B.clean_title("At least 8 killed in Brooklyn collapse - CBS New York"),
                         "At least 8 killed in Brooklyn collapse")
        self.assertEqual(B.clean_title("Big story about the thing | Reuters"), "Big story about the thing")
        self.assertEqual(B.clean_title("Nvidia CEO Jensen Huang resigns amid spy scandal : NPR"), "Nvidia CEO Jensen Huang resigns amid spy scandal")
        self.assertEqual(B.clean_title("The Latest: Nvidia CEO resigns after affair raises concerns"), "Nvidia CEO resigns after affair raises concerns")
        self.assertEqual(B.clean_title("Short - but not an outlet suffix at all here"),
                         "Short - but not an outlet suffix at all here")

    def test_slug_title(self):
        self.assertEqual(B.slug_title("https://x.com/news/2026/brooklyn-building-collapse-kills-eight-123.html"),
                         "brooklyn building collapse kills eight")
        self.assertEqual(B.slug_title("https://x.com/a/12345"), "")

    def test_country_of(self):
        cmap = {"bbc.co.uk": "UK", "yle.fi": "FI"}
        self.assertEqual(B.country_of("news.bbc.co.uk", cmap), "UK")
        self.assertEqual(B.country_of("example.de", {}), "GM")
        self.assertIsNone(B.country_of("example.com", {}))


class Stories(unittest.TestCase):
    def setUp(self):
        self._saved = (B.MIN_OUTLETS, B.NAME_MIN)
        B.MIN_OUTLETS, B.NAME_MIN = 3, 3

    def tearDown(self):
        B.MIN_OUTLETS, B.NAME_MIN = self._saved

    def line(self, payload, key):
        hits = [l for l in payload["lines"] if l["key"] == key]
        self.assertTrue(hits, "no line with key %r in %r" % (key, [l["key"] for l in payload["lines"]]))
        return hits[0]

    def test_wire_copy_counts_once(self):
        loc = "3#Springfield, Illinois, United States#US#USIL#1#1#1"
        wire = [art("local%d.com" % i, "Bridge collapses in Springfield, 4 dead", loc) for i in range(6)]
        own = [art("a.com", "Springfield bridge collapse leaves 4 dead", loc),
               art("b.com", "4 dead after bridge collapses in Springfield", loc)]
        _, p = run([(100, wire + own, [])])
        l = self.line(p, "springfield")
        self.assertEqual(l["outlets"], 8)
        self.assertEqual(l["wordings"], 3)

    def test_wordings_outrank_volume(self):
        loc_a, loc_b = "4#Lima, Peru#PE#PE#1#1#1", "4#Oslo, Norway#NO#NO#1#1#2"
        reprint = [art("chain%d.com" % i, "Mayor opens new library in Oslo centre", loc_b) for i in range(10)]
        varied = [art("p.com", "Earthquake strikes Lima, 3 dead", loc_a),
                  art("q.com", "Lima earthquake leaves 3 dead", loc_a),
                  art("r.com", "3 dead as earthquake hits Lima", loc_a),
                  art("s.com", "Strong earthquake shakes Lima, 3 dead", loc_a)]
        _, p = run([(100, reprint + varied, [])])
        self.assertEqual(p["lines"][0]["key"], "lima")

    def test_updated_figures_replace_old(self):
        loc = "4#Lima, Peru#PE#PE#1#1#1"
        doms = ["a.com", "b.com", "c.com", "d.com", "e.com", "f.com"]
        early = [art(d, "Earthquake strikes Lima, %s dead" % "3", loc) for d in doms]
        early[1] = art("b.com", "Lima earthquake leaves 3 dead", loc)
        late = [art(d, "Earthquake strikes Lima, 11 dead", loc) for d in doms]
        late[1] = art("b.com", "Lima earthquake leaves 11 dead", loc)
        _, p = run([(100, early, []), (104, late, [])])
        l = self.line(p, "lima")
        self.assertIn("11 dead", l["text"])
        self.assertNotIn("3 dead", l["text"])
        self.assertEqual(l["outlets"], 6)            # still one vote per outlet

    def test_disagreeing_numbers_show_range(self):
        loc = "4#Lima, Peru#PE#PE#1#1#1"
        arts = [art("a.com", "Earthquake strikes Lima, 8 dead", loc),
                art("b.com", "Lima earthquake: 8 dead", loc),
                art("c.com", "Earthquake in Lima leaves 9 dead", loc),
                art("d.com", "9 dead in Lima earthquake", loc)]
        _, p = run([(100, arts, [])])
        self.assertIn("8–9 dead", self.line(p, "lima")["text"])

    def test_majority_negation_stays_in_line(self):
        arts = [art("a.com", "Finance minister not charged in fraud probe"),
                art("b.com", "Fraud probe: finance minister not charged"),
                art("c.com", "Finance minister will not be charged after fraud probe"),
                art("d.com", "Prosecutors: finance minister not charged in fraud probe"),
                art("e.com", "Finance minister not charged as fraud probe closes")]
        _, p = run([(100, arts, [])])
        l = p["lines"][0]
        self.assertIn("not", (l["key"] + " " + l["text"]).split())
        self.assertNotIn("disputed", l["tags"])

    def test_minority_negation_is_disputed(self):
        arts = [art("a.com", "Finance minister charged in fraud probe"),
                art("b.com", "Fraud probe: finance minister charged"),
                art("c.com", "Finance minister charged after fraud probe"),
                art("d.com", "Finance minister charged as fraud probe widens"),
                art("e.com", "Finance minister not charged in fraud probe, lawyer insists")]
        _, p = run([(100, arts, [])])
        self.assertIn("disputed", p["lines"][0]["tags"])

    def test_hedged_story_is_claim(self):
        arts = [art("a.com", "Army says 40 rebels dead in border clash"),
                art("b.com", "40 rebels dead in border clash, army claims"),
                art("c.com", "Border clash leaves 40 rebels dead"),
                art("d.com", "Army: 40 rebels dead after border clash")]
        _, p = run([(100, arts, [])])
        self.assertIn("claim", p["lines"][0]["tags"])

    def test_early_tag_expires(self):
        arts = [art("%s.com" % c, "Volcano erupts on Etna slope, village evacuated %s" % c) for c in "abcd"]
        _, p = run([(100, arts, [])])
        self.assertIn("early", p["lines"][0]["tags"])
        _, p = run([(100, arts, []), (100 + B.EARLY, [art("z.com", "Volcano erupts on Etna slope again")], [])])
        self.assertNotIn("early", p["lines"][0]["tags"])

    def test_person_named_only_above_threshold(self):
        who = "john example"
        titles = ["John Example arrested in harbour raid", "Harbour raid: John Example arrested",
                  "Police arrest John Example after harbour raid", "John Example held after raid on harbour"]
        arts = [art("%d.com" % i, t, persons=who) for i, t in enumerate(titles)]
        B.NAME_MIN = 10
        _, p = run([(100, arts, [])])
        l = p["lines"][0]
        self.assertNotIn("example", l["key"] + " " + l["text"])
        self.assertNotIn("john", l["key"] + " " + l["text"])
        B.NAME_MIN = 3
        _, p = run([(100, arts, [])])
        self.assertIn("example", p["lines"][0]["key"] + " " + p["lines"][0]["text"])

    def test_common_names_do_not_glue_stories(self):
        common_loc, who = "4#Washington, District of Columbia, United States#US#USDC#1#1#1", "famous leader"
        noise = [art("n%d.com" % i, "Unrelated item number %d about gardening tips" % i, common_loc, who)
                 for i in range(400)]
        a = [art("a%d.com" % i, t, common_loc, who) for i, t in enumerate(
            ["Senate passes farm subsidy bill", "Farm subsidy bill clears Senate",
             "Senate approves farm subsidy bill", "Farm subsidy bill passes Senate vote",
             "Senate vote sends farm subsidy bill onward"])]
        b = [art("b%d.com" % i, t, common_loc, who) for i, t in enumerate(
            ["Court blocks port tariff order", "Port tariff order blocked by court",
             "Judges block port tariff order", "Court ruling halts port tariff order"])]
        foreign = [art("f.example", "Titre sans rapport", common_loc, who, translated=True)]
        st, p = run([(100, noise + a + b, foreign)])
        keys = [l["key"] + " " + l["text"] for l in p["lines"]]
        self.assertTrue(any("farm" in k for k in keys) and any("tariff" in k for k in keys), keys)
        self.assertFalse(any("farm" in k and "tariff" in k for k in keys), keys)
        self.assertTrue(all(l["other_lang"] == 0 for l in p["lines"]))

    def test_translated_attach_by_rare_names(self):
        loc, who = "4#Lima, Peru#PE#PE#1#1#1", "maria quispe;juan rare"
        en = [art("%s.com" % c, "Earthquake strikes Lima, 3 dead, rescuers search %s" % c, loc, who) for c in "abcde"]
        tr = [art("lemonde.fr", "Séisme à Lima", loc, who, translated=True),
              art("other.es", "Otra cosa", "1#Peru#PE#PE#1#1#9", "", translated=True)]
        _, p = run([(100, en, tr)])
        l = self.line(p, "lima")
        self.assertEqual((l["outlets"], l["other_lang"]), (6, 1))

    def test_fragments_of_one_event_merge(self):
        loc, who = "4#Logan Circle, District of Columbia, United States#US#USDC#1#1#1", "muriel example;chief sample"
        a = [art("a%d.com" % i, t, loc, who) for i, t in enumerate(
            ["4 people shot in Logan Circle neighborhood, police say", "Police: 4 shot in Logan Circle neighborhood",
             "Four people shot in Logan Circle neighborhood", "Logan Circle neighborhood: 4 people shot",
             "4 people shot in trendy Logan Circle neighborhood"])]
        b = [art("b%d.com" % i, t, loc, who) for i, t in enumerate(
            ["1 dead, 4 injured in gym shooting; gunman dead", "Gym shooting leaves 1 dead, 4 injured, gunman dead",
             "Gunman dead after gym shooting in Logan Circle that left 1 dead", "1 dead and 4 injured after gunman opens fire at gym",
             "Gym shooting gunman dead; 1 dead, 4 injured"])]
        c = [art("c%d.com" % i, t, "4#Lima, Peru#PE#PE#1#1#1", "maria quispe") for i, t in enumerate(
            ["Earthquake strikes Lima, 3 dead", "Lima earthquake leaves 3 dead", "3 dead as earthquake hits Lima"])]
        st, p = run([(100, a + b + c, [])])
        self.assertEqual(sorted(l["outlets"] for l in p["lines"]), [3, 10])

    def test_dates_do_not_glue_stories(self):
        arts = [art("a.com", "Forecast for Thursday, November 12th, 2026"),
                art("b.com", "Morning show line-up - Thursday 12th November 2026"),
                art("c.com", "News briefs for Thursday, November 12, 2026"),
                art("d.com", "Things to do on Thursday, Nov. 12, 2026")]
        _, p = run([(100, arts, [])])
        self.assertEqual(p["lines"], [])
        self.assertEqual([k for k, _ in B.tokenise("Thursday, November 12th, 2026")], [])

    def test_number_needs_adjacent_unit(self):
        self.assertEqual(B.number_units("Rescuers reach 8 in Brooklyn building collapse"), [])
        self.assertEqual(B.number_units("Death toll rises to 8 in Brooklyn building collapse"), [("8", "dead")])
        self.assertEqual(B.number_units("Eight killed, 17 hurt, 8 killed again in 2026"),
                         [("8", "dead"), ("17", "injured"), ("8", "dead")])
        self.assertEqual(B.number_units("5 people shot, 1 person killed, 12 people"), [("5", "shoot"), ("1", "dead")])
        self.assertEqual(B.number_units("Israeli strike on Gaza hospital kills 6, including surgeon"), [("6", "dead")])
        self.assertEqual(B.number_units("Strike kills at least six people, wounds 28"), [("6", "dead"), ("28", "injured")])
        self.assertEqual(B.number_units("Strike on hospital kills 6 people, Health Ministry says"), [("6", "dead")])

    def test_word_order_follows_majority(self):
        arts = [art("a.com", "President says country does not need trade deal, asks deputy to focus on ports"),
                art("b.com", "President: country doesn't need trade deal, deputy to focus on ports"),
                art("c.com", "Country does not need trade deal, president tells deputy"),
                art("d.com", "President says country does not need trade deal")]
        _, p = run([(100, arts, [])])
        l = p["lines"][0]
        words = (l["key"] + " " + l["text"]).split()
        self.assertLess(words.index("not"), words.index("need"))
        self.assertLess(words.index("need"), words.index("deal"))

    def test_negation_never_cut_for_length(self):
        base = "alpha bravo charlie delta echo foxtrot golf hotel"
        arts = [art("%s.com" % c, "Council will not approve %s plan %s" % (base, c)) for c in "abcde"]
        _, p = run([(100, arts, [])])
        self.assertIn("not", (p["lines"][0]["key"] + " " + p["lines"][0]["text"]).split())

    def test_reprints_count_a_tenth(self):
        wire = [art("w%d.com" % i, "Parliament passes pension reform bill after long debate") for i in range(40)]
        varied = [art("v%d.com" % i, t) for i, t in enumerate(
            ["Volcano erupts near Hilo town", "Hilo volcano erupts, town on alert", "Eruption near Hilo: volcano alert"])]
        _, p = run([(100, wire + varied, [])])
        self.assertEqual([l["score"] for l in p["lines"]], [round(4.9 * B.SPREAD_FLOOR * B.STATE_BOOST, 1), round(3.0 * B.SPREAD_FLOOR, 1)])       # "parliament" is an affair of state

    def test_acronym_case_does_not_split(self):
        self.assertEqual([k for k, _ in B.tokenise("Nato summit")][0], [k for k, _ in B.tokenise("NATO summit")][0])

    def test_shared_place_does_not_merge_two_events(self):
        loc, who = "4#Gaza, Israel (general), Israel#IS#IS00#1#1#1;4#Rafah, Israel (general), Israel#IS#IS00#1#1#2", ""
        a = [art("a%d.com" % i, t, loc, who) for i, t in enumerate(
            ["Israeli strike hits Gaza hospital", "Gaza hospital hit by Israeli strike", "Strike on Gaza hospital kills 6",
             "Israeli strike on Gaza hospital kills 6", "Hospital in Gaza struck, 6 dead"])]
        b = [art("b%d.com" % i, t, loc, who) for i, t in enumerate(
            ["Aid trucks enter Gaza crossing", "Gaza crossing opens to aid trucks", "Aid trucks cross into Gaza at Rafah",
             "Trucks carrying aid enter Gaza crossing", "Rafah crossing: aid trucks enter Gaza"])]
        noise = [art("n%d.com" % i, "zq%da zq%db zq%dc zq%dd" % (i, i, i, i), loc, who) for i in range(60)]
        _, p = run([(100, a + b + noise, [])])
        fives = [l for l in p["lines"] if l["outlets"] == 5]
        self.assertEqual(len(fives), 2, [(l["outlets"], l["key"], l["text"]) for l in p["lines"]])

    def test_counters_follow_outlets_after_expiry_and_merge(self):
        mk = lambda i, s: art("o%d.com" % i, "Dam bursts near Riverton, towns flooded %d" % i)
        st = B.new_state()
        B.cluster_slot(st, [mk(i, 100) for i in range(8)], 100)
        B.cluster_slot(st, [mk(i, 100 + B.WINDOW - 1) for i in range(3)], 100 + B.WINDOW - 1)
        B.prune(st, 100 + B.WINDOW)                    # five outlets have aged out
        s = list(st["stories"].values())[0]
        self.assertEqual((s["n"], len(s["d"]), len(s["ti"])), (3, 3, 3))
        self.assertEqual(s["t"]["dam"], 3)
        other = B.new_story(100)
        for i in (1, 2, 9):
            B.add_to_story(other, mk(i, 100), 100 + B.WINDOW - 1)
        B.merge_story(s, other)
        self.assertEqual((s["n"], len(s["d"])), (4, 4))    # two shared outlets are not double-counted

    def test_translated_article_waits_for_its_story(self):
        loc, who = "4#Lima, Peru#PE#PE#1#1#1", "maria quispe;juan rare"
        en = [art("%s.com" % c, "Earthquake strikes Lima, 3 dead, rescuers search %s" % c, loc, who) for c in "abcde"]
        tr = [art("lemonde.fr", "Séisme à Lima", loc, who, translated=True)]
        st = B.new_state()
        B.cluster_slot(st, en[:1], 100)
        B.attach_translated(st, tr, 100)               # story has one outlet: too early
        self.assertEqual(len(st["pending"]), 1)
        B.cluster_slot(st, en[1:], 101)
        B.attach_translated(st, [], 101)               # retried once the story has grown
        s = max(st["stories"].values(), key=lambda x: x["n"])
        self.assertEqual((list(s["f"]), st["pending"]), (["lemonde.fr"], []))

    def test_one_line_per_event(self):
        loc, who = "3#New York, New York, United States#US#USNY#1#1#1", "jensen example;colette sample"
        main = [art("a%d.com" % i, t, loc, who) for i, t in enumerate(
            ["Chipco CEO Jensen Example resigns amid affair", "Chipco CEO Jensen Example resigns over affair",
             "Jensen Example resigns as Chipco CEO amid affair", "Chipco boss Jensen Example resigns after affair",
             "Affair forces Chipco CEO Jensen Example to resign", "Chipco: Jensen Example resigns as CEO"])]
        react = [art("r%d.com" % i, t, loc, who + ";paul premier") for i, t in enumerate(
            ["Investor backs Tim Baker to lead Chipco", "Tim Baker should lead Chipco, investor says",
             "Investor: Tim Baker is right choice to lead Chipco", "Investor wants Tim Baker to lead Chipco"])]
        other = [art("o%d.com" % i, t, "4#Lima, Peru#PE#PE#1#1#1", "maria quispe") for i, t in enumerate(
            ["Earthquake strikes Lima, 3 dead", "Lima earthquake leaves 3 dead", "3 dead as earthquake hits Lima"])]
        _, p = run([(100, main + react + other, [])])
        self.assertEqual([(l["outlets"], l["related"]) for l in p["lines"]], [(6, 1), (3, 0)])

    def test_local_stories_weigh_less(self):
        cmap = {"w%d.com" % i: "C%d" % i for i in range(12)}
        cmap.update({"l%d.com" % i: "US" for i in range(12)})
        world = [art("w%d.com" % i, "Summit ends with climate accord, version %d" % i) for i in range(6)]
        local = [art("l%d.com" % i, "Stadium vote passes in county council, version %d" % i) for i in range(9)]
        _, p = run([(100, world + local, [])], cmap=cmap)
        self.assertEqual([l["outlets"] for l in p["lines"]], [6, 9])      # six countries beat nine local outlets
        mixed = {"m%d.com" % i: ("US" if i < 14 else "C%d" % i) for i in range(16)}       # 88% in one country
        cmap.update(mixed)
        heavy = [art("m%d.com" % i, "Stadium vote passes in county council, version %d" % i) for i in range(16)]
        _, p = run([(100, world + heavy, [])], cmap=cmap)
        self.assertEqual([l["outlets"] for l in p["lines"]], [6, 16])     # a few foreign outlets do not make it global

    def test_domestic_story_weighs_less(self):
        cmap = {"u%d.com" % i: "US" for i in range(12)}
        cmap.update({"w%d.com" % i: "C%d" % i for i in range(6)})
        home = [art("u%d.com" % i, "Gym shooting in Springfield leaves 3 dead, report %d" % i,
                    "3#Springfield, Illinois, United States#US#USIL#1#1#1") for i in range(12)]
        abroad = [art("w%d.com" % i, "Earthquake strikes Lima, 3 dead, report %d" % i, "4#Lima, Peru#PE#PE#1#1#2") for i in range(6)]
        _, p = run([(100, home + abroad, [])], cmap=cmap)
        self.assertEqual([l["outlets"] for l in p["lines"]], [6])          # the domestic story is held back

    def test_international_floor_and_country_cap(self):
        cmap = {"u%d.com" % i: "US" for i in range(40)}
        cmap.update({"w%d.com" % i: "C%d" % i for i in range(8)})
        us = "3#Springfield, Illinois, United States#US#USIL#1#1#1"
        local = [art("u%d.com" % i, "Gym shooting in Springfield leaves 3 dead, report %d" % i, us) for i in range(12)]
        world = [art("w%d.com" % i, "Earthquake strikes Lima, 3 dead, report %d" % i, "4#Lima, Peru#PE#PE#1#1#2") for i in range(6)]
        saved = B.MIN_SPREAD
        B.MIN_SPREAD = 2.5
        try:
            _, p = run([(100, local + world, [])], cmap=cmap)
            self.assertEqual([l["outlets"] for l in p["lines"]], [6])          # the local story is not listed
        finally:
            B.MIN_SPREAD = saved
        topics = ["Senate passes farm subsidy bill", "Court blocks port tariff order", "Governor signs water rights law"]
        three = [art("w%d.com" % (i % 8), "%s, note %d" % (topics[j], i), us) for j in range(3) for i in range(8 * j, 8 * j + 5)]
        cm = dict(cmap)
        _, p = run([(100, three, [])], cmap=cm)
        self.assertEqual(len(p["lines"]), B.PER_COUNTRY)

    def test_fragment_of_a_held_story_is_not_listed(self):
        cmap = {"u%d.com" % i: "US" for i in range(40)}
        cmap.update({"k%d.co.uk" % i: "UK" for i in range(6)})
        cmap.update({"w%d.com" % i: "C%d" % i for i in range(8)})
        us, who = "3#Washington, District of Columbia, United States#US#USDC#1#1#1;4#Logan Circle, District of Columbia, United States#US#USDC#1#1#2", "muriel example;chief sample"
        main = [art("u%d.com" % i, "Gym shooting in Logan Circle leaves 1 dead, report %d" % i, us, who) for i in range(14)]
        frag = [art(d, "Five people shot within walking distance of White House, edition %d" % i, us, who)
                for i, d in enumerate(["k0.co.uk", "k1.co.uk", "k2.co.uk", "w0.com", "w1.com", "w2.com"])]
        world = [art("w%d.com" % i, "Earthquake strikes Lima, 3 dead, report %d" % i, "4#Lima, Peru#PE#PE#1#1#2") for i in range(3, 8)]
        saved = B.MIN_SPREAD
        B.MIN_SPREAD = 2.5
        try:
            _, p = run([(100, main + frag + world, [])], cmap=cmap)
        finally:
            B.MIN_SPREAD = saved
        self.assertEqual([l["outlets"] for l in p["lines"]], [5])

    def test_agency_reprints_do_not_make_a_story_domestic(self):
        cmap = {"u%d.com" % i: "US" for i in range(30)}
        cmap.update({"j%d.id" % i: "ID" for i in range(3)})
        cmap.update({"x%d.com" % i: "X%d" % i for i in range(3)})
        where = "4#Jakarta, Jakarta Raya, Indonesia#ID#ID04#1#1#1"
        wire = [art("u%d.com" % i, "Indonesia's vice president resigns as credentials are questioned", where) for i in range(30)]
        own = [art("j0.id", "Vice president resigns in Jakarta", where), art("j1.id", "Indonesian vice president quits office", where),
               art("x0.com", "Vice president of Indonesia resigns", where), art("x1.com", "Indonesia vice president steps down", where)]
        saved = B.MIN_SPREAD
        B.MIN_SPREAD = 2.5
        try:
            _, p = run([(100, wire + own, [])], cmap=cmap)
        finally:
            B.MIN_SPREAD = saved
        self.assertEqual(len(p["lines"]), 1)                            # 30 US reprints are one vote; the story is listed
        self.assertGreaterEqual(p["lines"][0]["outlets"], 33)

    def test_domestic_and_unechoed_remarks_are_not_listed(self):
        cmap = {"u%d.com" % i: "US" for i in range(20)}
        cmap.update({"w%d.com" % i: "C%d" % i for i in range(8)})
        us = "3#Springfield, Illinois, United States#US#USIL#1#1#1"
        home = [art("u%d.com" % i, "Gym shooting in Springfield leaves 3 dead, report %d" % i, us) for i in range(12)]
        remark = [art("w%d.com" % i, "Leader says country does not need trade deal, take %d" % i) for i in range(4)]
        world = [art("w%d.com" % i, "Earthquake strikes Lima, 3 dead, report %d" % i, "4#Lima, Peru#PE#PE#1#1#2") for i in range(4, 8)]
        _, p = run([(100, home + remark + world, [])], cmap=cmap)
        self.assertEqual([l["outlets"] for l in p["lines"]], [4])
        self.assertIn("earthquake", p["lines"][0]["text"] + p["lines"][0]["key"])

    def test_fragment_is_held_when_one_shared_name_is_common(self):
        cmap = {"u%d.com" % i: "US" for i in range(60)}
        cmap.update({"w%d.com" % i: "C%d" % i for i in range(12)})
        us = "3#Washington, District of Columbia, United States#US#USDC#1#1#1;4#Logan Circle, District of Columbia, United States#US#USDC#1#1#2"
        elsewhere = [art("u%d.com" % i, "zq%da zq%db zq%dc zq%dd" % (i, i, i, i),
                         "3#Washington, District of Columbia, United States#US#USDC#1#1#1") for i in range(20, 60)]   # Washington is everywhere
        main = [art("u%d.com" % i, "Gym shooting in Logan Circle leaves 1 dead, report %d" % i, us) for i in range(14)]
        frag = [art("w%d.com" % i, "Five people shot within walking distance of White House, edition %d" % i, us) for i in range(6)]
        world = [art("w%d.com" % i, "Earthquake strikes Lima, 3 dead, report %d" % i, "4#Lima, Peru#PE#PE#1#1#2") for i in range(6, 11)]
        saved = B.MIN_SPREAD
        B.MIN_SPREAD = 2.5
        try:
            _, p = run([(100, elsewhere + main + frag + world, [])], cmap=cmap)
        finally:
            B.MIN_SPREAD = saved
        self.assertEqual([l["outlets"] for l in p["lines"]], [5])

    def test_big_event_fragments_fold_into_one_line(self):
        who = "jensen example"
        org = "chipco"
        def mk(prefix, titles):
            out = []
            for i, title in enumerate(titles):
                f = [""] * 27
                f[11], f[13] = who, org
                out.append({"domain": "%s%d.com" % (prefix, i), "url": "https://x/%s%d" % (prefix, i), "title": title,
                            "slug": False, "ents": B.entities(f), "toks": B.tokenise(title)})
            return out
        # the names are everywhere: 300 other reports mention them too
        spread = mk("s", ["qx%da qx%db qx%dc qx%dd" % (i, i, i, i) for i in range(100)])
        a = mk("a", ["Chipco CEO Jensen Example resigns, board names interim chief %d" % i for i in range(8)])
        b = mk("b", ["Former Chipco CEO Example linked to spy, report %d" % i for i in range(5)])
        noise = [art("n%d.com" % i, "zz%da zz%db zz%dc chipco" % (i, i, i)) for i in range(400)]
        _, p = run([(100, spread + a + b + noise, [])])
        big = [l for l in p["lines"] if l["outlets"] >= 5]
        self.assertEqual([l["outlets"] for l in big], [13])              # folded before ranking

    def test_affairs_of_state_weigh_more(self):
        a = [art("a%d.com" % i, "Bus crash on mountain road, toll version %d" % i) for i in range(6)]
        b = [art("b%d.com" % i, "Vice president resigns from office, version %d" % i) for i in range(5)]
        c = [art("c%d.com" % i, "Chipco chief resigns from company, version %d" % i) for i in range(4)]
        _, p = run([(100, a + b + c, [])])
        self.assertEqual([l["outlets"] for l in p["lines"]], [5, 6, 4])        # a company resignation gets no bonus

    def test_sport_and_entertainment_are_ignored(self):
        _, pat = B.load_rules()
        for title in ["Manchester United fires Michael Carrick as head coach", "Lakers reach NBA playoffs",
                      "Pochettino leaves USMNT for Man United", "Mauricio Pochettino set to join Manchester United",
                      "New album tops box office weekend", "Champions League draw made",
                      "Duran Duran drummer Roger Taylor steps down from band due to tinnitus"]:
            self.assertTrue(pat.search(title), title)
        for title in ["Israeli strike on Gaza hospital kills 6", "Trump threatens to double Mexico tariffs",
                      "Indonesia's vice president resigns"]:
            self.assertFalse(pat.search(title), title)

    def test_changed_rules_apply_to_stored_headlines(self):
        st = B.new_state()
        sport = [art("s%d.com" % i, "Pochettino leaves USMNT for Man United, take %d" % i) for i in range(4)]
        news = [art("n%d.com" % i, "Earthquake strikes Lima, 3 dead, take %d" % i) for i in range(4)]
        B.cluster_slot(st, sport + news + [art("s0.com", "Earthquake strikes Lima, 3 dead, take 9")], 100)
        B.apply_rules(st, B.load_rules())
        left = [(s["n"], sorted(s["d"])) for s in st["stories"].values()]
        self.assertEqual(left, [(5, ["n0.com", "n1.com", "n2.com", "n3.com", "s0.com"])])

    def test_sport_by_topic_tag(self):
        def mk(i, title, theme):
            f = [""] * 27
            f[7] = theme
            return {"domain": "s%d.com" % i, "url": "https://x/%d" % i, "title": title, "slug": False,
                    "ents": B.entities(f), "toks": B.tokenise(title)}
        feud = [mk(i, "Warner fires back at Cummins after nonsense claims %d" % i, "TAX_FNCACT_PLAYER;GENERAL") for i in range(5)]
        news = [mk(10 + i, "Earthquake strikes Lima, 3 dead, report %d" % i, "NATURAL_DISASTER") for i in range(5)]
        _, p = run([(100, feud + news, [])])
        self.assertEqual([l["key"] for l in p["lines"]], ["earthquake"])

    def test_commentary_headlines_are_ignored(self):
        _, pat = B.load_rules()
        for title in ["Black voters view Senate win through lens of state's racial legacy", "What to know about the tariffs",
                      "Why the CEO resigned", "Analysis: a bad week for chips", "5 takeaways from the debate"]:
            self.assertTrue(pat.search(title), title)
        for title in ["Mississippi elects Scott Colom to US Senate", "Earthquake strikes Lima, 3 dead"]:
            self.assertFalse(pat.search(title), title)

    def test_two_sections_do_not_overlap(self):
        old = [art("o%d.com" % i, "Parliament passes pension reform after debate %d" % i) for i in range(6)]
        new = [art("n%d.com" % i, "Volcano erupts near Hilo town, alert %d" % i) for i in range(4)]
        late = [art("p%d.com" % i, "Parliament passes pension reform after debate %d" % i) for i in range(6, 9)]
        _, p = run([(100, old, []), (100 + B.NEW_AGE + 4, new + late, [])])
        self.assertEqual([(l["section"], l["outlets"]) for l in p["lines"]], [("new", 4), ("day", 9)])
        saved = B.NEW_LINES
        B.NEW_LINES = 0
        try:
            _, p = run([(100, old, []), (100 + B.NEW_AGE + 4, new + late, [])])
            self.assertEqual([l["section"] for l in p["lines"]], ["day"])
        finally:
            B.NEW_LINES = saved

    def test_small_old_story_is_not_listed(self):
        cmap = {"w%d.com" % i: "C%d" % i for i in range(12)}
        big = [art("w%d.com" % i, "Summit ends with climate accord, version %d" % i) for i in range(10)]
        small = [art("w%d.com" % i, "Train station alert causes disruption, note %d" % i) for i in range(4)]
        saved = B.DAY_MIN_SCORE
        B.DAY_MIN_SCORE = 8
        try:
            _, p = run([(100, big + small, []), (100 + B.NEW_AGE + 2, [], [])], cmap=cmap)
        finally:
            B.DAY_MIN_SCORE = saved
        self.assertEqual([l["outlets"] for l in p["lines"]], [10])

    def test_small_new_story_is_not_listed(self):
        cmap = {"w%d.com" % i: "C%d" % i for i in range(12)}
        big = [art("w%d.com" % i, "Summit ends with climate accord, version %d" % i) for i in range(10)]
        small = [art("s%d.com" % i, "Radio station changes owner in Dakota, note %d" % i) for i in range(5)]
        saved = B.NEW_MIN_SCORE
        B.NEW_MIN_SCORE = 6
        try:
            _, p = run([(100, big + small, [])], cmap=cmap)
        finally:
            B.NEW_MIN_SCORE = saved
        self.assertEqual([l["outlets"] for l in p["lines"]], [10])

    def test_widely_reprinted_story_may_name_people(self):
        who = "john example"
        arts = [art("o%d.com" % i, "John Example elected mayor of Riverton", persons=who) for i in range(30)]
        saved = B.NAME_MIN
        B.NAME_MIN = 10
        try:
            _, p = run([(100, arts, [])])
        finally:
            B.NAME_MIN = saved
        self.assertIn("example", (p["lines"][0]["key"] + " " + p["lines"][0]["text"]))

    def test_renowned_sources_come_first(self):
        B.load_rules()
        self.assertLess(B.pref_rank("reuters.com"), B.pref_rank("news.bbc.co.uk"))
        self.assertEqual(B.pref_rank("dailymail.co.uk"), 999)
        self.assertLess(B.pref_rank("nytimes.com"), B.pref_rank("apnews.com"))          # newspapers of record first
        B.OUTLET_SIZE.update({"bigpaper.com": 900000, "localtv.com": 40})
        try:
            arts2 = [art(d, "Earthquake strikes Lima, 3 dead, edition %d" % i) for i, d in enumerate(["localtv.com", "tiny.com", "bigpaper.com"])]
            _, p2 = run([(100, arts2, [])])
            self.assertEqual(p2["lines"][0]["headlines"][0]["d"], "bigpaper.com")          # then the largest outlets
        finally:
            B.OUTLET_SIZE.clear()
        self.assertTrue(B.load_rules()[1].search("What have the talks in Abu Dhabi achieved for Ukraine?"))
        doms = ["tabloid.com", "localtv.com", "blogsite.com", "reuters.com", "apnews.com", "other.com"]
        arts = [art(d, "Earthquake strikes Lima, 3 dead, edition %d" % i) for i, d in enumerate(doms)]
        _, p = run([(100, arts, [])])
        self.assertEqual([h["d"] for h in p["lines"][0]["headlines"]][:2], ["reuters.com", "apnews.com"])
        wire = "Israeli strike on Gaza hospital kills 6, ministry says"
        titles = ["Strike on Gaza hospital leaves 6 dead"] * 9 + [wire]
        keys = {"gaza", "hospital", "strike"}
        self.assertEqual(B.common_headline(titles, keys), "Strike on Gaza hospital leaves 6 dead")
        self.assertEqual(B.common_headline(titles, keys, False, {wire: 0}), wire)

    def test_growth_counts(self):
        mk = lambda i: art("o%d.com" % i, "Dam bursts near Riverton, towns flooded %d" % i)
        _, p = run([(100, [mk(i) for i in range(3)], []), (104, [mk(i) for i in range(3, 8)], [])])
        l = p["lines"][0]
        self.assertEqual((l["outlets"], l["new_hour"], l["prev_hour"]), (8, 5, 3))
        self.assertEqual(sum(l["spark"]), 8)


class Writer(unittest.TestCase):
    TITLES = ["Earthquake strikes Lima, 3 dead", "Lima earthquake leaves 3 dead",
              "3 dead as earthquake hits Lima", "Strong earthquake shakes Lima, three killed"]

    def test_checker(self):
        ok = lambda s, neg=False: B.check_sentence(s, self.TITLES, neg)
        self.assertEqual(ok("Earthquake in Lima leaves 3 dead"), "")
        self.assertEqual(ok("Earthquake in Lima kills three"), "")                 # synonyms and number words
        self.assertTrue(ok("Earthquake in Lima leaves 30 dead").startswith(("number", "not in headlines")))
        self.assertTrue(ok("Earthquake in Lima leaves 3 dead, president blamed").startswith("not in headlines"))
        self.assertEqual(ok("Shocking earthquake strikes Lima, 3 dead"), "flash word")
        self.assertEqual(ok("Lima earthquake scandal leaves 3 dead"), "flash word")      # a verdict, not a fact
        self.assertTrue(ok("Earthquake does not strike Lima, 3 dead"))             # rejected
        self.assertEqual(ok("Earthquake in Lima leaves 3 dead", True), "dropped a negation")
        self.assertEqual(ok("Lima"), "length")
        self.assertEqual(ok(" ".join(["Lima"] * 20)), "length")
        self.assertEqual(ok("Earthquake in Lima. Lima earthquake leaves 3 dead"), "more than one sentence")
        self.assertEqual(ok("Here is the one that you told us about"), "too little content")
        self.assertTrue(ok("Earthquake in Lima leaves 2025 dead").startswith("number not in headlines"))

    def test_checker_numbers_stay_with_their_word(self):
        t = ["Shooting in Logan Circle leaves 8 dead, 17 injured", "Logan Circle shooting: 8 dead and 17 injured",
             "8 dead, 17 injured in Logan Circle shooting", "Gunfire in Logan Circle kills 8, 17 hurt",
             "Police say 1 dead in Logan Circle shooting"]
        c = lambda s: B.check_sentence(s, t, False)
        self.assertEqual(c("Logan Circle shooting leaves 8 dead and 17 injured"), "")
        self.assertTrue(c("Logan Circle shooting leaves 17 dead and 8 injured").startswith("number moved"))
        self.assertTrue(c("Logan Circle shooting leaves 1 dead").startswith(("number", "not in headlines")))
        self.assertTrue(c("One dead in Logan Circle shooting"))                     # "one" is checked as 1

    def test_checker_roles_and_small_words(self):
        t = ["Russia accuses Ukraine of attacking Belgorod", "Russia accuses Ukraine of attacking Belgorod region",
             "Moscow: Russia accuses Ukraine of Belgorod strike"]
        self.assertEqual(B.check_sentence("Russia accuses Ukraine of attacking Belgorod", t, False), "")
        self.assertTrue(B.check_sentence("Ukraine accuses Russia of attacking Belgorod", t, False).startswith("order"))
        t = ["Court rules against Trump on tariffs", "Trump tariffs: court rules against president",
             "Court rules against Trump tariffs plan"]
        self.assertEqual(B.check_sentence("Court rules against Trump on tariffs", t, False), "")
        self.assertTrue(B.check_sentence("Court rules for Trump on tariffs", t, False).startswith("small word"))
        t = ["Gunman kills 8 in Logan Circle", "Logan Circle gunman kills 8 people", "8 killed by gunman in Logan Circle"]
        self.assertEqual(B.check_sentence("Gunman dies in Logan Circle", t, False), "kill/die changed")

    def test_checker_real_outputs(self):
        t = ["US envoys meet with Putin in Kremlin after Ukraine talks in Abu Dhabi",
             "U.S. envoys meet Putin at Kremlin following Ukraine talks", "US envoys meet Putin in Moscow for Ukraine talks",
             "Envoys from US meet with Putin in Moscow on Ukraine"]
        self.assertEqual(B.check_sentence("U.S. envoys meet with Putin in Moscow on Ukraine talks", t, False), "")
        t = ["1 dead, 4 hurt in mass shooting at gym in DC's Logan Circle", "Five people shot at gym in Logan Circle",
             "Logan Circle gym shooting leaves 1 dead, 4 injured", "DC shooting: 1 dead and 4 injured at Logan Circle gym"]
        self.assertEqual(B.check_sentence("Shooting at Logan Circle gym leaves 1 dead, 4 injured", t, False), "")

    def test_big_event_fragments_merge_without_rare_names(self):
        loc, who = "3#New York, New York, United States#US#USNY#1#1#1", "jensen example;colette sample;alice other"
        a = [art("a%d.com" % i, t, loc, who) for i, t in enumerate(
            ["Chipco CEO Jensen Example resigns amid affair", "Chipco CEO Jensen Example resigns over affair",
             "Jensen Example resigns as Chipco CEO amid affair", "Chipco boss Jensen Example resigns after affair",
             "Affair forces Chipco CEO Jensen Example to resign"])]
        b = [art("b%d.com" % i, t, loc, who) for i, t in enumerate(
            ["Chipco CEO Jensen Example steps down amid scandal", "Jensen Example steps down as Chipco CEO",
             "Chipco CEO Jensen Example steps down in scandal", "Scandal: Chipco CEO Jensen Example steps down"])]
        # the names also fill hundreds of other reports, so none of them is rare
        spread = [art("s%d.com" % i, "qx%da qx%db qx%dc qx%dd" % (i, i, i, i), loc, who) for i in range(300)]
        _, p = run([(100, a + b + spread, [])])
        self.assertEqual(max(l["outlets"] for l in p["lines"]), 9)

    def test_checker_numbers_must_match_the_counted_line(self):
        t = ["Iran says two oil tankers caught fire in Strait of Hormuz", "Two oil tankers on fire in Strait of Hormuz, Iran says",
             "4 tankers hit by explosions in Strait of Hormuz", "Explosions hit 4 tankers in Strait of Hormuz",
             "Strait of Hormuz: 4 tankers damaged, oil fire reported"]
        c = lambda s, counted: B.check_sentence(s, t, False, (), False, counted)
        self.assertEqual(c("Explosions hit 4 tankers in Strait of Hormuz", "oil fire strait hormuz, 4 tankers"), "")
        self.assertEqual(c("Two oil tankers on fire in Strait of Hormuz", "oil fire strait hormuz, 4 tankers"),
                         "number not in the counted line: 2")
        self.assertEqual(c("Explosions hit 4 tankers in Strait of Hormuz", "oil fire strait hormuz"),
                         "number not in the counted line: 4")
        self.assertEqual(c("Explosions hit 5 tankers in Strait of Hormuz", "oil fire, 4–6 tankers")[:6], "not in")  # in range, but no headline says 5
        self.assertEqual(B.counted_numbers("x, 4–6 tankers, 12% y"), ({"4", "6", "12%"}, [(4.0, 6.0)]))

    def test_numbers_inside_names_are_not_quantities(self):
        self.assertEqual([k for k, _ in B.tokenise("FDA warns on GLP-1 drugs as COVID-19 fades, G7 and 5G next")],
                         ["fda", "warn", "glp", "drug", "covid", "fade", "g7", "next"])
        t = ["FDA orders new warning on GLP-1 drugs over blindness risk", "FDA flags vision loss risk on GLP-1 drugs",
             "GLP-1 drugs to carry FDA warning on vision loss risk"]
        self.assertEqual(B.check_sentence("FDA warning on GLP-1 drugs vision loss risk", t, False, (), False, "FDA drugs risk warning"), "")

    def test_claim_gets_room_for_its_source(self):
        t = ["Israeli strike on Gaza hospital kills 6 people, Health Ministry says",
             "Health Ministry says Israeli strike on Gaza hospital kills 6", "Israeli strike kills 6 people at Gaza hospital, Health Ministry says"]
        s11 = "Health Ministry says Israeli strike on Gaza hospital kills 6 people"
        self.assertEqual(B.check_sentence(s11, t, False, (), True, "israeli strike gaza hospital, 6 dead"), "")
        long = "Health Ministry says Israeli strike on Gaza hospital kills 6 people at Gaza hospital today"
        self.assertEqual(B.check_sentence(long, t, False, (), True, "israeli strike gaza hospital, 6 dead"), "")
        self.assertEqual(B.check_sentence(long, t, False, (), False, "israeli strike gaza hospital, 6 dead"), "length")

    def test_qualified_words_keep_their_qualifier(self):
        t = ["Chipco CEO resigns amid alleged affair with suspected spy", "Chipco CEO resigns over alleged affair",
             "CEO of Chipco resigns amid alleged affair, suspected spy named", "Chipco CEO resigns",
             "Chipco CEO resigns after reports of affair", "Chipco CEO resigns after reports of affair with spy"]
        c = lambda s: B.check_sentence(s, t, False)
        self.assertEqual(c("Chipco CEO resigns amid affair"), "dropped a qualifier: affair")
        self.assertEqual(c("Chipco CEO resigns amid alleged affair"), "")
        self.assertEqual(c("Chipco CEO resigns"), "")
        self.assertEqual(c("Chipco CEO resigns amid reports of affair"), "")

    def test_display_style(self):
        self.assertEqual(B.digits("U.S. envoys meet Putin as U.S. watches"), "US envoys meet Putin as US watches")

    def test_named_person_and_wrongdoing_needs_attribution(self):
        t = ["Chipco CEO John Example linked to spy", "John Example quits Chipco amid spy probe",
             "Spy probe: John Example quits Chipco", "John Example and the spy: Chipco CEO quits",
             "Chipco says CEO John Example quits after spy probe"]
        c = lambda s: B.check_sentence(s, t, False, (), False, None, persons={"john", "example"})
        self.assertEqual(c("John Example quits Chipco spy"), "unattributed allegation about a person")
        self.assertEqual(c("John Example quits Chipco amid spy probe"), "")
        self.assertEqual(B.check_sentence("John Example quits Chipco spy", t, False), "")   # no names given

    def test_status_word_must_be_common(self):
        t = ["Former Chipco CEO Example speaks", "Chipco CEO Example speaks at summit", "Chipco CEO Example speaks out",
             "Chipco CEO Example speaks to press", "Chipco CEO Example speaks again"]
        self.assertEqual(B.check_sentence("Former Chipco CEO Example speaks", t + ["Former Chipco CEO Example speaks in Lima", "Chipco CEO Example speaks in Oslo"], False),
                         "status word not common: former")

    def test_region_cap_and_aliases(self):
        self.assertEqual(B.alias("kiev"), "kyiv")
        f = [""] * 27
        f[9] = "4#Kiev, Kyyiv, Misto, Ukraine#UP#UP12#1#1#1"
        self.assertIn("L:kyiv", B.entities(f))

    def test_checker_one_fact_only(self):
        t = ["Death toll rises to 8 in Brooklyn building collapse as FDNY searches for survivors",
             "Brooklyn building collapse death toll rises to 8 as FDNY searches for survivors", "8 dead in Brooklyn building collapse",
             "Brooklyn building collapse leaves 8 dead and 17 injured", "Building collapse in Brooklyn: 8 dead, 17 injured"]
        keys = {"brooklyn", "building", "collapse", "toll", "rise", "dead", "injured"}
        c = lambda s: B.check_sentence(s, t, False, keys, False, "toll rises building collapse, 8 dead, 17 injured")
        self.assertEqual(c("Death toll rises to 8 in Brooklyn building collapse"), "")
        self.assertEqual(c("Brooklyn building collapse leaves 8 dead and 17 injured"), "")
        self.assertEqual(c("Toll rises to 8 in Brooklyn as FDNY searches survivors"), "extra clause")
        self.assertTrue(c("Death toll rises to 8 in Brooklyn building collapse as FDNY searches for survivors"))

    def test_checker_claim_names_its_source_up_front(self):
        t = ["Iran says two tankers caught fire in Strait of Hormuz", "Two tankers caught fire in Strait of Hormuz, Iran says",
             "Iran says tankers hit mines in Strait of Hormuz"]
        c = lambda s: B.check_sentence(s, t, False, (), True)
        self.assertEqual(c("Iran says tankers caught fire in Strait of Hormuz"), "")
        self.assertEqual(c("Tankers caught fire in Strait of Hormuz, Iran says"), "")
        self.assertEqual(c("Tankers caught fire in Strait of Hormuz"), "dropped the attribution")
        q = ["Former Chipco CEO linked to suspected spy", "Chipco CEO linked to suspected spy, sources say",
             "Former Chipco CEO's affair with suspected spy"]
        self.assertEqual(B.check_sentence("Former Chipco CEO linked to suspected spy", q, False, (), True), "")
        self.assertEqual(c("Tankers says Iran caught fire in Strait of Hormuz")[:11], "attribution")   # source not as in headlines
        self.assertEqual(B.common_headline(["Tankers on fire in Strait of Hormuz"] * 5 + [t[0]] * 2, {"tanker", "hormuz", "strait"}, True),
                         "Iran says two tankers caught fire in Strait of Hormuz")

    def test_fallback_headline_must_say_what_most_headlines_say(self):
        main = "Chipco CEO Jensen Example resigns amid alleged affair"
        other = "Chipco CEO Jensen Example steps down amid alleged spy scandal"
        titles = [other] * 9 + [main] * 4 + ["Chipco CEO resigns over alleged affair", "Jensen Example resigns from Chipco"]
        keys = {"chipco", "ceo", "jensen", "example", "resign", "affair"}
        # The core fact is shown; the allegation about the named person is left to the opened line.
        self.assertEqual(B.common_headline(titles, keys, False, {other: 0}), "Chipco CEO Jensen Example steps down")

    def test_fallback_can_use_the_opening_of_a_headline(self):
        titles = ["Pope returns home to Peru as 3 million expected at Lima Mass"] * 3 + [
            "Pope Leo returns to Peru", "Pope Leo XIV returns home to Peru", "Leo returns home to Peru as pope",
            "Pope back home in Peru", "Peru greets returning pope", "Pope Leo lands in Peru"]
        self.assertEqual(B.common_headline(titles, {"pope", "peru", "return"}, False, None, "pope leo, 3 million"),
                         "Pope returns home to Peru")          # the add-on is trimmed when the rest carries the story

    def test_page_states_how_much_history_it_has(self):
        st = B.new_state()
        for slot in range(100, 117):
            st["arts"][str(slot)] = 10
        st["last"] = 116
        self.assertEqual(B.render(st, 116, {}, 0)["history_hours"], 4)

    def test_fallback_headline_drops_one_outlets_colour(self):
        base = ["Chipco CEO quits after affair %s" % w for w in ("report", "probe", "claims", "inquiry", "review", "audit")]
        coloured = "Chipco CEO quits amid spy scandal"
        titles = base * 2 + [coloured] * 2 + ["Chipco CEO quits", "Chipco CEO quits as board meets"] * 2
        keys = {"chipco", "ceo", "quit"}
        self.assertNotEqual(B.common_headline(titles, keys, False, {coloured: 0}), coloured)

    def test_majority_headline_is_used_as_printed(self):
        wire = "EU leaders to meet in Dublin amid prospect of Europe joining Ukraine peace talks"
        titles = [wire] * 40 + ["EU leaders gather in Dublin on Ukraine talks %d" % i for i in range(30)]
        keys = {"eu", "leader", "dublin", "ukraine", "peace", "talk", "europe"}
        self.assertTrue(B.common_headline(titles, keys, False, {}, "dublin: EU leaders europe ukraine peace talks"))

    def test_fallback_headline_is_checked_and_shown_in_digits(self):
        titles = ["Pope Leo visits his second home, Peru"] * 3 + ["Pope Leo returns to Peru"] * 2 + [
            "Pope Leo returns to Peru for visit", "Leo returns to Peru as pope", "Pope Leo visits Peru again",
            "Peru welcomes Pope Leo on return visit", "Pope Leo back in Peru"]
        keys = {"pope", "leo", "peru", "return"}
        self.assertEqual(B.common_headline(titles, keys, False, None, "pope leo return"), "Pope Leo returns to Peru")
        self.assertEqual(B.digits("NYC collapse killed two children and six adults, no one hurt"),
                         "NYC collapse killed 2 children and 6 adults, no one hurt")
        self.assertEqual(B.digits("Eight dead in collapse"), "8 dead in collapse")

    def test_checker_outlier_headline_cannot_supply_words(self):
        t = self.TITLES + ["Peru president resigns after scandal"]
        self.assertTrue(B.check_sentence("Peru president dead after Lima earthquake", t, False).startswith("not in headlines"))
        t = self.TITLES + ["Visit casino-win.com for free money"]
        self.assertTrue(B.check_sentence("Visit casino-win.com for free money", t, False))

    def test_checker_claims_keep_attribution(self):
        t = ["Police say 4 people shot in Logan Circle", "4 people shot in Logan Circle, police say",
             "Police: 4 people shot in Logan Circle neighborhood"]
        self.assertEqual(B.check_sentence("Police say 4 people shot in Logan Circle", t, False, (), True), "")
        self.assertEqual(B.check_sentence("4 people shot in Logan Circle", t, False, (), True), "dropped the attribution")

    def test_checker_added_negation(self):
        mixed = self.TITLES + ["Earthquake did not damage Lima airport", "Lima airport: earthquake does not damage runway"]
        self.assertEqual(B.check_sentence("Earthquake does not damage Lima airport", mixed, False), "added a negation")

    def test_flash_words_never_printed(self):
        self.assertEqual([k for k, _ in B.tokenise("SHOCKING: Minister slams bombshell budget")], ["minister", "budget"])

    def _run(self, reply, n=12):
        # These tests are about the model's path, so no printed headline is picked first.
        saved = (B.AI, B.pick_model, B.write_sentence, B.MIN_OUTLETS, B.NAME_MIN)
        saved_ch, B.common_headline = B.common_headline, (lambda *a, **k: "")
        self.addCleanup(setattr, B, "common_headline", saved_ch)
        calls = []
        B.AI, B.MIN_OUTLETS, B.NAME_MIN = "auto", 3, 3
        B.pick_model = lambda: "stub"
        B.write_sentence = lambda model, heads, extra="": (calls.append(heads), reply)[1]
        try:
            arts = [art("o%d.com" % i, self.TITLES[i % 4] + (" update %d" % i if i >= 4 else "")) for i in range(n)]
            st = B.new_state()
            B.cluster_slot(st, arts, 100)
            st["last"] = 100
            p1 = B.render(st, 100, {}, 0)
            p2 = B.render(st, 100, {}, 0)
            return p1, p2, calls
        finally:
            B.AI, B.pick_model, B.write_sentence, B.MIN_OUTLETS, B.NAME_MIN = saved

    def test_good_sentence_is_used_and_cached(self):
        p1, p2, calls = self._run("Earthquake in Lima leaves 3 dead")
        self.assertEqual(p1["lines"][0]["sentence"], "Earthquake in Lima leaves 3 dead")
        self.assertEqual(p2["lines"][0]["sentence"], "Earthquake in Lima leaves 3 dead")
        self.assertEqual(len(calls), 1)                                # second render used the cache
        self.assertEqual((p1["ai"]["model"], p1["ai"]["sentences"]), ("stub", 1))

    def test_bad_sentence_falls_back_to_counted_line(self):
        p1, p2, calls = self._run("Earthquake in Lima leaves 300 dead, city destroyed")
        self.assertEqual(p1["lines"][0]["sentence"], "")
        self.assertEqual(len(calls), 4)                                # three retries, then give up until the story changes
        self.assertTrue(p1["lines"][0]["text"])

    def test_retry_names_the_refused_words(self):
        saved = (B.AI, B.pick_model, B.write_sentence, B.MIN_OUTLETS, B.NAME_MIN)
        saved_ch, B.common_headline = B.common_headline, (lambda *a, **k: "")
        self.addCleanup(setattr, B, "common_headline", saved_ch)
        extras = []
        def fake(model, heads, extra=""):
            extras.append(extra)
            return "Crowds greeted earthquake in Lima leaves 3 dead" if len(extras) == 1 else "Earthquake in Lima leaves 3 dead"
        B.AI, B.MIN_OUTLETS, B.NAME_MIN, B.pick_model, B.write_sentence = "auto", 3, 3, (lambda: "stub"), fake
        try:
            arts = [art("o%d.com" % i, self.TITLES[i % 4] + (" update %d" % i if i >= 4 else "")) for i in range(12)]
            st = B.new_state()
            B.cluster_slot(st, arts, 100)
            st["last"] = 100
            p = B.render(st, 100, {}, 0)
        finally:
            B.AI, B.pick_model, B.write_sentence, B.MIN_OUTLETS, B.NAME_MIN = saved
        self.assertEqual(p["lines"][0]["sentence"], "Earthquake in Lima leaves 3 dead")
        self.assertIn("Do not use: crowd, greeted.", extras[1])

    def test_fallback_is_the_most_printed_plain_headline(self):
        wire = "Israeli strike on Gaza hospital kills 6 people, Health Ministry says"
        titles = [wire] * 5 + ["SHOCKING strike on Gaza hospital kills 6"] * 9 + ["Gaza Hospital Strike Kills Six People Today"] * 7 + [
            "Israel hits Gaza hospital, killing six: live updates"] * 6 + ["Strike on Gaza hospital kills 6"]
        keys = {"gaza", "hospital", "strike", "israeli"}
        self.assertEqual(B.common_headline(titles, keys), wire)
        self.assertEqual(B.common_headline(["Strike on Gaza hospital kills 6", "Gaza hospital hit, 6 dead"], keys), "")

    def test_condition_is_cut_like_any_add_on(self):
        p1, _, _ = self._run("Earthquake in Lima leaves 3 dead if early reports hold")
        self.assertEqual(p1["lines"][0]["sentence"], "Earthquake in Lima leaves 3 dead")

    def test_accepted_sentence_is_kept_while_it_still_passes(self):
        saved = (B.AI, B.pick_model, B.write_sentence, B.MIN_OUTLETS, B.NAME_MIN)
        saved_ch, B.common_headline = B.common_headline, (lambda *a, **k: "")
        self.addCleanup(setattr, B, "common_headline", saved_ch)
        replies = ["Earthquake in Lima leaves 3 dead", "Earthquake in Lima leaves 3 dead, president blamed for delays"]
        calls = []
        B.AI, B.MIN_OUTLETS, B.NAME_MIN, B.pick_model = "auto", 3, 3, (lambda: "stub")
        B.write_sentence = lambda model, heads, extra="": (calls.append(1), replies[min(len(calls) - 1, 1)])[1]
        try:
            st = B.new_state()
            B.cluster_slot(st, [art("o%d.com" % i, self.TITLES[i % 4] + (" update %d" % i if i >= 4 else "")) for i in range(12)], 100)
            st["last"] = 100
            first = B.render(st, 100, {}, 0)["lines"][0]["sentence"]
            B.cluster_slot(st, [art("p%d.com" % i, "Lima earthquake: 3 dead, rescue teams arrive %d" % i) for i in range(3)], 101)
            second = B.render(st, 101, {}, 0)["lines"][0]["sentence"]       # headlines changed, sentence still valid
        finally:
            B.AI, B.pick_model, B.write_sentence, B.MIN_OUTLETS, B.NAME_MIN = saved
        self.assertEqual((first, second, len(calls)), ("Earthquake in Lima leaves 3 dead",) * 2 + (1,))

    def test_model_is_given_the_supported_vocabulary(self):
        words = B.supported_words(self.TITLES + ["Pope's arrival hits all the right notes"])
        self.assertEqual(sorted(words), ["dead", "earthquake", "hits", "lima"])     # "hits" is in two headlines
        self.assertNotIn("notes", words)

    def test_small_story_without_a_person_gets_a_sentence(self):
        saved = (B.AI, B.pick_model, B.write_sentence, B.MIN_OUTLETS, B.NAME_MIN)
        B.AI, B.MIN_OUTLETS, B.NAME_MIN, B.pick_model = "auto", 3, 10, (lambda: "stub")
        B.write_sentence = lambda model, heads, extra="": "Earthquake in Lima leaves 3 dead"
        try:
            out = []
            for who in ("", "john example"):
                st = B.new_state()
                B.cluster_slot(st, [art("o%d.com" % i, self.TITLES[i], persons=who) for i in range(4)], 100)
                st["last"] = 100
                out.append(B.render(st, 100, {}, 0)["lines"][0]["sentence"])
        finally:
            B.AI, B.pick_model, B.write_sentence, B.MIN_OUTLETS, B.NAME_MIN = saved
        self.assertEqual(out, ["Earthquake in Lima leaves 3 dead", ""])

    def test_add_on_is_cut_when_the_core_passes(self):
        p1, _, calls = self._run("Earthquake in Lima leaves 3 dead, crowds greeted rescuers")
        self.assertEqual(p1["lines"][0]["sentence"], "Earthquake in Lima leaves 3 dead")
        self.assertEqual(len(calls), 1)

    def test_word_forms_support_each_other(self):
        t = ["FDA orders new warning on GLP-1 drugs", "GLP-1 drugs to carry FDA warning", "FDA warned of risk from GLP-1 drugs"]
        self.assertEqual(B.check_sentence("FDA warns of GLP-1 drugs risk", t + ["Risk warning for GLP-1 drugs from FDA"], False), "")
        self.assertEqual((B.stem("warning"), B.stem("warned"), B.stem("press"), B.stem("gas")), ("warn", "warn", "press", "gas"))

    def test_no_reports_prefix_when_the_line_hedges_itself(self):
        saved = (B.AI, B.pick_model, B.write_sentence, B.MIN_OUTLETS, B.NAME_MIN)
        B.AI, B.MIN_OUTLETS, B.NAME_MIN, B.pick_model = "auto", 3, 3, (lambda: "stub")
        B.write_sentence = lambda model, heads, extra="": "Chipco CEO resigns amid alleged affair"
        try:
            titles = ["Chipco CEO resigns over alleged affair", "Chipco CEO resigns amid alleged affair, sources say",
                      "Alleged affair: Chipco CEO resigns", "Chipco CEO resigns after alleged affair, board says"]
            st = B.new_state()
            B.cluster_slot(st, [art("o%d.com" % i, t) for i, t in enumerate(titles)], 100)
            st["last"] = 100
            l = B.render(st, 100, {}, 0)["lines"][0]
        finally:
            B.AI, B.pick_model, B.write_sentence, B.MIN_OUTLETS, B.NAME_MIN = saved
        self.assertIn("claim", l["tags"])
        self.assertEqual(l["sentence"], "Chipco CEO resigns amid alleged affair")

    def test_writer_off_by_default_in_tests(self):
        _, p = run([(100, [art("%s.com" % c, "Dam bursts near Riverton town %s" % c) for c in "abcde"], [])])
        self.assertEqual((p["ai"]["model"], p["ai"]["sentences"]), ("", 0))


class EndToEnd(unittest.TestCase):
    """Runs main() against GDELT-format zip files on disk."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.fx = os.path.join(self.tmp, "fx")
        self.out = os.path.join(self.tmp, "out")
        os.makedirs(self.fx)
        self._saved = (B.BASE, B.OUT, B.STATE_DIR, B.COUNTRY_URL, B.MIN_OUTLETS, B.BUDGET)
        self._heal = os.environ.pop("SELF_HEAL", None)     # the local runner sets this; tests decide for themselves
        uri = lambda p: pathlib.Path(p).as_uri()          # file:///C:/... on Windows
        B.BASE, B.OUT, B.STATE_DIR = uri(self.fx), self.out, self.out
        B.COUNTRY_URL, B.MIN_OUTLETS = uri(os.path.join(self.fx, "none.csv")), 3

    def tearDown(self):
        B.BASE, B.OUT, B.STATE_DIR, B.COUNTRY_URL, B.MIN_OUTLETS, B.BUDGET = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)
        os.environ.pop("SELF_HEAL", None)
        if self._heal is not None:
            os.environ["SELF_HEAL"] = self._heal

    def put(self, ts, rows, translated=False):
        lines = []
        for i, (dom, title) in enumerate(rows):
            f = [""] * 27
            f[0], f[1], f[3], f[4] = "%s-%d" % (ts, i), ts, dom, "https://%s/%s-%d" % (dom, ts, i)
            f[9], f[11] = "4#Lima, Peru#PE#PE#1#1#1", "maria quispe;juan rare"
            f[26] = "<PAGE_TITLE>%s</PAGE_TITLE>" % title if title else ""
            lines.append("\t".join(f))
        name = ts + (".translation" if translated else "") + ".gkg.csv.zip"
        with zipfile.ZipFile(os.path.join(self.fx, name), "w") as z:
            z.writestr("x.csv", "\n".join(lines) + "\n")

    def pointer(self, ts, ts_tr=None):
        open(os.path.join(self.fx, "lastupdate.txt"), "w").write("1 x http://x/%s.gkg.csv.zip\n" % ts)
        if ts_tr:
            open(os.path.join(self.fx, "lastupdate-translation.txt"), "w").write(
                "1 x http://x/%s.translation.gkg.csv.zip\n" % ts_tr)

    def data(self):
        with open(os.path.join(self.out, "data.json")) as f:
            return json.load(f)

    def quake(self, tag):
        return [("%s%d.com" % (tag, i), "Earthquake strikes Lima, 3 dead, report %s%d" % (tag, i)) for i in range(5)]

    def test_full_cycle(self):
        self.put("20261112150000", self.quake("a") + [("spam.com", "Your daily horoscope for Friday")])
        self.pointer("20261112150000")
        B.main()
        d = self.data()
        self.assertEqual(d["lines"][0]["key"], "lima")
        self.assertEqual(d["lines"][0]["outlets"], 5)
        self.assertEqual(d["screened"]["articles"], 5)           # horoscope filtered by rules/
        for f in ("state.json.gz", "archive/2026-11-12.json", "archive/index.json", ".nojekyll", "index.html"):
            self.assertTrue(os.path.exists(os.path.join(self.out, f)), f)

        # Second run: English is one slot ahead of the translated feed.
        self.put("20261112151500", self.quake("b"))
        self.put("20261112150000", [("lemonde.fr", "Séisme à Lima")], translated=True)
        self.pointer("20261112151500", "20261112150000")
        B.main()
        d = self.data()
        self.assertEqual((d["lines"][0]["outlets"], d["lines"][0]["other_lang"]), (11, 1))

        # Third run: the lagging translated slot arrives late and is still picked up.
        self.put("20261112151500", [("elpais.com", "Terremoto en Lima")], translated=True)
        self.pointer("20261112151500", "20261112151500")
        B.main()
        self.assertEqual(self.data()["lines"][0]["other_lang"], 2)

        # Fourth run with nothing new changes no counts.
        B.main()
        self.assertEqual(self.data()["lines"][0]["outlets"], 12)

    def test_corrupt_state_stops_instead_of_wiping(self):
        self.put("20261112150000", self.quake("a"))
        self.pointer("20261112150000")
        B.main()
        open(os.path.join(self.out, "state.json.gz"), "wb").write(b"garbage")
        before = open(os.path.join(self.out, "data.json")).read()
        with self.assertRaises(SystemExit):
            B.main()
        self.assertEqual(open(os.path.join(self.out, "data.json")).read(), before)

    def test_local_runner_heals_a_damaged_state(self):
        self.put("20261112150000", self.quake("a"))
        self.pointer("20261112150000")
        B.main()
        with open(os.path.join(self.out, "state.json.gz"), "wb") as f:
            f.write(b"garbage")
        os.environ["SELF_HEAL"] = "1"
        try:
            B.main()
        finally:
            del os.environ["SELF_HEAL"]
        self.assertEqual(self.data()["lines"][0]["outlets"], 5)
        self.assertTrue(os.path.exists(os.path.join(self.out, "state.json.gz.bad")))

    def test_time_budget_defers_work(self):
        self.put("20261112150000", self.quake("a"))
        self.pointer("20261112150000")
        B.BUDGET = -1
        B.main()                                                  # processes nothing, must not crash
        self.assertEqual(self.data()["lines"], [])
        B.BUDGET = 420
        B.main()                                                  # catches up
        self.assertEqual(self.data()["lines"][0]["outlets"], 5)

    def test_missing_titles_fall_back_to_url_then_canary(self):
        rows = [("s%d.com" % i, "") for i in range(600)]
        self.put("20261112150000", rows)
        self.pointer("20261112150000")
        with self.assertRaises(SystemExit):
            B.main()
        self.assertFalse(os.path.exists(os.path.join(self.out, "data.json")))

    def test_country_lookup_file(self):
        open(os.path.join(self.fx, "c.csv"), "w").write(
            "domain,countrycode,cnt\n" + "".join("x%d.com,CI,50\nx%d.com,US,9\n" % (i, i) for i in range(120)))
        B.COUNTRY_URL = pathlib.Path(os.path.join(self.fx, "c.csv")).as_uri()
        self.put("20261112150000", [("x%d.com" % i, "Earthquake strikes Lima, 3 dead, item %d" % i) for i in range(5)])
        self.pointer("20261112150000")
        B.main()
        self.assertEqual(self.data()["lines"][0]["countries"], 1)
        self.assertTrue(os.path.exists(os.path.join(self.out, "countries.json.gz")))


class HeadlinePick(unittest.TestCase):
    def test_title_case_headline_is_put_in_sentence_case_and_cut(self):
        tc = "Nvidia CEO Jensen Huang Resigns After Reports of Affairs, Including One With Suspected Spy"
        titles = [tc] * 3 + ["Nvidia CEO Jensen Huang resigns after reports of affairs"[:0] + "Jensen Huang resigns as Nvidia CEO after reports"] * 2 + \
                 ["Nvidia's Jensen Huang resigns after reports of affairs"] * 2
        got = B.common_headline(titles, {"nvidia", "ceo", "jensen", "huang", "resign"})
        self.assertTrue(got)
        self.assertNotIn("Resigns", got)
        self.assertLessEqual(len(got), B.ONE_LINE)


class Learning(unittest.TestCase):
    def test_small_model_gets_similar_accepted_examples(self):
        B.EXAMPLES[:] = [{"h": ["Quake hits Lima, 3 dead"], "s": "Earthquake in Lima kills 3", "by": "big model"},
                         {"h": ["EU leaders meet in Dublin"], "s": "EU leaders meet in Dublin", "by": "headline"}]
        got = B.similar_examples(["Strong quake shakes Lima"], 1)
        self.assertEqual(got[0]["s"], "Earthquake in Lima kills 3")
        B.remember_example(["x"], "Earthquake in Lima kills 3", "big model")      # no duplicates
        self.assertEqual(len(B.EXAMPLES), 2)
        B.EXAMPLES[:] = []


class Wires(unittest.TestCase):
    def test_agency_copy_is_recognised_from_the_address(self):
        self.assertEqual(B.wire_of("https://www.wral.com/news/ap/6d74c-van-hollen/")[0], "AP")
        self.assertEqual(B.wire_of("https://lufkindailynews.com/news_reuters/business/x/article.html")[0], "Reuters")
        self.assertIsNone(B.wire_of("https://cointelegraph.com/news/huang-affair-reuters"))   # about a report, not the copy
        self.assertIsNone(B.wire_of("https://example.com/news/apple-shares"))
        self.assertLess(B.source_rank("wral.com", "https://www.wral.com/news/ap/x/"), B.pref_rank("dw.com"))

    def test_home_paper_of_record_comes_first_for_its_own_country(self):
        s = {"ti": {"nytimes.com": ("Irish vote counted", "https://nytimes.com/a", 0, False),
                    "irishtimes.com": ("Irish vote counted today", "https://irishtimes.com/b", 0, False)}}
        heads, _ = B.sources(s, {"irish", "vote"}, "EI", {"irishtimes.com": "EI", "nytimes.com": "US"})
        self.assertEqual(heads[0]["d"], "irishtimes.com")
        heads, _ = B.sources(s, {"irish", "vote"}, "CH", {"irishtimes.com": "EI", "nytimes.com": "US"})
        self.assertEqual(heads[0]["d"], "nytimes.com")


class Toll(unittest.TestCase):
    def test_toll_from_headlines(self):
        self.assertEqual(B.toll(["Strike on hospital kills 6", "Six dead, 12 injured in strike", "Hospital hit"]), (6, 12))
        self.assertEqual(B.toll(["Leaders meet in Dublin"]), (0, 0))
        self.assertEqual(B.toll(["Quake leaves 1,200 dead", "Quake kills 1,200"]), (1200, 0))


if __name__ == "__main__":
    unittest.main()
