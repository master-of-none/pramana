import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { answered, ask, expectAccessible } from "./helpers.ts";

type Library = { document: string; author: string; chapters: { id: string }[] }[];

async function chapterOf(page: Page, author: string) {
  const docs: Library = await (await page.request.get("/api/library")).json();
  return docs.find((d) => d.author === author)!.chapters[0].id;
}

test("the library lists the fixture texts and is accessible", async ({ page }) => {
  await page.goto("/#/study");
  await expect(page.getByRole("heading", { level: 1, name: "The library" })).toBeVisible();
  await expect(page.getByText("Brahma Sutra commentary (Sankaracharya)")).toBeVisible();
  await expectAccessible(page);
});

test("Read in the texts opens the passages behind an answer", async ({ page }) => {
  await page.goto("/");
  await ask(page, "How does action relate to understanding?");
  await answered(page);
  await page.getByRole("link", { name: "Read in the texts" }).click();
  await expect(
    page.getByRole("heading", { level: 1, name: "Passages behind this answer" }),
  ).toBeVisible();
  await expect(page.locator(".evidence-item blockquote").first()).toContainText(
    "Understanding grows",
  );
  await expectAccessible(page);
});

test("the sūtra view shows both commentaries with roles, notes and page marks", async ({
  page,
}) => {
  await page.goto("/#/study/sutra/1/1/1");
  const columns = page.locator(".parallel-column");
  await expect(columns).toHaveCount(2);
  await expect(columns.locator("> h2")).toHaveText(["Ramanuja", "Sankaracharya"]);
  await expect(page.locator(".role-objection").first()).toBeVisible();
  await expect(page.locator(".role-reply").first()).toBeVisible();
  await expect(page.locator(".page-mark").first()).toBeAttached();
  await expect(page.locator(".note-ref").first()).toBeAttached();
  await expectAccessible(page);
});

test("a code-point span after a supplementary character highlights the right words", async ({
  page,
}) => {
  const id = await chapterOf(page, "Sankaracharya");
  const text = "1. Then therefore the enquiry into Brahman. 𑀅 Ātman.";
  // Python code points, not UTF-16 units: 𑀅 is one code point but two units.
  const start = [...text].indexOf("Ā");
  await page.goto(`/#/study/read/${encodeURIComponent(id)}?s=${start}&e=${start + 5}`);
  await expect(page.locator(".passage-highlight")).toHaveText("Ātman", { useInnerText: true });
  await expect(page.getByRole("button", { name: "Ask about the highlighted passage" })).toBeVisible();
});

test("dark theme applies to the reader", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "dark" });
  const id = await chapterOf(page, "Ramanuja");
  await page.goto(`/#/study/read/${encodeURIComponent(id)}`);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  const background = await page.evaluate(
    () => getComputedStyle(document.body).backgroundColor,
  );
  const [r, g, b] = background.match(/\d+/g)!.map(Number);
  expect(r + g + b).toBeLessThan(200);
  await expectAccessible(page);
});

test("the answer trail sets each sentence beside its passage, in Study only", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Check", exact: true }).click();
  await ask(page, "How does action relate to understanding?");
  await answered(page);
  // Nothing of the trail in the chat.
  await expect(page.locator(".view:not(.study)")).not.toContainText("Sentence by sentence");
  await page.reload(); // the trail is kept with the turn in this tab
  await page.getByRole("link", { name: "Read in the texts" }).click();
  const trail = page.getByRole("region", { name: "Sentence by sentence" });
  await expect(trail).toBeVisible();
  const steps = trail.locator(".trail-step");
  // The removed sentence is not part of the trail; list marks are dropped.
  await expect(steps.locator(".trail-sentence")).toHaveText([
    "Understanding grows through thoughtful action and patient inquiry.",
    "Give the work your attention.",
    "Reflect on what it teaches you.",
  ]);
  await expect(steps.first().locator("blockquote")).toContainText("Understanding grows");
  // No internal references or scores in Study either.
  expect(await trail.innerText()).not.toMatch(/\bE\d+\b|\bp_[0-9a-f]+|score|relevance/i);
  await steps.first().getByRole("link").click();
  await expect(page.locator(".passage-highlight").first()).toBeVisible();
  await page.goBack();
  await expectAccessible(page);
});

test("without Check the evidence page says how to see the trail", async ({ page }) => {
  await page.goto("/");
  await ask(page, "How does action relate to understanding?");
  await answered(page);
  await page.getByRole("link", { name: "Read in the texts" }).click();
  await expect(page.getByText("turn on Check before asking")).toBeVisible();
  await expect(page.getByRole("heading", { name: "All passages behind it" })).toBeVisible();
});
