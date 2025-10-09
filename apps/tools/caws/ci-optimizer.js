#!/usr/bin/env node

/**
 * @fileoverview CAWS CI/CD Pipeline Optimizer
 * Implements risk-driven and change-driven optimizations for faster feedback
 * @author @darianrosebrook
 */

const fs = require('fs');
const path = require('path');
const yaml = require('js-yaml');

/**
 * CI optimization strategies
 */
const OPTIMIZATION_STRATEGIES = {
  TIER_BASED_CONDITIONAL: {
    name: 'Tier-based Conditional Runs',
    description: 'Skip expensive checks for low-risk changes',
    impact: 'high',
    implementation: 'GitHub Actions conditionals',
  },
  SELECTIVE_TEST_EXECUTION: {
    name: 'Selective Test Execution',
    description: 'Run only tests related to changed files',
    impact: 'medium',
    implementation: 'Test selection by file paths',
  },
  TWO_PHASE_PIPELINE: {
    name: 'Two-phase Pipeline',
    description: 'Quick feedback for commits, full validation for PRs',
    impact: 'high',
    implementation: 'Separate push/PR workflows',
  },
  PARALLEL_EXECUTION: {
    name: 'Parallel Execution',
    description: 'Maximize parallelization of independent checks',
    impact: 'medium',
    implementation: 'Job dependencies and matrix strategies',
  },
  INCREMENTAL_BUILDS: {
    name: 'Incremental Builds',
    description: 'Skip unchanged parts of the build',
    impact: 'low',
    implementation: 'Build caching and conditional steps',
  },
};

/**
 * Generate optimized GitHub Actions workflow
 * @param {Object} options - Optimization options
 * @returns {string} GitHub Actions workflow YAML
 */
