#!/usr/bin/env node

/**
 * @fileoverview CAWS Property-Based Testing Integration
 * Generates and runs property-based tests for enhanced test coverage
 * @author @darianrosebrook
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

/**
 * Property-based testing configurations for different languages
 */
const PROPERTY_TESTING_CONFIGS = {
  javascript: {
    library: 'fast-check',
    setup: {
      install: 'npm install --save-dev fast-check',
      import: "import fc from 'fast-check';",
      runner: 'npm test',
    },
    templates: {
      number: (propertyName) => `
describe('${propertyName}', () => {
  test('should satisfy ${propertyName}', () => {
    fc.assert(
      fc.property(
        fc.integer(),
        fc.string(),
        (a, b) => {
          // Property: ${propertyName}
          // Implement your property here
          return true; // Replace with actual property
        }
      )
    );
  });
});`,

      array: (propertyName) => `
describe('${propertyName}', () => {
  test('should satisfy ${propertyName}', () => {
    fc.assert(
      fc.property(
        fc.array(fc.integer()),
        (arr) => {
          // Property: ${propertyName}
          // Implement your property here
          return true; // Replace with actual property
        }
      )
    );
  });
});`,

      object: (propertyName) => `
describe('${propertyName}', () => {
  test('should satisfy ${propertyName}', () => {
    fc.assert(
      fc.property(
        fc.record({
          id: fc.integer(),
          name: fc.string(),
          active: fc.boolean()
        }),
        (obj) => {
          // Property: ${propertyName}
          // Implement your property here
          return true; // Replace with actual property
        }
      )
    );
  });
});`,
    },
  },

  python: {
    library: 'hypothesis',
    setup: {
      install: 'pip install hypothesis',
      import: 'from hypothesis import given, strategies as st',
      runner: 'pytest',
    },
    templates: {
      number: (propertyName) => `
@given(st.integers(), st.text())
def test_${propertyName.replace(/\s+/g, '_').toLowerCase()}(a, b):
    # Property: ${propertyName}
    # Implement your property here
    assert True  # Replace with actual property`,

      array: (propertyName) => `
@given(st.lists(st.integers()))
def test_${propertyName.replace(/\s+/g, '_').toLowerCase()}(arr):
    # Property: ${propertyName}
    # Implement your property here
    assert True  # Replace with actual property`,

      object: (propertyName) => `
@given(st.fixed_dictionaries({
    'id': st.integers(),
    'name': st.text(),
    'active': st.booleans()
}))
def test_${propertyName.replace(/\s+/g, '_').toLowerCase()}(obj):
    # Property: ${propertyName}
    # Implement your property here
    assert True  # Replace with actual property`,
    },
  },

  java: {
    library: 'jqwik',
    setup: {
      install: 'implementation "net.jqwik:jqwik:1.7.4"',
      import: 'import net.jqwik.api.*;',
      runner: './gradlew test',
    },
    templates: {
      number: (propertyName) => `
@Property
boolean ${propertyName.replace(/\s+/g, '_').toLowerCase()}(
    @ForAll int a,
    @ForAll String b) {
    // Property: ${propertyName}
    // Implement your property here
    return true; // Replace with actual property
}`,

      array: (propertyName) => `
@Property
boolean ${propertyName.replace(/\s+/g, '_').toLowerCase()}(
    @ForAll List<Integer> arr) {
    // Property: ${propertyName}
    // Implement your property here
    return true; // Replace with actual property
}`,

      object: (propertyName) => `
@Property
boolean ${propertyName.replace(/\s+/g, '_').toLowerCase()}(
    @ForAll("person") Person person) {
    // Property: ${propertyName}
    // Implement your property here
    return true; // Replace with actual property
}

@Provide
Arbitrary<Person> person() {
    return Combinators.combine(Person::new)
        .with(Arbitraries.integers())
        .with(Arbitraries.strings())
        .with(Arbitraries.of(true, false));
}`,
    },
  },
};

/**
 * Common property types that should be tested
 */
