# Palette's Journal

## 2024-06-25 - Accessibility of Drop Zones
**Learning:** Custom file upload drop zones (`div` based) often lack keyboard accessibility. Adding `tabindex="0"`, `role="button"`, and a `keydown` handler for Enter/Space keys is a reusable pattern to make them accessible.
**Action:** When creating or spotting custom drag-and-drop areas, always ensure they are keyboard accessible using this pattern.

## 2026-02-01 - Interactive List Items
**Learning:** Using `li` elements with click handlers for list selection creates an accessibility barrier for keyboard users.
**Action:** Always wrap the interactive content of a list item in a `<button>` element to ensure native keyboard focus and activation support, even if it requires restyling the button to look like plain text.
