// FormsLang desktop -- B2DEV TECH. Free to use, not to copy.
//
// The window is a shell: the Python engine (a frozen sidecar) starts on a
// free loopback port and the webview navigates to it as soon as it answers.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::net::{SocketAddr, TcpListener, TcpStream};
use std::sync::Mutex;
use std::time::Duration;

use tauri::{Manager, RunEvent};
use tauri_plugin_shell::process::CommandChild;
use tauri_plugin_shell::ShellExt;

struct Engine(Mutex<Option<CommandChild>>);

fn free_port() -> u16 {
    TcpListener::bind("127.0.0.1:0")
        .expect("no free loopback port")
        .local_addr()
        .expect("local_addr")
        .port()
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(Engine(Mutex::new(None)))
        .setup(|app| {
            let port = free_port();
            let docs = app
                .path()
                .document_dir()
                .or_else(|_| app.path().home_dir())?;
            let work = app.path().app_local_data_dir()?.join("workspace");
            std::fs::create_dir_all(&work)?;

            let (_rx, child) = app
                .shell()
                .sidecar("formslang-engine")?
                .args([
                    "workbench",
                    docs.to_string_lossy().as_ref(),
                    "-o",
                    work.to_string_lossy().as_ref(),
                    "--port",
                    &port.to_string(),
                    "--no-browser",
                ])
                .spawn()?;
            app.state::<Engine>().0.lock().unwrap().replace(child);

            let win = app.get_webview_window("main").expect("main window");
            std::thread::spawn(move || {
                let addr: SocketAddr = ([127, 0, 0, 1], port).into();
                for _ in 0..300 {
                    if TcpStream::connect_timeout(&addr, Duration::from_millis(200)).is_ok() {
                        // A small gap between http.server's bind and its serve loop.
                        std::thread::sleep(Duration::from_millis(150));
                        let js = format!("location.replace('http://127.0.0.1:{port}/')");
                        let _ = win.eval(js.as_str());
                        return;
                    }
                    std::thread::sleep(Duration::from_millis(200));
                }
                let _ = win.eval("document.body.dataset.state='dead'");
            });
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("failed to build the Tauri app")
        .run(|app, event| {
            if let RunEvent::Exit = event {
                if let Some(child) = app.state::<Engine>().0.lock().unwrap().take() {
                    // PyInstaller onefile runs as two processes (bootloader +
                    // child); taskkill /T takes down the whole tree.
                    use std::os::windows::process::CommandExt;
                    let pid = child.pid();
                    let _ = std::process::Command::new("taskkill")
                        .args(["/F", "/T", "/PID", &pid.to_string()])
                        .creation_flags(0x0800_0000)
                        .status();
                    let _ = child.kill();
                }
            }
        });
}
