---
target: página Como funciona o Wellhub
total_score: 31
p0_count: 0
p1_count: 2
timestamp: 2026-07-08T00-24-51Z
slug: views-portal-wellhub-templates-xml-como-funciona
---
# Critique — página "Como funciona o Wellhub"

Method: dual-agent (A design review · B detector+static). Browser unavailable (no Chrome) — no live overlay.

## Design Health Score: 31/40 (Good, with clear issues)

| # | Heuristic | Score | Key issue |
|---|-----------|:---:|---|
| 1 | System status | 3 | Long-scroll 7 sections, no TOC/anchors |
| 2 | Real world | 4 | "streaming de academias" analogy + clear PT-BR |
| 3 | Control/freedom | 3 | FAQ collapsible, no back-to-top |
| 4 | Consistency | 4 | Tokens rigorous, parity with form |
| 5 | Error prevention | 3 | Honest no-show warning |
| 6 | Recognition | 3 | "same email portal→app" recall across steps |
| 7 | Flexibility | 2 | No anchors/TOC, full linear cost |
| 8 | Aesthetic/minimal | 2 | Glass-as-default + gradient fatigue (ban) |
| 9 | Error recovery | 3 | N/A static |
| 10 | Help/docs | 4 | Page IS the help; FAQ+steps thorough |

## Anti-Patterns Verdict: Amber
- Glassmorphism-as-default (BAN): every section same glass panel (wh-block×4, wh-steps-card, wh-card) blur(18px).
- Coral→purple 135deg gradient = SaaS default; #FF385C = Airbnb Rausch; real Wellhub brand is yellow/black → generic AND off-brand.
- Identical card grids / section sameness (860px glass card ×7).
- Counter-signal: wh-phone/wh-phones device frames show real intent.
- Detector: target template 0 findings. 1 out-of-scope `overused-font` (Arial, Asaas email block, line 445). No overlay (no Chrome).
- Static scan (B): side-stripe ban wh-alert border-left:4px (scss:606) rendered in target; contrast --wh-ink-500 on --wh-bg = 4.41:1 FAIL AA.

## Priority Issues
- [P1] wh-phones overflow on narrow mobile (306px min in ~240px space) → clip/hscroll. Fix: below 380px stack, no overlap. → layout
- [P1] Side-stripe ban wh-alert border-left:4px colored. Fix: full 1px border + tint. → polish
- [P2] Glassmorphism-as-default; 5+ frosted panels + mobile paint cost. Fix: solid surfaces, glass for one moment. → quieter
- [P2] Payment step 3 no adjacent reassurance (trust valley); FAQ facts 4 sections away. Fix: inline chip "Sem taxa · Cancele quando quiser · Seguro". → onboard
- [P2] Contrast muted --wh-ink-500 on --wh-bg 4.41:1 fail; wh-credit worst case. Fix: ink-700 on tinted bg. → colorize
- [P3] Flat hierarchy (all titles 1.25rem/800) + peak-end broken (page ends on image credit not CTA) + off-brand palette. Fix: type scale, group 7 steps into phases, move credit above CTA, shift accent to real brand. → shape + colorize

## Persona Red Flags
- Jordan: 7-step wall no phase grouping; HR-formal jargon; payment no reassurance.
- Riley: hunts hidden fee, answer 4 sections away; wh-faq__q no hover/focus bg.
- Casey: phones overflow; muted-on-glass <4.5:1 in sunlight; no jump nav. Tap targets ok.

## Minor
- 3 breakpoints (640/880/992) hard to reason mid-width.
- Hero -72px overlap accidental here (designed for form card).
- role="note" good keep.
