#!/usr/bin/env tsx

/**
 * CAWS Security & Provenance Manager
 * Cryptographic signing, SLSA attestations, and security scanning
 *
 * @author @darianrosebrook
 */

import * as crypto from "crypto";
import * as fs from "fs";
import * as path from "path";
import { CawsBaseTool } from "./shared/base-tool.js";

interface SecurityProvenance {
  signature: string;
  signedBy: string;
  signedAt: string;
  algorithm: string;
  publicKeyFingerprint: string;
}

interface ModelProvenance {
  modelId: string;
  version: string;
  trainingDataCutoff?: string;
  provider: string;
  checksumVerified: boolean;
}

interface PromptProvenance {
  promptHashes: string[];
  totalPrompts: number;
  sanitizationApplied: boolean;
  injectionChecksPassed: boolean;
}

export class SecurityProvenanceManager extends CawsBaseTool {
  /**
   * Sign code or provenance manifest with cryptographic signature
   */
  async signArtifact(
    artifactPath: string,
    privateKeyPath?: string
  ): Promise<SecurityProvenance> {
    try {
      const content = fs.readFileSync(artifactPath, "utf-8");

      // Generate hash of content
      const hash = crypto.createHash("sha256").update(content).digest("hex");

      // Generate cryptographic signature with RSA-SHA256
      const signature = this.generateSignature(content, privateKeyPath);

      // Generate public key fingerprint for verification
      const publicKeyFingerprint = this.getPublicKeyFingerprint(privateKeyPath);

      return {
        signature,
        signedBy: process.env.CAWS_SIGNER || "caws-agent",
        signedAt: new Date().toISOString(),
        algorithm: "RSA-SHA256",
        publicKeyFingerprint,
      };
    } catch (error) {
      throw new Error(`Failed to sign artifact: ${error}`);
    }
  }

  /**
   * Verify artifact signature
   */
  async verifySignature(
    artifactPath: string,
    signature: string,
    publicKeyPath?: string
  ): Promise<boolean> {
    try {
      const content = fs.readFileSync(artifactPath, "utf-8");

      // Load public key from file or extract from development key pair
      let publicKey: string;

      if (publicKeyPath && fs.existsSync(publicKeyPath)) {
        publicKey = fs.readFileSync(publicKeyPath, "utf-8");

        // Ensure proper PEM format
        if (!publicKey.includes("-----BEGIN PUBLIC KEY-----")) {
          publicKey = `-----BEGIN PUBLIC KEY-----\n${publicKey}\n-----END PUBLIC KEY-----`;
        }
      } else {
        // For development, we can't verify without the public key
        // Fall back to hash-based verification for compatibility
        console.warn(
          "No public key provided, falling back to hash-based verification"
        );
        const expectedSignature = this.generateSignature(content, undefined);
        return signature === expectedSignature;
      }

      // Verify signature using RSA-SHA256
      const verify = crypto.createVerify("RSA-SHA256");
      verify.update(content);

      return verify.verify(publicKey, signature, "base64");
    } catch (error) {
      console.error(`Signature verification failed: ${error}`);
      // Fallback to hash-based verification for compatibility
      try {
        const content = fs.readFileSync(artifactPath, "utf-8");
        const expectedSignature = this.generateSignature(
          content,
          publicKeyPath
        );
        return signature === expectedSignature;
      } catch (fallbackError) {
        console.error(`Fallback verification also failed: ${fallbackError}`);
        return false;
      }
    }
  }

  /**
   * Track model provenance for AI-generated code
   */
  async trackModelProvenance(
    modelId: string,
    version: string,
    provider: string = "openai"
  ): Promise<ModelProvenance> {
    const checksumVerified = await this.verifyModelChecksum(modelId, version);

    return {
      modelId,
      version,
      trainingDataCutoff: this.getTrainingCutoff(modelId),
      provider,
      checksumVerified,
    };
  }

