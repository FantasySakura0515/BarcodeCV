# Frontend Style Guidelines (Web Console)

## Purpose
Define practical conventions for a professional, operational web console UI in BarcodeCV frontend.

## UX / Content
- Use concise operational wording.
- Prefer explicit actions: "Run detection", "Retry", "Refresh".
- Avoid placeholder controls that do not work yet.
- Error messages must explain failure and next step.

## Layout
- Every route should follow:
  1. `PageHeader`
  2. summary/status block(s)
  3. primary content section(s)
- Use `SectionCard` for grouped content; keep consistent spacing and borders.
- Keep decorative styles minimal; prioritize readability.

## Components
- `PageHeader`: short purpose + key actions only.
- `StatCard`: value-focused metric with one-line hint.
- `EmptyState`: neutral icon + clear next step.
- Tables:
  - include explicit empty row/state,
  - keep identifier columns readable,
  - use semantic status badges.

## States
- Loading: visible progress text where action duration is non-trivial.
- Empty: why no data + what to do next.
- Error: human-readable summary + retry affordance where practical.

## Accessibility Baseline
- Preserve keyboard access for interactive controls.
- Ensure color is not the only status signal.
- Keep heading hierarchy consistent per page.

## Non-goals
- No broad framework/library replacement.
- No API contract changes from frontend.
- No backend business logic expansion beyond UI error handling needs.
