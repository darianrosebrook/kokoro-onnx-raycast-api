/**
 * CAWS Configuration Manager
 * Centralized configuration management for CAWS tools
 *
 * @author @darianrosebrook
 */

import * as path from 'path';
import yaml from 'js-yaml';
import { CawsConfig } from './types.js';
import { CawsBaseTool, ToolResult } from './base-tool.js';

export class CawsConfigManager extends CawsBaseTool {
  private config: CawsConfig | null = null;
  private readonly configPath: string;

  constructor() {
    super();
    this.configPath = path.join(this.getCawsDirectory(), 'config.json');
    this.loadConfig();
  }

  /**
   * Load configuration from file
   */
  private loadConfig(): void {
    try {
      const configData = this.readJsonFile(this.configPath);
      if (configData) {
        this.config = configData as CawsConfig;
        this.validateConfig();
      }
    } catch {
      this.logWarning('Failed to load CAWS configuration, using defaults');
      this.config = this.getDefaultConfig();
    }
  }

  /**
   * Save configuration to file
   */
  private saveConfig(): boolean {
    try {
      return this.writeJsonFile(this.configPath, this.config);
    } catch (error) {
      this.logError(`Failed to save CAWS configuration: ${error}`);
      return false;
    }
  }

  /**
   * Get default configuration
   */
  private getDefaultConfig(): CawsConfig {
    return {
      version: '1.0.0',
      environment: 'development',
      gates: {
        coverage: {
          enabled: true,
          thresholds: {
            statements: 80,
            branches: 75,
            functions: 80,
            lines: 80,
          },
        },
        mutation: {
          enabled: true,
          thresholds: {
            killed: 70,
            survived: 30,
          },
        },
        contracts: {
          enabled: true,
          required: true,
        },
        trust_score: {
          enabled: true,
          threshold: 0.8,
        },
      },
      tools: {
        coverage: {
          command: 'nyc',
          args: ['--reporter=json', '--reporter=text'],
        },
        mutation: {
          command: 'stryker',
          args: ['run'],
        },
        contracts: {
          command: 'pact',
          args: ['verify'],
        },
        linting: {
          command: 'eslint',
          args: ['.'],
        },
        testing: {
          command: 'jest',
          args: ['--coverage'],
        },
      },
      paths: {
        working_directory: this.getWorkingDirectory(),
        reports: path.join(this.getWorkingDirectory(), 'reports'),
        coverage: path.join(this.getWorkingDirectory(), 'coverage'),
        artifacts: path.join(this.getWorkingDirectory(), 'artifacts'),
      },
      logging: {
        level: 'info',
        file: path.join(this.getCawsDirectory(), 'logs', 'caws.log'),
        format: 'json',
      },
      features: {
        multi_modal: true,
        obsidian_support: true,
        parallel_processing: true,
      },
      tiers: {
        1: {
          min_branch: 0.9,
          min_coverage: 0.9,
          min_mutation: 0.8,
          requires_contracts: true,
        },
        2: {
          min_branch: 0.8,
          min_coverage: 0.8,
          min_mutation: 0.7,
          requires_contracts: true,
        },
        3: {
          min_branch: 0.7,
          min_coverage: 0.7,
          min_mutation: 0.6,
          requires_contracts: false,
        },
      },
      defaultTier: '2',
      workingSpecPath: path.join(this.getCawsDirectory(), 'working-spec.yaml'),
      provenancePath: path.join(this.getCawsDirectory(), 'provenance.json'),
      waiversPath: path.join(this.getCawsDirectory(), 'waivers.yml'),
      cawsDirectory: this.getCawsDirectory(),
      experiment_defaults: {
        enabled: false,
        timeboxed_hours: 24,
        success_criteria: ['Basic functionality works'],
      },
    };
  }

  /**
   * Validate configuration structure
   */
  private validateConfig(): void {
    if (!this.config) return;

    // Basic validation
    if (!this.config.version) {
      this.logWarning('Configuration missing version, setting to default');
      this.config.version = '1.0.0';
    }

    if (!this.config.environment) {
      this.logWarning('Configuration missing environment, setting to development');
      this.config.environment = 'development';
    }

    // Validate paths
    if (!this.config.paths) {
      this.config.paths = this.getDefaultConfig().paths;
    }

    // Ensure required directories exist
    this.ensureDirectories();
  }

