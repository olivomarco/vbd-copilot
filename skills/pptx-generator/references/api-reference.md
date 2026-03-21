# pptx_utils API Reference

Quick reference for all functions in `pptx_utils.py`. Functions are grouped by
usage frequency: **Core** (use often), **Composites** (pre-built layouts), and
**Advanced** (rarely needed directly).

> **Key design principles (v3):**
> - **Native bullets**: `add_bullet_list()`, `add_checklist()`, and `add_header_card_with_bullets()` use
>   real PowerPoint bullets (`a:buChar`/`a:buAutoNum`), not Unicode text prefixes. Bullets are
>   editable, indentable, and style-changeable in the PowerPoint UI.
> - **Auto-grouping**: Composite elements (callout boxes, metric cards, header cards, code blocks,
>   card grids, speech panels) auto-group their sub-shapes into a single selectable/movable unit.
>   Users can ungroup in PowerPoint for editing.
> - **Premium typography**: Lead/section/impact titles use `Segoe UI Light` with letter spacing.
>   Standard slide titles use `Segoe UI Semibold`. Body text uses `Segoe UI`.
> - Composite elements embed text in shapes via `_set_shape_text()` - shapes are
>   single selectable units in PowerPoint, not floating textboxes on top.
> - Internal offsets scale proportionally with container size - no hardcoded Inches.
> - `auto_text_color()` / `ensure_contrast()` prevent white-on-white and low-contrast bugs.
> - `add_textbox()` supports `shrink_to_fit` and `v_align` to prevent text overflow.
> - `group_shapes()` lets you combine multi-shape elements into one unit.
> - `ElementBox` namedtuple provides consistent return types for chaining.

---

## Initialization

### `create_presentation() -> Presentation`
Creates a new 16:9 presentation. **Always call this first.**

### `new_blank_slide(prs) -> slide`
Adds a blank slide (layout index 6).

---

## Constants

### Colors
| Constant | Hex | Usage |
|----------|-----|-------|
| `MS_BLUE` | #0078D4 | Primary accent, borders, links |
| `MS_DARK_BLUE` | #243A5E | Headings, dark backgrounds |
| `MS_LIGHT_BLUE` | #50E6FF | Azure cyan accent |
| `MS_WHITE` | #FFFFFF | Slide backgrounds |
| `MS_LIGHT_GRAY` | #F2F2F2 | Alternating rows, subtle backgrounds |
| `MS_MID_GRAY` | #D2D2D2 | Borders, divider lines |
| `MS_DARK_GRAY` | #3D3D3D | Secondary text |
| `MS_TEXT` | #212121 | Body text |
| `MS_TEXT_MUTED` | #616161 | Muted/caption text |
| `MS_CALLOUT_BG` | #EFF6FC | Callout box background |
| `MS_GREEN` | #107C10 | Success, positive metrics |
| `MS_ORANGE` | #FF8C00 | Warning, attention |
| `MS_PURPLE` | #881C98 | **DEPRECATED** -- use `MS_DARK_BLUE` |
| `MS_RED` | #D13438 | Error, critical |
| `MS_BLUE_DARKER` | #006CBE | Darker blue variant |
| `MS_CODE_BG` | #F2F2F2 | Code block background (light theme) |
| `MS_CODE_TEXT` | #212121 | Code block text |
| `MS_ACCENT_LIGHT` | #CCE4FF | Light text on blue backgrounds |
| `MS_BLUE_LIGHT_BG` | #DEECF9 | Info / highlight background |
| `MS_NAVY_LIGHT` | #2E4A6E | Subtle dark layering |
| `MS_SUCCESS_BG` | #DFF6DD | Success / positive background |
| `MS_WARNING_BG` | #FFF4E5 | Warning background |
| `MS_ERROR_BG` | #FDE7E9 | Error / negative background |
| `MS_YELLOW` | #FFB900 | **DEPRECATED** -- use `MS_ORANGE` |
| `MS_TEAL` | #038387 | **DEPRECATED** -- use `MS_BLUE_DARKER` |

