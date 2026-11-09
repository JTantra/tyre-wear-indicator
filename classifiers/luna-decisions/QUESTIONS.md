# Luna refined-v2 question contract

Exact executable full rubric/payloads/parsers: [refinement source](refinement_v3.py). Same model gpt-6-luna2026-09-22, differing APIs, no backbone fine-tuning.

Decisions typed predicate tread_visible:
“Is enough tread face clear to see groove/raised relief or wear? Partial/oblique views suffice if clear. Sidewall/rim alone and fully obscuring mud do not. No exact depth measurement is required.”

Decisions typed predicate clear_damage:
“Is cracking, exposed cords, torn rubber or severe visible tyre damage clearly present? Do not confuse tread grooves, mud or shadows with damage.”

Condition choice good/bad/review uses the FULL executable RUBRIC, not the abbreviated infographic summary. It distinguishes design from condition, looks for raised relief versus flattened/bald wear, allows clear partial views, does not infer hidden detail/depth/TWI/roadworthiness. Decisions direct choice is v2; legacy probabilities/gates/OOF routing are separate diagnostics.

Responses observation checks summarized(not five separate API calls): enough tread visible; distinct raised groove relief versus flattened/shallow/obscured; visible damage; condition good/bad/review; conflicting/uncertain evidence requiring review. Structured fields include null physical-depth/TWI outputs. One response, not five independently priced questions.

The current [cost visual](../../docs/assets/twi-six-methods-costs.svg) keeps these questions and does not reinstate its removed Human Review section or availability badges. README status and scientific abstention/safety qualifications are still truthful.
