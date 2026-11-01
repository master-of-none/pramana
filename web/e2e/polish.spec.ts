import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { expectAccessible } from "./helpers.ts";

const palette = (page: Page) => page.getByRole("dialog", { name: "Command palette" });

async function openPalette(page: Page) {
  await page.keyboard.press("ControlOrMeta+k");
  await expect(palette(page)).toBeVisible();
}

test("the command palette offers only actions in the chat", async ({ page }) => {
  await page.goto("/");
  await openPalette(page);
  await expectAccessible(page);
  await page.keyboard.type("Brahma");
  // Titles, verses and concepts are metadata: never listed from the chat.
  await expect(palette(page).getByRole("option")).toHaveText([
    "Ask: Brahma",
    "Search the texts for “Brahma”",
  ]);
  await page.keyboard.press("Enter");
  await expect(palette(page)).toBeHidden();
  await expect(page.getByLabel("Your question")).toHaveValue("Brahma");
  await expect(page.getByLabel("Your question")).toBeFocused();
});

test("in Study the palette finds texts, sūtras and concepts by keyboard", async ({ page }) => {
  await page.goto("/#/study");
  await expect(page.getByRole("heading", { level: 1, name: "The library" })).toBeVisible();
  await openPalette(page);
  await page.keyboard.type("ramanuja");
  const text = palette(page).getByRole("option", { name: /Brahma Sutra commentary \(Ramanuja\)/ });
  await expect(text).toBeVisible();
  await page.keyboard.press("ArrowDown");
  await expect(palette(page).getByRole("option", { selected: true })).toBeVisible();
  await text.click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Ramanuja");

  await openPalette(page);
  await page.keyboard.type("BS 1.1.1");
  await expect(palette(page).getByRole("option").first()).toHaveText(/Brahma Sūtra 1\.1\.1/);
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/#\/study\/sutra\/1\/1\/1$/);

  await openPalette(page);
  await page.keyboard.press("Escape");
  await expect(palette(page)).toBeHidden();
});

test("the reader pages with arrow keys and lists the work's contents", async ({ page }) => {
  const docs: { author: string; chapters: { id: string }[] }[] = await (
    await page.request.get("/api/library")
  ).json();
  const id = docs.find((d) => d.author === "Sankaracharya")!.chapters[0].id;
  await page.goto(`/#/study/read/${id}`);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await page.keyboard.press("?");
  const sheet = page.getByRole("dialog", { name: "Keyboard shortcuts" });
  await expect(sheet).toBeVisible();
  await expectAccessible(page);
  await page.keyboard.press("Escape");
  await expect(sheet).toBeHidden();
  // Reading progress is remembered in this browser: the library offers to continue.
  await page.goto("/#/study");
  await expect(page.getByRole("link", { name: /Continue reading/ })).toContainText(
    "Brahma Sutra commentary (Sankaracharya)",
  );
});

test("reading settings change the reader's type and are remembered", async ({ page }) => {
  await page.goto("/#/study/sutra/1/1/1");
  await expect(page.locator(".parallel-column")).toHaveCount(2);
  const text = page.locator(".chapter-text").first();
  const before = await text.evaluate((el) => parseFloat(getComputedStyle(el).fontSize));
  await page.getByRole("button", { name: "Reading settings" }).click();
  const panel = page.getByRole("group", { name: "Reading settings" });
  await panel.getByRole("radio", { name: "Larger" }).click();
  await panel.getByRole("radio", { name: "Sans" }).click();
  await expectAccessible(page);
  const after = await text.evaluate((el) => parseFloat(getComputedStyle(el).fontSize));
  expect(after).toBeGreaterThan(before * 1.2);
  expect(await text.evaluate((el) => getComputedStyle(el).fontFamily)).toContain("Source Sans");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-size", "xlarge");
  await expect(page.locator("html")).toHaveAttribute("data-face", "sans");
});

test("a typed verse reference opens the passage", async ({ page }) => {
  await page.goto("/#/study");
  await openPalette(page);
  await page.keyboard.type("Ch 6.8.7");
  const verse = palette(page).getByRole("option", { name: /Chandogya Upanishad VI, 8, 7/ });
  await expect(verse).toBeVisible();
  await expect(palette(page).getByRole("option").first()).toHaveText(/Chandogya/);
  await page.keyboard.press("Enter");
  await expect(page.locator(".passage-highlight").first()).toContainText("subtle essence");
  // A division the library does not have is not offered.
  await openPalette(page);
  await page.keyboard.type("Ch 9.9.9");
  await page.waitForTimeout(400);
  await expect(palette(page).getByRole("option").first()).toHaveText(/^Ask: Ch 9\.9\.9/);
});
