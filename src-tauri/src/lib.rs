use serde::{Deserialize, Serialize};

mod annotations;
mod pdf_compress;
mod pdf_ocr;
mod pdf_viewer;
mod python_bridge;

use python_bridge::PythonBridge;
use tauri::menu::{MenuBuilder, MenuItemBuilder, SubmenuBuilder};
use tauri::{AppHandle, Emitter, Manager};

#[derive(Debug, Deserialize, Serialize)]
struct ImageTransform {
    rotation: Option<i32>,
    flip_h: Option<bool>,
    flip_v: Option<bool>,
    orientation: Option<String>, // "auto", "portrait", "landscape"
}

// ============================================================================
// Python Bridge Commands
// ============================================================================

/// Check if Python is available and return version info
#[tauri::command]
fn python_check(app: AppHandle) -> Result<PythonStatus, String> {
    let bridge = PythonBridge::new(&app).map_err(|e| e.to_string())?;

    let version = bridge.python_version().map_err(|e| e.to_string())?;
    let path = bridge.python_path().to_string_lossy().to_string();

    Ok(PythonStatus {
        available: true,
        version,
        path,
    })
}

#[derive(Debug, Serialize)]
struct PythonStatus {
    available: bool,
    version: String,
    path: String,
}

/// Check if specific Python packages are installed
#[tauri::command]
fn python_check_packages(app: AppHandle, packages: Vec<String>) -> Result<PackageCheckResult, String> {
    let bridge = PythonBridge::new(&app).map_err(|e| e.to_string())?;

    let pkg_refs: Vec<&str> = packages.iter().map(|s| s.as_str()).collect();
    let missing = bridge.check_packages(&pkg_refs).map_err(|e| e.to_string())?;

    Ok(PackageCheckResult {
        all_installed: missing.is_empty(),
        missing,
    })
}

#[derive(Debug, Serialize)]
struct PackageCheckResult {
    all_installed: bool,
    missing: Vec<String>,
}

/// Install a Python package
#[tauri::command]
fn python_install_package(app: AppHandle, package: String) -> Result<(), String> {
    let bridge = PythonBridge::new(&app).map_err(|e| e.to_string())?;
    bridge.install_package(&package).map_err(|e| e.to_string())
}

// ============================================================================
// PDF Compression Commands
// ============================================================================

/// Compress a PDF file
#[tauri::command]
fn compress_pdf(
    app: AppHandle,
    input: String,
    output: Option<String>,
    level: Option<String>,
) -> Result<pdf_compress::CompressionResult, String> {
    let output_path = output.unwrap_or_else(|| {
        let cache_dir = app
            .path()
            .app_cache_dir()
            .unwrap_or_else(|_| std::env::temp_dir());
        cache_dir
            .join("tlacuilo-compressed.pdf")
            .to_string_lossy()
            .to_string()
    });

    let compression_level = match level.as_deref() {
        Some("low") => pdf_compress::CompressionLevel::Low,
        Some("high") => pdf_compress::CompressionLevel::High,
        _ => pdf_compress::CompressionLevel::Medium,
    };

    pdf_compress::compress_pdf(&input, &output_path, compression_level)
}

/// Estimate compression potential for a PDF
#[tauri::command]
fn estimate_compression(input: String) -> Result<pdf_compress::EstimationResult, String> {
    pdf_compress::estimate_compression(&input)
}

// ============================================================================
// OCR Commands
// ============================================================================

/// Check OCR dependencies
#[tauri::command]
fn ocr_check_dependencies(app: AppHandle) -> Result<pdf_ocr::OcrDependencies, String> {
    pdf_ocr::check_dependencies(&app)
}

/// Analyze PDF for OCR needs
#[tauri::command]
fn ocr_analyze_pdf(app: AppHandle, input: String) -> Result<pdf_ocr::OcrAnalysis, String> {
    pdf_ocr::analyze_pdf(&app, &input)
}

/// Run OCR on a PDF
#[tauri::command]
fn ocr_run(
    app: AppHandle,
    input: String,
    output: Option<String>,
    options: Option<pdf_ocr::OcrOptions>,
) -> Result<pdf_ocr::OcrResult, String> {
    let output_path = output.unwrap_or_else(|| {
        let cache_dir = app
            .path()
            .app_cache_dir()
            .unwrap_or_else(|_| std::env::temp_dir());

        // Create a session directory with UUID to avoid conflicts
        let session_id = uuid::Uuid::new_v4().to_string();
        let session_dir = cache_dir.join("ocr-sessions").join(&session_id);

        // Create the session directory if it doesn't exist
        let _ = std::fs::create_dir_all(&session_dir);

        // Preserve original filename
        let original_filename = std::path::Path::new(&input)
            .file_name()
            .map(|f| f.to_string_lossy().to_string())
            .unwrap_or_else(|| "document.pdf".to_string());

        session_dir
            .join(&original_filename)
            .to_string_lossy()
            .to_string()
    });

    let opts = options.unwrap_or_default();
    pdf_ocr::run_ocr(&app, &input, &output_path, opts)
}