const COMMON_PROPERTIES = {
  idempotent: {
    name: 'Idempotent operations',
    description:
      'Running the same operation multiple times should have the same effect as running it once',
    examples: ['sorting algorithms', 'normalization functions', 'cleanup operations'],
  },

  commutative: {
    name: 'Commutative operations',
    description: 'Order of operations should not matter',
    examples: ['addition', 'set operations', 'string concatenation'],
  },

  associative: {
    name: 'Associative operations',
    description: 'Grouping of operations should not matter',
    examples: ['addition', 'multiplication', 'function composition'],
  },

  inverse: {
    name: 'Inverse operations',
    description: 'Operations should have meaningful inverses',
    examples: ['encode/decode', 'encrypt/decrypt', 'parse/format'],
  },

  monotonic: {
    name: 'Monotonic functions',
    description: 'Functions should preserve or reverse order',
    examples: ['sorting functions', 'comparison operations'],
  },

  roundtrip: {
    name: 'Roundtrip consistency',
    description: 'Convert to another format and back should preserve original',
    examples: ['serialization/deserialization', 'encoding/decoding'],
  },

  error_handling: {
    name: 'Error handling',
    description: 'Invalid inputs should be handled gracefully',
    examples: ['null/undefined checks', 'boundary conditions', 'invalid formats'],
  },
};

/**
 * Generate property-based tests for a given language and properties
 * @param {string} language - Target language (javascript, python, java)
 * @param {Array} properties - List of property names to generate tests for
 * @param {string} outputDir - Output directory for test files
 */
function generatePropertyTests(language, properties, outputDir = 'tests/property') {
  const config = PROPERTY_TESTING_CONFIGS[language];
  if (!config) {
    throw new Error(`Unsupported language: ${language}`);
  }

  console.log(`🔧 Generating property-based tests for ${language}...`);

  // Ensure output directory exists
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  // Generate setup file
  generateSetupFile(language, outputDir);

  // Generate tests for each property type
  properties.forEach((propertyName) => {
    const property = COMMON_PROPERTIES[propertyName];
    if (!property) {
      console.warn(`⚠️  Unknown property: ${propertyName}`);
      return;
    }

    const templateKey = inferTemplateType(property);
    const testContent = config.templates[templateKey](property.name);

    const fileName = `${propertyName}.test.${getFileExtension(language)}`;
    const filePath = path.join(outputDir, fileName);

    // Add property description as comments
    const enhancedContent = `/**
 * Property-based test: ${property.name}
 * Description: ${property.description}
 * Examples: ${property.examples.join(', ')}
 */

${testContent}`;

    fs.writeFileSync(filePath, enhancedContent);
    console.log(`✅ Generated ${propertyName} test: ${filePath}`);
  });

  // Generate README
  generatePropertyTestingReadme(language, properties, outputDir);
}

/**
 * Infer template type from property description
 */
function inferTemplateType(property) {
  if (property.examples.some((ex) => ex.includes('array') || ex.includes('list'))) {
    return 'array';
  }
  if (property.examples.some((ex) => ex.includes('object') || ex.includes('record'))) {
    return 'object';
  }
  return 'number'; // Default
}

/**
 * Get file extension for language
 */
function getFileExtension(language) {
  const extensions = {
    javascript: 'js',
    python: 'py',
    java: 'java',
  };
  return extensions[language] || 'js';
}

/**
 * Generate setup file for property-based testing
 */
