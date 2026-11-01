// Single-key shortcuts must not fire while the reader is typing or holding a modifier.
export function isShortcut(event: KeyboardEvent): boolean {
  if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.altKey) return false;
  const target = event.target as HTMLElement | null;
  if (!target) return true;
  return !(
    target.isContentEditable ||
    ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName) ||
    target.closest("dialog[open]:not(.shortcuts)")
  );
}

// The command palette and reading panel listen for these, wherever they are mounted.
export const PALETTE = "pramana:palette";
export const TYPOGRAPHY = "pramana:typography";
export const THEME = "pramana:theme";
export const SHORTCUTS = "pramana:shortcuts";
