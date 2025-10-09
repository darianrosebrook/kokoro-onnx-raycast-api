/**
 * CAWS Base Tool
 * Shared functionality for all CAWS tools including file operations,
 * configuration management, and common utilities
 *
 * @author @darianrosebrook
 */

import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';
import { CawsConfig } from './types.js';

export interface ToolResult {
  success: boolean;
  message: string;
  data?: any;
  errors?: string[];
  warnings?: string[];
}

export interface FileOperationOptions {
  encoding?: string;
  createDir?: boolean;
  backup?: boolean;
}

export abstract class CawsBaseTool {
  protected readonly __dirname: string;
  protected readonly cawsDirectory: string;
  protected readonly workingDirectory: string;

  constructor() {
    this.__dirname = path.dirname(fileURLToPath(import.meta.url));
    this.workingDirectory = process.cwd();
    this.cawsDirectory = path.join(this.workingDirectory, '.caws');
  }

  /**
   * Get the CAWS configuration directory
   */
  protected getCawsDirectory(): string {
    return this.cawsDirectory;
  }

  /**
   * Get the working directory
   */
  protected getWorkingDirectory(): string {
    return this.workingDirectory;
  }

  /**
   * Safely read a JSON file with error handling
   */
  protected readJsonFile<T = any>(filePath: string): T | null {
    try {
      if (!fs.existsSync(filePath)) {
        return null;
      }

      const content = fs.readFileSync(filePath, 'utf-8');
      return JSON.parse(content) as T;
    } catch (error) {
      this.logError(`Failed to read JSON file ${filePath}: ${error}`);
      return null;
    }
  }

  /**
   * Safely write a JSON file with backup option
   */
  protected writeJsonFile(
    filePath: string,
    data: any,
    options: FileOperationOptions = {}
  ): boolean {
    try {
      const { createDir = true, backup = false } = options;

      // Create directory if needed
      if (createDir) {
        const dir = path.dirname(filePath);
        if (!fs.existsSync(dir)) {
          fs.mkdirSync(dir, { recursive: true });
        }
      }

      // Create backup if requested
      if (backup && fs.existsSync(filePath)) {
        const backupPath = `${filePath}.backup`;
        fs.copyFileSync(filePath, backupPath);
      }

      // Write the file
      fs.writeFileSync(filePath, JSON.stringify(data, null, 2), 'utf-8');
      return true;
    } catch (error) {
      this.logError(`Failed to write JSON file ${filePath}: ${error}`);
      return false;
    }
  }

  /**
   * Safely read a YAML file
   */
  protected async readYamlFile<T = any>(filePath: string): Promise<T | null> {
    try {
      if (!fs.existsSync(filePath)) {
        return null;
      }

      const content = fs.readFileSync(filePath, 'utf-8');
      const yaml = await import('js-yaml');
      return yaml.load(content) as T;
    } catch (error) {
      this.logError(`Failed to read YAML file ${error}`);
      return null;
    }
  }

  /**
   * Check if a path exists
   */
  protected pathExists(filePath: string): boolean {
    return fs.existsSync(filePath);
  }

  /**
   * Create directory if it doesn't exist
   */
  protected ensureDirectoryExists(dirPath: string): boolean {
    try {
      if (!fs.existsSync(dirPath)) {
        fs.mkdirSync(dirPath, { recursive: true });
      }
      return true;
    } catch (error) {
      this.logError(`Failed to create directory ${dirPath}: ${error}`);
      return false;
    }
  }

  /**
   * Get relative path from working directory
   */
  protected getRelativePath(absolutePath: string): string {
    return path.relative(this.workingDirectory, absolutePath);
  }

  /**
   * Get absolute path from relative path
   */
  protected getAbsolutePath(relativePath: string): string {
    return path.resolve(this.workingDirectory, relativePath);
  }

  /**
   * Load tier policy configuration
   */
  protected loadTierPolicy(): Record<string, any> | null {
    const policyPath = path.join(this.cawsDirectory, 'policy', 'tier-policy.json');
    return this.readJsonFile(policyPath);
  }

  /**
   * Load CAWS configuration
   */
  protected loadCawsConfig(): CawsConfig | null {
    const configPath = path.join(this.cawsDirectory, 'config.json');
    return this.readJsonFile(configPath);
  }

  /**
   * Log an error message
   */
  protected logError(message: string): void {
    console.error(`❌ ${message}`);
  }

  /**
   * Log a warning message
   */
  protected logWarning(message: string): void {
    console.warn(`⚠️  ${message}`);
  }

  /**
   * Log an info message
   */
  protected logInfo(message: string): void {
    console.log(`ℹ️  ${message}`);
  }

  /**
   * Log a success message
   */
  protected logSuccess(message: string): void {
    console.log(`✅ ${message}`);
  }

  /**
   * Create a standardized result object
   */
  protected createResult(
    success: boolean,
    message: string,
    data?: any,
    errors?: string[],
    warnings?: string[]
  ): ToolResult {
    return {
      success,
      message,
      data,
      errors: errors || [],
      warnings: warnings || [],
    };
  }

  /**
   * Validate required environment variables
   */
  protected validateEnvironment(variables: string[]): boolean {
    const missing = variables.filter((varName) => !process.env[varName]);

    if (missing.length > 0) {
      this.logError(`Missing required environment variables: ${missing.join(', ')}`);
      return false;
    }

    return true;
  }

  /**
   * Get environment variable with fallback
   */
  protected getEnvVar(name: string, fallback: string = ''): string {
    return process.env[name] || fallback;
  }

  /**
   * Parse command line arguments
   */
  protected parseArgs(expectedArgs: string[]): Record<string, string> {
    const args = process.argv.slice(2);
    const result: Record<string, string> = {};

    for (let i = 0; i < args.length; i++) {
      if (i < expectedArgs.length) {
        result[expectedArgs[i]] = args[i];
      }
    }

    return result;
  }

  /**
   * Show usage information
   */
  protected showUsage(usage: string, description: string): void {
    console.log(`Usage: ${usage}`);
    console.log(description);
  }

  /**
   * Exit with appropriate code
   */
  protected exitWithResult(result: ToolResult): void {
    if (result.success) {
      this.logSuccess(result.message);
      process.exit(0);
    } else {
      this.logError(result.message);
      if (result.errors && result.errors.length > 0) {
        result.errors.forEach((error) => this.logError(error));
      }
      process.exit(1);
    }
  }
}
