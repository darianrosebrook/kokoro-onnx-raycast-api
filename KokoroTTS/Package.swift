// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "KokoroTTS",
    platforms: [
        .macOS(.v13)
    ],
    products: [
        .executable(name: "KokoroTTS", targets: ["KokoroTTS"])
    ],
    targets: [
        .executableTarget(
            name: "KokoroTTS",
            path: "KokoroTTS",
            resources: [
                .process("Assets.xcassets")
            ]
        )
    ]
)
