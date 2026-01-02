<script lang="ts">
  import { MessageSquare, X } from 'lucide-svelte';
  import {
    type Annotation,
    type AnnotationType,
    type AnnotationsStore,
    type Rect,
    type InkPath,
    type LineStyle,
    type Point,
    type StampType,
    STAMP_PRESETS,
  } from '$lib/stores/annotations.svelte';
  import { getAuthorString } from '$lib/stores/settings.svelte';
  import type { RedactionsStore } from '$lib/stores/redactions.svelte';

  interface Props {
    store: AnnotationsStore;
    page: number;
    pageWidth: number;
    pageHeight: number;
    scale?: number;
    interactive?: boolean; // Whether to enable drawing/selection
    redactionsStore?: RedactionsStore; // For redaction tool
  }

  let { store, page, pageWidth, pageHeight, scale = 1, interactive = true, redactionsStore }: Props = $props();

  let overlayElement: SVGSVGElement;
  let isDrawing = $state(false);
  let drawStart = $state<{ x: number; y: number } | null>(null);
  let drawEnd = $state<{ x: number; y: number } | null>(null); // Track actual end position for line/arrow preview
  let drawRect = $state<Rect | null>(null);
  let editingComment = $state<string | null>(null);
  let commentText = $state('');

  // Convert ink path points to SVG path data
  function inkPathToSvg(path: InkPath, pageW: number, pageH: number, s: number): string {
    const points = path.points;
    if (!points || points.length < 2) return '';

    // Convert normalized points to pixel coordinates
    const pixelPoints = points.map(p => ({
      x: p.x * pageW * s,
      y: p.y * pageH * s,
    }));

    // Start path
    let d = `M ${pixelPoints[0].x} ${pixelPoints[0].y}`;

    // Use quadratic bezier curves for smooth lines
    for (let i = 1; i < pixelPoints.length; i++) {
      const prev = pixelPoints[i - 1];
      const curr = pixelPoints[i];
      const midX = (prev.x + curr.x) / 2;
      const midY = (prev.y + curr.y) / 2;
      d += ` Q ${prev.x} ${prev.y} ${midX} ${midY}`;
    }

    // End at last point
    const last = pixelPoints[pixelPoints.length - 1];
    d += ` L ${last.x} ${last.y}`;

    return d;
  }

  // Get SVG dash array for line style
  function getDashArray(style: LineStyle | undefined, strokeWidth: number): string {
    if (!style || style === 'solid') return '';
    const sw = Math.max(strokeWidth, 2);
    if (style === 'dashed') return `${sw * 3} ${sw * 2}`;
    if (style === 'dotted') return `${sw} ${sw}`;
    return '';
  }

  // Freetext (typewriter) state
  let editingFreetext = $state<string | null>(null);
  let freetextValue = $state('');
  let freetextInputRef: HTMLTextAreaElement;

  // Ink drawing state
  let currentInkPath = $state<{ x: number; y: number }[]>([]);

  // Hover state for annotation tooltips
  let hoveredAnnotationId = $state<string | null>(null);
  let tooltipPosition = $state<{ x: number; y: number } | null>(null);

  // Move/drag state
  let isDragging = $state(false);
  let draggingAnnotationId = $state<string | null>(null);
  let dragOffset = $state<{ x: number; y: number } | null>(null);
  let dragOriginalRect = $state<Rect | null>(null);
  let dragOriginalStartPoint = $state<Point | null>(null);
  let dragOriginalEndPoint = $state<Point | null>(null);
  let dragOriginalPaths = $state<InkPath[] | null>(null);

  const annotations = $derived(store.getAnnotationsForPage(page));

  // Convert mouse event to NORMALIZED coordinates (0-1)
  // This ensures annotations are zoom-independent
  function getRelativeCoords(e: MouseEvent): { x: number; y: number } {
    const rect = overlayElement.getBoundingClientRect();
    // Get pixel position relative to overlay
    const pixelX = (e.clientX - rect.left) / scale;
    const pixelY = (e.clientY - rect.top) / scale;
    // Convert to normalized (0-1) coordinates
    return {
      x: pixelX / pageWidth,
      y: pixelY / pageHeight,
    };
  }

  // Convert normalized rect to pixel rect for display
  function toPixelRect(rect: Rect): Rect {
    return {
      x: rect.x * pageWidth * scale,
      y: rect.y * pageHeight * scale,
      width: rect.width * pageWidth * scale,
      height: rect.height * pageHeight * scale,
    };
  }

  // Calculate bounding rect from path points
  function calculateBoundingRect(points: { x: number; y: number }[]): Rect {
    if (points.length === 0) return { x: 0, y: 0, width: 0, height: 0 };
    let minX = points[0].x, maxX = points[0].x;
    let minY = points[0].y, maxY = points[0].y;
    for (const p of points) {
      minX = Math.min(minX, p.x);
      maxX = Math.max(maxX, p.x);
      minY = Math.min(minY, p.y);
      maxY = Math.max(maxY, p.y);
    }
    return { x: minX, y: minY, width: maxX - minX, height: maxY - minY };
  }

  // Reduce points to improve performance (take every Nth point)
  function reducePoints(points: { x: number; y: number }[], n: number): { x: number; y: number }[] {
    if (points.length <= n * 2) return points;
    const result = [points[0]];
    for (let i = n; i < points.length - 1; i += n) {
      result.push(points[i]);
    }
    result.push(points[points.length - 1]);
    return result;
  }

  // Check if a point is inside an annotation's bounds
  function findAnnotationAtPoint(point: { x: number; y: number }): Annotation | null {
    // Search in reverse order (top-most first)
    for (let i = annotations.length - 1; i >= 0; i--) {
      const ann = annotations[i];
      const rect = ann.rect;
      // Expand hit area slightly for small annotations
      const margin = 0.005;
      if (
        point.x >= rect.x - margin &&
        point.x <= rect.x + rect.width + margin &&
        point.y >= rect.y - margin &&
        point.y <= rect.y + rect.height + margin
      ) {
        return ann;
      }
    }
    return null;
  }

  function handleMouseDown(e: MouseEvent) {
    if (e.button !== 0) return;

    // Handle move tool
    if (store.activeTool === 'move') {
      e.stopPropagation();
      e.preventDefault();
      const coords = getRelativeCoords(e);
      const annotation = findAnnotationAtPoint(coords);
      if (annotation) {
        isDragging = true;
        draggingAnnotationId = annotation.id;
        // Store offset from mouse to annotation top-left
        dragOffset = {
          x: coords.x - annotation.rect.x,
          y: coords.y - annotation.rect.y,
        };
        dragOriginalRect = { ...annotation.rect };
        // Store original points for line/arrow annotations
        if (annotation.startPoint) {
          dragOriginalStartPoint = { ...annotation.startPoint };
        }
        if (annotation.endPoint) {
          dragOriginalEndPoint = { ...annotation.endPoint };
        }
        // Store original paths for ink annotations
        if (annotation.paths) {
          dragOriginalPaths = annotation.paths.map(path => ({
            ...path,
            points: path.points.map(p => ({ ...p })),
          }));
        }
        store.selectAnnotation(annotation.id);
      }
      return;
    }

    if (!store.activeTool) return;

    // Prevent event from bubbling to container (stops panning/scrolling)
    e.stopPropagation();
    e.preventDefault();

    const coords = getRelativeCoords(e);

    if (store.activeTool === 'ink') {
      // Start ink path
      currentInkPath = [coords];
      isDrawing = true;
    } else {
      // Start rect-based drawing
      isDrawing = true;
      drawStart = coords;
      drawRect = { x: coords.x, y: coords.y, width: 0, height: 0 };
    }
  }

  function handleMouseMove(e: MouseEvent) {
    // Handle dragging
    if (isDragging && draggingAnnotationId && dragOffset && dragOriginalRect) {
      e.stopPropagation();
      e.preventDefault();
      const coords = getRelativeCoords(e);

      // Calculate new position
      const newX = coords.x - dragOffset.x;
      const newY = coords.y - dragOffset.y;

      // Calculate delta from original position
      const deltaX = newX - dragOriginalRect.x;
      const deltaY = newY - dragOriginalRect.y;

      // Clamp to page bounds
      const clampedX = Math.max(0, Math.min(1 - dragOriginalRect.width, newX));
      const clampedY = Math.max(0, Math.min(1 - dragOriginalRect.height, newY));

      // Build update object
      const updates: Partial<Annotation> = {
        rect: {
          x: clampedX,
          y: clampedY,
          width: dragOriginalRect.width,
          height: dragOriginalRect.height,
        },
      };

      // Update start/end points for line/arrow annotations
      if (dragOriginalStartPoint) {
        updates.startPoint = {
          x: dragOriginalStartPoint.x + deltaX,
          y: dragOriginalStartPoint.y + deltaY,
        };
      }
      if (dragOriginalEndPoint) {
        updates.endPoint = {
          x: dragOriginalEndPoint.x + deltaX,
          y: dragOriginalEndPoint.y + deltaY,
        };
      }

      // Also update ink paths if present
      if (dragOriginalPaths) {
        updates.paths = dragOriginalPaths.map(path => ({
          ...path,
          points: path.points.map(p => ({
            x: p.x + deltaX,
            y: p.y + deltaY,
          })),
        }));
      }

      store.updateAnnotation(draggingAnnotationId, updates);
      return;
    }

    if (!isDrawing) return;

    // Prevent event from bubbling during drawing
    e.stopPropagation();

    const coords = getRelativeCoords(e);

    if (store.activeTool === 'ink') {
      // Add point to ink path
      currentInkPath = [...currentInkPath, coords];
    } else if (drawStart) {
      // Track actual end position for line/arrow preview
      drawEnd = coords;
      // Update rect for shape tools (normalized bounding box)
      const x = Math.min(drawStart.x, coords.x);
      const y = Math.min(drawStart.y, coords.y);
      const width = Math.abs(coords.x - drawStart.x);
      const height = Math.abs(coords.y - drawStart.y);
      drawRect = { x, y, width, height };
    }
  }

  function handleMouseUp(e: MouseEvent) {
    // End dragging
    if (isDragging) {
      isDragging = false;
      draggingAnnotationId = null;
      dragOffset = null;
      dragOriginalRect = null;
      dragOriginalStartPoint = null;
      dragOriginalEndPoint = null;
      dragOriginalPaths = null;
      return;
    }

    if (!isDrawing || !store.activeTool) {
      isDrawing = false;
      drawStart = null;
      drawEnd = null;
      drawRect = null;
      currentInkPath = [];
      return;
    }

    // Prevent event from bubbling
    e.stopPropagation();

    // Get current mouse position for line/arrow end points
    const endCoords = getRelativeCoords(e);

    // Get author for annotation attribution
    const author = getAuthorString() || undefined;

    if (store.activeTool === 'ink') {
      // Create ink annotation if path has enough points
      if (currentInkPath.length > 2) {
        const reducedPath = reducePoints(currentInkPath, 3);
        const boundingRect = calculateBoundingRect(reducedPath);
        store.addAnnotation({
          type: 'ink',
          page,
          rect: boundingRect,
          color: store.activeColor,
          opacity: store.activeOpacity,
          author,
          paths: [{
            points: reducedPath,
            strokeWidth: 0.003,
            color: store.activeColor,
          }],
        });
      }
      currentInkPath = [];
    } else if (drawRect) {
      // Only create annotation if it has meaningful size
      const hasSize = drawRect.width > 0.005 || drawRect.height > 0.005;

      if (hasSize) {
        if (store.activeTool === 'comment') {
          const annotation = store.addAnnotation({
            type: 'comment',
            page,
            rect: drawRect,
            color: store.activeColor,
            opacity: store.activeOpacity,
            text: '',
            author,
          });
          editingComment = annotation.id;
          commentText = '';
        } else if (store.activeTool === 'freetext') {
          const annotation = store.addAnnotation({
            type: 'freetext',
            page,
            rect: drawRect,
            color: store.activeColor,
            opacity: store.activeOpacity,
            text: '',
            fontsize: 12,
            author,
          });
          editingFreetext = annotation.id;
          freetextValue = '';
          setTimeout(() => freetextInputRef?.focus(), 0);
        } else if (store.activeTool === 'area-select') {
          const markupType = store.pendingMarkupType;
          store.addAnnotation({
            type: markupType,
            page,
            rect: drawRect,
            color: store.activeColor,
            opacity: store.activeOpacity,
            author,
          });
        } else if (store.activeTool === 'rectangle') {
          store.addAnnotation({
            type: 'rectangle',
            page,
            rect: drawRect,
            color: store.activeColor,
            opacity: store.activeOpacity,
            strokeWidth: 0.002,
            lineStyle: store.activeLineStyle,
            fill: store.activeFillEnabled ? {
              enabled: true,
              color: store.activeFillColor,
              opacity: store.activeFillOpacity,
            } : undefined,
            author,
          });
        } else if (store.activeTool === 'ellipse') {
          store.addAnnotation({
            type: 'ellipse',
            page,
            rect: drawRect,
            color: store.activeColor,
            opacity: store.activeOpacity,
            strokeWidth: 0.002,
            lineStyle: store.activeLineStyle,
            fill: store.activeFillEnabled ? {
              enabled: true,
              color: store.activeFillColor,
              opacity: store.activeFillOpacity,
            } : undefined,
            author,
          });
        } else if (store.activeTool === 'line') {
          // For lines, store actual start/end points to preserve direction
          store.addAnnotation({
            type: 'line',
            page,
            rect: drawRect,
            color: store.activeColor,
            opacity: store.activeOpacity,
            strokeWidth: 0.002,
            lineStyle: store.activeLineStyle,
            startPoint: { x: drawStart!.x, y: drawStart!.y },
            endPoint: { x: endCoords.x, y: endCoords.y },
            author,
          });
        } else if (store.activeTool === 'arrow') {
          // For arrows, store actual start/end points to preserve direction
          store.addAnnotation({
            type: 'arrow',
            page,
            rect: drawRect,
            color: store.activeColor,
            opacity: store.activeOpacity,
            strokeWidth: 0.002,
            lineStyle: store.activeLineStyle,
            startArrow: store.activeStartArrow,
            endArrow: store.activeEndArrow,
            startPoint: { x: drawStart!.x, y: drawStart!.y },
            endPoint: { x: endCoords.x, y: endCoords.y },
            author,
          });
        } else if (store.activeTool === 'sequenceNumber') {
          // Make it a square based on the smaller dimension
          const size = Math.min(drawRect.width, drawRect.height);
          const squareRect = {
            x: drawRect.x,
            y: drawRect.y,
            width: size,
            height: size,
          };
          store.addAnnotation({
            type: 'sequenceNumber',
            page,
            rect: squareRect,
            color: store.activeColor,
            opacity: store.activeOpacity,
            sequenceNumber: store.getNextSequenceNumber(),
            author,
          });
        } else if (store.activeTool === 'stamp') {
          store.addAnnotation({
            type: 'stamp',
            page,
            rect: drawRect,
            color: store.activeColor,
            opacity: store.activeOpacity,
            stampType: store.activeStampType,
            stampText: store.activeStampType === 'Custom' ? store.customStampText : undefined,
            stampImageData: store.activeStampType === 'Image' ? store.stampImageData : undefined,
            stampRotation: store.stampRotation,
            author,
          });
        } else if (store.activeTool === 'redact' && redactionsStore) {
          // Add redaction mark to the redactions store
          redactionsStore.addMark(page, drawRect);
        }
      }
    }

    isDrawing = false;
    drawStart = null;
    drawEnd = null;
    drawRect = null;
  }

  function handleAnnotationClick(e: MouseEvent, annotation: Annotation) {
    e.stopPropagation();

    if (!store.activeTool) {
      // Select mode - clicking highlights in the list
      store.selectAnnotation(
        store.selectedId === annotation.id ? null : annotation.id
      );
    }
  }

  function handleAnnotationMouseEnter(e: MouseEvent, annotation: Annotation) {
    hoveredAnnotationId = annotation.id;
    tooltipPosition = { x: e.clientX, y: e.clientY };
  }

  function handleAnnotationMouseMove(e: MouseEvent) {
    if (hoveredAnnotationId) {
      tooltipPosition = { x: e.clientX, y: e.clientY };
    }
  }

  function handleAnnotationMouseLeave() {
    hoveredAnnotationId = null;
    tooltipPosition = null;
  }

  // Format date for tooltip display
  function formatDateTime(date: Date): string {
    const d = new Date(date);
    return d.toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  function handleDeleteAnnotation(id: string) {
    store.deleteAnnotation(id);
  }

  function handleCommentSave(id: string) {
    if (commentText.trim()) {
      store.updateAnnotation(id, { text: commentText });
    } else {
      store.deleteAnnotation(id);
    }
    editingComment = null;
    commentText = '';
  }

  function handleCommentCancel(id: string) {
    if (!store.getAnnotationsForPage(page).find(a => a.id === id)?.text) {
      store.deleteAnnotation(id);
    }
    editingComment = null;
    commentText = '';
  }

  // Freetext handlers
  function handleFreetextSave(id: string) {
    if (freetextValue.trim()) {
      store.updateAnnotation(id, { text: freetextValue });
    } else {
      store.deleteAnnotation(id);
    }
    editingFreetext = null;
    freetextValue = '';
  }

  function handleFreetextCancel(id: string) {
    const ann = store.getAnnotationsForPage(page).find(a => a.id === id);
    if (!ann?.text) {
      store.deleteAnnotation(id);
    }
    editingFreetext = null;
    freetextValue = '';
  }

  function handleFreetextKeydown(e: KeyboardEvent, id: string) {
    if (e.key === 'Escape') {
      handleFreetextCancel(id);
    }
    // Enter without Shift saves
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleFreetextSave(id);
    }
  }

  const cursorStyle = $derived(() => {
    if (!interactive) return 'default';
    if (!store.activeTool) return 'default';
    if (store.activeTool === 'move') return isDragging ? 'grabbing' : 'grab';
    if (store.activeTool === 'comment') return 'cell';
    if (store.activeTool === 'freetext') return 'text';
    if (store.activeTool === 'ink') return 'crosshair';
    if (store.activeTool === 'rectangle' || store.activeTool === 'ellipse') return 'crosshair';
    if (store.activeTool === 'line' || store.activeTool === 'arrow') return 'crosshair';
    if (store.activeTool === 'sequenceNumber') return 'crosshair';
    if (store.activeTool === 'stamp') return 'crosshair';
    if (store.activeTool === 'redact') return 'crosshair';
    return 'crosshair';
  });

  // Helper to get stamp display info
  function getStampInfo(stampType: StampType, customText?: string) {
    if (stampType === 'Custom' && customText) {
      return { label: customText.toUpperCase(), color: '#FFFFFF', bgColor: '#607D8B' };
    }
    const preset = STAMP_PRESETS.find(s => s.type === stampType);
    return preset || { label: stampType.toUpperCase(), color: '#FFFFFF', bgColor: '#607D8B' };
  }
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<svg
  bind:this={overlayElement}
  class="absolute inset-0"
  class:pointer-events-auto={interactive}
  class:pointer-events-none={!interactive}
  style="cursor: {cursorStyle()};"
  width={pageWidth * scale}
  height={pageHeight * scale}
  onmousedown={interactive ? handleMouseDown : undefined}
  onmousemove={interactive ? handleMouseMove : undefined}
  onmouseup={interactive ? handleMouseUp : undefined}
  onmouseleave={interactive ? () => { isDrawing = false; drawStart = null; drawEnd = null; drawRect = null; currentInkPath = []; isDragging = false; draggingAnnotationId = null; dragOffset = null; dragOriginalRect = null; dragOriginalStartPoint = null; dragOriginalEndPoint = null; dragOriginalPaths = null; } : undefined}
