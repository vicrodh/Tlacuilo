use std::path::{Path, PathBuf};
use std::process::Command;

use tauri::menu::{MenuBuilder, MenuItemBuilder, SubmenuBuilder};
use tauri::{AppHandle, Manager};
use tauri_plugin_dialog::DialogExt;

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
    cache_dir.join("ihpdf-merge.pdf").to_string_lossy().to_string()
  });

  let python_bin = std::env::var("PYTHON_BIN").unwrap_or_else(|_| "python3.12".to_string());
  let (script_path, tried) =
    resolve_backend_script(&app).ok_or_else(|| format!("Backend script not found. Tried: {tried:?}"))?;

  let output = Command::new(&python_bin)
    .arg(&script_path)
    .arg("merge")
    .arg("--output")
    .arg(&output_path)
    .arg("--inputs")
    .args(inputs.clone())
    .output()
    .map_err(|e| format!("Failed to spawn python ({python_bin}): {e}"))?;

  if !output.status.success() {
    let stderr = String::from_utf8_lossy(&output.stderr);
    let stdout = String::from_utf8_lossy(&output.stdout);
    return Err(format!(
      "Python merge failed (code {:?}). stdout: {} stderr: {}",
      output.status.code(),
      stdout,
      stderr
    ));
  }

  Ok(output_path)
}

/// Locate backend/pdf_pages.py in dev and bundled modes.
fn resolve_backend_script(app: &AppHandle) -> Option<(PathBuf, Vec<PathBuf>)> {
  let mut tried: Vec<PathBuf> = Vec::new();

  if let Ok(p) = std::env::var("APP_BACKEND_SCRIPT") {
    let candidate = PathBuf::from(&p);
    tried.push(candidate.clone());
    if candidate.exists() {
      return Some((candidate, tried));
    }
  }

  // Try relative to executable: /ihpdf/src-tauri/target/debug/ihpdf -> pop 4 -> /ihpdf/backend/pdf_pages.py
  if let Ok(mut exe) = std::env::current_exe() {
    for _ in 0..4 {
      exe.pop();
    }
    let candidate = exe.join("backend/pdf_pages.py");
    tried.push(candidate.clone());
    if candidate.exists() {
      return Some((candidate, tried));
    }
  }

  // Try using app path resolve (resource or current dir).
  if let Ok(candidate) = app
    .path()
    .resolve("backend/pdf_pages.py", tauri::path::BaseDirectory::Resource)
  {
    tried.push(candidate.clone());
    if candidate.exists() {
      return Some((candidate, tried));
    }
  }

  let cwd_candidate = PathBuf::from("backend/pdf_pages.py");
  tried.push(cwd_candidate.clone());
  if cwd_candidate.exists() {
    return Some((cwd_candidate, tried));
  }

  None
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  tauri::Builder::default()
    .plugin(tauri_plugin_dialog::init())
    .menu(|app| {
      let file = SubmenuBuilder::new(app, "File")
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
        .item(&MenuItemBuilder::new("About I H PDF").id("about").build(app)?)
        .build()?;

      MenuBuilder::new(app).items(&[&file, &edit, &help]).build()
    })
    .on_menu_event(|app, event| {
      match event.id().as_ref() {
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
    .invoke_handler(tauri::generate_handler![merge_pdfs])
    .run(tauri::generate_context!())
    .expect("error while running tauri application");
}
