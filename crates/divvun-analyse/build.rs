// Trigger sysroot lookup from divvun-runtime's own build.rs
// by setting BUILD_ROOT to the divvun-runtime root.
fn main() {
    let manifest = std::env::var("CARGO_MANIFEST_DIR").unwrap();
    // Point BUILD_ROOT to the divvun-runtime root so the sysroot path
    // .x/sysroot/{target} is found by divvun-runtime's build.rs.
    let runtime_root = std::path::Path::new(&manifest)
        .join("../../../divvun-runtime")
        .canonicalize()
        .expect("Fann ikkje divvun-runtime-rota");
    std::env::set_var("BUILD_ROOT", runtime_root.to_str().unwrap());

    println!("cargo:rerun-if-changed=build.rs");
}
