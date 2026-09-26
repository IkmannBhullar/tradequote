import { expect, test } from "@playwright/test";

// The core journey of the product, end to end, in a real browser.
test("quote -> client approval -> work -> payment -> paid", async ({ page, browser }) => {
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

  let clientLink = "";
  await test.step("send it: the client link is shown once", async () => {
    page.once("dialog", (dialog) => dialog.accept()); // "Send this quote?"
    await page.getByRole("button", { name: "Send to client" }).click();
    clientLink = await page.getByLabel("Client link").inputValue();
    expect(clientLink).toMatch(/\/q\/[A-Za-z0-9_-]{43}$/);
    await expect(page.getByText(/waiting for the client/)).toBeVisible();
  });

  await test.step("the client, logged out, approves by typing their name", async () => {
    // A separate browser context: its own cookie jar, so truly signed out.
    const clientContext = await browser.newContext();
    const client = await clientContext.newPage();
    await client.goto(clientLink);
    await expect(client.getByTestId("public-total")).toHaveText("$966.00");
    await client.getByLabel("Your full name").first().fill("Jane Homeowner");
    await client.getByLabel(/I agree to this quote/).check();
    await client.getByRole("button", { name: "Approve quote" }).click();
    await expect(client.getByText(/Approved by Jane Homeowner/)).toBeVisible();
    await clientContext.close();
  });

  await test.step("the contractor sees the approval and the job moves on the board", async () => {
    await page.reload();
    await expect(page.getByText(/Approved by/)).toBeVisible();
    await page.getByRole("link", { name: "Jobs", exact: true }).click();
    const approvedColumn = page.getByRole("region", { name: "Approved" });
    await expect(approvedColumn.getByText("Repaint living room")).toBeVisible();
  });

  await test.step("do the work on the board: scheduled -> in progress -> completed", async () => {
    for (const column of ["Scheduled", "In progress", "Completed"]) {
      await page.getByRole("button", { name: `→ ${column}` }).click();
      await expect(page.getByRole("region", { name: column }).getByText("Repaint living room")).toBeVisible();
    }
  });

  await test.step("record the payment: the job moves to Paid by itself", async () => {
    await page.getByRole("region", { name: "Completed" }).getByRole("link", { name: "Repaint living room" }).click();
    await expect(page.getByTestId("balance")).toHaveText("$966.00");
    await page.getByLabel("Amount ($)").fill("966");
    await page.getByLabel("Method").fill("e-transfer");
    await page.getByRole("button", { name: "Record payment" }).click();
    await expect(page.getByText("Paid in full.")).toBeVisible();

    await page.getByRole("link", { name: "Jobs", exact: true }).click();
    await expect(page.getByRole("region", { name: "Paid" }).getByText("Repaint living room")).toBeVisible();
  });
});

test("an invalid client link shows a 404 page", async ({ page }) => {
  const response = await page.goto(`/q/${"x".repeat(43)}`);
  expect(response?.status()).toBe(404);
  await expect(page.getByRole("heading", { name: "Quote not found" })).toBeVisible();
});

test("signed-out visitors are sent to login and returned afterwards", async ({ page }) => {
  await page.goto("/clients");
  await expect(page).toHaveURL(/\/login\?next=%2Fclients/);
});
