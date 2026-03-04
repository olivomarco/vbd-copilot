# pptx_utils API Reference

Quick reference for all functions in `pptx_utils.py`. Always read the actual source file for the latest signatures.

## Initialization

### `create_presentation() -> Presentation`
Creates a new 16:9 presentation. Logo and lead background are loaded directly from `assets/`.
**Always call this first.**

### `new_blank_slide(prs) -> slide`
Adds a blank slide (layout index 6) to the presentation.

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

## Low-Level Helpers

### `set_slide_bg(slide, color)`
Set solid background color on a slide.

### `add_ms_logo(slide, left=None, top=None, width=Inches(1.4))`
Add Microsoft logo watermark. Default position: bottom-right.

### `add_rect(slide, left, top, width, height, color, line_color=None) -> shape`
Add a simple filled rectangle.

### `add_top_accent_bar(slide, color=MS_BLUE, height=Inches(0.07))`
Add a colored accent bar at the top of a slide. **Not used on standard slides** -- reserve for custom layouts.

### `add_bottom_bar(slide, page_num=None, total=None)`
Add page number at the bottom-left.

### `add_speaker_notes(slide, text)`
Set speaker notes on a slide.

### `add_gradient_fill(shape, color_start, color_end, angle_deg=90)`
Apply a linear gradient fill to any shape. Angle convention: 0=L-to-R, 90=top-to-bottom, 135=diagonal.
```python
bg = add_rect(slide, Inches(0), Inches(0), SLIDE_WIDTH, SLIDE_HEIGHT, MS_BLUE)
add_gradient_fill(bg, MS_BLUE, MS_DARK_BLUE, angle_deg=135)
```

### `add_gradient_fill_3(shape, color_start, color_mid, color_end, angle_deg=90)`
Apply a three-stop gradient for richer transitions.

### `add_shadow(shape, blur_pt=6, offset_pt=3, opacity=0.18, color="000000") -> shape`
Add a Fluent Design drop shadow. Presets:
| Level | blur_pt | offset_pt | opacity | Use case |
|-------|---------|-----------|---------|----------|
| Paper | 2 | 1 | 0.08 | Barely visible |
| Subtle | 4 | 2 | 0.12 | Cards at rest |
| Medium | 6 | 3 | 0.18 | Default, elevated |
| Strong | 12 | 5 | 0.25 | Modal / hero |
| Deep | 20 | 8 | 0.30 | Floating panel |

---

## Text Helpers

### `add_textbox(slide, text, left, top, width, height, font_size=16, color=MS_TEXT, bold=False, alignment=PP_ALIGN.LEFT, font_name=FONT_FAMILY, italic=False) -> shape`
Add a single-style text box. Most common function.

### `add_rich_text(slide, parts, left, top, width, height, alignment=PP_ALIGN.LEFT) -> shape`
Add multi-formatted text. `parts = [(text, {font_size, color, bold, italic, font_name}), ...]`

### `add_bullet_list(slide, items, left, top, width, height=Inches(5), font_size=14, color=MS_TEXT, spacing=Pt(8)) -> shape`
Add bullet list. Items can be strings or tuples `(bold_prefix, rest_text)` for rich bullets.

### `add_gradient_textbox(slide, text, left, top, width, height, color_start, color_end, angle_deg=0, font_size=16, bold=False, alignment=PP_ALIGN.LEFT, font_name=FONT_FAMILY, italic=False) -> shape`
Add text with native PowerPoint gradient fill on the characters. Creates a premium look for headings.
```python
add_gradient_textbox(slide, "Key Insights", x, y, w, h,
                     MS_BLUE, MS_LIGHT_BLUE, font_size=28, bold=True)
```

---

## Shape Helpers

### `add_icon_circle(slide, left, top, size, color, text="", text_color=None) -> shape`
Add a filled circle with optional centered text (great for numbered icons).
`text_color` defaults to `MS_WHITE` on dark fills and `MS_DARK_BLUE` on light/white fills.
Pass explicitly when the auto-detect does not match (e.g., white circle on a blue card).
```python
add_icon_circle(slide, x, y, Inches(0.45), MS_WHITE, "1", text_color=MS_BLUE)
```

### `add_rounded_card(slide, left, top, width, height, fill=MS_WHITE, border=None, corner_radius=0.05) -> shape`
Add a rounded rectangle card. `corner_radius`: 0.0=sharp, 0.5=pill. Default 0.05.