### Typography Scale
| Constant | Size (pt) | Usage |
|----------|-----------|-------|
| `TEXT_DISPLAY` | 46 | Hero / title slides |
| `TEXT_H1` | 32 | Primary headings |
| `TEXT_H2` | 28 | Slide titles (standard slides) |
| `TEXT_H3` | 20 | Sub-headings / card headers |
| `TEXT_BODY` | 14 | Body copy |
| `TEXT_BODY_SM` | 12 | Secondary body / descriptions |
| `TEXT_CAPTION` | 10 | Captions, annotations, footnotes |
| `TEXT_MICRO` | 8 | Tiny labels, watermarks |

### Spacing Grid
| Constant | Value | Usage |
|----------|-------|-------|
| `SPACE_XS` | 0.08" | Tight: internal padding |
| `SPACE_SM` | 0.15" | Small: between related elements |
| `SPACE_MD` | 0.25" | Medium: standard spacing |
| `SPACE_LG` | 0.4" | Large: between sections |
| `SPACE_XL` | 0.6" | Extra large: major divisions |
| `SPACE_2XL` | 0.8" | 2X large: slide margins |

### Layout Constants
| Constant | Value | Usage |
|----------|-------|-------|
| `SLIDE_WIDTH` | 13.333" | Slide width (16:9) |
| `SLIDE_HEIGHT` | 7.5" | Slide height |
| `CONTENT_LEFT` | 0.8" | Left margin for content |
| `CONTENT_TOP` | 1.2" | Top of content area (below title) |
| `CONTENT_WIDTH` | 11.0" | Max content width |
| `CONTENT_BOTTOM` | 6.8" | Bottom of content area |
| `FONT_FAMILY` | "Segoe UI" | Default font |
| `FONT_SEMIBOLD` | "Segoe UI Semibold" | Headings, slide titles |
| `FONT_LIGHT` | "Segoe UI Light" | Display/lead titles |
| `FONT_MONO` | "Courier New" | Monospace font for code |

---

## Contrast & Color Helpers

### `auto_text_color(bg_color) -> RGBColor`
Returns `MS_WHITE` or `MS_DARK_BLUE` based on background luminance (WCAG 2.0).
Use whenever you need to pick text color for an arbitrary background.
```python
text_c = auto_text_color(card_fill_color)
```

### `ensure_contrast(text_color, bg_color, min_ratio=3.0) -> RGBColor`
Returns a corrected text_color if contrast ratio is too low. Prevents white-on-white bugs.
```python
safe = ensure_contrast(MS_BLUE, MS_BLUE)   # -> MS_WHITE
safe = ensure_contrast(MS_WHITE, MS_WHITE)  # -> MS_DARK_BLUE
```

---

## Low-Level Helpers

### `set_slide_bg(slide, color)`
Set solid background color on a slide.

### `add_ms_logo(slide, left=None, top=None, width=Inches(1.4))`
Add Microsoft logo watermark. Default position: bottom-right.

### `add_rect(slide, left, top, width, height, color, line_color=None) -> shape`
Add a simple filled rectangle.

### `add_bottom_bar(slide, page_num=None, total=None)`
Reserved for future use. Currently a no-op -- page numbers are intentionally omitted to keep slides clean.

### `add_speaker_notes(slide, text)`
Set speaker notes on a slide.

### `add_gradient_fill(shape, color_start, color_end, angle_deg=90)`
Apply a linear gradient fill to any shape. Angle: 0=L-to-R, 90=top-to-bottom, 135=diagonal.

### `add_top_accent_bar(slide, color=MS_BLUE, height=Inches(0.07)) -> shape`
Add a colored accent bar at the very top of a slide. Not used on standard slides (title underline is the accent).

### `add_gradient_fill_3(shape, color_start, color_mid, color_end, angle_deg=90)`
Apply a three-stop linear gradient for richer color transitions.
```python
add_gradient_fill_3(card, MS_BLUE, MS_BLUE_DARKER, MS_DARK_BLUE)
```

