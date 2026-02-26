//
//  MenuBarView.swift
//  KokoroTTS
//
//  Main menu bar popup view
//

import SwiftUI

struct MenuBarView: View {
    @EnvironmentObject var serverManager: ServerManager
    @State private var showingLogs = false
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header with status
            HStack {
                Circle()
                    .fill(serverManager.statusColor)
                    .frame(width: 10, height: 10)
                Text("Kokoro TTS")
                    .font(.headline)
                Spacer()
                Text(serverManager.statusText)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            Divider()
            
            // Service status
            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Image(systemName: serverManager.apiStatus == .running ? "checkmark.circle.fill" : "xmark.circle")
                        .foregroundColor(serverManager.apiStatus == .running ? .green : .red)
                    Text("TTS API")
                    Spacer()
                    Text(":8080")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                HStack {
                    Image(systemName: serverManager.daemonStatus == .running ? "checkmark.circle.fill" : "xmark.circle")
                        .foregroundColor(serverManager.daemonStatus == .running ? .green : .red)
                    Text("Audio Daemon")
                    Spacer()
                    Text(":8081")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
            
            Divider()
            
            // Controls
            HStack(spacing: 8) {
                Button(action: { serverManager.startServices() }) {
                    Label("Start", systemImage: "play.fill")
                }
                .disabled(serverManager.apiStatus == .running && serverManager.daemonStatus == .running)
                
                Button(action: { serverManager.stopServices() }) {
                    Label("Stop", systemImage: "stop.fill")
                }
                .disabled(serverManager.apiStatus == .stopped && serverManager.daemonStatus == .stopped)
                
                Button(action: { serverManager.restartServices() }) {
                    Label("Restart", systemImage: "arrow.clockwise")
                }
            }
            .buttonStyle(.bordered)
            
            Divider()
            
            // Voice selection
            if !serverManager.voices.isEmpty {
                VStack(alignment: .leading, spacing: 6) {
                    Text("Voice")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    
                    Picker("Voice", selection: $serverManager.selectedVoice) {
                        ForEach(serverManager.voices, id: \.self) { voice in
                            Text(voice).tag(voice)
                        }
                    }
                    .labelsHidden()
                    .pickerStyle(.menu)
                }
            }
            
            // Speed slider
            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Text("Speed")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Spacer()
                    Text(String(format: "%.2fx", serverManager.speed))
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                Slider(value: $serverManager.speed, in: 0.5...2.0, step: 0.05)
            }
            
            Divider()
            
            // Logs toggle
            Button(action: {
                showingLogs.toggle()
                if showingLogs {
                    serverManager.refreshLogs()
                }
            }) {
                HStack {
                    Image(systemName: "doc.text")
                    Text(showingLogs ? "Hide Logs" : "Show Logs")
                }
            }
            .buttonStyle(.plain)
            
            // Log viewer
            if showingLogs {
                if serverManager.logs.isEmpty {
                    VStack(spacing: 8) {
                        Text("No logs available")
                            .foregroundColor(.secondary)
                            .font(.caption)
                        Button(action: { serverManager.refreshLogs() }) {
                            Label("Try Loading Logs", systemImage: "arrow.clockwise")
                        }
                        .buttonStyle(.bordered)
                        .font(.caption)
                    }
                    .frame(height: 100)
                } else {
                    ScrollView {
                        VStack(alignment: .leading, spacing: 2) {
                            ForEach(Array(serverManager.logs.enumerated()), id: \.offset) { index, line in
                                Text(line)
                                    .font(.system(size: 10, design: .monospaced))
                                    .foregroundColor(line.hasPrefix("---") ? .blue : 
                                                    line.contains("ERROR") || line.contains("Error") ? .red :
                                                    line.contains("WARNING") || line.contains("Warning") ? .orange :
                                                    .primary)
                                    .textSelection(.enabled)
                            }
                        }
                        .padding(4)
                    }
                    .frame(height: 200)
                    .background(Color(NSColor.textBackgroundColor))
                    .cornerRadius(4)
                }
                
                Button(action: { serverManager.refreshLogs() }) {
                    Label("Refresh Logs", systemImage: "arrow.clockwise")
                }
                .buttonStyle(.bordered)
                .font(.caption)
            }
            
            Divider()
            
            // Footer
            HStack {
                Button("Settings...") {
                    NSApp.sendAction(Selector(("showSettingsWindow:")), to: nil, from: nil)
                }
                .buttonStyle(.plain)
                
                Spacer()
                
                Button("Quit") {
                    NSApplication.shared.terminate(nil)
                }
                .buttonStyle(.plain)
                .foregroundColor(.red)
            }
            .font(.caption)
        }
        .padding()
        .frame(width: 300)
    }
}

#Preview {
    MenuBarView()
        .environmentObject(ServerManager())
}
