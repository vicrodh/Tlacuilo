/**
 * Form fields store for AcroForms handling.
 * Manages form field state, values, and sync with PDF.
 */

import { invoke } from '@tauri-apps/api/core';

// Form field types
export type FormFieldType = 'text' | 'checkbox' | 'radiobutton' | 'listbox' | 'combobox' | 'button' | 'signature' | 'unknown';

// Form field from backend
export interface FormField {
  name: string;
  field_type: FormFieldType;
  type_id: number;
  value: unknown;
  page: number;
  rect: [number, number, number, number]; // [x0, y0, x1, y1]
  read_only: boolean;
  choices?: string[];
  checked?: boolean;
  on_state?: unknown;
  max_length?: number;
  multiline?: boolean;
}

// Extended field with styling info (from Python)
export interface FormFieldWithStyle extends FormField {
  text_font?: string;
  text_fontsize?: number;
  text_color?: number[];
  fill_color?: number[];
  border_color?: number[];
}

// Form fields result from backend
interface FormFieldsResult {
  is_form: boolean;
  fields: FormField[];
  field_count: number;
}

// Form fill result
interface FormFillResult {
  success: boolean;
  filled_count: number;
  errors?: string[];
  output_path: string;
}

// Map PDF fonts to web fonts
const FONT_MAP: Record<string, string> = {
  'Helv': 'Helvetica, Arial, sans-serif',
  'Helvetica': 'Helvetica, Arial, sans-serif',
  'TiRo': 'Times New Roman, Times, serif',
  'Times': 'Times New Roman, Times, serif',
  'Cour': 'Courier New, Courier, monospace',
  'Courier': 'Courier New, Courier, monospace',
  'ZaDb': 'ZapfDingbats, sans-serif',
  'Symb': 'Symbol, sans-serif',
};

// Get web font from PDF font name
export function getWebFont(pdfFont?: string): string {
  if (!pdfFont) return 'Arial, sans-serif';
  return FONT_MAP[pdfFont] || 'Arial, sans-serif';
}

// Convert PDF color array to CSS
export function colorToCSS(color?: number[]): string {
  if (!color || color.length === 0) return 'inherit';
  if (color.length === 1) {
    // Grayscale
    const g = Math.round(color[0] * 255);
    return `rgb(${g}, ${g}, ${g})`;
  }
  if (color.length === 3) {
    // RGB
    const [r, g, b] = color.map(c => Math.round(c * 255));
    return `rgb(${r}, ${g}, ${b})`;
  }
  if (color.length === 4) {
    // CMYK - convert to RGB
    const [c, m, y, k] = color;
    const r = Math.round(255 * (1 - c) * (1 - k));
    const g = Math.round(255 * (1 - m) * (1 - k));
    const b = Math.round(255 * (1 - y) * (1 - k));
    return `rgb(${r}, ${g}, ${b})`;
  }
  return 'inherit';
}

// Reactive state
let currentFilePath = $state<string | null>(null);
let fields = $state<FormField[]>([]);
let isFormPdf = $state(false);
let isLoading = $state(false);
let modifiedValues = $state<Record<string, unknown>>({});
let formModeEnabled = $state(false);

// Load form fields for a PDF
export async function loadFormFields(filePath: string): Promise<void> {
  if (!filePath) return;

  isLoading = true;
  currentFilePath = filePath;
  modifiedValues = {};

  try {
    const result = await invoke<FormFieldsResult>('form_fields_list', { input: filePath });

    isFormPdf = result.is_form;
    fields = result.fields;

    // Auto-enable form mode if PDF has forms
    if (result.is_form && result.field_count > 0) {
      formModeEnabled = true;
    }
  } catch (err) {
    console.error('[FormsStore] Failed to load form fields:', err);
    isFormPdf = false;
    fields = [];
  } finally {
    isLoading = false;
  }
}

// Update a field value (in memory)
export function updateFieldValue(fieldName: string, value: unknown): void {
  modifiedValues = { ...modifiedValues, [fieldName]: value };
}

// Get current value for a field (modified or original)
export function getFieldValue(field: FormField): unknown {
  if (field.name in modifiedValues) {
    return modifiedValues[field.name];
  }
  return field.value;
}

// Check if field has been modified
export function isFieldModified(fieldName: string): boolean {
  return fieldName in modifiedValues;
}

// Get all modified values
export function getModifiedValues(): Record<string, unknown> {
  return { ...modifiedValues };
}

// Check if any fields have been modified
export function hasModifications(): boolean {
  return Object.keys(modifiedValues).length > 0;
}

// Save filled form to a new file
export async function saveFilledForm(outputPath: string): Promise<FormFillResult> {
  if (!currentFilePath) {
    throw new Error('No form loaded');
  }

  if (Object.keys(modifiedValues).length === 0) {
    throw new Error('No fields have been modified');
  }

  const result = await invoke<FormFillResult>('form_fields_fill', {
    input: currentFilePath,
    output: outputPath,
    fieldValues: modifiedValues,
  });

  if (result.success) {
    // Clear modifications after successful save
    modifiedValues = {};
  }

  return result;
}

// Clear all modifications
export function clearModifications(): void {
  modifiedValues = {};
}

// Toggle form mode
export function toggleFormMode(): void {
  formModeEnabled = !formModeEnabled;
}

// Set form mode
export function setFormMode(enabled: boolean): void {
  formModeEnabled = enabled;
}

// Reset store for a new document
export function resetStore(): void {
  currentFilePath = null;
  fields = [];
  isFormPdf = false;
  isLoading = false;
  modifiedValues = {};
  formModeEnabled = false;
}

// Get fields for a specific page
export function getFieldsForPage(page: number): FormField[] {
  return fields.filter(f => f.page === page);
}

// Get field by name
export function getFieldByName(name: string): FormField | undefined {
  return fields.find(f => f.name === name);
}

// Count fields by type
export function countFieldsByType(): Record<FormFieldType, number> {
  const counts: Record<FormFieldType, number> = {
    text: 0,
    checkbox: 0,
    radiobutton: 0,
    listbox: 0,
    combobox: 0,
    button: 0,
    signature: 0,
    unknown: 0,
  };

  for (const field of fields) {
    const type = field.field_type as FormFieldType;
    if (type in counts) {
      counts[type]++;
    }
  }

  return counts;
}

// Get filled/total count
export function getFilledCount(): { filled: number; total: number } {
  let filled = 0;
  for (const field of fields) {
    const value = field.name in modifiedValues ? modifiedValues[field.name] : field.value;
    if (value !== null && value !== undefined && value !== '' && value !== false) {
      filled++;
    }
  }
  return { filled, total: fields.length };
}

// Get store state (reactive)
export function getFormsStore() {
  return {
    get filePath() { return currentFilePath; },
    get fields() { return fields; },
    get isFormPdf() { return isFormPdf; },
    get isLoading() { return isLoading; },
    get formModeEnabled() { return formModeEnabled; },
    get hasModifications() { return Object.keys(modifiedValues).length > 0; },
    get modificationCount() { return Object.keys(modifiedValues).length; },
  };
}
