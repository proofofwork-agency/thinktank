"""Synthetic NL -> logic corpus. Deterministic given SEED."""

import random

SEED = 1337

PEOPLE = ["maria", "jan", "sofia", "lucas", "emma", "noah", "olivia", "liam", "ava",
          "mila", "finn", "julia", "daan", "sara", "thomas", "anna", "ruben", "eva",
          "bram", "noor", "tess", "sem", "lotte", "max", "fleur", "tim", "iris",
          "koen", "amber", "joost", "femke", "niels", "merel", "stijn", "elin",
          "dirk", "naomi", "wout", "lara", "pim"]
CITIES = ["amsterdam", "rotterdam", "utrecht", "eindhoven", "paris", "lyon", "berlin",
          "munich", "madrid", "barcelona", "rome", "milan", "lisbon", "porto",
          "vienna", "prague", "warsaw", "athens", "dublin", "brussels", "antwerp",
          "oslo", "stockholm", "helsinki", "copenhagen", "budapest", "zagreb",
          "geneva", "zurich", "ghent"]
COUNTRIES = ["netherlands", "france", "germany", "spain", "italy", "portugal",
             "austria", "czechia", "poland", "greece", "ireland", "belgium",
             "norway", "sweden", "finland", "denmark", "hungary", "croatia",
             "switzerland", "slovenia"]
COMPANIES = ["philips", "asml", "shell", "heineken", "adyen", "booking", "tomtom",
             "exact", "coolblue", "mollie", "picnic", "nxp", "kpn", "ing", "rabobank"]

# question templates -> query with variable X
QUESTIONS = {
    "capital":    [("what is the capital of {a}", "X", 1), ("which country has capital {b}", "X", 0)],
    "lives_in":   [("where does {a} live", "X", 1), ("who lives in {b}", "X", 0)],
    "parent":     [("who is the parent of {b}", "X", 0), ("who are the children of {a}", "X", 1)],
    "works_at":   [("where does {a} work", "X", 1), ("who works at {b}", "X", 0)],
    "located_in": [("in which country is {b}", "X", 1), ("which cities are located in {a}", "X", 0)],
}

TEMPLATES = {
    "capital":    [("{b} is the capital of {a}", "CITIES", "COUNTRIES"),
                   ("the capital of {a} is {b}", "CITIES", "COUNTRIES"),
                   ("{b} serves as capital of {a}", "CITIES", "COUNTRIES")],
    "lives_in":   [("{a} lives in {b}", "PEOPLE", "CITIES"),
                   ("{a} is living in {b}", "PEOPLE", "CITIES"),
                   ("{a} resides in {b}", "PEOPLE", "CITIES")],
    "parent":     [("{a} is the parent of {b}", "PEOPLE", "PEOPLE"),
                   ("{a} is the mother of {b}", "PEOPLE", "PEOPLE"),
                   ("{a} is the father of {b}", "PEOPLE", "PEOPLE")],
    "works_at":   [("{a} works at {b}", "PEOPLE", "COMPANIES"),
                   ("{a} is employed by {b}", "PEOPLE", "COMPANIES"),
                   ("{a} has a job at {b}", "PEOPLE", "COMPANIES")],
    "located_in": [("{b} is located in {a}", "CITIES", "COUNTRIES"),
                   ("{b} is a city in {a}", "CITIES", "COUNTRIES"),
                   ("you can find {b} in {a}", "CITIES", "COUNTRIES")],
}
POOLS = {"PEOPLE": PEOPLE, "CITIES": CITIES, "COUNTRIES": COUNTRIES, "COMPANIES": COMPANIES}


def make_pairs(n):
    """Return n unique (sentence, logic) pairs, deterministic."""
    rng = random.Random(SEED)
    preds = list(TEMPLATES)
    seen, pairs = set(), []
    misses = 0
    while len(pairs) < n and misses < 20000:  # stop when the space saturates
        p = rng.choice(preds)
        tpl, pool_b, pool_a = rng.choice(TEMPLATES[p])
        a, b = rng.choice(POOLS[pool_a]), rng.choice(POOLS[pool_b])
        if pool_a == pool_b and a == b:
            continue
        if p in ("capital", "located_in"):
            logic = f"{p}({a},{b})"          # country first
        else:
            logic = f"{p}({a},{b})"
        sent = tpl.format(a=a, b=b)
        if (sent, logic) in seen:
            misses += 1
            continue
        misses = 0
        seen.add((sent, logic))
        pairs.append((sent, logic))
        pairs.append((logic, sent))  # inverse: render logic back to language
        if True:  # mirror as a question
            q, var, slot = rng.choice(QUESTIONS[p])
            args = [a, b]
            ent = args[1 - slot]
            args[slot] = var
            qsent = q.format(a=ent, b=ent)
            qlogic = f"{p}({args[0]},{args[1]})"
            if (qsent, qlogic) not in seen:
                seen.add((qsent, qlogic))
                pairs.append((qsent, qlogic))
    return pairs


def split(pairs, holdout=200):
    return pairs[holdout:], pairs[:holdout]


if __name__ == "__main__":
    tr, ho = split(make_pairs(20000))
    print(f"train={len(tr)} holdout={len(ho)}")
    for s, l in tr[:5]:
        print(f"  {s}  ->  {l}")