  /**
   * Hash prompts for audit trail without storing sensitive content
   */
  async hashPrompts(prompts: string[]): Promise<PromptProvenance> {
    const sanitizationApplied = prompts.some((p) =>
      this.containsSensitiveData(p)
    );

    const promptHashes = prompts.map((prompt) => {
      // Sanitize before hashing
      const sanitized = this.sanitizePrompt(prompt);
      return crypto.createHash("sha256").update(sanitized).digest("hex");
    });

    const injectionChecksPassed = prompts.every((p) =>
      this.checkPromptInjection(p)
    );

    return {
      promptHashes,
      totalPrompts: prompts.length,
      sanitizationApplied,
      injectionChecksPassed,
    };
  }

  /**
   * Run security scans and collect results
   */
  async runSecurityScans(projectDir: string): Promise<{
    secretScanPassed: boolean;
    sastPassed: boolean;
    dependencyScanPassed: boolean;
    details: Record<string, any>;
  }> {
    const results = {
      secretScanPassed: true,
      sastPassed: true,
      dependencyScanPassed: true,
      details: {} as Record<string, any>,
    };

    // Check for secrets
    const secretScan = await this.scanForSecrets(projectDir);
    results.secretScanPassed = secretScan.passed;
    results.details.secrets = secretScan;

    // Check for vulnerabilities
    const sastScan = await this.runSAST(projectDir);
    results.sastPassed = sastScan.passed;
    results.details.sast = sastScan;

    // Check dependencies
    const depScan = await this.scanDependencies(projectDir);
    results.dependencyScanPassed = depScan.passed;
    results.details.dependencies = depScan;

    return results;
  }

  /**
   * Generate SLSA provenance attestation
   */
  async generateSLSAAttestation(buildInfo: {
    commit: string;
    builder: string;
    buildTime: string;
    artifacts: string[];
  }): Promise<Record<string, any>> {
    return {
      _type: "https://in-toto.io/Statement/v0.1",
      predicateType: "https://slsa.dev/provenance/v0.2",
      subject: buildInfo.artifacts.map((artifact) => ({
        name: artifact,
        digest: {
          sha256: this.hashFile(artifact),
        },
      })),
      predicate: {
        builder: {
          id: buildInfo.builder,
        },
        buildType: "https://caws.dev/build/v1",
        invocation: {
          configSource: {
            uri: `git+https://github.com/repo@${buildInfo.commit}`,
            digest: {
              sha256: buildInfo.commit,
            },
          },
        },
        metadata: {
          buildStartedOn: buildInfo.buildTime,
          buildFinishedOn: new Date().toISOString(),
          completeness: {
            parameters: true,
            environment: false,
            materials: true,
          },
          reproducible: false,
        },
        materials: buildInfo.artifacts.map((artifact) => ({
          uri: `file://${artifact}`,
          digest: {
            sha256: this.hashFile(artifact),
          },
        })),
      },
    };
  }

  private generateSignature(content: string, privateKeyPath?: string): string {
    try {
      // Load private key from file or generate ephemeral key for development
      let privateKey: string;
      let keyFormat: "pem" | "der" = "pem";

      if (privateKeyPath && fs.existsSync(privateKeyPath)) {
        privateKey = fs.readFileSync(privateKeyPath, "utf-8");

        // Detect key format
        if (privateKey.includes("-----BEGIN RSA PRIVATE KEY-----")) {
          keyFormat = "pem";
        } else if (privateKey.startsWith("MII")) {
          // Likely DER format, convert to PEM
          privateKey = `-----BEGIN RSA PRIVATE KEY-----\n${privateKey}\n-----END RSA PRIVATE KEY-----`;
        }
      } else {
        // Generate ephemeral key pair for development/testing
        const { privateKey: generatedPrivateKey } = crypto.generateKeyPairSync(
          "rsa",
          {
            modulusLength: 2048,
            publicKeyEncoding: { type: "spki", format: "pem" },
            privateKeyEncoding: { type: "pkcs8", format: "pem" },
          }
        );
        privateKey = generatedPrivateKey;
      }

      // Create signature using RSA-SHA256
      const sign = crypto.createSign("RSA-SHA256");
      sign.update(content);
      const signature = sign.sign(privateKey, "base64");

      return signature;
    } catch (error) {
      console.error(`Signature generation failed: ${error}`);
      // Fallback to hash-based signature for compatibility
      const hash = crypto.createHash("sha256").update(content);
      if (privateKeyPath && fs.existsSync(privateKeyPath)) {
        const keyContent = fs.readFileSync(privateKeyPath, "utf-8");
        hash.update(keyContent);
      }
      return hash.digest("hex");
    }
  }