  /**
   * Ensure required directories exist
   */
  private ensureDirectories(): void {
    if (!this.config?.paths) return;

    const requiredDirs = [
      this.config.paths.reports,
      this.config.paths.coverage,
      this.config.paths.artifacts,
      path.dirname(this.config.logging?.file || ''),
    ];

    for (const dir of requiredDirs) {
      if (dir) {
        this.ensureDirectoryExists(dir);
      }
    }
  }

  /**
   * Get current configuration
   */
  getConfig(): CawsConfig {
    return this.config || this.getDefaultConfig();
  }

  /**
   * Update configuration
   */
  updateConfig(updates: Partial<CawsConfig>): ToolResult {
    try {
      if (!this.config) {
        this.config = this.getDefaultConfig();
      }

      // Deep merge updates
      this.config = {
        ...this.config,
        ...updates,
        gates: { ...this.config.gates, ...updates.gates },
        tools: { ...this.config.tools, ...updates.tools },
        paths: { ...this.config.paths, ...updates.paths },
        logging: { ...this.config.logging, ...updates.logging },
        features: { ...this.config.features, ...updates.features },
      };

      // Validate and save
      this.validateConfig();

      if (this.saveConfig()) {
        return this.createResult(true, 'Configuration updated successfully');
      } else {
        return this.createResult(false, 'Failed to save configuration');
      }
    } catch (error) {
      return this.createResult(false, `Failed to update configuration: ${error}`);
    }
  }

  /**
   * Get specific configuration section
   */
  getSection<K extends keyof CawsConfig>(section: K): CawsConfig[K] | null {
    const config = this.getConfig();
    return config[section] || null;
  }

  /**
   * Get gate configuration
   */
  getGateConfig(gateName: string): any {
    const gates = this.getSection('gates');
    return gates?.[gateName] || null;
  }

  /**
   * Get tool configuration
   */
  getToolConfig(toolName: string): any {
    const tools = this.getSection('tools');
    return tools?.[toolName] || null;
  }

  /**
   * Get path configuration
   */
  getPathConfig(pathName: string): string | null {
    const paths = this.getSection('paths');
    return paths?.[pathName] || null;
  }

  /**
   * Check if a feature is enabled
   */
  isFeatureEnabled(feature: string): boolean {
    const features = this.getSection('features');
    const featureValue = features?.[feature];
    return typeof featureValue === 'boolean' ? featureValue : featureValue?.enabled === true;
  }

  /**
   * Get logging configuration
   */
  getLoggingConfig() {
    return this.getSection('logging');
  }

  /**
   * Load configuration from file path
   */
  loadConfigFromFile(filePath: string): ToolResult {
    try {
      const configData = this.readJsonFile(filePath);
      if (!configData) {
        return this.createResult(false, `Failed to read configuration from ${filePath}`);
      }

      this.config = configData as CawsConfig;
      this.validateConfig();

      return this.createResult(true, 'Configuration loaded from file');
    } catch (error) {
      return this.createResult(false, `Failed to load configuration: ${error}`);
    }
  }

  /**
   * Save configuration to custom path
   */
  saveConfigToFile(filePath: string): ToolResult {
    try {
      const saved = this.writeJsonFile(filePath, this.config);
      if (saved) {
        return this.createResult(true, `Configuration saved to ${filePath}`);
      } else {
        return this.createResult(false, `Failed to save configuration to ${filePath}`);
      }
    } catch (error) {
      return this.createResult(false, `Failed to save configuration: ${error}`);
    }
  }

  /**
   * Reset configuration to defaults
   */
  resetConfig(): ToolResult {
    this.config = this.getDefaultConfig();
    return this.updateConfig({});
  }

  /**
   * Export configuration as YAML
   */
  exportAsYaml(): string | null {
    try {
      return yaml.dump(this.getConfig(), {
        indent: 2,
        lineWidth: 80,
        noRefs: true,
      });
    } catch (error) {
      this.logError(`Failed to export configuration as YAML: ${error}`);
      return null;
    }
  }

  /**
   * Import configuration from YAML
   */
  importFromYaml(yamlContent: string): ToolResult {
    try {
      const configData = yaml.load(yamlContent) as CawsConfig;
      this.config = configData;
      this.validateConfig();

      if (this.saveConfig()) {
        return this.createResult(true, 'Configuration imported from YAML successfully');
      } else {
        return this.createResult(false, 'Failed to save imported configuration');
      }
    } catch (error) {
      return this.createResult(false, `Failed to import configuration from YAML: ${error}`);
    }
  }
}
