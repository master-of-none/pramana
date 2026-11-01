import { expect, test } from "@playwright/test";
import { answered, ask, expectAccessible, expectNoSourceMetadata } from "./helpers.ts";

test("the map shows each stretch of the Sūtra and explains it", async ({ page }) => {
  await page.goto("/#/study/map");
  await expect(page.getByRole("heading", { level: 1, name: "Where they part ways" })).toBeVisible();
  const cells = page.locator(".dv-cell");
  await expect(cells).toHaveCount(4);
  await expect(cells.first()).toHaveAccessibleName(/^Brahma Sūtra 1\.1\.1: /);
  await expectAccessible(page);

  // Keyboard: one tab stop, arrows move, Enter opens the details.
  await cells.first().focus();
  await page.keyboard.press("ArrowRight");
  await expect(cells.nth(1)).toBeFocused();
  await page.keyboard.press("ArrowDown"); // to the next pāda's row
  await expect(cells.nth(3)).toBeFocused();
  await page.keyboard.press("ArrowUp");
  await page.keyboard.press("Home");
  await expect(cells.first()).toBeFocused();
  await page.keyboard.press("Enter");
  const detail = page.getByRole("complementary", { name: "Brahma Sūtra 1.1.1" });
  await expect(detail).toBeVisible();
  await expect(detail).toContainText("Dispute terms");
  await expectAccessible(page);
  // Bands only: no numeric scores anywhere on the page.
  expect(await page.locator(".divergence").innerText()).not.toMatch(/\d\.\d{2}|score/i);

  // The disputed sūtra 1.1.2: different verses cited, terms named, linked to the reader.
  await cells.nth(1).click();
  const second = page.getByRole("complementary", { name: "Brahma Sūtra 1.1.2" });
  await expect(second).toContainText("Only Śaṅkara: Kh. Up. VI, 8, 7");
  await expect(second).toContainText("nescience ×2");
  await second.getByRole("link", { name: "Read side by side" }).click();
  await expect(page).toHaveURL(/#\/study\/sutra\/1\/1\/2$/);
  // The side-by-side page links back to the map at this stretch.
  await page.getByRole("link", { name: "See the map" }).click();
  await expect(page.getByRole("complementary", { name: "Brahma Sūtra 1.1.2" })).toBeVisible();
});

test("the signal switch, table view and dark mode", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto("/#/study/map");
  const cell = page.locator(".dv-cell").nth(2); // 1.1.3: the same words on both sides
  await page.getByRole("radio", { name: "Dispute terms" }).click();
  await expect(cell).toHaveAccessibleName(/: low$/);
  await page.getByRole("radio", { name: "Scripture cited" }).click();
  await expect(cell).toHaveAccessibleName(/: low$/);
  await expectAccessible(page);
  await page.getByRole("button", { name: "Show as a table" }).click();
  const table = page.getByRole("table");
  await expect(table.getByRole("row")).toHaveCount(5);
  await table.getByRole("button", { name: "Overall" }).click();
  await expect(table.getByRole("row").nth(1).getByRole("rowheader")).not.toHaveText("1.1.3");
  await expectAccessible(page);
});

test("the map fits a phone and the chat never shows it", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 740 });
  await page.goto("/#/study/map");
  await page.locator(".dv-cell").first().click();
  const sheet = page.locator(".dv-detail");
  await expect(sheet).toBeInViewport();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth,
  );
  expect(overflow).toBe(false);
  await page.goto("/");
  await ask(page, "How do Shankara and Ramanuja differ?");
  await answered(page);
  await expect(page.locator(".view:not(.study)")).not.toContainText("part ways");
  await expectNoSourceMetadata(page);
});