function generateOptimizedWorkflow(options = {}) {
  const {
    language = 'javascript',
    tier = 2,
    enableTwoPhase = true,
    enableSelectiveTests = true,
    enableTierConditionals = true,
  } = options;

  const workflow = {
    name: 'CAWS Optimized CI/CD',
    on: {
      push: { branches: ['main', 'develop'] },
      pull_request: { branches: ['main', 'develop'] },
    },
    jobs: {},
  };

  // Setup job (always runs)
  workflow.jobs.setup = {
    'runs-on': 'ubuntu-latest',
    outputs: {
      risk_tier: '${{ steps.detect.outputs.tier }}',
      changed_files: '${{ steps.detect.outputs.files }}',
      is_experimental: '${{ steps.detect.outputs.experimental }}',
    },
    steps: [
      {
        name: 'Checkout code',
        uses: 'actions/checkout@v4',
        with: { 'fetch-depth': 2 },
      },
      {
        id: 'detect',
        name: 'Detect CAWS configuration',
        run: `
          # Detect risk tier from working spec
          if [ -f .caws/working-spec.yaml ]; then
            TIER=$(grep 'risk_tier:' .caws/working-spec.yaml | cut -d':' -f2 | tr -d ' ')
            echo "tier=$TIER" >> $GITHUB_OUTPUT

            # Check for experimental mode
            if grep -q 'experimental_mode:' .caws/working-spec.yaml; then
              echo "experimental=true" >> $GITHUB_OUTPUT
            else
              echo "experimental=false" >> $GITHUB_OUTPUT
            fi
          else
            echo "tier=2" >> $GITHUB_OUTPUT
            echo "experimental=false" >> $GITHUB_OUTPUT
          fi

          # Get changed files
          if [ "$GITHUB_EVENT_NAME" = "pull_request" ]; then
            FILES=$(git diff --name-only "$GITHUB_BASE_SHA" "$GITHUB_SHA" | tr '\n' ' ')
          else
            FILES=$(git diff --name-only HEAD~1 HEAD | tr '\n' ' ')
          fi
          echo "files=$FILES" >> $GITHUB_OUTPUT
        `,
      },
    ],
  };

  // Quick feedback job (runs on every push)
  if (enableTwoPhase) {
    workflow.jobs.quick_feedback = {
      'runs-on': 'ubuntu-latest',
      needs: 'setup',
      if: "github.event_name == 'push'",
      steps: [
        {
          name: 'Checkout code',
          uses: 'actions/checkout@v4',
        },
        {
          name: 'Setup Node.js',
          uses: 'actions/setup-node@v4',
          with: { 'node-version': '18', cache: 'npm' },
        },
        {
          name: 'Install dependencies',
          run: 'npm ci',
        },
        {
          name: 'Quick lint',
          run: 'npm run lint || true',
        },
        {
          name: 'Quick tests',
          run: 'npm run test -- --passWithNoTests || true',
        },
      ],
    };
  }

  // Main validation job (runs on PR and after successful quick feedback)
  const mainJobCondition = enableTwoPhase
    ? "github.event_name == 'pull_request' || (github.event_name == 'push' && needs.quick_feedback.result == 'success')"
    : 'true';

  workflow.jobs.validate = {
    'runs-on': 'ubuntu-latest',
    needs: enableTwoPhase ? 'setup' : [],
    if: mainJobCondition,
    strategy: {
      matrix: {
        node: ['18', '20'],
      },
    },
    steps: [
      {
        name: 'Checkout code',
        uses: 'actions/checkout@v4',
        with: { 'fetch-depth': 0 },
      },
      {
        name: 'Setup Node.js ${{ matrix.node }}',
        uses: 'actions/setup-node@v4',
        with: {
          'node-version': '${{ matrix.node }}',
          cache: 'npm',
        },
      },
      {
        name: 'Install dependencies',
        run: 'npm ci',
      },
      {
        name: 'Lint code',
        run: 'npm run lint',
      },
      {
        name: 'Run tests',
        run: getTestCommand(language, tier, enableSelectiveTests),
      },
      {
        name: 'Generate coverage',
        run: getCoverageCommand(language, tier),
      },
      {
        name: 'Upload coverage',
        uses: 'codecov/codecov-action@v3',
        if: "matrix.node == '18'",
      },
    ],
  };

  // Tier-based conditional jobs
  if (enableTierConditionals) {
    // Mutation testing (only for tier 1 and 2)
    workflow.jobs.mutation_test = {
      'runs-on': 'ubuntu-latest',
      needs: ['setup', 'validate'],
      if: "(needs.setup.outputs.risk_tier == '1' || needs.setup.outputs.risk_tier == '2') && needs.setup.outputs.is_experimental == 'false'",
      steps: [
        {
          name: 'Checkout code',
          uses: 'actions/checkout@v4',
        },
        {
          name: 'Setup Node.js',
          uses: 'actions/setup-node@v4',
          with: { 'node-version': '18', cache: 'npm' },
        },
        {
          name: 'Install dependencies',
          run: 'npm ci',
        },
        {
          name: 'Run mutation tests',
          run: getMutationCommand(language, tier),
        },
      ],
    };

    // Contract tests (only for tier 1 and 2)
    workflow.jobs.contract_test = {
      'runs-on': 'ubuntu-latest',
      needs: ['setup', 'validate'],
      if: "(needs.setup.outputs.risk_tier == '1' || needs.setup.outputs.risk_tier == '2') && needs.setup.outputs.is_experimental == 'false'",
      steps: [
        {
          name: 'Checkout code',
          uses: 'actions/checkout@v4',
        },
        {
          name: 'Setup Node.js',
          uses: 'actions/setup-node@v4',
          with: { 'node-version': '18', cache: 'npm' },
        },
        {
          name: 'Install dependencies',
          run: 'npm ci',
        },
        {
          name: 'Run contract tests',
          run: getContractCommand(language, tier),
        },
      ],
    };

    // Property-based testing (only for tier 1)
    workflow.jobs.property_tests = {
      'runs-on': 'ubuntu-latest',
      needs: ['setup', 'validate'],
      if: "needs.setup.outputs.risk_tier == '1'",
      steps: [
        {
          name: 'Checkout code',
          uses: 'actions/checkout@v4',
        },
        {
          name: 'Setup Node.js',
          uses: 'actions/setup-node@v4',
          with: { 'node-version': '18', cache: 'npm' },
        },
        {
          name: 'Install dependencies',
          run: 'npm ci',
        },
        {
          name: 'Generate property tests',
          run: 'node apps/tools/caws/property-testing.js generate javascript idempotent,commutative,associative',
        },
        {
          name: 'Install property testing dependencies',
          run: 'npm install --save-dev fast-check',
        },
        {
          name: 'Run property tests',
          run: 'node apps/tools/caws/property-testing.js run javascript tests/property',
        },
      ],
    };

    // Security scan (only for tier 1)
    workflow.jobs.security_scan = {
      'runs-on': 'ubuntu-latest',
      needs: ['setup', 'validate'],
      if: "needs.setup.outputs.risk_tier == '1'",
      steps: [
        {
          name: 'Checkout code',
          uses: 'actions/checkout@v4',
        },
        {
          name: 'Run security scan',
          uses: 'securecodewarrior/github-action-sast-scan@main',
          with: {
            language: 'javascript',
          },
        },
      ],
    };

    // Performance tests (only for tier 1 and 2)
    workflow.jobs.performance_test = {
      'runs-on': 'ubuntu-latest',
      needs: ['setup', 'validate'],
      if: "(needs.setup.outputs.risk_tier == '1' || needs.setup.outputs.risk_tier == '2') && needs.setup.outputs.is_experimental == 'false'",
      steps: [
        {
          name: 'Checkout code',
          uses: 'actions/checkout@v4',
        },
        {
          name: 'Setup Node.js',
          uses: 'actions/setup-node@v4',
          with: { 'node-version': '18', cache: 'npm' },
        },
        {
          name: 'Install dependencies',
          run: 'npm ci',
        },
        {
          name: 'Run performance tests',
          run: 'npm run test:performance || true',
        },
      ],
    };
  }

  // Quality gates job
  workflow.jobs.quality_gates = {
    'runs-on': 'ubuntu-latest',
    needs: enableTierConditionals
      ? ['setup', 'validate', 'mutation_test', 'contract_test', 'property_tests'].filter(Boolean)
      : ['setup', 'validate'],
    steps: [
      {
        name: 'Checkout code',
        uses: 'actions/checkout@v4',
      },
      {
        name: 'Setup Node.js',
        uses: 'actions/setup-node@v4',
        with: { 'node-version': '18', cache: 'npm' },
      },
      {
        name: 'Run quality gates',
        run: `
          node apps/tools/caws/gates.js coverage \${{ needs.setup.outputs.risk_tier }} 85
          node apps/tools/caws/gates.js mutation \${{ needs.setup.outputs.risk_tier }} 60
          node apps/tools/caws/gates.js trust \${{ needs.setup.outputs.risk_tier }} 82
        `,
      },
    ],
  };

  return yaml.dump(workflow, { indent: 2 });
}

