# Growth Portal — Audit v2

Not "what is missing from the code" this time. **What we actually do in a
session to reach a scaling decision, step by step, and whether the portal can
do it.** Written 3 Aug 2026, with live numbers pulled while writing.

---

## Part 1 — The loop we actually run

Every real decision in these sessions followed the same seven steps. The portal
covers two of them.

| # | What we do | Portal |
|---|---|---|
| 1 | **Prove the measurement before reading it** — pixel quality, conversion-action config, is the tag even alive | ⚠️ partial |
| 2 | **Read performance at the level the decision is made** — campaign, ad group, creative | ⚠️ campaign only |
| 3 | **Check capacity, not just efficiency** — budget utilization, delivery status | ❌ **nothing** |
| 4 | **Correlate with what changed** — deploys, budget edits, config edits | ⚠️ partial |
| 5 | **Pick a step size, pre-commit the test and the revert criterion** | ❌ nothing |
| 6 | **Execute, then verify the execution landed** | ❌ out of scope by design |
| 7 | **Re-check after N closed days against the pre-committed criterion** | ❌ nothing |

Steps 3, 5 and 7 are the ones that decide whether money gets spent well. None
of them exists.

---

## Part 2 — The biggest gap: the portal measures efficiency and is blind to capacity

Every scaling decision we made was about **headroom**, not about ratio. TikTok's
was: *3 of 4 live campaigns are budget-capped at 93-95% utilization, total
capacity only 1,228 TRY/day.* That sentence is the decision. The portal cannot
produce it, because no adapter pulls a budget and `MetricRow` has no field for
one.

Here is the same question asked of Google, live, last 7 days:

| Campaign | Spend/day | Budget/day | Used | Purchase ROAS |
|---|---:|---:|---:|---:|
| ES \| Branded Search | 222 | 2,000 | **11%** | **14.9** |
| JHome \| PMAX \| Morocco | 646 | 8,800 | **7%** | **8.2** |
| App Install \| Android | 1,598 | 15,000 | 11% | **1.36** |
| PMAX \| Beauty & Perfumes | 218 | 730 | 30% | **0.55** |
| PMAX \| Fashion & Accessories | 255 | 640 | 40% | **0.77** |
| PMAX \| Rest of Catalog | 127 | 640 | 20% | **0.00** |
| **Account** | **3,066** | **27,810** | **11%** | — |

Two things fall out immediately, and neither is visible anywhere in the portal:

**Google is delivery-limited, not budget-limited.** The account uses 11% of the
budget already authorised. Raising a budget here does nothing at all — the
constraint is demand and eligibility, not money. A `Grow` verdict on a Google
campaign would recommend an action that cannot execute.

**72% of Google spend sits at ROAS ≤ 1.36.** App Install burns 1,598/day for 13
in-app purchases a week, and the three category PMAX campaigns burn ~600/day
between them for 0.55, 0.77 and literally zero. Meanwhile the two that work —
Branded Search at 14.9 and JHome PMAX at 8.2 — take 28% of the spend.

The portal's campaign analyzer would rank these by money impact and reach the
same list. What it would not tell you is that the fix is not "raise the good
one" — that lever is already at 7% and pulling it changes nothing.

**What this needs:** `budget`, `budget_type` and `delivery_status` on every
metric row, and a capacity view that answers "where is there headroom" before
any Grow verdict is allowed to say "scale this".

---

## Part 3 — Measurement checks we run every session, that the portal cannot

The single most valuable thing done in these sessions was catching that a
number was wrong before anyone acted on it. The portal has `Control Ratio` for
exactly this, and computes **one** of the four that matter.

| Check | How we do it now | Portal |
|---|---|---|
| Server events per order | `ads_get_dataset_stats` ÷ ERPNext orders | ❌ declared in the agent's tools, never written |
| Event match quality / `external_id` coverage | `ads_get_dataset_quality` | ❌ no adapter reads it |
| Deduplication ratio | reported purchases ÷ actual orders | ❌ |
| ATC → purchase | Shopify + pixel | ❌ no Shopify adapter |
| Items per order | ERPNext | ✅ |
| Is the tag alive at all | load the site, read the page | ❌ |
| Conversion action config | `customer_conversion_goal` audit | ❌ |