// ============================================================================
// Annotation Embedding Commands (PythonBridge)
// ============================================================================

/// Embed annotations from JSON into a PDF file
#[tauri::command]
fn annotations_embed_in_pdf(
    app: AppHandle,
    input: String,
    annotations_json: String,
    output: Option<String>,
) -> Result<AnnotationEmbedResult, String> {
    let output_path = output.unwrap_or_else(|| {
        let cache_dir = app
            .path()
            .app_cache_dir()
            .unwrap_or_else(|_| std::env::temp_dir());
        cache_dir
            .join("tlacuilo-annotated.pdf")
            .to_string_lossy()
            .to_string()
    });

    let bridge = PythonBridge::new(&app).map_err(|e| e.to_string())?;

    let args: Vec<&str> = vec![
        "embed",
        "--input", &input,
        "--annotations", &annotations_json,
        "--output", &output_path,
    ];

    let result = bridge
        .run_script("pdf_annotations.py", &args)
        .map_err(|e| e.to_string())?;

    // Parse the JSON output
    let stats: serde_json::Value = serde_json::from_str(&result.stdout)
        .map_err(|e| format!("Failed to parse result: {}", e))?;

    Ok(AnnotationEmbedResult {
        output_path,
        total: stats["total"].as_u64().unwrap_or(0) as u32,
        errors: stats["errors"]
            .as_array()
            .map(|arr| arr.iter().filter_map(|v| v.as_str().map(String::from)).collect())
            .unwrap_or_default(),
    })
}

#[derive(Debug, Serialize)]
struct AnnotationEmbedResult {
    output_path: String,
    total: u32,
    errors: Vec<String>,
}

/// Read annotations from a PDF file and return as JSON
#[tauri::command]
fn annotations_read_from_pdf(app: AppHandle, input: String) -> Result<String, String> {
    let bridge = PythonBridge::new(&app).map_err(|e| e.to_string())?;

    let args: Vec<&str> = vec!["read", "--input", &input];

    let result = bridge
        .run_script("pdf_annotations.py", &args)
        .map_err(|e| e.to_string())?;

    // Return the JSON directly
    Ok(result.stdout.trim().to_string())
}

/// Export annotations from PDF to XFDF format
#[tauri::command]
fn annotations_export_xfdf(
    app: AppHandle,
    input: String,
    output: String,
) -> Result<XfdfExportResult, String> {
    let bridge = PythonBridge::new(&app).map_err(|e| e.to_string())?;

    let args: Vec<&str> = vec!["export-xfdf", "--input", &input, "--output", &output];

    let result = bridge
        .run_script("pdf_annotations.py", &args)
        .map_err(|e| e.to_string())?;

    let stats: serde_json::Value = serde_json::from_str(&result.stdout)
        .map_err(|e| format!("Failed to parse result: {}", e))?;

    Ok(XfdfExportResult {
        output_path: output,
        exported: stats["exported"].as_u64().unwrap_or(0) as u32,
    })
}

#[derive(Debug, Serialize)]
struct XfdfExportResult {
    output_path: String,
    exported: u32,
}

/// Import annotations from XFDF into a PDF
#[tauri::command]
fn annotations_import_xfdf(
    app: AppHandle,
    input: String,
    xfdf: String,
    output: Option<String>,
) -> Result<AnnotationEmbedResult, String> {
    let output_path = output.unwrap_or_else(|| {
        let cache_dir = app
            .path()
            .app_cache_dir()
            .unwrap_or_else(|_| std::env::temp_dir());
        cache_dir
            .join("tlacuilo-xfdf-imported.pdf")
            .to_string_lossy()
            .to_string()
    });

    let bridge = PythonBridge::new(&app).map_err(|e| e.to_string())?;

    let args: Vec<&str> = vec![
        "import-xfdf",
        "--input", &input,
        "--xfdf", &xfdf,
        "--output", &output_path,
    ];

    let result = bridge
        .run_script("pdf_annotations.py", &args)
        .map_err(|e| e.to_string())?;

    let stats: serde_json::Value = serde_json::from_str(&result.stdout)
        .map_err(|e| format!("Failed to parse result: {}", e))?;

    Ok(AnnotationEmbedResult {
        output_path,
        total: stats["total"].as_u64().unwrap_or(0) as u32,
        errors: stats["errors"]
            .as_array()
            .map(|arr| arr.iter().filter_map(|v| v.as_str().map(String::from)).collect())
            .unwrap_or_default(),
    })
}