### `add_shadow(shape, blur_pt=6, offset_pt=3, opacity=0.18, color="000000") -> shape`
Add a Fluent Design drop shadow. Presets: Paper/Subtle/Medium/Strong/Deep.

---

## Text Helpers

### `add_textbox(slide, text, left, top, width, height, font_size=16, color=MS_TEXT, bold=False, alignment=PP_ALIGN.LEFT, font_name=FONT_FAMILY, italic=False, shrink_to_fit=False, v_align=None) -> shape`
Add a single-style text box. Most common function for standalone text.

- `shrink_to_fit=True`: PowerPoint auto-shrinks text to prevent overflow.
- `v_align`: `'top'` | `'middle'` | `'bottom'` - controls vertical text anchoring.

```python
add_textbox(slide, "Long text...", x, y, w, h,
            font_size=14, shrink_to_fit=True, v_align='middle')
```

### `add_bullet_list(slide, items, left, top, width, height=None, font_size=14, color=MS_TEXT, spacing=Pt(8), bullet_char="\u2022", bullet_color=None) -> ElementBox`
Native PowerPoint bullet list. Uses real `a:buChar` bullets (editable in PPT UI).
`height=None` auto-sizes to content (recommended). Pass explicit `Inches()` to force fixed height.
Items can be:
- `str`: plain text bullet
- `(bold_prefix, rest_text)`: mixed bold/normal
- `(text, {"level": 1})`: nested bullet (level 0-8)
- `(bold_prefix, rest_text, {"level": 1})`: bold prefix + nested

```python
add_bullet_list(slide, [
    "First item",
    ("Bold:", " rest text"),
    ("Nested item", {"level": 1}),
], CONTENT_LEFT, CONTENT_TOP, Inches(5))
```

### `add_numbered_list(slide, items, left, top, width, height=None, font_size=14, color=MS_TEXT, spacing=Pt(8), scheme='arabicPeriod', number_color=None) -> ElementBox`
Native PowerPoint auto-numbered list (1. 2. 3.). Numbers auto-renumber when items are added/removed.
`height=None` auto-sizes to content (recommended). Pass explicit `Inches()` to force fixed height.
`scheme`: `'arabicPeriod'` (1. 2. 3.), `'arabicParenR'` (1) 2) 3)), `'alphaLcPeriod'` (a. b. c.).

### `add_gradient_textbox(slide, text, left, top, width, height, color_start, color_end, angle_deg=0, font_size=16, bold=False, alignment=PP_ALIGN.LEFT, font_name=FONT_FAMILY, italic=False) -> shape`
Text with native gradient fill on characters. Premium look for headings.

### `add_rich_text(slide, parts, left, top, width, height, alignment=PP_ALIGN.LEFT) -> shape`
Add text with mixed formatting in a single textbox.
`parts = [(text, {font_size, color, bold, italic, font_name}), ...]`

---

## Shape Helpers

### `add_icon_circle(slide, left, top, size, color, text="", text_color=None) -> shape`
Filled circle with optional centered text. Text embedded in shape.
`text_color` auto-detected via `auto_text_color()` when None.

### `add_rounded_card(slide, left, top, width, height, fill=MS_WHITE, border=None, corner_radius=0.05) -> shape`
Rounded rectangle card. `corner_radius`: 0.0=sharp, 0.5=pill.

### `add_elevated_card(slide, left, top, width, height, fill=MS_WHITE, border=None, corner_radius=0.05, shadow="medium") -> shape`
Rounded card with drop shadow.
`shadow`: `"paper"` | `"subtle"` | `"medium"` | `"strong"` | `"deep"` | `None`.

### `add_gradient_card(slide, left, top, width, height, color_start, color_end, angle_deg=90, corner_radius=0.05, shadow="subtle") -> shape`
Rounded card with gradient fill + shadow.

### `add_arrow_right(slide, left, top, width=Inches(0.5), height=Inches(0.4), color=MS_BLUE) -> shape`
Right-pointing chevron arrow.

