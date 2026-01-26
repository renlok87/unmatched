/**
 * Content Diff Interface
 * Represents changes between content versions
 */
export interface ContentDiff {
  oldVersion: string;
  newVersion: string;
  heroesChanged: boolean;
  boardsChanged: boolean;
  changedHeroIds?: string[];
  changedBoardIds?: string[];
}
