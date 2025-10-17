#!/usr/bin/env tsx

/**
 * CAWS Flake Detection System
 *
 * Monitors test variance and quarantines intermittently failing tests.
 * This tool analyzes test run variance and identifies flaky tests for quarantine.
 *
 * @author @darianrosebrook
 */

import { readFileSync, writeFileSync, existsSync } from "fs";
import { dirname } from "path";
import { fileURLToPath } from "url";

interface TestResult {
  title: string;
  fullName: string;
  status: "passed" | "failed" | "pending" | "skipped";
  duration: number;
  failureMessages: string[];
}

interface TestSuiteResult {
  name: string;
  status: "passed" | "failed";
  testResults: TestResult[];
  startTime: number;
  endTime: number;
}

interface FlakeDetectionResult {
  flakyTests: string[];
  varianceScore: number;
  totalRuns: number;
  recommendations: string[];
}

interface HistoricalTestData {
  runs: TestRun[];
  quarantined: Set<string>;
  lastUpdated: string;
}

interface TestRun {
  timestamp: number;
  results: Map<string, TestResult>;
  variance: number;
}

/**
 * Flake Detection Service
 * Analyzes test run variance and identifies flaky tests
 */
class FlakeDetectionService {
  private readonly HISTORY_FILE = ".caws/flake-history.json";
  private readonly QUARANTINE_FILE = ".caws/quarantined-tests.json";
  private readonly VARIANCE_THRESHOLD = 0.05; // 5% variance threshold
  private readonly MIN_RUNS_FOR_ANALYSIS = 3;
  private readonly QUARANTINE_THRESHOLD = 0.15; // 15% flake rate triggers quarantine

  /**
   * Analyze test variance and detect flaky tests
   */
  async detectFlakes(
    currentResults: TestSuiteResult[]
  ): Promise<FlakeDetectionResult> {
    const history = this.loadHistory();
    const currentRun = this.createCurrentRun(currentResults);

    history.runs.push(currentRun);
    this.saveHistory(history);

    if (history.runs.length < this.MIN_RUNS_FOR_ANALYSIS) {
      return {
        flakyTests: [],
        varianceScore: 0,
        totalRuns: history.runs.length,
        recommendations: [
          `Need ${
            this.MIN_RUNS_FOR_ANALYSIS - history.runs.length
          } more test runs for analysis`,
        ],
      };
    }

    const flakyTests = this.identifyFlakyTests(history);
    const varianceScore = this.calculateVarianceScore(history);

    const recommendations = this.generateRecommendations(
      flakyTests,
      varianceScore
    );

    return {
      flakyTests,
      varianceScore,
      totalRuns: history.runs.length,
      recommendations,
    };
  }

  /**
   * Quarantine flaky tests
   */
  quarantineTests(testNames: string[]): void {
    const history = this.loadHistory();
    testNames.forEach((testName) => history.quarantined.add(testName));
    history.lastUpdated = new Date().toISOString();
    this.saveHistory(history);

    // Save quarantined tests list
    const quarantinedData = {
      quarantined: Array.from(history.quarantined),
      quarantinedAt: history.lastUpdated,
      reason: "Automated flake detection",
    };

    writeFileSync(
      this.QUARANTINE_FILE,
      JSON.stringify(quarantinedData, null, 2)
    );
    console.log(`🚫 Quarantined ${testNames.length} flaky tests`);
  }

  /**
   * Get currently quarantined tests
   */
  getQuarantinedTests(): string[] {
    const history = this.loadHistory();
    return Array.from(history.quarantined);
  }

  /**
   * Release tests from quarantine (manual override)
   */
  releaseFromQuarantine(testNames: string[]): void {
    const history = this.loadHistory();
    testNames.forEach((testName) => history.quarantined.delete(testName));
    history.lastUpdated = new Date().toISOString();
    this.saveHistory(history);
    console.log(`✅ Released ${testNames.length} tests from quarantine`);
  }

