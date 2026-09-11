use std::fs;
use std::path::PathBuf;

fn main() {
    // Windows resource generation requires an ICO on clean builds. Keep the
    // icon deterministic and generate it as a valid PNG-backed ICO here.
    if std::env::var("CARGO_CFG_TARGET_OS").as_deref() == Ok("windows") {
        let manifest_dir = PathBuf::from(std::env::var("CARGO_MANIFEST_DIR").unwrap());
        let icons_dir = manifest_dir.join("icons");
        let icon_path = icons_dir.join("icon.ico");
        fs::create_dir_all(&icons_dir).expect("failed to create Tauri icons directory");

        // ICO header + one 1x1 RGBA PNG image.
        const PNG: &[u8] = &[
            137,80,78,71,13,10,26,10,0,0,0,13,73,72,68,82,
            0,0,0,1,0,0,0,1,8,6,0,0,0,31,21,196,137,
            0,0,0,13,73,68,65,84,120,156,99,96,96,96,248,15,0,1,4,1,0,
            95,229,199,75,0,0,0,0,73,69,78,68,174,66,96,130,
        ];
        let mut ico = Vec::with_capacity(22 + PNG.len());
        ico.extend_from_slice(&[0, 0, 1, 0, 1, 0]);
        ico.extend_from_slice(&[1, 1, 0, 0]);
        ico.extend_from_slice(&1u16.to_le_bytes());
        ico.extend_from_slice(&32u16.to_le_bytes());
        ico.extend_from_slice(&(PNG.len() as u32).to_le_bytes());
        ico.extend_from_slice(&22u32.to_le_bytes());
        ico.extend_from_slice(PNG);
        fs::write(&icon_path, ico).expect("failed to generate Windows ICO");
        println!("cargo:rerun-if-changed=build.rs");
    }

    tauri_build::build();
}
