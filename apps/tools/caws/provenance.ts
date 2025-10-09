#!/usr/bin/env tsx

/**
 * CAWS Provenance Tool
 * Enhanced provenance generation with metadata and hashing
 *
 * @author @darianrosebrook
 */

import * as fs from 'fs';
import * as path from 'path';
import * as crypto from 'crypto';
import * as yaml from 'js-yaml';
import { CawsBaseTool } from './shared/base-tool.js';

interface ProvenanceData {
  agent: string;
  model: string;
  modelHash: string;
  toolAllowlist: string[];
  artifacts: string[];
  results: Record<string, any>;
  approvals: string[];
  timestamp: string;
  version: string;
  hash: string;
}

class ProvenanceCLI extends CawsBaseTool {
  /**
   * Generate provenance information for a CAWS project
   */
  generateProvenance(): ProvenanceData {
    try {
      // Check if we're in a CAWS project
      if (!this.pathExists('.caws')) {
        throw new Error('Not in a CAWS project directory');
      }

      const workingSpecPath = '.caws/working-spec.yaml';
      if (!this.pathExists(workingSpecPath)) {
        throw new Error('Working specification file not found');
      }

      // Load working spec
      const specContent = fs.readFileSync(workingSpecPath, 'utf8');
      const spec = yaml.load(specContent) as any;

      // Load package.json for version
      let version = '1.0.0';
      const packageJsonPath = path.join(process.cwd(), 'package.json');
      if (this.pathExists(packageJsonPath)) {
        const pkg = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));
        version = pkg.version || version;
      }

      // Generate provenance data
      const provenance: ProvenanceData = {
        agent: 'caws-cli',
        model: process.env.CAWS_MODEL || 'cli-interactive',
        modelHash: version,
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
          'tsx',
          'typescript',
        ],
        artifacts: ['.caws/working-spec.yaml'],
        results: {
          project_id: spec.id || 'unknown',
          project_title: spec.title || 'Unknown Project',
          risk_tier: spec.risk_tier || 3,
          mode: spec.mode || 'standard',
          change_budget: spec.change_budget,
          blast_radius: spec.blast_radius,
          operational_rollback_slo: spec.operational_rollback_slo,
          acceptance_criteria_count: spec.acceptance?.length || 0,
          contracts_count: spec.contracts?.length || 0,
        },
        approvals: spec.approvals || [],
        timestamp: new Date().toISOString(),
        version: '1.0.0',
        hash: '', // Will be calculated below
      };

      // Calculate hash
      const hashContent = JSON.stringify(provenance, Object.keys(provenance).sort());
      provenance.hash = crypto.createHash('sha256').update(hashContent).digest('hex');

      return provenance;
    } catch (error) {
      throw new Error(`Provenance generation failed: ${error}`);
    }
  }

  /**
   * Save provenance data to a file
   */
  saveProvenance(provenance: ProvenanceData, outputPath: string): void {
    try {
      // Ensure directory exists
      const dir = path.dirname(outputPath);
      if (!this.pathExists(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }

      // Save provenance
      fs.writeFileSync(outputPath, JSON.stringify(provenance, null, 2));
      this.logSuccess(`Provenance saved to ${outputPath}`);
    } catch (error) {
      throw new Error(`Failed to save provenance: ${error}`);
    }
  }

  /**
   * Display provenance information
   */
  displayProvenance(provenance: ProvenanceData): void {
    console.log('\n📋 CAWS Provenance');
    console.log('='.repeat(50));
    console.log(`Agent: ${provenance.agent}`);
    console.log(`Model: ${provenance.model}`);
    console.log(`Version: ${provenance.version}`);
    console.log(`Timestamp: ${provenance.timestamp}`);
    console.log(`Hash: ${provenance.hash.substring(0, 16)}...`);

    console.log('\n📊 Project Results:');
    Object.entries(provenance.results).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        console.log(`  ${key}: ${value}`);
      }
    });

    console.log('\n🔧 Tool Allowlist:');
    provenance.toolAllowlist.slice(0, 5).forEach((tool) => {
      console.log(`  - ${tool}`);
    });
    if (provenance.toolAllowlist.length > 5) {
      console.log(`  ... and ${provenance.toolAllowlist.length - 5} more`);
    }

    console.log('\n📦 Artifacts:');
    provenance.artifacts.forEach((artifact) => {
      console.log(`  - ${artifact}`);
    });

    if (provenance.approvals.length > 0) {
      console.log('\n✅ Approvals:');
      provenance.approvals.forEach((approval) => {
        console.log(`  - ${approval}`);
      });
    }

    console.log('='.repeat(50));
  }
}

// Main CLI handler
if (import.meta.url === `file://${process.argv[1]}`) {
  const command = process.argv[2];
  const cli = new ProvenanceCLI();

  try {
    switch (command) {
      case 'generate': {
        const provenance = cli.generateProvenance();
        const outputPath = process.argv[3] || '.agent/provenance.json';
        cli.saveProvenance(provenance, outputPath);
        cli.displayProvenance(provenance);
        break;
      }

      case 'show': {
        const filePath = process.argv[3] || '.agent/provenance.json';
        if (!cli.pathExists(filePath)) {
          console.error(`❌ Provenance file not found: ${filePath}`);
          process.exit(1);
        }

        const content = fs.readFileSync(filePath, 'utf8');
        const provenance = JSON.parse(content) as ProvenanceData;
        cli.displayProvenance(provenance);
        break;
      }

      default:
        console.log('CAWS Provenance Tool');
        console.log('');
        console.log('Commands:');
        console.log('  generate [output]  - Generate and save provenance data');
        console.log('  show [file]        - Display provenance from file');
        console.log('');
        console.log('Examples:');
        console.log('  provenance.ts generate .agent/provenance.json');
        console.log('  provenance.ts show .agent/provenance.json');
        process.exit(1);
    }
  } catch (error) {
    console.error(`❌ Error: ${error}`);
    process.exit(1);
  }
}

export { ProvenanceCLI };
