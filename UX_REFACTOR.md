# UX Refactor

This branch introduces a presentation-only navigation shell through the existing WSGI entrypoint.

## Goals
- Keep existing Flask routes and business logic unchanged.
- Keep existing DOM IDs and JavaScript handlers unchanged.
- Add clear RTL desktop navigation.
- Add compact responsive mobile navigation.
- Separate daily reporting, pricing, analytics, templates and administration visually.

## Compatibility
The existing `templates/index.html` remains unchanged. The WSGI middleware decorates HTML responses after Flask renders them, so existing API behavior and application logic are not rewritten.