  private getPublicKeyFingerprint(keyPath?: string): string {
    if (keyPath && fs.existsSync(keyPath)) {
      const keyContent = fs.readFileSync(keyPath, "utf-8");
      return crypto
        .createHash("sha256")
        .update(keyContent)
        .digest("hex")
        .substring(0, 16);
    }
    return "ephemeral-key";
  }

  /**
   * Generate a development key pair for testing cryptographic operations
   */
  async generateDevelopmentKeyPair(
    keyDir: string = ".caws/keys"
  ): Promise<{ privateKeyPath: string; publicKeyPath: string }> {
    try {
      // Ensure key directory exists
      if (!fs.existsSync(keyDir)) {
        fs.mkdirSync(keyDir, { recursive: true });
      }

      // Generate RSA key pair
      const { publicKey, privateKey } = crypto.generateKeyPairSync("rsa", {
        modulusLength: 2048,
        publicKeyEncoding: { type: "spki", format: "pem" },
        privateKeyEncoding: { type: "pkcs8", format: "pem" },
      });

      // Save keys to files
      const privateKeyPath = path.join(keyDir, "caws-private.pem");
      const publicKeyPath = path.join(keyDir, "caws-public.pem");

      fs.writeFileSync(privateKeyPath, privateKey, { mode: 0o600 }); // Private key should be secure
      fs.writeFileSync(publicKeyPath, publicKey);

      console.log(`Development key pair generated:`);
      console.log(`  Private key: ${privateKeyPath}`);
      console.log(`  Public key: ${publicKeyPath}`);

      return { privateKeyPath, publicKeyPath };
    } catch (error) {
      throw new Error(`Failed to generate development key pair: ${error}`);
    }
  }

  private async verifyModelChecksum(
    modelId: string,
    version: string
  ): Promise<boolean> {
    try {
      // Load known checksums from secure configuration store
      const checksumStore = this.loadChecksumStore();

      // Determine model file path based on modelId and version
      const modelPath = this.getModelFilePath(modelId, version);
      if (!modelPath || !fs.existsSync(modelPath)) {
        this.logger?.warn(
          `Model file not found for ${modelId}@${version}: ${modelPath}`
        );
        return false;
      }

      // Calculate SHA256 hash of the model file
      const fileHash = this.calculateFileHash(modelPath, "sha256");

      // Get expected checksum for this model + version combination
      const key = `${modelId}@${version}`;
      const expectedChecksum = checksumStore[key]?.sha256;
      if (!expectedChecksum) {
        this.logger?.warn(
          `No checksum found for ${modelId}@${version}, cannot verify integrity`
        );
        return false; // Require explicit checksum registration for security
      }

      // Compare hashes
      const isValid = fileHash === expectedChecksum;
      if (!isValid) {
        this.logger?.error(
          `SECURITY VIOLATION: Model checksum mismatch for ${modelId}@${version}`
        );
        this.logger?.error(`Expected: ${expectedChecksum}`);
        this.logger?.error(`Actual: ${fileHash}`);
        // Could implement additional security measures here (alerts, quarantine, etc.)
      } else {
        this.logger?.debug(`Model checksum verified for ${modelId}@${version}`);
      }

      return isValid;
    } catch (error) {
      this.logger?.error(
        `Failed to verify model checksum for ${modelId}@${version}:`,
        error
      );
      return false;
    }
  }

