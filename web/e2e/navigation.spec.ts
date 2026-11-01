import { expect, test } from "@playwright/test";

test("a route change moves focus to the page heading and sets the title", async ({
  page,
}) => {
  await page.goto("/#/study");
  await expect(page).toHaveTitle(/^The library · Pramana$/);
  await page.getByRole("link", { name: "Paths", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toBeFocused();
  await expect(page).toHaveTitle(/^Reading paths · Pramana$/);
  // The search page is for typing: its box takes focus instead.
  await page.getByRole("link", { name: "Search", exact: true }).click();
  await expect(page.getByLabel("Search terms")).toBeFocused();
  await expect(page).toHaveTitle(/^Search the library · Pramana$/);
  await page.goto("/#/");
  await expect(page).toHaveTitle(/^Pramana/);
});

test("Back restores the scroll position", async ({ page }) => {
  await page.setViewportSize({ width: 800, height: 400 });
  await page.goto("/#/study");
  await expect(page.getByRole("heading", { level: 1, name: "The library" })).toBeVisible();
  // The Study view scrolls its own main element, not the window.
  const main = page.locator("#study-main");
  await main.evaluate((m) => (m.scrollTop = 200));
  const before = await main.evaluate((m) => m.scrollTop);
  expect(before).toBeGreaterThan(150);
  // Navigate without scrolling a link into view first.
  await page.evaluate(() => (location.hash = "#/study/notes"));
  await expect(page.getByRole("heading", { level: 1, name: "My notes" })).toBeFocused();
  expect(await main.evaluate((m) => m.scrollTop)).toBe(0);
  await page.goBack();
  await expect(page.getByRole("heading", { level: 1, name: "The library" })).toBeFocused();
  await expect.poll(() => main.evaluate((m) => m.scrollTop)).toBe(before);
});

test("an unknown route says so and links to the library", async ({ page }) => {
  await page.goto("/#/study/nowhere");
  await expect(page.getByRole("heading", { level: 1, name: "Page not found" })).toBeVisible();
  await page.getByRole("link", { name: "Open the library" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "The library" })).toBeVisible();
});

test("the header fits a 360 px phone", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 740 });
  for (const route of ["/", "/#/study"]) {
    await page.goto(route);
    const overflow = await page.evaluate(() => {
      const bar = document.querySelector(".topbar")!;
      return [...bar.querySelectorAll("a, button")].some(
        (el) => el.getBoundingClientRect().right > window.innerWidth,
      );
    });
    expect(overflow, route).toBe(false);
  }
});
