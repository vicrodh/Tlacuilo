use std::path::PathBuf;
use std::process::Command;

use serde::{Deserialize, Serialize};

mod pdf_viewer;
use tauri::menu::{MenuBuilder, MenuItemBuilder, SubmenuBuilder};
use tauri::{AppHandle, Emitter, Manager};

#[derive(Debug, Deserialize, Serialize)]
struct ImageTransform {
  rotation: Option<i32>,
  flip_h: Option<bool>,
  flip_v: Option<bool>,
}

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

  let python_bin = resolve_python_bin();
  let resolved = resolve_backend_script(&app)
    .ok_or_else(|| "Backend script not found (backend/pdf_pages.py)".to_string())?;
  let (script_path, _tried) = resolved;

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

    let python_bin = resolve_python_bin();
    let (script_path, _) = resolve_backend_script(&app)
        .ok_or_else(|| "Backend script not found (backend/pdf_pages.py)".to_string())?;

    // Convert pages to format: file:page file:page ...
    let page_args: Vec<String> = pages
        .iter()
        .map(|(file, page)| format!("{}:{}", file, page))
        .collect();

    let output = Command::new(&python_bin)
        .arg(&script_path)
        .arg("merge-pages")
        .arg("--output")
        .arg(&output_path)
        .arg("--pages")
        .args(&page_args)
        .output()
        .map_err(|e| format!("Failed to spawn python ({python_bin}): {e}"))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        let stdout = String::from_utf8_lossy(&output.stdout);
        return Err(format!(
            "Python merge-pages failed (code {:?}). stdout: {} stderr: {}",
            output.status.code(),
            stdout,
            stderr
        ));
    }

    Ok(output_path)
}

#[tauri::command]
fn split_pdf(
  app: AppHandle,
  input: String,
  output_dir: Option<String>,
  ranges: Option<Vec<String>>,
) -> Result<Vec<String>, String> {
  let (script_path, _) = resolve_backend_script(&app)
    .ok_or_else(|| "Backend script not found (backend/pdf_pages.py)".to_string())?;
  let python_bin = resolve_python_bin();

  let out_dir = output_dir.unwrap_or_else(|| {
    let cache_dir = app
      .path()
      .app_cache_dir()
      .unwrap_or_else(|_| std::env::temp_dir());
    cache_dir.join("tlacuilo-split").to_string_lossy().to_string()
  });

  let mut cmd = Command::new(&python_bin);
  cmd
    .arg(&script_path)
    .arg("split")
    .arg("--input")
    .arg(&input)
    .arg("--output-dir")
    .arg(&out_dir);

  // Add ranges if provided
  if let Some(ref range_list) = ranges {
    if !range_list.is_empty() {
      cmd.arg("--ranges");
      cmd.args(range_list);
    }
  }

  let output = cmd
    .output()
    .map_err(|e| format!("Failed to spawn python ({python_bin}): {e}"))?;

  if !output.status.success() {
    let stderr = String::from_utf8_lossy(&output.stderr);
    let stdout = String::from_utf8_lossy(&output.stdout);
    return Err(format!(
      "Python split failed (code {:?}). stdout: {} stderr: {}",
      output.status.code(),
      stdout,
      stderr
    ));
  }

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
  let (script_path, _) = resolve_backend_script(&app)
    .ok_or_else(|| "Backend script not found (backend/pdf_pages.py)".to_string())?;
  let python_bin = resolve_python_bin();
  let out_path = output.unwrap_or_else(|| {
    let cache_dir = app
      .path()
      .app_cache_dir()
      .unwrap_or_else(|_| std::env::temp_dir());
    cache_dir.join("tlacuilo-rotated.pdf").to_string_lossy().to_string()
  });

  let mut cmd = Command::new(&python_bin);
  cmd
    .arg(&script_path)
    .arg("rotate")
    .arg("--input")
    .arg(&input)
    .arg("--output")
    .arg(&out_path);

  if let Some(rotation_list) = rotations {
    if !rotation_list.is_empty() {
      cmd.arg("--rotation");
      cmd.args(rotation_list);
    } else {
      cmd.arg("--degrees").arg(degrees.to_string());
    }
  } else {
    cmd.arg("--degrees").arg(degrees.to_string());
  }

  let output = cmd
    .output()
    .map_err(|e| format!("Failed to spawn python ({python_bin}): {e}"))?;

  if !output.status.success() {
    let stderr = String::from_utf8_lossy(&output.stderr);
    let stdout = String::from_utf8_lossy(&output.stdout);
    return Err(format!(
      "Python rotate failed (code {:?}). stdout: {} stderr: {}",
      output.status.code(),
      stdout,
      stderr
    ));
  }

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

  let python_bin = resolve_python_bin();
  let (script_path, _) = resolve_backend_script_by_name(&app, "pdf_convert.py")
    .ok_or_else(|| "Backend script not found (backend/pdf_convert.py)".to_string())?;

  let mut cmd = Command::new(&python_bin);
  cmd
    .arg(&script_path)
    .arg("images-to-pdf")
    .arg("--output")
    .arg(&output_path)
    .arg("--inputs")
    .args(&images);

  if let Some(size) = page_size {
    cmd.arg("--page-size").arg(size);
  }
  if let Some(orient) = orientation {
    cmd.arg("--orientation").arg(orient);
  }
  if let Some(m) = margin {
    cmd.arg("--margin").arg(m.to_string());
  }

  // Pass transforms as JSON string if provided
  if let Some(ref t) = transforms {
    let transforms_json = serde_json::to_string(t)
      .map_err(|e| format!("Failed to serialize transforms: {e}"))?;
    cmd.arg("--transforms").arg(transforms_json);
  }

  let output = cmd
    .output()
    .map_err(|e| format!("Failed to spawn python ({python_bin}): {e}"))?;

  if !output.status.success() {
    let stderr = String::from_utf8_lossy(&output.stderr);
    let stdout = String::from_utf8_lossy(&output.stdout);
    return Err(format!(
      "Python images-to-pdf failed (code {:?}). stdout: {} stderr: {}",
      output.status.code(),
      stdout,
      stderr
    ));
  }

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
    cache_dir.join("tlacuilo-images").to_string_lossy().to_string()
  });

  let python_bin = resolve_python_bin();
  let (script_path, _) = resolve_backend_script_by_name(&app, "pdf_convert.py")
    .ok_or_else(|| "Backend script not found (backend/pdf_convert.py)".to_string())?;

  let mut cmd = Command::new(&python_bin);
  cmd
    .arg(&script_path)
    .arg("pdf-to-images")
    .arg("--input")
    .arg(&input)
    .arg("--output-dir")
    .arg(&out_dir);

  if let Some(fmt) = format {
    cmd.arg("--format").arg(fmt);
  }
  if let Some(d) = dpi {
    cmd.arg("--dpi").arg(d.to_string());
  }
  if let Some(p) = pages {
    cmd.arg("--pages").arg(p);
  }

  let output = cmd
    .output()
    .map_err(|e| format!("Failed to spawn python ({python_bin}): {e}"))?;

  if !output.status.success() {
    let stderr = String::from_utf8_lossy(&output.stderr);
    let stdout = String::from_utf8_lossy(&output.stdout);
    return Err(format!(
      "Python pdf-to-images failed (code {:?}). stdout: {} stderr: {}",
      output.status.code(),
      stdout,
      stderr
    ));
  }

  // Parse output to get list of created files
  let stdout = String::from_utf8_lossy(&output.stdout);
  let files: Vec<String> = stdout
    .lines()
    .filter(|l| l.trim().starts_with(&out_dir) || l.trim().ends_with(".png") || l.trim().ends_with(".jpg"))
    .map(|l| l.trim().to_string())
    .collect();

  if files.is_empty() {
    // Return the output directory at minimum
    Ok(vec![out_dir])
  } else {
    Ok(files)
  }
}

