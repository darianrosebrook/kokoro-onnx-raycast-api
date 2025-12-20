//
//  KokoroTTSApp.swift
//  KokoroTTS
//
//  Menu bar application for Kokoro TTS server control
//

import SwiftUI

@main
struct KokoroTTSApp: App {
    @StateObject private var serverManager = ServerManager()
    
    var body: some Scene {
        MenuBarExtra {
            MenuBarView()
                .environmentObject(serverManager)
        } label: {
            HStack(spacing: 4) {
                Image(systemName: serverManager.statusIcon)
                    .foregroundColor(serverManager.statusColor)
                Text("TTS")
                    .font(.system(size: 12, weight: .medium))
            }
        }
        .menuBarExtraStyle(.window)
        
        Settings {
            SettingsView()
                .environmentObject(serverManager)
        }
    }
}