/**
 * Get test command based on language and optimization settings
 */
function getTestCommand(language, tier, enableSelectiveTests) {
  const baseCommands = {
    javascript: 'npm run test',
    python: 'pytest',
    java: 'mvn test',
    go: 'go test ./...',
    rust: 'cargo test',
  };

  let command = baseCommands[language] || 'npm run test';

  if (enableSelectiveTests) {
    // Add selective test execution based on changed files
    command += ' -- --findRelatedTests';
  }

  return command;
}

/**
 * Get coverage command based on language and tier
 */
function getCoverageCommand(language, _tier) {
  const commands = {
    javascript: 'npm run test:coverage',
    python: 'pytest --cov',
    java: 'mvn test jacoco:report',
    go: 'go test -coverprofile=coverage.out ./...',
    rust: 'cargo test --no-run && tarpaulin',
  };

  return commands[language] || 'echo "Coverage not configured for this language"';
}

/**
 * Get mutation testing command based on language and tier
 */
function getMutationCommand(language, _tier) {
  const commands = {
    javascript: 'npx stryker run',
    python: 'mutmut run --paths-to-mutate src/',
    java: 'mvn org.pitest:pitest-maven:mutationCoverage',
    go: 'gremlins -path .',
    rust: 'cargo mutagen',
  };

  return commands[language] || 'echo "Mutation testing not configured for this language"';
}