// ============================================================================
// Print Commands
// ============================================================================

#[derive(Debug, Serialize)]
struct PrintPrepareResult {
    output_path: String,
}

/// Prepare a PDF for printing by optionally embedding annotations
#[tauri::command]
fn print_prepare_pdf(
    app: AppHandle,
    input: String,
    annotations_json: String,
) -> Result<PrintPrepareResult, String> {
    // Create a temp file for the annotated PDF
    let cache_dir = app
        .path()
        .app_cache_dir()
        .unwrap_or_else(|_| std::env::temp_dir());

    // Ensure the cache directory exists
    std::fs::create_dir_all(&cache_dir)
        .map_err(|e| format!("Failed to create cache directory: {}", e))?;

    let temp_path = cache_dir
        .join(format!("tlacuilo-print-{}.pdf", uuid::Uuid::new_v4()))
        .to_string_lossy()
        .to_string();

    let bridge = PythonBridge::new(&app).map_err(|e| e.to_string())?;

    let args: Vec<&str> = vec![
        "embed",
        "--input", &input,
        "--annotations", &annotations_json,
        "--output", &temp_path,
    ];

    bridge
        .run_script("pdf_annotations.py", &args)
        .map_err(|e| e.to_string())?;

    Ok(PrintPrepareResult {
        output_path: temp_path,
    })
}

/// Open a PDF file in the system's print dialog
#[tauri::command]
fn print_pdf(path: String) -> Result<(), String> {
    #[cfg(target_os = "linux")]
    {
        // Try different methods to open print dialog on Linux
        // First try okular with --print flag (if available)
        let okular_result = std::process::Command::new("okular")
            .arg("--print")
            .arg(&path)
            .spawn();

        if okular_result.is_ok() {
            return Ok(());
        }

        // Try evince (GNOME PDF viewer) - it doesn't have a direct print flag,
        // but we can open it and user can print with Ctrl+P
        let evince_result = std::process::Command::new("evince")
            .arg(&path)
            .spawn();

        if evince_result.is_ok() {
            return Ok(());
        }

        // Fall back to xdg-open (opens in default PDF viewer)
        std::process::Command::new("xdg-open")
            .arg(&path)
            .spawn()
            .map_err(|e| format!("Failed to open PDF viewer: {}", e))?;
    }

    #[cfg(target_os = "macos")]
    {
        // On macOS, use lpr for direct printing or open with Preview
        // lpr sends directly to print queue, so we use Preview instead
        std::process::Command::new("open")
            .arg("-a")
            .arg("Preview")
            .arg(&path)
            .spawn()
            .map_err(|e| format!("Failed to open print dialog: {}", e))?;
    }

    #[cfg(target_os = "windows")]
    {
        // On Windows, use ShellExecute with "print" verb
        std::process::Command::new("rundll32")
            .args(["mshtml.dll,PrintHTML", &path])
            .spawn()
            .or_else(|_| {
                // Fallback: open the file and let user print manually
                std::process::Command::new("cmd")
                    .args(["/C", "start", "", &path])
                    .spawn()
            })
            .map_err(|e| format!("Failed to open print dialog: {}", e))?;
    }

    Ok(())
}

// ============================================================================
// PDF Operations Commands (PythonBridge)
// ============================================================================

#[tauri::command]
fn merge_pdfs(app: AppHandle, inputs: Vec<String>, output: Option<String>) -> Result<String, String> {
    if inputs.len() < 2 {
        return Err("Provide at least two PDF paths to merge.".into());
    }

    let output_path = output.unwrap_or_else(|| {
        let cache_dir = app
            .path()
            .app_cache_dir()
            .unwrap_or_else(|_| std::env::temp_dir());
        cache_dir.join("tlacuilo-merge.pdf").to_string_lossy().to_string()
    });

    let bridge = PythonBridge::new(&app).map_err(|e| e.to_string())?;

    let mut args = vec!["merge", "--output", &output_path, "--inputs"];
    let input_refs: Vec<&str> = inputs.iter().map(|s| s.as_str()).collect();
    args.extend(input_refs);

    bridge
        .run_script("pdf_pages.py", &args)
        .map_err(|e| e.to_string())?;

    Ok(output_path)
}

