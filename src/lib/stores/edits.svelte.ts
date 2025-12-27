/**
 * Edits Store - Manages PDF content editing operations
 *
 * Key design decisions:
 * 1. Normalized coordinates [0..1] - Rects use values 0-1 relative to page
 * 2. EditorOps as declarative log - Operations stored as JSON, applied on export
 * 3. Sidecar JSON persistence - .{filename}.editor.json alongside PDF
 * 4. Edit/Annotation modes mutually exclusive
 */

import { getContext, setContext } from 'svelte';

// Normalized rect (0-1 range, page-relative)
export interface NormalizedRect {
  x: number;      // 0-1
  y: number;      // 0-1
  width: number;  // 0-1
  height: number; // 0-1
}

export interface TextStyle {
  fontFamily: string;
  fontSize: number;
  color: string;
  bold?: boolean;
  italic?: boolean;
  align?: 'left' | 'center' | 'right';
  rotation?: number;  // Text rotation in degrees (from scanned document detection)
}

// Base operation with common fields
interface BaseOp {
  id: string;
  type: string;
  page: number;
  rect: NormalizedRect;
  createdAt: number;
}

export interface InsertTextOp extends BaseOp {
  type: 'insert_text';
  text: string;
  style: TextStyle;
}

// Original line info for precise positioning during Apply
export interface OriginalLineInfo {
  text: string;
  rect: NormalizedRect;  // Original line position (normalized)
}

export interface ReplaceTextOp extends BaseOp {
  type: 'replace_text';  // Implemented as: redact original + insert new
  originalText?: string;
  originalLines?: OriginalLineInfo[];  // Store original line positions
  text: string;
  style: TextStyle;
}

export interface DeleteTextOp extends BaseOp {
  type: 'delete_text';
  originalText?: string;
}

export interface InsertImageOp extends BaseOp {
  type: 'insert_image';
  imagePath?: string;     // File path
  imageData?: string;     // Base64 for embedded
  keepAspect: boolean;
}

export interface ReplaceImageOp extends BaseOp {
  type: 'replace_image';
  imagePath?: string;
  imageData?: string;
  keepAspect: boolean;
}

export interface DeleteImageOp extends BaseOp {
  type: 'delete_image';
}

export interface DrawShapeOp extends BaseOp {
  type: 'draw_shape';
  shape: 'rect' | 'ellipse' | 'line';
  strokeColor: string;
  strokeWidth: number;
  fillColor?: string;
  fillOpacity?: number;
}

export type EditorOp =
  | InsertTextOp
  | ReplaceTextOp
  | DeleteTextOp
  | InsertImageOp
  | ReplaceImageOp
  | DeleteImageOp
  | DrawShapeOp;

// Document format for sidecar JSON
export interface EditorOpsDocument {
  version: 1;
  pdfPath: string;
  ops: EditorOp[];
  lastModified: number;
}

export type EditTool =
  | 'select'
  | 'text'
  | 'image'
  | 'shape-rect'
  | 'shape-ellipse'
  | 'line'
  | null;

// Granularity for text editing: block (paragraph), line, or word
export type EditGranularity = 'block' | 'line' | 'word';

export interface EditsStore {
  // State
  ops: EditorOp[];
  activeTool: EditTool;
  editGranularity: EditGranularity;
  selectedId: string | null;
  isDirty: boolean;
  isApplying: boolean;

  // Getters
  getOpsForPage(page: number): EditorOp[];
  getOpById(id: string): EditorOp | undefined;
  hasOps: boolean;
  opCount: number;

  // Tool state
  activeTextStyle: TextStyle;
  activeStrokeColor: string;
  activeStrokeWidth: number;
  activeFillColor: string;
  activeFillEnabled: boolean;

  // Actions
  setActiveTool(tool: EditTool): void;
  setEditGranularity(granularity: EditGranularity): void;
  selectOp(id: string | null): void;

  addOp<T extends EditorOp>(op: Omit<T, 'id' | 'createdAt'>): T;
  updateOp(id: string, patch: Partial<EditorOp>): void;
  removeOp(id: string): void;
  clearOps(): void;
  clearPage(page: number): void;

  // Style setters
  setTextStyle(style: Partial<TextStyle>): void;
  setStrokeColor(color: string): void;
  setStrokeWidth(width: number): void;
  setFillColor(color: string): void;
  setFillEnabled(enabled: boolean): void;

  // Persistence
  loadFromJson(json: string): void;
  toJson(pdfPath: string): string;

  // Undo/Redo
  undo(): void;
  redo(): void;
  canUndo(): boolean;
  canRedo(): boolean;

  // Apply
  setApplying(value: boolean): void;
}

const EDITS_KEY = Symbol('edits');

