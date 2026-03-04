# pptx_utils API Reference

Quick reference for all functions in `pptx_utils.py`. Functions are grouped by
usage frequency: **Core** (use often), **Composites** (pre-built layouts), and
**Advanced** (rarely needed directly).

> **Key design principles (v2):**
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
| `MS_PURPLE` | #881C98 | AI/premium features |
| `MS_RED` | #D13438 | Error, critical |
| `MS_BLUE_DARKER` | #006CBE | Darker blue variant |
| `MS_CODE_BG` | #24292F | Code block background |
| `MS_CODE_TEXT` | #EAF0F7 | Code block text |
| `MS_ACCENT_LIGHT` | #CCE4FF | Light text on blue backgrounds |
| `MS_BLUE_LIGHT_BG` | #DEECF9 | Info / highlight background |
| `MS_NAVY_LIGHT` | #2E4A6E | Subtle dark layering |
| `MS_SUCCESS_BG` | #DFF6DD | Success / positive background |
| `MS_WARNING_BG` | #FFF4E5 | Warning background |
| `MS_ERROR_BG` | #FDE7E9 | Error / negative background |
| `MS_YELLOW` | #FFB900 | Accent yellow |
| `MS_TEAL` | #038387 | Teal accent |

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
| `FONT_MONO` | "Cascadia Code" | Monospace font for code |

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
Add page number at the bottom-left.

### `add_speaker_notes(slide, text)`
Set speaker notes on a slide.

### `add_gradient_fill(shape, color_start, color_end, angle_deg=90)`
Apply a linear gradient fill to any shape. Angle: 0=L-to-R, 90=top-to-bottom, 135=diagonal.

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

### `add_bullet_list(slide, items, left, top, width, height=Inches(5), font_size=14, color=MS_TEXT, spacing=Pt(8)) -> shape`
Bullet list. Items can be strings or tuples `(bold_prefix, rest_text)`.

### `add_gradient_textbox(slide, text, left, top, width, height, color_start, color_end, ...) -> shape`
Text with native gradient fill on characters. Premium look for headings.

---

## Shape Helpers

### `add_icon_circle(slide, left, top, size, color, text="", text_color=None) -> shape`
Filled circle with optional centered text. Text embedded in shape.
`text_color` auto-detected via `auto_text_color()` when None.

### `add_rounded_card(slide, left, top, width, height, fill=MS_WHITE, border=None, corner_radius=0.05) -> shape`
Rounded rectangle card. `corner_radius`: 0.0=sharp, 0.5=pill.

### `add_elevated_card(slide, ..., shadow="medium") -> shape`
Rounded card with drop shadow.

### `add_gradient_card(slide, left, top, width, height, color_start, color_end, ...) -> shape`
Rounded card with gradient fill + shadow.

### `add_arrow_right(slide, left, top, width=Inches(0.5), height=Inches(0.4), color=MS_BLUE) -> shape`
Right-pointing chevron arrow.

### `add_arrow_down(slide, left, top, ...) -> shape`
Downward-pointing chevron arrow.

### `add_header_card(slide, left, top, width, height, header_text, color, header_height=Inches(0.5)) -> (header_shape, body_shape)`
Card with colored header banner and white body.

### `add_badge(slide, text, left, top, bg_color=MS_BLUE, text_color=MS_WHITE, font_size=9, width=None, height=Inches(0.28)) -> shape`
Pill-shaped status badge. Text embedded in shape. Contrast auto-checked.
```python
add_badge(slide, "GA", x, y, bg_color=MS_GREEN)
add_badge(slide, "Preview", x, y, bg_color=MS_ORANGE)
```

### `add_divider_line(slide, left, top, width, ...) -> shape`
Subtle horizontal divider.

### `add_checklist(slide, items, left, top, width, ...) -> shape`
Checklist with green checkmarks. `items = [str]` or `[(str, bool)]`.

---

## Composite Content Elements

These build complete visual components. Most embed text in shapes.

### `add_callout_box(slide, text, left, top, width, height=None, bg=MS_CALLOUT_BG, accent=MS_BLUE, font_size=13) -> height`
Callout with left accent bar. Text embedded in card. `height=None` auto-sizes.
Returns actual height for vertical chaining.

### `add_warning_box(slide, text, left, top, width, height=None) -> height`
Orange warning callout.

### `add_code_block(slide, code, left, top, width, height) -> shape`
Dark-themed code block. Text embedded in background rectangle (single unit).

### `add_styled_table(slide, data, left, top, width, col_widths=None, header_color=MS_DARK_BLUE, font_size=12) -> table_shape`
Professional table with dark header and alternating rows.

### `add_metric_card(slide, metric, label, x, y, w=Inches(3.5), h=Inches(2.5), color=MS_BLUE, sublabel="", trend="", trend_positive=True) -> shape`
Big-number metric card with all text embedded in shape. Scales proportionally.
Optional `trend` adds colored arrow (replaces old `add_kpi_card`).
```python
add_metric_card(slide, "98.5%", "Uptime SLA", x, y,
                trend="+0.3%", trend_positive=True)
```

### `add_stats_row(slide, stats, left=CONTENT_LEFT, top=Inches(1.8), width=None, card_h=Inches(1.6), gap=Inches(0.25)) -> [shapes]`
Horizontal row of stat cards with text embedded in shapes.
`stats = [(value, label), ...]` or `[(value, label, color), ...]`.

