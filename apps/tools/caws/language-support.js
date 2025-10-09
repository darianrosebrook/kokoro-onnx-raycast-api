#!/usr/bin/env node

/**
 * @fileoverview CAWS Multi-Language Support System
 * Provides pluggable quality gates and tool configurations for different programming languages
 * @author @darianrosebrook
 */

const fs = require('fs');
const path = require('path');

/**
 * Supported languages and their tool configurations
 */
const LANGUAGE_CONFIGS = {
  javascript: {
    name: 'JavaScript/TypeScript',
    extensions: ['.js', '.ts', '.jsx', '.tsx', '.mjs', '.cjs'],
    testExtensions: ['.test.js', '.test.ts', '.spec.js', '.spec.ts'],
    qualityTools: {
      unitTest: {
        commands: ['jest', 'mocha', 'vitest'],
        coverageCommand: 'jest --coverage',
        defaultCommand: 'jest',
      },
      mutationTest: {
        commands: ['stryker'],
        defaultCommand: 'stryker run',
      },
      lint: {
        commands: ['eslint'],
        defaultCommand: 'eslint .',
      },
      format: {
        commands: ['prettier'],
        defaultCommand: 'prettier --write .',
      },
      typeCheck: {
        commands: ['tsc'],
        defaultCommand: 'tsc --noEmit',
      },
      contractTest: {
        commands: ['pact'],
        defaultCommand: 'pact',
      },
    },
    coverageReports: ['coverage/lcov.info', 'coverage/coverage-final.json'],
    tierAdjustments: {
      1: { min_branch: 0.9, min_mutation: 0.7 },
      2: { min_branch: 0.8, min_mutation: 0.5 },
      3: { min_branch: 0.7, min_mutation: 0.3 },
    },
  },

  python: {
    name: 'Python',
    extensions: ['.py', '.pyw'],
    testExtensions: ['test_*.py', '*_test.py'],
    qualityTools: {
      unitTest: {
        commands: ['pytest', 'unittest'],
        coverageCommand: 'pytest --cov',
        defaultCommand: 'pytest',
      },
      mutationTest: {
        commands: ['mutmut', 'cosmic-ray'],
        defaultCommand: 'mutmut run',
      },
      lint: {
        commands: ['pylint', 'flake8', 'black'],
        defaultCommand: 'flake8 .',
      },
      format: {
        commands: ['black', 'autopep8'],
        defaultCommand: 'black .',
      },
      typeCheck: {
        commands: ['mypy'],
        defaultCommand: 'mypy .',
      },
      contractTest: {
        commands: ['schemathesis'],
        defaultCommand: 'schemathesis run',
      },
    },
    coverageReports: ['.coverage', 'coverage.xml', 'htmlcov/'],
    tierAdjustments: {
      1: { min_branch: 0.85, min_mutation: 0.6 },
      2: { min_branch: 0.75, min_mutation: 0.4 },
      3: { min_branch: 0.6, min_mutation: 0.2 },
    },
  },

  java: {
    name: 'Java',
    extensions: ['.java'],
    testExtensions: ['*Test.java', 'Test*.java'],
    qualityTools: {
      unitTest: {
        commands: ['mvn test', 'gradle test', 'junit'],
        coverageCommand: 'mvn test jacoco:report',
        defaultCommand: 'mvn test',
      },
      mutationTest: {
        commands: ['pitest', 'pitest-maven'],
        defaultCommand: 'mvn org.pitest:pitest-maven:mutationCoverage',
      },
      lint: {
        commands: ['checkstyle', 'pmd'],
        defaultCommand: 'mvn checkstyle:check',
      },
      format: {
        commands: ['google-java-format'],
        defaultCommand: 'google-java-format --replace',
      },
      contractTest: {
        commands: ['pact-jvm'],
        defaultCommand: 'pact-jvm',
      },
    },
    coverageReports: ['target/site/jacoco/', 'build/reports/jacoco/'],
    tierAdjustments: {
      1: { min_branch: 0.85, min_mutation: 0.65 },
      2: { min_branch: 0.75, min_mutation: 0.45 },
      3: { min_branch: 0.65, min_mutation: 0.25 },
    },
  },

  go: {
    name: 'Go',
    extensions: ['.go'],
    testExtensions: ['*_test.go'],
    qualityTools: {
      unitTest: {
        commands: ['go test'],
        coverageCommand: 'go test -coverprofile=coverage.out',
        defaultCommand: 'go test ./...',
      },
      mutationTest: {
        commands: ['gremlins'],
        defaultCommand: 'gremlins',
      },
      lint: {
        commands: ['golangci-lint', 'golint'],
        defaultCommand: 'golangci-lint run',
      },
      format: {
        commands: ['gofmt'],
        defaultCommand: 'gofmt -w .',
      },
      contractTest: {
        commands: ['pact-go'],
        defaultCommand: 'pact-go',
      },
    },
    coverageReports: ['coverage.out', 'coverage.html'],
    tierAdjustments: {
      1: { min_branch: 0.8, min_mutation: 0.6 },
      2: { min_branch: 0.7, min_mutation: 0.4 },
      3: { min_branch: 0.6, min_mutation: 0.2 },
    },
  },

  rust: {
    name: 'Rust',
    extensions: ['.rs'],
    testExtensions: ['*.rs'], // Rust tests are in the same files
    qualityTools: {
      unitTest: {
        commands: ['cargo test'],
        coverageCommand: 'cargo test --no-run && tarpaulin',
        defaultCommand: 'cargo test',
      },
      mutationTest: {
        commands: ['mutagen'],
        defaultCommand: 'mutagen',
      },
      lint: {
        commands: ['cargo clippy'],
        defaultCommand: 'cargo clippy',
      },
      format: {
        commands: ['cargo fmt'],
        defaultCommand: 'cargo fmt',
      },
      contractTest: {
        commands: ['pact-rust'],
        defaultCommand: 'pact-rust',
      },
    },
    coverageReports: ['cobertura.xml', 'lcov.info'],
    tierAdjustments: {
      1: { min_branch: 0.9, min_mutation: 0.7 },
      2: { min_branch: 0.8, min_mutation: 0.5 },
      3: { min_branch: 0.7, min_mutation: 0.3 },
    },
  },
};

