#!/usr/bin/env tsx

/**
 * CAWS Configuration Management CLI
 *
 * Provides command-line interface for managing CAWS configuration
 * with YAML import/export, section management, and feature flags
 *
 * @author @darianrosebrook
 */

import * as path from 'path';
import { fileURLToPath } from 'url';
import { CawsConfigManager } from './shared/config-manager.js';
import { CawsConfig } from './shared/types.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// CLI interface
if (import.meta.url === `file://${process.argv[1]}`) {
  const command = process.argv[2];
  const configManager = new CawsConfigManager();
  let section: keyof CawsConfig;
  let key: string;
  let value: string;

  switch (command) {
    case 'get': {
      section = process.argv[3] as keyof CawsConfig;
      if (!section) {
        console.log(JSON.stringify(configManager.getConfig(), null, 2));
      } else {
        const configSection = configManager.getSection(section);
        if (configSection) {
          console.log(JSON.stringify(configSection, null, 2));
        } else {
          console.error(`❌ Section '${section}' not found`);
          process.exit(1);
        }
      }
      break;
    }

    case 'set': {
      key = process.argv[3];
      value = process.argv[4];

      if (!key || !value) {
        console.error('Usage: config set <key> <value>');
        console.error('Example: config set gates.coverage.enabled false');
        process.exit(1);
      }

      // Parse the key path and value
      const keyParts = key.split('.');
      let parsedValue: any;
      try {
        parsedValue = JSON.parse(value);
      } catch {
        parsedValue = value; // Use as string if not valid JSON
      }

      // Build the update object
      const update: any = {};
      let current = update;
      for (let i = 0; i < keyParts.length - 1; i++) {
        current[keyParts[i]] = {};
        current = current[keyParts[i]];
      }
      current[keyParts[keyParts.length - 1]] = parsedValue;

      const result = configManager.updateConfig(update);
      if (result.success) {
        console.log('✅ Configuration updated successfully');
      } else {
        console.error(`❌ Failed to update configuration: ${result.message}`);
        if (result.errors) {
          result.errors.forEach((error) => console.error(`   ${error}`));
        }
        process.exit(1);
      }
      break;
    }

    case 'reset': {
      const resetResult = configManager.resetConfig();
      if (resetResult.success) {
        console.log('✅ Configuration reset to defaults');
      } else {
        console.error(`❌ Failed to reset configuration: ${resetResult.message}`);
        process.exit(1);
      }
      break;
    }

    case 'export': {
      const yamlOutput = configManager.exportAsYaml();
      if (yamlOutput) {
        console.log(yamlOutput);
      } else {
        console.error('❌ Failed to export configuration');
        process.exit(1);
      }
      break;
    }

    case 'import': {
      const filePath = process.argv[3];
      if (!filePath) {
        console.error('Usage: config import <file-path>');
        process.exit(1);
      }

      // Read YAML from file
      try {
        const fs = await import('fs');
        const yamlContent = fs.readFileSync(filePath, 'utf-8');
        const importResult = configManager.importFromYaml(yamlContent);

        if (importResult.success) {
          console.log('✅ Configuration imported successfully');
        } else {
          console.error(`❌ Failed to import configuration: ${importResult.message}`);
          if (importResult.errors) {
            importResult.errors.forEach((error) => console.error(`   ${error}`));
          }
          process.exit(1);
        }
      } catch (error) {
        console.error(`❌ Failed to read file: ${error}`);
        process.exit(1);
      }
      break;
    }

    case 'load': {
      const loadPath = process.argv[3];
      if (!loadPath) {
        console.error('Usage: config load <file-path>');
        process.exit(1);
      }

      const loadResult = configManager.loadConfigFromFile(loadPath);
      if (loadResult.success) {
        console.log('✅ Configuration loaded from file');
      } else {
        console.error(`❌ Failed to load configuration: ${loadResult.message}`);
        process.exit(1);
      }
      break;
    }

    case 'save': {
      const savePath = process.argv[3];
      if (!savePath) {
        console.error('Usage: config save <file-path>');
        process.exit(1);
      }

      const saveResult = configManager.saveConfigToFile(savePath);
      if (saveResult.success) {
        console.log(`✅ Configuration saved to ${savePath}`);
      } else {
        console.error(`❌ Failed to save configuration: ${saveResult.message}`);
        process.exit(1);
      }
      break;
    }

    case 'features': {
      const features = configManager.getSection('features');
      if (features) {
        console.log('Enabled features:');
        Object.entries(features).forEach(([key, feature]) => {
          const enabled = typeof feature === 'boolean' ? feature : feature.enabled;
          console.log(`  ${key}: ${enabled ? '✅' : '❌'}`);
        });
      } else {
        console.error('❌ No features configuration found');
      }
      break;
    }

    case 'paths': {
      const paths = configManager.getSection('paths');
      if (paths) {
        console.log('Configured paths:');
        Object.entries(paths).forEach(([key, pathValue]) => {
          console.log(`  ${key}: ${pathValue}`);
        });
      } else {
        console.error('❌ No paths configuration found');
      }
      break;
    }

    case 'gates': {
      const gates = configManager.getSection('gates');
      if (gates) {
        console.log('Gate configurations:');
        Object.entries(gates).forEach(([gateName, config]) => {
          console.log(`  ${gateName}: ${JSON.stringify(config, null, 2)}`);
        });
      } else {
        console.error('❌ No gates configuration found');
      }
      break;
    }

    case 'tools': {
      const tools = configManager.getSection('tools');
      if (tools) {
        console.log('Tool configurations:');
        Object.entries(tools).forEach(([toolName, config]) => {
          console.log(`  ${toolName}: ${JSON.stringify(config, null, 2)}`);
        });
      } else {
        console.error('❌ No tools configuration found');
      }
      break;
    }

    default:
      console.log('CAWS Configuration Manager');
      console.log('');
      console.log('Usage:');
      console.log('  config get [section]    - Get current configuration or specific section');
      console.log('  config set <key> <value> - Set a configuration value');
      console.log('  config reset            - Reset configuration to defaults');
      console.log('  config export           - Export configuration as YAML');
      console.log('  config import <file>    - Import configuration from YAML file');
      console.log('  config load <file>      - Load configuration from JSON file');
      console.log('  config save <file>      - Save configuration to JSON file');
      console.log('  config features         - Show enabled features');
      console.log('  config paths            - Show configured paths');
      console.log('  config gates            - Show gate configurations');
      console.log('  config tools            - Show tool configurations');
      console.log('');
      console.log('Examples:');
      console.log('  config get gates');
      console.log('  config set gates.coverage.enabled false');
      console.log('  config import my-config.yaml');
      break;
  }
}
