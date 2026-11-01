import { expect, test } from "@playwright/test";
import { answered, ask, expectAccessible, expectNoSourceMetadata } from "./helpers.ts";

test("the great sayings: found where the text has them, reported where it does not", async ({
  page,
}) => {
  await page.goto("/#/study/sayings");
  await expect(page.getByRole("heading", { level: 1, name: "The great sayings" })).toBeVisible();
  const cards = page.locator(".sy-card");
  await expect(cards).toHaveCount(4);
  // The fixture library has only the Chāndogya: one found, three honestly missing.
  await expect(cards.filter({ hasText: "Not found in this library" })).toHaveCount(3);
  const tat = cards.filter({ hasText: "tat tvam asi" });
  await expect(tat).toContainText("Chandogya Upanishad VI, 8");
  await expect(tat).toContainText("Śaṅkara cites it");
  await expectAccessible(page);

  await tat.getByRole("link", { name: "Read the verse and its citations" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "tat tvam asi" })).toBeVisible();
  // The saying is marked inside its verse.
  await expect(page.locator(".vs-verse mark")).toHaveText("thou, O Svetaketu, art it");
  const cited = page.getByRole("group", { name: "Passages citing this verse, by author" });
  // In the fixture only Śaṅkara cites verse 7 (Rāmānuja's page cites verse 8).
  await expect(cited.locator(".vs-column h3")).toHaveText(["Śaṅkara cites it once"]);
  await expect(cited.locator(".vs-excerpt mark").first()).toContainText("Kh. Up. VI, 8, 7");
  // Words used without a printed reference are listed apart.
  const elsewhere = page.getByRole("group", { name: "The same words elsewhere, by author" });
  await expect(elsewhere).toContainText("Thou art that");
  await expect(elsewhere.locator(".vs-column h3")).toHaveText(["Rāmānuja uses them once"]);
  await expectAccessible(page);
  await page.emulateMedia({ colorScheme: "dark" });
  await expectAccessible(page);
});

test("the reader's cited-by list opens the verse page", async ({ page }) => {
  const docs: { document: string; chapters: { id: string }[] }[] = await (
    await page.request.get("/api/library")
  ).json();
  const id = docs.find((d) => d.document === "Chandogya Upanishad")!.chapters[0].id;
  await page.goto(`/#/study/read/${id}`);
  const cited = page.locator(".cited-by").first();
  await cited.locator("summary").click();
  await cited.getByRole("link", { name: "All citations of this verse, side by side" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Chandogya Upanishad VI, 8" })).toBeVisible();
  await expect(page.locator(".vs-passage").first()).toBeVisible();
});

test("the palette finds a saying, the page fits a phone, the chat shows none of it", async ({
  page,
}) => {
  await page.setViewportSize({ width: 360, height: 740 });
  await page.goto("/#/study");
  await page.keyboard.press("ControlOrMeta+k");
  await page.keyboard.type("tat tvam");
  // The saying, not the glossary concept of the same name.
  await page.getByRole("option", { name: /^tat tvam asi Great saying/ }).click();
  await expect(page.getByRole("heading", { level: 1, name: "tat tvam asi" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)).toBe(
    false,
  );
  await page.goto("/");
  await ask(page, "What does that art thou mean?");
  await answered(page);
  await expect(page.locator(".view:not(.study)")).not.toContainText("cites it");
  await expectNoSourceMetadata(page);
});