function generateSetupFile(language, outputDir) {
  const config = PROPERTY_TESTING_CONFIGS[language];

  let setupContent = '';

  switch (language) {
    case 'javascript':
      setupContent = `// Property-based testing setup for JavaScript
// Run: ${config.setup.install}

${config.setup.import}

// Configure fast-check for better shrinking and debugging
fc.configureGlobal({
  verbose: true,
  seed: 42,
  numRuns: 100 // Increase for production
});

module.exports = { fc };
`;
      break;

    case 'python':
      setupContent = `# Property-based testing setup for Python
# Run: ${config.setup.install}

${config.setup.import}

# Configure hypothesis for better test runs
settings.register_profile("ci", settings(max_examples=1000))
settings.load_profile("ci")
`;
      break;

    case 'java':
      setupContent = `// Property-based testing setup for Java
// Add to build.gradle: ${config.setup.install}

${config.setup.import}

// Configure jqwik for better test runs
@Configure
class JqwikConfiguration {
    @Provide
    Arbitrary<Integer> integers() {
        return Arbitraries.integers().between(-1000, 1000);
    }

    @Provide
    Arbitrary<String> strings() {
        return Arbitraries.strings().withLength(0, 50);
    }
}
`;
      break;
  }

  const setupPath = path.join(outputDir, `setup.${getFileExtension(language)}`);
  fs.writeFileSync(setupPath, setupContent);
  console.log(`✅ Generated setup file: ${setupPath}`);
}

/**
 * Generate README for property-based testing
 */
function generatePropertyTestingReadme(language, properties, outputDir) {
  const config = PROPERTY_TESTING_CONFIGS[language];

  const readmeContent = `# Property-Based Testing

This directory contains property-based tests generated by CAWS.

## Setup

1. Install dependencies:
   \`\`\`bash
   ${config.setup.install}
   \`\`\`

2. Run property tests:
   \`\`\`bash
   ${config.setup.runner}
   \`\`\`

## Generated Properties

${properties.map((prop) => `- **${COMMON_PROPERTIES[prop].name}**: ${COMMON_PROPERTIES[prop].description}`).join('\n')}

## Understanding Properties

### Idempotent Operations
An operation is idempotent if running it multiple times has the same effect as running it once.

### Commutative Operations
Order doesn't matter - f(a, b) = f(b, a)

### Associative Operations
Grouping doesn't matter - f(f(a, b), c) = f(a, f(b, c))

### Inverse Operations
Operations should have meaningful inverses that restore original state

## Tips for Writing Properties

1. **Start Simple**: Begin with obvious properties, then add more complex ones
2. **Use Generators**: Create appropriate input generators for your domain
3. **Handle Edge Cases**: Ensure properties work with null, empty, and boundary values
4. **Document Assumptions**: Clearly state what your property assumes about inputs

## Examples

\`\`\`${language}
${config.templates.number('Example property')}
\`\`\`
`;

  fs.writeFileSync(path.join(outputDir, 'README.md'), readmeContent);
  console.log(`✅ Generated README: ${path.join(outputDir, 'README.md')}`);
}

/**
 * Run property-based tests and analyze results
 * @param {string} language - Target language
 * @param {string} testDir - Test directory
 * @returns {Object} Test results
 */
function runPropertyTests(language, testDir = 'tests/property') {
  const config = PROPERTY_TESTING_CONFIGS[language];
  if (!config) {
    throw new Error(`Unsupported language: ${language}`);
  }

  console.log(`🧪 Running property-based tests for ${language}...`);

  const results = {
    total: 0,
    passed: 0,
    failed: 0,
    errors: [],
    coverage: {},
  };

  try {
    // Check if test files exist
    if (!fs.existsSync(testDir)) {
      results.errors.push(`Test directory not found: ${testDir}`);
      return results;
    }

    const testFiles = fs
      .readdirSync(testDir)
      .filter(
        (file) =>
          file.endsWith(`.test.${getFileExtension(language)}`) ||
          file.endsWith(`_test.${getFileExtension(language)}`)
      );

    if (testFiles.length === 0) {
      results.errors.push(`No property test files found in ${testDir}`);
      return results;
    }

    // Run tests based on language
    let testOutput;
    try {
      switch (language) {
        case 'javascript':
          testOutput = execSync(`${config.setup.runner} -- --testPathPattern=property`, {
            encoding: 'utf8',
            cwd: process.cwd(),
          });
          break;
        case 'python':
          testOutput = execSync(`${config.setup.runner} ${testDir}`, {
            encoding: 'utf8',
            cwd: process.cwd(),
          });
          break;
        case 'java':
          testOutput = execSync(config.setup.runner, {
            encoding: 'utf8',
            cwd: process.cwd(),
          });
          break;
      }

      // Parse test output
      results.total = (testOutput.match(/test|spec/g) || []).length;
      results.passed = (testOutput.match(/✓|passed|ok/g) || []).length;
      results.failed = (testOutput.match(/✗|failed|error/g) || []).length;
    } catch (error) {
      results.errors.push(`Test execution failed: ${error.message}`);
      results.failed = testFiles.length; // Assume all failed if execution failed
    }
  } catch (error) {
    results.errors.push(`Error running property tests: ${error.message}`);
  }

  return results;
}

