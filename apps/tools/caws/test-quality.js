#!/usr/bin/env node

/**
 * @fileoverview CAWS Test Quality Analyzer
 * Analyzes test files for meaningful assertions and quality indicators beyond coverage
 * @author @darianrosebrook
 */

const fs = require("fs");
const path = require("path");

/**
 * Test quality scoring criteria
 */
const QUALITY_CRITERIA = {
  ASSERTION_DENSITY: {
    weight: 0.25,
    description: "Ratio of assertions to test functions",
    thresholds: { excellent: 0.8, good: 0.6, poor: 0.3 },
  },
  EDGE_CASE_COVERAGE: {
    weight: 0.2,
    description: "Coverage of edge cases and error conditions",
    thresholds: { excellent: 0.7, good: 0.5, poor: 0.2 },
  },
  DESCRIPTIVE_NAMING: {
    weight: 0.15,
    description: "Quality of test names and descriptions",
    thresholds: { excellent: 0.8, good: 0.6, poor: 0.3 },
  },
  SETUP_TEARDOWN: {
    weight: 0.1,
    description: "Proper test setup and teardown",
    thresholds: { excellent: 0.9, good: 0.7, poor: 0.4 },
  },
  MOCKING_QUALITY: {
    weight: 0.15,
    description: "Appropriate use of mocks and test doubles",
    thresholds: { excellent: 0.8, good: 0.6, poor: 0.3 },
  },
  SPEC_COVERAGE: {
    weight: 0.15,
    description: "Alignment with acceptance criteria from working spec",
    thresholds: { excellent: 0.9, good: 0.7, poor: 0.4 },
  },
};

/**
 * Analyze a single test file for quality metrics
 * @param {string} filePath - Path to test file
 * @param {Object} _spec - Working specification for spec coverage check
 * @returns {Object} Quality analysis results
 */
function analyzeTestFile(filePath, _spec = null) {
  let content = "";
  let language = "javascript";

  // Determine language from file extension
  const ext = path.extname(filePath);
  if (ext === ".py") {
    language = "python";
  } else if (ext === ".java") {
    language = "java";
  } else if (ext === ".js" || ext === ".ts") {
    language = "javascript";
  }

  try {
    content = fs.readFileSync(filePath, "utf8");
  } catch (error) {
    console.warn(`⚠️  Could not read test file: ${filePath}`);
    return null;
  }

  const lines = content.split("\n");
  const analysis = {
    file: path.basename(filePath),
    language,
    totalLines: lines.length,
    testFunctions: 0,
    assertions: 0,
    edgeCases: 0,
    descriptiveNames: 0,
    properSetup: false,
    properTeardown: false,
    mocksUsed: false,
    specAlignment: 0,
    issues: [],
  };

  // Language-specific analysis
  switch (language) {
    case "javascript":
      analyzeJavaScriptTest(content, lines, analysis, _spec);
      break;
    case "python":
      analyzePythonTest(content, lines, analysis, _spec);
      break;
    case "java":
      analyzeJavaTest(content, lines, analysis, _spec);
      break;
  }

  return analysis;
}

/**
 * Analyze JavaScript/TypeScript test file
 */
