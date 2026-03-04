---
name: pptx-generator
description: Generate a PowerPoint (.pptx) presentation using python-pptx and the shared pptx_utils.py module. Use this skill whenever the user asks to create a PowerPoint file, generate a .pptx, export slides to PPTX, or wants a downloadable presentation file. Also use when the user says "generate pptx", "make a PowerPoint", "export to pptx", or "I need a .pptx file".
---

# PPTX Generator

Generate a professional Microsoft-branded PowerPoint (.pptx) presentation using python-pptx and the shared `pptx_utils.py` module.

## When to Use This Skill

Use this skill when the user:
- Says "make a PowerPoint", "generate pptx", "export to pptx", or "I need a downloadable presentation"
- Wants to create a new PPTX presentation from scratch on a given topic

## Step-by-Step Process

### Step 1: Define the slide content from a plan or outline

Work from the plan or outline provided. For each slide, identify:
- **Slide type**: title/lead, section divider, standard content, or closing
- **Title**: the main heading for the slide
- **Body content**: bullets, tables, code blocks, metrics, cards, or a mix
- **Speaker notes**: full presenter transcripts written in the plan - **MUST be written verbatim in full**; these are complete presenter transcripts, not summaries

> **CRITICAL**: Speaker notes must be full presenter transcripts. Write them **word-for-word** as provided in the plan into the `notes=` parameter. Do NOT summarize, shorten, or paraphrase. The presenter depends on these exact scripts. If a note is 500 words, the PPTX note must be 500 words.

### Step 2: Design the slide layout for each slide

For each slide, choose the best visual representation:

| Content Pattern | PPTX Approach |
|---|---|
| Title/lead slide | `create_lead_slide()` |
| Section divider | `create_section_divider()` |
| Title + bullet list | `create_standard_slide()` + `add_bullet_list()` |
| Title + table | `create_standard_slide()` + `add_styled_table()` |
| Title + code block | `create_standard_slide()` + `add_code_block()` |
| Title + comparison table | `create_standard_slide()` + `add_styled_table()` |
| Title + multiple short items | `create_standard_slide()` + `add_numbered_items()` |
| Title + cards/pillars | `create_standard_slide()` + `add_card_grid()` or `add_pillar_cards()` |
| Title + big metrics | `create_standard_slide()` + `add_metric_card()` |
| Title + blockquote/callout | `create_standard_slide()` + `add_callout_box()` |
| Closing/thank-you slide | `create_closing_slide()` |

**Visual enhancement rules** - go beyond 1:1 mapping for richer slides:
- Plain bullet lists with bold prefixes -> use `add_numbered_items()` or `add_card_grid()` for visual cards
- Comparison/feature lists -> use `add_pillar_cards()` for vertical pillars
- Single big number/metric -> use `add_metric_card()`
- Important callout text -> use `add_callout_box()` or `add_warning_box()` (height auto-sizes)
- Code/YAML blocks -> use `add_code_block()` (dark theme, monospace)
- Tables with data -> use `add_styled_table()` (alternating rows, header styling)
- Right-side visual cards -> use `add_rounded_card()` for highlight panels
- Vertical step flows -> use `add_arrow_down()` between stacked cards

### Design Aesthetics Principles

PPTX slides must be **distinctive and purposefully designed** -- not generic AI-output. Apply these principles on every slide:

