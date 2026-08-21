# SiteProof product design

SiteProof should feel like a practical field tool, not a technical demo.

## Principles

- Use plain language. Prefer “Try again” over protocol or implementation terms.
- Show the task first. Put hashes, engine details and diagnostics behind an optional details section.
- Keep one clear primary action on each screen.
- Do not repeat the same status in several places unless it prevents a mistake.
- Use labels and text for status; color is supporting information, not the only signal.
- Keep destructive actions separate and visually quiet until the user asks for them.
- Preserve audit and security information without making every screen read like security documentation.

## Visual language

Web and Android share the same base palette and spacing approach:

- warm off-white page background
- white cards and sheets
- dark forest green primary action
- muted gray-green secondary text
- amber for warning states
- red for destructive or failed states
- modest corner radii and subtle shadows

Avoid neon accents, decorative gradients, oversized display type and unnecessary animation.

## Writing

Use short, specific sentences. UI text should describe what happened and what the user can do next.

Avoid development labels such as phase numbers, field-test, debug, control desk, engine internals or API terminology in normal user flows. Those details can remain in developer documentation and technical evidence views where they are useful.

## Technical detail

Verification scores, receipts, evidence hashes and sensor diagnostics are important, but they are secondary to the decision and next action. Default screens should show the result, confidence, receipt state and reviewer action. Deeper evidence stays available on demand.