/**
 * Analyze property testing coverage and suggest improvements
 * @param {Object} testResults - Results from runPropertyTests
 * @param {Array} implementedProperties - List of implemented properties
 * @returns {Object} Coverage analysis
 */
function analyzePropertyCoverage(testResults, implementedProperties) {
  const analysis = {
    coverage_score: 0,
    missing_properties: [],
    recommendations: [],
    strengths: [],
    weaknesses: [],
  };

  if (testResults.total === 0) {
    analysis.missing_properties = Object.keys(COMMON_PROPERTIES);
    analysis.recommendations.push('No property tests implemented');
    return analysis;
  }

  // Calculate coverage score
  const implementedSet = new Set(implementedProperties);
  const totalProperties = Object.keys(COMMON_PROPERTIES).length;
  analysis.coverage_score = (implementedSet.size / totalProperties) * 100;

  // Find missing properties
  Object.keys(COMMON_PROPERTIES).forEach((prop) => {
    if (!implementedSet.has(prop)) {
      analysis.missing_properties.push(prop);
    }
  });

  // Generate recommendations
  if (analysis.missing_properties.length > 0) {
    analysis.recommendations.push(
      `Missing ${analysis.missing_properties.length} property types: ${analysis.missing_properties.join(', ')}`
    );
  }

  if (testResults.failed > 0) {
    analysis.weaknesses.push(`${testResults.failed} property tests are failing`);
    analysis.recommendations.push('Fix failing property tests and strengthen property definitions');
  }

  if (testResults.passed > 0) {
    analysis.strengths.push(`${testResults.passed} property tests are passing`);
  }

  if (analysis.coverage_score >= 80) {
    analysis.strengths.push('Good property coverage');
  } else if (analysis.coverage_score >= 50) {
    analysis.recommendations.push('Consider adding more property types for better coverage');
  } else {
    analysis.recommendations.push(
      'Property testing coverage is low - prioritize adding key properties'
    );
  }

  return analysis;
}

