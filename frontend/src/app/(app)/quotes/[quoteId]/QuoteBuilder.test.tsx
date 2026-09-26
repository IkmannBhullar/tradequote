// Behavior tests for the quote builder. The real Server Actions are replaced
// by fakes (possible because the builder receives them as props), so these
// tests check what the UI sends and how it shows what comes back, without
// any server.

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ActionResult } from "@/lib/api/errors";
import type { Quote, Template } from "@/lib/api/types";
import { QuoteBuilder, type QuoteActions } from "./QuoteBuilder";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

// --- Test data --------------------------------------------------------------

const WALLS_ITEM = {
  id: "item-walls",
  name: "Walls",
  measure_type: "area" as const,
  material_name: "Interior wall paint",
  material_unit: "gallon",
  material_unit_cost_cents: 4500,
  coverage_per_material_unit: "350.000",
  waste_factor: "0.1000",
  labor_hours_per_unit: "0.00600",
  default_coats: 2,
};

const TEMPLATES: Template[] = [
  { id: "tpl", organization_id: null, trade: "painting", name: "Interior Painting", items: [WALLS_ITEM] },
];

function makeQuote(overrides: Partial<Quote> = {}): Quote {
  return {
    id: "quote-1",
    job_id: "job-1",
    version: 1,
    status: "draft",
    subtotal_cents: 0,
    tax_cents: 0,
    total_cents: 0,
    deposit_required_cents: 0,
    labor_rate_cents: 6500,
    tax_rate: "0.05000",
    sent_at: null,
    token_expires_at: null,
    approved_at: null,
    approved_by_name: null,
    declined_at: null,
    declined_by_name: null,
    decline_reason: null,
    created_at: "2026-09-25T00:00:00Z",
    areas: [],
    line_items: [],
    ...overrides,
  };
}

/** The worked example: 420 sq ft of walls -> $483.00. */
const PRICED = makeQuote({
  subtotal_cents: 46000,
  tax_cents: 2300,
  total_cents: 48300,
  areas: [
    {
      id: "area-1",
      position: 0,
      name: "Living room walls",
      measure_type: "area",
      quantity: "420.000",
      coats: 2,
      template_item_id: "item-walls",
      material_name: "Interior wall paint",
      material_unit: "gallon",
      material_unit_cost_cents: 4500,
      coverage_per_material_unit: "350.000",
      waste_factor: "0.1000",
      labor_hours_per_unit: "0.00600",
    },
  ],
  line_items: [
    {
      id: "line-material",
      area_id: "area-1",
      kind: "material",
      description: "Living room walls: Interior wall paint",
      quantity: "3.000",
      unit: "gallon",
      unit_price_cents: 4500,
      total_cents: 13500,
      is_override: false,
      override_quantity: null,
      override_unit_price_cents: null,
    },
    {
      id: "line-labor",
      area_id: "area-1",
      kind: "labor",
      description: "Living room walls: labor",
      quantity: "5.000",
      unit: "hour",
      unit_price_cents: 6500,
      total_cents: 32500,
      is_override: false,
      override_quantity: null,
      override_unit_price_cents: null,
    },
  ],
});

const LINK = { url: "http://localhost:3000/q/secret-token", expiresAt: "2026-10-25T15:00:00Z" };

const ok = (data: Quote): Promise<ActionResult<Quote>> => Promise.resolve({ ok: true, data });

function fakeActions(): QuoteActions {
  return {
    addArea: vi.fn(() => ok(PRICED)),
    updateArea: vi.fn(() => ok(PRICED)),
    deleteArea: vi.fn(() => ok(makeQuote())),
    setOverride: vi.fn(() => ok(PRICED)),
    clearOverride: vi.fn(() => ok(PRICED)),
    updateDeposit: vi.fn(() => ok(PRICED)),
    refreshRates: vi.fn(() => ok(PRICED)),
    createRevision: vi.fn(() => ok(makeQuote({ id: "quote-2", version: 2 }))),
    sendQuote: vi.fn(() =>
      Promise.resolve({
        ok: true as const,
        data: {
          quote: { ...PRICED, status: "sent" as const, sent_at: "2026-09-25T15:00:00Z", token_expires_at: LINK.expiresAt },
          link: LINK,
        },
      }),
    ),
    newShareLink: vi.fn(() => Promise.resolve({ ok: true as const, data: { ...LINK, url: "http://localhost:3000/q/new-token" } })),
  };
}

function renderBuilder(quote: Quote, actions = fakeActions()) {
  render(<QuoteBuilder initialQuote={quote} templates={TEMPLATES} actions={actions} />);
  return { actions, user: userEvent.setup() };
}

const total = () => screen.getByTestId("total");

beforeEach(() => {
  push.mockReset();
  // The builder asks "are you sure?" before sending; answer yes by default.
  vi.spyOn(window, "confirm").mockReturnValue(true);
});

// --- Tests ------------------------------------------------------------------

