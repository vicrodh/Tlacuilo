/**
 * Redactions Store
 *
 * Manages pending redaction marks before they are permanently applied.
 * Redactions are destructive - they permanently remove content from the PDF.
 */

import { getContext, setContext } from 'svelte';

export interface RedactionMark {
  id: string;
  page: number;
  rect: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  fillColor: string;
  createdAt: number;
}

export interface RedactionsStore {
  // State
  marks: RedactionMark[];
  isApplying: boolean;

  // Getters
  getMarksForPage(page: number): RedactionMark[];
  hasMarks: boolean;
  markCount: number;

  // Actions
  addMark(page: number, rect: RedactionMark['rect']): RedactionMark;
  removeMark(id: string): void;
  clearMarks(): void;
  clearPage(page: number): void;
  setApplying(value: boolean): void;
}

const REDACTIONS_KEY = Symbol('redactions');

export function createRedactionsStore(): RedactionsStore {
  let marks = $state<RedactionMark[]>([]);
  let isApplying = $state(false);

  function generateId(): string {
    return `redact_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
  }

  return {
    get marks() { return marks; },
    get isApplying() { return isApplying; },

    get hasMarks() { return marks.length > 0; },
    get markCount() { return marks.length; },

    getMarksForPage(page: number): RedactionMark[] {
      return marks.filter(m => m.page === page);
    },

    addMark(page: number, rect: RedactionMark['rect']): RedactionMark {
      const mark: RedactionMark = {
        id: generateId(),
        page,
        rect,
        fillColor: '#000000',
        createdAt: Date.now(),
      };
      marks = [...marks, mark];
      return mark;
    },

    removeMark(id: string): void {
      marks = marks.filter(m => m.id !== id);
    },

    clearMarks(): void {
      marks = [];
    },

    clearPage(page: number): void {
      marks = marks.filter(m => m.page !== page);
    },

    setApplying(value: boolean): void {
      isApplying = value;
    },
  };
}

export function setRedactionsStore(store: RedactionsStore): void {
  setContext(REDACTIONS_KEY, store);
}

export function getRedactionsStore(): RedactionsStore {
  return getContext<RedactionsStore>(REDACTIONS_KEY);
}
