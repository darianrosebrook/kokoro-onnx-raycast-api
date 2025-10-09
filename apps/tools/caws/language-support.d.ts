#!/usr/bin/env node
export namespace LANGUAGE_CONFIGS {
    namespace javascript {
        let name: string;
        let extensions: string[];
        let testExtensions: string[];
        namespace qualityTools {
            namespace unitTest {
                let commands: string[];
                let coverageCommand: string;
                let defaultCommand: string;
            }
            namespace mutationTest {
                let commands_1: string[];
                export { commands_1 as commands };
                let defaultCommand_1: string;
                export { defaultCommand_1 as defaultCommand };
            }
            namespace lint {
                let commands_2: string[];
                export { commands_2 as commands };
                let defaultCommand_2: string;
                export { defaultCommand_2 as defaultCommand };
            }
            namespace format {
                let commands_3: string[];
                export { commands_3 as commands };
                let defaultCommand_3: string;
                export { defaultCommand_3 as defaultCommand };
            }
            namespace typeCheck {
                let commands_4: string[];
                export { commands_4 as commands };
                let defaultCommand_4: string;
                export { defaultCommand_4 as defaultCommand };
            }
            namespace contractTest {
                let commands_5: string[];
                export { commands_5 as commands };
                let defaultCommand_5: string;
                export { defaultCommand_5 as defaultCommand };
            }
        }
        let coverageReports: string[];
        let tierAdjustments: {
            1: {
                min_branch: number;
                min_mutation: number;
            };
            2: {
                min_branch: number;
                min_mutation: number;
            };
            3: {
                min_branch: number;
                min_mutation: number;
            };
        };
    }
    namespace python {
        let name_1: string;
        export { name_1 as name };
        let extensions_1: string[];
        export { extensions_1 as extensions };
        let testExtensions_1: string[];
        export { testExtensions_1 as testExtensions };
        export namespace qualityTools_1 {
            export namespace unitTest_1 {
                let commands_6: string[];
                export { commands_6 as commands };
                let coverageCommand_1: string;
                export { coverageCommand_1 as coverageCommand };
                let defaultCommand_6: string;
                export { defaultCommand_6 as defaultCommand };
            }
            export { unitTest_1 as unitTest };
            export namespace mutationTest_1 {
                let commands_7: string[];
                export { commands_7 as commands };
                let defaultCommand_7: string;
                export { defaultCommand_7 as defaultCommand };
            }
            export { mutationTest_1 as mutationTest };
            export namespace lint_1 {
                let commands_8: string[];
                export { commands_8 as commands };
                let defaultCommand_8: string;
                export { defaultCommand_8 as defaultCommand };
            }
            export { lint_1 as lint };
            export namespace format_1 {
                let commands_9: string[];
                export { commands_9 as commands };
                let defaultCommand_9: string;
                export { defaultCommand_9 as defaultCommand };
            }
            export { format_1 as format };
            export namespace typeCheck_1 {
                let commands_10: string[];
                export { commands_10 as commands };
                let defaultCommand_10: string;
                export { defaultCommand_10 as defaultCommand };
            }
            export { typeCheck_1 as typeCheck };
            export namespace contractTest_1 {
                let commands_11: string[];
                export { commands_11 as commands };
                let defaultCommand_11: string;
                export { defaultCommand_11 as defaultCommand };
            }
            export { contractTest_1 as contractTest };
        }
        export { qualityTools_1 as qualityTools };
        let coverageReports_1: string[];
        export { coverageReports_1 as coverageReports };
        let tierAdjustments_1: {
            1: {
                min_branch: number;
                min_mutation: number;
            };
            2: {
                min_branch: number;
                min_mutation: number;
            };
            3: {
                min_branch: number;
                min_mutation: number;
            };
        };
        export { tierAdjustments_1 as tierAdjustments };
    }
    namespace java {
        let name_2: string;
        export { name_2 as name };
        let extensions_2: string[];
        export { extensions_2 as extensions };
        let testExtensions_2: string[];
        export { testExtensions_2 as testExtensions };
        export namespace qualityTools_2 {
            export namespace unitTest_2 {
                let commands_12: string[];
                export { commands_12 as commands };
                let coverageCommand_2: string;
                export { coverageCommand_2 as coverageCommand };
                let defaultCommand_12: string;
                export { defaultCommand_12 as defaultCommand };
            }
            export { unitTest_2 as unitTest };
            export namespace mutationTest_2 {
                let commands_13: string[];
                export { commands_13 as commands };
                let defaultCommand_13: string;
                export { defaultCommand_13 as defaultCommand };
            }
            export { mutationTest_2 as mutationTest };
            export namespace lint_2 {
                let commands_14: string[];
                export { commands_14 as commands };
                let defaultCommand_14: string;
                export { defaultCommand_14 as defaultCommand };
            }
            export { lint_2 as lint };
            export namespace format_2 {
                let commands_15: string[];
                export { commands_15 as commands };
                let defaultCommand_15: string;
                export { defaultCommand_15 as defaultCommand };
            }
            export { format_2 as format };
            export namespace contractTest_2 {
                let commands_16: string[];
                export { commands_16 as commands };
                let defaultCommand_16: string;
                export { defaultCommand_16 as defaultCommand };
            }
            export { contractTest_2 as contractTest };
        }
        export { qualityTools_2 as qualityTools };
        let coverageReports_2: string[];
        export { coverageReports_2 as coverageReports };
        let tierAdjustments_2: {
            1: {
                min_branch: number;
                min_mutation: number;
            };
            2: {
                min_branch: number;
                min_mutation: number;
            };
            3: {
                min_branch: number;
                min_mutation: number;
            };
        };
        export { tierAdjustments_2 as tierAdjustments };
    }
    namespace go {
        let name_3: string;
        export { name_3 as name };
        let extensions_3: string[];
        export { extensions_3 as extensions };
        let testExtensions_3: string[];
        export { testExtensions_3 as testExtensions };
        export namespace qualityTools_3 {
            export namespace unitTest_3 {
                let commands_17: string[];
                export { commands_17 as commands };
                let coverageCommand_3: string;
                export { coverageCommand_3 as coverageCommand };
                let defaultCommand_17: string;
                export { defaultCommand_17 as defaultCommand };
            }
            export { unitTest_3 as unitTest };
            export namespace mutationTest_3 {
                let commands_18: string[];
                export { commands_18 as commands };
                let defaultCommand_18: string;
                export { defaultCommand_18 as defaultCommand };
            }
            export { mutationTest_3 as mutationTest };
            export namespace lint_3 {
                let commands_19: string[];
                export { commands_19 as commands };
                let defaultCommand_19: string;
                export { defaultCommand_19 as defaultCommand };
            }
            export { lint_3 as lint };
            export namespace format_3 {
                let commands_20: string[];
                export { commands_20 as commands };
                let defaultCommand_20: string;
                export { defaultCommand_20 as defaultCommand };
            }
            export { format_3 as format };
            export namespace contractTest_3 {
                let commands_21: string[];
                export { commands_21 as commands };
                let defaultCommand_21: string;
                export { defaultCommand_21 as defaultCommand };
            }
            export { contractTest_3 as contractTest };
        }
        export { qualityTools_3 as qualityTools };
        let coverageReports_3: string[];
        export { coverageReports_3 as coverageReports };
        let tierAdjustments_3: {
            1: {
                min_branch: number;
                min_mutation: number;
            };
            2: {
                min_branch: number;
                min_mutation: number;
            };
            3: {
                min_branch: number;
                min_mutation: number;
            };
        };
        export { tierAdjustments_3 as tierAdjustments };
    }
    namespace rust {
        let name_4: string;
        export { name_4 as name };
        let extensions_4: string[];
        export { extensions_4 as extensions };
        let testExtensions_4: string[];
        export { testExtensions_4 as testExtensions };
        export namespace qualityTools_4 {
            export namespace unitTest_4 {
                let commands_22: string[];
                export { commands_22 as commands };
                let coverageCommand_4: string;
                export { coverageCommand_4 as coverageCommand };
                let defaultCommand_22: string;
                export { defaultCommand_22 as defaultCommand };
            }
            export { unitTest_4 as unitTest };
            export namespace mutationTest_4 {
                let commands_23: string[];
                export { commands_23 as commands };
                let defaultCommand_23: string;
                export { defaultCommand_23 as defaultCommand };
            }
            export { mutationTest_4 as mutationTest };
            export namespace lint_4 {
                let commands_24: string[];
                export { commands_24 as commands };
                let defaultCommand_24: string;
                export { defaultCommand_24 as defaultCommand };
            }
            export { lint_4 as lint };
            export namespace format_4 {
                let commands_25: string[];
                export { commands_25 as commands };
                let defaultCommand_25: string;
                export { defaultCommand_25 as defaultCommand };
            }
            export { format_4 as format };
            export namespace contractTest_4 {
                let commands_26: string[];
                export { commands_26 as commands };
                let defaultCommand_26: string;
                export { defaultCommand_26 as defaultCommand };
            }
            export { contractTest_4 as contractTest };
        }
        export { qualityTools_4 as qualityTools };
        let coverageReports_4: string[];
        export { coverageReports_4 as coverageReports };
        let tierAdjustments_4: {
            1: {
                min_branch: number;
                min_mutation: number;
            };
            2: {
                min_branch: number;
                min_mutation: number;
            };
            3: {
                min_branch: number;
                min_mutation: number;
            };
        };
        export { tierAdjustments_4 as tierAdjustments };
    }
}
/**
 * Detect the primary language of a project
 * @param {string} projectDir - Project directory path
 * @returns {string} Detected language key or 'unknown'
 */
export function detectProjectLanguage(projectDir?: string): string;
/**
 * Get quality tool configuration for a language
 * @param {string} language - Language key
 * @param {string} toolType - Type of tool (unitTest, mutationTest, etc.)
 * @returns {Object} Tool configuration
 */
export function getQualityToolConfig(language: string, toolType: string): any;
/**
 * Generate CI configuration for a language
 * @param {string} language - Language key
 * @param {number} tier - Risk tier (1, 2, 3)
 * @returns {Object} CI configuration
 */
export function generateCIConfig(language: string, tier: number): any;
/**
 * Validate that required tools are installed for a language
 * @param {string} language - Language key
 * @returns {Object} Validation results
 */
export function validateTooling(language: string): any;
/**
 * Generate a language-specific CAWS configuration file
 * @param {string} language - Language key
 * @param {string} configPath - Output configuration path
 */
export function generateLanguageConfig(language: string, configPath?: string): {
    language: string;
    name: any;
    tier: any;
    thresholds: any;
    tools: {};
    generated_at: string;
};
//# sourceMappingURL=language-support.d.ts.map