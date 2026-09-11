use std::fs;
use std::path::PathBuf;

fn main() {
    // Tauri's Windows resource compiler requires an ICO even when the bundle
    // config intentionally leaves the icon list empty. Generate a tiny valid
    // ICO at build time so clean CI checkouts never depend on a binary icon
    // being committed to the repository.
    if std::env::var("CARGO_CFG_TARGET_OS").as_deref() == Ok("windows") {
        let manifest_dir = PathBuf::from(std::env::var("CARGO_MANIFEST_DIR").unwrap());
        let icons_dir = manifest_dir.join("icons");
        let icon_path = icons_dir.join("icon.ico");
        fs::create_dir_all(&icons_dir).expect("failed to create Tauri icons directory");
        const ICON: &[u8] = &[
            0,0,1,0,1,0,32,32,0,0,1,0,32,0,116,0,0,0,22,0,0,0,137,80,78,71,13,10,26,10,
            0,0,0,13,73,72,68,82,0,0,0,32,0,0,0,32,8,6,0,0,0,115,122,122,244,0,0,0,59,
            73,68,65,84,120,218,237,213,161,17,0,32,12,0,177,74,28,6,195,254,43,176,95,
            59,3,138,163,23,241,62,238,99,204,157,47,11,0,0,0,128,111,0,235,228,85,0,
            0,0,0,0,0,253,0,110,8,0,0,208,22,80,97,122,161,60,53,54,121,31,0,0,0,0,
            73,69,78,68,174,66,96,130,
        ];
        fs::write(&icon_path, ICON).expect("failed to generate Windows ICO");
        println!("cargo:rerun-if-changed=build.rs");
    }

    tauri_build::build();
}
