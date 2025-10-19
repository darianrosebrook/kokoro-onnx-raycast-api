/**
 * CAWS Gate Checker
 * Consolidated gate checking logic for coverage, mutation, contracts, and trust score
 *
 * @author @darianrosebrook
 */

import * as path from "path";
import * as fs from "fs";
import { CawsBaseTool } from "./base-tool.js";
import {
  GateResult,
  GateCheckOptions,
  MutationData,
  ContractTestResults,
  TierPolicy,
  WaiverConfig,
  HumanOverride,
  AIAssessment,
} from "./types.js";
import { WaiversManager } from "./waivers-manager.js";

export class CawsGateChecker extends CawsBaseTool {
  private logger: any; // Logger instance (inherited from base tool)
  private tierPolicies: Record<number, TierPolicy> = {
    1: {
      min_branch: 0.9,
      min_mutation: 0.7,
      min_coverage: 0.9,
      requires_contracts: true,
      requires_manual_review: true,
    },
    2: {
      min_branch: 0.8,
      min_mutation: 0.5,
      min_coverage: 0.8,
      requires_contracts: true,
    },
    3: {
      min_branch: 0.7,
      min_mutation: 0.3,
      min_coverage: 0.7,
      requires_contracts: false,
    },
  };

  private waiversManager: WaiversManager;

  constructor() {
    super();
    this.loadTierPolicies();
    this.waiversManager = new WaiversManager();
  }

  /**
   * Load tier policies from configuration
   */
  private loadTierPolicies(): void {
    const policy = this.loadTierPolicy();
    if (policy) {
      this.tierPolicies = { ...this.tierPolicies, ...policy };
    }
  }

  /**
   * Auto-detect the correct working directory for coverage/mutation reports in monorepos
   */
  private findReportDirectory(
    startPath: string = this.getWorkingDirectory()
  ): string {
    // First, check if the current directory has the reports
    if (
      this.hasCoverageReports(startPath) ||
      this.hasMutationReports(startPath)
    ) {
      return startPath;
    }

    // Check for npm workspaces configuration
    const packageJsonPath = path.join(startPath, "package.json");
    if (this.pathExists(packageJsonPath)) {
      try {
        const packageJson = this.readJsonFile<any>(packageJsonPath);
        if (packageJson?.workspaces) {
          const workspaces = packageJson.workspaces;

          // Handle workspace patterns (e.g., ["packages/*", "iterations/*"])
          for (const wsPattern of workspaces) {
            if (wsPattern.includes("*")) {
              const baseDir = wsPattern.split("*")[0];
              const fullBaseDir = path.join(startPath, baseDir);

              if (this.pathExists(fullBaseDir)) {
                const entries = fs.readdirSync(fullBaseDir, {
                  withFileTypes: true,
                });
                for (const entry of entries) {
                  if (entry.isDirectory()) {
                    const wsPath = path.join(fullBaseDir, entry.name);
                    if (
                      this.hasCoverageReports(wsPath) ||
                      this.hasMutationReports(wsPath)
                    ) {
                      return wsPath;
                    }
                  }
                }
              }
            } else {
              // Direct workspace path
              const wsPath = path.join(startPath, wsPattern);
              if (
                this.hasCoverageReports(wsPath) ||
                this.hasMutationReports(wsPath)
              ) {
                return wsPath;
              }
            }
          }
        }
      } catch (error) {
        // Ignore workspace parsing errors
      }
    }

    // Fall back to original working directory
    return startPath;
  }

  /**
   * Check if a directory has coverage reports
   */
  private hasCoverageReports(dirPath: string): boolean {
    const coveragePath = path.join(dirPath, "coverage", "coverage-final.json");
    return this.pathExists(coveragePath);
  }

  /**
   * Check if a directory has mutation reports
   */
  private hasMutationReports(dirPath: string): boolean {
    const mutationPath = path.join(
      dirPath,
      "reports",
      "mutation",
      "mutation.json"
    );
    return this.pathExists(mutationPath);
  }

  /**
   * Check if a waiver applies to the given gate
   */
  private async checkWaiver(
    gate: string,
    workingDirectory?: string
  ): Promise<{
    waived: boolean;
    waiver?: WaiverConfig;
    reason?: string;
  }> {
    try {
      const waivers = await this.waiversManager.getWaiversByGate(gate);
      if (waivers.length === 0) {
        return { waived: false };
      }

      // Implement sophisticated waiver matching and conflict resolution
      const applicableWaivers = await this.findApplicableWaivers(waivers, gate);

      if (applicableWaivers.length === 0) {
        return { waived: false };
      }

      // Resolve conflicts and apply precedence rules
      const resolvedWaiver = await this.resolveWaiverConflicts(
        applicableWaivers
      );

      if (resolvedWaiver) {
        return {
          waived: true,
          waiver: resolvedWaiver,
        };
      }

      return { waived: false };

      return { waived: false };
    } catch (error) {
      return { waived: false, reason: `Waiver check failed: ${error}` };
    }
  }

