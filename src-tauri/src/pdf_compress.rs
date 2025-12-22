//! PDF Compression module using MuPDF.
//!
//! Provides compression functionality with multiple quality levels:
//! - Low: Just garbage collection (remove unused objects)
//! - Medium: Garbage + basic compression
//! - High: Full compression + optimization + linearization

use mupdf::pdf::{PdfDocument, PdfWriteOptions};
use serde::{Deserialize, Serialize};
use std::fs;

/// Compression level options
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum CompressionLevel {
    /// Remove unused objects only
    Low,
    /// Basic compression + garbage collection
    Medium,
    /// Maximum compression + optimization + linearization
    High,
}

impl Default for CompressionLevel {
    fn default() -> Self {
        Self::Medium
    }
}

/// Result of compression operation
#[derive(Debug, Serialize, Deserialize)]
pub struct CompressionResult {
    /// Path to the compressed file
    pub output_path: String,
    /// Original file size in bytes
    pub original_size: u64,
    /// Compressed file size in bytes
    pub compressed_size: u64,
    /// Compression ratio (compressed/original)
    pub ratio: f64,
    /// Bytes saved
    pub bytes_saved: i64,
    /// Percentage reduction
    pub percent_saved: f64,
}

/// Compress a PDF file
///
/// # Arguments
/// * `input` - Path to input PDF file
/// * `output` - Path to output PDF file (can be same as input for in-place)
/// * `level` - Compression level
///
/// # Returns
/// Result containing compression statistics
pub fn compress_pdf(
    input: &str,
    output: &str,
    level: CompressionLevel,
) -> Result<CompressionResult, String> {
    // Get original file size
    let original_size = fs::metadata(input)
        .map_err(|e| format!("Failed to read input file metadata: {}", e))?
        .len();

    // Open the PDF document
    let doc = PdfDocument::open(input)
        .map_err(|e| format!("Failed to open PDF: {:?}", e))?;

    // Configure write options based on compression level
    let mut options = PdfWriteOptions::default();

    match level {
        CompressionLevel::Low => {
            // Just remove unused objects
            options.set_garbage(true);
            options.set_garbage_level(1);
        }
        CompressionLevel::Medium => {
            // Garbage collection + basic compression
            options.set_garbage(true);
            options.set_garbage_level(2);
            options.set_compress(true);
            options.set_clean(true);
        }
        CompressionLevel::High => {
            // Maximum compression
            options.set_garbage(true);
            options.set_garbage_level(4); // Highest level
            options.set_compress(true);
            options.set_compress_images(true);
            options.set_compress_fonts(true);
            options.set_clean(true);
            options.set_sanitize(true);
            options.set_linear(true);
        }
    }

    // Handle in-place compression by using a temp file
    let is_in_place = input == output;
    let temp_output = if is_in_place {
        format!("{}.tmp", output)
    } else {
        output.to_string()
    };

    // Save with compression options
    doc.save_with_options(&temp_output, options)
        .map_err(|e| format!("Failed to save compressed PDF: {:?}", e))?;

    // If in-place, replace original with temp file
    if is_in_place {
        fs::rename(&temp_output, output)
            .map_err(|e| format!("Failed to replace original file: {}", e))?;
    }

    // Get compressed file size
    let compressed_size = fs::metadata(output)
        .map_err(|e| format!("Failed to read output file metadata: {}", e))?
        .len();

    // Calculate statistics
    let bytes_saved = original_size as i64 - compressed_size as i64;
    let ratio = compressed_size as f64 / original_size as f64;
    let percent_saved = if original_size > 0 {
        (1.0 - ratio) * 100.0
    } else {
        0.0
    };

    Ok(CompressionResult {
        output_path: output.to_string(),
        original_size,
        compressed_size,
        ratio,
        bytes_saved,
        percent_saved,
    })
}

/// Get estimated compression ratio without actually compressing
/// (based on analyzing the PDF structure)
pub fn estimate_compression(input: &str) -> Result<EstimationResult, String> {
    let original_size = fs::metadata(input)
        .map_err(|e| format!("Failed to read file: {}", e))?
        .len();

    let doc = PdfDocument::open(input)
        .map_err(|e| format!("Failed to open PDF: {:?}", e))?;

    // Count pages
    let page_count = doc.page_count()
        .map_err(|e| format!("Failed to get page count: {:?}", e))? as u32;

    // Estimate compression potential based on file size per page
    // PDFs with high size-per-page ratio usually compress better
    let bytes_per_page = original_size as f64 / page_count.max(1) as f64;

    let estimated_reduction = if bytes_per_page > 500_000.0 {
        // Large pages (likely uncompressed images) - high potential
        0.5 // 50% reduction possible
    } else if bytes_per_page > 100_000.0 {
        // Medium pages - moderate potential
        0.3 // 30% reduction possible
    } else {
        // Already compact - low potential
        0.1 // 10% reduction possible
    };

    Ok(EstimationResult {
        original_size,
        page_count,
        bytes_per_page: bytes_per_page as u64,
        estimated_reduction,
        estimated_size: (original_size as f64 * (1.0 - estimated_reduction)) as u64,
    })
}

#[derive(Debug, Serialize, Deserialize)]
pub struct EstimationResult {
    pub original_size: u64,
    pub page_count: u32,
    pub bytes_per_page: u64,
    pub estimated_reduction: f64,
    pub estimated_size: u64,
}

/// Format file size for display
pub fn format_size(bytes: u64) -> String {
    const KB: u64 = 1024;
    const MB: u64 = KB * 1024;
    const GB: u64 = MB * 1024;

    if bytes >= GB {
        format!("{:.2} GB", bytes as f64 / GB as f64)
    } else if bytes >= MB {
        format!("{:.2} MB", bytes as f64 / MB as f64)
    } else if bytes >= KB {
        format!("{:.2} KB", bytes as f64 / KB as f64)
    } else {
        format!("{} bytes", bytes)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_format_size() {
        assert_eq!(format_size(500), "500 bytes");
        assert_eq!(format_size(1024), "1.00 KB");
        assert_eq!(format_size(1536), "1.50 KB");
        assert_eq!(format_size(1048576), "1.00 MB");
        assert_eq!(format_size(1073741824), "1.00 GB");
    }

    #[test]
    fn test_compression_level_default() {
        assert_eq!(CompressionLevel::default(), CompressionLevel::Medium);
    }
}
