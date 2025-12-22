//! Python Bridge Module
//!
//! Provides a centralized, reusable interface for executing Python scripts
//! from Tauri. Handles virtual environment discovery, dependency checking,
//! and structured error handling.

use std::collections::HashMap;
use std::path::PathBuf;
use std::process::{Command, Output, Stdio};

use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Manager};

/// Result type for Python bridge operations
pub type PythonResult<T> = Result<T, PythonError>;

/// Errors that can occur during Python execution
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct PythonError {
    pub kind: PythonErrorKind,
    pub message: String,
    pub stdout: Option<String>,
    pub stderr: Option<String>,
    pub exit_code: Option<i32>,
}

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq)]
pub enum PythonErrorKind {
    /// Python interpreter not found
    PythonNotFound,
    /// Script file not found
    ScriptNotFound,
    /// Failed to spawn process
    SpawnFailed,
    /// Script execution failed (non-zero exit)
    ExecutionFailed,
    /// Missing required dependency
    MissingDependency,
    /// Invalid arguments
    InvalidArgs,
    /// Timeout
    Timeout,
}

impl std::fmt::Display for PythonError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}: {}", self.kind_str(), self.message)
    }
}

impl PythonError {
    fn kind_str(&self) -> &'static str {
        match self.kind {
            PythonErrorKind::PythonNotFound => "PythonNotFound",
            PythonErrorKind::ScriptNotFound => "ScriptNotFound",
            PythonErrorKind::SpawnFailed => "SpawnFailed",
            PythonErrorKind::ExecutionFailed => "ExecutionFailed",
            PythonErrorKind::MissingDependency => "MissingDependency",
            PythonErrorKind::InvalidArgs => "InvalidArgs",
            PythonErrorKind::Timeout => "Timeout",
        }
    }

    pub fn python_not_found(message: impl Into<String>) -> Self {
        Self {
            kind: PythonErrorKind::PythonNotFound,
            message: message.into(),
            stdout: None,
            stderr: None,
            exit_code: None,
        }
    }

    pub fn script_not_found(message: impl Into<String>) -> Self {
        Self {
            kind: PythonErrorKind::ScriptNotFound,
            message: message.into(),
            stdout: None,
            stderr: None,
            exit_code: None,
        }
    }

    pub fn spawn_failed(message: impl Into<String>) -> Self {
        Self {
            kind: PythonErrorKind::SpawnFailed,
            message: message.into(),
            stdout: None,
            stderr: None,
            exit_code: None,
        }
    }

    pub fn execution_failed(
        message: impl Into<String>,
        stdout: Option<String>,
        stderr: Option<String>,
        exit_code: Option<i32>,
    ) -> Self {
        Self {
            kind: PythonErrorKind::ExecutionFailed,
            message: message.into(),
            stdout,
            stderr,
            exit_code,
        }
    }

    pub fn missing_dependency(package: impl Into<String>) -> Self {
        Self {
            kind: PythonErrorKind::MissingDependency,
            message: format!("Missing Python package: {}", package.into()),
            stdout: None,
            stderr: None,
            exit_code: None,
        }
    }
}

// Enable conversion to String for Tauri command compatibility
impl From<PythonError> for String {
    fn from(err: PythonError) -> Self {
        if let Some(stderr) = &err.stderr {
            format!("{}: {} (stderr: {})", err.kind_str(), err.message, stderr)
        } else {
            format!("{}: {}", err.kind_str(), err.message)
        }
    }
}

/// Configuration for Python execution
#[derive(Debug, Clone)]
pub struct PythonConfig {
    /// Path to Python interpreter (or None to auto-detect)
    pub python_bin: Option<PathBuf>,
    /// Path to virtual environment (or None to auto-detect)
    pub venv_path: Option<PathBuf>,
    /// Working directory for script execution
    pub working_dir: Option<PathBuf>,
    /// Environment variables to set
    pub env_vars: HashMap<String, String>,
}

impl Default for PythonConfig {
    fn default() -> Self {
        Self {
            python_bin: None,
            venv_path: None,
            working_dir: None,
            env_vars: HashMap::new(),
        }
    }
}

/// Main Python bridge struct
pub struct PythonBridge {
    config: PythonConfig,
    python_path: PathBuf,
    scripts_dir: PathBuf,
}

impl PythonBridge {
    /// Create a new PythonBridge with auto-detected settings
    pub fn new(app: &AppHandle) -> PythonResult<Self> {
        Self::with_config(app, PythonConfig::default())
    }