/// Locate a backend script in dev and bundled modes.
fn resolve_backend_script(app: &AppHandle) -> Option<(PathBuf, Vec<PathBuf>)> {
  resolve_backend_script_by_name(app, "pdf_pages.py")
}

/// Locate a specific backend script by name.
fn resolve_backend_script_by_name(app: &AppHandle, script_name: &str) -> Option<(PathBuf, Vec<PathBuf>)> {
  let mut tried: Vec<PathBuf> = Vec::new();
  let script_path = format!("backend/{}", script_name);

  if let Ok(p) = std::env::var("APP_BACKEND_SCRIPT") {
    let candidate = PathBuf::from(&p);
    tried.push(candidate.clone());
    if candidate.exists() {
      return Some((candidate, tried));
    }
  }

  // Try relative to executable: /tlacuilo/src-tauri/target/debug/tlacuilo -> pop 4 -> /tlacuilo/backend/
  if let Ok(mut exe) = std::env::current_exe() {
    for _ in 0..4 {
      exe.pop();
    }
    let candidate = exe.join(&script_path);
    tried.push(candidate.clone());
    if candidate.exists() {
      return Some((candidate, tried));
    }
  }

  // Try using app path resolve (resource or current dir).
  if let Ok(candidate) = app
    .path()
    .resolve(&script_path, tauri::path::BaseDirectory::Resource)
  {
    tried.push(candidate.clone());
    if candidate.exists() {
      return Some((candidate, tried));
    }
  }

  let cwd_candidate = PathBuf::from(&script_path);
  tried.push(cwd_candidate.clone());
  if cwd_candidate.exists() {
    return Some((cwd_candidate, tried));
  }

  None
}

/// Determine which Python interpreter to use.
/// Priority:
/// 1) APP_PYTHON_BIN env var
/// 2) backend/venv/bin/python3 relative to workspace root (common dev setup)
/// 3) python3.12
/// 4) python3
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
  "python3.12".to_string()
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
      merge_pdfs,
      merge_pages,
      split_pdf,
      rotate_pdf,
      images_to_pdf,
      pdf_to_images,
      pdf_viewer::pdf_open,
      pdf_viewer::pdf_render_page,
      pdf_viewer::pdf_render_thumbnail,
      pdf_viewer::pdf_render_thumbnails,
      pdf_viewer::pdf_close
    ])
    .run(tauri::generate_context!())
    .expect("error while running tauri application");
}
