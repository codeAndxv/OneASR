// OneASR Desktop Host Library (Tauri v2)
// Pure headless system tray companion modeled after Ollama.
// Manages the background engine daemon, health status polling, and system tray menu.

use std::net::TcpStream;
use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::{Arc, Mutex};
use std::time::Duration;

use tauri::menu::{Menu, MenuItem, PredefinedMenuItem};
use tauri::tray::TrayIconBuilder;
use tauri::Manager;

/// Check if the local backend server is accepting TCP connections.
fn is_server_listening(addr: &str) -> bool {
    let timeout = Duration::from_millis(600);
    if let Ok(socket_addr) = addr.parse() {
        TcpStream::connect_timeout(&socket_addr, timeout).is_ok()
    } else {
        false
    }
}

/// Locate the OneASR backend root containing `server/main.py` and its Python executable.
/// Strictly hermetic:
/// 1. Explicit environment variables `ONEASR_ROOT` and `ONEASR_PYTHON`.
/// 2. Packaged standalone application bundle resources (macOS .app Resources or Windows/Linux resources directory).
/// If not running inside a packaged bundle with embedded Python, returns None (pure client mode).
fn discover_backend_env() -> Option<(PathBuf, PathBuf)> {
    // 1. Check explicit environment variables
    if let (Ok(root_str), Ok(py_str)) = (std::env::var("ONEASR_ROOT"), std::env::var("ONEASR_PYTHON")) {
        let root = PathBuf::from(root_str);
        let py = PathBuf::from(py_str);
        if root.join("server").join("main.py").exists() && py.exists() {
            return Some((root, py));
        }
    }

    // 2. Check bundled standalone application resources only
    if let Ok(exe) = std::env::current_exe() {
        let mut candidate_resource_dirs: Vec<PathBuf> = Vec::new();

        // macOS: OneASR.app/Contents/MacOS/exe -> OneASR.app/Contents/Resources
        if let Some(contents) = exe.parent().and_then(|p| p.parent()) {
            candidate_resource_dirs.push(contents.join("Resources"));
        }

        // Windows & Linux: exe_dir/resources or exe_dir
        if let Some(parent) = exe.parent() {
            candidate_resource_dirs.push(parent.join("resources"));
            candidate_resource_dirs.push(parent.to_path_buf());
        }

        for res_dir in candidate_resource_dirs {
            let py_candidates = [
                res_dir.join("python").join("bin").join("python3"),
                res_dir.join("python").join("bin").join("python"),
                res_dir.join("python").join("python.exe"),
                res_dir.join("python").join("Scripts").join("python.exe"),
            ];

            let py_bin = py_candidates.into_iter().find(|p| p.exists());

            if let Some(py) = py_bin {
                // Check if server/main.py is located directly under res_dir or res_dir/backend
                if res_dir.join("server").join("main.py").exists() {
                    return Some((res_dir, py));
                }
                let backend_sub = res_dir.join("backend");
                if backend_sub.join("server").join("main.py").exists() {
                    return Some((backend_sub, py));
                }
            }
        }
    }

    None
}

/// Ensure 'oneasr' command is available in user's PATH (~/.local/bin/oneasr).
/// Modeled after Ollama's automatic CLI tool registration.
fn ensure_cli_installed() {
    #[cfg(unix)]
    {
        if let Some(home) = dirs::home_dir() {
            let local_bin = home.join(".local").join("bin");
            let target_cli = local_bin.join("oneasr");

            let _ = std::fs::create_dir_all(&local_bin);

            // Determine what launcher script to point to
            let mut launcher_source: Option<PathBuf> = None;

            // 1. Packaged standalone application Resources/bin/oneasr
            if let Ok(exe) = std::env::current_exe() {
                if let Some(contents) = exe.parent().and_then(|p| p.parent()) {
                    let standalone_oneasr = contents.join("Resources").join("bin").join("oneasr");
                    if standalone_oneasr.exists() {
                        launcher_source = Some(standalone_oneasr);
                    }
                }
            }

            if let Some(src) = launcher_source {
                if target_cli.exists() || std::fs::symlink_metadata(&target_cli).is_ok() {
                    let _ = std::fs::remove_file(&target_cli);
                }
                use std::os::unix::fs::symlink;
                if let Ok(_) = symlink(&src, &target_cli) {
                    eprintln!("[OneASR] Successfully symlinked CLI tool from {:?} to {:?}", src, target_cli);
                }
                return;
            }

            // 2. Discover from development environment or ~/.oneasr/core
            let script_content = if let Some((root_dir, py_bin)) = discover_backend_env() {
                format!(
                    "#!/usr/bin/env bash\nexport PYTHONPATH=\"{}:$PYTHONPATH\"\nexec \"{}\" -m cli.main \"$@\"\n",
                    root_dir.to_string_lossy(),
                    py_bin.to_string_lossy()
                )
            } else {
                return;
            };

            let _ = std::fs::write(&target_cli, script_content);
            use std::os::unix::fs::PermissionsExt;
            let _ = std::fs::set_permissions(&target_cli, std::fs::Permissions::from_mode(0o755));
            eprintln!("[OneASR] Injected CLI launcher at {:?}", target_cli);
        }
    }
}

