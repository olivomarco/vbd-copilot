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
| Title + big metric | `create_standard_slide()` + `add_metric_card()` (supports trend arrows) |
| Title + metric row | `create_standard_slide()` + `add_stats_row()` |
| Title + blockquote/callout | `create_standard_slide()` + `add_callout_box()` |
| Title + quote/testimonial | `create_standard_slide()` + `add_quote_block()` |
| Title + feature grid | `create_standard_slide()` + `add_feature_grid()` |
| Title + columns | `create_standard_slide()` + `add_colored_columns()` |
| Title + architecture stack | `create_standard_slide()` + `add_layered_architecture()` |
| Title + process flow | `create_standard_slide()` + `add_process_flow()` |
| Title + SWOT analysis | `create_standard_slide()` + `add_swot_grid()` |
| Title + maturity model | `create_standard_slide()` + `add_maturity_model()` |
| Title + roadmap | `create_standard_slide()` + `add_roadmap()` |
| Title + pricing table | `create_standard_slide()` + `add_pricing_table()` |
| Title + agenda list | `create_standard_slide()` + `add_agenda_list()` |
| Title + timeline | `create_standard_slide()` + `add_timeline()` |
| Title + progress bar | `create_standard_slide()` + `add_progress_bar()` |
| Title + checklist | `create_standard_slide()` + `add_checklist()` |
| High-impact statement | `create_impact_slide()` |
| Gradient background | `create_gradient_slide()` |
| Split layout | `create_two_tone_slide()` |
| Closing/thank-you slide | `create_closing_slide()` |

**Visual enhancement rules** - go beyond 1:1 mapping for richer slides:
- Plain bullet lists with bold prefixes -> use `add_numbered_items()` or `add_card_grid()` for visual cards
- Comparison/feature lists -> use `add_pillar_cards()` for vertical pillars
- Single big number/metric -> use `add_metric_card()`
- Important callout text -> use `add_callout_box()` or `add_warning_box()` (height auto-sizes)
- Quote/testimonial text -> use `add_quote_block()` with attribution
- Code/YAML blocks -> use `add_code_block()` (dark theme, monospace, text embedded in shape)
- Tables with data -> use `add_styled_table()` (alternating rows, header styling)
- Right-side visual cards -> use `add_rounded_card()` for highlight panels
- Vertical step flows -> use `add_arrow_down()` between stacked cards
- Architecture layers -> use `add_layered_architecture()` (text embedded, auto contrast)
- Process flow -> use `add_process_flow()` (text embedded in boxes)

### Design Aesthetics Principles

PPTX slides must be **distinctive and purposefully designed** -- not generic AI-output. Apply these principles on every slide:

**1. Color Budget (MANDATORY -- highest priority rule)**
- Maximum 2 accent hue families per deck: `MS_BLUE` / `MS_BLUE_DARKER` (primary) + `MS_DARK_BLUE` / `MS_NAVY_LIGHT` (structural). That is the full accent palette.
- `MS_GREEN`, `MS_ORANGE`, `MS_RED` are ONLY for semantic meaning (success/warning/error callouts). Never use them to "make a card look different" or "add visual variety."
- NEVER use `MS_PURPLE`, `MS_YELLOW`, or `MS_TEAL` -- they are deprecated.
- For multi-element differentiation (card grids, columns, architecture layers), use **tonal variations** of blue (`MS_BLUE`, `MS_BLUE_DARKER`, `MS_DARK_BLUE`, `MS_NAVY_LIGHT`) or **neutral contrast** (gray vs blue).
- Comparison columns: always `left_color=MS_MID_GRAY, right_color=MS_BLUE`. Never orange vs green.
- Use `TONAL_BLUES` list from pptx_utils when you need 3-5 distinct shades for a single element.