### `add_elevated_card(slide, left, top, width, height, fill=MS_WHITE, border=None, corner_radius=0.05, shadow="medium") -> shape`
Rounded card with a drop shadow. Shadow preset: `"paper"` | `"subtle"` | `"medium"` | `"strong"` | `"deep"` | `None`.
**Use instead of `add_rounded_card` when the card needs visual depth.**

### `add_gradient_card(slide, left, top, width, height, color_start, color_end, angle_deg=90, corner_radius=0.05, shadow="subtle") -> shape`
Rounded card with gradient fill + shadow in one call.
```python
add_gradient_card(slide, x, y, w, h, MS_BLUE, MS_DARK_BLUE, angle_deg=135)
```

### `add_arrow_right(slide, left, top, width=Inches(0.5), height=Inches(0.4), color=MS_BLUE) -> shape`
Right-pointing chevron arrow. Use between horizontal flow cards.

### `add_arrow_down(slide, left, top, width=Inches(0.4), height=Inches(0.5), color=MS_BLUE) -> shape`
Downward-pointing chevron arrow for vertical flow diagrams.

### `add_arrow_up(slide, left, top, width=Inches(0.4), height=Inches(0.5), color=MS_BLUE) -> shape`
Upward-pointing chevron arrow.

### `add_header_card(slide, left, top, width, height, header_text, color, header_height=Inches(0.5)) -> (header_shape, body_shape)`
Rounded card with colored header banner and white body.

### `add_badge(slide, text, left, top, bg_color=MS_BLUE, text_color=MS_WHITE, font_size=9, width=None, height=Inches(0.28)) -> shape`
Pill-shaped status badge. Width auto-sizes to text when None.
```python
add_badge(slide, "GA",         x, y, bg_color=MS_GREEN)
add_badge(slide, "Preview",    x, y, bg_color=MS_ORANGE)
add_badge(slide, "New",        x, y, bg_color=MS_BLUE)
add_badge(slide, "Deprecated", x, y, bg_color=MS_RED)
```

### `add_divider_line(slide, left, top, width, color=MS_MID_GRAY, thickness=Pt(1)) -> shape`
Subtle horizontal divider line between content sections.

### `add_progress_bar(slide, left, top, width, height=Inches(0.18), progress=0.7, bar_color=MS_BLUE, track_color=MS_LIGHT_GRAY, label="", show_pct=True) -> shape`
Horizontal progress/completion bar with optional label and percentage.
```python
add_progress_bar(slide, x, y, Inches(4), progress=0.85, label="Adoption")
```

### `add_checklist(slide, items, left, top, width, height=Inches(5), font_size=13, check_color=MS_GREEN, spacing=Pt(10)) -> shape`
Checklist with green checkmarks. `items = [str]` for all checked, or `[(str, bool)]` for mixed.

---

## Composite Content Elements

### `add_callout_box(slide, text, left, top, width, height=None, bg=MS_CALLOUT_BG, accent=MS_BLUE, font_size=13) -> height`
Blue-bordered callout box with left accent bar. `height=None` auto-sizes to content.
Returns the actual height so callers can chain positions.

### `add_warning_box(slide, text, left, top, width, height=None) -> height`
Orange-themed warning callout box.

### `add_code_block(slide, code, left, top, width, height) -> shape`
Dark-themed code block with blue left accent bar, monospace font.

### `add_styled_table(slide, data, left, top, width, col_widths=None, header_color=MS_DARK_BLUE, font_size=12) -> table_shape`
Professional table with dark header row and alternating light/white rows.

### `add_metric_card(slide, metric, label, x, y, w=Inches(3.5), h=Inches(2.5), color=MS_BLUE, sublabel="")`
Big-number metric card with color-accented top border.

### `add_kpi_card(slide, value, label, trend="", trend_positive=True, x=CONTENT_LEFT, y=Inches(2.0), w=Inches(2.8), h=Inches(2.2), color=MS_BLUE) -> shape`
KPI card with value, label, and trend arrow (green up / red down).
```python
add_kpi_card(slide, "98.5%", "Uptime SLA", "+0.3%", True, x=Inches(1), y=Inches(2))
```

### `add_stats_row(slide, stats, left=CONTENT_LEFT, top=Inches(1.8), width=None, card_h=Inches(1.6), gap=Inches(0.25)) -> [shapes]`
Horizontal row of big-number stat cards. `stats = [(value, label), ...]` or `[(value, label, color), ...]`.

### `add_quote_block(slide, quote, attribution="", left=CONTENT_LEFT, top=Inches(2.0), width=Inches(10), accent_color=MS_BLUE) -> shape`
Professional quotation block with oversized quote mark, accent bar, and attribution.