#[tauri::command]
fn merge_pages(
    app: AppHandle,
    pages: Vec<(String, i32)>,
    output: Option<String>,
) -> Result<String, String> {
    if pages.is_empty() {
        return Err("Provide at least one page specification.".into());
    }

    let output_path = output.unwrap_or_else(|| {
        let cache_dir = app
            .path()
            .app_cache_dir()
            .unwrap_or_else(|_| std::env::temp_dir());
        cache_dir
            .join("tlacuilo-merged-pages.pdf")
            .to_string_lossy()
            .to_string()
    });

    let bridge = PythonBridge::new(&app).map_err(|e| e.to_string())?;

    // Convert pages to format: file:page file:page ...
    let page_args: Vec<String> = pages
        .iter()
        .map(|(file, page)| format!("{}:{}", file, page))
        .collect();

    let mut args = vec!["merge-pages", "--output", &output_path, "--pages"];
    let page_refs: Vec<&str> = page_args.iter().map(|s| s.as_str()).collect();
    args.extend(page_refs);

    bridge
        .run_script("pdf_pages.py", &args)
        .map_err(|e| e.to_string())?;

    Ok(output_path)
}

#[tauri::command]
fn split_pdf(
    app: AppHandle,
    input: String,
    output_dir: Option<String>,
    ranges: Option<Vec<String>>,
) -> Result<Vec<String>, String> {
    let out_dir = output_dir.unwrap_or_else(|| {
        let cache_dir = app
            .path()
            .app_cache_dir()
            .unwrap_or_else(|_| std::env::temp_dir());
        cache_dir.join("tlacuilo-split").to_string_lossy().to_string()
    });

    let bridge = PythonBridge::new(&app).map_err(|e| e.to_string())?;

    let mut args: Vec<&str> = vec!["split", "--input", &input, "--output-dir", &out_dir];

    // Add ranges if provided
    let range_refs: Vec<String> = ranges.as_ref().map(|r| r.clone()).unwrap_or_default();
    if !range_refs.is_empty() {
        args.push("--ranges");
        for r in &range_refs {
            args.push(r);
        }
    }

    bridge
        .run_script("pdf_pages.py", &args)
        .map_err(|e| e.to_string())?;

    // Return the output directory and the number of files created based on ranges
    let num_files = ranges.as_ref().map(|r| r.len()).unwrap_or(0);
    let mut result = vec![out_dir.clone()];
    for i in 1..=num_files.max(1) {
        result.push(format!("{}/split_{}.pdf", out_dir, i));
    }
    Ok(result)
}

#[tauri::command]
fn rotate_pdf(
    app: AppHandle,
    input: String,
    degrees: i32,
    output: Option<String>,
    rotations: Option<Vec<String>>,
) -> Result<String, String> {
    let out_path = output.unwrap_or_else(|| {
        let cache_dir = app
            .path()
            .app_cache_dir()
            .unwrap_or_else(|_| std::env::temp_dir());
        cache_dir.join("tlacuilo-rotated.pdf").to_string_lossy().to_string()
    });

    let bridge = PythonBridge::new(&app).map_err(|e| e.to_string())?;

    let degrees_str = degrees.to_string();
    let mut args: Vec<&str> = vec!["rotate", "--input", &input, "--output", &out_path];

    // Clone rotations to extend lifetime
    let rotation_refs: Vec<String> = rotations.unwrap_or_default();
    if !rotation_refs.is_empty() {
        args.push("--rotation");
        for r in &rotation_refs {
            args.push(r);
        }
    } else {
        args.push("--degrees");
        args.push(&degrees_str);
    }

    bridge
        .run_script("pdf_pages.py", &args)
        .map_err(|e| e.to_string())?;

    Ok(out_path)
}

