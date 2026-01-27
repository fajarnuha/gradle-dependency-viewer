# Palette's Journal

## 2024-06-25 - Accessibility of Drop Zones
**Learning:** Custom file upload drop zones (`div` based) often lack keyboard accessibility. Adding `tabindex="0"`, `role="button"`, and a `keydown` handler for Enter/Space keys is a reusable pattern to make them accessible.
**Action:** When creating or spotting custom drag-and-drop areas, always ensure they are keyboard accessible using this pattern.

## 2024-10-24 - Inline Async Action Feedback
**Learning:** For inline destructive actions (like deleting an item from a list), simply removing the item after a delay creates a confusing "dead time". Replacing the action button with a spinner/loading state provides immediate confirmation that the request is processing, even if the list re-renders on success.
**Action:** Always add a visual loading state (spinner/disabled) to action buttons that trigger async network requests, even for "micro" interactions.