### `add_numbered_items(slide, items, left, top, width, item_height=Inches(1.1), colors=None)`
Horizontal striped items with numbered circles. `items = [(title, description), ...]`

### `add_card_grid(slide, cards, left, top, cols=2, card_w=Inches(5.5), card_h=Inches(2.3), gap_x=Inches(0.35), gap_y=Inches(0.35))`
Grid of cards with color accent, number icon, title, description. `cards = [(color, title, desc), ...]`

### `add_pillar_cards(slide, pillars, left=CONTENT_LEFT, top=CONTENT_TOP, height=Inches(5.2))`
Vertical pillar cards evenly distributed. `pillars = [(color, num, title, desc), ...]`

### `add_feature_grid(slide, features, left=CONTENT_LEFT, top=CONTENT_TOP, cols=3, card_w=None, card_h=Inches(1.8), gap=Inches(0.2))`
Grid of numbered feature cards with subtle shadows. `features = [(title, desc), ...]` or `[(title, desc, color), ...]`.

### `add_colored_columns(slide, columns, left=CONTENT_LEFT, top=CONTENT_TOP, width=None, gap=Inches(0.3), title_font_size=TEXT_H3, body_font_size=TEXT_BODY_SM, bullet_symbol="\u00B7 ", gradient_titles=True)`
Side-by-side columns with colored bold titles (gradient text) and bullet lists. Lightweight -- no card background. Titles use native PowerPoint gradient text fill for a polished look. Pass a `(color_start, color_end)` tuple for explicit gradient control, or a single `RGBColor` for auto-lightened gradient.
```python
add_colored_columns(slide, [
    ("Scaling with the customer", ["Planning adoption", "Setting R&R"], MS_BLUE),
    ("Strong IP Developed", ["Playbook with guidance", "Workshops"], MS_GREEN),
    ("Align to outcomes", ["Metrics to goals", "Usage tracking"], MS_ORANGE),
    ("Unified approach", ["VAS offerings", "Adaptable packages"], MS_PURPLE),
])
```

### `add_comparison_columns(slide, col_left, col_right, left=CONTENT_LEFT, top=CONTENT_TOP, width=None, height=Inches(5.0), left_title="Before", right_title="After", left_color=MS_MID_GRAY, right_color=MS_BLUE)`
Side-by-side Before/After comparison with VS divider circle.

### `add_layered_architecture(slide, layers, left=CONTENT_LEFT, top=Inches(1.5), width=None, layer_h=Inches(0.9), gap=Inches(0.08))`
Stacked architecture layer bars. `layers = [(label, color), ...]` top-to-bottom.

### `add_agenda_list(slide, items, left=CONTENT_LEFT, top=Inches(1.5), width=None, highlight_index=None)`
Numbered agenda list. Active item highlighted with blue background.

### `add_icon_row(slide, items, left=CONTENT_LEFT, top=Inches(2.5), width=None, icon_size=Inches(0.6))`
Horizontal row of icon circles with labels. `items = [(symbol, label), ...]` or `[(symbol, label, color), ...]`.

### `add_pricing_table(slide, tiers, left=CONTENT_LEFT, top=Inches(1.3), width=None, height=Inches(5.5), highlight_index=None)`
Tiered pricing/comparison table. `tiers = [(name, price, features_list, color), ...]`. Featured tier gets elevation + "Recommended" badge.

### `add_swot_grid(slide, strengths, weaknesses, opportunities, threats, left=CONTENT_LEFT, top=CONTENT_TOP, width=None, height=Inches(5.0))`
2x2 SWOT analysis matrix with colored quadrants.

### `add_maturity_model(slide, levels, current_level=None, left=CONTENT_LEFT, top=Inches(2.0), width=None, height=Inches(4.0))`
Ascending staircase maturity visualization. `levels = [(label, desc), ...]`. Current level highlighted.

### `add_roadmap(slide, phases, left=CONTENT_LEFT, top=Inches(2.0), width=None, phase_h=Inches(1.2))`
Horizontal phased roadmap with bullet items per phase. `phases = [(label, items_list, color), ...]`.

---

## Microsoft-Style Components

### `add_title_icon_badge(slide, left, top, symbol="\u2693", size=Inches(0.55), bg_color=MS_BLUE, text_color=MS_WHITE) -> shape`
Circular icon badge for slide titles. Uses Unicode symbols rendered in Segoe UI.

