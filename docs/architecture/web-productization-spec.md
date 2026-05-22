# Web Productization Spec (Frontend)

## Scope
Productize the Next.js web console for BarcodeCV. Keep current API contracts and core workflows intact while improving operational clarity, consistency, and maintainability.

## Target Users
1. **Operations staff**: run image/live detection, review outcomes, monitor quality.
2. **Quality/engineering staff**: inspect batches/objects, validate model usage and output quality.
3. **Technical managers**: review system health and trend-level metrics.

## Core Workflows
1. **Run single-image detection**
   - Upload image → run detection → inspect object table/canvas → open object detail.
2. **Run live detection**
   - Select camera/device → start preview/scanning → capture frame to batch record.
3. **Review historical data**
   - Browse batch list → open batch detail → inspect per-object details.
4. **Check model and system summary**
   - View dashboard KPI + trends, active model state, model inventory.

## Information Architecture / Navigation
- Global primary nav:
  - Dashboard
  - Image Detection
  - Live Detection
  - Batch Records
  - Models
- Per-page hierarchy:
  1. Page header (title, purpose, key actions)
  2. Summary/status cards
  3. Main operational surface (canvas/table/form)
  4. Supporting details
- Home route redirects to Dashboard.

## Visual Tone
- Neutral, professional, low-distraction.
- Minimize decorative gradients/glass effects.
- Emphasize readability, status clarity, and task progression.
- Use color semantically (success/warning/error/info), not ornamentally.

## Content Voice Rules
- Use direct, operational language.
- Avoid playful or ambiguous phrases.
- Labels should describe system state or required action.
- Error copy should include:
  - what failed,
  - likely impact,
  - next action (retry / refresh / check backend connectivity).

## Component Standards
- **PageHeader**: title + short purpose + optional context badge + primary/secondary actions.
- **SectionCard**: section title + optional description + optional action; consistent spacing.
- **Data tables**:
  - fixed column intent,
  - consistent empty row/empty state,
  - row selection state where applicable.
- **Status indicators**:
  - consistent badge variants and wording.
- **Forms/inputs**:
  - avoid non-functional placeholder controls in production views.

## Empty / Loading / Error States
- **Empty**: explain why empty and next step.
- **Loading**: use explicit state text for camera scan, detection in progress, etc.
- **Error**:
  - concise cause and user action,
  - provide retry affordance where practical,
  - avoid raw stack traces or vague generic failure text only.

## Accessibility Baseline
- Semantic headings and landmarks.
- Keyboard reachable controls (buttons/links/selects).
- Sufficient color contrast for text and status chips.
- Icons are supplementary; critical info must be text.
- Motion is subtle and must not block interaction.

## Responsive Behavior
- Desktop-first console with reliable tablet/mobile fallback.
- Key actions remain visible near page header.
- Tables may wrap critical fields but keep identifiers readable.
- Detection canvases maintain aspect ratio and selection behavior.

## Acceptance Checklist
- [ ] Navigation and page hierarchy are consistent across core routes.
- [ ] Playful/demo-like wording removed from user-facing copy.
- [ ] Non-functional UI elements removed or explicitly marked as future scope.
- [ ] Empty/loading/error states are present and actionable.
- [ ] API failure messaging is clearer and includes retry path where possible.
- [ ] Existing detection/model/batch/object functionality remains intact.
- [ ] Frontend lint/build pass after changes.