/**
 * Detect the primary language of a project
 * @param {string} projectDir - Project directory path
 * @returns {string} Detected language key or 'unknown'
 */
function detectProjectLanguage(projectDir = process.cwd()) {
  const fileStats = {};

  // Count files by extension
  function scanDirectory(dir) {
    try {
      const files = fs.readdirSync(dir);

      files.forEach((file) => {
        const filePath = path.join(dir, file);
        const stat = fs.statSync(filePath);

        if (
          stat.isDirectory() &&
          !file.startsWith('.') &&
          file !== 'node_modules' &&
          file !== 'target'
        ) {
          scanDirectory(filePath);
        } else if (stat.isFile()) {
          const ext = path.extname(file);

          Object.keys(LANGUAGE_CONFIGS).forEach((lang) => {
            if (LANGUAGE_CONFIGS[lang].extensions.includes(ext)) {
              fileStats[lang] = (fileStats[lang] || 0) + 1;
            }
          });
        }
      });
    } catch (error) {
      // Skip directories we can't read
    }
  }

  scanDirectory(projectDir);

  // Find the language with the most files
  let maxCount = 0;
  let detectedLanguage = 'unknown';

  Object.keys(fileStats).forEach((lang) => {
    if (fileStats[lang] > maxCount) {
      maxCount = fileStats[lang];
      detectedLanguage = lang;
    }
  });

  if (detectedLanguage !== 'unknown') {
    console.log(
      `🔍 Detected project language: ${LANGUAGE_CONFIGS[detectedLanguage].name} (${fileStats[detectedLanguage]} files)`
    );
  }

  return detectedLanguage;
}

/**
 * Get quality tool configuration for a language
 * @param {string} language - Language key
 * @param {string} toolType - Type of tool (unitTest, mutationTest, etc.)
 * @returns {Object} Tool configuration
 */
function getQualityToolConfig(language, toolType) {
  const config = LANGUAGE_CONFIGS[language];
  if (!config || !config.qualityTools[toolType]) {
    return null;
  }

  return config.qualityTools[toolType];
}

/**
 * Generate CI configuration for a language
 * @param {string} language - Language key
 * @param {number} tier - Risk tier (1, 2, 3)
 * @returns {Object} CI configuration
 */
function generateCIConfig(language, tier) {
  const config = LANGUAGE_CONFIGS[language];
  if (!config) {
    throw new Error(`Unsupported language: ${language}`);
  }

  const thresholds = config.tierAdjustments[tier] || config.tierAdjustments[2];

  return {
    language,
    tier,
    thresholds,
    steps: {
      install: getInstallCommands(language),
      lint: getLintCommands(language),
      test: getTestCommands(language, tier),
      coverage: getCoverageCommands(language),
      mutation: getMutationCommands(language),
      contract: getContractCommands(language),
    },
  };
}