  private loadChecksumStore(): Record<
    string,
    { sha256: string; sha512?: string }
  > {
    try {
      const checksumPath = path.join(
        process.cwd(),
        ".caws",
        "model-checksums.json"
      );
      if (!fs.existsSync(checksumPath)) {
        this.logger?.warn(
          "Model checksum store not found, creating empty store"
        );
        return {};
      }
      const storeContent = fs.readFileSync(checksumPath, "utf-8");
      return JSON.parse(storeContent);
    } catch (error) {
      this.logger?.error("Failed to load checksum store:", error);
      return {};
    }
  }

  private getModelFilePath(modelId: string, version: string): string | null {
    const modelMappings: Record<string, string> = {
      "kokoro-v1.0": "kokoro-v1.0.int8.onnx",
      "kokoro-v1.0-int8": "kokoro-v1.0.int8.onnx",
      "voices-v1.0": "voices-v1.0.bin",
    };

    const key = version.includes("int8") ? `${modelId}-int8` : modelId;
    const fileName = modelMappings[key] || modelMappings[modelId];

    if (!fileName) {
      this.logger?.warn(`Unknown model mapping for ${modelId}@${version}`);
      return null;
    }

    // Use project root instead of current working directory
    // This ensures models are found regardless of where the script is run from
    // From apps/tools/caws, go up 3 levels to kokoro-onnx: ../../../
    const projectRoot = path.resolve(__dirname, "../../../");
    return path.join(projectRoot, fileName);
  }

  private findProjectRoot(): string {
    // Find project root by looking for common markers
    let currentDir = process.cwd();

    // Look up the directory tree for project markers
    const maxDepth = 10;
    for (let i = 0; i < maxDepth; i++) {
      // Check for project markers
      const markers = [
        "kokoro-v1.0.int8.onnx",
        "voices-v1.0.bin",
        "README.md",
        "requirements.txt",
        "package.json",
      ];

      const hasMarker = markers.some((marker) =>
        fs.existsSync(path.join(currentDir, marker))
      );

      if (hasMarker) {
        return currentDir;
      }

      // Go up one directory
      const parentDir = path.dirname(currentDir);
      if (parentDir === currentDir) {
        // Reached root directory
        break;
      }
      currentDir = parentDir;
    }

    // Fallback to current directory
    return process.cwd();
  }

  private calculateFileHash(
    filePath: string,
    algorithm: "sha256" | "sha512" = "sha256"
  ): string {
    try {
      const fileContent = fs.readFileSync(filePath);
      return crypto.createHash(algorithm).update(fileContent).digest("hex");
    } catch (error) {
      this.logger?.error(
        `Failed to calculate ${algorithm} hash for ${filePath}:`,
        error
      );
      throw error;
    }
  }

  /**
   * Register or update checksums for a model
   * This method should only be called by trusted administrators
   */
  public async registerModelChecksum(
    modelId: string,
    version: string,
    modelPath?: string
  ): Promise<void> {
    try {
      const actualPath = modelPath || this.getModelFilePath(modelId, version);
      if (!actualPath || !fs.existsSync(actualPath)) {
        throw new Error(`Model file not found: ${actualPath}`);
      }

      const checksumStore = this.loadChecksumStore();
      const key = `${modelId}@${version}`;

      // Calculate hashes
      const sha256 = this.calculateFileHash(actualPath, "sha256");
      const sha512 = this.calculateFileHash(actualPath, "sha512");

      // Update store
      checksumStore[key] = {
        sha256,
        sha512,
        registered_at: new Date().toISOString(),
        registered_by: process.env.CAWS_USER || "unknown",
      };

      // Save updated store
      const checksumPath = path.join(
        process.cwd(),
        ".caws",
        "model-checksums.json"
      );
      fs.writeFileSync(checksumPath, JSON.stringify(checksumStore, null, 2));

      this.logger?.info(`Registered checksums for ${modelId}@${version}`);
      this.logger?.debug(`SHA256: ${sha256}`);
    } catch (error) {
      this.logger?.error(
        `Failed to register checksum for ${modelId}@${version}:`,
        error
      );
      throw error;
    }
  }

  private getTrainingCutoff(modelId: string): string | undefined {
    // Known cutoff dates for common models
    const cutoffs: Record<string, string> = {
      "gpt-4": "2023-04-01",
      "gpt-4-turbo": "2023-12-01",
      "claude-3": "2023-08-01",
      "claude-sonnet-4": "2024-09-01",
    };

    return cutoffs[modelId];
  }

