/**
 * Annotations Store
 *
 * Manages PDF annotations (highlights, comments, drawings) in memory.
 * Future: persist to PDF or external storage.
 */

import { getContext, setContext } from 'svelte';

// Base annotation types + new shape/drawing types
export type AnnotationType =
  | 'highlight' | 'comment' | 'underline' | 'strikethrough' | 'freetext'
  | 'ink' | 'rectangle' | 'ellipse' | 'line' | 'arrow' | 'sequenceNumber';

// Markup types that can be applied via text or area selection
export type MarkupType = 'highlight' | 'underline' | 'strikethrough';

// Tool modes: selection modes + standalone tools + drawing tools
export type ToolMode =
  | 'text-select'   // Select text to apply markup
  | 'area-select'   // Draw area to apply markup
  | 'comment'       // Place comment icons
  | 'freetext'      // Typewriter tool
  | 'ink'           // Freehand drawing
  | 'rectangle'     // Rectangle shape
  | 'ellipse'       // Ellipse/circle shape
  | 'line'          // Line
  | 'arrow'         // Arrow
  | 'sequenceNumber' // Numbered circles
  | 'move'          // Move/drag annotations
  | null;           // No tool active (pointer mode)

// Line style options
export type LineStyle = 'solid' | 'dashed' | 'dotted';

// Arrow head style
export type ArrowHeadStyle = 'none' | 'open' | 'closed';

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

// Path for ink/freehand annotations
export interface InkPath {
  points: Point[];
  strokeWidth: number;
  color: string;
}

// Fill options for shapes
export interface ShapeFill {
  enabled: boolean;
  color: string;
  opacity: number;
}

export interface Annotation {
  id: string;
  type: AnnotationType;
  page: number;
  rect: Rect;
  color: string;
  opacity: number;
  text?: string;                // For comments and freetext
  fontsize?: number;            // For freetext (in PDF points)
  createdAt: Date;
  modifiedAt: Date;
  author?: string;              // Author attribution
  // Ink annotation specific
  paths?: InkPath[];            // Array of paths for ink annotations
  // Shape annotation specific
  fill?: ShapeFill;             // Fill settings for shapes
  lineStyle?: LineStyle;        // Line style (solid/dashed/dotted)
  strokeWidth?: number;         // Stroke width in normalized units
  // Arrow specific
  startArrow?: ArrowHeadStyle;
  endArrow?: ArrowHeadStyle;
  // Line/arrow endpoints (normalized 0-1)
  startPoint?: Point;
  endPoint?: Point;
  // Sequence number specific
  sequenceNumber?: number;      // The number to display
}

export interface AnnotationsState {
  annotations: Map<number, Annotation[]>; // page -> annotations
  selectedId: string | null;
  activeTool: ToolMode;
  activeColor: string;
  activeOpacity: number; // 0-1 opacity for new annotations
  // Pending markup type to apply (for text-select and area-select modes)
  pendingMarkupType: MarkupType;
  // Sequence number counter
  sequenceCounter: number;
  // Line/shape style settings
  activeLineStyle: LineStyle;
  activeStartArrow: ArrowHeadStyle;
  activeEndArrow: ArrowHeadStyle;
  // Shape fill settings
  activeFillEnabled: boolean;
  activeFillColor: string;
  activeFillOpacity: number;
}

// History action types for undo/redo
type HistoryAction =
  | { type: 'add'; annotation: Annotation }
  | { type: 'delete'; annotation: Annotation }
  | { type: 'update'; id: string; oldState: Partial<Annotation>; newState: Partial<Annotation> }
  | { type: 'clear'; annotations: Annotation[] };

const ANNOTATION_KEY = Symbol('annotations');
const MAX_HISTORY_SIZE = 50;

