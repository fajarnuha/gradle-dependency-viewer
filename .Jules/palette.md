# Palette's Journal

## 2024-06-25 - Accessibility of Drop Zones
**Learning:** Custom file upload drop zones (`div` based) often lack keyboard accessibility. Adding `tabindex="0"`, `role="button"`, and a `keydown` handler for Enter/Space keys is a reusable pattern to make them accessible.
**Action:** When creating or spotting custom drag-and-drop areas, always ensure they are keyboard accessible using this pattern.

## 2024-06-25 - Interactive List Items with Actions
**Learning:** List items that serve as primary actions but also contain secondary actions (e.g., a file list with a delete button) cannot be implemented as a single clickable container with a nested button due to accessibility rules against nested interactive controls.
**Action:** Structure such items as a wrapper element (e.g., `li` or `div`) containing sibling buttons: one for the primary action (taking up remaining space) and one for the secondary action.