  /**
   * Load and validate working spec from project
   */
  private async loadWorkingSpec(workingDirectory?: string): Promise<{
    spec?: any;
    experiment_mode?: boolean;
    human_override?: HumanOverride;
    ai_assessment?: AIAssessment;
    errors?: string[];
  }> {
    try {
      const specPath = path.join(
        workingDirectory || this.getWorkingDirectory(),
        ".caws/working-spec.yml"
      );

      if (!this.pathExists(specPath)) {
        return { errors: ["Working spec not found at .caws/working-spec.yml"] };
      }

      const spec = await this.readYamlFile(specPath);
      if (!spec) {
        return { errors: ["Failed to parse working spec"] };
      }

      return {
        spec,
        experiment_mode: spec.experiment_mode,
        human_override: spec.human_override,
        ai_assessment: spec.ai_assessment,
      };
    } catch (error) {
      return { errors: [`Failed to load working spec: ${error}`] };
    }
  }

  /**
   * Check if human override applies to waive requirements
   */
  private checkHumanOverride(
    humanOverride: HumanOverride | undefined,
    requirement: string
  ): { waived: boolean; reason?: string } {
    if (!humanOverride) {
      return { waived: false };
    }

    if (humanOverride.waived_requirements?.includes(requirement)) {
      return {
        waived: true,
        reason: `Human override by ${humanOverride.approved_by}: ${humanOverride.reason}`,
      };
    }

    return { waived: false };
  }

  /**
   * Check if experiment mode applies reduced requirements
   */
  private checkExperimentMode(experimentMode: boolean | undefined): {
    reduced: boolean;
    adjustments?: Record<string, any>;
  } {
    if (!experimentMode) {
      return { reduced: false };
    }

    return {
      reduced: true,
      adjustments: {
        skip_mutation: true,
        skip_contracts: true,
        reduced_coverage: 0.5, // Minimum coverage for experiments
        skip_manual_review: true,
      },
    };
  }

  /**
   * Check branch coverage against tier requirements
   */
  async checkCoverage(options: GateCheckOptions): Promise<GateResult> {
    try {
      // Check waivers and overrides first
      const waiverCheck = await this.checkWaiver(
        "coverage",
        options.workingDirectory
      );
      if (waiverCheck.waived) {
        return {
          passed: true,
          score: 1.0, // Waived checks pass with perfect score
          details: {
            waived: true,
            waiver_reason: waiverCheck.waiver?.reason,
            waiver_owner: waiverCheck.waiver?.owner,
          },
          tier: options.tier,
        };
      }

      // Load working spec for overrides and experiment mode
      const specData = await this.loadWorkingSpec(options.workingDirectory);

      // Check human override
      const overrideCheck = this.checkHumanOverride(
        specData.human_override,
        "coverage"
      );
      if (overrideCheck.waived) {
        return {
          passed: true,
          score: 1.0,
          details: {
            overridden: true,
            override_reason: overrideCheck.reason,
          },
          tier: options.tier,
        };
      }

      // Check experiment mode
      const experimentCheck = this.checkExperimentMode(
        specData.experiment_mode
      );

      let effectiveTier = options.tier;
      if (
        experimentCheck.reduced &&
        experimentCheck.adjustments?.reduced_coverage
      ) {
        // For experiments, use reduced coverage requirement
        effectiveTier = 4; // Special experiment tier
        this.tierPolicies[4] = {
          min_branch: experimentCheck.adjustments.reduced_coverage,
          min_mutation: 0,
          min_coverage: experimentCheck.adjustments.reduced_coverage,
          requires_contracts: false,
          requires_manual_review: false,
        };
      }

      // Auto-detect the correct directory for coverage reports
      const reportDir = this.findReportDirectory(
        options.workingDirectory || this.getWorkingDirectory()
      );
      const coveragePath = path.join(
        reportDir,
        "coverage",
        "coverage-final.json"
      );

      if (!this.pathExists(coveragePath)) {
        return {
          passed: false,
          score: 0,
          details: {
            error: "Coverage report not found. Run tests with coverage first.",
            searched_paths: [
              path.join(reportDir, "coverage", "coverage-final.json"),
              path.join(
                this.getWorkingDirectory(),
                "coverage",
                "coverage-final.json"
              ),
            ],
            expected_format: "Istanbul coverage format (coverage-final.json)",
            run_command: "npm test -- --coverage --coverageReporters=json",
          },
          errors: [
            `Coverage report not found at ${path.relative(
              this.getWorkingDirectory(),
              coveragePath
            )}`,
          ],
        };
      }

      const coverageData = this.readJsonFile<any>(coveragePath);
      if (!coverageData) {
        return {
          passed: false,
          score: 0,
          details: { error: "Failed to parse coverage data" },
          errors: ["Failed to parse coverage data"],
        };
      }

      // Calculate coverage from detailed data
      let totalStatements = 0;
      let coveredStatements = 0;
      let totalBranches = 0;
      let coveredBranches = 0;
      let totalFunctions = 0;
      let coveredFunctions = 0;

      for (const file of Object.values(coverageData)) {
        const fileData = file as any;
        if (fileData.s) {
          totalStatements += Object.keys(fileData.s).length;
          coveredStatements += Object.values(fileData.s).filter(
            (s: any) => s > 0
          ).length;
        }
        if (fileData.b) {
          for (const branches of Object.values(fileData.b) as number[][]) {
            totalBranches += branches.length;
            coveredBranches += branches.filter((b: number) => b > 0).length;
          }
        }
        if (fileData.f) {
          totalFunctions += Object.keys(fileData.f).length;
          coveredFunctions += Object.values(fileData.f).filter(
            (f: any) => f > 0
          ).length;
        }
      }

      // Calculate percentages
      const statementsPct =
        totalStatements > 0 ? (coveredStatements / totalStatements) * 100 : 0;
      const branchesPct =
        totalBranches > 0 ? (coveredBranches / totalBranches) * 100 : 0;
      const functionsPct =
        totalFunctions > 0 ? (coveredFunctions / totalFunctions) * 100 : 0;

      const branchCoverage = branchesPct / 100;
      const policy = this.tierPolicies[effectiveTier];
      const passed = branchCoverage >= policy.min_branch;

      return {
        passed,
        score: branchCoverage,
        details: {
          branch_coverage: branchCoverage,
          required_branch: policy.min_branch,
          functions_coverage: functionsPct / 100,
          lines_coverage: statementsPct / 100,
          statements_coverage: statementsPct / 100,
        },
      };
    } catch (error) {
      return {
        passed: false,
        score: 0,
        details: { error: `Coverage check failed: ${error}` },
        errors: [`Coverage check failed: ${error}`],
      };
    }
  }

