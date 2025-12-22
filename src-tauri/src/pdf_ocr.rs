//! PDF OCR module using OCRmyPDF via Python bridge.
//!
//! Provides OCR functionality for scanned PDFs through the Python backend.

use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use std::process::Command;
use tauri::AppHandle;

/// OCR dependency check result
#[derive(Debug, Serialize, Deserialize)]
pub struct OcrDependencies {
    pub ocrmypdf_installed: bool,
    pub ocrmypdf_version: Option<String>,
    pub tesseract_installed: bool,
    pub tesseract_version: Option<String>,
    pub available_languages: Vec<String>,
}

/// OCR analysis result
#[derive(Debug, Serialize, Deserialize)]
pub struct OcrAnalysis {
    pub success: bool,
    pub page_count: Option<u32>,
    pub has_text: Option<bool>,
    pub has_images: Option<bool>,
    pub needs_ocr: Option<bool>,
    pub recommendation: Option<String>,
    pub error: Option<String>,
}

/// OCR operation result
#[derive(Debug, Serialize, Deserialize)]
pub struct OcrResult {
    pub success: bool,
    pub output_path: Option<String>,
    pub exit_code: i32,
    pub message: Option<String>,
    pub error: Option<String>,
}

/// OCR options
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct OcrOptions {
    /// OCR language(s), e.g., "eng", "eng+spa"
    #[serde(default = "default_language")]
    pub language: String,
    /// Deskew pages before OCR
    #[serde(default)]
    pub deskew: bool,
    /// Rotate pages to correct orientation
    #[serde(default)]
    pub rotate_pages: bool,
    /// Remove background from pages
    #[serde(default)]
    pub remove_background: bool,
    /// Clean pages to improve OCR accuracy
    #[serde(default)]
    pub clean: bool,
    /// Skip pages that already have text
    #[serde(default)]
    pub skip_text: bool,
    /// Force OCR even if text is present
    #[serde(default)]
    pub force_ocr: bool,
    /// Redo OCR on pages that have text
    #[serde(default)]
    pub redo_ocr: bool,
    /// Optimization level (0-3)
    #[serde(default = "default_optimize")]
    pub optimize: i32,
}

fn default_language() -> String {
    "eng".to_string()
}

fn default_optimize() -> i32 {
    1
}

/// Resolve the OCR Python script path
fn resolve_ocr_script(app: &AppHandle) -> Option<PathBuf> {
    use tauri::Manager;

    // Try relative to executable (dev mode)
    if let Ok(mut exe) = std::env::current_exe() {
        for _ in 0..4 {
            exe.pop();
        }
        let script = exe.join("backend/pdf_ocr.py");
        if script.exists() {
            return Some(script);
        }
    }

    // Try app resource directory (bundled mode)
    if let Ok(resource) = app
        .path()
        .resolve("backend/pdf_ocr.py", tauri::path::BaseDirectory::Resource)
    {
        if resource.exists() {
            return Some(resource);
        }
    }

    // Fallback to current directory
    let cwd = PathBuf::from("backend/pdf_ocr.py");
    if cwd.exists() {
        return Some(cwd);
    }

    None
}

/// Resolve Python binary
fn resolve_python_bin() -> String {
    if let Ok(p) = std::env::var("APP_PYTHON_BIN") {
        return p;
    }

    let mut root = std::env::current_exe().unwrap_or_else(|_| PathBuf::from("."));
    for _ in 0..4 {
        root.pop();
    }

    let venv = root.join("backend/venv/bin/python3");
    if venv.exists() {
        return venv.to_string_lossy().to_string();
    }

    "python3".to_string()
}

/// Check OCR dependencies
pub fn check_dependencies(app: &AppHandle) -> Result<OcrDependencies, String> {
    let script = resolve_ocr_script(app)
        .ok_or_else(|| "OCR script not found (backend/pdf_ocr.py)".to_string())?;

    let python = resolve_python_bin();

    let output = Command::new(&python)
        .arg(&script)
        .arg("check")
        .output()
        .map_err(|e| format!("Failed to run OCR check: {}", e))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("OCR check failed: {}", stderr));
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    serde_json::from_str(&stdout)
        .map_err(|e| format!("Failed to parse OCR check result: {}", e))
}

/// Analyze PDF for OCR needs
pub fn analyze_pdf(app: &AppHandle, input: &str) -> Result<OcrAnalysis, String> {
    let script = resolve_ocr_script(app)
        .ok_or_else(|| "OCR script not found (backend/pdf_ocr.py)".to_string())?;

    let python = resolve_python_bin();

    let output = Command::new(&python)
        .arg(&script)
        .arg("analyze")
        .arg("--input")
        .arg(input)
        .output()
        .map_err(|e| format!("Failed to analyze PDF: {}", e))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("PDF analysis failed: {}", stderr));
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    serde_json::from_str(&stdout)
        .map_err(|e| format!("Failed to parse analysis result: {}", e))
}

/// Run OCR on a PDF
pub fn run_ocr(
    app: &AppHandle,
    input: &str,
    output: &str,
    options: OcrOptions,
) -> Result<OcrResult, String> {
    let script = resolve_ocr_script(app)
        .ok_or_else(|| "OCR script not found (backend/pdf_ocr.py)".to_string())?;

    let python = resolve_python_bin();

    let mut cmd = Command::new(&python);
    cmd.arg(&script)
        .arg("ocr")
        .arg("--input")
        .arg(input)
        .arg("--output")
        .arg(output)
        .arg("--language")
        .arg(&options.language)
        .arg("--optimize")
        .arg(options.optimize.to_string());

    if options.deskew {
        cmd.arg("--deskew");
    }
    if options.rotate_pages {
        cmd.arg("--rotate-pages");
    }
    if options.remove_background {
        cmd.arg("--remove-background");
    }
    if options.clean {
        cmd.arg("--clean");
    }
    if options.skip_text {
        cmd.arg("--skip-text");
    }
    if options.force_ocr {
        cmd.arg("--force-ocr");
    }
    if options.redo_ocr {
        cmd.arg("--redo-ocr");
    }

    let output_result = cmd
        .output()
        .map_err(|e| format!("Failed to run OCR: {}", e))?;

    if !output_result.status.success() {
        let stderr = String::from_utf8_lossy(&output_result.stderr);
        return Err(format!("OCR failed: {}", stderr));
    }

    let stdout = String::from_utf8_lossy(&output_result.stdout);
    serde_json::from_str(&stdout)
        .map_err(|e| format!("Failed to parse OCR result: {}", e))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_options() {
        let opts = OcrOptions::default();
        assert_eq!(opts.language, "eng");
        assert_eq!(opts.optimize, 1);
        assert!(!opts.deskew);
    }
}
