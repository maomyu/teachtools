export function getEffectiveHandoutPaperIds(
  selectedPaperIds: number[],
  availablePaperIds: number[]
): number[] | undefined {
  if (availablePaperIds.length > 0 && selectedPaperIds.length === availablePaperIds.length) {
    return undefined
  }
  return selectedPaperIds
}

export function getHandoutSelectionToken(
  selectedPaperIds: number[],
  availablePaperIds: number[]
): string {
  if (availablePaperIds.length > 0 && selectedPaperIds.length === availablePaperIds.length) {
    return '__ALL__'
  }

  return [...selectedPaperIds]
    .sort((left, right) => left - right)
    .join(',')
}