#[tauri::command]
fn images_to_pdf(
    app: AppHandle,
    images: Vec<String>,
    output: Option<String>,
    page_size: Option<String>,
    orientation: Option<String>,
    margin: Option<f64>,
    transforms: Option<Vec<ImageTransform>>,
) -> Result<String, String> {
    if images.is_empty() {
        return Err("Provide at least one image path.".into());
    }

    let output_path = output.unwrap_or_else(|| {
        let cache_dir = app
            .path()
            .app_cache_dir()
            .unwrap_or_else(|_| std::env::temp_dir());
        cache_dir.join("tlacuilo-images.pdf").to_string_lossy().to_string()
    });

    let bridge = PythonBridge::new(&app).map_err(|e| e.to_string())?;

    let mut args: Vec<String> = vec![
        "images-to-pdf".to_string(),
        "--output".to_string(),
        output_path.clone(),
        "--inputs".to_string(),
    ];
    args.extend(images);

    if let Some(size) = page_size {
        args.push("--page-size".to_string());
        args.push(size);
    }
    if let Some(orient) = orientation {
        args.push("--orientation".to_string());
        args.push(orient);
    }
    if let Some(m) = margin {
        args.push("--margin".to_string());
        args.push(m.to_string());
    }

    // Pass transforms as JSON string if provided
    if let Some(ref t) = transforms {
        let transforms_json = serde_json::to_string(t)
            .map_err(|e| format!("Failed to serialize transforms: {e}"))?;
        args.push("--transforms".to_string());
        args.push(transforms_json);
    }

    let args_refs: Vec<&str> = args.iter().map(|s| s.as_str()).collect();
    bridge
        .run_script("pdf_convert.py", &args_refs)
        .map_err(|e| e.to_string())?;

    Ok(output_path)
}

#[tauri::command]
fn pdf_to_images(
    app: AppHandle,
    input: String,
    output_dir: Option<String>,
    format: Option<String>,
    dpi: Option<i32>,
    pages: Option<String>,
) -> Result<Vec<String>, String> {
    let out_dir = output_dir.unwrap_or_else(|| {
        let cache_dir = app
            .path()
            .app_cache_dir()
            .unwrap_or_else(|_| std::env::temp_dir());
        cache_dir
            .join("tlacuilo-images")
            .to_string_lossy()
            .to_string()
    });

    let bridge = PythonBridge::new(&app).map_err(|e| e.to_string())?;

    let mut args: Vec<String> = vec![
        "pdf-to-images".to_string(),
        "--input".to_string(),
        input,
        "--output-dir".to_string(),
        out_dir.clone(),
    ];

    if let Some(fmt) = format {
        args.push("--format".to_string());
        args.push(fmt);
    }
    if let Some(d) = dpi {
        args.push("--dpi".to_string());
        args.push(d.to_string());
    }
    if let Some(p) = pages {
        args.push("--pages".to_string());
        args.push(p);
    }

    let args_refs: Vec<&str> = args.iter().map(|s| s.as_str()).collect();
    let output = bridge
        .run_script("pdf_convert.py", &args_refs)
        .map_err(|e| e.to_string())?;

    // Parse output to get list of created files
    let files: Vec<String> = output
        .stdout
        .lines()
        .filter(|l| {
            l.trim().starts_with(&out_dir)
                || l.trim().ends_with(".png")
                || l.trim().ends_with(".jpg")
                || l.trim().ends_with(".webp")
                || l.trim().ends_with(".tiff")
        })
        .map(|l| l.trim().to_string())
        .collect();

    if files.is_empty() {
        // Return the output directory at minimum
        Ok(vec![out_dir])
    } else {
        Ok(files)
    }
}

// ============================================================================
// PDF Attachments Commands (PythonBridge)
// ============================================================================

#[derive(Debug, Serialize)]
struct AttachmentInfo {
    index: u32,
    name: String,
    filename: String,
    size: u64,
    length: u64,
    created: String,
    modified: String,
    description: String,
}

/// List all embedded files in a PDF
#[tauri::command]
fn attachments_list(app: AppHandle, input: String) -> Result<Vec<AttachmentInfo>, String> {
    let bridge = PythonBridge::new(&app).map_err(|e| e.to_string())?;

    let args: Vec<&str> = vec!["list", "--input", &input];

    let result = bridge
        .run_script("pdf_attachments.py", &args)
        .map_err(|e| e.to_string())?;

    let attachments: Vec<serde_json::Value> = serde_json::from_str(&result.stdout)
        .map_err(|e| format!("Failed to parse result: {}", e))?;

    Ok(attachments
        .iter()
        .map(|a| AttachmentInfo {
            index: a["index"].as_u64().unwrap_or(0) as u32,
            name: a["name"].as_str().unwrap_or("").to_string(),
            filename: a["filename"].as_str().unwrap_or("").to_string(),
            size: a["size"].as_u64().unwrap_or(0),
            length: a["length"].as_u64().unwrap_or(0),
            created: a["created"].as_str().unwrap_or("").to_string(),
            modified: a["modified"].as_str().unwrap_or("").to_string(),
            description: a["description"].as_str().unwrap_or("").to_string(),
        })
        .collect())
}