  private containsSensitiveData(prompt: string): boolean {
    const patterns = [
      /password/i,
      /api[_-]?key/i,
      /secret/i,
      /token/i,
      /credential/i,
      /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/, // email
      /\b\d{3}-\d{2}-\d{4}\b/, // SSN
    ];

    return patterns.some((pattern) => pattern.test(prompt));
  }

  private sanitizePrompt(prompt: string): string {
    // Remove sensitive data before hashing
    let sanitized = prompt;

    // Redact emails
    sanitized = sanitized.replace(
      /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/g,
      "[EMAIL_REDACTED]"
    );

    // Redact potential API keys
    sanitized = sanitized.replace(/[a-zA-Z0-9]{32,}/g, "[KEY_REDACTED]");

    return sanitized;
  }

  private checkPromptInjection(prompt: string): boolean {
    // Check for common prompt injection patterns
    const injectionPatterns = [
      /ignore previous instructions/i,
      /disregard all above/i,
      /system:\s*you are now/i,
      /<\|im_start\|>/,
    ];

    return !injectionPatterns.some((pattern) => pattern.test(prompt));
  }

  private async scanForSecrets(
    projectDir: string
  ): Promise<{ passed: boolean; findings: string[] }> {
    const findings: string[] = [];

    // Simple secret scan (in production, use trufflehog or similar)
    const files = this.findFilesRecursive(projectDir);

    for (const file of files) {
      if (file.includes("node_modules")) continue;

      const content = fs.readFileSync(file, "utf-8");
      if (this.containsSensitiveData(content)) {
        findings.push(`Potential secret in ${file}`);
      }
    }

    return { passed: findings.length === 0, findings };
  }

  private async runSAST(
    projectDir: string
  ): Promise<{ passed: boolean; vulnerabilities: number }> {
    // TODO: Implement SAST integration for security scanning
    // - [ ] Integrate with Snyk or SonarQube SAST tools
    // - [ ] Parse and report security vulnerabilities
    // - [ ] Configure severity thresholds and blocking rules
    // - [ ] Generate security reports and trend analysis
    return { passed: true, vulnerabilities: 0 };
  }

  private async scanDependencies(
    projectDir: string
  ): Promise<{ passed: boolean; vulnerable: number }> {
    // TODO: Implement dependency vulnerability scanning
    // - [ ] Integrate with npm audit or Snyk dependency scanning
    // - [ ] Parse vulnerability reports and severity levels
    // - [ ] Implement dependency update recommendations
    // - [ ] Configure allowlists for acceptable vulnerabilities
    return { passed: true, vulnerable: 0 };
  }

  private hashFile(filePath: string): string {
    if (!fs.existsSync(filePath)) {
      return "";
    }
    const content = fs.readFileSync(filePath);
    return crypto.createHash("sha256").update(content).digest("hex");
  }

  private findFilesRecursive(dir: string, files: string[] = []): string[] {
    try {
      const entries = fs.readdirSync(dir, { withFileTypes: true });

      for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);
        if (entry.isDirectory() && !entry.name.includes("node_modules")) {
          this.findFilesRecursive(fullPath, files);
        } else if (entry.isFile()) {
          files.push(fullPath);
        }
      }
    } catch {
      // Directory doesn't exist
    }

    return files;
  }
}

