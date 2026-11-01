import AxeBuilder from "@axe-core/playwright";
import { expect } from "@playwright/test";
import type { Locator, Page } from "@playwright/test";

// The fixture answer's last sentence; Check removes it as unsupported.
export const UNSUPPORTED = "remain intact in this conversation";

export async function ask(page: Page, question: string) {
  const box = page.getByLabel("Your question");
  await box.fill(question);
  await box.press("Enter");
}

// The newest exchange in the conversation.
export function lastTurn(page: Page): Locator {
  return page.locator("article.turn").last();
}

export async function answered(page: Page) {
  await expect(lastTurn(page).locator(".answer-prose").first()).toBeVisible();
}

// Select the given words inside `scope` and fire the mouseup the UI listens for.
export async function selectWords(scope: Locator, words: string) {
  await scope.evaluate((root, words) => {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const at = (node as Text).data.indexOf(words);
      if (at < 0) continue;
      const range = document.createRange();
      range.setStart(node, at);
      range.setEnd(node, at + words.length);
      const selection = window.getSelection()!;
      selection.removeAllRanges();
      selection.addRange(range);
      node.parentElement!.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
      return;
    }
    throw new Error(`"${words}" not found`);
  }, words);
}

// Chat must never render document metadata; the fixture marks it HIDDEN_*.
export async function expectNoSourceMetadata(page: Page) {
  const html = await page.locator(".view:not(.study)").first().innerHTML();
  expect(html).not.toContain("HIDDEN_");
  expect(html).not.toMatch(/\bE\d+\b/);
}

export async function expectAccessible(page: Page) {
  const results = await new AxeBuilder({ page }).analyze();
  const serious = results.violations.filter((v) =>
    ["serious", "critical"].includes(v.impact ?? ""),
  );
  expect(
    serious.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`),
  ).toEqual([]);
}
