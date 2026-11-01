import { expect, test } from "@playwright/test";
import {
  UNSUPPORTED,
  answered,
  ask,
  expectAccessible,
  expectNoSourceMetadata,
  lastTurn,
  selectWords,
} from "./helpers.ts";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
});

test("welcome screen is accessible and offers starter questions", async ({ page }) => {
  await expect(page.getByLabel("Suggested questions").getByRole("button")).toHaveCount(5);
  await expectAccessible(page);
});

test("a question and a follow-up are answered without source metadata", async ({ page }) => {
  await ask(page, "How does action relate to understanding?");
  await answered(page);
  await expect(lastTurn(page)).toContainText("thoughtful action");
  await ask(page, "And what about inquiry?");
  await expect(page.locator("article.turn")).toHaveCount(2);
  await answered(page);
  await expectNoSourceMetadata(page);
  // Unicode, including a supplementary character, survives rendering.
  await expect(lastTurn(page)).toContainText("Ānanda and 𑀅", { useInnerText: true });
  await expectAccessible(page);
});

test("the conversation survives a reload and New chat clears it", async ({ page }) => {
  await ask(page, "What is the Self?");
  await answered(page);
  await page.reload();
  await expect(page.locator("article.turn")).toHaveCount(1);
  await page.getByRole("button", { name: "New chat" }).click();
  await expect(page.locator("article.turn")).toHaveCount(0);
  await page.reload();
  await expect(page.locator("article.turn")).toHaveCount(0);
});

test("Stop cancels a slow answer and Try again is offered", async ({ page }) => {
  await ask(page, "A slow question");
  await expect(lastTurn(page).getByRole("status")).toBeVisible();
  await page.getByRole("button", { name: "Stop answer" }).click();
  await expect(lastTurn(page)).toContainText("Answer stopped");
  await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
});

test("a failed answer can be retried", async ({ page }, info) => {
  // The fixture fails each distinct 'fail' question once.
  await ask(page, `Please fail once (${info.project.name} ${Date.now()})`);
  await expect(lastTurn(page).getByRole("alert")).toContainText("temporarily unavailable");
  await page.getByRole("button", { name: "Try again" }).click();
  await answered(page);
});

test("a comparison shows one card per thinker", async ({ page }) => {
  await ask(page, "How do Shankara and Ramanuja differ?");
  await answered(page);
  const cards = lastTurn(page).locator(".perspective");
  await expect(cards).toHaveCount(2);
  await expect(cards.locator("h3")).toHaveText(["Ramanuja", "Sankaracharya"]);
  await expectNoSourceMetadata(page);
});

test("Check removes the unsupported sentence", async ({ page }) => {
  await page.getByRole("button", { name: "Check", exact: true }).click();
  await ask(page, "How does action relate to understanding?");
  await answered(page);
  await expect(lastTurn(page)).toContainText("thoughtful action");
  await expect(lastTurn(page)).not.toContainText(UNSUPPORTED);
  await expect(lastTurn(page).locator(".check-badge")).toBeVisible();
});

