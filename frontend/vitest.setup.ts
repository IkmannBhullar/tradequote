// Adds DOM matchers like expect(element).toBeDisabled().
import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Unmount rendered components between tests so they can't interfere.
afterEach(() => cleanup());