#[derive(Debug, Serialize)]
struct AttachmentExtractResult {
    success: bool,
    path: String,
    name: String,
    size: u64,
}

/// Extract a single embedded file
#[tauri::command]
fn attachments_extract(
    app: AppHandle,
    input: String,
    name: String,
    output: Option<String>,
) -> Result<AttachmentExtractResult, String> {
    let output_path = output.unwrap_or_else(|| {
        let cache_dir = app
            .path()
            .app_cache_dir()
            .unwrap_or_else(|_| std::env::temp_dir());
        cache_dir
            .join("attachments")
            .join(&name)
            .to_string_lossy()
            .to_string()
    });

    let bridge = PythonBridge::new(&app).map_err(|e| e.to_string())?;

    let args: Vec<&str> = vec!["extract", "--input", &input, "--name", &name, "--output", &output_path];

    let result = bridge
        .run_script("pdf_attachments.py", &args)
        .map_err(|e| e.to_string())?;

    let parsed: serde_json::Value = serde_json::from_str(&result.stdout)
        .map_err(|e| format!("Failed to parse result: {}", e))?;

    Ok(AttachmentExtractResult {
        success: parsed["success"].as_bool().unwrap_or(false),
        path: parsed["path"].as_str().unwrap_or("").to_string(),
        name: parsed["name"].as_str().unwrap_or("").to_string(),
        size: parsed["size"].as_u64().unwrap_or(0),
    })
}

/// Extract all embedded files to a directory
#[tauri::command]
fn attachments_extract_all(
    app: AppHandle,
    input: String,
    output_dir: Option<String>,
) -> Result<Vec<AttachmentExtractResult>, String> {
    let out_dir = output_dir.unwrap_or_else(|| {
        let cache_dir = app
            .path()
            .app_cache_dir()
            .unwrap_or_else(|_| std::env::temp_dir());
        cache_dir
            .join("attachments")
            .to_string_lossy()
            .to_string()
    });

    let bridge = PythonBridge::new(&app).map_err(|e| e.to_string())?;

    let args: Vec<&str> = vec!["extract-all", "--input", &input, "--output-dir", &out_dir];

    let result = bridge
        .run_script("pdf_attachments.py", &args)
        .map_err(|e| e.to_string())?;

    let parsed: Vec<serde_json::Value> = serde_json::from_str(&result.stdout)
        .map_err(|e| format!("Failed to parse result: {}", e))?;

    Ok(parsed
        .iter()
        .map(|a| AttachmentExtractResult {
            success: a["success"].as_bool().unwrap_or(false),
            path: a["path"].as_str().unwrap_or("").to_string(),
            name: a["name"].as_str().unwrap_or("").to_string(),
            size: a["size"].as_u64().unwrap_or(0),
        })
        .collect())
}

// ============================================================================
// Form Fields (AcroForms)
// ============================================================================

#[derive(Debug, Clone, serde::Serialize)]
struct FormField {
    name: String,
    field_type: String,
    type_id: u32,
    value: serde_json::Value,
    page: u32,
    rect: Vec<f64>,
    read_only: bool,
    choices: Option<Vec<String>>,
    checked: Option<bool>,
    on_state: Option<serde_json::Value>,
    max_length: Option<u32>,
    multiline: Option<bool>,
}

#[derive(Debug, Clone, serde::Serialize)]
struct FormFieldsResult {
    is_form: bool,
    fields: Vec<FormField>,
    field_count: u32,
}

#[derive(Debug, Clone, serde::Serialize)]
struct FormFillResult {
    success: bool,
    filled_count: u32,
    errors: Option<Vec<String>>,
    output_path: String,
}

