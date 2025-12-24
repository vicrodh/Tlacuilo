<script lang="ts">
  import {
    getFieldsForPage,
    getFieldValue,
    updateFieldValue,
    getWebFont,
    colorToCSS,
    type FormField
  } from '$lib/stores/forms.svelte';

  interface Props {
    page: number;              // 1-indexed page number from viewer
    pageWidth: number;         // Rendered width in pixels
    pageHeight: number;        // Rendered height in pixels
    pdfPageWidth: number;      // Original PDF width in points
    pdfPageHeight: number;     // Original PDF height in points
    formModeEnabled: boolean;
  }

  let { page, pageWidth, pageHeight, pdfPageWidth, pdfPageHeight, formModeEnabled }: Props = $props();

  // Get fields for this page (Python uses 0-indexed pages)
  const pageFields = $derived(getFieldsForPage(page - 1));

  // Scale factor from PDF points to rendered pixels
  const scaleX = $derived(pageWidth / pdfPageWidth);
  const scaleY = $derived(pageHeight / pdfPageHeight);

  // Convert PDF rect to CSS position
  // PyMuPDF rect is [x0, y0, x1, y1] where origin is TOP-LEFT (same as CSS)
  function rectToStyle(rect: [number, number, number, number]) {
    const [x0, y0, x1, y1] = rect;

    // Scale from PDF points to rendered pixels (no Y-flip needed, PyMuPDF uses top-left origin)
    const left = x0 * scaleX;
    const top = y0 * scaleY;
    const width = (x1 - x0) * scaleX;
    const height = (y1 - y0) * scaleY;

    return {
      left: `${left}px`,
      top: `${top}px`,
      width: `${width}px`,
      height: `${height}px`,
    };
  }

  // Get input style for a field
  function getInputStyle(field: FormField): string {
    const pos = rectToStyle(field.rect);
    const font = getWebFont((field as any).text_font);
    const fontSize = (field as any).text_fontsize || 0;
    const textColor = colorToCSS((field as any).text_color);
    const bgColor = colorToCSS((field as any).fill_color);

    let style = `
      position: absolute;
      left: ${pos.left};
      top: ${pos.top};
      width: ${pos.width};
      height: ${pos.height};
      font-family: ${font};
      color: ${textColor};
      background-color: ${bgColor === 'inherit' ? 'transparent' : bgColor};
      border: none;
      outline: none;
      padding: 2px 4px;
      box-sizing: border-box;
    `;

    // Auto or fixed font size (scale from PDF points to pixels)
    if (fontSize > 0) {
      style += `font-size: ${fontSize * scaleY}px;`;
    } else {
      // Auto-size based on height
      const height = (field.rect[3] - field.rect[1]) * scaleY;
      style += `font-size: ${Math.max(10, height * 0.7)}px;`;
    }

    return style;
  }

  // Handle text input change
  function handleTextChange(field: FormField, event: Event) {
    const target = event.target as HTMLInputElement | HTMLTextAreaElement;
    updateFieldValue(field.name, target.value);
  }

  // Handle checkbox change
  function handleCheckboxChange(field: FormField, event: Event) {
    const target = event.target as HTMLInputElement;
    updateFieldValue(field.name, target.checked ? field.on_state : false);
  }

  // Handle select change
  function handleSelectChange(field: FormField, event: Event) {
    const target = event.target as HTMLSelectElement;
    updateFieldValue(field.name, target.value);
  }

  // Get current display value for a field
  function getDisplayValue(field: FormField): string {
    const value = getFieldValue(field);
    if (value === null || value === undefined) return '';
    return String(value);
  }

  // Check if checkbox is checked
  function isChecked(field: FormField): boolean {
    const value = getFieldValue(field);
    return value === field.on_state || value === true;
  }
</script>

{#if formModeEnabled && pageFields.length > 0}
  <div
    class="absolute inset-0 pointer-events-none"
    style="z-index: 20;"
  >
    {#each pageFields as field (field.name)}
      {#if !field.read_only}
        {#if field.field_type === 'text'}
          <!-- Text Field -->
          {#if field.multiline}
            <textarea
              class="form-field-input pointer-events-auto resize-none"
              style={getInputStyle(field)}
              value={getDisplayValue(field)}
              oninput={(e) => handleTextChange(field, e)}
              maxlength={field.max_length || undefined}
              placeholder=""
            ></textarea>
          {:else}
            <input
              type="text"
              class="form-field-input pointer-events-auto"
              style={getInputStyle(field)}
              value={getDisplayValue(field)}
              oninput={(e) => handleTextChange(field, e)}
              maxlength={field.max_length || undefined}
            />
          {/if}
        {:else if field.field_type === 'checkbox'}
          <!-- Checkbox -->
          {@const pos = rectToStyle(field.rect)}
          <div
            class="absolute flex items-center justify-center pointer-events-auto"
            style="left: {pos.left}; top: {pos.top}; width: {pos.width}; height: {pos.height};"
          >
            <input
              type="checkbox"
              class="form-field-checkbox"
              checked={isChecked(field)}
              onchange={(e) => handleCheckboxChange(field, e)}
              style="width: 100%; height: 100%; cursor: pointer; accent-color: var(--nord8);"
            />
          </div>
        {:else if field.field_type === 'radiobutton'}
          <!-- Radio Button -->
          {@const pos = rectToStyle(field.rect)}
          <div
            class="absolute flex items-center justify-center pointer-events-auto"
            style="left: {pos.left}; top: {pos.top}; width: {pos.width}; height: {pos.height};"
          >
            <input
              type="radio"
              class="form-field-radio"
              name={field.name.split('.')[0]}
              checked={isChecked(field)}
              onchange={(e) => handleCheckboxChange(field, e)}
              style="width: 100%; height: 100%; cursor: pointer; accent-color: var(--nord8);"
            />
          </div>
        {:else if field.field_type === 'combobox' || field.field_type === 'listbox'}
          <!-- Dropdown / List -->
          {@const pos = rectToStyle(field.rect)}
          <select
            class="form-field-select pointer-events-auto"
            style="
              position: absolute;
              left: {pos.left};
              top: {pos.top};
              width: {pos.width};
              height: {pos.height};
              font-family: {getWebFont((field as any).text_font)};
              border: none;
              outline: none;
              background-color: transparent;
              cursor: pointer;
            "
            value={getDisplayValue(field)}
            onchange={(e) => handleSelectChange(field, e)}
          >
            <option value="">-- Select --</option>
            {#each field.choices || [] as choice}
              <option value={choice}>{choice}</option>
            {/each}
          </select>
        {/if}
      {:else}
        <!-- Read-only field indicator -->
        {@const pos = rectToStyle(field.rect)}
        <div
          class="absolute opacity-30 pointer-events-none"
          style="
            left: {pos.left};
            top: {pos.top};
            width: {pos.width};
            height: {pos.height};
            background-color: var(--nord3);
            border-radius: 2px;
          "
          title="Read-only field"
        ></div>
      {/if}
    {/each}
  </div>
{/if}

<style>
  .form-field-input {
    transition: box-shadow 0.15s ease;
  }

  .form-field-input:focus {
    box-shadow: 0 0 0 2px var(--nord8);
    background-color: rgba(136, 192, 208, 0.1) !important;
  }

  .form-field-input:hover:not(:focus) {
    background-color: rgba(136, 192, 208, 0.05) !important;
  }

  .form-field-select:focus {
    box-shadow: 0 0 0 2px var(--nord8);
  }
</style>