test("words selected in an answer can be asked about, highlighted or noted", async ({
  page,
}) => {
  await ask(page, "How does action relate to understanding?");
  await answered(page);
  await selectWords(lastTurn(page).locator(".answer-prose").first(), "patient inquiry");
  await expect(page.getByRole("button", { name: "Highlight" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Note" })).toBeVisible();
  await page.getByRole("button", { name: "Ask about this" }).click();
  await expect(page.getByLabel("Your question")).toHaveValue(/^About “patient inquiry”: /);
});

test("Escape closes the note editor without stopping an answer", async ({ page }) => {
  await ask(page, "How does action relate to understanding?");
  await answered(page);
  const first = page.locator("article.turn").first();
  await ask(page, "A slow question");
  await expect(lastTurn(page).getByRole("status")).toBeVisible();
  await selectWords(first.locator(".answer-prose").first(), "patient inquiry");
  await page.getByRole("button", { name: "Note" }).click();
  const note = page.getByLabel("Your note");
  await expect(note).toBeFocused();
  await note.press("Escape");
  await expect(note).toBeHidden();
  await expect(lastTurn(page)).not.toContainText("Answer stopped");
  await expect(page.getByRole("button", { name: "Stop answer" })).toBeVisible();
  // Escape with nothing open still stops the answer.
  await page.keyboard.press("Escape");
  await expect(lastTurn(page)).toContainText("Answer stopped");
});

test("Jump to latest appears only when the newest answer is out of view", async ({
  page,
}) => {
  await ask(page, "How does action relate to understanding?");
  await answered(page);
  const jump = page.getByRole("button", { name: "Jump to latest message" });
  await expect(jump).toBeHidden();
  for (const q of ["One more?", "And another?", "A third?"]) {
    await ask(page, q);
    await answered(page);
  }
  // The window scrolls on desktop, the conversation itself on mobile.
  await page.evaluate(() =>
    document.querySelector("article.turn")!.scrollIntoView({ block: "start" }),
  );
  await expect(jump).toBeVisible();
  await jump.click();
  await expect(jump).toBeHidden();
});

test("an earlier question can be edited and asked again", async ({ page }) => {
  await ask(page, "What is the Self?");
  await answered(page);
  await ask(page, "And Brahman?");
  await answered(page);
  const first = page.locator("article.turn").first();
  await first.hover();
  await first.getByRole("button", { name: "Edit" }).click();
  const box = page.getByLabel("Your question");
  await expect(box).toHaveValue("What is the Self?");
  await expect(page.getByText("Editing an earlier question")).toBeVisible();
  await box.fill("What is the witness?");
  await box.press("Enter");
  // The edited question replaces its turn and everything after it, with fresh retrieval.
  await expect(page.locator("article.turn")).toHaveCount(1);
  await expect(lastTurn(page)).toContainText("What is the witness?");
  await answered(page);
});

test("the conversation saves as Markdown without evidence pointers", async ({ page }) => {
  await ask(page, "How do Shankara and Ramanuja differ?");
  await answered(page);
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Save as Markdown" }).click();
  const file = await download;
  expect(file.suggestedFilename()).toMatch(/^pramana-conversation-\d{4}-\d{2}-\d{2}\.md$/);
  const text = await (await file.createReadStream()).toArray();
  const md = Buffer.concat(text).toString("utf8");
  expect(md).toContain("## How do Shankara and Ramanuja differ?");
  expect(md).toContain("### Sankaracharya");
  expect(md).not.toMatch(/HIDDEN_|\bE\d+\b|ps_|ch_/);
});

test("Vichāra and Check say what they do while on", async ({ page }) => {
  await page.getByRole("button", { name: "Vichāra" }).click();
  await expect(page.getByText(/questions to reflect on/)).toBeVisible();
  await page.getByRole("button", { name: "Check", exact: true }).click();
  await expect(page.getByText(/removes sentences the passages do not support/)).toBeVisible();
  await expectAccessible(page);
});

test("without an answer model a question opens as a search in Study", async ({ page }) => {
  await page.route("**/api/config", (route) =>
    route.fulfill({
      json: {
        hosted: false,
        provider: { name: "ollama", model: "gemma4:e4b", ready: false, reason: "Ollama is not running." },
      },
    }),
  );
  await page.goto("/");
  await expect(page.getByText("Answers need a language model, and none is ready.")).toBeVisible();
  await expect(page.getByLabel("Your question")).toHaveAttribute("placeholder", "Search the texts…");
  await expectAccessible(page);
  await ask(page, "adhyasa");
  await expect(page).toHaveURL(/#\/study\/search\?q=adhyasa$/);
  await expect(page.getByLabel("Search terms")).toHaveValue("adhyasa");
});
