//! PDF Viewer module using MuPDF for high-quality rendering.
//!
//! This module provides Tauri commands for:
//! - Loading PDF documents
//! - Rendering pages at various DPI/quality levels
//! - Getting document metadata
//! - Extracting text with positions for text selection

use base64::Engine;
use mupdf::text_page::TextPageOptions;
use mupdf::{Colorspace, Document, Matrix, MetadataName, Outline as MuOutline};
use serde::{Deserialize, Serialize};
use std::io::Cursor;

/// PDF document info
#[derive(Debug, Serialize, Deserialize)]
pub struct PdfInfo {
    pub path: String,
    pub num_pages: u32,
    pub page_sizes: Vec<PageSize>,
}

/// Page size in points (1/72 inch)
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct PageSize {
    pub width: f32,
    pub height: f32,
}

/// Rendered page result
#[derive(Debug, Serialize, Deserialize)]
pub struct RenderedPage {
    /// Base64-encoded PNG image data
    pub data: String,
    /// Width of the rendered image in pixels
    pub width: u32,
    /// Height of the rendered image in pixels
    pub height: u32,
    /// Page number (1-indexed)
    pub page: u32,
}

/// Load a PDF and return its info
#[tauri::command]
pub fn pdf_open(path: String) -> Result<PdfInfo, String> {
    let document = Document::open(&path)
        .map_err(|e| format!("Failed to load PDF: {:?}", e))?;

    let num_pages = document
        .page_count()
        .map_err(|e| format!("Failed to get page count: {:?}", e))? as u32;

    let mut page_sizes = Vec::with_capacity(num_pages as usize);

    for i in 0..num_pages {
        match document.load_page(i as i32) {
            Ok(page) => {
                let bounds = page.bounds().map_err(|e| format!("Failed to get page bounds: {:?}", e))?;
                page_sizes.push(PageSize {
                    width: bounds.width(),
                    height: bounds.height(),
                });
            }
            Err(e) => {
                log::warn!("Failed to load page {}: {:?}", i, e);
                page_sizes.push(PageSize {
                    width: 612.0, // Default letter width
                    height: 792.0, // Default letter height
                });
            }
        }
    }

    Ok(PdfInfo {
        path,
        num_pages,
        page_sizes,
    })
}

/// Render a single page at the specified DPI
#[tauri::command]
pub fn pdf_render_page(
    path: String,
    page: u32,
    dpi: Option<u32>,
    max_width: Option<u32>,
    max_height: Option<u32>,
    hide_annotations: Option<bool>,
) -> Result<RenderedPage, String> {
    let dpi = dpi.unwrap_or(150);
    let show_annots = !hide_annotations.unwrap_or(false);

    let document = Document::open(&path)
        .map_err(|e| format!("Failed to load PDF: {:?}", e))?;

    let page_index = (page - 1) as i32;
    let pdf_page = document
        .load_page(page_index)
        .map_err(|e| format!("Failed to get page {}: {:?}", page, e))?;

    // Get page dimensions in points (72 points per inch)
    let bounds = pdf_page.bounds().map_err(|e| format!("Failed to get page bounds: {:?}", e))?;
    let width_points = bounds.width();
    let height_points = bounds.height();

    // Calculate scale factor based on DPI (PDF default is 72 DPI)
    let mut scale = dpi as f32 / 72.0;

    // Calculate pixel dimensions
    let mut pixel_width = (width_points * scale) as u32;
    let mut pixel_height = (height_points * scale) as u32;

    // Apply max constraints if specified
    if let Some(max_w) = max_width {
        if pixel_width > max_w {
            let constraint_scale = max_w as f32 / pixel_width as f32;
            scale *= constraint_scale;
            pixel_width = max_w;
            pixel_height = (pixel_height as f32 * constraint_scale) as u32;
        }
    }
    if let Some(max_h) = max_height {
        if pixel_height > max_h {
            let constraint_scale = max_h as f32 / pixel_height as f32;
            scale *= constraint_scale;
            pixel_height = max_h;
            pixel_width = (pixel_width as f32 * constraint_scale) as u32;
        }
    }

    // Create transformation matrix for scaling
    let matrix = Matrix::new_scale(scale, scale);

    // Render the page to a pixmap (RGB with alpha)
    // show_annots controls whether PDF annotations are rendered
    let pixmap = pdf_page
        .to_pixmap(&matrix, &Colorspace::device_rgb(), true, show_annots)
        .map_err(|e| format!("Failed to render page: {:?}", e))?;

    // Get actual rendered dimensions
    let actual_width = pixmap.width() as u32;
    let actual_height = pixmap.height() as u32;

    // Write pixmap to PNG
    let mut png_data = Vec::new();
    let mut cursor = Cursor::new(&mut png_data);
    pixmap
        .write_to(&mut cursor, mupdf::ImageFormat::PNG)
        .map_err(|e| format!("Failed to encode PNG: {:?}", e))?;

    // Encode as base64
    let base64_data = base64::engine::general_purpose::STANDARD.encode(&png_data);

    Ok(RenderedPage {
        data: base64_data,
        width: actual_width,
        height: actual_height,
        page,
    })
}