### `add_arrow_down(slide, left, top, width=Inches(0.4), height=Inches(0.5), color=MS_BLUE) -> shape`
Downward-pointing chevron arrow. Rotated 90 degrees from CHEVRON shape.

### `add_arrow_up(slide, left, top, width=Inches(0.4), height=Inches(0.5), color=MS_BLUE) -> shape`
Upward-pointing chevron arrow. Rotated 270 degrees from CHEVRON shape.

### `add_header_card(slide, left, top, width, height, header_text, color, header_height=Inches(0.5)) -> (header_shape, body_shape)`
Card with colored header banner and white body. **Auto-grouped** into one unit.

### `add_badge(slide, text, left, top, bg_color=MS_BLUE, text_color=MS_WHITE, font_size=9, width=None, height=Inches(0.28)) -> shape`
Pill-shaped status badge. Text embedded in shape. Contrast auto-checked.
```python
add_badge(slide, "GA", x, y, bg_color=MS_GREEN)
add_badge(slide, "Preview", x, y, bg_color=MS_ORANGE)
```

### `add_divider_line(slide, left, top, width, color=MS_MID_GRAY, thickness=Pt(1)) -> shape`
Subtle horizontal divider.

### `add_progress_bar(slide, left, top, width, height=Inches(0.18), progress=0.7, bar_color=MS_BLUE, track_color=MS_LIGHT_GRAY, label="", show_pct=True) -> ElementBox`
Horizontal progress/completion bar.
Returns `ElementBox` for vertical chaining.
`progress`: 0.0 to 1.0 (percentage complete).
```python
add_progress_bar(slide, x, y, Inches(4), progress=0.85, label="Adoption")
```

### `add_checklist(slide, items, left, top, width, height=None, font_size=13, check_color=MS_GREEN, spacing=Pt(10)) -> ElementBox`
Checklist with native bullet characters (green checkmarks / gray circles).
Uses `a:buChar` so glyphs are real bullets, not text prefixes.
`items = [str]` or `[(str, bool)]`.

---

## Composite Content Elements

These build complete visual components. Most embed text in shapes.

### `add_callout_box(slide, text, left, top, width, height=None, bg=MS_CALLOUT_BG, accent=MS_BLUE, font_size=13) -> ElementBox`
Callout with left accent bar. Text embedded in card. `height=None` auto-sizes.
**Auto-grouped** (card + accent bar). Includes subtle paper shadow.
Returns `ElementBox` for vertical chaining.

### `add_warning_box(slide, text, left, top, width, height=None) -> ElementBox`
Orange warning callout. **Auto-grouped**.

### `add_code_block(slide, code, left, top, width, height=None, language="") -> ElementBox`
Dark-themed code block with rounded corners and blue left border.
**Auto-grouped** (background + accent + optional language label).
`height`: `None` = auto-size to content (recommended). Pass explicit `Inches()` to force fixed height.
`language`: optional label (e.g. `'Python'`, `'YAML'`) shown in top-right corner.
```python
eb = add_code_block(slide, 'kubectl get pods', x, y, w, language='Shell')
next_top = eb.top + eb.height + Inches(0.15)  # chain vertically
```

### `add_styled_table(slide, data, left, top, width, col_widths=None, header_color=MS_DARK_BLUE, font_size=12) -> table_shape`
Professional table with dark header and alternating rows.

### `add_metric_card(slide, metric, label, left, top, width=Inches(3.5), height=Inches(2.5), color=MS_BLUE, sublabel="", trend="", trend_positive=True) -> ElementBox`
Big-number metric card with all text embedded in shape. Scales proportionally.
**Auto-grouped** (card + top accent bar).
Optional `trend` adds colored arrow (replaces old `add_kpi_card`).
```python
add_metric_card(slide, "98.5%", "Uptime SLA", left, top,
                trend="+0.3%", trend_positive=True)
```

### `add_stats_row(slide, stats, left=CONTENT_LEFT, top=Inches(1.8), width=None, card_h=Inches(1.6), gap=Inches(0.25)) -> ElementBox`
Horizontal row of stat cards with text embedded in shapes.
`stats = [(value, label), ...]` or `[(value, label, color), ...]`.

