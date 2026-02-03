# Palette's Journal

## 2024-06-25 - Accessibility of Drop Zones
**Learning:** Custom file upload drop zones (`div` based) often lack keyboard accessibility. Adding `tabindex="0"`, `role="button"`, and a `keydown` handler for Enter/Space keys is a reusable pattern to make them accessible.
**Action:** When creating or spotting custom drag-and-drop areas, always ensure they are keyboard accessible using this pattern.

## 2024-05-23 - Interactive List Items
**Learning:** List items (`li`) with click handlers are not natively focusable. Replacing content with `<button>` elements (using CSS resets) provides instant keyboard support without breaking layout or requiring complex ARIA roles.
**Action:** Refactor clickable `li` elements to contain semantic `<button>` elements.

## 2026-01-26 - Icon-Only Buttons Accessibility
**Learning:** The app relies heavily on `title` attributes for icon-only buttons (like delete, copy, enlist). While `title` provides a tooltip, it is not a robust substitute for `aria-label`, especially for touch devices or screen reader verbose modes.
**Action:** Always add `aria-label` to icon-only buttons, even if a `title` is present. For dynamic lists, include the item name in the `aria-label` (e.g., "Delete file.txt") for better context.


## 2025-01-28 - Interactive List Items
**Learning:** List items (`li`) with `click` handlers are not keyboard-accessible by default. Converting them to contain a full-width `<button>` element is the most robust way to ensure accessibility (focus, Enter/Space support) without reimplementing button behavior on `div`s or `li`s.
**Action:** Always prefer native `<button>` elements for interactive list items, using CSS to reset styles and make them fill the container.