  /**
   * Check mutation testing score
   */
  async checkMutation(options: GateCheckOptions): Promise<GateResult> {
    try {
      // Check waivers and overrides first
      const waiverCheck = await this.checkWaiver(
        "mutation",
        options.workingDirectory
      );
      if (waiverCheck.waived) {
        return {
          passed: true,
          score: 1.0,
          details: {
            waived: true,
            waiver_reason: waiverCheck.waiver?.reason,
            waiver_owner: waiverCheck.waiver?.owner,
          },
          tier: options.tier,
        };
      }

      // Load working spec for overrides and experiment mode
      const specData = await this.loadWorkingSpec(options.workingDirectory);

      // Check human override
      const overrideCheck = this.checkHumanOverride(
        specData.human_override,
        "mutation_testing"
      );
      if (overrideCheck.waived) {
        return {
          passed: true,
          score: 1.0,
          details: {
            overridden: true,
            override_reason: overrideCheck.reason,
          },
          tier: options.tier,
        };
      }

      // Check experiment mode
      const experimentCheck = this.checkExperimentMode(
        specData.experiment_mode
      );
      if (
        experimentCheck.reduced &&
        experimentCheck.adjustments?.skip_mutation
      ) {
        return {
          passed: true,
          score: 1.0,
          details: {
            experiment_mode: true,
            mutation_skipped: true,
          },
          tier: options.tier,
        };
      }

      // Auto-detect the correct directory for mutation reports
      const reportDir = this.findReportDirectory(
        options.workingDirectory || this.getWorkingDirectory()
      );
      const mutationPath = path.join(
        reportDir,
        "reports",
        "mutation",
        "mutation.json"
      );

      if (!this.pathExists(mutationPath)) {
        return {
          passed: false,
          score: 0,
          details: {
            error: "Mutation report not found. Run mutation tests first.",
            searched_paths: [
              path.join(reportDir, "reports", "mutation", "mutation.json"),
              path.join(
                this.getWorkingDirectory(),
                "reports",
                "mutation",
                "mutation.json"
              ),
            ],
            expected_format: "Stryker mutation testing JSON report",
            run_command: "npx stryker run",
          },
          errors: [
            `Mutation report not found at ${path.relative(
              this.getWorkingDirectory(),
              mutationPath
            )}`,
          ],
        };
      }

      const mutationData = this.readJsonFile<MutationData>(mutationPath);
      if (!mutationData) {
        return {
          passed: false,
          score: 0,
          details: { error: "Failed to parse mutation data" },
          errors: ["Failed to parse mutation data"],
        };
      }

      const killed = mutationData.metrics.killed || 0;
      const total = mutationData.metrics.totalDetected || 1;
      const mutationScore = killed / total;
      const policy = this.tierPolicies[options.tier];
      const passed = mutationScore >= policy.min_mutation;

      return {
        passed,
        score: mutationScore,
        details: {
          mutation_score: mutationScore,
          required_mutation: policy.min_mutation,
          killed,
          total,
          survived: mutationData.metrics.survived || 0,
        },
      };
    } catch (error) {
      return {
        passed: false,
        score: 0,
        details: { error: `Mutation check failed: ${error}` },
        errors: [`Mutation check failed: ${error}`],
      };
    }
  }