/**
 * Get installation commands for a language
 */
function getInstallCommands(language) {
  const configs = {
    javascript: ['npm ci', 'npm install'],
    python: [
      'python -m pip install --upgrade pip',
      'pip install -r requirements.txt',
      'pip install -r requirements-dev.txt',
    ],
    java: ['mvn dependency:resolve', './gradlew dependencies'],
    go: ['go mod download'],
    rust: ['cargo fetch'],
  };

  return configs[language] || [];
}

/**
 * Get lint commands for a language
 */
function getLintCommands(language) {
  const toolConfig = getQualityToolConfig(language, 'lint');
  return toolConfig ? [toolConfig.defaultCommand] : [];
}

/**
 * Get test commands for a language
 */
function getTestCommands(language, tier) {
  const toolConfig = getQualityToolConfig(language, 'unitTest');
  if (!toolConfig) return [];

  // Adjust test rigor based on tier
  const commands = [toolConfig.defaultCommand];

  // For higher tiers, add more comprehensive testing
  if (tier <= 2) {
    commands.push(`${toolConfig.defaultCommand} --verbose`);
  }

  return commands;
}

/**
 * Get coverage commands for a language
 */
function getCoverageCommands(language) {
  const toolConfig = getQualityToolConfig(language, 'unitTest');
  return toolConfig?.coverageCommand ? [toolConfig.coverageCommand] : [];
}

/**
 * Get mutation testing commands for a language
 */
function getMutationCommands(language) {
  const toolConfig = getQualityToolConfig(language, 'mutationTest');
  return toolConfig ? [toolConfig.defaultCommand] : [];
}

/**
 * Get contract testing commands for a language
 */
function getContractCommands(language) {
  const toolConfig = getQualityToolConfig(language, 'contractTest');
  return toolConfig ? [toolConfig.defaultCommand] : [];
}

/**
 * Generate a language-specific CAWS configuration file
 * @param {string} language - Language key
 * @param {string} configPath - Output configuration path
 */
function generateLanguageConfig(language, configPath = '.caws/language-config.json') {
  const ciConfig = generateCIConfig(language, 2); // Default to tier 2

  const config = {
    language,
    name: LANGUAGE_CONFIGS[language]?.name || 'Unknown',
    tier: ciConfig.tier,
    thresholds: ciConfig.thresholds,
    tools: {},
    generated_at: new Date().toISOString(),
  };

  // Add tool configurations
  Object.keys(LANGUAGE_CONFIGS[language]?.qualityTools || {}).forEach((toolType) => {
    const toolConfig = getQualityToolConfig(language, toolType);
    if (toolConfig) {
      config.tools[toolType] = {
        commands: toolConfig.commands,
        default: toolConfig.defaultCommand,
      };
    }
  });

  // Ensure directory exists
  const dir = path.dirname(configPath);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }

  fs.writeFileSync(configPath, JSON.stringify(config, null, 2));
  console.log(`✅ Generated language config: ${configPath}`);

  return config;
}

/**
 * Validate that required tools are installed for a language
 * @param {string} language - Language key
 * @returns {Object} Validation results
 */
function validateTooling(language) {
  const config = LANGUAGE_CONFIGS[language];
  if (!config) {
    return { valid: false, errors: [`Unsupported language: ${language}`] };
  }

  const results = {
    valid: true,
    errors: [],
    warnings: [],
    missingTools: [],
    availableTools: [],
  };

  // Check each tool type
  Object.keys(config.qualityTools).forEach((toolType) => {
    const toolConfig = config.qualityTools[toolType];

    // Check if any of the tool commands are available
    let found = false;
    toolConfig.commands.forEach((command) => {
      try {
        require('child_process').execSync(`which ${command.split(' ')[0]}`, { stdio: 'ignore' });
        found = true;
        results.availableTools.push(command);
      } catch (error) {
        // Tool not found
      }
    });

    if (!found) {
      results.missingTools.push(toolType);
      results.errors.push(`${toolType} tools not found: ${toolConfig.commands.join(', ')}`);
      results.valid = false;
    }
  });

  return results;
}

