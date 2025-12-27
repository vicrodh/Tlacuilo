//! Font detection module via Python bridge.

use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use std::process::Command;
use tauri::{AppHandle, Manager};

#[derive(Debug, Serialize, Deserialize)]
pub struct EngineAvailability {
    pub available: bool,
    pub reason: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct FontDetectEngines {
    pub baseline_render_compare: EngineAvailability,
    pub ml_embeddings: EngineAvailability,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct CatalogStatus {
    pub available: bool,
    pub source: Option<String>,
    pub path: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct FontDetectCheckResult {
    pub ok: bool,
    pub cache_dir: String,
    pub engines: FontDetectEngines,
    pub catalog: CatalogStatus,
    pub indexed_fonts: i32,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct FontDetectIndexResult {
    pub ok: bool,
    pub cache_dir: String,
    pub indexed_fonts: i32,
    pub duration_ms: i32,
    pub ml_indexed: bool,
    pub cached: Option<bool>,
    pub ml_reason: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ScoreBreakdown {
    pub ssim: f32,
    pub histogram: f32,
    pub template: f32,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct FontCandidate {
    pub family: String,
    pub style: String,
    pub category: Option<String>,
    pub weight: Option<i32>,
    pub italic: Option<bool>,
    pub path: String,
    pub score: f32,
    pub score_breakdown: Option<ScoreBreakdown>,
    pub preview_sample: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct FallbackInfo {
    pub used: bool,
    pub reason: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct MatchMeta {
    pub indexed_fonts: i32,
    pub duration_ms: i32,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct FontDetectMatchResult {
    pub ok: bool,
    pub requested_engine: String,
    pub engine_used: String,
    pub fallback: FallbackInfo,
    pub candidates: Vec<FontCandidate>,
    pub meta: MatchMeta,
}

fn resolve_font_detect_script(app: &AppHandle) -> Option<PathBuf> {
    use tauri::Manager;

    if let Ok(mut exe) = std::env::current_exe() {
        for _ in 0..4 {
            exe.pop();
        }
        let script = exe.join("backend/font_detect.py");
        if script.exists() {
            return Some(script);
        }
    }

    if let Ok(resource) = app
        .path()
        .resolve("backend/font_detect.py", tauri::path::BaseDirectory::Resource)
    {
        if resource.exists() {
            return Some(resource);
        }
    }

    let cwd = PathBuf::from("backend/font_detect.py");
    if cwd.exists() {
        return Some(cwd);
    }

    None
}

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

fn resolve_cache_dir(app: &AppHandle) -> PathBuf {
    app.path()
        .app_cache_dir()
        .unwrap_or_else(|_| std::env::temp_dir())
}

pub fn check(app: &AppHandle) -> Result<FontDetectCheckResult, String> {
    let script = resolve_font_detect_script(app)
        .ok_or_else(|| "font_detect script not found (backend/font_detect.py)".to_string())?;

    let python = resolve_python_bin();
    let cache_dir = resolve_cache_dir(app);

    let output = Command::new(&python)
        .arg(&script)
        .arg("check")
        .env("TLACUILO_CACHE_DIR", &cache_dir)
        .output()
        .map_err(|e| format!("Failed to run font detect check: {}", e))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("Font detect check failed: {}", stderr));
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    serde_json::from_str(&stdout)
        .map_err(|e| format!("Failed to parse font detect check result: {}", e))
}

pub fn index(app: &AppHandle, force: bool) -> Result<FontDetectIndexResult, String> {
    let script = resolve_font_detect_script(app)
        .ok_or_else(|| "font_detect script not found (backend/font_detect.py)".to_string())?;

    let python = resolve_python_bin();
    let cache_dir = resolve_cache_dir(app);

    let mut cmd = Command::new(&python);
    cmd.arg(&script).arg("index");
    if force {
        cmd.arg("--force");
    }
    let output = cmd
        .env("TLACUILO_CACHE_DIR", &cache_dir)
        .output()
        .map_err(|e| format!("Failed to run font detect index: {}", e))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("Font detect index failed: {}", stderr));
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    serde_json::from_str(&stdout)
        .map_err(|e| format!("Failed to parse font detect index result: {}", e))
}

pub fn match_image(
    app: &AppHandle,
    input: &str,
    engine: &str,
    topk: i32,
) -> Result<FontDetectMatchResult, String> {
    let script = resolve_font_detect_script(app)
        .ok_or_else(|| "font_detect script not found (backend/font_detect.py)".to_string())?;

    let python = resolve_python_bin();
    let cache_dir = resolve_cache_dir(app);

    let output = Command::new(&python)
        .arg(&script)
        .arg("match")
        .arg("--input")
        .arg(input)
        .arg("--engine")
        .arg(engine)
        .arg("--topk")
        .arg(topk.to_string())
        .env("TLACUILO_CACHE_DIR", &cache_dir)
        .output()
        .map_err(|e| format!("Failed to run font detect match: {}", e))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("Font detect match failed: {}", stderr));
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    serde_json::from_str(&stdout)
        .map_err(|e| format!("Failed to parse font detect match result: {}", e))
}
