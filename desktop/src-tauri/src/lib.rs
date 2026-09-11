#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            #[cfg(desktop)]
            {
                use tauri_plugin_shell::ShellExt;
                let sidecar = app
                    .shell()
                    .sidecar("friday-api")
                    .expect("Friday API sidecar is not bundled");
                sidecar
                    .spawn()
                    .expect("failed to start Friday API sidecar");
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running Friday");
}