/// Render a thumbnail (low-res) for a page
#[tauri::command]
pub fn pdf_render_thumbnail(
    path: String,
    page: u32,
    max_size: Option<u32>,
) -> Result<RenderedPage, String> {
    let max_size = max_size.unwrap_or(200);
    pdf_render_page(path, page, Some(72), Some(max_size), Some(max_size), None)
}

/// Batch render multiple thumbnails
#[tauri::command]
pub fn pdf_render_thumbnails(
    path: String,
    pages: Vec<u32>,
    max_size: Option<u32>,
) -> Result<Vec<RenderedPage>, String> {
    let max_size = max_size.unwrap_or(200);

    let document = Document::open(&path)
        .map_err(|e| format!("Failed to load PDF: {:?}", e))?;

    let mut results = Vec::with_capacity(pages.len());

    for page_num in pages {
        let page_index = (page_num - 1) as i32;

        match document.load_page(page_index) {
            Ok(pdf_page) => {
                match pdf_page.bounds() {
                    Ok(bounds) => {
                        let width_points = bounds.width();
                        let height_points = bounds.height();

                        // Calculate thumbnail scale maintaining aspect ratio
                        let aspect = width_points / height_points;
                        let thumb_width = if aspect > 1.0 {
                            max_size as f32
                        } else {
                            max_size as f32 * aspect
                        };

                        // Calculate scale to achieve thumbnail size
                        let scale = thumb_width / width_points;
                        let matrix = Matrix::new_scale(scale, scale);

                        match pdf_page.to_pixmap(&matrix, &Colorspace::device_rgb(), true, false) {
                            Ok(pixmap) => {
                                let mut png_data = Vec::new();
                                let mut cursor = Cursor::new(&mut png_data);

                                if pixmap.write_to(&mut cursor, mupdf::ImageFormat::PNG).is_ok() {
                                    let base64_data =
                                        base64::engine::general_purpose::STANDARD.encode(&png_data);
                                    results.push(RenderedPage {
                                        data: base64_data,
                                        width: pixmap.width() as u32,
                                        height: pixmap.height() as u32,
                                        page: page_num,
                                    });
                                }
                            }
                            Err(e) => {
                                log::warn!("Failed to render thumbnail for page {}: {:?}", page_num, e);
                            }
                        }
                    }
                    Err(e) => {
                        log::warn!("Failed to get bounds for page {}: {:?}", page_num, e);
                    }
                }
            }
            Err(e) => {
                log::warn!("Failed to get page {}: {:?}", page_num, e);
            }
        }
    }

    Ok(results)
}

/// Close a document (no-op since MuPDF handles cleanup automatically)
#[tauri::command]
pub fn pdf_close(_path: String) -> Result<(), String> {
    Ok(())
}

/// Rectangle in normalized coordinates (0-1)
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct NormalizedRect {
    pub x: f32,
    pub y: f32,
    pub width: f32,
    pub height: f32,
}

/// A single character with its bounding box
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct TextCharInfo {
    pub char: String,
    pub quad: [f32; 8], // 4 corners: [x0,y0, x1,y1, x2,y2, x3,y3]
}

