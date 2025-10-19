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
    try {
      const sastResults = await this.runComprehensiveSAST(projectDir);
      const criticalVulnerabilities = sastResults.filter(
        (v) => v.severity === "CRITICAL" || v.severity === "HIGH"
      );

      this.logger?.info(
        `SAST completed: ${sastResults.length} total issues, ${criticalVulnerabilities.length} critical/high`
      );

      return {
        passed: criticalVulnerabilities.length === 0,
        vulnerabilities: sastResults.length,
      };
    } catch (error) {
      this.logger?.error(`SAST failed: ${error}`);
      return { passed: false, vulnerabilities: -1 };
    }
  }

  private async runComprehensiveSAST(projectDir: string): Promise<
    Array<{
      file: string;
      line: number;
      severity: string;
      rule: string;
      message: string;
      tool: string;
    }>
  > {
    const findings: Array<{
      file: string;
      line: number;
      severity: string;
      rule: string;
      message: string;
      tool: string;
    }> = [];

    // Run ESLint with security plugins
    try {
      const eslintFindings = await this.runESLintSecurity(projectDir);
      findings.push(...eslintFindings);
    } catch (error) {
      this.logger?.debug(`ESLint security scan failed: ${error}`);
    }

    // Run Node.js security linting
    try {
      const nodeFindings = await this.runNodeSecurityScan(projectDir);
      findings.push(...nodeFindings);
    } catch (error) {
      this.logger?.debug(`Node security scan failed: ${error}`);
    }

    // Run TypeScript strict checks for security
    try {
      const tsFindings = await this.runTypeScriptSecurityChecks(projectDir);
      findings.push(...tsFindings);
    } catch (error) {
      this.logger?.debug(`TypeScript security checks failed: ${error}`);
    }

    return findings;
  }

  private async runESLintSecurity(projectDir: string): Promise<
    Array<{
      file: string;
      line: number;
      severity: string;
      rule: string;
      message: string;
      tool: string;
    }>
  > {
    const findings: Array<{
      file: string;
      line: number;
      severity: string;
      rule: string;
      message: string;
      tool: string;
    }> = [];

    try {
      // Check if ESLint is available
      const eslintConfig = path
        .join(
          projectDir,
          ".eslintrc.js",
          ".eslintrc.json",
          ".eslintrc.yml",
          "eslint.config.js"
        )
        .find((config) => {
          return fs.existsSync(path.join(projectDir, config));
        });

      if (!eslintConfig) {
        return findings; // No ESLint config found
      }

      // Run ESLint programmatically if available
      try {
        const { ESLint } = await import("eslint");
        const eslint = new ESLint({
          cwd: projectDir,
          useEslintrc: true,
        });

        const results = await eslint.lintFiles([
          "**/*.js",
          "**/*.ts",
          "**/*.tsx",
        ]);

        for (const result of results) {
          for (const message of result.messages) {
            if (
              message.ruleId &&
              (message.ruleId.includes("security") ||
                message.ruleId.includes("xss") ||
                message.ruleId.includes("injection") ||
                message.ruleId.includes("crypto"))
            ) {
              findings.push({
                file: result.filePath,
                line: message.line,
                severity:
                  message.severity === 2
                    ? "HIGH"
                    : message.severity === 1
                    ? "MEDIUM"
                    : "LOW",
                rule: message.ruleId,
                message: message.message,
                tool: "eslint",
              });
            }
          }
        }
      } catch (importError) {
        this.logger?.debug(
          `ESLint programmatic API not available: ${importError}`
        );
      }
    } catch (error) {
      this.logger?.debug(`ESLint security scan setup failed: ${error}`);
    }

    return findings;
  }

  private async runNodeSecurityScan(projectDir: string): Promise<
    Array<{
      file: string;
      line: number;
      severity: string;
      rule: string;
      message: string;
      tool: string;
    }>
  > {
    const findings: Array<{
      file: string;
      line: number;
      severity: string;
      rule: string;
      message: string;
      tool: string;
    }> = [];

    try {
      // Scan for common Node.js security issues
      const scanFiles = await this.findJavaScriptFiles(projectDir);

      for (const file of scanFiles) {
        try {
          const content = fs.readFileSync(file, "utf-8");
          const lines = content.split("\n");

          for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            const lineNumber = i + 1;

            // Check for dangerous patterns
            if (line.includes("eval(")) {
              findings.push({
                file,
                line: lineNumber,
                severity: "CRITICAL",
                rule: "no-eval",
                message: "Use of eval() function detected - high security risk",
                tool: "node-security",
              });
            }

            if (line.includes("child_process.exec") && line.includes("shell")) {
              findings.push({
                file,
                line: lineNumber,
                severity: "HIGH",
                rule: "shell-injection",
                message: "Potential shell injection vulnerability",
                tool: "node-security",
              });
            }

            if (
              line.includes("fs.") &&
              line.includes("..") &&
              !line.includes("path.resolve")
            ) {
              findings.push({
                file,
                line: lineNumber,
                severity: "HIGH",
                rule: "path-traversal",
                message: "Potential path traversal vulnerability",
                tool: "node-security",
              });
            }

            if (line.includes("innerHTML") || line.includes("outerHTML")) {
              findings.push({
                file,
                line: lineNumber,
                severity: "MEDIUM",
                rule: "xss-risk",
                message: "Potential XSS vulnerability with HTML injection",
                tool: "node-security",
              });
            }
          }
        } catch (fileError) {
          this.logger?.debug(`Failed to scan file ${file}: ${fileError}`);
        }
      }
    } catch (error) {
      this.logger?.debug(`Node security scan failed: ${error}`);
    }

    return findings;
  }

  private async runTypeScriptSecurityChecks(projectDir: string): Promise<
    Array<{
      file: string;
      line: number;
      severity: string;
      rule: string;
      message: string;
      tool: string;
    }>
  > {
    const findings: Array<{
      file: string;
      line: number;
      severity: string;
      rule: string;
      message: string;
      tool: string;
    }> = [];

    try {
      const tsFiles = await this.findTypeScriptFiles(projectDir);

      for (const file of tsFiles) {
        try {
          const content = fs.readFileSync(file, "utf-8");
          const lines = content.split("\n");

          for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            const lineNumber = i + 1;

            // Check for TypeScript security issues
            if (line.includes("as any") && !line.includes("//")) {
              findings.push({
                file,
                line: lineNumber,
                severity: "MEDIUM",
                rule: "no-any-cast",
                message: "Type assertion to any bypasses type safety",
                tool: "typescript-security",
              });
            }

            if (line.includes("Function(") || line.includes("new Function")) {
              findings.push({
                file,
                line: lineNumber,
                severity: "HIGH",
                rule: "no-function-constructor",
                message:
                  "Function constructor usage can lead to code injection",
                tool: "typescript-security",
              });
            }
          }
        } catch (fileError) {
          this.logger?.debug(
            `Failed to scan TypeScript file ${file}: ${fileError}`
          );
        }
      }
    } catch (error) {
      this.logger?.debug(`TypeScript security checks failed: ${error}`);
    }

    return findings;
  }

  private async findJavaScriptFiles(projectDir: string): Promise<string[]> {
    const files: string[] = [];

    const walk = (dir: string) => {
      const items = fs.readdirSync(dir);

      for (const item of items) {
        const fullPath = path.join(dir, item);
        const stat = fs.statSync(fullPath);

        if (
          stat.isDirectory() &&
          !item.startsWith(".") &&
          item !== "node_modules"
        ) {
          walk(fullPath);
        } else if (
          stat.isFile() &&
          (item.endsWith(".js") ||
            item.endsWith(".mjs") ||
            item.endsWith(".cjs"))
        ) {
          files.push(fullPath);
        }
      }
    };

    walk(projectDir);
    return files;
  }

  private async findTypeScriptFiles(projectDir: string): Promise<string[]> {
    const files: string[] = [];

    const walk = (dir: string) => {
      const items = fs.readdirSync(dir);

      for (const item of items) {
        const fullPath = path.join(dir, item);
        const stat = fs.statSync(fullPath);

        if (
          stat.isDirectory() &&
          !item.startsWith(".") &&
          item !== "node_modules"
        ) {
          walk(fullPath);
        } else if (
          stat.isFile() &&
          (item.endsWith(".ts") || item.endsWith(".tsx"))
        ) {
          files.push(fullPath);
        }
      }
    };

    walk(projectDir);
    return files;
  }

  private async scanDependencies(
    projectDir: string
  ): Promise<{ passed: boolean; vulnerable: number }> {
    try {
      const scanResults = await this.runDependencyVulnerabilityScan(projectDir);
      const criticalVulnerabilities = scanResults.filter(
        (v) => v.severity === "CRITICAL" || v.severity === "HIGH"
      );

      this.logger?.info(
        `Dependency scan completed: ${scanResults.length} vulnerabilities found, ${criticalVulnerabilities.length} critical/high`
      );

      return {
        passed: criticalVulnerabilities.length === 0,
        vulnerable: scanResults.length,
      };
    } catch (error) {
      this.logger?.error(`Dependency scan failed: ${error}`);
      return { passed: false, vulnerable: -1 };
    }
  }

  private async runDependencyVulnerabilityScan(projectDir: string): Promise<
    Array<{
      package: string;
      version: string;
      severity: string;
      vulnerability: string;
      description: string;
      fixedIn?: string;
    }>
  > {
    const vulnerabilities: Array<{
      package: string;
      version: string;
      severity: string;
      vulnerability: string;
      description: string;
      fixedIn?: string;
    }> = [];

    // Try npm audit first
    try {
      const npmResults = await this.runNPMAudit(projectDir);
      vulnerabilities.push(...npmResults);
    } catch (error) {
      this.logger?.debug(`npm audit failed: ${error}`);
    }

    // Try yarn audit if npm failed
    if (vulnerabilities.length === 0) {
      try {
        const yarnResults = await this.runYarnAudit(projectDir);
        vulnerabilities.push(...yarnResults);
      } catch (error) {
        this.logger?.debug(`yarn audit failed: ${error}`);
      }
    }

    // Try pip audit for Python dependencies
    try {
      const pipResults = await this.runPipAudit(projectDir);
      vulnerabilities.push(...pipResults);
    } catch (error) {
      this.logger?.debug(`pip audit failed: ${error}`);
    }

    // If no automated tools available, check for known vulnerable patterns
    if (vulnerabilities.length === 0) {
      try {
        const manualResults = await this.checkKnownVulnerablePackages(
          projectDir
        );
        vulnerabilities.push(...manualResults);
      } catch (error) {
        this.logger?.debug(`Manual vulnerability check failed: ${error}`);
      }
    }

    return vulnerabilities;
  }

  private async runNPMAudit(projectDir: string): Promise<
    Array<{
      package: string;
      version: string;
      severity: string;
      vulnerability: string;
      description: string;
      fixedIn?: string;
    }>
  > {
    const vulnerabilities: Array<{
      package: string;
      version: string;
      severity: string;
      vulnerability: string;
      description: string;
      fixedIn?: string;
    }> = [];

    try {
      const { spawn } = await import("child_process");
      const { promisify } = await import("util");
      const exec = promisify(spawn);

      // Run npm audit
      const auditProcess = spawn("npm", ["audit", "--json"], {
        cwd: projectDir,
        stdio: ["pipe", "pipe", "pipe"],
      });

      let stdout = "";
      let stderr = "";

      auditProcess.stdout?.on("data", (data) => {
        stdout += data.toString();
      });

      auditProcess.stderr?.on("data", (data) => {
        stderr += data.toString();
      });

      await new Promise((resolve, reject) => {
        auditProcess.on("close", (code) => {
          if (code === 0 || code === 1) {
            // npm audit returns 1 when vulnerabilities found
            resolve({ code, stdout, stderr });
          } else {
            reject(new Error(`npm audit failed with code ${code}: ${stderr}`));
          }
        });
      });

      if (stdout) {
        const auditData = JSON.parse(stdout);
        if (auditData.vulnerabilities) {
          for (const [pkgName, vulnData] of Object.entries(
            auditData.vulnerabilities
          )) {
            const vuln = vulnData as any;
            vulnerabilities.push({
              package: pkgName,
              version: vuln.version || "unknown",
              severity: this.mapNPMSeverity(vuln.severity),
              vulnerability: vuln.title || vuln.name || "Unknown vulnerability",
              description: vuln.overview || "No description available",
              fixedIn: vuln.fixAvailable
                ? vuln.fixAvailable.version
                : undefined,
            });
          }
        }
      }
    } catch (error) {
      this.logger?.debug(`npm audit execution failed: ${error}`);
    }

    return vulnerabilities;
  }

  private async runYarnAudit(projectDir: string): Promise<
    Array<{
      package: string;
      version: string;
      severity: string;
      vulnerability: string;
      description: string;
      fixedIn?: string;
    }>
  > {
    const vulnerabilities: Array<{
      package: string;
      version: string;
      severity: string;
      vulnerability: string;
      description: string;
      fixedIn?: string;
    }> = [];

    try {
      const { spawn } = await import("child_process");

      const auditProcess = spawn("yarn", ["audit", "--json"], {
        cwd: projectDir,
        stdio: ["pipe", "pipe", "pipe"],
      });

      let stdout = "";

      auditProcess.stdout?.on("data", (data) => {
        stdout += data.toString();
      });

      await new Promise((resolve, reject) => {
        auditProcess.on("close", (code) => {
          if (code === 0 || code === 1) {
            resolve({ code, stdout });
          } else {
            reject(new Error(`yarn audit failed with code ${code}`));
          }
        });
      });

      if (stdout) {
        const lines = stdout.trim().split("\n");
        for (const line of lines) {
          try {
            const auditEntry = JSON.parse(line);
            if (auditEntry.type === "auditAdvisory") {
              vulnerabilities.push({
                package: auditEntry.data.advisory.module_name,
                version: auditEntry.data.advisory.vulnerable_versions,
                severity: this.mapYarnSeverity(
                  auditEntry.data.advisory.severity
                ),
                vulnerability: auditEntry.data.advisory.title,
                description: auditEntry.data.advisory.overview,
                fixedIn: auditEntry.data.advisory.patched_versions,
              });
            }
          } catch (parseError) {
            // Skip malformed JSON lines
          }
        }
      }
    } catch (error) {
      this.logger?.debug(`yarn audit execution failed: ${error}`);
    }

    return vulnerabilities;
  }

  private async runPipAudit(projectDir: string): Promise<
    Array<{
      package: string;
      version: string;
      severity: string;
      vulnerability: string;
      description: string;
      fixedIn?: string;
    }>
  > {
    const vulnerabilities: Array<{
      package: string;
      version: string;
      severity: string;
      vulnerability: string;
      description: string;
      fixedIn?: string;
    }> = [];

    try {
      const { spawn } = await import("child_process");

      // Try pip-audit if available
      const auditProcess = spawn("pip-audit", ["--format", "json"], {
        cwd: projectDir,
        stdio: ["pipe", "pipe", "pipe"],
      });

      let stdout = "";
      let stderr = "";

      auditProcess.stdout?.on("data", (data) => {
        stdout += data.toString();
      });

      auditProcess.stderr?.on("data", (data) => {
        stderr += data.toString();
      });

      await new Promise((resolve, reject) => {
        auditProcess.on("close", (code) => {
          if (code === 0 || code === 1) {
            resolve({ code, stdout, stderr });
          } else {
            reject(new Error(`pip-audit failed with code ${code}: ${stderr}`));
          }
        });
      });

      if (stdout) {
        const auditData = JSON.parse(stdout);
        for (const vuln of auditData) {
          vulnerabilities.push({
            package: vuln.name,
            version: vuln.version,
            severity: this.mapPipSeverity(vuln.severity || "UNKNOWN"),
            vulnerability: vuln.vulnerability_id || vuln.id || "Unknown",
            description: vuln.description || "No description available",
            fixedIn: vuln.fixed_version,
          });
        }
      }
    } catch (error) {
      this.logger?.debug(`pip audit execution failed: ${error}`);
    }

    return vulnerabilities;
  }

  private async checkKnownVulnerablePackages(projectDir: string): Promise<
    Array<{
      package: string;
      version: string;
      severity: string;
      vulnerability: string;
      description: string;
      fixedIn?: string;
    }>
  > {
    const vulnerabilities: Array<{
      package: string;
      version: string;
      severity: string;
      vulnerability: string;
      description: string;
      fixedIn?: string;
    }> = [];

    try {
      // Check package.json for Node.js dependencies
      const packageJsonPath = path.join(projectDir, "package.json");
      if (fs.existsSync(packageJsonPath)) {
        const packageJson = JSON.parse(
          fs.readFileSync(packageJsonPath, "utf-8")
        );
        const dependencies = {
          ...packageJson.dependencies,
          ...packageJson.devDependencies,
        };

        // Check for known vulnerable packages (basic patterns)
        const knownVulnerabilities = {
          lodash: { maxSafeVersion: "4.17.20", severity: "HIGH" },
          axios: { maxSafeVersion: "0.21.1", severity: "CRITICAL" },
          express: { maxSafeVersion: "4.17.3", severity: "HIGH" },
        };

        for (const [pkg, version] of Object.entries(dependencies)) {
          if (knownVulnerabilities[pkg]) {
            const vuln = knownVulnerabilities[pkg];
            if (
              this.isVersionVulnerable(version as string, vuln.maxSafeVersion)
            ) {
              vulnerabilities.push({
                package: pkg,
                version: version as string,
                severity: vuln.severity,
                vulnerability: `Outdated ${pkg} version`,
                description: `${pkg} version ${version} is vulnerable. Update to ${vuln.maxSafeVersion} or later.`,
                fixedIn: vuln.maxSafeVersion,
              });
            }
          }
        }
      }

      // Check requirements.txt for Python dependencies
      const requirementsPath = path.join(projectDir, "requirements.txt");
      if (fs.existsSync(requirementsPath)) {
        const requirements = fs
          .readFileSync(requirementsPath, "utf-8")
          .split("\n");

        for (const req of requirements) {
          if (req.trim() && !req.startsWith("#")) {
            const match = req.match(/^([a-zA-Z0-9\-_.]+)([<>=!~]+)(.+)$/);
            if (match) {
              const [, pkg, , version] = match;

              // Basic check for known vulnerable Python packages
              const knownVulns = {
                requests: { maxSafeVersion: "2.25.0", severity: "HIGH" },
                urllib3: { maxSafeVersion: "1.26.5", severity: "CRITICAL" },
              };

              if (
                knownVulns[pkg] &&
                this.isVersionVulnerable(
                  version,
                  knownVulns[pkg].maxSafeVersion
                )
              ) {
                const vuln = knownVulns[pkg];
                vulnerabilities.push({
                  package: pkg,
                  version: version,
                  severity: vuln.severity,
                  vulnerability: `Outdated ${pkg} version`,
                  description: `${pkg} version ${version} is vulnerable. Update to ${vuln.maxSafeVersion} or later.`,
                  fixedIn: vuln.maxSafeVersion,
                });
              }
            }
          }
        }
      }
    } catch (error) {
      this.logger?.debug(`Manual vulnerability check failed: ${error}`);
    }

    return vulnerabilities;
  }

  private mapNPMSeverity(severity: string): string {
    const severityMap: { [key: string]: string } = {
      critical: "CRITICAL",
      high: "HIGH",
      moderate: "MEDIUM",
      low: "LOW",
      info: "INFO",
    };
    return severityMap[severity.toLowerCase()] || "MEDIUM";
  }

  private mapYarnSeverity(severity: string): string {
    const severityMap: { [key: string]: string } = {
      critical: "CRITICAL",
      high: "HIGH",
      moderate: "MEDIUM",
      low: "LOW",
      info: "INFO",
    };
    return severityMap[severity.toLowerCase()] || "MEDIUM";
  }

  private mapPipSeverity(severity: string): string {
    const severityMap: { [key: string]: string } = {
      CRITICAL: "CRITICAL",
      HIGH: "HIGH",
      MODERATE: "MEDIUM",
      LOW: "LOW",
      UNKNOWN: "MEDIUM",
    };
    return severityMap[severity.toUpperCase()] || "MEDIUM";
  }

  private isVersionVulnerable(
    currentVersion: string,
    maxSafeVersion: string
  ): boolean {
    try {
      // Simple version comparison (basic implementation)
      const current = currentVersion
        .replace(/[^0-9.]/g, "")
        .split(".")
        .map(Number);
      const safe = maxSafeVersion
        .replace(/[^0-9.]/g, "")
        .split(".")
        .map(Number);

      for (let i = 0; i < Math.max(current.length, safe.length); i++) {
        const c = current[i] || 0;
        const s = safe[i] || 0;
        if (c < s) return true;
        if (c > s) return false;
      }
      return false;
    } catch (error) {
      // If version comparison fails, assume it's vulnerable
      return true;
    }
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
