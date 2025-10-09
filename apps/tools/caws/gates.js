#!/usr/bin/env node

/**
 * @fileoverview CAWS Gates Tool - Enhanced Implementation
 * @author @darianrosebrook
 *
 * Note: For enhanced TypeScript version with full gate checking, use gates.ts
 * This .js version provides basic gate enforcement for backward compatibility
 */

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

/**
 * Show tier policy
 * @param {number} tier - Risk tier (1-3)
 */
function showTierPolicy(tier = 1) {
  const policy = TIER_POLICIES[tier];
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
 * Enforce coverage gate
 * @param {number} coverage - Coverage value to test
 * @param {number} threshold - Threshold to test against
 */
function enforceCoverageGate(coverage, threshold = 0.8) {
  if (coverage >= threshold) {
    console.log(`✅ Branch coverage gate passed: ${coverage} >= ${threshold}`);
    return true;
  } else {
    console.log(`❌ Branch coverage gate failed: ${coverage} < ${threshold}`);
    return false;
  }
}

/**
 * Enforce mutation gate
 * @param {number} score - Mutation score to test
 * @param {number} threshold - Threshold to test against
 */
function enforceMutationGate(score, threshold = 0.5) {
  if (score >= threshold) {
    console.log(`✅ Mutation gate passed: ${score} >= ${threshold}`);
    return true;
  } else {
    console.log(`❌ Mutation gate failed: ${score} < ${threshold}`);
    return false;
  }
}

/**
 * Enforce trust score gate
 * @param {number} score - Trust score to test
 * @param {number} threshold - Threshold to test against
 */
function enforceTrustScoreGate(score, threshold = 82) {
  if (score >= threshold) {
    console.log(`✅ Trust score gate passed: ${score} >= ${threshold}`);
    return true;
  } else {
    console.log(`❌ Trust score gate failed: ${score} < ${threshold}`);
    return false;
  }
}

/**
 * Enforce budget gate
 * @param {number} files - File count to test
 * @param {number} loc - Lines of code to test
 * @param {number} maxFiles - Maximum allowed files
 * @param {number} maxLoc - Maximum allowed LOC
 */
function enforceBudgetGate(files, loc, maxFiles = 25, maxLoc = 1000) {
  const filesOk = files <= maxFiles;
  const locOk = loc <= maxLoc;

  if (filesOk && locOk) {
    console.log(`✅ Budget gate passed: ${files} files, ${loc} LOC`);
    return true;
  } else {
    if (!filesOk) {
      console.log(`❌ Budget gate failed: ${files} files > ${maxFiles} max files`);
    }
    if (!locOk) {
      console.log(`❌ Budget gate failed: ${loc} LOC > ${maxLoc} max LOC`);
    }
    return false;
  }
}

/**
 * Main command handler
 */
function main() {
  const command = process.argv[2];

  switch (command) {
    case 'tier':
      const tier = parseInt(process.argv[3]) || 1;
      showTierPolicy(tier);
      break;

    case 'coverage':
      const coverage = parseFloat(process.argv[3]) || 0.85;
      const coverageThreshold = 0.8;
      if (!enforceCoverageGate(coverage, coverageThreshold)) {
        throw new Error(`Coverage gate failed: ${coverage} < ${coverageThreshold}`);
      }
      break;

    case 'mutation':
      const mutationScore = parseFloat(process.argv[3]) || 0.6;
      const mutationThreshold = 0.5;
      if (!enforceMutationGate(mutationScore, mutationThreshold)) {
        throw new Error(`Mutation gate failed: ${mutationScore} < ${mutationThreshold}`);
      }
      break;

    case 'trust':
      const trustScore = parseInt(process.argv[3]) || 85;
      const trustThreshold = 82;
      if (!enforceTrustScoreGate(trustScore, trustThreshold)) {
        throw new Error(`Trust score gate failed: ${trustScore} < ${trustThreshold}`);
      }
      break;

    case 'budget':
      const files = parseInt(process.argv[3]) || 20;
      const loc = parseInt(process.argv[4]) || 800;
      if (!enforceBudgetGate(files, loc, 25, 1000)) {
        throw new Error(`Budget gate failed: ${files} files or ${loc} LOC exceeds limits`);
      }
      break;

    default:
      console.log('CAWS Gates Tool - Quality Gate Enforcement');
      console.log('');
      console.log('Commands:');
      console.log('  tier <tier>       - Show tier policy');
      console.log('  coverage <score>  - Enforce coverage gate');
      console.log('  mutation <score>  - Enforce mutation gate');
      console.log('  trust <score>     - Enforce trust score gate');
      console.log('  budget <files> <loc> - Enforce budget gate');
      console.log('');
      console.log('Note: For enhanced features, use gates.ts with: npx tsx gates.ts');
      process.exit(1);
  }
}

// Handle direct script execution
if (require.main === module) {
  main();
}

module.exports = {
  showTierPolicy,
  enforceCoverageGate,
  enforceMutationGate,
  enforceTrustScoreGate,
  enforceBudgetGate,
  TIER_POLICIES,
};