**2. Dominant color + sharp accent (not timid even palettes)**
Use `MS_DARK_BLUE` (#243A5E) as the dominant structural color, `MS_BLUE` (#0078D4) as the single sharp accent. Do not scatter multiple accent colors across one slide. One color leads; the others support.

**3. Visual hierarchy through contrast, not size alone**
- Title: 28pt (`TEXT_H2`) bold dark blue | Section: 46pt (`TEXT_DISPLAY`) bold white on dark | Body: 12-14pt muted
- Use weight extremes: bold headings + light body text. Avoid mid-weight everything.
- Key stat or metric: oversized (36-46pt) in accent blue against neutral background.

**4. Layout variety -- no two adjacent slides the same pattern**
Rotate between: 2-column split | full-width table | pillar cards | code+callout | metric row. Never use the same layout three slides in a row.

**5. Whitespace is a design element**
Generous padding inside cards (`Inches(0.2)` minimum). Cards should not touch each other -- use `Inches(0.2-0.35)` gaps. Content should never fill the full slide edge-to-edge.

**6. Depth through layering**
Build slides in z-order layers: background fill first, then cards/panels, then text/icons on top. Use `add_rounded_card()` as backgrounds before adding text -- the subtle shadow/fill creates visual depth that flat text boxes lack.

**7. Sizes to content -- no empty boxes**
- Use `estimate_text_height()` to size callout boxes to their text
- For card grids, measure title + desc length and choose `card_h` accordingly
- Tables: `0.38 * row_count` inches -- never add extra empty rows
- Code blocks: `line_count * 0.19 + 0.3` inches

**8. Avoid generic patterns**
- Never center all text on all slides
- Never use a bullet list when a card grid would communicate structure better
- Dark-background section dividers should stand in sharp contrast to the white content slides they bracket
- Vary left/right/split layouts -- do not always lead with text on the left

### Vertical Chaining with ElementBox

Most composite functions return an `ElementBox(shape, left, top, width, height)` namedtuple. Use it to stack elements vertically without hardcoding positions:

```python
eb = add_callout_box(slide, "Important note", CONTENT_LEFT, CONTENT_TOP, Inches(10))
next_top = eb.top + eb.height + Inches(0.2)
eb2 = add_code_block(slide, "kubectl get pods", CONTENT_LEFT, next_top, Inches(10))
```

Use `remaining_height(from_top)` to check whether the next element fits before placing it.

> **Note**: `create_section_divider()` does not accept `page_num` / `total` parameters (unlike other slide templates). This is by design -- section dividers are full-bleed and unnumbered.

### Step 3: Write the generator script

Create a file named `generate_{topic}_pptx.py` inside `outputs/slides/` following this pattern:

```python
#!/usr/bin/env python3
"""Generate {TOPIC} PowerPoint presentation using pptx_utils."""
import os, sys
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(SCRIPT_DIR)), 'skills', 'pptx-generator'))
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
1. Run programmatic QA via `run_pptx_qa_checks` tool or: `python skills/pptx-generator/pptx_qa_checks.py outputs/slides/{OUTNAME}.pptx --expected-slides {TOTAL}`
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
10. **Code blocks**: keep to ~15 lines max, use `add_code_block()` for light-themed rendering (light gray background, dark text). Pass `height=None` (or omit) to auto-size the block to its code content. Returns `ElementBox` for vertical chaining.
11. **python-pptx must be installed**: `pip install python-pptx`
12. **Clean title style** - `create_standard_slide()` renders titles in `MS_BLUE` with Segoe UI Semibold and no underline or accent bar. Do NOT call `add_top_accent_bar()` or manually add underline rectangles on standard slides.
14. **Rounded card borders** - `add_rounded_card()` defaults to no border. Only pass `border=` when a box needs explicit separation from a white background (rare).
15. **Callout / warning box line breaks** - When a callout box has multiple sentences, separate them with `\n` so each sentence renders on its own line. This avoids walls of text. Example: `"First point.\nSecond point.\nThird point."`. Height auto-sizes to content when `height=None`.
16. **Embedded text** - composite helpers (`add_badge`, `add_callout_box`, `add_code_block`, `add_blue_speech_panel`, `add_metric_card`, `add_stats_row`, `add_layered_architecture`, `add_process_flow`, `add_activity_bars`, `add_timeline` boxes) embed text in shapes. Do NOT add separate `add_textbox()` overlays for these.
17. **Auto contrast** - `add_icon_circle`, `add_badge`, `add_layered_architecture`, `add_activity_bars`, and `add_blue_speech_panel` use `auto_text_color()` / `ensure_contrast()`. You do NOT need to check light/dark fills manually.
18. **Shrink-to-fit** - use `shrink_to_fit=True` on `add_textbox()` when text length is unpredictable. **Critical for custom card layouts**: whenever you place text inside a fixed-height card (e.g., `add_rounded_card` + `add_textbox` overlay, or `_set_shape_text` on a card), you MUST use `shrink_to_fit=True` so PowerPoint auto-scales text that exceeds the card height. Without this, long text overflows past the card boundary and overlaps with elements below.
19. **Use `add_metric_card()` for both metrics and KPIs** - it supports optional `trend` and `trend_positive` parameters. Do NOT use `add_kpi_card()` (deprecated alias).
20. **Function Decision Guide** - see the table in `references/api-reference.md` to pick the right function for your content pattern.
21. **Bold markup** - use `**word**` (double-asterisk) inside any text string to make a word or phrase bold in the rendered slide. Bold runs automatically use **Segoe UI Semibold** for a polished typographic weight distinction (not just synthetic bold). This works in `add_textbox()`, `add_bullet_list()` (plain string items), `add_numbered_list()`, `add_callout_box()`, `add_styled_table()` (data cells), `add_card_grid()`, `add_pillar_cards()`, `add_feature_grid()`, `add_numbered_items()`, `add_colored_columns()`, `add_header_card_with_bullets()`, `add_checklist()`, `_set_shape_text()`, and `_add_shape_paragraph()`. Use bold markup **generously** to highlight key terms, product names, technical concepts, and important phrases within body text and bullet items - for example: `"Use **GitHub Copilot** to accelerate development"` or `"Runs on **GitHub Actions** with **read-only** permissions"`. Aim for 2-4 bold phrases per text block or bullet list. The tuple format `(bold_prefix, rest)` in bullet lists still works unchanged.

## Overlap Prevention and Layer Order Rules

These rules prevent the most common visual bugs:

**ElementBox return pattern - chain elements without overlap:**

All composite functions return an `ElementBox(shape, left, top, width, height)`
namedtuple. This includes: `add_bullet_list`, `add_numbered_list`, `add_checklist`,
`add_numbered_items`, `add_card_grid`, `add_feature_grid`, `add_stats_row`,
`add_pillar_cards`, `add_metric_card`, `add_comparison_columns`, `add_colored_columns`,
`add_layered_architecture`, `add_agenda_list`, `add_icon_row`, `add_pricing_table`,
`add_swot_grid`, `add_maturity_model`, `add_roadmap`, `add_timeline`,
`add_activity_bars`, `add_process_flow`, `add_callout_box`, `add_warning_box`,
and `add_quote_block`. Use the returned box to chain elements vertically:

```python
eb1 = add_callout_box(slide, text1, left, top, width)
eb2 = add_bullet_list(slide, items, left, eb1.top + eb1.height + Inches(0.15), width)
eb3 = add_quote_block(slide, quote, left=left, top=eb2.top + eb2.height + Inches(0.2), width=width)
```

**Check remaining space before placing elements:**

Use `remaining_height(from_top)` to check available vertical space before
placing the next element. This prevents content from overflowing past
`CONTENT_BOTTOM (6.8")`:

```python
eb = add_bullet_list(slide, items, left, top, width)
next_top = eb.top + eb.height + Inches(0.15)
avail = remaining_height(next_top)
# avail is EMU space left; compare with the height of the next element
if avail < Inches(2.0):
    # not enough room -- shrink card_h or move to next slide
```

**Auto-sizing lists - let height fit content:**

`add_bullet_list()`, `add_numbered_list()`, and `add_checklist()` default to
`height=None` which auto-sizes the container to its content. Pass explicit
`height=Inches(X)` only when you need a fixed-size container. Auto-sizing
prevents both overflow (text cut off) and wasted space (huge empty box).

**Bounds validation:**

Grid and stacking functions (`add_card_grid`, `add_feature_grid`, `add_pillar_cards`,
`add_stats_row`, `add_icon_row`, `add_numbered_items`, `add_agenda_list`,
`add_layered_architecture`, `add_timeline`, `add_activity_bars`, `add_process_flow`,
`add_maturity_model`, `add_pricing_table`, `add_roadmap`) emit warnings when content
would extend beyond slide boundaries. Minimum card width is `Inches(1.5)` -- grids
with too many columns will warn when cards become too narrow to fit readable text.

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