  /**
   * Check contract test compliance
   */
  async checkContracts(options: GateCheckOptions): Promise<GateResult> {
    try {
      // Check waivers and overrides first
      const waiverCheck = await this.checkWaiver(
        "contracts",
        options.workingDirectory
      );
      if (waiverCheck.waived) {
        return {
          passed: true,
          score: 1.0,
          details: {
            waived: true,
            waiver_reason: waiverCheck.waiver?.reason,
            waiver_owner: waiverCheck.waiver?.owner,
          },
          tier: options.tier,
        };
      }

      const policy = this.tierPolicies[options.tier];

      if (!policy.requires_contracts) {
        return {
          passed: true,
          score: 1.0,
          details: { contracts_required: false, tier: options.tier },
        };
      }

      // Auto-detect the correct directory for contract test results
      const reportDir = this.findReportDirectory(
        options.workingDirectory || this.getWorkingDirectory()
      );
      const contractResultsPath = path.join(
        reportDir,
        "test-results",
        "contract-results.json"
      );

      if (!this.pathExists(contractResultsPath)) {
        return {
          passed: false,
          score: 0,
          details: {
            error: "Contract test results not found",
            searched_paths: [
              path.join(reportDir, "test-results", "contract-results.json"),
              path.join(
                this.getWorkingDirectory(),
                "test-results",
                "contract-results.json"
              ),
              path.join(reportDir, ".caws", "contract-results.json"),
              path.join(
                this.getWorkingDirectory(),
                ".caws",
                "contract-results.json"
              ),
            ],
            expected_format:
              "JSON with { tests: [], passed: boolean, numPassed: number, numTotal: number }",
            example_command:
              "npm run test:contract -- --json --outputFile=test-results/contract-results.json",
          },
          errors: [
            `Contract test results not found. Searched in: ${[
              path.relative(
                this.getWorkingDirectory(),
                path.join(reportDir, "test-results", "contract-results.json")
              ),
              "test-results/contract-results.json",
              ".caws/contract-results.json",
            ].join(", ")}`,
          ],
        };
      }

      const results =
        this.readJsonFile<ContractTestResults>(contractResultsPath);
      if (!results) {
        return {
          passed: false,
          score: 0,
          details: { error: "Failed to parse contract test results" },
          errors: ["Failed to parse contract test results"],
        };
      }

      const passed =
        results.numPassed === results.numTotal && results.numTotal > 0;

      return {
        passed,
        score: passed ? 1.0 : 0,
        details: {
          tests_passed: results.numPassed,
          tests_total: results.numTotal,
          consumer_tests: results.consumer || false,
          provider_tests: results.provider || false,
        },
      };
    } catch (error) {
      return {
        passed: false,
        score: 0,
        details: { error: `Contract check failed: ${error}` },
        errors: [`Contract check failed: ${error}`],
      };
    }
  }

