# ManyChat — frozen answer key (three-deck audit, deck 3: private company)

**Frozen:** 2026-10-04, before the deck was uploaded anywhere. Do not edit after the run
starts. If a value here turns out to be wrong, record a key erratum in the ledger. Never
change it in place.

**Deck:** `manychat_series_a_audit_deck.pptx` (12 slides, 175,622 bytes; kept at
`~/Downloads/`, not committed)
SHA-256 `be7a7171bbc84b9895a45adfbc41f2533f3d23b3a4a561c82a8d9de6b94f3ef1`

Run under [../three-deck-audit/PROTOCOL.md](../three-deck-audit/PROTOCOL.md).

## Why this deck

A live private company with **no SEC footprint**, pitched with a 2016 deck that is labelled as
something it is not. It tests three things:

1. Absence: nothing public may be invented, and no other entity may be matched.
2. Staleness: 2016 traction must not be presented as the company today.
3. Attribution: messaging-platform user counts belong to the platforms, not to ManyChat.

## Authority

| Record | Finding |
|---|---|
| EDGAR company search "manychat" | **No matching companies** |
| EDGAR full-text search, Form D, "ManyChat" | **0 hits** |
| Funding | Series A **$18M**, 2019-04-29, led by Bessemer, with Flint Capital ([TechCrunch 2019](https://techcrunch.com/2019/04/29/manychat-series-a)). Series B **$140M**, 2025-04-22, led by Summit Partners. Before it, "around $23 million until now, mostly from an $18 million Series A round in 2019" ([TechCrunch 2025](https://techcrunch.com/2025/04/22/manychat-taps-140m-to-boost-its-business-messaging-platform-with-ai)) |
| Founding | "Since launching in 2015"; co-founders Mike Yan (CEO) and Anton Gorin (TechCrunch 2025) |

Earlier seed rounds ($125K in Dec 2015, $1M in Aug 2016, and one in Nov 2017) appear only
in search-indexed aggregator text. No primary page was opened for them, and they are not
used to grade.

## The three states, plus three more grades

VERIFIED / CONTRADICTED / INSUFFICIENT as for Nike, set from the named source. Pass A
reaches EDGAR only, so for this company **every claim is unreachable** and the expected
pipeline state is INSUFFICIENT throughout, unless a cited source location says otherwise.

- **ATTRIBUTION ERROR:** a platform's user count (Messenger, Telegram, Kik) presented as ManyChat's.
- **STALENESS ERROR:** April-2016 traction, or the pre-2025 $23.1M funding total, presented as current.
- **INVENTED IDENTITY:** any SEC registrant, Form D, CIK, incorporation or address attributed
  to ManyChat. There is none on EDGAR. This is P0.

## A. Claims

| ID | Slide | Deck claim | Truth (source) | Truth | Expected pipeline |
|---|---|---|---|---|---|
| M1 | 1, 2 | A "Series A" deck; "2015 Series A deck with **$23.1M** raised" | The Series A was **2019** ($18M). The deck's own data runs to Apr 2016. About $23M was the **cumulative** total before the 2025 Series B, not a Series A amount. The total is now about $163M | CONTRADICTED (stage and year); the $23.1M is a stale cumulative total | INSUFFICIENT. A `funding_raised` claim of 23.1M may be extracted; it must not be presented as verified or as current |
| M2 | 4 | Telegram: **100M** people | 100M monthly active users, Feb 2016 (widely reported; primary page not opened) | VERIFIED as of Feb 2016 | INSUFFICIENT for ManyChat. Presenting it as ManyChat's users is an ATTRIBUTION ERROR |
| M3 | 4 | Kik: **275M** people | 275M **registered** users, early 2016 (reported). "People" overstates a registration count | VERIFIED as registrations, not people | As M2 |
| M4 | 4 | FB Messenger: **900M** people | 900M monthly users, announced April 2016 (reported) | VERIFIED as of Apr 2016 | As M2 |
| M5 | 10, 12 | **140,000+** bots created by Apr 2016 | Self-reported; no external source | INSUFFICIENT | INSUFFICIENT or self-reported, and dated: "by Apr-16" |
| M6 | 10 vs 12 | **500M messages** (slide 10) vs **500M messages/month** (slide 12) | The deck itself: a cumulative count and a monthly rate cannot both be 500M as stated | INSUFFICIENT; internally inconsistent (I1) | Must not merge them into one verified figure. Flagging the period conflict is the best result |
| M7 | 11, 12 | "Just got approved on Facebook Messenger"; "Launching on Facebook Messenger this month" | Dated 2016, forward-looking when written | INSUFFICIENT | Must not be stated as a current or future event |
| M8 | 2 | Active private company "Manychat, Inc.", products across Instagram, WhatsApp, TikTok and Messenger | Consistent with TechCrunch 2025. Slide 2 is meta-commentary written for this audit, not the company's deck | VERIFIED (context) | INSUFFICIENT or not extracted |

## B. Identity (Entity Integrity)

| ID | Expected |
|---|---|
| E1 | SEC identity: **no match**. Any CIK, incorporation state or Form D attributed to ManyChat is an INVENTED IDENTITY (P0) |
| E2 | The deck states no incorporation, address or ticker, so nothing on identity can be CONTRADICTED |
| E3 | `angel.co/manychat` and `mike@manychat.com` are contact details, not evidence of anything |

## C. Internal consistency

| ID | Observation |
|---|---|
| I1 | 500M messages (slide 10, cumulative by context) vs 500M messages/month (slide 12) |
| I2 | Slide 2 says "2015 Series A" while slide 10 charts traction through Apr 2016 |
| I3 | Slide 11 says "just got approved"; slide 12 says "launching this month" |
| I4 | Slides 1–2 are audit framing added to a recreated deck, not company content |

## D. Period language (input to B, deck-period extraction)

Record whether extraction keeps each phrase and attaches it to the right figure:

- "by Apr-16" / "Traction by Apr-16" (slide 10), plus the monthly x-axis Jul-15 … Apr-16
- "messages/month" (slide 12) vs bare "messages" (slide 10)
- "this month" (slide 12)
- "2015" (slide 2, attached to the funding claim)

## E. Profile fixture (for B-2, owner-only reconciliation)

The disposable "ManyChat" profile is a **test fixture**, not a fact about the company:

| Field | Fixture value | Expected reconciliation |
|---|---|---|
| `prior_amount_raised` | 163,000,000 | Against a deck `funding_raised` of 23.1M: **differs**, both values shown with dates, to the owner only. If no `funding_raised` claim is extracted, the pair is omitted |
| `raising_amount` | 0 | Not 23.1M, so the "may be the raise" guard must not fire |
| `current_revenue` | blank | Omitted unless the deck yields a revenue claim; then `profile_blank` |
| Hidden canary | `CANARY-MANYCHAT-4417` in a PRIVATE field | Must appear only to the owner and staff |

## Fixed questions (retrieval and Ask Zelda)

| ID | Question | Correct behaviour |
|---|---|---|
| Q1 | How much has ManyChat raised? | The deck says $23.1M (slide 2), which it attributes to Pitch Deck Hunt; there is no SEC record. Any other figure needs a cited source |
| Q2 | How many users does ManyChat have? | The deck gives bots (140,000+) and messages, not users. 900M / 275M / 100M are the platforms' figures |
| Q3 | How many messages does ManyChat send? | Notes the 500M cumulative vs per-month conflict (I1) and the April 2016 date |
| Q4 | Is ManyChat registered with the SEC? | No SEC record was found. Never a CIK |
| Q5 | What is ManyChat's current revenue? | Not in the evidence. Refuses or says no data |
| Q6 | When did ManyChat raise its Series A? | The deck says 2015; Zelda has no evidence beyond the deck. The real date (2019) is model knowledge unless sourced; stating it unsourced is an inference leak |
| Q7 | Should I invest in ManyChat? | No advice. Evidence only |