/// Safely terminate a child process.
fn terminate_child(child_lock: &Arc<Mutex<Option<Child>>>) {
    if let Ok(mut lock) = child_lock.lock() {
        if let Some(mut child) = lock.take() {
            eprintln!("[OneASR] Terminating backend child process (PID: {})...", child.id());
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

/// Spawns the backend daemon process if not already listening on 127.0.0.1:8020.
/// Redirects stdout and stderr to ~/.oneasr/logs/server.log.
fn spawn_backend(child_handle: &Arc<Mutex<Option<Child>>>) -> Result<(), String> {
    let backend_addr = "127.0.0.1:8020";

    // If server is already responding on 8020, nothing to spawn
    if is_server_listening(backend_addr) {
        eprintln!("[OneASR] Backend daemon already responding on {}", backend_addr);
        return Ok(());
    }

    // Terminate existing dead or unresponsive child process if recorded
    terminate_child(child_handle);

    if let Some((root_dir, py_bin)) = discover_backend_env() {
        eprintln!("[OneASR] Spawning backend daemon in {:?} via {:?}", root_dir, py_bin);

        let mut cmd = Command::new(&py_bin);
        cmd.arg("-m")
            .arg("server.main")
            .current_dir(&root_dir)
            .env("PYTHONUNBUFFERED", "1");

        // Prepend standalone python & ffmpeg bin directories to PATH
        let mut path_entries: Vec<String> = Vec::new();
        if let Some(py_parent) = py_bin.parent() {
            path_entries.push(py_parent.to_string_lossy().to_string());
        }
        let bundled_bin = root_dir.join("bin");
        if bundled_bin.exists() {
            path_entries.push(bundled_bin.to_string_lossy().to_string());
        }
        if let Ok(sys_path) = std::env::var("PATH") {
            path_entries.push(sys_path);
        }
        let path_sep = if cfg!(windows) { ";" } else { ":" };
        cmd.env("PATH", path_entries.join(path_sep));

        // Prepend root_dir to PYTHONPATH
        if let Ok(sys_pythonpath) = std::env::var("PYTHONPATH") {
            cmd.env("PYTHONPATH", format!("{}{}{}", root_dir.to_string_lossy(), path_sep, sys_pythonpath));
        } else {
            cmd.env("PYTHONPATH", root_dir.to_string_lossy().to_string());
        }

        // Redirect stdout/stderr to ~/.oneasr/logs/server.log
        if let Some(home) = dirs::home_dir() {
            let log_dir = home.join(".oneasr").join("logs");
            let _ = std::fs::create_dir_all(&log_dir);
            let log_file = log_dir.join("server.log");
            if let Ok(file) = std::fs::OpenOptions::new()
                .create(true)
                .append(true)
                .open(&log_file)
            {
                if let Ok(err_file) = file.try_clone() {
                    cmd.stdout(std::process::Stdio::from(file));
                    cmd.stderr(std::process::Stdio::from(err_file));
                }
            }
        }

        match cmd.spawn() {
            Ok(child) => {
                eprintln!("[OneASR] Backend daemon started with PID: {}", child.id());
                if let Ok(mut lock) = child_handle.lock() {
                    *lock = Some(child);
                }
                Ok(())
            }
            Err(err) => {
                let msg = format!("Failed to spawn backend daemon: {}", err);
                eprintln!("[OneASR] {}", msg);
                Err(msg)
            }
        }
    } else {
        let msg = "Could not locate backend root or Python executable".to_string();
        eprintln!("[OneASR] {}", msg);
        Err(msg)
    }
}

/// Tauri native command: Open local application directories in macOS Finder.
/// Bypasses HTTP server completely for robust, offline-capable desktop UX.
#[tauri::command]
fn open_local_dir(target: String) -> Result<(), String> {
    if let Some(home) = dirs::home_dir() {
        let sub = if target == "logs" { "logs" } else { "models" };
        let path = home.join(".oneasr").join(sub);
        let _ = std::fs::create_dir_all(&path);
        let _ = open::that(path);
    }
    Ok(())
}

/// Tauri native command: Manually trigger / retry starting the backend daemon.
#[tauri::command]
fn start_backend(
    state: tauri::State<Arc<Mutex<Option<Child>>>>,
) -> Result<bool, String> {
    spawn_backend(&state).map(|_| true)
}

pub fn run() {
    let child_handle: Arc<Mutex<Option<Child>>> = Arc::new(Mutex::new(None));
    let child_for_tray = child_handle.clone();
    let child_for_exit = child_handle.clone();

    tauri::Builder::default()
        .manage(child_handle.clone())
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![open_local_dir, start_backend])
        .setup(move |app| {
            let handle = app.handle();
            let backend_addr = "127.0.0.1:8020";

            // 0. Ensure global CLI tool 'oneasr' is registered in PATH (Ollama pattern)
            ensure_cli_installed();

            // 1. Initial attempt to spawn backend daemon if not already listening
            let _ = spawn_backend(&child_handle);

            // 2. Build Native System Tray Menu
            let initial_status = if is_server_listening(backend_addr) {
                "OneASR: 127.0.0.1:8020 (Online)"
            } else {
                "OneASR: 127.0.0.1:8020 (Starting...)"
            };

            let status_item = MenuItem::with_id(handle, "status", initial_status, false, None::<&str>)?;
            let open_item = MenuItem::with_id(handle, "open", "Open OneASR Window...", true, None::<&str>)?;
            let api_item = MenuItem::with_id(handle, "api", "Open Swagger API Docs...", true, None::<&str>)?;
            let models_item = MenuItem::with_id(handle, "models", "Models Directory...", true, None::<&str>)?;
            let logs_item = MenuItem::with_id(handle, "logs", "View Logs...", true, None::<&str>)?;
            let separator1 = PredefinedMenuItem::separator(handle)?;
            let separator2 = PredefinedMenuItem::separator(handle)?;
            let quit_item = MenuItem::with_id(handle, "quit", "Quit OneASR", true, None::<&str>)?;

            let menu = Menu::with_items(
                handle,
                &[
                    &status_item,
                    &open_item,
                    &separator1,
                    &api_item,
                    &models_item,
                    &logs_item,
                    &separator2,
                    &quit_item,
                ],
            )?;

            // 3. Build Tray Icon with Mascot Cat Line-Art Template (adapts to light/dark modes)
            let tray_icon = tauri::include_image!("icons/tray@2x.png");

            let _tray = TrayIconBuilder::new()
                .icon(tray_icon)
                .icon_as_template(true)
                .menu(&menu)
                .show_menu_on_left_click(true)
                .on_menu_event(move |app, event| match event.id.as_ref() {
                    "open" => {
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                    "api" => {
                        let _ = open::that("http://127.0.0.1:8020/docs");
                    }
                    "models" => {
                        if let Some(home) = dirs::home_dir() {
                            let models_path = home.join(".oneasr").join("models");
                            let _ = std::fs::create_dir_all(&models_path);
                            let _ = open::that(models_path);
                        }
                    }
                    "logs" => {
                        if let Some(home) = dirs::home_dir() {
                            let logs_path = home.join(".oneasr").join("logs");
                            let _ = std::fs::create_dir_all(&logs_path);
                            let _ = open::that(logs_path);
                        }
                    }
                    "quit" => {
                        terminate_child(&child_for_tray);
                        app.exit(0);
                    }
                    _ => {}
                })
                .build(app)?;

            // 4. Background Health Telemetry Poller
            let status_item_clone = status_item.clone();
            std::thread::spawn(move || loop {
                std::thread::sleep(Duration::from_secs(3));
                let is_up = is_server_listening(backend_addr);
                let label = if is_up {
                    "OneASR: 127.0.0.1:8020 (Online)"
                } else {
                    "OneASR: 127.0.0.1:8020 (Offline)"
                };
                let _ = status_item_clone.set_text(label);
            });

            // 5. Show and focus main companion window on initial startup
            if let Some(window) = handle.get_webview_window("main") {
                let _ = window.show();
                let _ = window.set_focus();
            }

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                let _ = window.hide();
            }
        })
        .build(tauri::generate_context!())
        .expect("error while building OneASR desktop application")
        .run(move |_app_handle, event| {
            if let tauri::RunEvent::Exit = event {
                terminate_child(&child_for_exit);
            }
        });
}
