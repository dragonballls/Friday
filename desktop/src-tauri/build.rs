use std::fs;
use std::path::PathBuf;

fn main() {
    // Tauri's Windows resource compiler requires an ICO during a clean build.
    // Generate a tiny valid ICO at build time so CI never depends on a
    // committed binary icon.
    if std::env::var("CARGO_CFG_TARGET_OS").as_deref() == Ok("windows") {
        let manifest_dir = PathBuf::from(std::env::var("CARGO_MANIFEST_DIR").unwrap());
        let icons_dir = manifest_dir.join("icons");
        let icon_path = icons_dir.join("icon.ico");
        fs::create_dir_all(&icons_dir).expect("failed to create Tauri icons directory");

        // 1x1, 32-bit RGBA ICO containing a minimal BMP/DIB image.
        const ICON: &[u8] = &[
            0,0,1,0,1,0,1,1,0,0,1,0,32,0,48,0,0,0,22,0,0,0,
            40,0,0,0,1,0,0,0,2,0,0,0,1,0,32,0,0,0,0,0,4,0,0,0,
            0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
            0,0,0,0,255,0,0,0,0,0
        ];
        fs::write(&icon_path, ICON).expect("failed to generate Windows ICO");
        println!("cargo:rerun-if-changed=build.rs");
    }

    tauri_build::build();
}