/// List all form fields in a PDF
#[tauri::command]
fn form_fields_list(app: AppHandle, input: String) -> Result<FormFieldsResult, String> {
    let bridge = PythonBridge::new(&app).map_err(|e| e.to_string())?;

    let args: Vec<&str> = vec!["list", &input];

    let result = bridge
        .run_script("pdf_forms.py", &args)
        .map_err(|e| e.to_string())?;

    let parsed: serde_json::Value = serde_json::from_str(&result.stdout)
        .map_err(|e| format!("Failed to parse result: {}", e))?;

    if let Some(error) = parsed.get("error") {
        return Err(error.as_str().unwrap_or("Unknown error").to_string());
    }

    let is_form = parsed["is_form"].as_bool().unwrap_or(false);
    let field_count = parsed["field_count"].as_u64().unwrap_or(0) as u32;

    let fields: Vec<FormField> = parsed["fields"]
        .as_array()
        .unwrap_or(&vec![])
        .iter()
        .map(|f| FormField {
            name: f["name"].as_str().unwrap_or("").to_string(),
            field_type: f["type"].as_str().unwrap_or("unknown").to_string(),
            type_id: f["type_id"].as_u64().unwrap_or(0) as u32,
            value: f["value"].clone(),
            page: f["page"].as_u64().unwrap_or(0) as u32,
            rect: f["rect"]
                .as_array()
                .map(|arr| arr.iter().filter_map(|v| v.as_f64()).collect())
                .unwrap_or_default(),
            read_only: f["read_only"].as_bool().unwrap_or(false),
            choices: f["choices"].as_array().map(|arr| {
                arr.iter()
                    .filter_map(|v| v.as_str().map(|s| s.to_string()))
                    .collect()
            }),
            checked: f["checked"].as_bool(),
            on_state: f.get("on_state").cloned(),
            max_length: f["max_length"].as_u64().map(|v| v as u32),
            multiline: f["multiline"].as_bool(),
        })
        .collect();

    Ok(FormFieldsResult {
        is_form,
        fields,
        field_count,
    })
}