/// A line of text with its bounding box and characters
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct TextLineInfo {
    pub text: String,
    pub rect: NormalizedRect,
    pub chars: Vec<TextCharInfo>,
}

/// A block of text (paragraph) with its lines
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct TextBlockInfo {
    pub rect: NormalizedRect,
    pub lines: Vec<TextLineInfo>,
}

/// Text content of a page
#[derive(Debug, Serialize, Deserialize)]
pub struct PageTextContent {
    pub page: u32,
    pub blocks: Vec<TextBlockInfo>,
}

/// Extract text blocks with positions from a page
#[tauri::command]
pub fn pdf_get_text_blocks(path: String, page: u32) -> Result<PageTextContent, String> {
    let document = Document::open(&path)
        .map_err(|e| format!("Failed to load PDF: {:?}", e))?;

    let page_index = (page - 1) as i32;
    let pdf_page = document
        .load_page(page_index)
        .map_err(|e| format!("Failed to get page {}: {:?}", page, e))?;

    // Get page dimensions for normalization
    let bounds = pdf_page.bounds()
        .map_err(|e| format!("Failed to get page bounds: {:?}", e))?;
    let page_width = bounds.width();
    let page_height = bounds.height();

    // Extract text page
    let text_page = pdf_page
        .to_text_page(TextPageOptions::empty())
        .map_err(|e| format!("Failed to extract text: {:?}", e))?;

    let mut blocks = Vec::new();

    for block in text_page.blocks() {
        // Skip image blocks
        if block.lines().next().is_none() {
            continue;
        }

        let block_bounds = block.bounds();
        let block_rect = NormalizedRect {
            x: block_bounds.x0 / page_width,
            y: block_bounds.y0 / page_height,
            width: (block_bounds.x1 - block_bounds.x0) / page_width,
            height: (block_bounds.y1 - block_bounds.y0) / page_height,
        };

        let mut lines = Vec::new();

        for line in block.lines() {
            let line_bounds = line.bounds();
            let line_rect = NormalizedRect {
                x: line_bounds.x0 / page_width,
                y: line_bounds.y0 / page_height,
                width: (line_bounds.x1 - line_bounds.x0) / page_width,
                height: (line_bounds.y1 - line_bounds.y0) / page_height,
            };

            let mut chars = Vec::new();
            let mut line_text = String::new();

            for char_info in line.chars() {
                if let Some(c) = char_info.char() {
                    line_text.push(c);

                    let quad = char_info.quad();
                    // Normalize quad coordinates
                    let normalized_quad = [
                        quad.ul.x / page_width,
                        quad.ul.y / page_height,
                        quad.ur.x / page_width,
                        quad.ur.y / page_height,
                        quad.lr.x / page_width,
                        quad.lr.y / page_height,
                        quad.ll.x / page_width,
                        quad.ll.y / page_height,
                    ];

                    chars.push(TextCharInfo {
                        char: c.to_string(),
                        quad: normalized_quad,
                    });
                }
            }

            if !line_text.is_empty() {
                lines.push(TextLineInfo {
                    text: line_text,
                    rect: line_rect,
                    chars,
                });
            }
        }

        if !lines.is_empty() {
            blocks.push(TextBlockInfo {
                rect: block_rect,
                lines,
            });
        }
    }

    Ok(PageTextContent { page, blocks })
}

/// Search result with page and position info
#[derive(Debug, Serialize, Deserialize)]
pub struct SearchResult {
    /// Page number (1-indexed)
    pub page: u32,
    /// Normalized Y position of the match (0-1)
    pub y: f32,
    /// Match rectangle (normalized coordinates)
    pub rect: NormalizedRect,
    /// Text context around the match
    pub context: String,
}

/// Search results for the entire document
#[derive(Debug, Serialize, Deserialize)]
pub struct SearchResults {
    /// Search query
    pub query: String,
    /// Total number of matches
    pub total: u32,
    /// List of results
    pub results: Vec<SearchResult>,
}

