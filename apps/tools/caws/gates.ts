#!/usr/bin/env tsx

/**
 * CAWS Gates Tool - Enhanced Implementation
 * CLI wrapper for CawsGateChecker with tier policies
 *
 * @author @darianrosebrook
 */

import { CawsGateChecker } from './shared/gate-checker.js';
import { CawsConfigManager } from './shared/config-manager.js';

// Tier policies for quality gates
const TIER_POLICIES = {
  1: {
    branch_coverage: 0.9,
    mutation_score: 0.7,
    max_files: 40,
    max_loc: 1500,
    trust_score: 85,
  },
  2: {
    branch_coverage: 0.8,
    mutation_score: 0.5,
    max_files: 25,
    max_loc: 1000,
    trust_score: 82,
  },
  3: {
    branch_coverage: 0.7,
    mutation_score: 0.3,
    max_files: 15,
    max_loc: 500,
    trust_score: 75,
  },
};

class GatesCLI {
  private gateChecker: CawsGateChecker;
  private configManager: CawsConfigManager;

  constructor() {
    this.gateChecker = new CawsGateChecker();
    this.configManager = new CawsConfigManager();
  }

  /**
   * Show tier policy
   */
  showTierPolicy(tier: number = 1): void {
    const policy = TIER_POLICIES[tier as keyof typeof TIER_POLICIES];
    if (!policy) {
      console.error(`❌ Unknown tier: ${tier}`);
      process.exit(1);
    }

    console.log(`📋 Tier ${tier} Policy:`);
    console.log(`Branch Coverage: ≥${policy.branch_coverage * 100}%`);
    console.log(`Mutation Score: ≥${policy.mutation_score * 100}%`);
    console.log(`Max Files: ${policy.max_files}`);
    console.log(`Max LOC: ${policy.max_loc}`);
    console.log(`Trust Score: ≥${policy.trust_score}`);
    console.log('Requires Contracts: true');
    console.log('Manual Review: Required');
  }

  /**
   * Enforce coverage gate using CawsGateChecker
   */
  async enforceCoverageGate(tier: number = 2): Promise<boolean> {
    try {
      const policy = TIER_POLICIES[tier as keyof typeof TIER_POLICIES];
      const result = await this.gateChecker.checkCoverage({
        tier,
        workingDirectory: process.cwd(),
      });

      if (result.passed) {
        console.log(
          `✅ Coverage gate passed: ${(result.score * 100).toFixed(1)}% ≥ ${policy.branch_coverage * 100}%`
        );
        return true;
      } else {
        console.log(
          `❌ Coverage gate failed: ${(result.score * 100).toFixed(1)}% < ${policy.branch_coverage * 100}%`
        );
        if (result.errors && result.errors.length > 0) {
          result.errors.forEach((error) => console.error(`  - ${error}`));
        }
        if (result.details?.searched_paths) {
          console.error(`  Searched paths: ${result.details.searched_paths.join(', ')}`);
        }
        if (result.details?.run_command) {
          console.error(`  Run: ${result.details.run_command}`);
        }
        return false;
      }
    } catch (error) {
      console.error(`❌ Coverage gate check failed: ${error}`);
      return false;
    }
  }

  /**
   * Enforce mutation gate using CawsGateChecker
   */
  async enforceMutationGate(tier: number = 2): Promise<boolean> {
    try {
      const policy = TIER_POLICIES[tier as keyof typeof TIER_POLICIES];
      const result = await this.gateChecker.checkMutation({
        tier,
        workingDirectory: process.cwd(),
      });

      if (result.passed) {
        console.log(
          `✅ Mutation gate passed: ${(result.score * 100).toFixed(1)}% ≥ ${policy.mutation_score * 100}%`
        );
        return true;
      } else {
        console.log(
          `❌ Mutation gate failed: ${(result.score * 100).toFixed(1)}% < ${policy.mutation_score * 100}%`
        );
        if (result.errors && result.errors.length > 0) {
          result.errors.forEach((error) => console.error(`  - ${error}`));
        }
        if (result.details?.searched_paths) {
          console.error(`  Searched paths: ${result.details.searched_paths.join(', ')}`);
        }
        if (result.details?.run_command) {
          console.error(`  Run: ${result.details.run_command}`);
        }
        return false;
      }
    } catch (error) {
      console.error(`❌ Mutation gate check failed: ${error}`);
      return false;
    }
  }

  /**
   * Enforce contract gate using CawsGateChecker
   */
  async enforceContractGate(tier: number = 2): Promise<boolean> {
    try {
      const result = await this.gateChecker.checkContracts({
        tier,
        workingDirectory: process.cwd(),
      });

      if (result.passed) {
        console.log('✅ Contract gate passed');
        return true;
      } else {
        console.log('❌ Contract gate failed');
        if (result.errors && result.errors.length > 0) {
          result.errors.forEach((error) => console.error(`  - ${error}`));
        }
        if (result.details?.searched_paths) {
          console.error(`  Searched paths: ${result.details.searched_paths.join(', ')}`);
        }
        if (result.details?.example_command) {
          console.error(`  Example: ${result.details.example_command}`);
        }
        return false;
      }
    } catch (error) {
      console.error(`❌ Contract gate check failed: ${error}`);
      return false;
    }
  }

  /**
   * Run all gates for a tier
   */
  async runAllGates(tier: number = 2): Promise<boolean> {
    console.log(`\n🚪 Running all gates for Tier ${tier}...\n`);

    const results = await Promise.all([
      this.enforceCoverageGate(tier),
      this.enforceMutationGate(tier),
      this.enforceContractGate(tier),
    ]);

    const allPassed = results.every((r) => r);

    console.log(`\n${'='.repeat(50)}`);
    if (allPassed) {
      console.log('✅ All gates passed!');
    } else {
      console.log('❌ Some gates failed');
    }
    console.log('='.repeat(50));

    return allPassed;
  }
}

// Main CLI handler
if (import.meta.url === `file://${process.argv[1]}`) {
  (async () => {
    const command = process.argv[2];
    const cli = new GatesCLI();

    switch (command) {
      case 'tier': {
        const tier = parseInt(process.argv[3]) || 1;
        cli.showTierPolicy(tier);
        break;
      }

      case 'coverage': {
        const tier = parseInt(process.argv[3]) || 2;
        const passed = await cli.enforceCoverageGate(tier);
        process.exit(passed ? 0 : 1);
      }

      case 'mutation': {
        const tier = parseInt(process.argv[3]) || 2;
        const passed = await cli.enforceMutationGate(tier);
        process.exit(passed ? 0 : 1);
      }

      case 'contracts': {
        const tier = parseInt(process.argv[3]) || 2;
        const passed = await cli.enforceContractGate(tier);
        process.exit(passed ? 0 : 1);
      }

      case 'all': {
        const tier = parseInt(process.argv[3]) || 2;
        const passed = await cli.runAllGates(tier);
        process.exit(passed ? 0 : 1);
      }

      default:
        console.log('CAWS Gates Tool - Quality Gate Enforcement');
        console.log('');
        console.log('Commands:');
        console.log('  tier <tier>       - Show tier policy');
        console.log('  coverage <tier>   - Enforce coverage gate');
        console.log('  mutation <tier>   - Enforce mutation gate');
        console.log('  contracts <tier>  - Enforce contract gate');
        console.log('  all <tier>        - Run all gates for tier');
        console.log('');
        console.log('Examples:');
        console.log('  gates.ts tier 1');
        console.log('  gates.ts coverage 2');
        console.log('  gates.ts all 2');
        process.exit(1);
    }
  })();
}

export { GatesCLI };