/// Fill form fields and save to output path
#[tauri::command]
fn form_fields_fill(
    app: AppHandle,
    input: String,
    output: String,
    field_values: std::collections::HashMap<String, serde_json::Value>,
) -> Result<FormFillResult, String> {
    let bridge = PythonBridge::new(&app).map_err(|e| e.to_string())?;

    let values_json = serde_json::to_string(&field_values)
        .map_err(|e| format!("Failed to serialize field values: {}", e))?;

    let args: Vec<&str> = vec!["fill", &input, &output, &values_json];

    let result = bridge
        .run_script("pdf_forms.py", &args)
        .map_err(|e| e.to_string())?;

    let parsed: serde_json::Value = serde_json::from_str(&result.stdout)
        .map_err(|e| format!("Failed to parse result: {}", e))?;

    if let Some(error) = parsed.get("error") {
        return Err(error.as_str().unwrap_or("Unknown error").to_string());
    }

    Ok(FormFillResult {
        success: parsed["success"].as_bool().unwrap_or(false),
        filled_count: parsed["filled_count"].as_u64().unwrap_or(0) as u32,
        errors: parsed["errors"].as_array().map(|arr| {
            arr.iter()
                .filter_map(|v| v.as_str().map(|s| s.to_string()))
                .collect()
        }),
        output_path: parsed["output_path"].as_str().unwrap_or("").to_string(),
    })
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  // On Linux/Wayland (especially KDE), prefer XDG Desktop Portal file dialogs.
  //
  // Notes:
  // - Some GTK-native file chooser paths have been observed to hard-crash (SIGSEGV) when other
  //   statically linked C libraries interpose common symbols (e.g. from vendored deps).
  // - Portals generally provide a better KDE/GNOME native experience on Wayland.
  //
  // Overrides:
  // - If `GTK_USE_PORTAL` is already set, we respect it.
  // - Otherwise we set it from `TLACUILO_GTK_USE_PORTAL` (default: "1").
  #[cfg(target_os = "linux")]
  {
    if std::env::var_os("GTK_USE_PORTAL").is_none() {
      let desired = std::env::var("TLACUILO_GTK_USE_PORTAL").unwrap_or_else(|_| "1".to_string());
      let normalized = desired.trim().to_ascii_lowercase();
      let value = match normalized.as_str() {
        "0" | "false" | "no" | "off" => "0",
        "1" | "true" | "yes" | "on" => "1",
        _ => "1",
      };
      std::env::set_var("GTK_USE_PORTAL", value);
    }
  }

  tauri::Builder::default()
    .plugin(tauri_plugin_fs::init())
    .plugin(tauri_plugin_dialog::init())
    .plugin(tauri_plugin_store::Builder::new().build())
    .menu(|app| {
      let file = SubmenuBuilder::new(app, "File")
        .item(
          &MenuItemBuilder::new("Open")
            .id("open")
            .accelerator("CmdOrCtrl+O")
            .build(app)?,
        )
        .separator()
        .item(
          &MenuItemBuilder::new("Save")
            .id("save")
            .accelerator("CmdOrCtrl+S")
            .build(app)?,
        )
        .item(
          &MenuItemBuilder::new("Save As...")
            .id("save-as")
            .accelerator("CmdOrCtrl+Shift+S")
            .build(app)?,
        )
        .item(
          &MenuItemBuilder::new("Reload from PDF")
            .id("reload-annotations")
            .build(app)?,
        )
        .separator()
        .item(
          &MenuItemBuilder::new("Export XFDF...")
            .id("export-xfdf")
            .build(app)?,
        )
        .item(
          &MenuItemBuilder::new("Import XFDF...")
            .id("import-xfdf")
            .build(app)?,
        )
        .separator()
        .item(
          &MenuItemBuilder::new("Print...")
            .id("print")
            .accelerator("CmdOrCtrl+P")
            .build(app)?,
        )
        .separator()
        .item(
          &MenuItemBuilder::new("Quit")
            .id("quit")
            .accelerator("CmdOrCtrl+Q")
            .build(app)?,
        )
        .build()?;

      let edit = SubmenuBuilder::new(app, "Edit")
        .separator()
        .item(&MenuItemBuilder::new("Undo").id("undo").build(app)?)
        .item(&MenuItemBuilder::new("Redo").id("redo").build(app)?)
        .separator()
        .item(&MenuItemBuilder::new("Cut").id("cut").build(app)?)
        .item(&MenuItemBuilder::new("Copy").id("copy").build(app)?)
        .item(&MenuItemBuilder::new("Paste").id("paste").build(app)?)
        .build()?;

      let help = SubmenuBuilder::new(app, "Help")
        .item(&MenuItemBuilder::new("About Tlacuilo").id("about").build(app)?)
        .build()?;

      MenuBuilder::new(app).items(&[&file, &edit, &help]).build()
    })
    .on_menu_event(|app, event| {
      match event.id().as_ref() {
        "open" => {
          // Emit event to frontend to handle file open
          if let Some(window) = app.get_webview_window("main") {
            let _ = window.emit("menu-open", ());
          }
        }
        "save" => {
          // Emit event to frontend to save annotations
          if let Some(window) = app.get_webview_window("main") {
            let _ = window.emit("menu-save", ());
          }
        }
        "save-as" => {
          if let Some(window) = app.get_webview_window("main") {
            let _ = window.emit("menu-save-as", ());
          }
        }
        "reload-annotations" => {
          if let Some(window) = app.get_webview_window("main") {
            let _ = window.emit("menu-reload-annotations", ());
          }
        }
        "export-xfdf" => {
          if let Some(window) = app.get_webview_window("main") {
            let _ = window.emit("menu-export-xfdf", ());
          }
        }
        "import-xfdf" => {
          if let Some(window) = app.get_webview_window("main") {
            let _ = window.emit("menu-import-xfdf", ());
          }
        }
        "print" => {
          if let Some(window) = app.get_webview_window("main") {
            let _ = window.emit("menu-print", ());
          }
        }
        "quit" => app.exit(0),
        _ => {}
      }
    })
    .setup(|app| {
      if cfg!(debug_assertions) {
        app.handle().plugin(
          tauri_plugin_log::Builder::default()
            .level(log::LevelFilter::Info)
            .build(),
        )?;
      }
      Ok(())
    })
    .invoke_handler(tauri::generate_handler![
      // Python bridge
      python_check,
      python_check_packages,
      python_install_package,
      // PDF compression (MuPDF)
      compress_pdf,
      estimate_compression,
      // OCR (Python/OCRmyPDF)
      ocr_check_dependencies,
      ocr_analyze_pdf,
      ocr_run,
      // PDF operations (PythonBridge)
      merge_pdfs,
      merge_pages,
      split_pdf,
      rotate_pdf,
      images_to_pdf,
      pdf_to_images,
      // PDF viewer
      pdf_viewer::pdf_open,
      pdf_viewer::pdf_render_page,
      pdf_viewer::pdf_render_thumbnail,
      pdf_viewer::pdf_render_thumbnails,
      pdf_viewer::pdf_close,
      pdf_viewer::pdf_get_text_blocks,
      pdf_viewer::pdf_get_outlines,
      pdf_viewer::pdf_get_metadata,
      // Annotations (JSON file-based)
      annotations::annotations_save,
      annotations::annotations_load,
      annotations::annotations_delete,
      // Annotations (PDF embedded)
      annotations_embed_in_pdf,
      annotations_read_from_pdf,
      annotations_export_xfdf,
      annotations_import_xfdf,
      // Print commands
      print_prepare_pdf,
      print_pdf,
      // Attachments
      attachments_list,
      attachments_extract,
      attachments_extract_all,
      form_fields_list,
      form_fields_fill
    ])
    .run(tauri::generate_context!())
    .expect("error while running tauri application");
}
