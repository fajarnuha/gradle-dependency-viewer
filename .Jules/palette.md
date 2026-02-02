# Palette's Journal

## 2024-06-25 - Accessibility of Drop Zones
**Learning:** Custom file upload drop zones (`div` based) often lack keyboard accessibility. Adding `tabindex="0"`, `role="button"`, and a `keydown` handler for Enter/Space keys is a reusable pattern to make them accessible.
**Action:** When creating or spotting custom drag-and-drop areas, always ensure they are keyboard accessible using this pattern.

## 2024-06-25 - Accessibility of Interactive List Items
**Learning:** When making `li` elements interactive, avoid `role="button"` if they contain nested buttons (like delete), as this creates invalid ARIA. Use `tabindex="0"` and `aria-selected` instead.
**Action:** Always check for nested interactive elements when adding keyboard support to list items and manage event bubbling (e.g., `e.target` checks) to prevent conflicting actions.