  private loadHistory(): HistoricalTestData {
    if (!existsSync(this.HISTORY_FILE)) {
      return {
        runs: [],
        quarantined: new Set(),
        lastUpdated: new Date().toISOString(),
      };
    }

    try {
      const data = JSON.parse(readFileSync(this.HISTORY_FILE, "utf-8"));
      return {
        runs: data.runs || [],
        quarantined: new Set(data.quarantined || []),
        lastUpdated: data.lastUpdated || new Date().toISOString(),
      };
    } catch {
      return {
        runs: [],
        quarantined: new Set(),
        lastUpdated: new Date().toISOString(),
      };
    }
  }

  private saveHistory(history: HistoricalTestData): void {
    const data = {
      runs: history.runs,
      quarantined: Array.from(history.quarantined),
      lastUpdated: history.lastUpdated,
    };
    writeFileSync(this.HISTORY_FILE, JSON.stringify(data, null, 2));
  }

  private createCurrentRun(results: TestSuiteResult[]): TestRun {
    const testMap = new Map<string, TestResult>();

    results.forEach((suite) => {
      suite.testResults.forEach((test) => {
        const key = this.getTestKey(test);
        testMap.set(key, test);
      });
    });

    const variance = this.calculateRunVariance(testMap, results);
    return {
      timestamp: Date.now(),
      results: testMap,
      variance,
    };
  }

  private getTestKey(test: TestResult): string {
    return test.fullName;
  }

  private identifyFlakyTests(history: HistoricalTestData): string[] {
    const flakyTests = new Set<string>();
    const recentRuns = history.runs.slice(-5); // Analyze last 5 runs

    // Find tests that have inconsistent results
    for (const run of recentRuns) {
      for (const [testName, result] of run.results) {
        if (result.status !== "passed") {
          // Check if this test has passed in other recent runs
          const passedInOtherRuns = recentRuns
            .filter((r) => r !== run)
            .some((r) => r.results.get(testName)?.status === "passed");

          if (passedInOtherRuns) {
            flakyTests.add(testName);
          }
        }
      }
    }

    // Check against quarantine threshold
    for (const testName of flakyTests) {
      const flakeRate = this.calculateFlakeRate(testName, recentRuns);
      if (flakeRate < this.QUARANTINE_THRESHOLD) {
        flakyTests.delete(testName);
      }
    }

    return Array.from(flakyTests);
  }

  private calculateFlakeRate(testName: string, runs: TestRun[]): number {
    const results = runs
      .map((run) => run.results.get(testName)?.status)
      .filter(Boolean);
    const failures = results.filter((status) => status !== "passed").length;
    return failures / results.length;
  }

  private calculateVarianceScore(history: HistoricalTestData): number {
    if (history.runs.length < 2) return 0;

    const recentRuns = history.runs.slice(-5);
    const varianceSum = recentRuns.reduce((sum, run) => sum + run.variance, 0);
    return varianceSum / recentRuns.length;
  }

  private calculateRunVariance(
    testMap: Map<string, TestResult>,
    _suites: TestSuiteResult[]
  ): number {
    const totalTests = testMap.size;
    const failedTests = Array.from(testMap.values()).filter(
      (t) => t.status !== "passed"
    ).length;
    return totalTests > 0 ? failedTests / totalTests : 0;
  }

  private generateRecommendations(
    flakyTests: string[],
    varianceScore: number
  ): string[] {
    const recommendations: string[] = [];

    if (flakyTests.length > 0) {
      recommendations.push(
        `Quarantine ${flakyTests.length} flaky tests for investigation`
      );
    }

    if (varianceScore > this.VARIANCE_THRESHOLD) {
      recommendations.push(
        "High test variance detected - consider test environment stability"
      );
    }

    if (varianceScore === 0) {
      recommendations.push("Excellent test stability - no flakes detected");
    }

    return recommendations;
  }
}

/**
 * Read test results from common test result file formats
 */
