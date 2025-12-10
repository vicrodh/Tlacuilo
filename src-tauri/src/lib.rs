use std::path::PathBuf;
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
  let script_path = resolve_backend_script();
  if !script_path.exists() {
    return Err(format!("Backend script not found at {}", script_path.display()));
  }

  let status = Command::new(python_bin)
    .arg(script_path)
    .arg("merge")
    .arg("--output")
    .arg(&output_path)
    .args(["--inputs"])
    .args(inputs.clone())
    .status()
    .map_err(|e| format!("Failed to spawn python: {e}"))?;

  if !status.success() {
    return Err(format!("Python merge exited with code {:?}", status.code()));
  }

  Ok(output_path)
}

/// Locate backend/pdf_pages.py in dev and bundled modes.
fn resolve_backend_script() -> PathBuf {
  if let Ok(p) = std::env::var("APP_BACKEND_SCRIPT") {
    let candidate = PathBuf::from(&p);
    if candidate.exists() {
      return candidate;
    }
  }

  // Try relative to the running binary: target/debug/ihpdf -> ../../backend/pdf_pages.py
  if let Ok(mut exe_path) = std::env::current_exe() {
    for _ in 0..3 {
      exe_path.pop();
    }
    let candidate = exe_path.join("backend/pdf_pages.py");
    if candidate.exists() {
      return candidate;
    }
  }

  // Fallback: project root relative path
  PathBuf::from("backend/pdf_pages.py")
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
