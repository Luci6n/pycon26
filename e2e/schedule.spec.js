import { test, expect } from "@playwright/test";

// Deterministic learning resources so the schedule can be generated without
// relying on a live Exa key during the test.
const RESOURCE_STUB = {
  provider: "exa",
  configured: true,
  query: "stub",
  categories: [
    {
      type: "video",
      label: "Videos",
      results: [
        { type: "video", type_label: "Videos", title: "Intro to ML", url: "https://example.com/v1" },
        { type: "video", type_label: "Videos", title: "Neural Nets 101", url: "https://example.com/v2" },
      ],
    },
    {
      type: "book",
      label: "Books",
      results: [{ type: "book", type_label: "Books", title: "Deep Learning", url: "https://example.com/b1" }],
    },
    {
      type: "course",
      label: "Courses",
      results: [{ type: "course", type_label: "Courses", title: "MLOps Course", url: "https://example.com/c1" }],
    },
    {
      type: "project",
      label: "Projects to build",
      results: [{ type: "project", type_label: "Projects", title: "Build a classifier", url: "https://example.com/p1" }],
    },
  ],
  results: [],
  detail: "stub",
};

const MARKET_STUB = { provider: "apify", configured: false, jobs: [], skills: [] };

test("arrange-my-time: generate a schedule and export an ICS file", async ({ page }) => {
  await page.route("**/api/enrich/resources", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(RESOURCE_STUB) })
  );
  await page.route("**/api/enrich/market", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MARKET_STUB) })
  );

  await page.goto("/");
  await page.waitForLoadState("networkidle");

  // Pick a current and target role (skip the empty placeholder option).
  const roleSelects = page.locator(".role-select select");
  await expect(roleSelects).toHaveCount(2);
  await roleSelects.nth(0).selectOption({ index: 1 });
  await roleSelects.nth(1).selectOption({ index: 2 });

  // Run the analysis.
  await page.getByRole("button", { name: /Analyze profile/i }).click();

  // The scheduler panel appears once analysis produces a result.
  await expect(page.getByRole("heading", { name: "Arrange my time" })).toBeVisible();

  const arrangeButton = page.getByRole("button", { name: /^Arrange my time$/ });
  await expect(arrangeButton).toBeEnabled();
  await arrangeButton.click();

  // The generated plan renders session cards.
  await expect(page.getByRole("heading", { name: "Your learning plan" })).toBeVisible();
  await expect(page.locator(".session-card").first()).toBeVisible();

  // Exporting downloads an .ics file (works for Apple + Google Calendar).
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: /Add to calendar/i }).click(),
  ]);
  expect(download.suggestedFilename()).toMatch(/\.ics$/);
});