async function readTestResultsFromFiles(): Promise<TestSuiteResult[]> {
  const results: TestSuiteResult[] = [];

  // Common test result file locations and formats
  const testResultFiles = [
    "junit.xml",
    "test-results.xml",
    "test-results.json",
    "coverage.xml",
    ".caws/test-history.json",
    "test-output.xml",
    "junit-report.xml",
  ];

  for (const filePath of testResultFiles) {
    if (existsSync(filePath)) {
      try {
        const content = readFileSync(filePath, "utf8");

        if (filePath.endsWith(".xml")) {
          const parsedResults = parseXMLTestResults(content, filePath);
          results.push(...parsedResults);
        } else if (filePath.endsWith(".json")) {
          const parsedResults = parseJSONTestResults(content, filePath);
          results.push(...parsedResults);
        }

        console.log(`✅ Read test results from ${filePath}`);
      } catch (error) {
        console.warn(`⚠️  Could not parse ${filePath}: ${error}`);
      }
    }
  }

  return results;
}

/**
 * Parse XML test results (JUnit, Cobertura formats)
 */
function parseXMLTestResults(
  content: string,
  filePath: string
): TestSuiteResult[] {
  const results: TestSuiteResult[] = [];

  try {
    // Simple XML parsing for test results
    // This is a basic implementation - in production you'd use a proper XML parser

    if (content.includes("<testsuite") || content.includes("<testsuites")) {
      // JUnit format
      const testMatches =
        content.match(/<testcase[^>]*name="([^"]*)"[^>]*>/g) || [];
      const failureMatches = content.match(/<failure[^>]*>/g) || [];

      const testSuite: TestSuiteResult = {
        name: filePath,
        status: failureMatches.length > 0 ? "failed" : "passed",
        tests: testMatches.map((_, index) => ({
          title: `Test ${index + 1}`,
          fullName: `Test ${index + 1}`,
          status: "passed",
          duration: 0,
          failureMessages: [],
        })),
        startTime: Date.now(),
        endTime: Date.now(),
      };

      results.push(testSuite);
    } else if (content.includes("<coverage")) {
      // Cobertura coverage format - convert to test-like results
      const lineRateMatch = content.match(/line-rate="([^"]*)"/);
      const lineRate = lineRateMatch ? parseFloat(lineRateMatch[1]) : 0;

      const testSuite: TestSuiteResult = {
        name: `${filePath} (coverage)`,
        status: lineRate > 0.8 ? "passed" : "failed",
        tests: [
          {
            title: "Coverage Test",
            fullName: "Coverage Test",
            status: lineRate > 0.8 ? "passed" : "failed",
            duration: 0,
            failureMessages:
              lineRate <= 0.8
                ? [`Coverage too low: ${(lineRate * 100).toFixed(1)}%`]
                : [],
          },
        ],
        startTime: Date.now(),
        endTime: Date.now(),
      };

      results.push(testSuite);
    }
  } catch (error) {
    console.warn(`⚠️  Error parsing XML from ${filePath}: ${error}`);
  }

  return results;
}

/**
 * Parse JSON test results
 */
function parseJSONTestResults(
  content: string,
  filePath: string
): TestSuiteResult[] {
  const results: TestSuiteResult[] = [];

  try {
    const data = JSON.parse(content);

    // Handle different JSON test result formats
    if (Array.isArray(data)) {
      // Array of test results
      data.forEach((item, index) => {
        const testSuite: TestSuiteResult = {
          name: `${filePath} (suite ${index + 1})`,
          status: item.status || "passed",
          tests: item.tests || [
            {
              title: `Test ${index + 1}`,
              fullName: `Test ${index + 1}`,
              status: item.status || "passed",
              duration: item.duration || 0,
              failureMessages: item.failureMessages || [],
            },
          ],
          startTime: item.startTime || Date.now(),
          endTime: item.endTime || Date.now(),
        };
        results.push(testSuite);
      });
    } else if (data.tests) {
      // Single test suite object
      const testSuite: TestSuiteResult = {
        name: filePath,
        status: data.status || "passed",
        tests: data.tests,
        startTime: data.startTime || Date.now(),
        endTime: data.endTime || Date.now(),
      };
      results.push(testSuite);
    }
  } catch (error) {
    console.warn(`⚠️  Error parsing JSON from ${filePath}: ${error}`);
  }

  return results;
}