    /// Create a new PythonBridge with custom configuration
    pub fn with_config(app: &AppHandle, config: PythonConfig) -> PythonResult<Self> {
        let python_path = config
            .python_bin
            .clone()
            .unwrap_or_else(|| PathBuf::from(resolve_python_bin()));

        let scripts_dir = resolve_scripts_dir(app);

        Ok(Self {
            config,
            python_path,
            scripts_dir,
        })
    }

    /// Get the resolved Python interpreter path
    pub fn python_path(&self) -> &PathBuf {
        &self.python_path
    }

    /// Get the scripts directory
    pub fn scripts_dir(&self) -> &PathBuf {
        &self.scripts_dir
    }

    /// Check if a Python package is installed
    pub fn check_package(&self, package: &str) -> PythonResult<bool> {
        let output = Command::new(&self.python_path)
            .args(["-c", &format!("import {}", package.replace('-', "_"))])
            .output()
            .map_err(|e| PythonError::spawn_failed(format!("Failed to check package: {}", e)))?;

        Ok(output.status.success())
    }

    /// Check multiple packages and return list of missing ones
    pub fn check_packages(&self, packages: &[&str]) -> PythonResult<Vec<String>> {
        let mut missing = Vec::new();
        for &pkg in packages {
            if !self.check_package(pkg)? {
                missing.push(pkg.to_string());
            }
        }
        Ok(missing)
    }

    /// Install a Python package using pip
    pub fn install_package(&self, package: &str) -> PythonResult<()> {
        let output = Command::new(&self.python_path)
            .args(["-m", "pip", "install", "--quiet", package])
            .output()
            .map_err(|e| PythonError::spawn_failed(format!("Failed to install package: {}", e)))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr).to_string();
            return Err(PythonError::execution_failed(
                format!("Failed to install {}", package),
                None,
                Some(stderr),
                output.status.code(),
            ));
        }

        Ok(())
    }

    /// Run a Python script with arguments
    pub fn run_script(&self, script_name: &str, args: &[&str]) -> PythonResult<ScriptOutput> {
        let script_path = self.scripts_dir.join(script_name);

        if !script_path.exists() {
            return Err(PythonError::script_not_found(format!(
                "Script not found: {} (looked in {:?})",
                script_name, self.scripts_dir
            )));
        }

        self.run_script_path(&script_path, args)
    }

    /// Run a Python script from a specific path
    pub fn run_script_path(&self, script_path: &PathBuf, args: &[&str]) -> PythonResult<ScriptOutput> {
        let mut cmd = Command::new(&self.python_path);
        cmd.arg(script_path);
        cmd.args(args);

        // Apply environment variables
        for (key, value) in &self.config.env_vars {
            cmd.env(key, value);
        }

        // Set working directory if specified
        if let Some(ref wd) = self.config.working_dir {
            cmd.current_dir(wd);
        }

        let output = cmd
            .output()
            .map_err(|e| PythonError::spawn_failed(format!("Failed to spawn Python: {}", e)))?;

        self.process_output(output)
    }

    /// Run a Python command (like -m module)
    pub fn run_module(&self, module: &str, args: &[&str]) -> PythonResult<ScriptOutput> {
        let mut cmd = Command::new(&self.python_path);
        cmd.args(["-m", module]);
        cmd.args(args);

        // Apply environment variables
        for (key, value) in &self.config.env_vars {
            cmd.env(key, value);
        }

        // Set working directory if specified
        if let Some(ref wd) = self.config.working_dir {
            cmd.current_dir(wd);
        }

        let output = cmd
            .output()
            .map_err(|e| PythonError::spawn_failed(format!("Failed to spawn Python module: {}", e)))?;

        self.process_output(output)
    }

    /// Run inline Python code
    pub fn run_code(&self, code: &str) -> PythonResult<ScriptOutput> {
        let output = Command::new(&self.python_path)
            .args(["-c", code])
            .output()
            .map_err(|e| PythonError::spawn_failed(format!("Failed to run Python code: {}", e)))?;

        self.process_output(output)
    }

    /// Get Python version
    pub fn python_version(&self) -> PythonResult<String> {
        let output = self.run_code("import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")?;
        Ok(output.stdout.trim().to_string())
    }

    /// Process command output into structured result
    fn process_output(&self, output: Output) -> PythonResult<ScriptOutput> {
        let stdout = String::from_utf8_lossy(&output.stdout).to_string();
        let stderr = String::from_utf8_lossy(&output.stderr).to_string();
        let exit_code = output.status.code();

        if output.status.success() {
            Ok(ScriptOutput {
                stdout,
                stderr,
                exit_code,
                success: true,
            })
        } else {
            Err(PythonError::execution_failed(
                "Script execution failed",
                Some(stdout),
                Some(stderr),
                exit_code,
            ))
        }
    }
}

