# Tlacuilo - Roadmap

**Ultima actualizacion:** 2024-12-24

---

## Estado Actual: PDF Viewer/Annotator Funcional

El viewer es usable para trabajo diario. Las herramientas de manipulacion (merge, split, rotate, compress, convert) estan funcionales.

---

## Completado

### Core Viewer
- [x] Renderizado PDF de alta calidad con MuPDF (Rust bindings)
- [x] Visor multi-tab
- [x] Controles de zoom (fit-width, fit-page, custom)
- [x] Rotacion de vista
- [x] Navegacion de paginas
- [x] Seleccion de texto con menu contextual
- [x] Copiar texto seleccionado
- [x] Busqueda con highlight y navegacion

### Annotations
- [x] Highlight (resaltado)
- [x] Underline (subrayado)
- [x] Strikethrough (tachado)
- [x] Comments (notas adhesivas)
- [x] Freetext (texto libre/typewriter)
- [x] Ink (dibujo libre)
- [x] Rectangle
- [x] Ellipse
- [x] Line
- [x] Arrow (con puntas configurables)
- [x] Sequence Numbers (numeracion)
- [x] Colores y opacidad configurables
- [x] Estilos de linea (solid, dashed, dotted)
- [x] Fill para shapes
- [x] Guardar anotaciones en PDF
- [x] Exportar como XFDF
- [x] Imprimir con opciones de anotaciones
- [x] Panel de anotaciones con busqueda
- [x] Cambiar color de anotacion existente

### Bookmarks
- [x] Lector de PDF Outlines (Table of Contents)
- [x] Navegacion a seccion con scroll preciso
- [x] Outlines jerarquicos expandibles
- [x] User bookmarks (marcadores de usuario)
- [x] Persistencia de bookmarks por archivo
- [x] Agregar/editar/eliminar bookmarks
- [x] Busqueda en bookmarks y outlines

### OCR
- [x] Deteccion automatica de documentos escaneados
- [x] OCR con Tesseract via ocrmypdf
- [x] Soporte multi-idioma
- [x] Indicador de progreso
- [x] Manejo de archivos temporales OCR
- [x] Flujo: archivo original -> OCR -> temp -> Save As

### PDF Operations
- [x] Merge PDFs (unir)
- [x] Split PDFs (dividir)
- [x] Rotate pages (rotar)
- [x] Compress PDFs (comprimir con Ghostscript)

### Conversion
- [x] Images to PDF (JPG, PNG, WEBP, TIFF, BMP)
- [x] PDF to Images (PNG, JPG, WEBP, TIFF)
- [x] Configuracion de DPI
- [x] Per-image transforms

### UI/UX
- [x] Tema Nord
- [x] Sidebar con favoritos personalizables
- [x] Archivos recientes
- [x] Configuracion persistente (tauri-plugin-store)
- [x] Atajos de teclado
- [x] Sistema de tabs
- [x] Menu de aplicacion (File, Edit, View, Help)
- [x] Dialogo de confirmacion para cambios no guardados

---

## En Progreso

### Signatures Module
- [x] Placeholder UI
- [ ] Firma grafica (dibujar/cargar imagen)
- [ ] Posicionar firma en documento
- [ ] Biblioteca de firmas guardadas

### Metadata Viewer
- [x] Mostrar info del documento (titulo, autor, fechas)
- [x] Propiedades del PDF (version, encriptacion)
- [x] Estadisticas (paginas, tamano)
- [x] Copiar campos al portapapeles

### Attachments Viewer
- [x] Listar archivos embebidos con metadata
- [x] Extraer attachment individual (Save As dialog)
- [x] Extraer todos los attachments
- [ ] Preview de attachments (imagenes, texto)

---

## Siguiente (Quick Wins)

### Stamps
- [ ] Stamps predefinidos (Approved, Draft, Confidential, etc.)
- [ ] Stamps personalizados
- [ ] Posicionar como anotacion

---

## Medio Plazo

### AcroForms
- [ ] Detectar campos de formulario
- [ ] Llenar campos (text, checkbox, radio, dropdown)
- [ ] Guardar formulario llenado
- [ ] Validaciones basicas

### Callouts
- [ ] Freetext con linea conectora
- [ ] Posicionamiento automatico

### Layers
- [ ] Detectar layers del PDF
- [ ] Toggle visibilidad

---

## Largo Plazo

### Redaction
- [ ] Marcar areas para redactar
- [ ] Eliminar contenido real (no solo cubrir)
- [ ] Verificacion de redaccion

### Sanitization
- [ ] Limpiar metadata
- [ ] Eliminar scripts
- [ ] Remover objetos ocultos

### Digital Signatures
- [ ] PKCS#7 con certificados
- [ ] PAdES
- [ ] Timestamp
- [ ] Verificacion de firmas

### Office Conversion
- [ ] DOCX a PDF (LibreOffice)
- [ ] XLSX a PDF
- [ ] PPTX a PDF

---

## Nice to Have (Needs Research)

- [ ] Cloud Storage Integration (OneDrive, Google Drive, Dropbox, iCloud)
- [ ] Escanear a PDF (SANE)
- [ ] Comparar PDFs
- [ ] Reparar PDFs danados
- [ ] PKCS#11 (hardware tokens)

---

## Arquitectura Actual

```
ihpdf/
├── src-tauri/           # Rust (Tauri + MuPDF bindings)
│   ├── src/
│   │   ├── lib.rs       # Commands y menu
│   │   ├── pdf_viewer.rs # MuPDF operations
│   │   ├── pdf_ocr.rs   # OCR wrapper
│   │   └── ...
│
├── src/                 # Frontend (Svelte 5 + TypeScript)
│   ├── lib/
│   │   ├── components/
│   │   │   ├── PDFViewer/    # Viewer components
│   │   │   ├── Sidebar/      # Navigation
│   │   │   └── ...
│   │   ├── stores/           # Svelte stores
│   │   └── views/            # Page views
│
├── backend/             # Python scripts
│   ├── pdf_ops.py       # Merge, split, rotate
│   ├── pdf_compress.py  # Compression
│   ├── pdf_convert.py   # Image conversion
│   └── ...
```

---

## Stack

| Layer | Technology |
|-------|------------|
| Frontend | Svelte 5 (runes) + Vite |
| Desktop | Tauri 2.x (Rust) |
| PDF Rendering | MuPDF via Rust bindings |
| PDF Processing | PyMuPDF, pikepdf, pypdf |
| OCR | ocrmypdf + Tesseract |
| Styling | Tailwind CSS + Nord theme |
| Icons | Lucide |
