#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            #[cfg(desktop)]
            {
                use tauri::async_runtime;
                use tauri_plugin_shell::{process::CommandEvent, ShellExt};

                let sidecar = app
                    .shell()
                    .sidecar("friday-api")
                    .expect("Friday API sidecar is not bundled");

                async_runtime::spawn(async move {
                    match sidecar.spawn() {
                        Ok((mut events, _child)) => {
                            while let Some(event) = events.recv().await {
                                match event {
                                    CommandEvent::Error(message) => {
                                        eprintln!("Friday API sidecar error: {message}");
                                    }
                                    CommandEvent::Terminated(payload) => {
                                        eprintln!(
                                            "Friday API sidecar terminated: code={:?} signal={:?}",
                                            payload.code, payload.signal
                                        );
                                        break;
                                    }
                                    _ => {}
                                }
                            }
                        }
                        Err(error) => {
                            eprintln!("Failed to start Friday API sidecar: {error}");
                        }
                    }
                });
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running Friday");
}