/**
 * Get contract testing command based on language and tier
 */
function getContractCommand(language, _tier) {
  const commands = {
    javascript: 'npm run test:contracts',
    python: 'schemathesis run --checks all http://localhost:3000/api/openapi.json',
    java: 'pact-jvm-provider-maven',
    go: 'pact-go',
    rust: 'pact-rust',
  };

  return commands[language] || 'echo "Contract testing not configured for this language"';
}

/**
 * Analyze current workflow for optimization opportunities
 * @param {string} workflowPath - Path to current workflow file
 * @returns {Object} Analysis results
 */
function analyzeCurrentWorkflow(workflowPath = '.github/workflows/ci.yml') {
  const results = {
    currentOptimizations: [],
    missingOptimizations: [],
    recommendations: [],
    estimatedTimeSavings: 0,
  };

  try {
    if (!fs.existsSync(workflowPath)) {
      results.missingOptimizations.push('No GitHub Actions workflow found');
      results.recommendations.push('Create a GitHub Actions workflow with CAWS optimizations');
      return results;
    }

    const workflowContent = fs.readFileSync(workflowPath, 'utf8');
    const workflow = yaml.load(workflowContent);

    // Check for existing optimizations
    if (workflow.jobs?.setup?.outputs) {
      results.currentOptimizations.push('Setup job with outputs');
    }

    if (workflow.on?.pull_request && workflow.on?.push) {
      results.currentOptimizations.push('Multi-trigger workflow');
    }

    if (workflow.jobs?.validate?.strategy?.matrix) {
      results.currentOptimizations.push('Matrix strategy for multi-version testing');
    }

    // Check for missing optimizations
    if (!workflow.jobs?.quick_feedback) {
      results.missingOptimizations.push('Two-phase pipeline (quick feedback)');
      results.recommendations.push('Add quick feedback job for faster iteration');
      results.estimatedTimeSavings += 30; // seconds
    }

    if (!workflow.jobs?.mutation_test?.if) {
      results.missingOptimizations.push('Tier-based conditional execution');
      results.recommendations.push('Add conditional execution based on risk tier');
      results.estimatedTimeSavings += 60; // seconds
    }

    // Calculate potential improvements
    if (results.missingOptimizations.length > 0) {
      results.estimatedTimeSavings += results.missingOptimizations.length * 20;
    }
  } catch (error) {
    results.missingOptimizations.push(`Error analyzing workflow: ${error.message}`);
  }

  return results;
}

/**
 * Generate optimization recommendations
 * @param {Object} analysis - Workflow analysis results
 * @returns {Array} Detailed recommendations
 */
function generateOptimizationRecommendations(analysis) {
  const recommendations = [];

  if (analysis.missingOptimizations.includes('Two-phase pipeline (quick feedback)')) {
    recommendations.push({
      strategy: OPTIMIZATION_STRATEGIES.TWO_PHASE_PIPELINE,
      priority: 'high',
      effort: 'medium',
      description: 'Implement quick feedback for commits and full validation for PRs',
      benefits: [
        'Faster developer feedback',
        'Reduced CI queue time',
        'Better development velocity',
      ],
      implementation: [
        'Add quick_feedback job for push events',
        'Run full validation only on pull_request events',
        'Use job dependencies to ensure proper execution order',
      ],
    });
  }

  if (analysis.missingOptimizations.includes('Tier-based conditional execution')) {
    recommendations.push({
      strategy: OPTIMIZATION_STRATEGIES.TIER_BASED_CONDITIONAL,
      priority: 'high',
      effort: 'low',
      description: 'Skip expensive checks for low-risk changes',
      benefits: [
        'Faster CI for low-risk changes',
        'Better resource utilization',
        'Maintained quality for high-risk changes',
      ],
      implementation: [
        'Add setup job to detect risk tier from working spec',
        'Use job conditions based on risk tier',
        'Skip mutation tests for Tier 3 changes',
      ],
    });
  }

  return recommendations;
}

