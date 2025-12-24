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

{#if pageFields.length > 0}
  <div
    class="absolute inset-0"
    class:pointer-events-none={!formModeEnabled}
    style="z-index: 20;"
  >
    {#each pageFields as field (field.name)}
      {#if !field.read_only}
        {#if field.field_type === 'text'}
          <!-- Text Field -->
          {#if field.multiline}
            <textarea
              class="form-field-input resize-none"
              class:pointer-events-auto={formModeEnabled}
              class:form-field-readonly={!formModeEnabled}
              style={getInputStyle(field)}
              value={getDisplayValue(field)}
              oninput={(e) => handleTextChange(field, e)}
              maxlength={field.max_length || undefined}
              placeholder=""
              readonly={!formModeEnabled}
            ></textarea>
          {:else}
            <input
              type="text"
              class="form-field-input"
              class:pointer-events-auto={formModeEnabled}
              class:form-field-readonly={!formModeEnabled}
              style={getInputStyle(field)}
              value={getDisplayValue(field)}
              oninput={(e) => handleTextChange(field, e)}
              maxlength={field.max_length || undefined}
              readonly={!formModeEnabled}
            />
          {/if}
        {:else if field.field_type === 'checkbox'}
          <!-- Checkbox -->
          {@const pos = rectToStyle(field.rect)}
          <div
            class="absolute flex items-center justify-center"
            class:pointer-events-auto={formModeEnabled}
            style="left: {pos.left}; top: {pos.top}; width: {pos.width}; height: {pos.height};"
          >
            <input
              type="checkbox"
              class="form-field-checkbox"
              checked={isChecked(field)}
              onchange={(e) => handleCheckboxChange(field, e)}
              disabled={!formModeEnabled}
              style="width: 100%; height: 100%;"
            />
          </div>
        {:else if field.field_type === 'radiobutton'}
          <!-- Radio Button -->
          {@const pos = rectToStyle(field.rect)}
          <div
            class="absolute flex items-center justify-center"
            class:pointer-events-auto={formModeEnabled}
            style="left: {pos.left}; top: {pos.top}; width: {pos.width}; height: {pos.height};"
          >
            <input
              type="radio"
              class="form-field-radio"
              name={field.name.split('.')[0]}
              checked={isChecked(field)}
              onchange={(e) => handleCheckboxChange(field, e)}
              disabled={!formModeEnabled}
              style="width: 100%; height: 100%;"
            />
          </div>
        {:else if field.field_type === 'combobox' || field.field_type === 'listbox'}
          <!-- Dropdown / List -->
          {@const pos = rectToStyle(field.rect)}
          {#if formModeEnabled}
            <select
              class="form-field-select pointer-events-auto"
              style="
                position: absolute;
                left: {pos.left};
                top: {pos.top};
                width: {pos.width};
                height: {pos.height};
                font-family: {getWebFont((field as any).text_font)};
              "
              value={getDisplayValue(field)}
              onchange={(e) => handleSelectChange(field, e)}
            >
              <option value="">-- Select --</option>
              {#each field.choices || [] as choice}
                <option value={choice}>{choice}</option>
              {/each}
            </select>
          {:else}
            <!-- Show as text when not editable -->
            <div
              class="form-field-readonly-text"
              style="
                position: absolute;
                left: {pos.left};
                top: {pos.top};
                width: {pos.width};
                height: {pos.height};
                font-family: {getWebFont((field as any).text_font)};
                display: flex;
                align-items: center;
                padding: 0 4px;
              "
            >
              {getDisplayValue(field)}
            </div>
          {/if}
        {/if}
      {:else}
        <!-- Read-only field - show value -->
        {@const pos = rectToStyle(field.rect)}
        <div
          class="form-field-readonly-text"
          style="
            position: absolute;
            left: {pos.left};
            top: {pos.top};
            width: {pos.width};
            height: {pos.height};
            display: flex;
            align-items: center;
            padding: 0 4px;
            font-family: {getWebFont((field as any).text_font)};
          "
        >
          {getDisplayValue(field)}
        </div>
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

  .form-field-input:hover:not(:focus):not(.form-field-readonly) {
    background-color: rgba(136, 192, 208, 0.05) !important;
  }

  .form-field-readonly {
    cursor: default;
    user-select: text;
    pointer-events: auto;
  }

  .form-field-readonly-text {
    cursor: default;
    user-select: text;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  /* Custom styled select */
  .form-field-select {
    appearance: none;
    -webkit-appearance: none;
    background-color: var(--nord1);
    color: var(--nord4);
    border: 1px solid var(--nord3);
    border-radius: 4px;
    padding: 2px 24px 2px 8px;
    font-size: inherit;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%2381A1C1' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 6px center;
    transition: border-color 0.15s, box-shadow 0.15s;
  }

  .form-field-select:hover {
    border-color: var(--nord8);
  }

  .form-field-select:focus {
    outline: none;
    border-color: var(--nord8);
    box-shadow: 0 0 0 2px rgba(136, 192, 208, 0.3);
  }

  .form-field-select option {
    background-color: var(--nord1);
    color: var(--nord4);
    padding: 8px;
  }

  /* Custom styled checkbox */
  .form-field-checkbox {
    appearance: none;
    -webkit-appearance: none;
    background-color: var(--nord1);
    border: 2px solid var(--nord3);
    border-radius: 3px;
    cursor: pointer;
    transition: all 0.15s ease;
    position: relative;
  }

  .form-field-checkbox:hover:not(:disabled) {
    border-color: var(--nord8);
  }

  .form-field-checkbox:checked {
    background-color: var(--nord8);
    border-color: var(--nord8);
  }

  .form-field-checkbox:checked::after {
    content: '';
    position: absolute;
    top: 45%;
    left: 50%;
    width: 35%;
    height: 60%;
    border: solid var(--nord0);
    border-width: 0 2px 2px 0;
    transform: translate(-50%, -50%) rotate(45deg);
  }

  .form-field-checkbox:disabled {
    opacity: 0.7;
    cursor: default;
  }

  /* Custom styled radio */
  .form-field-radio {
    appearance: none;
    -webkit-appearance: none;
    background-color: var(--nord1);
    border: 2px solid var(--nord3);
    border-radius: 50%;
    cursor: pointer;
    transition: all 0.15s ease;
    position: relative;
  }

  .form-field-radio:hover:not(:disabled) {
    border-color: var(--nord8);
  }

  .form-field-radio:checked {
    border-color: var(--nord8);
  }

  .form-field-radio:checked::after {
    content: '';
    position: absolute;
    top: 50%;
    left: 50%;
    width: 50%;
    height: 50%;
    background-color: var(--nord8);
    border-radius: 50%;
    transform: translate(-50%, -50%);
  }

  .form-field-radio:disabled {
    opacity: 0.7;
    cursor: default;
  }
</style>