/// Output from a successful script execution
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScriptOutput {
    pub stdout: String,
    pub stderr: String,
    pub exit_code: Option<i32>,
    pub success: bool,
}

impl ScriptOutput {
    /// Parse stdout as JSON
    pub fn parse_json<T: for<'de> Deserialize<'de>>(&self) -> Result<T, serde_json::Error> {
        serde_json::from_str(&self.stdout)
    }

    /// Get stdout lines
    pub fn lines(&self) -> Vec<&str> {
        self.stdout.lines().collect()
    }
}

/// Determine which Python interpreter to use.
/// Priority:
/// 1) APP_PYTHON_BIN env var
/// 2) backend/venv/bin/python3 relative to workspace root
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

    // Check venv first
    let venv = root.join("backend/venv/bin/python3");
    if venv.exists() {
        return venv.to_string_lossy().to_string();
    }

    // Try common Python versions
    for bin in &["python3.12", "python3.11", "python3.10", "python3"] {
        if Command::new(bin)
            .arg("--version")
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .is_ok()
        {
            return bin.to_string();
        }
    }

    "python3".to_string()
}

/// Resolve the scripts directory
fn resolve_scripts_dir(app: &AppHandle) -> PathBuf {
    // Try relative to executable first (dev mode)
    if let Ok(mut exe) = std::env::current_exe() {
        for _ in 0..4 {
            exe.pop();
        }
        let backend = exe.join("backend");
        if backend.exists() {
            return backend;
        }
    }

    // Try app resource directory (bundled mode)
    if let Ok(resource) = app.path().resolve("backend", tauri::path::BaseDirectory::Resource) {
        if resource.exists() {
            return resource;
        }
    }

    // Fallback to current directory
    PathBuf::from("backend")
}

/// Builder pattern for running scripts with complex arguments
pub struct ScriptRunner<'a> {
    bridge: &'a PythonBridge,
    script: String,
    args: Vec<String>,
    required_packages: Vec<String>,
}

impl<'a> ScriptRunner<'a> {
    pub fn new(bridge: &'a PythonBridge, script: impl Into<String>) -> Self {
        Self {
            bridge,
            script: script.into(),
            args: Vec::new(),
            required_packages: Vec::new(),
        }
    }

    /// Add a positional argument
    pub fn arg(mut self, arg: impl Into<String>) -> Self {
        self.args.push(arg.into());
        self
    }

    /// Add multiple arguments
    pub fn args<I, S>(mut self, args: I) -> Self
    where
        I: IntoIterator<Item = S>,
        S: Into<String>,
    {
        self.args.extend(args.into_iter().map(|s| s.into()));
        self
    }

    /// Add a flag argument (--flag)
    pub fn flag(mut self, name: &str) -> Self {
        self.args.push(format!("--{}", name));
        self
    }

    /// Add a key-value argument (--key value)
    pub fn option(mut self, name: &str, value: impl Into<String>) -> Self {
        self.args.push(format!("--{}", name));
        self.args.push(value.into());
        self
    }

    /// Add an optional key-value argument (only if value is Some)
    pub fn option_if<T: Into<String>>(self, name: &str, value: Option<T>) -> Self {
        match value {
            Some(v) => self.option(name, v),
            None => self,
        }
    }

    /// Specify required packages (will be checked before running)
    pub fn requires(mut self, package: impl Into<String>) -> Self {
        self.required_packages.push(package.into());
        self
    }

    /// Run the script
    pub fn run(self) -> PythonResult<ScriptOutput> {
        // Check required packages
        if !self.required_packages.is_empty() {
            let packages: Vec<&str> = self.required_packages.iter().map(|s| s.as_str()).collect();
            let missing = self.bridge.check_packages(&packages)?;
            if !missing.is_empty() {
                return Err(PythonError::missing_dependency(missing.join(", ")));
            }
        }

        let args: Vec<&str> = self.args.iter().map(|s| s.as_str()).collect();
        self.bridge.run_script(&self.script, &args)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_python_error_display() {
        let err = PythonError::python_not_found("No Python");
        assert!(err.to_string().contains("PythonNotFound"));
    }

    #[test]
    fn test_script_output_lines() {
        let output = ScriptOutput {
            stdout: "line1\nline2\nline3".to_string(),
            stderr: String::new(),
            exit_code: Some(0),
            success: true,
        };
        assert_eq!(output.lines().len(), 3);
    }
}