/// Search for text across all pages of a PDF
/// Uses MuPDF's native search which is much faster than JavaScript iteration
/// Runs in a blocking thread to avoid freezing the UI
#[tauri::command]
pub async fn pdf_search_text(path: String, query: String, max_results: Option<u32>) -> Result<SearchResults, String> {
    let max_results = max_results.unwrap_or(1000);

    if query.is_empty() {
        return Ok(SearchResults {
            query,
            total: 0,
            results: Vec::new(),
        });
    }

    // Run the heavy search in a blocking thread to not freeze UI
    let query_clone = query.clone();
    let results = tauri::async_runtime::spawn_blocking(move || {
        search_text_blocking(&path, &query_clone, max_results)
    })
    .await
    .map_err(|e| format!("Search task failed: {:?}", e))??;

    Ok(SearchResults {
        query,
        total: results.len() as u32,
        results,
    })
}

/// Internal blocking search function
fn search_text_blocking(path: &str, query: &str, max_results: u32) -> Result<Vec<SearchResult>, String> {
    let document = Document::open(path)
        .map_err(|e| format!("Failed to load PDF: {:?}", e))?;

    let num_pages = document
        .page_count()
        .map_err(|e| format!("Failed to get page count: {:?}", e))? as u32;

    let mut results = Vec::new();
    let mut total_found: u32 = 0;

    // Track last result position for deduplication
    let mut last_page: u32 = 0;
    let mut last_y: f32 = -1.0;
    const Y_THRESHOLD: f32 = 0.02; // 2% of page height threshold for dedup

    for page_num in 0..num_pages {
        if total_found >= max_results {
            break;
        }

        let pdf_page = match document.load_page(page_num as i32) {
            Ok(p) => p,
            Err(_) => continue,
        };

        let bounds = match pdf_page.bounds() {
            Ok(b) => b,
            Err(_) => continue,
        };

        let page_width = bounds.width();
        let page_height = bounds.height();

        // Use MuPDF's native search
        let hits_remaining = (max_results - total_found).min(100);
        let search_results = match pdf_page.search(query, hits_remaining) {
            Ok(r) => r,
            Err(_) => continue,
        };

        // Get text content for context extraction
        let text_page = pdf_page.to_text_page(TextPageOptions::empty()).ok();

        for quad in search_results.iter() {
            // Calculate bounding box from quad
            let x0 = quad.ul.x.min(quad.ll.x);
            let y0 = quad.ul.y.min(quad.ur.y);
            let x1 = quad.ur.x.max(quad.lr.x);
            let y1 = quad.ll.y.max(quad.lr.y);

            let normalized_y = y0 / page_height;
            let current_page = page_num + 1;

            // Deduplicate: skip if same page and very close Y position
            if current_page == last_page && (normalized_y - last_y).abs() < Y_THRESHOLD {
                continue;
            }

            let rect = NormalizedRect {
                x: x0 / page_width,
                y: normalized_y,
                width: (x1 - x0) / page_width,
                height: (y1 - y0) / page_height,
            };

            // Try to get context text around the match
            let context = if let Some(ref tp) = text_page {
                extract_context_around_match(tp, query, y0, page_height)
            } else {
                query.to_string()
            };

            results.push(SearchResult {
                page: current_page, // 1-indexed
                y: normalized_y,
                rect,
                context,
            });

            last_page = current_page;
            last_y = normalized_y;
            total_found += 1;

            if total_found >= max_results {
                break;
            }
        }
    }

    Ok(results)
}

/// Extract context text around a match position
fn extract_context_around_match(text_page: &mupdf::TextPage, query: &str, match_y: f32, page_height: f32) -> String {
    let query_lower = query.to_lowercase();

    for block in text_page.blocks() {
        for line in block.lines() {
            let line_bounds = line.bounds();
            // Check if this line is near the match position
            if (line_bounds.y0 - match_y).abs() < 5.0 ||
               (line_bounds.y1 - match_y).abs() < 5.0 ||
               (match_y >= line_bounds.y0 && match_y <= line_bounds.y1) {

                let mut line_text = String::new();
                for char_info in line.chars() {
                    if let Some(c) = char_info.char() {
                        line_text.push(c);
                    }
                }

                // Check if this line contains the query
                if line_text.to_lowercase().contains(&query_lower) {
                    // Return a trimmed context
                    let trimmed = line_text.trim();
                    if trimmed.len() > 100 {
                        return format!("{}...", &trimmed[..100]);
                    }
                    return trimmed.to_string();
                }
            }
        }
    }

    query.to_string()
}

