from dataclasses import dataclass

ALLOW = "ALLOW"
REVIEW = "REVIEW"
BLOCK = "BLOCK"
ESCALATE = "ESCALATE"
ACTION_ORDER = {ALLOW: 0, REVIEW: 1, BLOCK: 2, ESCALATE: 3}


@dataclass
class RuleHit:
    code: str
    description: str
    min_action: str


def evaluate_rules(feats: dict, txn: dict) -> list[RuleHit]:
    hits: list[RuleHit] = []
    amount = float(txn.get("amount", 0))
    count_1h = feats.get("cust_txn_count_1h", 0)
    count_24h = feats.get("cust_txn_count_24h", 0)

    if count_1h >= 5 and amount <= 200:
        hits.append(
            RuleHit(
                "CARD_TESTING_BURST",
                f"{int(count_1h)} micro-transactions in the last hour - classic card testing pattern",
                BLOCK,
            )
        )
    elif count_1h >= 4:
        hits.append(
            RuleHit("VELOCITY_SPIKE", f"{int(count_1h)} transactions from this customer in the last hour", REVIEW)
        )

    if feats.get("country_mismatch") == 1.0 and amount >= 10_000:
        hits.append(
            RuleHit(
                "GEO_MISMATCH_HIGH_VALUE",
                f"High-value ({amount:.0f} INR) transaction with IP country different from billing country",
                REVIEW,
            )
        )

    if feats.get("is_night") == 1.0 and amount >= 25_000:
        hits.append(
            RuleHit("NIGHT_LARGE_AMOUNT", f"Large amount ({amount:.0f} INR) between 00:00 and 05:00 local time", REVIEW)
        )

    if feats.get("card_age_days", 9999) < 2 and amount >= 15_000:
        hits.append(
            RuleHit(
                "NEW_CARD_HIGH_VALUE",
                f"Amount {amount:.0f} INR on a card added {feats.get('card_age_days', 0):.0f} day(s) ago",
                BLOCK,
            )
        )

    if feats.get("device_txn_count_7d", 0) >= 40:
        hits.append(
            RuleHit(
                "DEVICE_FARM_SIGNAL",
                f"{int(feats['device_txn_count_7d'])} transactions from this device in 7 days across accounts",
                REVIEW,
            )
        )

    if count_24h >= 12:
        hits.append(
            RuleHit(
                "ACCOUNT_DRAIN_PATTERN",
                f"{int(count_24h)} transactions in 24h totalling {feats.get('cust_amount_sum_24h', 0):.0f} INR",
                REVIEW,
            )
        )
    return hits


def max_action(actions: list[str]) -> str:
    best = ALLOW
    for a in actions:
        if ACTION_ORDER.get(a, 0) > ACTION_ORDER[best]:
            best = a
    return best
