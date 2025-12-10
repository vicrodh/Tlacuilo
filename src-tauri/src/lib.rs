use std::path::PathBuf;
use std::process::Command;

use tauri::menu::{Menu, MenuItem, Submenu};
use tauri::{AppHandle, Manager};

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
  let script_path = app
    .path()
    .resolve("backend/pdf_pages.py", tauri::path::BaseDirectory::Resource)
    .unwrap_or_else(|_| PathBuf::from("backend/pdf_pages.py"));

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

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  let menu = Menu::new()
    .add_submenu(Submenu::new(
      "File",
      Menu::new()
        .add_native_item(MenuItem::CloseWindow)
        .add_native_item(MenuItem::Separator)
        .add_native_item(MenuItem::Quit),
    ))
    .add_submenu(Submenu::new(
      "Edit",
      Menu::new()
        .add_native_item(MenuItem::Undo)
        .add_native_item(MenuItem::Redo)
        .add_native_item(MenuItem::Separator)
        .add_native_item(MenuItem::Cut)
        .add_native_item(MenuItem::Copy)
        .add_native_item(MenuItem::Paste),
    ))
    .add_submenu(Submenu::new(
      "Help",
      Menu::new().add_native_item(MenuItem::About {
        name: "I H PDF".into(),
        version: Some("0.1.0".into()),
        authors: Some(vec!["I H PDF".into()]),
        comments: Some("Offline PDF toolkit".into()),
        copyright: None,
        license: Some("MIT".into()),
        website: None,
        website_label: None,
        credits: None,
        icon: None,
      }),
    ));

  tauri::Builder::default()
    .menu(menu)
    .on_menu_event(|event| {
      let id = event.id().as_ref();
      if id == "quit" {
        event.app_handle().exit(0);
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
