# Palette's Journal

## 2024-06-25 - Accessibility of Drop Zones
**Learning:** Custom file upload drop zones (`div` based) often lack keyboard accessibility. Adding `tabindex="0"`, `role="button"`, and a `keydown` handler for Enter/Space keys is a reusable pattern to make them accessible.
**Action:** When creating or spotting custom drag-and-drop areas, always ensure they are keyboard accessible using this pattern.

## 2024-05-23 - Interactive List Items
**Learning:** List items (`li`) with click handlers are not natively focusable. Replacing content with `<button>` elements (using CSS resets) provides instant keyboard support without breaking layout or requiring complex ARIA roles.
**Action:** Refactor clickable `li` elements to contain semantic `<button>` elements.
