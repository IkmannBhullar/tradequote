import { expect, test } from "@playwright/test";

// The core journey of the product, end to end, in a real browser.
test("a contractor signs up and builds a quote with live totals", async ({ page }) => {
  // A unique email per run, so the test never collides with earlier runs.
  const email = `e2e-${Date.now()}@example.com`;

  await test.step("sign up", async () => {
    await page.goto("/signup");
    await page.getByLabel("Company name").fill("E2E Painting");
    await page.getByLabel("Email", { exact: true }).fill(email);
    await page.getByLabel("Password", { exact: true }).fill("correct horse battery staple");
    await page.getByRole("button", { name: "Create account" }).click();
    await expect(page).toHaveURL(/\/settings/);
  });

  await test.step("set rates: $65/hour, 5% tax", async () => {
    await page.getByLabel("Labor rate ($ per hour)").fill("65");
    await page.getByLabel("Tax rate (%)").fill("5");
    await page.getByRole("button", { name: "Save settings" }).click();
    await expect(page.getByRole("status")).toHaveText("Saved.");
  });

  await test.step("create a client and a job", async () => {
    await page.getByRole("link", { name: "Clients" }).click();
    // Wait for the navigation to finish before touching the form; otherwise
    // we'd be typing into the page we're leaving.
    await expect(page.getByRole("heading", { name: "Clients", level: 1 })).toBeVisible();
    // exact: getByLabel matches substrings by default, and "Name" would also
    // match "Company name".
    await page.getByLabel("Name", { exact: true }).fill("Jane Homeowner");
    await page.getByRole("button", { name: "Add client" }).click();
    await expect(page.getByRole("heading", { name: "Jane Homeowner" })).toBeVisible();
    await page.getByLabel("Job title").fill("Repaint living room");
    await page.getByRole("button", { name: "New job" }).click();
    await expect(page.getByRole("heading", { name: "Repaint living room" })).toBeVisible();
  });

  await test.step("quote 420 sq ft of walls: the worked example, $483.00", async () => {
    await page.getByRole("button", { name: "Create quote" }).click();
    await expect(page.getByRole("heading", { name: "Quote v1" })).toBeVisible();
    await page.getByRole("combobox").selectOption({ label: "Walls" });
    await page.getByLabel("Area name").fill("Living room walls");
    await page.getByLabel(/^Quantity/).fill("420");
    await page.getByRole("button", { name: "Add area" }).click();
    await expect(page.getByTestId("total")).toHaveText("$483.00");
  });

  await test.step("re-measure: totals update live and persist", async () => {
    const quantity = page.getByLabel("Quantity of Living room walls");
    await quantity.fill("840");
    await quantity.blur();
    await expect(page.getByTestId("total")).toHaveText("$966.00");
    await page.reload();
    await expect(page.getByTestId("total")).toHaveText("$966.00");
  });
});

test("signed-out visitors are sent to login and returned afterwards", async ({ page }) => {
  await page.goto("/clients");
  await expect(page).toHaveURL(/\/login\?next=%2Fclients/);
});