export function createAnnotationsStore() {
  let state = $state<AnnotationsState>({
    annotations: new Map(),
    selectedId: null,
    activeTool: null,
    activeColor: '#FFEB3B', // Default yellow for markup tools (typewriter switches to black)
    activeOpacity: 1, // Default full opacity
    pendingMarkupType: 'highlight', // Default markup type
    sequenceCounter: 1, // Starting sequence number
    activeLineStyle: 'solid', // Default line style
    activeStartArrow: 'none', // Default start arrow
    activeEndArrow: 'closed', // Default end arrow (for arrow tool)
    activeFillEnabled: false, // Default no fill
    activeFillColor: '#FFEB3B', // Default fill color (same as stroke)
    activeFillOpacity: 0.3, // Default fill opacity
  });

  // Undo/Redo history
  let undoStack: HistoryAction[] = [];
  let redoStack: HistoryAction[] = [];

  function pushToHistory(action: HistoryAction) {
    undoStack.push(action);
    if (undoStack.length > MAX_HISTORY_SIZE) {
      undoStack.shift();
    }
    // Clear redo stack when new action is performed
    redoStack = [];
  }

  function generateId(): string {
    return `ann-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  function addAnnotation(annotation: Omit<Annotation, 'id' | 'createdAt' | 'modifiedAt'>, skipHistory = false): Annotation {
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

    if (!skipHistory) {
      pushToHistory({ type: 'add', annotation: newAnnotation });
    }

    return newAnnotation;
  }

  // Internal: add annotation with specific ID (for redo)
  function addAnnotationWithId(annotation: Annotation, skipHistory = false): void {
    const pageAnnotations = state.annotations.get(annotation.page) || [];
    state.annotations.set(annotation.page, [...pageAnnotations, annotation]);
    state.annotations = new Map(state.annotations);

    if (!skipHistory) {
      pushToHistory({ type: 'add', annotation });
    }
  }

  function updateAnnotation(id: string, updates: Partial<Omit<Annotation, 'id' | 'createdAt'>>, skipHistory = false): void {
    state.annotations.forEach((pageAnns, page) => {
      const idx = pageAnns.findIndex(a => a.id === id);
      if (idx !== -1) {
        const oldAnnotation = pageAnns[idx];
        const oldState: Partial<Annotation> = {};
        const newState: Partial<Annotation> = {};

        // Track what changed for undo
        for (const key of Object.keys(updates) as (keyof Annotation)[]) {
          if (key !== 'id' && key !== 'createdAt') {
            oldState[key] = oldAnnotation[key] as any;
            newState[key] = updates[key as keyof typeof updates] as any;
          }
        }

        pageAnns[idx] = {
          ...pageAnns[idx],
          ...updates,
          modifiedAt: new Date(),
        };
        state.annotations.set(page, [...pageAnns]);
        state.annotations = new Map(state.annotations);

        if (!skipHistory && Object.keys(oldState).length > 0) {
          pushToHistory({ type: 'update', id, oldState, newState });
        }
      }
    });
  }

  function deleteAnnotation(id: string, skipHistory = false): void {
    let deletedAnnotation: Annotation | null = null;

    state.annotations.forEach((pageAnns, page) => {
      const annotation = pageAnns.find(a => a.id === id);
      if (annotation) {
        deletedAnnotation = annotation;
        const filtered = pageAnns.filter(a => a.id !== id);
        state.annotations.set(page, filtered);
        state.annotations = new Map(state.annotations);
      }
    });

    if (state.selectedId === id) {
      state.selectedId = null;
    }

    if (!skipHistory && deletedAnnotation) {
      pushToHistory({ type: 'delete', annotation: deletedAnnotation });
    }
  }

  function undo(): boolean {
    const action = undoStack.pop();
    if (!action) return false;

    switch (action.type) {
      case 'add':
        // Undo add = delete
        deleteAnnotation(action.annotation.id, true);
        break;
      case 'delete':
        // Undo delete = add back
        addAnnotationWithId(action.annotation, true);
        break;
      case 'update':
        // Undo update = restore old state
        updateAnnotation(action.id, action.oldState, true);
        break;
      case 'clear':
        // Undo clear = restore all deleted annotations
        for (const annotation of action.annotations) {
          addAnnotationWithId(annotation, true);
        }
        break;
    }

    redoStack.push(action);
    return true;
  }

  function redo(): boolean {
    const action = redoStack.pop();
    if (!action) return false;

    switch (action.type) {
      case 'add':
        // Redo add = add again
        addAnnotationWithId(action.annotation, true);
        break;
      case 'delete':
        // Redo delete = delete again
        deleteAnnotation(action.annotation.id, true);
        break;
      case 'update':
        // Redo update = apply new state
        updateAnnotation(action.id, action.newState, true);
        break;
      case 'clear':
        // Redo clear = delete all annotations again
        for (const annotation of action.annotations) {
          deleteAnnotation(annotation.id, true);
        }
        break;
    }

    undoStack.push(action);
    return true;
  }

  function canUndo(): boolean {
    return undoStack.length > 0;
  }

  function canRedo(): boolean {
    return redoStack.length > 0;
  }

  function getAnnotationsForPage(page: number): Annotation[] {
    return state.annotations.get(page) || [];
  }

  function selectAnnotation(id: string | null): void {
    state.selectedId = id;
  }

  // Default colors for different tool types
  const DEFAULT_FREETEXT_COLOR = '#000000'; // Black for typewriter
  const DEFAULT_MARKUP_COLOR = '#FFEB3B';   // Yellow for highlight/underline/strikethrough

  function setActiveTool(tool: ToolMode): void {
    state.activeTool = tool;
    if (tool) {
      state.selectedId = null; // Deselect when switching tools

      // Auto-switch to tool-appropriate color if using the other tool's default
      if (tool === 'freetext') {
        // Switching to typewriter: if color is yellow (markup default), change to black
        if (state.activeColor === DEFAULT_MARKUP_COLOR) {
          state.activeColor = DEFAULT_FREETEXT_COLOR;
        }
      } else if (tool === 'text-select' || tool === 'area-select') {
        // Selection modes: use markup color
        if (state.activeColor === DEFAULT_FREETEXT_COLOR) {
          state.activeColor = DEFAULT_MARKUP_COLOR;
        }
      }
    }
  }

  function setPendingMarkupType(type: MarkupType): void {
    state.pendingMarkupType = type;
    // Ensure we're using markup-appropriate color
    if (state.activeColor === DEFAULT_FREETEXT_COLOR) {
      state.activeColor = DEFAULT_MARKUP_COLOR;
    }
  }

  function setActiveColor(color: string): void {
    state.activeColor = color;
  }

  function setActiveOpacity(opacity: number): void {
    state.activeOpacity = Math.max(0, Math.min(1, opacity));
  }

  function getNextSequenceNumber(): number {
    const num = state.sequenceCounter;
    state.sequenceCounter++;
    return num;
  }

  function setSequenceCounter(value: number): void {
    state.sequenceCounter = Math.max(1, Math.floor(value));
  }

  function resetSequenceCounter(): void {
    state.sequenceCounter = 1;
  }

  function setActiveLineStyle(style: LineStyle): void {
    state.activeLineStyle = style;
  }

  function setActiveStartArrow(style: ArrowHeadStyle): void {
    state.activeStartArrow = style;
  }

  function setActiveEndArrow(style: ArrowHeadStyle): void {
    state.activeEndArrow = style;
  }

  function setActiveFillEnabled(enabled: boolean): void {
    state.activeFillEnabled = enabled;
  }

  function setActiveFillColor(color: string): void {
    state.activeFillColor = color;
  }

  function setActiveFillOpacity(opacity: number): void {
    state.activeFillOpacity = Math.max(0, Math.min(1, opacity));
  }

  function clearAnnotations(page?: number): void {
    // Collect all annotations that will be deleted for undo support
    const deletedAnnotations: Annotation[] = [];

    if (page !== undefined) {
      const pageAnns = state.annotations.get(page);
      if (pageAnns) {
        deletedAnnotations.push(...pageAnns);
      }
      state.annotations.delete(page);
    } else {
      // Collect all annotations before clearing
      state.annotations.forEach(pageAnns => {
        deletedAnnotations.push(...pageAnns);
      });
      state.annotations.clear();
    }

    state.annotations = new Map(state.annotations);
    state.selectedId = null;

    // Push to history for undo support (only if there were annotations)
    if (deletedAnnotations.length > 0) {
      pushToHistory({ type: 'clear', annotations: deletedAnnotations });
    }
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
    get activeOpacity() { return state.activeOpacity; },
    get pendingMarkupType() { return state.pendingMarkupType; },
    get sequenceCounter() { return state.sequenceCounter; },
    get activeLineStyle() { return state.activeLineStyle; },
    get activeStartArrow() { return state.activeStartArrow; },
    get activeEndArrow() { return state.activeEndArrow; },
    get activeFillEnabled() { return state.activeFillEnabled; },
    get activeFillColor() { return state.activeFillColor; },
    get activeFillOpacity() { return state.activeFillOpacity; },

    addAnnotation,
    updateAnnotation,
    deleteAnnotation,
    getAnnotationsForPage,
    selectAnnotation,
    setActiveTool,
    setPendingMarkupType,
    setActiveColor,
    setActiveOpacity,
    getNextSequenceNumber,
    setSequenceCounter,
    resetSequenceCounter,
    setActiveLineStyle,
    setActiveStartArrow,
    setActiveEndArrow,
    setActiveFillEnabled,
    setActiveFillColor,
    setActiveFillOpacity,
    clearAnnotations,
    getAllAnnotations,
    exportAnnotations,
    importAnnotations,
    // Undo/Redo
    undo,
    redo,
    canUndo,
    canRedo,
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
  { name: 'Black', value: '#000000' },
  { name: 'White', value: '#FFFFFF' },
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
