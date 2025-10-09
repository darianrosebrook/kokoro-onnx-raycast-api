/**
 * @fileoverview CAWS Provenance Tool
 * @author @darianrosebrook
 *
 * Note: For enhanced TypeScript version with better error handling, use provenance.ts
 * This .js version provides basic provenance for backward compatibility
 */

/**
 * Generates provenance information for a CAWS project
 * @returns {Object} Provenance data with metadata and artifacts
 */
function generateProvenance() {
  try {
    const fs = require('fs');
    const crypto = require('crypto');

    // Check if we're in a CAWS project
    if (!fs.existsSync('.caws')) {
      throw new Error('Not in a CAWS project directory');
    }

    const workingSpecPath = '.caws/working-spec.yaml';
    if (!fs.existsSync(workingSpecPath)) {
      throw new Error('Working specification file not found');
    }

    // Load working spec
    const yaml = require('js-yaml');
    const specContent = fs.readFileSync(workingSpecPath, 'utf8');
    const spec = yaml.load(specContent);

    // Generate provenance data
    const provenance = {
      agent: 'caws-cli',
      model: 'cli-interactive',
      modelHash: (() => {
        try {
          return require('../../../package.json').version || '1.0.0';
        } catch (error) {
          return '1.0.0'; // Fallback version if package.json not found
        }
      })(),
      toolAllowlist: [
        'node',
        'npm',
        'git',
        'fs-extra',
        'inquirer',
        'commander',
        'js-yaml',
        'ajv',
        'chalk',
      ],
      artifacts: ['.caws/working-spec.yaml'],
      results: {
        project_id: spec.id,
        project_title: spec.title,
        risk_tier: spec.risk_tier,
        mode: spec.mode,
        change_budget: spec.change_budget,
        blast_radius: spec.blast_radius,
        operational_rollback_slo: spec.operational_rollback_slo,
      },
      approvals: [],
      timestamp: new Date().toISOString(),
      version: '1.0.0',
      hash: '', // Will be calculated below
    };

    // Calculate hash
    provenance.hash = crypto
      .createHash('sha256')
      .update(JSON.stringify(provenance, Object.keys(provenance).sort()))
      .digest('hex');

    return provenance;
  } catch (error) {
    throw new Error(`Provenance generation failed: ${error.message}`);
  }
}

/**
 * Saves provenance data to a file
 * @param {Object} provenance - Provenance data to save
 * @param {string} outputPath - Path where to save the provenance file
 */
function saveProvenance(provenance, outputPath) {
  try {
    const fs = require('fs');
    const path = require('path');

    // Ensure directory exists
    const dir = path.dirname(outputPath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }

    // Save provenance
    fs.writeFileSync(outputPath, JSON.stringify(provenance, null, 2));
    console.log(`✅ Provenance saved to ${outputPath}`);
  } catch (error) {
    throw new Error(`Failed to save provenance: ${error.message}`);
  }
}

// Handle direct script execution
if (require.main === module) {
  const command = process.argv[2];

  try {
    if (command === 'generate') {
      const provenance = generateProvenance();
      const outputPath = process.argv[3] || '.agent/provenance.json';
      saveProvenance(provenance, outputPath);
      console.log('✅ Provenance generated successfully');
    } else {
      console.log('CAWS Provenance Tool');
      console.log('');
      console.log('Usage:');
      console.log('  node provenance.js generate [output-path]');
      console.log('');
      console.log('Note: For enhanced features, use: npx tsx provenance.ts');
      process.exit(1);
    }
  } catch (error) {
    console.error(`❌ Error: ${error.message}`);
    process.exit(1);
  }
}

module.exports = { generateProvenance, saveProvenance };
