#!/usr/bin/env node

/**
 * @fileoverview CAWS Scope Guard
 * Enforces that experimental code stays within designated sandbox areas
 * @author @darianrosebrook
 */

const fs = require('fs');
const { execSync } = require('child_process');

/**
 * Check if experimental code is properly contained
 * @param {string} workingSpecPath - Path to working spec file
 * @returns {Object} Scope validation results
 */
function checkExperimentalContainment(workingSpecPath = '.caws/working-spec.yaml') {
  try {
    if (!fs.existsSync(workingSpecPath)) {
      console.error('❌ Working spec not found:', workingSpecPath);
      return { valid: false, errors: ['Working spec not found'] };
    }

    const yaml = require('js-yaml');
    const spec = yaml.load(fs.readFileSync(workingSpecPath, 'utf8'));

    const results = {
      valid: true,
      errors: [],
      warnings: [],
      experimentalFiles: [],
      nonExperimentalFiles: [],
    };

    // Only check if experimental mode is enabled
    if (!spec.experimental_mode?.enabled) {
      console.log('ℹ️  Experimental mode not enabled - skipping containment check');
      return results;
    }

    const sandboxLocation = spec.experimental_mode.sandbox_location || 'experimental/';
    console.log(`🔍 Checking containment for experimental code in: ${sandboxLocation}`);

    // Get list of changed files (this would typically come from git diff)
    const changedFiles = getChangedFiles();

    if (changedFiles.length === 0) {
      console.log('ℹ️  No files changed - skipping scope check');
      return results;
    }

    // Check each changed file
    changedFiles.forEach((file) => {
      const isInSandbox =
        file.startsWith(sandboxLocation) ||
        file.includes(`/${sandboxLocation}`) ||
        file.includes(sandboxLocation);

      if (isInSandbox) {
        results.experimentalFiles.push(file);
        console.log(`✅ Experimental file properly contained: ${file}`);
      } else {
        results.nonExperimentalFiles.push(file);
        results.valid = false;
        results.errors.push(`Experimental code found outside sandbox: ${file}`);
        console.error(`❌ Experimental code outside sandbox: ${file}`);
      }
    });

    // Check if experimental files actually exist
    results.experimentalFiles.forEach((file) => {
      if (!fs.existsSync(file)) {
        results.warnings.push(`Experimental file not found (may have been deleted): ${file}`);
        console.warn(`⚠️  Experimental file not found: ${file}`);
      }
    });

    return results;
  } catch (error) {
    console.error('❌ Error checking experimental containment:', error.message);
    return { valid: false, errors: [error.message] };
  }
}

/**
 * Get list of changed files from git
 * @returns {Array} List of changed file paths
 */
function getChangedFiles() {
  try {
    // Get files that are staged or modified
    const staged = execSync('git diff --cached --name-only', { encoding: 'utf8' })
      .split('\n')
      .filter((file) => file.trim());

    const modified = execSync('git diff --name-only', { encoding: 'utf8' })
      .split('\n')
      .filter((file) => file.trim());

    // Combine and deduplicate
    const allFiles = [...new Set([...staged, ...modified])];

    // Filter out deleted files (they might still be in the diff)
    return allFiles.filter((file) => {
      try {
        return fs.existsSync(file);
      } catch {
        return false;
      }
    });
  } catch (error) {
    console.warn('⚠️  Could not get changed files from git:', error.message);
    return [];
  }
}

/**
 * Validate that experimental code follows containment rules
 * @param {string} workingSpecPath - Path to working spec file
 */
function validateExperimentalScope(workingSpecPath = '.caws/working-spec.yaml') {
  console.log('🔍 Validating experimental code containment...');

  const results = checkExperimentalContainment(workingSpecPath);

  if (!results.valid) {
    console.error('\n❌ Experimental containment validation failed:');
    results.errors.forEach((error) => {
      console.error(`   - ${error}`);
    });

    if (results.warnings.length > 0) {
      console.warn('\n⚠️  Warnings:');
      results.warnings.forEach((warning) => {
        console.warn(`   - ${warning}`);
      });
    }

    console.error('\n💡 To fix containment issues:');
    console.error('   1. Move experimental code to the designated sandbox location');
    console.error('   2. Update the sandbox_location in your working spec');
    console.error('   3. Or disable experimental mode if this is production code');

    process.exit(1);
  }

  if (results.warnings.length > 0) {
    console.warn('\n⚠️  Experimental containment warnings:');
    results.warnings.forEach((warning) => {
      console.warn(`   - ${warning}`);
    });
  }

  console.log('✅ Experimental code containment validated');
  console.log(`   - Files in sandbox: ${results.experimentalFiles.length}`);
  console.log(`   - Files outside sandbox: ${results.nonExperimentalFiles.length}`);
}

// CLI interface
if (require.main === module) {
  const command = process.argv[2];
  const specPath = process.argv[3] || '.caws/working-spec.yaml';

  switch (command) {
    case 'validate':
      validateExperimentalScope(specPath);
      break;

    case 'check':
      const results = checkExperimentalContainment(specPath);
      console.log('\n📊 Containment Check Results:');
      console.log(`   Valid: ${results.valid}`);
      console.log(`   Experimental files: ${results.experimentalFiles.length}`);
      console.log(`   Non-experimental files: ${results.nonExperimentalFiles.length}`);
      console.log(`   Errors: ${results.errors.length}`);
      console.log(`   Warnings: ${results.warnings.length}`);

      if (results.errors.length > 0) {
        console.log('\n❌ Errors:');
        results.errors.forEach((error) => console.log(`   - ${error}`));
      }

      if (results.warnings.length > 0) {
        console.log('\n⚠️  Warnings:');
        results.warnings.forEach((warning) => console.log(`   - ${warning}`));
      }

      process.exit(results.valid ? 0 : 1);
      break;

    default:
      console.log('CAWS Scope Guard');
      console.log('Usage:');
      console.log('  node scope-guard.js validate [spec-path]');
      console.log('  node scope-guard.js check [spec-path]');
      console.log('');
      console.log('Examples:');
      console.log('  node scope-guard.js validate');
      console.log('  node scope-guard.js check .caws/working-spec.yaml');
      process.exit(1);
  }
}

module.exports = {
  checkExperimentalContainment,
  validateExperimentalScope,
  getChangedFiles,
};