### `add_numbered_items(slide, items, left, top, width, item_height=Inches(1.1), colors=None)`
Striped items with numbered circles. Offsets scale with item_height.
`items = [(title, description), ...]`

### `add_card_grid(slide, cards, left, top, cols=2, card_w=Inches(5.5), card_h=Inches(2.3), ...)`
Grid of cards. Offsets scale with card_h. `cards = [(color, title, desc), ...]`

### `add_pillar_cards(slide, pillars, left=CONTENT_LEFT, top=CONTENT_TOP, height=Inches(5.2))`
Vertical pillar cards, proportionally laid out. `pillars = [(color, num, title, desc), ...]`

### `add_feature_grid(slide, features, left=CONTENT_LEFT, top=CONTENT_TOP, cols=3, card_w=None, card_h=Inches(1.8), gap=Inches(0.2))`
Grid of numbered feature cards. Offsets scale with card_h.
`features = [(title, desc), ...]` or `[(title, desc, color), ...]`

### `add_colored_columns(slide, columns, left=CONTENT_LEFT, top=CONTENT_TOP, ...)`
Side-by-side columns with gradient title text and bullets.
```python
add_colored_columns(slide, [
    ("Scaling", ["Planning adoption", "Setting R&R"], MS_BLUE),
    ("Strong IP", ["Playbook", "Workshops"], MS_GREEN),
])
```

### `add_comparison_columns(slide, col_left, col_right, ..., left_title="Before", right_title="After")`
Before/After comparison with VS divider.

### `add_layered_architecture(slide, layers, left=CONTENT_LEFT, top=Inches(1.5), ...)`
Stacked architecture layer bars. Text embedded with auto contrast.
`layers = [(label, color), ...]`

### `add_process_flow(slide, steps, left=CONTENT_LEFT, top=Inches(2.0), ...) -> [shapes]`
Horizontal flow with boxes and chevron arrows. Text embedded in boxes.
`steps = ["Step1", "Step2", ...]`

---

## Microsoft-Style Components

### `add_blue_speech_panel(slide, text, left, top, width, height, ...) -> shape`
Blue panel with white text embedded in shape. Contrast auto-checked.

### `add_header_card_with_bullets(slide, header_text, bullets, left, top, width, height, ...) -> (header_shape, body_shape, textbox)`
Card with colored header banner and bullet list body.

### `add_timeline(slide, phases, left=CONTENT_LEFT, ...) -> [shapes]`
Horizontal timeline. Milestone text embedded in boxes.
`phases = [(label, week_label, desc), ...]`

### `add_activity_bars(slide, activities, left=CONTENT_LEFT, ...) -> [shapes]`
Horizontal workstream bars. Text embedded with auto contrast.

---

## Slide Templates

### `create_standard_slide(prs, title, page_num=None, total=None, notes="") -> slide`
Standard content slide. Content starts at `CONTENT_TOP` (1.2").

### `create_section_divider(prs, title, subtitle="", notes="") -> slide`
Dark navy section divider.

### `create_lead_slide(prs, title, subtitle="", meta="", notes="", level="", use_bg_image=True) -> slide`
Title/lead slide. `level`: `"L100"` | `"L200"` | `"L300"` | `"L400"`.
```python
create_lead_slide(prs, "GitHub Copilot Deep Dive",
    subtitle="Architecture Patterns",
    meta="L300 | March 2026", level="L300")
```

### `create_closing_slide(prs, ...) -> slide`
Split closing: blue left (takeaways) + white right (CTA/questions).

### `create_two_tone_slide(prs, title, ...) -> (slide, left_width, right_left, right_width)`
Split-background slide. Returns layout coordinates.

### `create_agenda_slide(prs, title, items, highlight_index=None, ...) -> slide`
Standard slide + numbered agenda list.

### `create_impact_slide(prs, headline, subtext="", stats=None, ...) -> slide`
High-impact statement on gradient background.

### `create_gradient_slide(prs, title, color_start=MS_BLUE, color_end=MS_DARK_BLUE, ...) -> slide`
Full-bleed gradient background. Use white text.

---

## Layout & Grouping Helpers

### `estimate_text_height(text, font_size_pt, width_inches, padding_inches=0.22, line_spacing_factor=1.45, min_lines=1) -> Inches`
Estimate height for text. Wider character heuristic (0.58), handles long tokens, 10% safety margin.

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
| Numbered steps/items | `add_numbered_items()` |
| Cards in a 2-col grid | `add_card_grid()` |
| Cards in a 3-col grid | `add_feature_grid()` |
| Vertical pillars | `add_pillar_cards()` |
| Side-by-side columns with bullets | `add_colored_columns()` |
| Before/After comparison | `add_comparison_columns()` |
| Architecture layers | `add_layered_architecture()` |
| Process flow with arrows | `add_process_flow()` |
| Timeline with milestones | `add_timeline()` |
| A prominent callout | `add_callout_box()` |
| A warning notice | `add_warning_box()` |
| A key statement on blue bg | `add_blue_speech_panel()` |
| Code/CLI/YAML block | `add_code_block()` |
| Data table | `add_styled_table()` |
| Status badge (GA/Preview) | `add_badge()` |
