// Friendly names for the generated API types (see schema.d.ts, generated
// from the backend's OpenAPI schema by `npm run gen:api`; never edit it).
import type { components } from "./schema";

type Schemas = components["schemas"];

export type Quote = Schemas["QuoteOut"];
export type QuoteSummary = Schemas["QuoteSummaryOut"];
export type Area = Schemas["AreaOut"];
export type LineItem = Schemas["LineItemOut"];
export type Job = Schemas["JobOut"];
export type JobStatus = Schemas["JobStatus"];
export type Client = Schemas["ClientOut"];
export type Template = Schemas["TemplateOut"];
export type Organization = Schemas["OrganizationOut"];
export type Me = Schemas["MeResponse"];
