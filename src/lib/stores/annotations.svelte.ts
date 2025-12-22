/**
 * Annotations Store
 *
 * Manages PDF annotations (highlights, comments, drawings) in memory.
 * Future: persist to PDF or external storage.
 */

import { getContext, setContext } from 'svelte';

export type AnnotationType = 'highlight' | 'comment' | 'underline' | 'strikethrough' | 'freetext';

export interface Point {
  x: number;
  y: number;
}

export interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface Annotation {
  id: string;
  type: AnnotationType;
  page: number;
  rect: Rect;
  color: string;
  opacity: number;
  text?: string; // For comments
  createdAt: Date;
  modifiedAt: Date;
}

export interface AnnotationsState {
  annotations: Map<number, Annotation[]>; // page -> annotations
  selectedId: string | null;
  activeTool: AnnotationType | null;
  activeColor: string;
}

const ANNOTATION_KEY = Symbol('annotations');

export function createAnnotationsStore() {
  let state = $state<AnnotationsState>({
    annotations: new Map(),
    selectedId: null,
    activeTool: null,
    activeColor: '#FFEB3B', // Default yellow for highlights
  });

  function generateId(): string {
    return `ann-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  function addAnnotation(annotation: Omit<Annotation, 'id' | 'createdAt' | 'modifiedAt'>): Annotation {
    const now = new Date();
    const newAnnotation: Annotation = {
      ...annotation,
      id: generateId(),
      createdAt: now,
      modifiedAt: now,
    };

    const pageAnnotations = state.annotations.get(annotation.page) || [];
    state.annotations.set(annotation.page, [...pageAnnotations, newAnnotation]);
    state.annotations = new Map(state.annotations); // Trigger reactivity

    return newAnnotation;
  }

  function updateAnnotation(id: string, updates: Partial<Omit<Annotation, 'id' | 'createdAt'>>): void {
    state.annotations.forEach((pageAnns, page) => {
      const idx = pageAnns.findIndex(a => a.id === id);
      if (idx !== -1) {
        pageAnns[idx] = {
          ...pageAnns[idx],
          ...updates,
          modifiedAt: new Date(),
        };
        state.annotations.set(page, [...pageAnns]);
        state.annotations = new Map(state.annotations);
      }
    });
  }

  function deleteAnnotation(id: string): void {
    state.annotations.forEach((pageAnns, page) => {
      const filtered = pageAnns.filter(a => a.id !== id);
      if (filtered.length !== pageAnns.length) {
        state.annotations.set(page, filtered);
        state.annotations = new Map(state.annotations);
      }
    });

    if (state.selectedId === id) {
      state.selectedId = null;
    }
  }

  function getAnnotationsForPage(page: number): Annotation[] {
    return state.annotations.get(page) || [];
  }

  function selectAnnotation(id: string | null): void {
    state.selectedId = id;
  }

  function setActiveTool(tool: AnnotationType | null): void {
    state.activeTool = tool;
    if (tool) {
      state.selectedId = null; // Deselect when switching tools
    }
  }

  function setActiveColor(color: string): void {
    state.activeColor = color;
  }

  function clearAnnotations(page?: number): void {
    if (page !== undefined) {
      state.annotations.delete(page);
    } else {
      state.annotations.clear();
    }
    state.annotations = new Map(state.annotations);
    state.selectedId = null;
  }

  function getAllAnnotations(): Annotation[] {
    const all: Annotation[] = [];
    state.annotations.forEach(pageAnns => {
      all.push(...pageAnns);
    });
    return all.sort((a, b) => a.page - b.page);
  }

  function exportAnnotations(): object {
    const exported: Record<number, Annotation[]> = {};
    state.annotations.forEach((pageAnns, page) => {
      exported[page] = pageAnns;
    });
    return exported;
  }

  function importAnnotations(data: Record<number, Annotation[]>): void {
    state.annotations.clear();
    Object.entries(data).forEach(([page, anns]) => {
      state.annotations.set(Number(page), anns);
    });
    state.annotations = new Map(state.annotations);
  }

  return {
    get state() { return state; },
    get annotations() { return state.annotations; },
    get selectedId() { return state.selectedId; },
    get activeTool() { return state.activeTool; },
    get activeColor() { return state.activeColor; },

    addAnnotation,
    updateAnnotation,
    deleteAnnotation,
    getAnnotationsForPage,
    selectAnnotation,
    setActiveTool,
    setActiveColor,
    clearAnnotations,
    getAllAnnotations,
    exportAnnotations,
    importAnnotations,
  };
}

export type AnnotationsStore = ReturnType<typeof createAnnotationsStore>;

export function setAnnotationsContext(store: AnnotationsStore) {
  setContext(ANNOTATION_KEY, store);
}

export function getAnnotationsContext(): AnnotationsStore {
  return getContext(ANNOTATION_KEY);
}

// Color presets for annotations
export const HIGHLIGHT_COLORS = [
  { name: 'Yellow', value: '#FFEB3B' },
  { name: 'Green', value: '#4CAF50' },
  { name: 'Blue', value: '#2196F3' },
  { name: 'Pink', value: '#E91E63' },
  { name: 'Orange', value: '#FF9800' },
  { name: 'Purple', value: '#9C27B0' },
];

export const COMMENT_COLORS = [
  { name: 'Yellow', value: '#FFC107' },
  { name: 'Blue', value: '#03A9F4' },
  { name: 'Green', value: '#8BC34A' },
  { name: 'Red', value: '#F44336' },
];
