//
//  SettingsView.swift
//  KokoroTTS
//
//  Settings/Preferences window
//

import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var serverManager: ServerManager
    @AppStorage("apiPort") private var apiPort = "8080"
    @AppStorage("daemonPort") private var daemonPort = "8081"
    @AppStorage("launchAtLogin") private var launchAtLogin = true
    
    var body: some View {
        Form {
            Section("Server Configuration") {
                TextField("API Port", text: $apiPort)
                    .textFieldStyle(.roundedBorder)
                
                TextField("Audio Daemon Port", text: $daemonPort)
                    .textFieldStyle(.roundedBorder)
            }
            
            Section("Startup") {
                Toggle("Start services at login", isOn: $launchAtLogin)
                
                Text("LaunchAgents are installed at:\n~/Library/LaunchAgents/")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            Section("Paths") {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Project: \(serverManager.projectPath)")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    
                    Text("Logs: ~/Library/Logs/kokoro/")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
            
            Section("Actions") {
                HStack {
                    Button("Open Logs Folder") {
                        NSWorkspace.shared.open(URL(fileURLWithPath: "/Users/darianrosebrook/Library/Logs/kokoro/"))
                    }
                    
                    Button("Open Project Folder") {
                        NSWorkspace.shared.open(URL(fileURLWithPath: serverManager.projectPath))
                    }
                }
            }
            
            Section("About") {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Kokoro TTS Menu Bar")
                        .font(.headline)
                    Text("Version 1.0.0")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Text("A menu bar app for controlling Kokoro TTS server")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
        }
        .formStyle(.grouped)
        .padding()
        .frame(width: 400, height: 400)
    }
}

#Preview {
    SettingsView()
        .environmentObject(ServerManager())
}