### `add_numbered_items(slide, items, left, top, width, item_height=Inches(1.1), colors=None) -> ElementBox`
Striped items with numbered circles. Offsets scale with item_height.
`items = [(title, description), ...]`

### `add_card_grid(slide, cards, left, top, cols=2, card_w=Inches(5.3), card_h=Inches(2.3), gap_x=Inches(0.35), gap_y=Inches(0.35)) -> ElementBox`
Grid of cards. Each card **auto-grouped** (5 shapes per card into one unit).
Offsets scale with card_h. Default `card_w=5.3"` fits 2 cols within `CONTENT_WIDTH`.
`cards = [(color, title, desc), ...]`

### `add_pillar_cards(slide, pillars, left=CONTENT_LEFT, top=CONTENT_TOP, height=Inches(5.2), min_gap=Inches(0.15)) -> ElementBox`
Vertical pillar cards, proportionally laid out. `pillars = [(color, num, title, desc), ...]`

### `add_feature_grid(slide, features, left=CONTENT_LEFT, top=CONTENT_TOP, cols=3, card_w=None, card_h=Inches(1.8), gap=Inches(0.2)) -> ElementBox`
Grid of numbered feature cards. Offsets scale with card_h.
`features = [(title, desc), ...]` or `[(title, desc, color), ...]`

### `add_colored_columns(slide, columns, left=CONTENT_LEFT, top=CONTENT_TOP, width=None, gap=Inches(0.3), title_font_size=TEXT_H3, body_font_size=TEXT_BODY_SM, bullet_symbol="\u00B7 ", gradient_titles=True, max_height=None) -> ElementBox`
Side-by-side columns with gradient title text and bullets.
```python
add_colored_columns(slide, [
    ("Scaling", ["Planning adoption", "Setting R&R"], MS_BLUE),
    ("Strong IP", ["Playbook", "Workshops"], MS_BLUE_DARKER),
])
```

### `add_comparison_columns(slide, col_left, col_right, left=CONTENT_LEFT, top=CONTENT_TOP, width=None, height=Inches(5.0), left_title="Before", right_title="After", left_color=MS_MID_GRAY, right_color=MS_BLUE) -> ElementBox`
Before/After comparison with VS divider.

### `add_layered_architecture(slide, layers, left=CONTENT_LEFT, top=Inches(1.5), width=None, layer_h=Inches(0.9), gap=Inches(0.08)) -> ElementBox`
Stacked architecture layer bars. Text embedded with auto contrast.
`layers = [(label, color), ...]`

### `add_process_flow(slide, steps, left=CONTENT_LEFT, top=Inches(2.0), box_w=Inches(2.5), box_h=Inches(1.4), arrow_w=Inches(0.6), colors=None, annotations=None) -> ElementBox`
Horizontal flow with boxes and chevron arrows. Text embedded in boxes.
`steps = ["Step1", "Step2", ...]`
`annotations`: optional list of `(step_index, text)` for bullets below a step.

### `add_quote_block(slide, quote, attribution="", left=CONTENT_LEFT, top=Inches(2.0), width=Inches(10), accent_color=MS_BLUE) -> ElementBox`
Large quotation block with left accent bar and attribution.
Professional style for testimonials, key statements, or expert opinions.
Returns `ElementBox` for vertical chaining.
```python
eb = add_quote_block(slide, "Copilot reduced onboarding by 55%.",
    "- VP Engineering, Contoso Ltd")
next_top = eb.top + eb.height + Inches(0.2)
```

### `add_swot_grid(slide, strengths, weaknesses, opportunities, threats, left=CONTENT_LEFT, top=CONTENT_TOP, width=None, height=Inches(5.0)) -> ElementBox`
SWOT analysis 2x2 grid. Each quadrant is a colored card with header and bullets.
```python
add_swot_grid(slide,
    ["Strong brand", "Market leader"],
    ["High costs", "Legacy systems"],
    ["Cloud migration", "AI adoption"],
    ["New competitors", "Regulation"])
```