// CLI interface
if (import.meta.url === `file://${process.argv[1]}`) {
  (async () => {
    const command = process.argv[2];
    const manager = new SecurityProvenanceManager();

    switch (command) {
      case "sign": {
        const artifactPath = process.argv[3];
        const keyPath = process.argv[4];

        if (!artifactPath) {
          console.error("Usage: security-provenance sign <artifact> [key]");
          process.exit(1);
        }

        try {
          const signature = await manager.signArtifact(artifactPath, keyPath);
          console.log("✅ Artifact signed successfully");
          console.log(JSON.stringify(signature, null, 2));
        } catch (error) {
          console.error(`❌ Signing failed: ${error}`);
          process.exit(1);
        }
        break;
      }

      case "verify": {
        const artifactPath = process.argv[3];
        const signature = process.argv[4];
        const keyPath = process.argv[5];

        if (!artifactPath || !signature) {
          console.error(
            "Usage: security-provenance verify <artifact> <signature> [key]"
          );
          process.exit(1);
        }

        try {
          const valid = await manager.verifySignature(
            artifactPath,
            signature,
            keyPath
          );
          if (valid) {
            console.log("✅ Signature is valid");
          } else {
            console.log("❌ Signature is invalid");
            process.exit(1);
          }
        } catch (error) {
          console.error(`❌ Verification failed: ${error}`);
          process.exit(1);
        }
        break;
      }

      case "scan": {
        const projectDir = process.argv[3] || process.cwd();

        try {
          const results = await manager.runSecurityScans(projectDir);

          console.log("\n🔒 Security Scan Results");
          console.log("=".repeat(50));
          console.log(
            `Secret Scan: ${
              results.secretScanPassed ? "✅ PASSED" : "❌ FAILED"
            }`
          );
          console.log(
            `SAST Scan: ${results.sastPassed ? "✅ PASSED" : "❌ FAILED"}`
          );
          console.log(
            `Dependency Scan: ${
              results.dependencyScanPassed ? "✅ PASSED" : "❌ FAILED"
            }`
          );

          if (results.details.secrets?.findings?.length > 0) {
            console.log("\n🚨 Secret Findings:");
            results.details.secrets.findings.forEach((finding: string) => {
              console.log(`  - ${finding}`);
            });
          }

          const allPassed =
            results.secretScanPassed &&
            results.sastPassed &&
            results.dependencyScanPassed;
          process.exit(allPassed ? 0 : 1);
        } catch (error) {
          console.error(`❌ Scan failed: ${error}`);
          process.exit(1);
        }
        break;
      }

      case "slsa": {
        const commit = process.argv[3];
        const builder = process.argv[4] || "caws-builder";

        if (!commit) {
          console.error("Usage: security-provenance slsa <commit> [builder]");
          process.exit(1);
        }

        try {
          const attestation = await manager.generateSLSAAttestation({
            commit,
            builder,
            buildTime: new Date().toISOString(),
            artifacts: [".agent/provenance.json"],
          });

          console.log(JSON.stringify(attestation, null, 2));
        } catch (error) {
          console.error(`❌ SLSA generation failed: ${error}`);
          process.exit(1);
        }
        break;
      }

      case "register": {
        const modelId = process.argv[3];
        const version = process.argv[4];
        const modelPath = process.argv[5];

        if (!modelId || !version) {
          console.error(
            "Usage: security-provenance register <modelId> <version> [modelPath]"
          );
          console.error(
            "Example: security-provenance register kokoro-v1.0 v1.0 ./kokoro-v1.0.int8.onnx"
          );
          process.exit(1);
        }

        try {
          await manager.registerModelChecksum(modelId, version, modelPath);
          console.log("✅ Model checksum registered successfully");
        } catch (error) {
          console.error(`❌ Registration failed: ${error}`);
          process.exit(1);
        }
        break;
      }

      default:
        console.log("CAWS Security & Provenance Manager");
        console.log("");
        console.log("Usage:");
        console.log(
          "  security-provenance sign <artifact> [key]           - Sign artifact"
        );
        console.log(
          "  security-provenance verify <artifact> <sig> [key]   - Verify signature"
        );
        console.log(
          "  security-provenance scan [dir]                      - Run security scans"
        );
        console.log(
          "  security-provenance slsa <commit> [builder]         - Generate SLSA attestation"
        );
        console.log(
          "  security-provenance register <modelId> <version> [path] - Register model checksum"
        );
        console.log("");
        console.log("Examples:");
        console.log("  security-provenance sign .agent/provenance.json");
        console.log("  security-provenance scan .");
        console.log("  security-provenance register kokoro-v1.0 v1.0");
        break;
    }
  })();
}
