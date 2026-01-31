# Palette's Journal

## 2024-06-25 - Accessibility of Drop Zones
**Learning:** Custom file upload drop zones (`div` based) often lack keyboard accessibility. Adding `tabindex="0"`, `role="button"`, and a `keydown` handler for Enter/Space keys is a reusable pattern to make them accessible.
**Action:** When creating or spotting custom drag-and-drop areas, always ensure they are keyboard accessible using this pattern.

## 2024-05-22 - Native Dialog Replacement
**Learning:** Native `window.confirm()` is blocking and jarring. Replacing it with the HTML `<dialog>` element allows for a seamless, styled experience while maintaining native accessibility features (focus trapping, Esc to close).
**Action:** Replace `confirm()` calls with `<dialog>` modals for destructive actions.