/**
 * CLI Interface
 */
async function main() {
  const args = process.argv.slice(2);

  if (args.length === 0) {
    console.log("🔍 CAWS Flake Detection Tool");
    console.log("Usage: flake-detector.ts <command> [options]");
    console.log("");
    console.log("Commands:");
    console.log("  detect     - Analyze test variance and detect flaky tests");
    console.log("  quarantine - Quarantine specified flaky tests");
    console.log("  release    - Release tests from quarantine");
    console.log("  status     - Show current flake detection status");
    console.log("");
    console.log("Examples:");
    console.log("  flake-detector.ts detect");
    console.log('  flake-detector.ts quarantine "test name"');
    console.log('  flake-detector.ts release "test name"');
    return;
  }

  const command = args[0];
  const detector = new FlakeDetectionService();

  try {
    switch (command) {
      case "detect": {
        console.log("🔍 Analyzing test variance...");

        // Try to read test results from common test result files
        const testResults = await readTestResultsFromFiles();

        if (testResults.length === 0) {
          console.log("⚠️  No test result files found. Looking for:");
          console.log("   - junit.xml (JUnit format)");
          console.log("   - test-results.json (JSON format)");
          console.log("   - coverage.xml (Cobertura format)");
          console.log("   - .caws/test-history.json (CAWS history)");
          console.log("");
          console.log(
            "💡 To generate test results, run your test suite with output formats:"
          );
          console.log(
            "   - Jest: jest --coverage --testResultsProcessor=jest-junit"
          );
          console.log(
            "   - pytest: pytest --junitxml=junit.xml --cov-report=xml"
          );
          console.log("");
          console.log("📊 Using historical data for analysis...");
        } else {
          console.log(`📊 Found ${testResults.length} test result files`);
        }

        const result = await detector.detectFlakes(testResults);

        console.log(`📊 Flake Detection Results:`);
        console.log(
          `   Variance Score: ${(result.varianceScore * 100).toFixed(2)}%`
        );
        console.log(`   Total Runs Analyzed: ${result.totalRuns}`);
        console.log(`   Flaky Tests Found: ${result.flakyTests.length}`);

        if (result.flakyTests.length > 0) {
          console.log("\n🚨 Flaky Tests:");
          result.flakyTests.forEach((test) => console.log(`   - ${test}`));
        }

        result.recommendations.forEach((rec) => console.log(`💡 ${rec}`));
        break;
      }

      case "quarantine": {
        const testNames = args.slice(1);
        if (testNames.length === 0) {
          console.log("❌ Please specify test names to quarantine");
          return;
        }
        detector.quarantineTests(testNames);
        break;
      }

      case "release": {
        const testNames = args.slice(1);
        if (testNames.length === 0) {
          console.log("❌ Please specify test names to release");
          return;
        }
        detector.releaseFromQuarantine(testNames);
        break;
      }

      case "status": {
        const quarantined = detector.getQuarantinedTests();
        console.log("🚫 Currently Quarantined Tests:");
        if (quarantined.length === 0) {
          console.log("   None - all tests are active");
        } else {
          quarantined.forEach((test) => console.log(`   - ${test}`));
        }
        break;
      }

      default:
        console.log(`❌ Unknown command: ${command}`);
        process.exit(1);
    }
  } catch (error) {
    console.error("❌ Error:", error);
    process.exit(1);
  }
}

// Run CLI if this file is executed directly
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch(console.error);
}

export { FlakeDetectionService };
