#!/usr/bin/env tsx

/**
 * CAWS Validation Tool
 * CLI wrapper for CawsValidator with schema validation
 *
 * @author @darianrosebrook
 */

import * as path from 'path';
import { CawsValidator } from './shared/validator.js';
import { ValidationResult } from './shared/types.js';

class ValidateCLI {
  private validator: CawsValidator;

  constructor() {
    this.validator = new CawsValidator();
  }

  /**
   * Validate a working specification file
   */
  validateWorkingSpec(specPath: string): ValidationResult {
    try {
      const result = this.validator.validateWorkingSpec(specPath);

      if (result.passed) {
        console.log('✅ Working specification is valid');
        console.log(`   Score: ${(result.score * 100).toFixed(0)}%`);

        if (result.warnings && result.warnings.length > 0) {
          console.log('\n⚠️  Warnings:');
          result.warnings.forEach((warning) => console.log(`  - ${warning}`));
        }

        if (result.details) {
          console.log('\n📊 Details:');
          if (result.details.risk_tier) {
            console.log(`  Tier: ${result.details.risk_tier}`);
          }
          if (result.details.acceptance_count) {
            console.log(`  Acceptance Criteria: ${result.details.acceptance_count}`);
          }
          if (result.details.contract_count) {
            console.log(`  Contracts: ${result.details.contract_count}`);
          }
        }
      } else {
        console.error('❌ Working specification is invalid:');
        if (result.errors && result.errors.length > 0) {
          result.errors.forEach((error) => console.error(`  - ${error}`));
        }
      }

      return result;
    } catch (error) {
      console.error(`❌ Validation failed: ${error}`);
      return {
        passed: false,
        errors: [`Validation error: ${error}`],
        score: 0,
        details: {},
      };
    }
  }

  /**
   * Validate a provenance file
   */
  validateProvenance(provenancePath: string): ValidationResult {
    try {
      const result = this.validator.validateProvenance(provenancePath);

      if (result.passed) {
        console.log('✅ Provenance file is valid');
        console.log(`   Score: ${(result.score * 100).toFixed(0)}%`);

        if (result.details) {
          console.log('\n📊 Provenance Details:');
          if (result.details.agent) {
            console.log(`  Agent: ${result.details.agent}`);
          }
          if (result.details.model) {
            console.log(`  Model: ${result.details.model}`);
          }
          if (result.details.commit) {
            console.log(`  Commit: ${result.details.commit}`);
          }
        }
      } else {
        console.error('❌ Provenance file is invalid:');
        if (result.errors && result.errors.length > 0) {
          result.errors.forEach((error) => console.error(`  - ${error}`));
        }
      }

      return result;
    } catch (error) {
      console.error(`❌ Provenance validation failed: ${error}`);
      return {
        passed: false,
        errors: [`Validation error: ${error}`],
        score: 0,
        details: {},
      };
    }
  }

  /**
   * Validate a JSON file against a schema
   */
  validateJsonSchema(jsonPath: string, schemaPath: string): ValidationResult {
    try {
      const result = this.validator.validateJsonAgainstSchema(jsonPath, schemaPath);

      if (result.passed) {
        console.log('✅ JSON file is valid against schema');
      } else {
        console.error('❌ JSON file is invalid:');
        if (result.errors && result.errors.length > 0) {
          result.errors.forEach((error) => console.error(`  - ${error}`));
        }
      }

      return result;
    } catch (error) {
      console.error(`❌ Schema validation failed: ${error}`);
      return {
        passed: false,
        errors: [`Validation error: ${error}`],
        score: 0,
        details: {},
      };
    }
  }

  /**
   * Validate a YAML file against a schema
   */
  validateYamlSchema(yamlPath: string, schemaPath: string): ValidationResult {
    try {
      const result = this.validator.validateYamlAgainstSchema(yamlPath, schemaPath);

      if (result.passed) {
        console.log('✅ YAML file is valid against schema');
      } else {
        console.error('❌ YAML file is invalid:');
        if (result.errors && result.errors.length > 0) {
          result.errors.forEach((error) => console.error(`  - ${error}`));
        }
      }

      return result;
    } catch (error) {
      console.error(`❌ Schema validation failed: ${error}`);
      return {
        passed: false,
        errors: [`Validation error: ${error}`],
        score: 0,
        details: {},
      };
    }
  }
}

// Main CLI handler
if (import.meta.url === `file://${process.argv[1]}`) {
  const command = process.argv[2];
  const cli = new ValidateCLI();

  switch (command) {
    case 'spec': {
      const specPath = process.argv[3] || '.caws/working-spec.yaml';
      const result = cli.validateWorkingSpec(specPath);
      process.exit(result.passed ? 0 : 1);
    }

    case 'provenance': {
      const provenancePath = process.argv[3] || '.agent/provenance.json';
      const result = cli.validateProvenance(provenancePath);
      process.exit(result.passed ? 0 : 1);
    }

    case 'json': {
      const jsonPath = process.argv[3];
      const schemaPath = process.argv[4];

      if (!jsonPath || !schemaPath) {
        console.error('Usage: validate.ts json <json-file> <schema-file>');
        process.exit(1);
      }

      const result = cli.validateJsonSchema(jsonPath, schemaPath);
      process.exit(result.passed ? 0 : 1);
    }

    case 'yaml': {
      const yamlPath = process.argv[3];
      const schemaPath = process.argv[4];

      if (!yamlPath || !schemaPath) {
        console.error('Usage: validate.ts yaml <yaml-file> <schema-file>');
        process.exit(1);
      }

      const result = cli.validateYamlSchema(yamlPath, schemaPath);
      process.exit(result.passed ? 0 : 1);
    }

    default:
      console.log('CAWS Validation Tool');
      console.log('');
      console.log('Commands:');
      console.log('  spec [path]              - Validate working specification');
      console.log('  provenance [path]        - Validate provenance file');
      console.log('  json <file> <schema>     - Validate JSON against schema');
      console.log('  yaml <file> <schema>     - Validate YAML against schema');
      console.log('');
      console.log('Examples:');
      console.log('  validate.ts spec .caws/working-spec.yaml');
      console.log('  validate.ts provenance .agent/provenance.json');
      console.log('  validate.ts yaml .caws/waivers.yml schemas/waivers.schema.json');
      process.exit(1);
  }
}

export { ValidateCLI };
