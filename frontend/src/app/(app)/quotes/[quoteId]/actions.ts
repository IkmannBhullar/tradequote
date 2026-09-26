"use server";

// Quote builder actions. Each returns the whole recalculated quote from the
// backend, which is how the builder gets live totals. Ids arrive from the
// browser and can be tampered with; that's fine, because FastAPI checks every
// id against the logged-in user's organization (other orgs' ids are 404s).

import { api, toActionResult } from "@/lib/api/client";
import type { ActionResult } from "@/lib/api/errors";
import type { Quote } from "@/lib/api/types";

export type AreaInput = { template_item_id: string; name: string; quantity: string; coats: number | null };
export type AreaChanges = { name?: string; quantity?: string; coats?: number };
export type OverrideInput = { quantity: string | null; unit_price_cents: number | null };

const quotePath = (quoteId: string) => ({ params: { path: { quote_id: quoteId } } });

export async function addArea(quoteId: string, input: AreaInput): Promise<ActionResult<Quote>> {
  return toActionResult(await (await api()).POST("/quotes/{quote_id}/areas", { ...quotePath(quoteId), body: input }));
}

export async function updateArea(quoteId: string, areaId: string, changes: AreaChanges): Promise<ActionResult<Quote>> {
  return toActionResult(
    await (await api()).PATCH("/quotes/{quote_id}/areas/{area_id}", {
      params: { path: { quote_id: quoteId, area_id: areaId } },
      body: changes,
    }),
  );
}

export async function deleteArea(quoteId: string, areaId: string): Promise<ActionResult<Quote>> {
  return toActionResult(
    await (await api()).DELETE("/quotes/{quote_id}/areas/{area_id}", {
      params: { path: { quote_id: quoteId, area_id: areaId } },
    }),
  );
}

export async function setOverride(quoteId: string, lineId: string, input: OverrideInput): Promise<ActionResult<Quote>> {
  return toActionResult(
    await (await api()).PUT("/quotes/{quote_id}/line-items/{line_id}/override", {
      params: { path: { quote_id: quoteId, line_id: lineId } },
      body: input,
    }),
  );
}

export async function clearOverride(quoteId: string, lineId: string): Promise<ActionResult<Quote>> {
  return toActionResult(
    await (await api()).DELETE("/quotes/{quote_id}/line-items/{line_id}/override", {
      params: { path: { quote_id: quoteId, line_id: lineId } },
    }),
  );
}

export async function updateDeposit(quoteId: string, cents: number): Promise<ActionResult<Quote>> {
  return toActionResult(
    await (await api()).PATCH("/quotes/{quote_id}", { ...quotePath(quoteId), body: { deposit_required_cents: cents } }),
  );
}

export async function refreshRates(quoteId: string): Promise<ActionResult<Quote>> {
  return toActionResult(await (await api()).POST("/quotes/{quote_id}/refresh-rates", quotePath(quoteId)));
}

export async function createRevision(quoteId: string): Promise<ActionResult<Quote>> {
  return toActionResult(await (await api()).POST("/quotes/{quote_id}/revisions", quotePath(quoteId)));
}