**1. Dominant color + sharp accent (not timid even palettes)**
Use `MS_DARK_BLUE` (#243A5E) as the dominant structural color, `MS_BLUE` (#0078D4) as the single sharp accent. Do not scatter multiple accent colors across one slide. One color leads; the others support.

**2. Visual hierarchy through contrast, not size alone**
- Title: 28pt bold dark blue | Section: 44pt bold white on dark | Body: 12-14pt muted
- Use weight extremes: bold headings + light body text. Avoid mid-weight everything.
- Key stat or metric: oversized (36-44pt) in accent blue against neutral background.

**3. Layout variety -- no two adjacent slides the same pattern**
Rotate between: 2-column split | full-width table | pillar cards | code+callout | metric row. Never use the same layout three slides in a row.

**4. Whitespace is a design element**
Generous padding inside cards (`Inches(0.2)` minimum). Cards should not touch each other -- use `Inches(0.2-0.35)` gaps. Content should never fill the full slide edge-to-edge.

**5. Depth through layering**
Build slides in z-order layers (see Layer Order rule below). Use `add_rounded_card()` as backgrounds before adding text -- the subtle shadow/fill creates visual depth that flat text boxes lack.

**6. Sizes to content -- no empty boxes**
- Use `estimate_text_height()` to size callout boxes to their text
- For card grids, measure title + desc length and choose `card_h` accordingly
- Tables: `0.38 * row_count` inches -- never add extra empty rows
- Code blocks: `line_count * 0.19 + 0.3` inches

**7. Avoid generic patterns**
- Never center all text on all slides
- Never use a bullet list when a card grid would communicate structure better
- Dark-background section dividers should stand in sharp contrast to the white content slides they bracket
- Vary left/right/split layouts -- do not always lead with text on the left

### Step 3: Write the generator script

Create a file named `generate_{topic}_pptx.py` inside `outputs/slides/` following this pattern:

```python
#!/usr/bin/env python3
"""Generate {TOPIC} PowerPoint presentation using pptx_utils."""
import os, sys
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(SCRIPT_DIR)))  # repo root
from pptx_utils import *

TOTAL = <number_of_slides>

def build():
    prs = create_presentation()

    # -- 1. Title / Lead --
    create_lead_slide(prs,
        title="...",
        subtitle="...",
        meta="L300 Deep Dive  |  February 2026",
        level="L300",
        notes="Speaker notes here...")

    # -- 2. Agenda --
    slide = create_standard_slide(prs, "Agenda", 2, TOTAL,
        notes="Speaker notes...")
    # ... add content using pptx_utils functions ...

    # -- 3. Section Divider --
    create_section_divider(prs, "Section Title",
        "Subtitle text", "Speaker notes...")

    # ── 4+ Content slides ──
    slide = create_standard_slide(prs, "Slide Title", 4, TOTAL,
        notes="Speaker notes...")
    # ... add tables, cards, code blocks, etc. ...

    # ── Last. Closing ──
    create_closing_slide(prs,
        title="Key Takeaways",
        takeaways=["Point 1", "Point 2", "Point 3"],
        cta_title="Get Started",
        cta_url="link.here",
        cta_items=[("Big", "Small"), ...],
        page_num=TOTAL, total=TOTAL,
        notes="...")

    out = os.path.join(SCRIPT_DIR, "topic-level-duration.pptx")
    save_presentation(prs, out)

if __name__ == "__main__":
    print("Generating {TOPIC} PowerPoint...")
    build()
    print("  Done!")
```

### Step 4: Run the script

```bash
python3 outputs/slides/generate_{topic}_pptx.py
```

Verify:
- Output file exists in `outputs/slides/`
- Slide count matches expected
- No errors in terminal

## QA (Required)

After generating the `.pptx`, run the programmatic QA checks, then invoke pptx-qa-subagent for content review.

Quick checklist:
1. Run programmatic QA via `run_pptx_qa_checks` tool or: `python scripts/pptx_qa_checks.py outputs/slides/{OUTNAME}.pptx --expected-slides {TOTAL}`
2. Invoke `pptx-qa-subagent` with PPTX path, programmatic results, and expected slide descriptions
3. Fix CRITICAL/MAJOR issues and re-verify until `CLEAN`

## Critical Rules

1. **Always import from `pptx_utils`** - never duplicate color constants, shape helpers, or slide templates
2. **Always use `create_presentation()`** to initialize - it sets the correct slide dimensions and resolves asset paths
3. **Always include `add_ms_logo()`** on every slide - `create_standard_slide()`, `create_section_divider()`, `create_lead_slide()`, and `create_closing_slide()` do this automatically
4. **Always copy speaker notes verbatim** from the plan using the `notes=` parameter - these are full presenter transcripts; never summarize or shorten them
5. **Content area bounds**: use `CONTENT_LEFT` (0.8"), `CONTENT_TOP` (1.2"), `CONTENT_WIDTH` (11.0") to avoid overlapping with title bar, bottom bar, or logo
6. **No hardcoded colors** - always use the `MS_*` constants from `pptx_utils`
7. **Section dividers use `MS_DARK_BLUE` background** (#243A5E) with white text and logo at bottom-right - dark background ensures the MS logo is clearly readable
8. **Lead slides use the background image** from `assets/lead-bg.jpg`
9. **Tables**: pass `col_widths` parameter to control column proportions, max ~8 rows
10. **Code blocks**: keep to ~15 lines max, use `add_code_block()` for dark-themed rendering
11. **python-pptx must be installed**: `pip install python-pptx`
12. **No top accent bar** - `create_standard_slide()` no longer draws a blue bar at the very top; the title underline is the sole brand accent. Do NOT call `add_top_accent_bar()` on standard slides.
13. **Rounded card borders** - `add_rounded_card()` defaults to no border. Only pass `border=` when a box needs explicit separation from a white background (rare). The fill color alone is sufficient.
14. **Callout / warning box height** - pass `height=None` (or omit) to auto-size the box to its text content. Only pass a fixed `Inches()` height when you need exact placement in a dense layout.

## Overlap Prevention and Layer Order Rules

These rules prevent the most common visual bugs:

**Layer order (z-order = insertion order; last added = on top):**
1. Background fills / color bands / full-slide images
2. Structural containers (cards, panels) -- draw ALL containers first in a dedicated loop
3. Arrows / connectors (`add_arrow_right()`, `add_arrow_down()`) -- draw AFTER all cards
4. Text boxes, icons, number badges -- draw LAST so they always sit on top

**Always use two passes in loops:**
```python
# Pass 1: containers
for i, item in enumerate(items):
    add_rounded_card(slide, x, y, ...)

# Pass 2: arrows (drawn after all cards so arrows are above cards)
for i in range(len(items) - 1):
    add_arrow_down(slide, cx, bottom_of_card[i] + Inches(0.05))

# Pass 3: text/icons (always last)
for i, item in enumerate(items):
    add_textbox(slide, item.title, ...)
```

**Positioning rules:**
1. **Never use `Inches(i)` in loop arithmetic** - `Inches()` converts to EMUs; use plain `i * item_height` not `Inches(i) * item_height`
2. **Title bar occupies 0-1.0"** - never place content above `CONTENT_TOP` (1.2")
3. **Bottom bar + logo occupy 6.8-7.5"** - keep content above `CONTENT_BOTTOM` (6.8")
4. **Logo safe zone**: bottom-right 1.6" x 0.7" is reserved for the Microsoft logo on standard slides
5. **Use `add_arrow_right()` for horizontal flow** and `add_arrow_down()` for vertical flow -- never use text characters like "->" or "v"
6. **When placing a right-side card**, reduce the width of left-side content to avoid overlap - e.g., if a card starts at 8.5", use width `Inches(7.2)` instead of `CONTENT_WIDTH` for left content
7. **`add_numbered_items()`** auto-calculates spacing - verify that `top + len(items) * item_height < 6.8"`
8. **Tables**: total height = `0.38" * row_count` - verify it fits between top position and 6.8"
9. **Code blocks**: estimate height as `line_count * 0.19"` + 0.3" padding

## References

- **API Reference**: `references/api-reference.md` - Complete function signatures and usage