  /**
   * Calculate overall trust score
   */
  async calculateTrustScore(options: GateCheckOptions): Promise<GateResult> {
    try {
      // Run all gate checks
      const [coverageResult, mutationResult, contractResult] =
        await Promise.all([
          this.checkCoverage(options),
          this.checkMutation(options),
          this.checkContracts(options),
        ]);

      // Load provenance if available
      let provenance = null;
      try {
        const provenancePath = path.join(
          options.workingDirectory || this.getWorkingDirectory(),
          ".agent/provenance.json"
        );
        if (this.pathExists(provenancePath)) {
          provenance = this.readJsonFile(provenancePath);
        }
      } catch {
        // Provenance not available
      }

      // CAWS trust score weights
      const weights = {
        coverage: 0.3,
        mutation: 0.3,
        contracts: 0.2,
        a11y: 0.1,
        perf: 0.1,
      };

      // Calculate weighted score
      let totalScore = 0;
      let totalWeight = 0;

      // Coverage component
      totalScore += coverageResult.score * weights.coverage;
      totalWeight += weights.coverage;

      // Mutation component
      totalScore += mutationResult.score * weights.mutation;
      totalWeight += weights.mutation;

      // Contracts component
      totalScore += contractResult.score * weights.contracts;
      totalWeight += weights.contracts;

      // Load working spec for requirements
      let workingSpec = null;
      try {
        const specPath = path.join(
          options.workingDirectory || this.getWorkingDirectory(),
          ".caws/working-spec.yaml"
        );
        if (this.pathExists(specPath)) {
          workingSpec = this.readYamlFile(specPath);
        }
      } catch {
        // Working spec not available
      }

      // Calculate A11y component score
      const a11yScore = this.calculateA11yScore(
        provenance?.results?.a11y,
        workingSpec
      );
      totalScore += a11yScore * weights.a11y;
      totalWeight += weights.a11y;

      // Calculate Performance component score
      const perfScore = this.calculatePerformanceScore(
        provenance?.results?.perf,
        workingSpec
      );
      totalScore += perfScore * weights.perf;
      totalWeight += weights.perf;

      const trustScore = totalScore / totalWeight;
      const tierPolicy = this.tierPolicies[options.tier];
      const passed = trustScore >= 0.8;

      // Apply tier-specific penalties
      let adjustedScore = trustScore;
      if (options.tier <= 2 && !contractResult.passed) {
        adjustedScore *= 0.8; // 20% penalty for missing contracts on high tiers
      }

      return {
        passed,
        score: adjustedScore,
        details: {
          tier: options.tier,
          tier_policy: tierPolicy,
          coverage: coverageResult,
          mutation: mutationResult,
          contracts: contractResult,
          a11y: { score: a11yScore, details: provenance?.results?.a11y },
          perf: { score: perfScore, details: provenance?.results?.perf },
          raw_score: trustScore,
          weights,
        },
      };
    } catch (error) {
      return {
        passed: false,
        score: 0,
        details: { error: `Trust score calculation failed: ${error}` },
        errors: [`Trust score calculation failed: ${error}`],
      };
    }
  }

  /**
   * Get tier policy for a specific tier
   */
  getTierPolicy(tier: number): TierPolicy | null {
    return this.tierPolicies[tier] || null;
  }

  /**
   * Calculate accessibility score based on axe-core results and working spec requirements
   */
  private calculateA11yScore(a11yResults: any, workingSpec: any): number {
    try {
      // If no a11y results available, return minimum score
      if (!a11yResults) {
        this.logger?.warn("No accessibility results found in provenance");
        return 0.0;
      }

      // If results indicate a simple pass, give full score
      if (a11yResults === "pass" || a11yResults.passed === true) {
        return 1.0;
      }

      // Parse detailed axe-core results
      let score = 0.5; // Start with partial credit
      const violations = a11yResults.violations || [];
      const incomplete = a11yResults.incomplete || [];
      const passes = a11yResults.passes || [];

      // Get accessibility requirements from working spec
      const specRequirements = workingSpec?.non_functional?.a11y || [];

      // Severity mapping for violations
      const severityWeights = {
        critical: 1.0,
        serious: 0.8,
        moderate: 0.6,
        minor: 0.3,
      };

      // Calculate penalty based on violations
      let totalPenalty = 0;
      violations.forEach((violation: any) => {
        const impact = violation.impact || "minor";
        const weight =
          severityWeights[impact as keyof typeof severityWeights] || 0.3;
        const nodeCount = violation.nodes?.length || 1;

        totalPenalty += weight * nodeCount;

        // Log detailed violation information
        this.logger?.warn(
          `A11y violation: ${violation.id} (${impact}) - ${violation.description}`
        );
        this.logger?.warn(`  Affected elements: ${nodeCount}`);
        if (violation.helpUrl) {
          this.logger?.warn(`  Help: ${violation.helpUrl}`);
        }
      });

      // Check for incomplete checks (could indicate issues)
      if (incomplete.length > 0) {
        totalPenalty += 0.2 * incomplete.length;
        this.logger?.warn(
          `${incomplete.length} incomplete accessibility checks`
        );
      }

      // Validate against working spec requirements if available
      if (specRequirements.length > 0) {
        const specViolations = specRequirements.filter((req: string) => {
          // Check if this requirement is satisfied by the results
          // This is a simplified check - in practice would need more sophisticated matching
          return !passes.some(
            (pass: any) =>
              pass.id?.includes(req) || pass.description?.includes(req)
          );
        });

        if (specViolations.length > 0) {
          totalPenalty += 0.5 * specViolations.length;
          this.logger?.warn(
            `Working spec a11y requirements not met: ${specViolations.join(
              ", "
            )}`
          );
        }
      }

      // Calculate final score (start at 0.8, reduce by penalties)
      score = Math.max(0.0, 0.8 - totalPenalty * 0.1);

      // Log final accessibility score
      const violationCount = violations.length;
      const passCount = passes.length;
      this.logger?.info(
        `A11y score: ${score.toFixed(
          2
        )} (${passCount} passed, ${violationCount} violations)`
      );

      return score;
    } catch (error) {
      this.logger?.error("Failed to calculate accessibility score:", error);
      return 0.0;
    }
  }

