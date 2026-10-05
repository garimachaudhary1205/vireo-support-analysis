"""How do we know the classifier works?

Tickets where the category is NOT 'Other' carry a tag the intake bot set and
the agent could correct at closure (policy section 2) - the closest thing to
ground truth in the pack. We run the rules classifier on every one of those
tickets and measure agreement, overall and per category, counting only the
tickets where the classifier was confident (it abstains to 'Other' otherwise).

Also writes a 50-row random sample of 'Other' reclassifications
(output/handcheck_sample.csv) for manual review; the hand-check verdict is
recorded in README.md.
"""

import csv
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from classify import classify_rules

ROOT = Path(__file__).resolve().parent.parent


def main():
    tickets = list(csv.DictReader(open(ROOT / "data" / "tickets.csv")))
    labelled = [t for t in tickets if t["category"] != "Other"]

    hits, misses, abstained = 0, 0, 0
    per_cat = defaultdict(lambda: [0, 0])  # cat -> [hits, total judged]
    confusion = Counter()
    for t in labelled:
        pred, confident = classify_rules(t["customer_message"])
        if not confident:
            abstained += 1
            continue
        per_cat[t["category"]][1] += 1
        if pred == t["category"]:
            hits += 1
            per_cat[t["category"]][0] += 1
        else:
            misses += 1
            confusion[(t["category"], pred)] += 1

    judged = hits + misses
    print(f"Labelled tickets: {len(labelled)}  judged: {judged}  abstained: {abstained} "
          f"({100*abstained/len(labelled):.0f}%)")
    print(f"Agreement with agent/bot tag: {hits}/{judged} = {100*hits/judged:.1f}%\n")
    print("Per category (agreement, n judged):")
    for cat, (h, n) in sorted(per_cat.items(), key=lambda x: x[1][0]/max(1, x[1][1])):
        print(f"  {cat:22s} {100*h/n:5.1f}%  n={n}")
    print("\nTop confusions (truth -> predicted):")
    for (truth, pred), n in confusion.most_common(8):
        print(f"  {truth} -> {pred}: {n}")

    random.seed(42)
    others = [t for t in tickets if t["category"] == "Other"]
    sample = random.sample(others, 50)
    with open(ROOT / "output" / "handcheck_sample.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ticket_id", "predicted", "confident", "customer_message"])
        for t in sample:
            pred, conf = classify_rules(t["customer_message"])
            w.writerow([t["ticket_id"], pred, "Y" if conf else "N",
                        t["customer_message"][:300].replace("\n", " ")])
    print("\nWrote output/handcheck_sample.csv (50 rows) for manual review.")


if __name__ == "__main__":
    main()