### `add_blue_speech_panel(slide, text, left, top, width, height, bg_color=MS_BLUE, text_color=MS_WHITE, font_size=13, accent_bar=True) -> shape`
Solid blue panel with white text. High-contrast branded panel for key statements.

### `add_header_card_with_bullets(slide, header_text, bullets, left, top, width, height, header_color=MS_BLUE, header_height=Inches(0.5), font_size=11, bullet_symbol="\u2022 ") -> (header_shape, body_shape, textbox)`
Card with colored header banner and built-in bullet list body.

### `add_timeline(slide, phases, left=CONTENT_LEFT, top=Inches(1.3), box_height=Inches(0.55), desc_height=Inches(1.8), available_width=None, bar_color=MS_BLUE) -> [shapes]`
Horizontal timeline with milestone boxes, week labels, and descriptions. `phases = [(label, week_label, desc), ...]`.

### `add_activity_bars(slide, activities, left=CONTENT_LEFT, top=Inches(5.8), width=None, bar_height=Inches(0.32), gap=Inches(0.05), colors=None) -> [shapes]`
Horizontal activity/workstream bars at slide bottom. `activities = ["Surveys", "Comms", ...]`.

### `add_process_flow(slide, steps, left=CONTENT_LEFT, top=Inches(2.0), box_w=Inches(2.5), box_h=Inches(1.4), arrow_w=Inches(0.6), colors=None, annotations=None) -> [shapes]`
Horizontal process flow with boxes and chevron arrows. `steps = ["Step1", "Step2", ...]`.

### `add_process_flow_grouped(slide, steps, group_range=None, group_label="", ...) -> ([shapes], group_shape)`
Process flow with dashed grouping border around a subset of steps.

---

## Slide Templates

### `create_standard_slide(prs, title, page_num=None, total=None, notes="") -> slide`
Standard content slide with title, blue underline, logo, page number. Content starts at `CONTENT_TOP` (1.2").

### `create_section_divider(prs, title, subtitle="", notes="") -> slide`
Dark navy section divider with decorative circles and bright blue accent bar.

### `create_lead_slide(prs, title, subtitle="", meta="", notes="", level="", use_bg_image=True) -> slide`
Title/lead slide with background image on the left and a blue panel on the right. Title is bold dark text, subtitle in blue, meta in gray. The `level` parameter (`"L100"`, `"L200"`, `"L300"`, `"L400"`) renders as a large concentric circle badge on the blue panel. Microsoft logo appears at top-left.
```python
create_lead_slide(prs, "GitHub Copilot Deep Dive",
    subtitle="Architecture and Implementation Patterns",
    meta="L300 Deep Dive | March 2026",
    level="L300")
```

### `create_closing_slide(prs, title="Key Takeaways", takeaways=None, cta_title="", cta_url="", cta_items=None, page_num=None, total=None, notes="") -> slide`
Split closing slide: blue left (takeaways) + white right (CTA/questions).

### `create_two_tone_slide(prs, title, left_color=MS_DARK_BLUE, right_color=MS_WHITE, split_inches=5.0, page_num=None, total=None, notes="") -> (slide, left_width, right_left, right_width)`
Split-background slide: colored left panel + white right area. Returns layout coordinates for content placement.

### `create_gradient_slide(prs, title, color_start=MS_BLUE, color_end=MS_DARK_BLUE, angle_deg=135, page_num=None, total=None, notes="") -> slide`
Full-bleed gradient background. All text should use white colors.

### `create_agenda_slide(prs, title, items, highlight_index=None, page_num=None, total=None, notes="") -> slide`
Convenience wrapper: standard slide + `add_agenda_list`.

### `create_impact_slide(prs, headline, subtext="", stats=None, page_num=None, total=None, notes="") -> slide`
High-impact statement on gradient background with optional bottom stats row.
```python
create_impact_slide(prs, "55% Faster Onboarding",
    "Across 180+ teams at Contoso",
    stats=[("55%", "Faster"), ("3.2x", "More PRs"), ("40%", "Less Bugs")])
```

---

## Utilities

### `estimate_text_height(text, font_size_pt, width_inches, padding_inches=0.22, line_spacing_factor=1.45) -> Inches`
Estimate height needed to display text. Returns Inches() EMU value.

### `parse_slide_notes(notes_path) -> [str]`
Parse a slide markdown file and extract speaker notes by slide index (0-based).

### `download_image(url, filepath) -> bool`
Download an image from URL. Returns True on success.

### `save_presentation(prs, output_path) -> path`
Save the .pptx file and print summary. Creates directories if needed.