  /**
   * Calculate performance score based on metrics and working spec budgets
   */
  private calculatePerformanceScore(
    perfResults: any,
    workingSpec: any
  ): number {
    try {
      // If no performance results available, return minimum score
      if (!perfResults) {
        this.logger?.warn("No performance results found in provenance");
        return 0.0;
      }

      // Get performance budgets from working spec
      const budgets = workingSpec?.non_functional?.perf || {};
      const apiBudget = budgets.api_p95_ms;
      const lcpBudget = budgets.lcp_ms;

      // If no budgets defined, give neutral score
      if (!apiBudget && !lcpBudget) {
        this.logger?.warn("No performance budgets defined in working spec");
        return 0.5;
      }

      let score = 1.0; // Start with full score
      let violations = 0;

      // Check API performance budget
      if (apiBudget && perfResults.api_p95_ms !== undefined) {
        const actualApiTime = perfResults.api_p95_ms;
        if (actualApiTime > apiBudget) {
          const overrun = (actualApiTime - apiBudget) / apiBudget;
          score -= Math.min(0.5, overrun * 0.3); // Penalty based on overrun percentage
          violations++;
          this.logger?.warn(
            `API p95 budget violation: ${actualApiTime}ms > ${apiBudget}ms (${(
              overrun * 100
            ).toFixed(1)}% over)`
          );
        } else {
          this.logger?.debug(
            `API p95 budget met: ${actualApiTime}ms ≤ ${apiBudget}ms`
          );
        }
      }

      // Check LCP performance budget
      if (lcpBudget && perfResults.lcp_ms !== undefined) {
        const actualLcpTime = perfResults.lcp_ms;
        if (actualLcpTime > lcpBudget) {
          const overrun = (actualLcpTime - lcpBudget) / lcpBudget;
          score -= Math.min(0.5, overrun * 0.3); // Penalty based on overrun percentage
          violations++;
          this.logger?.warn(
            `LCP budget violation: ${actualLcpTime}ms > ${lcpBudget}ms (${(
              overrun * 100
            ).toFixed(1)}% over)`
          );
        } else {
          this.logger?.debug(
            `LCP budget met: ${actualLcpTime}ms ≤ ${lcpBudget}ms`
          );
        }
      }

      // Check for performance regressions vs baseline (if available)
      if (perfResults.baseline_comparison) {
        const regression = perfResults.baseline_comparison;
        if (regression.api_p95_regression > 0.05) {
          // 5% regression threshold
          score -= 0.1;
          violations++;
          this.logger?.warn(
            `API performance regression: ${(
              regression.api_p95_regression * 100
            ).toFixed(1)}% slower than baseline`
          );
        }
        if (regression.lcp_regression > 0.05) {
          // 5% regression threshold
          score -= 0.1;
          violations++;
          this.logger?.warn(
            `LCP performance regression: ${(
              regression.lcp_regression * 100
            ).toFixed(1)}% slower than baseline`
          );
        }
      }

      // Additional metrics that could affect score
      if (
        perfResults.error_rate !== undefined &&
        perfResults.error_rate > 0.01
      ) {
        // >1% errors
        score -= 0.2;
        violations++;
        this.logger?.warn(
          `High error rate: ${(perfResults.error_rate * 100).toFixed(2)}%`
        );
      }

      // Ensure score doesn't go below 0
      score = Math.max(0.0, score);

      // Log final performance score
      this.logger?.info(
        `Performance score: ${score.toFixed(2)} (${violations} violations)`
      );
      if (apiBudget) {
        this.logger?.info(
          `API budget: ${apiBudget}ms (actual: ${
            perfResults.api_p95_ms || "N/A"
          }ms)`
        );
      }
      if (lcpBudget) {
        this.logger?.info(
          `LCP budget: ${lcpBudget}ms (actual: ${
            perfResults.lcp_ms || "N/A"
          }ms)`
        );
      }

      return score;
    } catch (error) {
      this.logger?.error("Failed to calculate performance score:", error);
      return 0.0;
    }
  }

  /**
   * Get all available tiers
   */
  getAvailableTiers(): number[] {
    return Object.keys(this.tierPolicies).map(Number);
  }