// CLI interface
if (require.main === module) {
  const command = process.argv[2];

  switch (command) {
    case 'generate':
      const language = process.argv[3] || 'javascript';
      const properties = process.argv[4]
        ? process.argv[4].split(',')
        : ['idempotent', 'commutative'];
      const outputDir = process.argv[5] || 'tests/property';

      if (!PROPERTY_TESTING_CONFIGS[language]) {
        console.error(`❌ Unsupported language: ${language}`);
        console.error(`Supported languages: ${Object.keys(PROPERTY_TESTING_CONFIGS).join(', ')}`);
        process.exit(1);
      }

      try {
        generatePropertyTests(language, properties, outputDir);
        console.log(`\n🎯 Generated property-based tests for ${language}`);
        console.log(`Properties: ${properties.join(', ')}`);
        console.log(`Output directory: ${outputDir}`);
      } catch (error) {
        console.error(`❌ Error generating property tests: ${error.message}`);
        process.exit(1);
      }
      break;

    case 'run':
      const runLanguage = process.argv[3] || 'javascript';
      const testDir = process.argv[4] || 'tests/property';

      try {
        const results = runPropertyTests(runLanguage, testDir);

        console.log('\n🧪 Property Test Results:');
        console.log(`   Total: ${results.total}`);
        console.log(`   Passed: ${results.passed}`);
        console.log(`   Failed: ${results.failed}`);

        if (results.errors.length > 0) {
          console.log('\n❌ Errors:');
          results.errors.forEach((error) => console.log(`   - ${error}`));
        }

        if (results.failed > 0) {
          console.error(`\n❌ ${results.failed} property tests failed`);
          process.exit(1);
        } else if (results.passed === 0) {
          console.warn('⚠️  No property tests passed');
          process.exit(1);
        } else {
          console.log('✅ All property tests passed');
        }
      } catch (error) {
        console.error(`❌ Error running property tests: ${error.message}`);
        process.exit(1);
      }
      break;

    case 'analyze':
      const analyzeLanguage = process.argv[3] || 'javascript';
      const testResultsArg = process.argv[4] || 'tests/property';
      const implementedProps = process.argv[5] ? process.argv[5].split(',') : [];

      try {
        // Run tests first if not provided
        let results;
        if (typeof testResultsArg === 'string' && fs.existsSync(testResultsArg)) {
          results = runPropertyTests(analyzeLanguage, testResultsArg);
        } else {
          // Assume test results are passed as arguments
          results = {
            total: parseInt(process.argv[4]) || 0,
            passed: parseInt(process.argv[5]) || 0,
            failed: parseInt(process.argv[6]) || 0,
            errors: [],
          };
        }

        const coverage = analyzePropertyCoverage(results, implementedProps);

        console.log('\n📊 Property Testing Coverage Analysis:');
        console.log(`   Coverage Score: ${Math.round(coverage.coverage_score)}/100`);

        if (coverage.strengths.length > 0) {
          console.log('\n✅ Strengths:');
          coverage.strengths.forEach((strength) => console.log(`   - ${strength}`));
        }

        if (coverage.weaknesses.length > 0) {
          console.log('\n⚠️  Weaknesses:');
          coverage.weaknesses.forEach((weakness) => console.log(`   - ${weakness}`));
        }

        if (coverage.missing_properties.length > 0) {
          console.log('\n📋 Missing Properties:');
          coverage.missing_properties.forEach((prop) => {
            const property = COMMON_PROPERTIES[prop];
            console.log(`   - ${property.name}: ${property.description}`);
          });
        }

        if (coverage.recommendations.length > 0) {
          console.log('\n💡 Recommendations:');
          coverage.recommendations.forEach((rec) => console.log(`   - ${rec}`));
        }

        if (coverage.coverage_score < 70) {
          console.error(
            `\n❌ Property testing coverage too low: ${Math.round(coverage.coverage_score)}/100`
          );
          process.exit(1);
        }
      } catch (error) {
        console.error(`❌ Error analyzing property coverage: ${error.message}`);
        process.exit(1);
      }
      break;

    default:
      console.log('CAWS Property-Based Testing Tool');
      console.log('Usage:');
      console.log('  node property-testing.js generate <language> [properties] [output-dir]');
      console.log('  node property-testing.js run <language> [test-dir]');
      console.log('  node property-testing.js analyze <language> [test-dir] [properties]');
      console.log('');
      console.log('Supported languages:');
      Object.keys(PROPERTY_TESTING_CONFIGS).forEach((lang) => {
        console.log(`  - ${lang}: ${PROPERTY_TESTING_CONFIGS[lang].library}`);
      });
      console.log('');
      console.log('Available properties:');
      Object.keys(COMMON_PROPERTIES).forEach((prop) => {
        console.log(`  - ${prop}: ${COMMON_PROPERTIES[prop].name}`);
      });
      console.log('');
      console.log('Examples:');
      console.log('  node property-testing.js generate javascript idempotent,commutative');
      console.log('  node property-testing.js run python tests/property');
      console.log('  node property-testing.js analyze java 5 3 2');
      process.exit(1);
  }
}

module.exports = {
  generatePropertyTests,
  runPropertyTests,
  analyzePropertyCoverage,
  COMMON_PROPERTIES,
  PROPERTY_TESTING_CONFIGS,
};
