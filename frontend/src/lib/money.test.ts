import { describe, expect, it } from "vitest";

import {
  centsToDollars,
  dollarsToCents,
  formatCents,
  formatQuantity,
  fractionToPercent,
  percentToFraction,
} from "./money";

describe("dollarsToCents", () => {
  it.each([
    ["65", 6500],
    ["65.5", 6550],
    ["65.50", 6550],
    ["0.01", 1],
    [" $1,234.56 ", 123456],
    ["0", 0],
  ])("%j -> %i cents", (input, cents) => {
    expect(dollarsToCents(input)).toBe(cents);
  });

  it.each(["", "abc", "-1", "65.555", "1.2.3", "$"])("rejects %j", (input) => {
    expect(dollarsToCents(input)).toBeNull();
  });

  it("is exact where float math is not", () => {
    // The trap it avoids: 19.99 * 100 is 1998.9999999999998 in JavaScript.
    expect(19.99 * 100).not.toBe(1999);
    expect(dollarsToCents("19.99")).toBe(1999);
  });
});

describe("percent <-> fraction (string math, no floats)", () => {
  it.each([
    ["0.05000", "5"],
    ["0.07000", "7"],
    ["0.04712", "4.712"],
    ["0.00000", "0"],
    ["1.00000", "100"],
  ])("fractionToPercent(%j) -> %j", (fraction, percent) => {
    expect(fractionToPercent(fraction)).toBe(percent);
  });

  it.each([
    ["5", "0.05"],
    ["7", "0.07"],
    ["7.5", "0.075"],
    ["4.712", "0.04712"],
    ["0.001", "0.00001"],
    ["100", "1"],
    ["5%", "0.05"],
    ["0", "0"],
  ])("percentToFraction(%j) -> %j", (percent, fraction) => {
    expect(percentToFraction(percent)).toBe(fraction);
  });

  it("avoids the float trap", () => {
    expect(0.07 * 100).not.toBe(7); // 7.000000000000001
    expect(fractionToPercent("0.07000")).toBe("7");
  });

  it.each(["", "abc", "7.1234", "-5"])("rejects %j", (input) => {
    expect(percentToFraction(input)).toBeNull();
  });
});

describe("formatting", () => {
  it("formats cents as currency", () => {
    expect(formatCents(48300)).toBe("$483.00");
    expect(formatCents(101325)).toBe("$1,013.25");
    expect(formatCents(0)).toBe("$0.00");
  });

  it("round-trips cents through an editable dollar string", () => {
    expect(centsToDollars(6550)).toBe("65.50");
    expect(centsToDollars(5)).toBe("0.05");
    expect(dollarsToCents(centsToDollars(123456))).toBe(123456);
  });

  it.each([
    ["3.000", "3"],
    ["5.250", "5.25"],
    ["420", "420"],
    ["0.000", "0"],
    ["10.000", "10"],
  ])("formatQuantity(%j) -> %j", (input, output) => {
    expect(formatQuantity(input)).toBe(output);
  });
});