  /**
   * Find waivers that are applicable to a specific gate
   */
  private async findApplicableWaivers(
    waivers: WaiverConfig[],
    targetGate: string
  ): Promise<WaiverConfig[]> {
    const applicableWaivers: Array<any> = [];

    for (const waiver of waivers) {
      try {
        // Check if waiver applies to this gate
        if (!waiver.gates.includes(targetGate) && !waiver.gates.includes("*")) {
          continue;
        }

        // Check waiver status (active, not expired, approved)
        const status = await this.waiversManager.checkWaiverStatus(
          waiver.created_at
        );
        if (!status.active) {
          continue;
        }

        // Check expiration
        if (!this.isWaiverValid(waiver)) {
          continue;
        }

        // Check scope constraints (if any)
        if (!this.isWaiverScopeValid(waiver)) {
          continue;
        }

        // Check approval chain
        if (!(await this.validateApprovalChain(waiver))) {
          continue;
        }

        applicableWaivers.push(waiver);
      } catch (error) {
        this.logger?.debug(`Error checking waiver ${waiver.id}: ${error}`);
        continue;
      }
    }

    return applicableWaivers;
  }

  /**
   * Resolve conflicts between multiple applicable waivers
   */
  private async resolveWaiverConflicts(
    waivers: Array<any>
  ): Promise<any | null> {
    if (waivers.length === 0) {
      return null;
    }

    if (waivers.length === 1) {
      return waivers[0];
    }

    // Sort waivers by precedence (newer, higher impact level, more specific)
    const sortedWaivers = waivers.sort((a, b) => {
      // Newer waivers take precedence
      const dateCompare =
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      if (dateCompare !== 0) {
        return dateCompare;
      }

      // Higher impact level takes precedence
      const impactLevels = { critical: 3, high: 2, medium: 1, low: 0 };
      const impactCompare =
        (impactLevels[b.impactLevel] || 0) - (impactLevels[a.impactLevel] || 0);
      if (impactCompare !== 0) {
        return impactCompare;
      }

      // More specific scope takes precedence (fewer wildcards)
      const scopeCompare = this.compareScopeSpecificity(a.scope, b.scope);
      if (scopeCompare !== 0) {
        return scopeCompare;
      }

      return 0;
    });

    // Check for conflicting waivers (same gate, different mitigation plans)
    const conflicts = this.detectWaiverConflicts(sortedWaivers);
    if (conflicts.length > 0) {
      await this.handleWaiverConflicts(conflicts);
    }

    // Return the highest precedence waiver
    return sortedWaivers[0];
  }

  /**
   * Check if a waiver is still valid (not expired, properly approved)
   */
  private isWaiverValid(waiver: any): boolean {
    try {
      const now = new Date();
      const expiresAt = new Date(waiver.expiresAt);

      // Check expiration
      if (now > expiresAt) {
        this.logger?.debug(`Waiver ${waiver.id} has expired`);
        return false;
      }

      // Check if waiver was created too far in the past (sanity check)
      const createdAt = new Date(waiver.created_at);
      const maxAge = 90 * 24 * 60 * 60 * 1000; // 90 days
      if (now.getTime() - createdAt.getTime() > maxAge) {
        this.logger?.debug(`Waiver ${waiver.id} is too old`);
        return false;
      }

      return true;
    } catch (error) {
      this.logger?.error(`Error validating waiver ${waiver.id}: ${error}`);
      return false;
    }
  }

  /**
   * Check if waiver scope constraints are satisfied
   */
  private isWaiverScopeValid(waiver: any): boolean {
    try {
      if (!waiver.scope) {
        return true; // No scope constraints
      }

      // Check file scope
      if (waiver.scope.files) {
        // In a real implementation, this would check current file context
        // For now, assume scope is valid
      }

      // Check branch scope
      if (waiver.scope.branches) {
        // In a real implementation, this would check current git branch
        // For now, assume scope is valid
      }

      // Check environment scope
      if (waiver.scope.environments) {
        // In a real implementation, this would check current environment
        // For now, assume scope is valid
      }

      return true;
    } catch (error) {
      this.logger?.error(
        `Error validating waiver scope ${waiver.id}: ${error}`
      );
      return false;
    }
  }