>
  <!-- Rendered annotations -->
  {#each annotations as annotation (annotation.id)}
    {@const pixelRect = toPixelRect(annotation.rect)}
    {#if annotation.type === 'highlight'}
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <!-- svelte-ignore a11y_mouse_events_have_key_events -->
      <rect
        x={pixelRect.x}
        y={pixelRect.y}
        width={pixelRect.width}
        height={pixelRect.height}
        fill={annotation.color}
        fill-opacity={annotation.opacity}
        class="cursor-pointer hover:opacity-80 transition-opacity"
        class:ring-2={store.selectedId === annotation.id}
        onclick={(e) => handleAnnotationClick(e, annotation)}
        onmouseenter={(e) => handleAnnotationMouseEnter(e, annotation)}
        onmousemove={handleAnnotationMouseMove}
        onmouseleave={handleAnnotationMouseLeave}
      />
    {:else if annotation.type === 'underline'}
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <!-- svelte-ignore a11y_mouse_events_have_key_events -->
      <line
        x1={pixelRect.x}
        y1={pixelRect.y + pixelRect.height}
        x2={pixelRect.x + pixelRect.width}
        y2={pixelRect.y + pixelRect.height}
        stroke={annotation.color}
        stroke-width="2"
        class="cursor-pointer"
        onclick={(e) => handleAnnotationClick(e, annotation)}
        onmouseenter={(e) => handleAnnotationMouseEnter(e, annotation)}
        onmousemove={handleAnnotationMouseMove}
        onmouseleave={handleAnnotationMouseLeave}
      />
    {:else if annotation.type === 'strikethrough'}
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <!-- svelte-ignore a11y_mouse_events_have_key_events -->
      <line
        x1={pixelRect.x}
        y1={pixelRect.y + pixelRect.height / 2}
        x2={pixelRect.x + pixelRect.width}
        y2={pixelRect.y + pixelRect.height / 2}
        stroke={annotation.color}
        stroke-width="2"
        class="cursor-pointer"
        onclick={(e) => handleAnnotationClick(e, annotation)}
        onmouseenter={(e) => handleAnnotationMouseEnter(e, annotation)}
        onmousemove={handleAnnotationMouseMove}
        onmouseleave={handleAnnotationMouseLeave}
      />
    {:else if annotation.type === 'comment'}
      <!-- Comment marker -->
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <!-- svelte-ignore a11y_mouse_events_have_key_events -->
      <g
        class="cursor-pointer"
        onclick={(e) => handleAnnotationClick(e, annotation)}
        onmouseenter={(e) => handleAnnotationMouseEnter(e, annotation)}
        onmousemove={handleAnnotationMouseMove}
        onmouseleave={handleAnnotationMouseLeave}
      >
        <rect
          x={pixelRect.x}
          y={pixelRect.y}
          width="24"
          height="24"
          rx="4"
          fill={annotation.color}
        />
        <foreignObject
          x={pixelRect.x + 4}
          y={pixelRect.y + 4}
          width="16"
          height="16"
        >
          <MessageSquare size={16} style="color: white;" />
        </foreignObject>
      </g>
    {:else if annotation.type === 'freetext'}
      <!-- Freetext / Typewriter annotation -->
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <!-- svelte-ignore a11y_mouse_events_have_key_events -->
      {@const fontSize = (annotation.fontsize || 12) * scale}
      <foreignObject
        x={pixelRect.x}
        y={pixelRect.y}
        width={Math.max(pixelRect.width, 100)}
        height={Math.max(pixelRect.height, fontSize * 1.5)}
        class="cursor-pointer overflow-visible"
        onclick={(e) => handleAnnotationClick(e, annotation)}
        onmouseenter={(e) => handleAnnotationMouseEnter(e, annotation)}
        onmousemove={handleAnnotationMouseMove}
        onmouseleave={handleAnnotationMouseLeave}
      >
        <div
          xmlns="http://www.w3.org/1999/xhtml"
          class="whitespace-pre-wrap"
          style="
            color: {annotation.color};
            font-family: Helvetica, Arial, sans-serif;
            font-size: {fontSize}px;
            line-height: 1.3;
          "
        >
          {annotation.text || ''}
        </div>
      </foreignObject>
    {:else if annotation.type === 'ink' && annotation.paths}
      <!-- Ink/freehand annotation -->
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <!-- svelte-ignore a11y_mouse_events_have_key_events -->
      <g
        class="cursor-pointer"
        onclick={(e) => handleAnnotationClick(e, annotation)}
        onmouseenter={(e) => handleAnnotationMouseEnter(e, annotation)}
        onmousemove={handleAnnotationMouseMove}
        onmouseleave={handleAnnotationMouseLeave}
      >
        {#each annotation.paths as path}
          {@const strokeWidth = (path.strokeWidth || 0.003) * pageWidth * scale}
          <path
            d={inkPathToSvg(path, pageWidth, pageHeight, scale)}
            fill="none"
            stroke={path.color || annotation.color}
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
            opacity={annotation.opacity}
          />
        {/each}
      </g>
    {:else if annotation.type === 'rectangle'}
      <!-- Rectangle annotation -->
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <!-- svelte-ignore a11y_mouse_events_have_key_events -->
      {@const strokeWidth = (annotation.strokeWidth || 0.002) * pageWidth * scale}
      <rect
        x={pixelRect.x}
        y={pixelRect.y}
        width={pixelRect.width}
        height={pixelRect.height}
        fill={annotation.fill?.enabled ? annotation.fill.color : 'none'}
        fill-opacity={annotation.fill?.enabled ? annotation.fill.opacity : 0}
        stroke={annotation.color}
        stroke-width={strokeWidth}
        stroke-dasharray={getDashArray(annotation.lineStyle, strokeWidth)}
        opacity={annotation.opacity}
        class="cursor-pointer"
        onclick={(e) => handleAnnotationClick(e, annotation)}
        onmouseenter={(e) => handleAnnotationMouseEnter(e, annotation)}
        onmousemove={handleAnnotationMouseMove}
        onmouseleave={handleAnnotationMouseLeave}
      />
    {:else if annotation.type === 'ellipse'}
      <!-- Ellipse annotation -->
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <!-- svelte-ignore a11y_mouse_events_have_key_events -->
      {@const strokeWidth = (annotation.strokeWidth || 0.002) * pageWidth * scale}
      {@const cx = pixelRect.x + pixelRect.width / 2}
      {@const cy = pixelRect.y + pixelRect.height / 2}
      {@const rx = pixelRect.width / 2}
      {@const ry = pixelRect.height / 2}
      <ellipse
        {cx} {cy} {rx} {ry}
        fill={annotation.fill?.enabled ? annotation.fill.color : 'none'}
        fill-opacity={annotation.fill?.enabled ? annotation.fill.opacity : 0}
        stroke={annotation.color}
        stroke-width={strokeWidth}
        stroke-dasharray={getDashArray(annotation.lineStyle, strokeWidth)}
        opacity={annotation.opacity}
        class="cursor-pointer"
        onclick={(e) => handleAnnotationClick(e, annotation)}
        onmouseenter={(e) => handleAnnotationMouseEnter(e, annotation)}
        onmousemove={handleAnnotationMouseMove}
        onmouseleave={handleAnnotationMouseLeave}
      />
    {:else if annotation.type === 'line'}
      <!-- Line annotation -->
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <!-- svelte-ignore a11y_mouse_events_have_key_events -->
      {@const strokeWidth = (annotation.strokeWidth || 0.002) * pageWidth * scale}
      {@const x1 = annotation.startPoint ? annotation.startPoint.x * pageWidth * scale : pixelRect.x}
      {@const y1 = annotation.startPoint ? annotation.startPoint.y * pageHeight * scale : pixelRect.y}
      {@const x2 = annotation.endPoint ? annotation.endPoint.x * pageWidth * scale : pixelRect.x + pixelRect.width}
      {@const y2 = annotation.endPoint ? annotation.endPoint.y * pageHeight * scale : pixelRect.y + pixelRect.height}
      <line
        {x1} {y1} {x2} {y2}
        stroke={annotation.color}
        stroke-width={strokeWidth}
        stroke-dasharray={getDashArray(annotation.lineStyle, strokeWidth)}
        opacity={annotation.opacity}
        class="cursor-pointer"
        onclick={(e) => handleAnnotationClick(e, annotation)}
        onmouseenter={(e) => handleAnnotationMouseEnter(e, annotation)}
        onmousemove={handleAnnotationMouseMove}
        onmouseleave={handleAnnotationMouseLeave}
      />
    {:else if annotation.type === 'arrow'}
      <!-- Arrow annotation -->
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <!-- svelte-ignore a11y_mouse_events_have_key_events -->
      {@const strokeWidth = (annotation.strokeWidth || 0.002) * pageWidth * scale}
      {@const arrowId = `arrow-${annotation.id}`}
      {@const hasStartArrow = annotation.startArrow && annotation.startArrow !== 'none'}
      {@const hasEndArrow = annotation.endArrow && annotation.endArrow !== 'none'}
      {@const isClosedStart = annotation.startArrow === 'closed'}
      {@const isClosedEnd = annotation.endArrow === 'closed'}
      {@const x1 = annotation.startPoint ? annotation.startPoint.x * pageWidth * scale : pixelRect.x}
      {@const y1 = annotation.startPoint ? annotation.startPoint.y * pageHeight * scale : pixelRect.y}
      {@const x2 = annotation.endPoint ? annotation.endPoint.x * pageWidth * scale : pixelRect.x + pixelRect.width}
      {@const y2 = annotation.endPoint ? annotation.endPoint.y * pageHeight * scale : pixelRect.y + pixelRect.height}
      <g
        class="cursor-pointer"
        onclick={(e) => handleAnnotationClick(e, annotation)}
        onmouseenter={(e) => handleAnnotationMouseEnter(e, annotation)}
        onmousemove={handleAnnotationMouseMove}
        onmouseleave={handleAnnotationMouseLeave}
      >
        <defs>
          {#if hasEndArrow}
            <marker
              id="{arrowId}-end"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto"
            >
              <path
                d="M 0 0 L 10 5 L 0 10 {isClosedEnd ? 'z' : ''}"
                fill={isClosedEnd ? annotation.color : 'none'}
                stroke={annotation.color}
                stroke-width="1"
              />
            </marker>
          {/if}
          {#if hasStartArrow}
            <marker
              id="{arrowId}-start"
              viewBox="0 0 10 10"
              refX="1"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto"
            >
              <path
                d="M 10 0 L 0 5 L 10 10 {isClosedStart ? 'z' : ''}"
                fill={isClosedStart ? annotation.color : 'none'}
                stroke={annotation.color}
                stroke-width="1"
              />
            </marker>
          {/if}
        </defs>
        <line
          {x1} {y1} {x2} {y2}
          stroke={annotation.color}
          stroke-width={strokeWidth}
          stroke-dasharray={getDashArray(annotation.lineStyle, strokeWidth)}
          marker-start={hasStartArrow ? `url(#${arrowId}-start)` : undefined}
          marker-end={hasEndArrow ? `url(#${arrowId}-end)` : undefined}
          opacity={annotation.opacity}
        />
      </g>
    {:else if annotation.type === 'sequenceNumber'}
      <!-- Sequence number annotation -->
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <!-- svelte-ignore a11y_mouse_events_have_key_events -->
      {@const r = Math.min(pixelRect.width, pixelRect.height) / 2}
      {@const cx = pixelRect.x + pixelRect.width / 2}
      {@const cy = pixelRect.y + pixelRect.height / 2}
      {@const fontSize = r * 1.2}
      <g
        class="cursor-pointer"
        onclick={(e) => handleAnnotationClick(e, annotation)}
        onmouseenter={(e) => handleAnnotationMouseEnter(e, annotation)}
        onmousemove={handleAnnotationMouseMove}
        onmouseleave={handleAnnotationMouseLeave}
      >
        <circle
          {cx} {cy} {r}
          fill={annotation.color}
          opacity={annotation.opacity}
        />
        <text
          x={cx}
          y={cy}
          text-anchor="middle"
          dominant-baseline="central"
          fill="white"
          font-size="{fontSize}px"
          font-weight="bold"
          font-family="Helvetica, Arial, sans-serif"
        >
          {annotation.sequenceNumber || 1}
        </text>
      </g>
    {:else if annotation.type === 'stamp'}
      <!-- Stamp annotation -->
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <!-- svelte-ignore a11y_mouse_events_have_key_events -->
      {@const stampInfo = getStampInfo(annotation.stampType || 'Approved', annotation.stampText)}
      {@const centerX = pixelRect.x + pixelRect.width / 2}
      {@const centerY = pixelRect.y + pixelRect.height / 2}
      {@const rotation = annotation.stampRotation || 0}
      <g
        class="cursor-pointer"
        onclick={(e) => handleAnnotationClick(e, annotation)}
        onmouseenter={(e) => handleAnnotationMouseEnter(e, annotation)}
        onmousemove={handleAnnotationMouseMove}
        onmouseleave={handleAnnotationMouseLeave}
        transform="rotate({rotation} {centerX} {centerY})"
      >
        {#if annotation.stampType === 'Image' && annotation.stampImageData}
          <!-- Image stamp -->
          <image
            x={pixelRect.x}
            y={pixelRect.y}
            width={pixelRect.width}
            height={pixelRect.height}
            href={annotation.stampImageData}
            preserveAspectRatio="xMidYMid meet"
            opacity={annotation.opacity}
          />
        {:else}
          <!-- Text stamp -->
          {@const fontSize = Math.min(pixelRect.width / (stampInfo.label.length * 0.6), pixelRect.height * 0.6)}
          <rect
            x={pixelRect.x}
            y={pixelRect.y}
            width={pixelRect.width}
            height={pixelRect.height}
            rx="4"
            fill={stampInfo.bgColor}
            opacity={annotation.opacity}
          />
          <rect
            x={pixelRect.x + 2}
            y={pixelRect.y + 2}
            width={pixelRect.width - 4}
            height={pixelRect.height - 4}
            rx="2"
            fill="none"
            stroke={stampInfo.color}
            stroke-width="2"
            opacity={annotation.opacity * 0.5}
          />
          <text
            x={centerX}
            y={centerY}
            text-anchor="middle"
            dominant-baseline="central"
            fill={stampInfo.color}
            font-size="{fontSize}px"
            font-weight="bold"
            font-family="Helvetica, Arial, sans-serif"
          >
            {stampInfo.label}
          </text>
        {/if}
      </g>
    {/if}
  {/each}

  <!-- Drawing preview -->
  {#if isDrawing && store.activeTool}
    <!-- Ink preview -->
    {#if store.activeTool === 'ink' && currentInkPath.length > 1}
      {@const pathData = inkPathToSvg({ points: currentInkPath, strokeWidth: 0.003, color: store.activeColor }, pageWidth, pageHeight, scale)}
      <path
        d={pathData}
        fill="none"
        stroke={store.activeColor}
        stroke-width={0.003 * pageWidth * scale}
        stroke-linecap="round"
        stroke-linejoin="round"
        opacity="0.7"
      />
    {:else if drawRect}
      {@const previewRect = toPixelRect(drawRect)}
      {#if store.activeTool === 'area-select' && store.pendingMarkupType === 'highlight'}
        <rect
          x={previewRect.x}
          y={previewRect.y}
          width={previewRect.width}
          height={previewRect.height}
          fill={store.activeColor}
          fill-opacity="0.3"
          stroke={store.activeColor}
          stroke-width="1"
          stroke-dasharray="4"
        />
      {:else if store.activeTool === 'area-select' && store.pendingMarkupType === 'underline'}
        <line
          x1={previewRect.x}
          y1={previewRect.y + previewRect.height}
          x2={previewRect.x + previewRect.width}
          y2={previewRect.y + previewRect.height}
          stroke={store.activeColor}
          stroke-width="2"
          stroke-dasharray="4"
        />
      {:else if store.activeTool === 'area-select' && store.pendingMarkupType === 'strikethrough'}
        <line
          x1={previewRect.x}
          y1={previewRect.y + previewRect.height / 2}
          x2={previewRect.x + previewRect.width}
          y2={previewRect.y + previewRect.height / 2}
          stroke={store.activeColor}
          stroke-width="2"
          stroke-dasharray="4"
        />
      {:else if store.activeTool === 'comment'}
        <rect
          x={previewRect.x}
          y={previewRect.y}
          width={previewRect.width}
          height={previewRect.height}
          fill="none"
          stroke={store.activeColor}
          stroke-width="2"
          stroke-dasharray="4"
        />
      {:else if store.activeTool === 'freetext'}
        <rect
          x={previewRect.x}
          y={previewRect.y}
          width={previewRect.width}
          height={previewRect.height}
          fill="rgba(255,255,255,0.8)"
          stroke={store.activeColor}
          stroke-width="1"
          stroke-dasharray="4"
        />
      {:else if store.activeTool === 'rectangle'}
        <rect
          x={previewRect.x}
          y={previewRect.y}
          width={previewRect.width}
          height={previewRect.height}
          fill="none"
          stroke={store.activeColor}
          stroke-width="2"
          stroke-dasharray="4"
        />
      {:else if store.activeTool === 'ellipse'}
        <ellipse
          cx={previewRect.x + previewRect.width / 2}
          cy={previewRect.y + previewRect.height / 2}
          rx={previewRect.width / 2}
          ry={previewRect.height / 2}
          fill="none"
          stroke={store.activeColor}
          stroke-width="2"
          stroke-dasharray="4"
        />
      {:else if store.activeTool === 'line'}
        <!-- Use drawStart and drawEnd for actual direction -->
        {@const lineX1 = drawStart ? drawStart.x * pageWidth * scale : previewRect.x}
        {@const lineY1 = drawStart ? drawStart.y * pageHeight * scale : previewRect.y}
        {@const lineX2 = drawEnd ? drawEnd.x * pageWidth * scale : previewRect.x + previewRect.width}
        {@const lineY2 = drawEnd ? drawEnd.y * pageHeight * scale : previewRect.y + previewRect.height}
        <line
          x1={lineX1}
          y1={lineY1}
          x2={lineX2}
          y2={lineY2}
          stroke={store.activeColor}
          stroke-width="2"
          stroke-dasharray="4"
        />
      {:else if store.activeTool === 'arrow'}
        <!-- Use drawStart and drawEnd for actual direction -->
        {@const arrowX1 = drawStart ? drawStart.x * pageWidth * scale : previewRect.x}
        {@const arrowY1 = drawStart ? drawStart.y * pageHeight * scale : previewRect.y}
        {@const arrowX2 = drawEnd ? drawEnd.x * pageWidth * scale : previewRect.x + previewRect.width}
        {@const arrowY2 = drawEnd ? drawEnd.y * pageHeight * scale : previewRect.y + previewRect.height}
        <defs>
          <marker
            id="preview-arrow-end"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto"
          >
            <path
              d="M 0 0 L 10 5 L 0 10 z"
              fill={store.activeColor}
            />
          </marker>
        </defs>
        <line
          x1={arrowX1}
          y1={arrowY1}
          x2={arrowX2}
          y2={arrowY2}
          stroke={store.activeColor}
          stroke-width="2"
          stroke-dasharray="4"
          marker-end="url(#preview-arrow-end)"
        />
      {:else if store.activeTool === 'sequenceNumber'}
        {@const size = Math.min(previewRect.width, previewRect.height)}
        {@const r = size / 2}
        {@const cx = previewRect.x + size / 2}
        {@const cy = previewRect.y + size / 2}
        <circle
          {cx} {cy} {r}
          fill={store.activeColor}
          opacity="0.7"
        />
        <text
          x={cx}
          y={cy}
          text-anchor="middle"
          dominant-baseline="central"
          fill="white"
          font-size="{r * 1.2}px"
          font-weight="bold"
          font-family="Helvetica, Arial, sans-serif"
        >
          {store.sequenceCounter}
        </text>
      {:else if store.activeTool === 'stamp'}
        {@const stampInfo = getStampInfo(store.activeStampType, store.customStampText)}
        {@const centerX = previewRect.x + previewRect.width / 2}
        {@const centerY = previewRect.y + previewRect.height / 2}
        <g transform="rotate({store.stampRotation} {centerX} {centerY})">
          {#if store.activeStampType === 'Image' && store.stampImageData}
            <image
              x={previewRect.x}
              y={previewRect.y}
              width={previewRect.width}
              height={previewRect.height}
              href={store.stampImageData}
              preserveAspectRatio="xMidYMid meet"
              opacity="0.7"
            />
          {:else}
            {@const fontSize = Math.min(previewRect.width / (stampInfo.label.length * 0.6), previewRect.height * 0.6)}
            <rect
              x={previewRect.x}
              y={previewRect.y}
              width={previewRect.width}
              height={previewRect.height}
              rx="4"
              fill={stampInfo.bgColor}
              opacity="0.7"
            />
            <text
              x={centerX}
              y={centerY}
              text-anchor="middle"
              dominant-baseline="central"
              fill={stampInfo.color}
              font-size="{fontSize}px"
              font-weight="bold"
              font-family="Helvetica, Arial, sans-serif"
            >
              {stampInfo.label}
            </text>
          {/if}
        </g>
      {:else if store.activeTool === 'redact'}
        <!-- Redaction preview - red dashed rectangle -->
        <rect
          x={previewRect.x}
          y={previewRect.y}
          width={previewRect.width}
          height={previewRect.height}
          fill="rgba(191, 97, 106, 0.3)"
          stroke="var(--nord11)"
          stroke-width="2"
          stroke-dasharray="4"
        />
        <!-- Diagonal pattern preview -->
        <defs>
          <pattern
            id="redact-preview-pattern"
            width="10"
            height="10"
            patternUnits="userSpaceOnUse"
            patternTransform="rotate(45)"
          >
            <line x1="0" y1="0" x2="0" y2="10" stroke="var(--nord11)" stroke-width="2" opacity="0.3" />
          </pattern>
        </defs>
        <rect
          x={previewRect.x}
          y={previewRect.y}
          width={previewRect.width}
          height={previewRect.height}
          fill="url(#redact-preview-pattern)"
        />
      {/if}
    {/if}
  {/if}
</svg>

<!-- Comment edit popup -->
{#if editingComment}
  {@const annotation = annotations.find(a => a.id === editingComment)}
  {#if annotation}
    {@const popupRect = toPixelRect(annotation.rect)}
    <div
      class="absolute z-50 p-3 rounded-lg shadow-lg"
      style="
        left: {popupRect.x + popupRect.width + 10}px;
        top: {popupRect.y}px;
        background-color: var(--nord1);
        border: 1px solid var(--nord3);
        min-width: 200px;
      "
    >
      <textarea
        bind:value={commentText}
        class="w-full h-20 px-2 py-1 rounded text-sm resize-none"
        style="background-color: var(--nord2); border: 1px solid var(--nord3);"
        placeholder="Enter comment..."
      ></textarea>
      <div class="flex justify-end gap-2 mt-2">
        <button
          onclick={() => handleCommentCancel(editingComment!)}
          class="px-3 py-1 rounded text-xs hover:bg-[var(--nord2)]"
        >
          Cancel
        </button>
        <button
          onclick={() => handleCommentSave(editingComment!)}
          class="px-3 py-1 rounded text-xs"
          style="background-color: var(--nord8); color: var(--on-primary);"
        >
          Save
        </button>
      </div>
    </div>
  {/if}
{/if}

<!-- Freetext edit input -->
{#if editingFreetext}
  {@const annotation = annotations.find(a => a.id === editingFreetext)}
  {#if annotation}
    {@const inputRect = toPixelRect(annotation.rect)}
    {@const editFontSize = (annotation.fontsize || 12) * scale}
    <div
      class="absolute z-50"
      style="
        left: {inputRect.x}px;
        top: {inputRect.y}px;
      "
    >
      <textarea
        bind:this={freetextInputRef}
        bind:value={freetextValue}
        onkeydown={(e) => handleFreetextKeydown(e, editingFreetext!)}
        onblur={() => handleFreetextSave(editingFreetext!)}
        class="px-1 py-0.5 rounded outline-none resize"
        style="
          background-color: rgba(255, 255, 255, 0.95);
          border: 1px solid {annotation.color};
          color: {annotation.color};
          font-family: Helvetica, Arial, sans-serif;
          font-size: {editFontSize}px;
          line-height: 1.3;
          width: {Math.max(inputRect.width, 100)}px;
          height: {Math.max(inputRect.height, editFontSize * 2)}px;
        "
        placeholder="Type here..."
      ></textarea>
      <div class="text-[10px] mt-1 opacity-60" style="color: var(--nord4);">
        Enter to save, Shift+Enter for new line, Esc to cancel
      </div>
    </div>
  {/if}
{/if}

<!-- Annotation hover tooltip -->
{#if hoveredAnnotationId && tooltipPosition && !store.activeTool}
  {@const hovered = annotations.find(a => a.id === hoveredAnnotationId)}
  {#if hovered}
    <div
      class="fixed z-[99999] px-3 py-2 rounded-lg shadow-lg pointer-events-none"
      style="
        left: {tooltipPosition.x + 12}px;
        top: {tooltipPosition.y + 12}px;
        background-color: var(--nord1);
        border: 1px solid var(--nord3);
        max-width: 250px;
      "
    >
      {#if hovered.author}
        <div class="text-xs font-medium" style="color: var(--nord6);">
          {hovered.author}
        </div>
      {/if}
      <div class="text-[10px]" style="color: var(--nord4);">
        {formatDateTime(hovered.createdAt)}
      </div>
      {#if (hovered.type === 'comment' || hovered.type === 'freetext') && hovered.text}
        <div
          class="mt-1 pt-1 border-t text-xs line-clamp-3"
          style="border-color: var(--nord3); color: var(--nord4);"
        >
          {hovered.text}
        </div>
      {/if}
    </div>
  {/if}
{/if}
