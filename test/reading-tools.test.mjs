import assert from "node:assert/strict";
import test from "node:test";
import { calculateReadingProgress, shouldShowBackToTop } from "../src/utils/reading-tools.mjs";

test("reading progress is zero before reaching the entry", () => {
  assert.equal(calculateReadingProgress(50, 100, 2000, 1000), 0);
});

test("reading progress tracks the entry and clamps at completion", () => {
  assert.equal(calculateReadingProgress(600, 100, 2000, 1000), 0.5);
  assert.equal(calculateReadingProgress(1500, 100, 2000, 1000), 1);
});

test("a short entry reports complete once it reaches the viewport", () => {
  assert.equal(calculateReadingProgress(100, 100, 700, 1000), 1);
});

test("back to top only appears for long entries after meaningful progress", () => {
  assert.equal(shouldShowBackToTop(0.19, 2000, 1000), false);
  assert.equal(shouldShowBackToTop(0.2, 2000, 1000), true);
  assert.equal(shouldShowBackToTop(0.8, 1200, 1000), false);
});