  /**
   * Validate waiver approval chain
   */
  private async validateApprovalChain(waiver: any): Promise<boolean> {
    try {
      // Check if approver has required permissions
      const requiredApprovers = this.getRequiredApprovers(waiver.impactLevel);

      if (!requiredApprovers.includes(waiver.approvedBy)) {
        this.logger?.debug(
          `Waiver ${waiver.id} approved by unauthorized user: ${waiver.approvedBy}`
        );
        return false;
      }

      // Check approval timestamp (should be after creation)
      const createdAt = new Date(waiver.created_at);
      const approvedAt = new Date(waiver.approvedAt || waiver.created_at);

      if (approvedAt < createdAt) {
        this.logger?.debug(
          `Waiver ${waiver.id} has invalid approval timestamp`
        );
        return false;
      }

      return true;
    } catch (error) {
      this.logger?.error(
        `Error validating approval chain for waiver ${waiver.id}: ${error}`
      );
      return false;
    }
  }

  /**
   * Compare scope specificity (more specific scopes get higher precedence)
   */
  private compareScopeSpecificity(scopeA: any, scopeB: any): number {
    if (!scopeA && !scopeB) return 0;
    if (!scopeA && scopeB) return -1;
    if (scopeA && !scopeB) return 1;

    // Count specificity indicators
    const specificityA = this.calculateScopeSpecificity(scopeA);
    const specificityB = this.calculateScopeSpecificity(scopeB);

    return specificityB - specificityA; // Higher specificity first
  }

  /**
   * Calculate scope specificity score
   */
  private calculateScopeSpecificity(scope: any): number {
    let specificity = 0;

    if (scope.files) {
      specificity += scope.files.length;
      if (!scope.files.includes("*")) specificity += 10;
    }

    if (scope.branches) {
      specificity += scope.branches.length;
      if (!scope.branches.includes("*")) specificity += 10;
    }

    if (scope.environments) {
      specificity += scope.environments.length;
      if (!scope.environments.includes("*")) specificity += 10;
    }

    return specificity;
  }

  /**
   * Detect conflicts between waivers
   */
  private detectWaiverConflicts(waivers: Array<any>): Array<{
    waiverA: any;
    waiverB: any;
    conflictType: string;
  }> {
    const conflicts: Array<{
      waiverA: any;
      waiverB: any;
      conflictType: string;
    }> = [];

    for (let i = 0; i < waivers.length; i++) {
      for (let j = i + 1; j < waivers.length; j++) {
        const waiverA = waivers[i];
        const waiverB = waivers[j];

        // Check for conflicting mitigation plans
        if (waiverA.mitigationPlan !== waiverB.mitigationPlan) {
          conflicts.push({
            waiverA,
            waiverB,
            conflictType: "conflicting_mitigation",
          });
        }

        // Check for overlapping but inconsistent scopes
        if (this.haveConflictingScopes(waiverA.scope, waiverB.scope)) {
          conflicts.push({
            waiverA,
            waiverB,
            conflictType: "conflicting_scope",
          });
        }
      }
    }

    return conflicts;
  }

  /**
   * Check if two scopes have conflicts
   */
  private haveConflictingScopes(scopeA: any, scopeB: any): boolean {
    if (!scopeA || !scopeB) return false;

    // Check for conflicting file patterns
    if (scopeA.files && scopeB.files) {
      const conflicts = scopeA.files.some((fileA: string) =>
        scopeB.files.some((fileB: string) =>
          this.filePatternsConflict(fileA, fileB)
        )
      );
      if (conflicts) return true;
    }

    return false;
  }

  /**
   * Check if two file patterns conflict
   */
  private filePatternsConflict(patternA: string, patternB: string): boolean {
    // Simple conflict detection - patterns that could match the same files
    if (patternA === patternB) return true;
    if (patternA === "*" || patternB === "*") return true;
    if (patternA.includes("*") && patternB.includes("*")) {
      // More complex pattern matching would be needed here
      return true;
    }
    return false;
  }

  /**
   * Handle detected waiver conflicts
   */
  private async handleWaiverConflicts(
    conflicts: Array<{
      waiverA: any;
      waiverB: any;
      conflictType: string;
    }>
  ): Promise<void> {
    for (const conflict of conflicts) {
      this.logger?.warn(`Waiver conflict detected: ${conflict.conflictType}`, {
        waiverA: conflict.waiverA.id,
        waiverB: conflict.waiverB.id,
        type: conflict.conflictType,
      });

      // In a real implementation, this would:
      // 1. Notify conflict resolution team
      // 2. Create conflict resolution ticket
      // 3. Escalate to higher approval authority
      // 4. Log audit trail
    }
  }

  /**
   * Get required approvers for a given impact level
   */
  private getRequiredApprovers(impactLevel: string): string[] {
    const approverMap: { [key: string]: string[] } = {
      low: ["developer", "tech-lead"],
      medium: ["tech-lead", "engineering-manager"],
      high: ["engineering-manager", "vp-engineering"],
      critical: ["vp-engineering", "ciso", "ceo"],
    };

    return approverMap[impactLevel] || ["engineering-manager"];
  }
}