function analyzeJavaScriptTest(content, lines, analysis, _spec) {
  // Count test functions (describe/it/test blocks in Jest/Mocha)
  const testPatterns = [
    /\b(describe|it|test)\s*\(/g,
    /\btest\s*\(\s*['"`][^'"`]*['"`]/g,
  ];

  testPatterns.forEach((pattern) => {
    const matches = content.match(pattern);
    if (matches) {
      analysis.testFunctions += matches.length;
    }
  });

  // Count assertions
  const assertionPatterns = [
    /\.toBe\s*\(/g,
    /\.toEqual\s*\(/g,
    /\.toContain\s*\(/g,
    /\.toHaveBeenCalled/g,
    /\.toHaveBeenCalledWith/g,
    /\bexpect\s*\(/g,
    /\bassert\s*\(/g,
    /\bshould\s*\(/g,
  ];

  assertionPatterns.forEach((pattern) => {
    const matches = content.match(pattern);
    if (matches) {
      analysis.assertions += matches.length;
    }
  });

  // Check for edge cases (error conditions, null/undefined, boundaries)
  const edgeCasePatterns = [
    /catch\s*\(/g,
    /throw\s+/g,
    /Error\s*\(/g,
    /null\s*,?\s*undefined/g,
    /boundary|edge|limit|extreme/g,
    /invalid|malformed|corrupt/g,
  ];

  edgeCasePatterns.forEach((pattern) => {
    const matches = content.match(pattern);
    if (matches) {
      analysis.edgeCases += matches.length;
    }
  });

  // Check for descriptive naming
  const describeBlocks = content.match(/describe\s*\(\s*['"`]([^'"`]+)['"`]/g);
  if (describeBlocks) {
    describeBlocks.forEach((block) => {
      if (block.length > 20 && !/\btest|spec|should\b/.test(block)) {
        analysis.descriptiveNames++;
      }
    });
  }

  // Check for setup/teardown
  analysis.properSetup = /\bbeforeEach|beforeAll|setup\b/.test(content);
  analysis.properTeardown = /\bafterEach|afterAll|teardown\b/.test(content);

  // Check for mocking
  analysis.mocksUsed = /\b(mock|spy|stub|jest\.mock|sinon\.)/.test(content);

  // Check spec alignment if spec provided
  if (_spec && _spec.acceptance) {
    const specKeywords = _spec.acceptance
      .flatMap((ac) => [ac.given, ac.when, ac.then].filter(Boolean))
      .join(" ")
      .toLowerCase();

    const testContent = content.toLowerCase();
    const matchedTerms = specKeywords
      .split(/\s+/)
      .filter((term) => term.length > 3 && testContent.includes(term)).length;

    analysis.specAlignment = Math.min(
      matchedTerms / Math.max(specKeywords.split(/\s+/).length, 1),
      1
    );
  }

  // Identify issues
  if (
    analysis.testFunctions > 0 &&
    analysis.assertions / analysis.testFunctions < 0.5
  ) {
    analysis.issues.push(
      "Low assertion density - tests may not be properly validating behavior"
    );
  }

  if (analysis.edgeCases === 0 && analysis.testFunctions > 3) {
    analysis.issues.push(
      "No edge case testing detected - consider adding error condition tests"
    );
  }

  if (!analysis.properSetup && analysis.testFunctions > 5) {
    analysis.issues.push(
      "Missing test setup - consider using beforeEach for common setup"
    );
  }

  if (!analysis.mocksUsed && /\bimport.*from/.test(content)) {
    analysis.issues.push(
      "External dependencies detected but no mocking - consider adding mocks for better isolation"
    );
  }
}

/**
 * Analyze Python test file
 */
function analyzePythonTest(content, lines, analysis, _spec) {
  // Count test functions
  const testMatches = content.match(/\bdef\s+test_\w+/g);
  analysis.testFunctions = testMatches ? testMatches.length : 0;

  // Count assertions
  const assertionPatterns = [
    /\bassert\s+/g,
    /\bself\.assert/g,
    /\bassertEqual\b/g,
    /\bassertTrue\b/g,
    /\bassertFalse\b/g,
    /\bassertRaises\b/g,
    /\bassertIn\b/g,
    /\bassertIsNone\b/g,
  ];

  assertionPatterns.forEach((pattern) => {
    const matches = content.match(pattern);
    if (matches) {
      analysis.assertions += matches.length;
    }
  });

  // Check for edge cases
  const edgeCasePatterns = [
    /with\s+pytest\.raises/g,
    /try:\s*except/g,
    /ValueError|TypeError|Exception/g,
    /None\s*,?\s*null/g,
    /boundary|edge|limit|extreme/g,
    /invalid|malformed|corrupt/g,
  ];

  edgeCasePatterns.forEach((pattern) => {
    const matches = content.match(pattern);
    if (matches) {
      analysis.edgeCases += matches.length;
    }
  });

  // Check for descriptive naming
  const classMatches = content.match(/class\s+Test\w+/g);
  if (classMatches) {
    classMatches.forEach((className) => {
      if (className.length > 8 && !/\bTest\b/.test(className)) {
        analysis.descriptiveNames++;
      }
    });
  }

  // Check for setup/teardown
  analysis.properSetup = /\bsetUp\b|\bfixtures?\b/.test(content);
  analysis.properTeardown = /\btearDown\b/.test(content);

  // Check for mocking
  analysis.mocksUsed = /\b(mocking|patch|MagicMock|Mock)\b/.test(content);
}

/**
 * Analyze Java test file
 */
function analyzeJavaTest(content, lines, analysis, _spec) {
  // Count test methods
  const testMatches = content.match(/@\w*Test\s*public\s+void\s+\w+/g);
  analysis.testFunctions = testMatches ? testMatches.length : 0;

  // Count assertions
  const assertionPatterns = [
    /\bassert/g,
    /\bfail\s*\(/g,
    /\bAssert\.assert/g,
    /\bAssertions\.assert/g,
  ];

  assertionPatterns.forEach((pattern) => {
    const matches = content.match(pattern);
    if (matches) {
      analysis.assertions += matches.length;
    }
  });

  // Check for edge cases
  const edgeCasePatterns = [
    /@Test.*expected\s*=/g,
    /try\s*{\s*.*\s*}\s*catch/g,
    /Exception|Error/g,
    /null\s*,?\s*boundary/g,
    /invalid|malformed|corrupt/g,
  ];

  edgeCasePatterns.forEach((pattern) => {
    const matches = content.match(pattern);
    if (matches) {
      analysis.edgeCases += matches.length;
    }
  });

  // Check for setup/teardown
  analysis.properSetup = /@BeforeEach|@Before/.test(content);
  analysis.properTeardown = /@AfterEach|@After/.test(content);

  // Check for mocking
  analysis.mocksUsed = /@Mock|Mockito|when\(|verify\(/.test(content);
}

/**
 * Calculate overall quality score for a test file
 * @param {Object} analysis - Test analysis results
 * @returns {number} Quality score (0-100)
 */
function calculateQualityScore(analysis) {
  if (analysis.testFunctions === 0) return 0;

  const scores = {};

  // Assertion density score
  const assertionDensity =
    analysis.testFunctions > 0
      ? analysis.assertions / analysis.testFunctions
      : 0;
  scores.assertionDensity = normalizeScore(
    assertionDensity,
    QUALITY_CRITERIA.ASSERTION_DENSITY.thresholds
  );

  // Edge case coverage score
  const edgeCaseRatio =
    analysis.testFunctions > 0
      ? analysis.edgeCases / analysis.testFunctions
      : 0;
  scores.edgeCaseCoverage = normalizeScore(
    edgeCaseRatio,
    QUALITY_CRITERIA.EDGE_CASE_COVERAGE.thresholds
  );

  // TODO: Implement comprehensive test naming quality analysis
  // - [ ] Implement natural language processing for test name analysis
  // - [ ] Add pattern recognition for good/bad naming conventions
  // - [ ] Calculate naming quality based on clarity, specificity, and descriptiveness
  // - [ ] Add machine learning model for automated naming quality scoring
  // - [ ] Implement test naming guidelines enforcement and suggestions
  const namingScore = analysis.descriptiveNames > 0 ? 1 : 0.5;
  scores.descriptiveNaming = normalizeScore(
    namingScore,
    QUALITY_CRITERIA.DESCRIPTIVE_NAMING.thresholds
  );

  // Setup/teardown score
  const setupScore =
    (analysis.properSetup ? 0.5 : 0) + (analysis.properTeardown ? 0.5 : 0);
  scores.setupTeardown = normalizeScore(
    setupScore,
    QUALITY_CRITERIA.SETUP_TEARDOWN.thresholds
  );

  // Mocking quality score
  scores.mockingQuality = analysis.mocksUsed
    ? normalizeScore(0.8, QUALITY_CRITERIA.MOCKING_QUALITY.thresholds)
    : normalizeScore(0.3, QUALITY_CRITERIA.MOCKING_QUALITY.thresholds);

  // Spec alignment score
  scores.specCoverage = normalizeScore(
    analysis.specAlignment,
    QUALITY_CRITERIA.SPEC_COVERAGE.thresholds
  );

  // Calculate weighted score
  let totalScore = 0;
  Object.keys(QUALITY_CRITERIA).forEach((criterion) => {
    totalScore +=
      scores[criterion.toLowerCase()] * QUALITY_CRITERIA[criterion].weight;
  });

  return Math.round(totalScore * 100);
}

/**
 * Normalize a raw score to 0-1 scale based on thresholds
 */
function normalizeScore(value, thresholds) {
  if (value >= thresholds.excellent) return 1.0;
  if (value >= thresholds.good) return 0.8;
  if (value >= thresholds.poor) return 0.5;
  return 0.2;
}

/**
 * Analyze all test files in a directory
 * @param {string} testDir - Directory containing test files
 * @param {Object} _spec - Working specification
 * @returns {Object} Analysis summary
 */
function analyzeTestDirectory(testDir, _spec = null) {
  const results = {
    files: [],
    summary: {
      totalFiles: 0,
      totalTests: 0,
      totalAssertions: 0,
      averageQualityScore: 0,
      issues: [],
    },
  };

  try {
    const files = fs.readdirSync(testDir);

    files.forEach((file) => {
      const filePath = path.join(testDir, file);
      const stat = fs.statSync(filePath);

      if (stat.isFile() && /\.(test|spec)\.(js|ts|py|java)$/.test(file)) {
        const analysis = analyzeTestFile(filePath, _spec);
        if (analysis) {
          const qualityScore = calculateQualityScore(analysis);
          analysis.qualityScore = qualityScore;

          results.files.push(analysis);
          results.summary.totalFiles++;
          results.summary.totalTests += analysis.testFunctions;
          results.summary.totalAssertions += analysis.assertions;

          if (analysis.issues.length > 0) {
            results.summary.issues.push(
              ...analysis.issues.map((issue) => `${file}: ${issue}`)
            );
          }
        }
      }
    });

    // Calculate average quality score
    if (results.files.length > 0) {
      const totalScore = results.files.reduce(
        (sum, file) => sum + file.qualityScore,
        0
      );
      results.summary.averageQualityScore = Math.round(
        totalScore / results.files.length
      );
    }
  } catch (error) {
    console.error(`❌ Error analyzing test directory: ${error.message}`);
  }

  return results;
}

/**
 * Generate recommendations based on analysis
 * @param {Object} results - Analysis results
 * @returns {Array} Recommendations
 */
function generateRecommendations(results) {
  const recommendations = [];

  if (results.summary.averageQualityScore < 70) {
    recommendations.push({
      type: "critical",
      message:
        "Overall test quality is below acceptable threshold. Consider improving test meaningfulness.",
      suggestions: [
        "Add more assertions per test function",
        "Include edge case and error condition testing",
        "Improve test naming for better clarity",
        "Ensure proper setup/teardown procedures",
      ],
    });
  }

  if (
    results.summary.totalAssertions / Math.max(results.summary.totalTests, 1) <
    0.5
  ) {
    recommendations.push({
      type: "warning",
      message: "Low assertion density detected across tests.",
      suggestions: [
        "Each test should validate expected behavior with assertions",
        "Avoid tests that only check if code runs without errors",
        "Add assertions for return values, side effects, and state changes",
      ],
    });
  }

  const filesWithoutEdgeCases = results.files.filter(
    (f) => f.edgeCases === 0 && f.testFunctions > 2
  );
  if (filesWithoutEdgeCases.length > 0) {
    recommendations.push({
      type: "info",
      message: `${filesWithoutEdgeCases.length} test file(s) lack edge case coverage.`,
      suggestions: [
        "Add tests for null/undefined inputs",
        "Test boundary conditions and error scenarios",
        "Include tests for invalid or malformed data",
      ],
    });
  }

  return recommendations;
}

// CLI interface
if (require.main === module) {
  const command = process.argv[2];
  const testDir = process.argv[3] || "tests";

  switch (command) {
    case "analyze":
      console.log(`🔍 Analyzing test quality in: ${testDir}`);

      // Try to load working spec for spec alignment check
      let spec = null;
      const specPath = ".caws/working-spec.yaml";
      if (fs.existsSync(specPath)) {
        try {
          const yaml = require("js-yaml");
          spec = yaml.load(fs.readFileSync(specPath, "utf8"));
          console.log("✅ Loaded working spec for alignment analysis");
        } catch (error) {
          console.warn(
            "⚠️  Could not load working spec for alignment analysis"
          );
        }
      }

      const results = analyzeTestDirectory(testDir, spec);

      console.log("\n📊 Test Quality Analysis Results:");
      console.log(`   Files analyzed: ${results.summary.totalFiles}`);
      console.log(`   Test functions: ${results.summary.totalTests}`);
      console.log(`   Total assertions: ${results.summary.totalAssertions}`);
      console.log(
        `   Average quality score: ${results.summary.averageQualityScore}/100`
      );

      if (results.files.length > 0) {
        console.log("\n📋 File-by-file breakdown:");
        results.files.forEach((file) => {
          console.log(
            `   ${file.file}: ${file.qualityScore}/100 (${file.testFunctions} tests, ${file.assertions} assertions)`
          );
        });
      }

      if (results.summary.issues.length > 0) {
        console.log("\n⚠️  Issues found:");
        results.summary.issues.forEach((issue) => {
          console.log(`   - ${issue}`);
        });
      }

      const recommendations = generateRecommendations(results);
      if (recommendations.length > 0) {
        console.log("\n💡 Recommendations:");
        recommendations.forEach((rec) => {
          console.log(`   [${rec.type.toUpperCase()}] ${rec.message}`);
          rec.suggestions.forEach((suggestion) => {
            console.log(`      • ${suggestion}`);
          });
        });
      }

      // Exit with error code if quality is poor
      if (results.summary.averageQualityScore < 70) {
        console.error("\n❌ Test quality below acceptable threshold");
        process.exit(1);
      }

      break;

    default:
      console.log("CAWS Test Quality Analyzer");
      console.log("Usage:");
      console.log("  node test-quality.js analyze [test-directory]");
      console.log("");
      console.log("Examples:");
      console.log("  node test-quality.js analyze tests/unit");
      console.log("  node test-quality.js analyze tests/");
      process.exit(1);
  }
}

module.exports = {
  analyzeTestFile,
  analyzeTestDirectory,
  calculateQualityScore,
  generateRecommendations,
  QUALITY_CRITERIA,
};