describe("QuoteBuilder", () => {
  it("adding an area sends exact strings and shows the server's totals", async () => {
    const { actions, user } = renderBuilder(makeQuote());
    expect(total()).toHaveTextContent("$0.00");

    await user.selectOptions(screen.getByRole("combobox"), "item-walls");
    await user.type(screen.getByLabelText("Area name"), "Living room walls");
    await user.type(screen.getByLabelText(/^Quantity/), "420");
    await user.click(screen.getByRole("button", { name: "Add area" }));

    expect(actions.addArea).toHaveBeenCalledWith("quote-1", {
      template_item_id: "item-walls",
      name: "Living room walls",
      quantity: "420", // a string, never a float
      coats: null, // empty -> the template's default
    });
    // Live totals come from the action's result, not from browser math.
    expect(await screen.findByText("$483.00")).toBe(total());
    expect(screen.getByText("Living room walls: Interior wall paint")).toBeInTheDocument();
  });

  it("uses the item name when the area name is left empty", async () => {
    const { actions, user } = renderBuilder(makeQuote());
    await user.selectOptions(screen.getByRole("combobox"), "item-walls");
    await user.type(screen.getByLabelText(/^Quantity/), "100");
    await user.click(screen.getByRole("button", { name: "Add area" }));

    expect(actions.addArea).toHaveBeenCalledWith("quote-1", expect.objectContaining({ name: "Walls" }));
  });

  it("saves an area field on blur, but only when it changed", async () => {
    const { actions, user } = renderBuilder(PRICED);
    const quantity = screen.getByLabelText("Quantity of Living room walls");

    await user.click(quantity);
    await user.tab(); // unchanged
    expect(actions.updateArea).not.toHaveBeenCalled();

    await user.clear(quantity);
    await user.type(quantity, "840");
    await user.tab();
    expect(actions.updateArea).toHaveBeenCalledWith("quote-1", "area-1", { quantity: "840" });
  });

  it("sends an override and validates the price locally first", async () => {
    const { actions, user } = renderBuilder(PRICED);
    const materialRow = screen.getByText("Living room walls: Interior wall paint").closest("tr")!;
    await user.click(within(materialRow).getByRole("button", { name: "Override" }));

    await user.type(screen.getByLabelText("Unit price ($)"), "not money");
    await user.click(screen.getByRole("button", { name: "Save override" }));
    expect(screen.getByText(/enter a price/i)).toBeInTheDocument();
    expect(actions.setOverride).not.toHaveBeenCalled();

    await user.clear(screen.getByLabelText("Unit price ($)"));
    await user.type(screen.getByLabelText("Quantity (gallon)"), "7");
    await user.click(screen.getByRole("button", { name: "Save override" }));
    expect(actions.setOverride).toHaveBeenCalledWith("quote-1", "line-material", {
      quantity: "7",
      unit_price_cents: null,
    });
  });

  it("shows the server's error message when an action fails", async () => {
    const actions = fakeActions();
    actions.updateDeposit = vi.fn(() =>
      Promise.resolve({ ok: false as const, error: "Deposit can't be more than the quote total" }),
    );
    const { user } = renderBuilder(PRICED, actions);

    const deposit = screen.getByLabelText("Deposit required ($)");
    await user.clear(deposit);
    await user.type(deposit, "999999");
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(actions.updateDeposit).toHaveBeenCalledWith("quote-1", 99999900);
    expect(await screen.findByRole("alert")).toHaveTextContent("Deposit can't be more than the quote total");
    expect(total()).toHaveTextContent("$483.00"); // unchanged
  });

  it("is read-only once sent, and offers a revision instead", async () => {
    const { actions, user } = renderBuilder({ ...PRICED, status: "sent" });

    expect(screen.getByText(/can't be edited/)).toBeInTheDocument();
    expect(screen.getByLabelText("Quantity of Living room walls")).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Add area" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Override" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Create revision" }));
    expect(actions.createRevision).toHaveBeenCalledWith("quote-1");
    expect(push).toHaveBeenCalledWith("/quotes/quote-2");
  });

  it("sends the quote and shows the client link once", async () => {
    const { actions, user } = renderBuilder(PRICED);

    await user.click(screen.getByRole("button", { name: "Send to client" }));

    expect(actions.sendQuote).toHaveBeenCalledWith("quote-1");
    expect(await screen.findByLabelText("Client link")).toHaveValue("http://localhost:3000/q/secret-token");
    expect(screen.getByText(/only shown once/)).toBeInTheDocument();
    // Now sent: read-only, with a way to issue a new link.
    expect(screen.queryByRole("button", { name: "Send to client" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "New client link" })).toBeInTheDocument();
  });

  it("does nothing if the user cancels sending", async () => {
    vi.mocked(window.confirm).mockReturnValue(false);
    const { actions, user } = renderBuilder(PRICED);

    await user.click(screen.getByRole("button", { name: "Send to client" }));

    expect(actions.sendQuote).not.toHaveBeenCalled();
  });

  it("can't send an empty quote", () => {
    renderBuilder(makeQuote());
    expect(screen.getByRole("button", { name: "Send to client" })).toBeDisabled();
  });

  it("shows who approved the quote", () => {
    renderBuilder({ ...PRICED, status: "approved", sent_at: "2026-09-25T15:00:00Z", approved_at: "2026-09-26T15:00:00Z", approved_by_name: "Jane Homeowner" });
    expect(screen.getByText("Jane Homeowner")).toBeInTheDocument();
    expect(screen.getByText(/Approved by/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Download PDF" })).toHaveAttribute("href", "/quotes/quote-1/pdf");
  });
});
