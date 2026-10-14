import "@testing-library/jest-dom/vitest";
import "fake-indexeddb/auto";
import { vi } from "vitest";
Object.defineProperty(window,"matchMedia",{value:vi.fn().mockImplementation(() => ({matches:false,addEventListener:vi.fn(),removeEventListener:vi.fn()}))});
globalThis.ResizeObserver=class {observe(){} unobserve(){} disconnect(){}};
Element.prototype.scrollTo=vi.fn();