That last row is not theoretical. In the same 7 days, this account reports:

- `JUSTYOL - Justyol (Android) First open` — 1,290 conversions
- `com.justyol.retail (Android) first_open` — 761 conversions

**Two separate first-open actions for what is one app install**, from the old
and new app configurations, both live and both counted. Any "conversions"
figure on that campaign is inflated by whichever one is redundant. This is the
exact class of misconfiguration that took a full session to find in July, and
nothing in the portal watches for it.

**What this needs:** a config-audit pass per platform that lists conversion
actions, flags duplicates and dead ones, and writes a `Growth Finding` — and
the three missing control ratios actually computed.

---

## Part 4 — The decision discipline is not encoded anywhere

The most expensive lesson so far is written in memory, not in code:

> TikTok's efficient ceiling for this account is ~750-900 TRY/day; doubling the
> budget roughly quartered ROAS. Any future scaling must go in ~15% steps with
> 3 closed days between, not 2×.

That lesson was learned by scaling 104% in one step, watching ROAS fall 18.7 →
5.8 → 4.7 over two days, and reverting. It cost real money to buy, and the
portal would not stop anyone repeating it tomorrow.

Missing, in order of what it would have saved:

1. **Per-entity step ceiling.** A `Grow` verdict should carry a maximum step
   (+15%), not an open-ended "candidate to scale".
2. **A pre-committed test.** When a scale-up is actioned, the portal should
   record the criterion and the date it will be judged on — before the money
   moves, not after.
3. **Automatic re-check.** On that date, compare and say plainly whether the
   step passed or failed its own test.
4. **Known ceilings per channel.** TikTok's ~900 TRY/day ceiling is a fact
   about this account. It belongs in a rule, not in a memory file.

One piece of this discipline *is* encoded, and it is the one that already
prevented a loss: `guard.assert_pulled_performance` refuses to judge an entity
whose performance was not pulled — the rule written after nearly disabling
UGC-DPA-All-Campaign, the single best campaign in the TikTok account.

---

## Part 5 — Still missing as data

Unchanged from v1 except where the three new adapters landed:

| | State |
|---|---|
| Meta / Google / TikTok spend | ✅ adapters written, **never yet run** |
| Budget & delivery status | ❌ — see Part 2 |
| Ad-group / creative level | ❌ campaign only |
| COGS per `item_code` | ❌ — no contribution margin, only revenue |
| Cost per **delivered** order | ❌ needs COGS + order-level join |
| Shopify / GA4 / Clarity / SEMrush | ❌ |
| AppsFlyer | ❌ — and the dashboard there reads 42.37 against a real 1.88 |
| Deploy events on the timeline | ❌ — only ad-platform change logs |
| Period-over-period comparison | ❌ — the Nov–Jan seasonal peak is invisible |
| `Dormant` verdict | ❌ defined, never issued; `dormant_after_days` unused |

---

## Part 6 — Order of work

**Now, because it blocks every scaling decision:**
1. `budget`, `budget_type`, `delivery_status` on `MetricRow` + all three adapters
2. A capacity view: spend vs authorised budget vs delivery status per campaign
3. Gate `Grow` on headroom — no "scale this" for an entity at 7% utilization

**Next, because it is what a wrong number costs:**
4. The three missing control ratios
5. A per-platform config audit writing `Growth Finding`
6. Deploy events on the timeline

**Then:**
7. Step ceilings, pre-committed tests, automatic re-check
8. Ad-group and creative level
9. COGS → contribution margin → cost per delivered order
10. Shopify, GA4, Clarity, SEMrush, AppsFlyer

---

## What the audit is not saying

The engine, the guards and the ERPNext path are sound and were exercised against
real rows. The three new adapters are written against verified API shapes. The
gap is not quality — it is that the portal currently answers *"which entity is
inefficient"* when the decisions we actually make need *"where is there room,
what will I commit to, and how will I know if I was wrong"*.