// CLI interface
if (require.main === module) {
  const command = process.argv[2];

  switch (command) {
    case 'detect':
      const language = detectProjectLanguage();
      if (language !== 'unknown') {
        console.log(`📋 Language: ${LANGUAGE_CONFIGS[language].name}`);
        console.log(`📁 Extensions: ${LANGUAGE_CONFIGS[language].extensions.join(', ')}`);
        console.log(`🧪 Test patterns: ${LANGUAGE_CONFIGS[language].testExtensions.join(', ')}`);
      } else {
        console.log('❌ Could not detect project language');
        process.exit(1);
      }
      break;

    case 'config':
      const targetLanguage = process.argv[3] || detectProjectLanguage();
      const tier = parseInt(process.argv[4]) || 2;
      const configPath = process.argv[5] || '.caws/language-config.json';

      if (targetLanguage === 'unknown') {
        console.error('❌ Unknown or unsupported language');
        process.exit(1);
      }

      generateLanguageConfig(targetLanguage, configPath);
      console.log(
        `📋 Generated config for ${LANGUAGE_CONFIGS[targetLanguage].name} (Tier ${tier})`
      );
      break;

    case 'validate':
      const langToValidate = process.argv[3] || detectProjectLanguage();

      if (langToValidate === 'unknown') {
        console.error('❌ Cannot validate tooling for unknown language');
        process.exit(1);
      }

      console.log(`🔍 Validating tooling for ${LANGUAGE_CONFIGS[langToValidate].name}...`);
      const validation = validateTooling(langToValidate);

      if (validation.errors.length > 0) {
        console.error('\n❌ Tooling validation failed:');
        validation.errors.forEach((error) => console.error(`   - ${error}`));
      }

      if (validation.warnings.length > 0) {
        console.warn('\n⚠️  Tooling warnings:');
        validation.warnings.forEach((warning) => console.warn(`   - ${warning}`));
      }

      if (validation.missingTools.length > 0) {
        console.log('\n💡 To install missing tools:');
        validation.missingTools.forEach((toolType) => {
          const toolConfig = getQualityToolConfig(langToValidate, toolType);
          console.log(
            `   ${toolType}: ${toolConfig.commands[0]} (or alternatives: ${toolConfig.commands.slice(1).join(', ')})`
          );
        });
      }

      if (validation.valid) {
        console.log('✅ All required tools are available');
      }

      process.exit(validation.valid ? 0 : 1);
      break;

    case 'ci':
      const ciLanguage = process.argv[3] || detectProjectLanguage();
      const ciTier = parseInt(process.argv[4]) || 2;

      if (ciLanguage === 'unknown') {
        console.error('❌ Cannot generate CI config for unknown language');
        process.exit(1);
      }

      const ciConfig = generateCIConfig(ciLanguage, ciTier);
      console.log(`📋 CI Configuration for ${LANGUAGE_CONFIGS[ciLanguage].name} (Tier ${ciTier}):`);
      console.log(
        `   Thresholds: Branch ≥${ciConfig.thresholds.min_branch * 100}%, Mutation ≥${ciConfig.thresholds.min_mutation * 100}%`
      );

      console.log('\n🔧 Installation steps:');
      ciConfig.steps.install.forEach((cmd) => console.log(`   - ${cmd}`));

      console.log('\n🧪 Test steps:');
      ciConfig.steps.test.forEach((cmd) => console.log(`   - ${cmd}`));

      if (ciConfig.steps.mutation.length > 0) {
        console.log('\n🧬 Mutation testing:');
        ciConfig.steps.mutation.forEach((cmd) => console.log(`   - ${cmd}`));
      }
      break;

    default:
      console.log('CAWS Multi-Language Support Tool');
      console.log('Usage:');
      console.log('  node language-support.js detect');
      console.log('  node language-support.js config [language] [tier] [output-path]');
      console.log('  node language-support.js validate [language]');
      console.log('  node language-support.js ci [language] [tier]');
      console.log('');
      console.log('Supported languages:');
      Object.keys(LANGUAGE_CONFIGS).forEach((lang) => {
        console.log(`  - ${lang}: ${LANGUAGE_CONFIGS[lang].name}`);
      });
      console.log('');
      console.log('Examples:');
      console.log('  node language-support.js detect');
      console.log('  node language-support.js config python 2');
      console.log('  node language-support.js validate javascript');
      process.exit(1);
  }
}

module.exports = {
  LANGUAGE_CONFIGS,
  detectProjectLanguage,
  getQualityToolConfig,
  generateCIConfig,
  validateTooling,
  generateLanguageConfig,
};
