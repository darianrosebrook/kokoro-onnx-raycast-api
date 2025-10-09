/**
 * @fileoverview CAWS Validation Tool
 * @author @darianrosebrook
 *
 * Note: For enhanced TypeScript version with schema validation, use validate.ts
 * This .js version provides basic validation for backward compatibility
 */

/**
 * Validates a working specification file
 * @param {string} specPath - Path to the working specification file
 * @returns {Object} Validation result with valid boolean and errors array
 */
function validateWorkingSpec(specPath) {
  try {
    const fs = require('fs');
    const yaml = require('js-yaml');

    if (!fs.existsSync(specPath)) {
      return {
        valid: false,
        errors: [{ message: `Specification file not found: ${specPath}` }],
      };
    }

    const specContent = fs.readFileSync(specPath, 'utf8');
    const spec = yaml.load(specContent);

    // Basic validation
    const errors = [];

    if (!spec.id) errors.push({ message: 'Missing required field: id' });
    if (!spec.title) errors.push({ message: 'Missing required field: title' });
    if (!spec.risk_tier) errors.push({ message: 'Missing required field: risk_tier' });

    if (spec.risk_tier && (spec.risk_tier < 1 || spec.risk_tier > 3)) {
      errors.push({ message: 'Risk tier must be 1, 2, or 3' });
    }

    if (!spec.scope || !spec.scope.in || spec.scope.in.length === 0) {
      errors.push({ message: 'Scope IN must not be empty' });
    }

    return {
      valid: errors.length === 0,
      errors: errors,
    };
  } catch (error) {
    return {
      valid: false,
      errors: [{ message: `Validation error: ${error.message}` }],
    };
  }
}

// Handle direct script execution
if (require.main === module) {
  const specPath = process.argv[2];
  if (!specPath) {
    console.error('Usage: node validate.js <spec-path>');
    console.log('');
    console.log('Note: For enhanced schema validation, use: npx tsx validate.ts spec <spec-path>');
    process.exit(1);
  }

  const result = validateWorkingSpec(specPath);
  if (result.valid) {
    console.log('✅ Working specification is valid');
  } else {
    console.error('❌ Working specification is invalid:');
    result.errors.forEach((error) => console.error(`  - ${error.message}`));
    process.exit(1);
  }
}

module.exports = validateWorkingSpec;