export function createEditsStore(): EditsStore {
  let ops = $state<EditorOp[]>([]);
  let activeTool = $state<EditTool>(null);
  let editGranularity = $state<EditGranularity>('block');  // Default to block-level editing
  let selectedId = $state<string | null>(null);
  let isDirty = $state(false);
  let isApplying = $state(false);

  // Undo/redo stacks
  let undoStack = $state<EditorOp[][]>([]);
  let redoStack = $state<EditorOp[][]>([]);

  // Default text style
  let activeTextStyle = $state<TextStyle>({
    fontFamily: 'Helvetica',
    fontSize: 12,
    color: '#000000',
    bold: false,
    italic: false,
    align: 'left',
  });

  // Shape style
  let activeStrokeColor = $state('#000000');
  let activeStrokeWidth = $state(1);
  let activeFillColor = $state('#FFFFFF');
  let activeFillEnabled = $state(false);

  function generateId(): string {
    return `edit_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
  }

  function pushUndo() {
    undoStack = [...undoStack, [...ops]];
    redoStack = []; // Clear redo on new action
  }

  return {
    get ops() { return ops; },
    get activeTool() { return activeTool; },
    get editGranularity() { return editGranularity; },
    get selectedId() { return selectedId; },
    get isDirty() { return isDirty; },
    get isApplying() { return isApplying; },

    get hasOps() { return ops.length > 0; },
    get opCount() { return ops.length; },

    get activeTextStyle() { return activeTextStyle; },
    get activeStrokeColor() { return activeStrokeColor; },
    get activeStrokeWidth() { return activeStrokeWidth; },
    get activeFillColor() { return activeFillColor; },
    get activeFillEnabled() { return activeFillEnabled; },

    getOpsForPage(page: number): EditorOp[] {
      return ops.filter(op => op.page === page);
    },

    getOpById(id: string): EditorOp | undefined {
      return ops.find(op => op.id === id);
    },

    setActiveTool(tool: EditTool): void {
      activeTool = tool;
      if (tool !== 'select') {
        selectedId = null;
      }
    },

    setEditGranularity(granularity: EditGranularity): void {
      editGranularity = granularity;
    },

    selectOp(id: string | null): void {
      selectedId = id;
    },

    addOp<T extends EditorOp>(opData: Omit<T, 'id' | 'createdAt'>): T {
      pushUndo();
      const op = {
        ...opData,
        id: generateId(),
        createdAt: Date.now(),
      } as T;
      ops = [...ops, op];
      isDirty = true;
      return op;
    },

    updateOp(id: string, patch: Partial<EditorOp>): void {
      pushUndo();
      ops = ops.map(op =>
        op.id === id ? { ...op, ...patch } as EditorOp : op
      );
      isDirty = true;
    },

    removeOp(id: string): void {
      pushUndo();
      ops = ops.filter(op => op.id !== id);
      if (selectedId === id) {
        selectedId = null;
      }
      isDirty = true;
    },

    clearOps(): void {
      if (ops.length > 0) {
        pushUndo();
        ops = [];
        selectedId = null;
        isDirty = true;
      }
    },

    clearPage(page: number): void {
      const pageOps = ops.filter(op => op.page === page);
      if (pageOps.length > 0) {
        pushUndo();
        ops = ops.filter(op => op.page !== page);
        if (selectedId && pageOps.some(op => op.id === selectedId)) {
          selectedId = null;
        }
        isDirty = true;
      }
    },

    setTextStyle(style: Partial<TextStyle>): void {
      activeTextStyle = { ...activeTextStyle, ...style };
      // Also update the currently selected text operation if there is one
      if (selectedId) {
        const op = ops.find(o => o.id === selectedId);
        if (op && (op.type === 'insert_text' || op.type === 'replace_text')) {
          const textOp = op as InsertTextOp | ReplaceTextOp;
          ops = ops.map(o =>
            o.id === selectedId
              ? { ...o, style: { ...textOp.style, ...style } } as EditorOp
              : o
          );
          isDirty = true;
        }
      }
    },

    setStrokeColor(color: string): void {
      activeStrokeColor = color;
    },

    setStrokeWidth(width: number): void {
      activeStrokeWidth = width;
    },

    setFillColor(color: string): void {
      activeFillColor = color;
    },

    setFillEnabled(enabled: boolean): void {
      activeFillEnabled = enabled;
    },

    loadFromJson(json: string): void {
      try {
        const doc = JSON.parse(json) as EditorOpsDocument;
        if (doc.version === 1 && Array.isArray(doc.ops)) {
          ops = doc.ops;
          isDirty = false;
          undoStack = [];
          redoStack = [];
        }
      } catch (e) {
        console.error('[EditsStore] Failed to load JSON:', e);
      }
    },

    toJson(pdfPath: string): string {
      const doc: EditorOpsDocument = {
        version: 1,
        pdfPath,
        ops,
        lastModified: Date.now(),
      };
      return JSON.stringify(doc, null, 2);
    },

    undo(): void {
      if (undoStack.length > 0) {
        redoStack = [...redoStack, [...ops]];
        ops = undoStack[undoStack.length - 1];
        undoStack = undoStack.slice(0, -1);
        isDirty = true;
      }
    },

    redo(): void {
      if (redoStack.length > 0) {
        undoStack = [...undoStack, [...ops]];
        ops = redoStack[redoStack.length - 1];
        redoStack = redoStack.slice(0, -1);
        isDirty = true;
      }
    },

    canUndo(): boolean {
      return undoStack.length > 0;
    },

    canRedo(): boolean {
      return redoStack.length > 0;
    },

    setApplying(value: boolean): void {
      isApplying = value;
    },
  };
}

export function setEditsStore(store: EditsStore): void {
  setContext(EDITS_KEY, store);
}

export function getEditsStore(): EditsStore {
  return getContext<EditsStore>(EDITS_KEY);
}
