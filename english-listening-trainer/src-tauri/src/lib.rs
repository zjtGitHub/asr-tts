use std::sync::Mutex;

use tauri::Manager;
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

#[derive(Default)]
struct BackendProcess(Mutex<Option<CommandChild>>);

fn stop_backend(app: &tauri::AppHandle) {
    let state = app.state::<BackendProcess>();
    let child = state
        .0
        .lock()
        .expect("backend process mutex poisoned")
        .take();

    if let Some(child) = child {
        let _ = child.kill();
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let backend = BackendProcess::default();

            #[cfg(not(debug_assertions))]
            {
                let sidecar = app.shell().sidecar("english-listening-backend")?;
                let (mut events, child) = sidecar.spawn()?;

                eprintln!(
                    "English Listening Trainer backend started (pid {}).",
                    child.pid()
                );
                *backend
                    .0
                    .lock()
                    .expect("backend process mutex poisoned") = Some(child);

                tauri::async_runtime::spawn(async move {
                    while let Some(event) = events.recv().await {
                        match event {
                            CommandEvent::Stdout(bytes) => {
                                eprintln!(
                                    "[backend] {}",
                                    String::from_utf8_lossy(&bytes).trim_end()
                                );
                            }
                            CommandEvent::Stderr(bytes) => {
                                eprintln!(
                                    "[backend] {}",
                                    String::from_utf8_lossy(&bytes).trim_end()
                                );
                            }
                            CommandEvent::Error(error) => {
                                eprintln!("[backend] process error: {error}");
                            }
                            CommandEvent::Terminated(payload) => {
                                eprintln!("[backend] terminated: {payload:?}");
                            }
                            _ => {}
                        }
                    }
                });
            }

            app.manage(backend);
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building English Listening Trainer");

    app.run(|app_handle, event| {
        if matches!(event, tauri::RunEvent::Exit) {
            stop_backend(app_handle);
        }
    });
}
