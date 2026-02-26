//
//  ServerManager.swift
//  KokoroTTS
//
//  Manages server health checks and launchctl control
//

import SwiftUI
import Combine

enum ServerStatus {
    case running
    case starting
    case stopped
    case error
}

@MainActor
class ServerManager: ObservableObject {
    @Published var apiStatus: ServerStatus = .stopped
    @Published var daemonStatus: ServerStatus = .stopped
    @Published var voices: [String] = []
    @Published var selectedVoice: String = "af_heart"
    @Published var speed: Double = 1.0
    @Published var lastError: String?
    @Published var logs: [String] = []
    
    private var healthCheckTimer: Timer?
    private let apiURL = "http://127.0.0.1:8080"
    private let daemonURL = "http://127.0.0.1:8081"

    private static let homeDir = FileManager.default.homeDirectoryForCurrentUser.path
    static let logsDir = "\(homeDir)/Library/Logs/kokoro"

    /// Project path — resolved from LaunchAgent plist or defaults to ~/Desktop/Projects/kokoro-onnx
    let projectPath: String = {
        let plistPath = "\(homeDir)/Library/LaunchAgents/com.kokoro.tts-api.plist"
        if let plist = NSDictionary(contentsOfFile: plistPath),
           let workDir = plist["WorkingDirectory"] as? String {
            return workDir
        }
        return "\(homeDir)/Desktop/Projects/kokoro-onnx"
    }()
    
    var statusIcon: String {
        if apiStatus == .running && daemonStatus == .running {
            return "circle.fill"
        } else if apiStatus == .starting || daemonStatus == .starting {
            return "circle.dotted"
        } else {
            return "circle"
        }
    }
    
    var statusColor: Color {
        if apiStatus == .running && daemonStatus == .running {
            return .green
        } else if apiStatus == .starting || daemonStatus == .starting {
            return .yellow
        } else if apiStatus == .error || daemonStatus == .error {
            return .red
        } else {
            return .gray
        }
    }
    
    var statusText: String {
        if apiStatus == .running && daemonStatus == .running {
            return "Running"
        } else if apiStatus == .starting || daemonStatus == .starting {
            return "Starting..."
        } else if apiStatus == .error || daemonStatus == .error {
            return "Error"
        } else {
            return "Stopped"
        }
    }
    
    init() {
        startHealthChecks()
    }
    
    func startHealthChecks() {
        // Initial check
        Task { await checkHealth() }
        
        // Periodic checks every 5 seconds
        healthCheckTimer = Timer.scheduledTimer(withTimeInterval: 5.0, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in
                await self?.checkHealth()
            }
        }
    }
    
    func checkHealth() async {
        // Check API health
        await checkAPIHealth()
        
        // Check daemon health
        await checkDaemonHealth()
        
        // Fetch voices if API is running
        if apiStatus == .running && voices.isEmpty {
            await fetchVoices()
        }
    }
    
    private func checkAPIHealth() async {
        guard let url = URL(string: "\(apiURL)/health") else { return }
        
        do {
            let (data, response) = try await URLSession.shared.data(from: url)
            if let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 {
                if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let status = json["status"] as? String, status == "ok" {
                    apiStatus = .running
                    return
                }
            }
            apiStatus = .stopped
        } catch {
            apiStatus = .stopped
        }
    }
    
    private func checkDaemonHealth() async {
        guard let url = URL(string: "\(daemonURL)/health") else { return }
        
        do {
            let (_, response) = try await URLSession.shared.data(from: url)
            if let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 {
                daemonStatus = .running
                return
            }
            daemonStatus = .stopped
        } catch {
            daemonStatus = .stopped
        }
    }
    
    func fetchVoices() async {
        guard let url = URL(string: "\(apiURL)/voices") else { return }
        
        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let voiceList = json["voices"] as? [String] {
                voices = voiceList.sorted()
                if !voices.contains(selectedVoice), let first = voices.first {
                    selectedVoice = first
                }
            }
        } catch {
            lastError = "Failed to fetch voices: \(error.localizedDescription)"
        }
    }
    
    // MARK: - Service Control
    
    func startServices() {
        apiStatus = .starting
        daemonStatus = .starting
        
        // Load LaunchAgents
        runLaunchctl(action: "load", service: "com.kokoro.tts-api")
        runLaunchctl(action: "load", service: "com.kokoro.audio-daemon")
        
        // Check health after a delay
        Task {
            try? await Task.sleep(nanoseconds: 3_000_000_000)
            await checkHealth()
        }
    }
    
    func stopServices() {
        runLaunchctl(action: "unload", service: "com.kokoro.tts-api")
        runLaunchctl(action: "unload", service: "com.kokoro.audio-daemon")
        
        apiStatus = .stopped
        daemonStatus = .stopped
    }
    
    func restartServices() {
        stopServices()
        
        Task {
            try? await Task.sleep(nanoseconds: 1_000_000_000)
            startServices()
        }
    }
    
    private func runLaunchctl(action: String, service: String) {
        let plistPath = "\(Self.homeDir)/Library/LaunchAgents/\(service).plist"
        
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/bin/launchctl")
        process.arguments = [action, plistPath]
        
        do {
            try process.run()
            process.waitUntilExit()
        } catch {
            lastError = "Failed to \(action) \(service): \(error.localizedDescription)"
        }
    }
    
    // MARK: - Log Reading
    
    func refreshLogs() {
        let logFiles = [
            "\(Self.logsDir)/tts-api.log",
            "\(Self.logsDir)/audio-daemon.log"
        ]
        
        var allLogs: [String] = []
        
        for logFile in logFiles {
            let fileURL = URL(fileURLWithPath: logFile)
            
            // Check if file exists
            guard FileManager.default.fileExists(atPath: logFile) else {
                allLogs.append("--- \(fileURL.lastPathComponent) ---")
                allLogs.append("Log file not found at: \(logFile)")
                continue
            }
            
            // Try to read the file
            do {
                let content = try String(contentsOf: fileURL, encoding: .utf8)
                let lines = content.components(separatedBy: .newlines)
                let lastLines = Array(lines.suffix(25))
                
                if lastLines.isEmpty {
                    allLogs.append("--- \(fileURL.lastPathComponent) ---")
                    allLogs.append("(Log file is empty)")
                } else {
                    allLogs.append("--- \(fileURL.lastPathComponent) ---")
                    allLogs.append(contentsOf: lastLines)
                }
            } catch {
                allLogs.append("--- \(fileURL.lastPathComponent) ---")
                allLogs.append("Error reading log: \(error.localizedDescription)")
            }
        }
        
        // If no logs were read, add a message
        if allLogs.isEmpty {
            allLogs.append("No logs available")
        }
        
        logs = allLogs
    }
}
