import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { MotionGlobalConfig } from "motion/react";
import { afterEach, vi } from "vitest";

afterEach(() => cleanup());

// Tests check behaviour, not motion: finish every animation instantly. jsdom has no
// real animation clock, so exit animations (AnimatePresence) would otherwise hang.
MotionGlobalConfig.skipAnimations = true;

// jsdom doesn't implement scrolling; Motion layout animations call it.
window.scrollTo = vi.fn() as unknown as typeof window.scrollTo;

// jsdom lacks matchMedia, which Motion consults for reduced motion.
if (!window.matchMedia) {
  Object.defineProperty(window, "matchMedia", {
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}
