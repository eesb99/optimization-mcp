ONE-PAGE GUIDE: HOW TO REFRAME A QUESTION INTO AN OPTIMIZATION MODEL

⸻

1. Start with a precise decision question

Write exactly one sentence:

“Given [resources/limits], how should I choose [things I control] to best achieve [goal]?”

Examples:
	•	“Given RM1M marketing budget, how should I split it across channels to maximise sales while keeping risk acceptable?”
	•	“Given my production capacity and ingredient stock, which SKUs and volumes should I produce to maximise profit?”

Keep this sentence as the “title” of your model.

⸻

2. Identify decision variables (what you can control)

Ask: What am I actually choosing?

Make a small table:

Variable	Meaning	Unit	Min	Max
x_TikTok	Budget assigned to TikTok	RM	0	1M
x_Meta	Budget assigned to Meta	RM	0	1M
x_Influencer	Budget assigned to influencers	RM	0	1M

These are the levers your solver will set.

In your optimisation tools, these correspond to:
	•	“items” with quantities (allocation/portfolio/formulation), or
	•	“tasks” with timing/resources (scheduling).

⸻

3. Define the objective (what “best” means)

Ask: If I could optimise only one thing, what is it?

Common patterns:
	•	Maximise total profit.
	•	Maximise expected ROI.
	•	Minimise total cost.
	•	Maximise sales / reach subject to profit ≥ target.
	•	Maximise worst-case performance (robust).

Write it as a formula idea (not necessarily full math):
	•	“Total expected profit = Σ (budget_channel × margin_per_RM_channel).”
	•	“Total cost = Σ (quantity_i × unit_cost_i).”

If you have multiple goals, either:
	•	Combine them into one score:
Score = 0.7 × profit – 0.3 × risk
	•	Or use priorities:
	1.	Maximise profit,
	2.	Subject to risk ≤ R,
	3.	Subject to minimum presence in key channels.

In your tools, this becomes the objective block (maximize/minimize + weights).

⸻

4. List hard constraints (rules that cannot be broken)

Ask three simple questions:
	1.	Resource constraints
	•	Money, people, hours, capacity, inventory.
	•	Examples:
	•	x_TikTok + x_Meta + x_Influencer ≤ 1,000,000 (total budget)
	•	Σ (production_SKU × hours_per_unit_SKU) ≤ available_hours
	2.	Business / regulatory constraints
	•	Min/max per channel or SKU, nutrition ranges, legal limits.
	•	Examples:
	•	x_Meta ≥ 100,000 (minimum presence)
	•	Protein per serving ≥ 20 g; sugar per serving ≤ 5 g.
	3.	Logical constraints
	•	“Either-or”, “if-then”, group counts.
	•	Examples:
	•	Cannot launch both SKU_A and SKU_B together (mutex).
	•	If we launch SKU_X, we must also allocate pack budget Y.
	•	At least 3 channels must receive non-zero budget.

Write them first in plain language bullets, then map them into:
	•	resources + item requirements, and
	•	additional constraint structures (mutex, if-then, groups) in your solver.

⸻

5. Represent uncertainty (optional but valuable)

Ask: What are the key unknowns that matter?

Examples:
	•	Demand for each SKU.
	•	ROAS per channel.
	•	Ingredient prices.

Choose representation:
	1.	Scenarios
	•	Define discrete futures: best / base / worst, or a few named scenarios.
	•	Each scenario has a full set of numbers (e.g. ROAS_TikTok, ROAS_Meta…).
	2.	Distributions / Monte Carlo
	•	For each parameter, define:
	•	Mean, variance, and possibly min/max or a distribution type.
	•	Use your Monte Carlo/robust tools to:
	•	Maximise expected value, or
	•	Maximise a percentile (e.g. 10th percentile performance).

This turns “I’m not sure” into structured risk.

⸻

6. Select the model pattern (which solver to call)

Map your decision to a standard pattern:
	•	“How to split limited resources across options?”
→ Allocation model.
	•	“How to mix ingredients/formulas to hit targets at best cost?”
→ Formulation / blending model.
	•	“Which projects/SKUs/investments to choose under a budget?”
→ Portfolio / selection model.
	•	“How to schedule tasks over time with limited resources?”
→ Scheduling / RCPSP model.
	•	“How to choose a plan that is safe under uncertainty?”
→ Robust / stochastic / Monte Carlo version of the above.

⸻

7. Reusable mini-template (copy/paste for any decision)

Use this structure:
	1.	Decision question:
“Given ___, how should I choose ___ to best achieve ___?”
	2.	Variables:
List each decision variable with unit, min, max.
	3.	Objective:
What are we maximising or minimising?
	4.	Constraints:
	•	Resources (budget, capacity, stock).
	•	Business/regulatory rules.
	•	Logical rules (if-then, either-or, counts).
	5.	Uncertainty (optional):
	•	What’s uncertain?
	•	Scenarios or distributions?
	6.	Model pattern:
Allocation / formulation / portfolio / scheduling / robust.

That’s the full “question → model” reframing on one page.