### `add_maturity_model(slide, levels, current_level=None, left=CONTENT_LEFT, top=Inches(2.0), width=None, height=Inches(4.0)) -> ElementBox`
Staircase maturity model visualization.
`levels = [(label, description), ...]` ordered lowest to highest.
`current_level`: 0-based index of highlighted level.

### `add_roadmap(slide, phases, left=CONTENT_LEFT, top=Inches(2.0), width=None, phase_h=Inches(1.2)) -> ElementBox`
Horizontal phased roadmap with milestone markers and arrow connectors.
`phases = [(phase_label, items_list, color), ...]`
More detailed than `add_timeline` -- each phase has room for multiple items.

### `add_pricing_table(slide, tiers, left=CONTENT_LEFT, top=Inches(1.3), width=None, height=Inches(5.5), highlight_index=None) -> ElementBox`
Pricing/comparison table with tiered columns.
`tiers = [(name, price, features_list, color), ...]`
`highlight_index`: index of the recommended tier (elevated + badge).

### `add_kpi_card(slide, value, label, trend="", trend_positive=True, left=CONTENT_LEFT, top=Inches(2.0), width=Inches(3.5), height=Inches(2.5), color=MS_BLUE) -> ElementBox`
**Deprecated alias** for `add_metric_card`. Prefer `add_metric_card` directly.

---

## Microsoft-Style Components

### `add_title_icon_badge(slide, left, top, symbol="\u2693", size=Inches(0.55), bg_color=MS_BLUE, text_color=MS_WHITE) -> shape`
Circular icon badge next to a slide title. Common symbols: \u2699 Gear, \u2605 Star, \u26A1 Lightning, \u2714 Checkmark.

### `add_blue_speech_panel(slide, text, left, top, width, height, bg_color=MS_BLUE, text_color=MS_WHITE, font_size=13, accent_bar=True) -> ElementBox`
Blue panel with white text embedded in shape. Contrast auto-checked. **Auto-grouped** when accent bar is present.
Returns `ElementBox` for vertical chaining.

### `add_header_card_with_bullets(slide, header_text, bullets, left, top, width, height, header_color=MS_BLUE, header_height=Inches(0.5), font_size=11, bullet_symbol="\u2022") -> (header_shape, body_shape, textbox)`
Card with colored header banner and **native-bulleted** body. Uses real PowerPoint bullets.

### `add_timeline(slide, phases, left=CONTENT_LEFT, top=Inches(1.3), box_height=Inches(0.55), desc_height=Inches(1.8), available_width=None, bar_color=MS_BLUE) -> ElementBox`
Horizontal timeline. Milestone text embedded in boxes.
`phases = [(label, week_label, desc), ...]`

### `add_activity_bars(slide, activities, left=CONTENT_LEFT, top=Inches(5.8), width=None, bar_height=Inches(0.32), gap=Inches(0.05), colors=None) -> ElementBox`
Horizontal workstream bars. Text embedded with auto contrast.

### `add_process_flow_grouped(slide, steps, group_range=None, group_label="", left=CONTENT_LEFT, top=Inches(2.0), box_w=Inches(2.5), box_h=Inches(1.4), arrow_w=Inches(0.6), colors=None, annotations=None) -> (ElementBox, group_shape_or_None)`
Process flow with optional dashed grouping border around a subset of steps.
`group_range`: `(start_idx, end_idx)` inclusive indices.

---

## Slide Templates

