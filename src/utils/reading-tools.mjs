export function calculateReadingProgress(scrollY, articleTop, articleHeight, viewportHeight) {
  const readableDistance = articleHeight - viewportHeight;
  if (readableDistance <= 0) return scrollY >= articleTop ? 1 : 0;

  const progress = (scrollY - articleTop) / readableDistance;
  return Math.min(1, Math.max(0, progress));
}

export function shouldShowBackToTop(progress, articleHeight, viewportHeight) {
  const entryNeedsScrolling = articleHeight > viewportHeight * 1.35;
  return entryNeedsScrolling && progress >= 0.2;
}
