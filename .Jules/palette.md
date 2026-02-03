# Palette's Journal

## 2024-06-25 - Accessibility of Drop Zones
**Learning:** Custom file upload drop zones (`div` based) often lack keyboard accessibility. Adding `tabindex="0"`, `role="button"`, and a `keydown` handler for Enter/Space keys is a reusable pattern to make them accessible.
**Action:** When creating or spotting custom drag-and-drop areas, always ensure they are keyboard accessible using this pattern.

## 2026-01-26 - Icon-Only Buttons Accessibility
**Learning:** The app relies heavily on `title` attributes for icon-only buttons (like delete, copy, enlist). While `title` provides a tooltip, it is not a robust substitute for `aria-label`, especially for touch devices or screen reader verbose modes.
**Action:** Always add `aria-label` to icon-only buttons, even if a `title` is present. For dynamic lists, include the item name in the `aria-label` (e.g., "Delete file.txt") for better context.