### `create_standard_slide(prs, title, page_num=None, total=None, notes="", title_font_size=28) -> slide`
Standard content slide. Title uses **Segoe UI Semibold**. Content starts at `CONTENT_TOP` (1.2").
`title_font_size`: reduce for longer titles to avoid overflow.

### `create_section_divider(prs, title, subtitle="", notes="") -> slide`
Dark navy section divider. Title uses **Segoe UI Light** with letter spacing.

### `create_lead_slide(prs, title, subtitle="", meta="", notes="", level="", use_bg_image=True) -> slide`
Title/lead slide. Title uses **Segoe UI Light** with letter spacing. `level`: `"L100"` | `"L200"` | `"L300"` | `"L400"`.
```python
create_lead_slide(prs, "GitHub Copilot Deep Dive",
    subtitle="Architecture Patterns",
    meta="L300 | March 2026", level="L300")
```

### `create_closing_slide(prs, title="Key Takeaways", takeaways=None, cta_title="", cta_url="", cta_items=None, page_num=None, total=None, notes="", title_font_size=30, title_height=None) -> slide`
Split closing: blue left (takeaways) + white right (CTA/questions).
`title_font_size`: reduce to 22-24pt for longer titles.

### `create_two_tone_slide(prs, title, left_color=MS_DARK_BLUE, right_color=MS_WHITE, split_inches=5.0, page_num=None, total=None, notes="") -> (slide, left_width, right_left, right_width)`
Split-background slide. Returns layout coordinates.

### `add_agenda_list(slide, items, left=CONTENT_LEFT, top=Inches(1.5), width=None, highlight_index=None) -> ElementBox`
Numbered agenda/table-of-contents list. `highlight_index` highlights the active item.

### `add_icon_row(slide, items, left=CONTENT_LEFT, top=Inches(2.5), width=None, icon_size=Inches(0.6)) -> ElementBox`
Horizontal row of icon circles with labels below.
`items = [(symbol, label), ...]` or `[(symbol, label, color), ...]`

### `create_agenda_slide(prs, title, items, highlight_index=None, page_num=None, total=None, notes="") -> slide`
Standard slide + numbered agenda list.

### `create_impact_slide(prs, headline, subtext="", stats=None, page_num=None, total=None, notes="") -> slide`
High-impact statement on gradient background. Headline uses **Segoe UI Light** with wide letter spacing.

### `create_gradient_slide(prs, title, color_start=MS_BLUE, color_end=MS_DARK_BLUE, angle_deg=135, page_num=None, total=None, notes="") -> slide`
Full-bleed gradient background. Use white text.

---

## New Primitives

### `add_image_card(slide, image_path, left, top, width, height, caption="", border_color=None, corner_radius=0.05, shadow="subtle") -> shape`
Rounded card containing an image with optional caption. **Auto-grouped**.
Shows a placeholder if the image file doesn't exist.
```python
add_image_card(slide, "screenshot.png", x, y, Inches(4), Inches(3),
               caption="Architecture Diagram")
```

### `add_hyperlink(run, url) -> run`
Make a text run clickable (native PowerPoint hyperlink).
Styles the run as blue + underline.
```python
tb = add_textbox(slide, "Visit docs", x, y, w, h, color=MS_BLUE)
add_hyperlink(tb.text_frame.paragraphs[0].runs[0],
              "https://learn.microsoft.com")
```

### `set_shape_transparency(shape, alpha_pct) -> shape`
Set fill transparency. `alpha_pct`: 0 = opaque, 100 = fully transparent.
```python
overlay = add_rect(slide, 0, 0, SLIDE_WIDTH, SLIDE_HEIGHT, MS_DARK_BLUE)
set_shape_transparency(overlay, 40)  # 40% transparent
```

### `add_bar_chart(slide, data, left, top, width, height, chart_title="", colors=None) -> chart_shape`
Styled bar chart with Microsoft brand colors.
```python
add_bar_chart(slide, {
    "categories": ["Q1", "Q2", "Q3", "Q4"],
    "series": [("Revenue", [100, 120, 140, 160])],
}, x, y, Inches(8), Inches(4.5), chart_title="Quarterly Results")
```

### `add_donut_chart(slide, data, left, top, width, height, chart_title="", colors=None, hole_size=50) -> chart_shape`
Styled donut/pie chart. `hole_size=0` for full pie.
```python
add_donut_chart(slide, {
    "categories": ["Desktop", "Mobile", "Tablet"],
    "values": [60, 30, 10],
}, x, y, Inches(5), Inches(4), chart_title="Platform Mix")
```

### `add_connector_line(slide, start_shape, end_shape, color=MS_BLUE, width_pt=1.5, dash=False) -> connector`
Native PowerPoint connector between two shapes. Reflows when shapes are moved.
Alternative to chevron arrows for editable flow diagrams.

---

## Layout & Grouping Helpers

### `MIN_CARD_WIDTH = Inches(1.5)`
Minimum readable width for auto-computed card widths in grids.

### `estimate_text_height(text, font_size_pt, width_inches, padding_inches=0.22, line_spacing_factor=1.45, min_lines=1) -> Inches`
Estimate height for text. Wider character heuristic (0.58), handles long tokens, 10% safety margin.

### `auto_height_for_items(items, font_size, width_inches, spacing_pt=8, padding_inches=0.2) -> Inches`
Calculate minimum container height for a list of text items.
Uses `estimate_text_height` per item plus inter-item spacing.

### `remaining_height(from_top, bottom=CONTENT_BOTTOM) -> int`
Return available height (EMU) from `from_top` to the content bottom boundary.
Use to check whether the next element fits before placing it.
```python
eb = add_bullet_list(slide, items, left, top, width)
avail = remaining_height(eb.top + eb.height)
# Compare avail with the next element's expected height
```

### `group_shapes(slide, shapes_list) -> GroupShape`
Group shapes into one selectable/movable unit. Ungroupable in PowerPoint.
```python
card = add_rounded_card(slide, x, y, w, h)
icon = add_icon_circle(slide, ix, iy, size, color, "1")
group = group_shapes(slide, [card, icon])
```

### `ElementBox = namedtuple("ElementBox", ["shape", "left", "top", "width", "height"])`
Consistent return type for position chaining.

---

## Utilities

### `save_presentation(prs, output_path) -> path`
Save .pptx and print summary.

### `download_image(url, filepath) -> bool`
Download image from URL.

### `parse_slide_notes(notes_path) -> [str]`
Extract speaker notes from slide markdown by index (0-based).

---

## Function Decision Guide

| I want to show... | Use this |
|---|---|
| A single big number/metric | `add_metric_card()` |
| A row of 2-5 stats | `add_stats_row()` |
| Numbered steps/items (visual circles) | `add_numbered_items()` |
| Auto-numbered list (1. 2. 3.) | `add_numbered_list()` |
| Bullet list | `add_bullet_list()` |
| Checklist (checked/unchecked) | `add_checklist()` |
| Cards in a 2-col grid | `add_card_grid()` |
| Cards in a 3-col grid | `add_feature_grid()` |
| Vertical pillars | `add_pillar_cards()` |
| Side-by-side columns with bullets | `add_colored_columns()` |
| Before/After comparison | `add_comparison_columns()` |
| Architecture layers | `add_layered_architecture()` |
| Process flow with arrows | `add_process_flow()` |
| Process flow with grouping | `add_process_flow_grouped()` |
| Process flow with connectors | `add_connector_line()` |
| Timeline with milestones | `add_timeline()` |
| Phased roadmap with details | `add_roadmap()` |
| Agenda / table of contents | `add_agenda_list()` |
| A prominent callout | `add_callout_box()` |
| A warning notice | `add_warning_box()` |
| A key statement on blue bg | `add_blue_speech_panel()` |
| A quote / testimonial | `add_quote_block()` |
| SWOT analysis grid | `add_swot_grid()` |
| Maturity model (staircase) | `add_maturity_model()` |
| Pricing / tier comparison | `add_pricing_table()` |
| Progress / completion bar | `add_progress_bar()` |
| Icon row with labels | `add_icon_row()` |
| Code/CLI/YAML block | `add_code_block()` |
| Data table | `add_styled_table()` |
| Status badge (GA/Preview) | `add_badge()` |
| Title icon badge | `add_title_icon_badge()` |
| Image with caption | `add_image_card()` |
| Bar/column chart | `add_bar_chart()` |
| Donut/pie chart | `add_donut_chart()` |
| Clickable link | `add_hyperlink()` |
| Semi-transparent overlay | `set_shape_transparency()` |