// CLI interface
if (require.main === module) {
  const command = process.argv[2];

  switch (command) {
    case 'analyze':
      console.log('🔍 Analyzing current CI/CD setup for optimization opportunities...');

      const analysis = analyzeCurrentWorkflow();

      console.log('\n📊 Current Workflow Analysis:');
      console.log(`✅ Current optimizations: ${analysis.currentOptimizations.length}`);
      analysis.currentOptimizations.forEach((opt) => console.log(`   - ${opt}`));

      console.log(`\n❌ Missing optimizations: ${analysis.missingOptimizations.length}`);
      analysis.missingOptimizations.forEach((opt) => console.log(`   - ${opt}`));

      if (analysis.recommendations.length > 0) {
        console.log('\n💡 Quick recommendations:');
        analysis.recommendations.forEach((rec) => console.log(`   - ${rec}`));
      }

      if (analysis.estimatedTimeSavings > 0) {
        console.log(`\n⏱️  Estimated time savings: ${analysis.estimatedTimeSavings}s per run`);
      }

      const detailedRecommendations = generateOptimizationRecommendations(analysis);
      if (detailedRecommendations.length > 0) {
        console.log('\n📋 Detailed Optimization Plan:');
        detailedRecommendations.forEach((rec, index) => {
          console.log(`\n${index + 1}. ${rec.strategy.name} [${rec.priority} priority]`);
          console.log(`   ${rec.description}`);
          console.log(`   Effort: ${rec.effort} | Impact: ${rec.strategy.impact}`);
          console.log(`   Benefits: ${rec.benefits.join(', ')}`);
          console.log(`   Implementation steps:`);
          rec.implementation.forEach((step) => console.log(`     - ${step}`));
        });
      }
      break;

    case 'generate':
      const language = process.argv[3] || 'javascript';
      const tier = parseInt(process.argv[4]) || 2;
      const outputPath = process.argv[5] || '.github/workflows/caws-ci.yml';

      console.log(`🚀 Generating optimized workflow for ${language} (Tier ${tier})...`);

      try {
        const workflow = generateOptimizedWorkflow({
          language,
          tier,
          enableTwoPhase: true,
          enableSelectiveTests: true,
          enableTierConditionals: true,
        });

        // Ensure directory exists
        const dir = path.dirname(outputPath);
        if (!fs.existsSync(dir)) {
          fs.mkdirSync(dir, { recursive: true });
        }

        fs.writeFileSync(outputPath, workflow);
        console.log(`✅ Generated optimized workflow: ${outputPath}`);

        console.log('\n🔧 Next steps:');
        console.log('   1. Review the generated workflow file');
        console.log('   2. Commit and push to trigger the new pipeline');
        console.log('   3. Monitor CI performance and adjust as needed');
        console.log('   4. Consider enabling branch protection rules');
      } catch (error) {
        console.error('❌ Error generating workflow:', error.message);
        process.exit(1);
      }
      break;

    default:
      console.log('CAWS CI/CD Pipeline Optimizer');
      console.log('Usage:');
      console.log('  node ci-optimizer.js analyze [workflow-path]');
      console.log('  node ci-optimizer.js generate [language] [tier] [output-path]');
      console.log('');
      console.log('Optimization strategies:');
      Object.values(OPTIMIZATION_STRATEGIES).forEach((strategy) => {
        console.log(`  - ${strategy.name}: ${strategy.description} (${strategy.impact} impact)`);
      });
      console.log('');
      console.log('Examples:');
      console.log('  node ci-optimizer.js analyze');
      console.log('  node ci-optimizer.js generate python 2 .github/workflows/ci.yml');
      process.exit(1);
  }
}

module.exports = {
  OPTIMIZATION_STRATEGIES,
  generateOptimizedWorkflow,
  analyzeCurrentWorkflow,
  generateOptimizationRecommendations,
};
