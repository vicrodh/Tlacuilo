use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;

#[derive(Debug, Serialize, Deserialize)]
pub struct Rect {
    pub x: f64,
    pub y: f64,
    pub width: f64,
    pub height: f64,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct Annotation {
    pub id: String,
    #[serde(rename = "type")]
    pub annotation_type: String,
    pub page: u32,
    pub rect: Rect,
    pub color: String,
    pub opacity: f64,
    pub text: Option<String>,
    #[serde(rename = "createdAt")]
    pub created_at: String,
    #[serde(rename = "modifiedAt")]
    pub modified_at: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct AnnotationsFile {
    pub version: u32,
    pub pdf_path: String,
    pub annotations: std::collections::HashMap<u32, Vec<Annotation>>,
}

fn get_annotations_path(pdf_path: &str) -> PathBuf {
    let mut path = PathBuf::from(pdf_path);
    let file_name = path.file_name().unwrap().to_string_lossy().to_string();
    path.set_file_name(format!(".{}.annotations.json", file_name));
    path
}

#[tauri::command]
pub fn annotations_save(pdf_path: String, annotations_json: String) -> Result<String, String> {
    let annotations_path = get_annotations_path(&pdf_path);

    // Parse and re-serialize to validate JSON
    let annotations: std::collections::HashMap<u32, Vec<Annotation>> =
        serde_json::from_str(&annotations_json)
            .map_err(|e| format!("Invalid annotations JSON: {}", e))?;

    let file = AnnotationsFile {
        version: 1,
        pdf_path: pdf_path.clone(),
        annotations,
    };

    let json = serde_json::to_string_pretty(&file)
        .map_err(|e| format!("Failed to serialize annotations: {}", e))?;

    fs::write(&annotations_path, json)
        .map_err(|e| format!("Failed to write annotations file: {}", e))?;

    Ok(annotations_path.to_string_lossy().to_string())
}

#[tauri::command]
pub fn annotations_load(pdf_path: String) -> Result<Option<String>, String> {
    let annotations_path = get_annotations_path(&pdf_path);

    if !annotations_path.exists() {
        return Ok(None);
    }

    let content = fs::read_to_string(&annotations_path)
        .map_err(|e| format!("Failed to read annotations file: {}", e))?;

    let file: AnnotationsFile = serde_json::from_str(&content)
        .map_err(|e| format!("Failed to parse annotations file: {}", e))?;

    let annotations_json = serde_json::to_string(&file.annotations)
        .map_err(|e| format!("Failed to serialize annotations: {}", e))?;

    Ok(Some(annotations_json))
}

#[tauri::command]
pub fn annotations_delete(pdf_path: String) -> Result<(), String> {
    let annotations_path = get_annotations_path(&pdf_path);

    if annotations_path.exists() {
        fs::remove_file(&annotations_path)
            .map_err(|e| format!("Failed to delete annotations file: {}", e))?;
    }

    Ok(())
}