/// PDF outline (table of contents) entry
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct OutlineEntry {
    /// Title of the outline entry
    pub title: String,
    /// Target page number (1-indexed), if available
    pub page: Option<u32>,
    /// Y position on the page (normalized 0-1)
    pub y: Option<f32>,
    /// Child entries (sub-sections)
    pub children: Vec<OutlineEntry>,
}

/// Convert MuPDF Outline to our OutlineEntry, fetching page dimensions for normalization
fn convert_outline(outline: &MuOutline, document: &Document) -> OutlineEntry {
    let (page, normalized_y) = if let Some(p) = outline.page {
        // Page is 0-indexed in the outline
        let page_num = p + 1; // Convert to 1-indexed

        // Normalize Y coordinate if we have a valid page
        let norm_y = if outline.y > 0.0 {
            if let Ok(pdf_page) = document.load_page(p as i32) {
                if let Ok(bounds) = pdf_page.bounds() {
                    Some(outline.y / bounds.height())
                } else {
                    None
                }
            } else {
                None
            }
        } else {
            None
        };

        (Some(page_num), norm_y)
    } else {
        (None, None)
    };

    OutlineEntry {
        title: outline.title.clone(),
        page,
        y: normalized_y,
        children: outline.down.iter().map(|c| convert_outline(c, document)).collect(),
    }
}

/// Get PDF outline (table of contents)
#[tauri::command]
pub fn pdf_get_outlines(path: String) -> Result<Vec<OutlineEntry>, String> {
    let document = Document::open(&path)
        .map_err(|e| format!("Failed to load PDF: {:?}", e))?;

    let outlines = document
        .outlines()
        .map_err(|e| format!("Failed to get outlines: {:?}", e))?;

    let entries: Vec<OutlineEntry> = outlines
        .iter()
        .map(|o| convert_outline(o, &document))
        .collect();

    Ok(entries)
}

/// PDF document metadata
#[derive(Debug, Serialize, Deserialize)]
pub struct PdfMetadata {
    /// PDF format/version (e.g., "PDF 1.7")
    pub format: Option<String>,
    /// Encryption info
    pub encryption: Option<String>,
    /// Document title
    pub title: Option<String>,
    /// Author name
    pub author: Option<String>,
    /// Subject/description
    pub subject: Option<String>,
    /// Keywords
    pub keywords: Option<String>,
    /// Software that created the document
    pub creator: Option<String>,
    /// Software that produced the PDF
    pub producer: Option<String>,
    /// Creation date (raw PDF format)
    pub creation_date: Option<String>,
    /// Modification date (raw PDF format)
    pub mod_date: Option<String>,
    /// Number of pages
    pub page_count: u32,
    /// File size in bytes
    pub file_size: u64,
}

/// Get PDF metadata
#[tauri::command]
pub fn pdf_get_metadata(path: String) -> Result<PdfMetadata, String> {
    let document = Document::open(&path)
        .map_err(|e| format!("Failed to load PDF: {:?}", e))?;

    let page_count = document
        .page_count()
        .map_err(|e| format!("Failed to get page count: {:?}", e))? as u32;

    // Helper to get metadata, returning None for empty strings
    let get_meta = |name: MetadataName| -> Option<String> {
        document.metadata(name).ok().filter(|s| !s.is_empty())
    };

    // Get file size
    let file_size = std::fs::metadata(&path)
        .map(|m| m.len())
        .unwrap_or(0);

    Ok(PdfMetadata {
        format: get_meta(MetadataName::Format),
        encryption: get_meta(MetadataName::Encryption),
        title: get_meta(MetadataName::Title),
        author: get_meta(MetadataName::Author),
        subject: get_meta(MetadataName::Subject),
        keywords: get_meta(MetadataName::Keywords),
        creator: get_meta(MetadataName::Creator),
        producer: get_meta(MetadataName::Producer),
        creation_date: get_meta(MetadataName::CreationDate),
        mod_date: get_meta(MetadataName::ModDate),
        page_count,
        file_size,
    })
}
