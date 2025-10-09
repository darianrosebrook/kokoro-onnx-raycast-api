#!/usr/bin/env node

/**
 * @fileoverview CAWS Legacy Codebase Assessment Tool
 * Evaluates existing projects and provides incremental adoption roadmap for CAWS
 * @author @darianrosebrook
 */

const fs = require('fs');
const path = require('path');

/**
 * Assessment categories and their scoring criteria
 */
const ASSESSMENT_CATEGORIES = {
  TESTING: {
    name: 'Testing Infrastructure',
    weight: 0.25,
    indicators: {
      testFiles: { weight: 0.3, description: 'Presence of test files' },
      testCoverage: { weight: 0.25, description: 'Code coverage metrics' },
      testTypes: { weight: 0.2, description: 'Unit, integration, and E2E tests' },
      testQuality: { weight: 0.15, description: 'Test structure and assertions' },
      testAutomation: { weight: 0.1, description: 'CI/CD integration' },
    },
  },
  DOCUMENTATION: {
    name: 'Documentation Quality',
    weight: 0.2,
    indicators: {
      readmeQuality: { weight: 0.3, description: 'README completeness' },
      codeComments: { weight: 0.25, description: 'Inline documentation' },
      apiDocs: { weight: 0.2, description: 'API documentation' },
      architectureDocs: { weight: 0.15, description: 'Architecture documentation' },
      changelog: { weight: 0.1, description: 'Change tracking' },
    },
  },
  CODE_QUALITY: {
    name: 'Code Quality',
    weight: 0.2,
    indicators: {
      linting: { weight: 0.25, description: 'Linting configuration' },
      formatting: { weight: 0.2, description: 'Code formatting standards' },
      complexity: { weight: 0.2, description: 'Cyclomatic complexity' },
      dependencies: { weight: 0.2, description: 'Dependency management' },
      security: { weight: 0.15, description: 'Security scanning' },
    },
  },
  PROJECT_STRUCTURE: {
    name: 'Project Structure',
    weight: 0.15,
    indicators: {
      organization: { weight: 0.3, description: 'Logical file organization' },
      buildConfig: { weight: 0.25, description: 'Build configuration' },
      packageManagement: { weight: 0.2, description: 'Package management' },
      ciCd: { weight: 0.15, description: 'CI/CD configuration' },
      versionControl: { weight: 0.1, description: 'Version control setup' },
    },
  },
  PROCESS_MATURITY: {
    name: 'Process Maturity',
    weight: 0.2,
    indicators: {
      branchingStrategy: { weight: 0.25, description: 'Branching and merging strategy' },
      codeReview: { weight: 0.25, description: 'Code review process' },
      releaseProcess: { weight: 0.2, description: 'Release management' },
      issueTracking: { weight: 0.15, description: 'Issue tracking' },
      teamCollaboration: { weight: 0.15, description: 'Team collaboration tools' },
    },
  },
};

/**
 * Assess a project directory for CAWS readiness
 * @param {string} projectDir - Project directory path
 * @returns {Object} Assessment results
 */
function assessProject(projectDir = process.cwd()) {
  console.log(`🔍 Assessing project for CAWS adoption: ${projectDir}`);

  const assessment = {
    projectInfo: getProjectInfo(projectDir),
    scores: {},
    recommendations: [],
    adoptionRoadmap: [],
    riskProfile: {},
  };

  // Calculate scores for each category
  Object.keys(ASSESSMENT_CATEGORIES).forEach((category) => {
    assessment.scores[category] = calculateCategoryScore(projectDir, category);
  });

  // Calculate overall readiness score
  assessment.overallScore = calculateOverallScore(assessment.scores);

  // Generate recommendations
  assessment.recommendations = generateRecommendations(assessment.scores);

  // Generate adoption roadmap
  assessment.adoptionRoadmap = generateAdoptionRoadmap(assessment.scores);

  // Assess risk profile
  assessment.riskProfile = assessRiskProfile(projectDir, assessment.scores);

  return assessment;
}

/**
 * Get basic project information
 */
function getProjectInfo(projectDir) {
  const info = {
    name: path.basename(projectDir),
    path: projectDir,
    languages: [],
    packageManager: null,
    frameworks: [],
    size: { files: 0, lines: 0, directories: 0 },
  };

  // Detect languages and frameworks
  try {
    const files = fs.readdirSync(projectDir, { recursive: true });

    files.forEach((file) => {
      const filePath = path.join(projectDir, file);
      const stat = fs.statSync(filePath);

      if (stat.isFile()) {
        info.size.files++;
        if (file.endsWith('.js') || file.endsWith('.ts')) {
          info.languages.push('javascript');
          if (file.includes('react') || file.includes('vue') || file.includes('angular')) {
            info.frameworks.push('frontend');
          }
        } else if (file.endsWith('.py')) {
          info.languages.push('python');
        } else if (file.endsWith('.java')) {
          info.languages.push('java');
        } else if (file.endsWith('.go')) {
          info.languages.push('go');
        } else if (file.endsWith('.rs')) {
          info.languages.push('rust');
        }
      } else if (stat.isDirectory()) {
        info.size.directories++;
      }
    });

    // Remove duplicates
    info.languages = [...new Set(info.languages)];
    info.frameworks = [...new Set(info.frameworks)];

    // Detect package manager
    if (fs.existsSync(path.join(projectDir, 'package.json'))) {
      info.packageManager = 'npm';
    } else if (fs.existsSync(path.join(projectDir, 'requirements.txt'))) {
      info.packageManager = 'pip';
    } else if (fs.existsSync(path.join(projectDir, 'pom.xml'))) {
      info.packageManager = 'maven';
    } else if (fs.existsSync(path.join(projectDir, 'go.mod'))) {
      info.packageManager = 'go modules';
    } else if (fs.existsSync(path.join(projectDir, 'Cargo.toml'))) {
      info.packageManager = 'cargo';
    }
  } catch (error) {
    console.warn('⚠️  Error gathering project info:', error.message);
  }

  return info;
}

/**
 * Calculate score for a specific category
 */
function calculateCategoryScore(projectDir, category) {
  const categoryInfo = ASSESSMENT_CATEGORIES[category];
  let totalScore = 0;

  Object.keys(categoryInfo.indicators).forEach((indicator) => {
    const indicatorInfo = categoryInfo.indicators[indicator];
    const score = calculateIndicatorScore(projectDir, category, indicator);
    const weightedScore = score * indicatorInfo.weight;
    totalScore += weightedScore;
  });

  return Math.round(totalScore * 100);
}

/**
 * Calculate score for a specific indicator
 */
function calculateIndicatorScore(projectDir, category, indicator) {
  switch (category) {
    case 'TESTING':
      return calculateTestingScore(projectDir, indicator);
    case 'DOCUMENTATION':
      return calculateDocumentationScore(projectDir, indicator);
    case 'CODE_QUALITY':
      return calculateCodeQualityScore(projectDir, indicator);
    case 'PROJECT_STRUCTURE':
      return calculateProjectStructureScore(projectDir, indicator);
    case 'PROCESS_MATURITY':
      return calculateProcessMaturityScore(projectDir, indicator);
    default:
      return 0.5; // Neutral score
  }
}

/**
 * Calculate testing-related scores
 */
function calculateTestingScore(projectDir, indicator) {
  const testDir = path.join(projectDir, 'tests') || path.join(projectDir, 'test');

  switch (indicator) {
    case 'testFiles':
      if (fs.existsSync(testDir)) {
        const testFiles = fs
          .readdirSync(testDir)
          .filter((f) => f.includes('test') || f.includes('spec'));
        return Math.min(testFiles.length / 10, 1); // Scale based on number of test files
      }
      return 0;

    case 'testCoverage':
      // Check for coverage configuration
      const coverageFiles = [
        '.nycrc',
        'jest.config.js',
        'coverage.json',
        'sonar-project.properties',
      ];
      const hasCoverage = coverageFiles.some((file) => fs.existsSync(path.join(projectDir, file)));
      return hasCoverage ? 1 : 0;

    case 'testTypes':
      if (fs.existsSync(testDir)) {
        const files = fs.readdirSync(testDir);
        let types = 0;
        if (files.some((f) => f.includes('unit'))) types += 0.3;
        if (files.some((f) => f.includes('integration'))) types += 0.3;
        if (files.some((f) => f.includes('e2e'))) types += 0.4;
        return Math.min(types, 1);
      }
      return 0;

    case 'testQuality':
      // Basic check for test structure
      if (fs.existsSync(testDir)) {
        const testContent = fs
          .readdirSync(testDir)
          .filter((f) => f.endsWith('.js') || f.endsWith('.ts'))
          .map((f) => fs.readFileSync(path.join(testDir, f), 'utf8'))
          .join('');

        const hasAssertions = /\b(expect|assert|should)\b/.test(testContent);
        const hasDescribe = /\bdescribe\b/.test(testContent);
        return hasAssertions && hasDescribe ? 0.8 : 0.3;
      }
      return 0;

    case 'testAutomation':
      const hasCI =
        fs.existsSync(path.join(projectDir, '.github/workflows')) ||
        fs.existsSync(path.join(projectDir, '.gitlab-ci.yml')) ||
        fs.existsSync(path.join(projectDir, 'Jenkinsfile'));
      return hasCI ? 1 : 0;

    default:
      return 0.5;
  }
}

/**
 * Calculate documentation-related scores
 */
function calculateDocumentationScore(projectDir, indicator) {
  switch (indicator) {
    case 'readmeQuality':
      const readmePath = path.join(projectDir, 'README.md');
      if (fs.existsSync(readmePath)) {
        const readme = fs.readFileSync(readmePath, 'utf8');
        const score =
          (readme.length > 500 ? 0.4 : 0) +
          (readme.includes('#') ? 0.2 : 0) +
          (readme.includes('install') || readme.includes('setup') ? 0.2 : 0) +
          (readme.includes('usage') || readme.includes('example') ? 0.2 : 0);
        return Math.min(score, 1);
      }
      return 0;

    case 'codeComments':
      // Basic check for comment density
      const sourceFiles = getSourceFiles(projectDir);
      if (sourceFiles.length === 0) return 0.5;

      const totalLines = sourceFiles.reduce((sum, file) => {
        return sum + fs.readFileSync(file, 'utf8').split('\n').length;
      }, 0);

      const commentLines = sourceFiles.reduce((sum, file) => {
        const content = fs.readFileSync(file, 'utf8');
        return (
          sum +
          (content.match(/\/\//g) || []).length +
          (content.match(/\/\*/g) || []).length +
          (content.match(/#/g) || []).length
        );
      }, 0);

      const commentRatio = commentLines / totalLines;
      return Math.min(commentRatio * 5, 1); // Scale comment ratio

    case 'apiDocs':
      const hasApiDocs =
        fs.existsSync(path.join(projectDir, 'docs/api')) ||
        fs.existsSync(path.join(projectDir, 'docs/API.md'));
      return hasApiDocs ? 1 : 0;

    case 'architectureDocs':
      const hasArchDocs =
        fs.existsSync(path.join(projectDir, 'docs/architecture')) ||
        fs.existsSync(path.join(projectDir, 'ARCHITECTURE.md'));
      return hasArchDocs ? 1 : 0;

    case 'changelog':
      const hasChangelog =
        fs.existsSync(path.join(projectDir, 'CHANGELOG.md')) ||
        fs.existsSync(path.join(projectDir, 'HISTORY.md'));
      return hasChangelog ? 1 : 0;

    default:
      return 0.5;
  }
}

/**
 * Calculate code quality scores
 */
function calculateCodeQualityScore(projectDir, indicator) {
  switch (indicator) {
    case 'linting':
      const lintingFiles = ['.eslintrc', '.prettierrc', 'tsconfig.json', '.editorconfig'];
      const hasLinting = lintingFiles.some((file) => fs.existsSync(path.join(projectDir, file)));
      return hasLinting ? 1 : 0;

    case 'formatting':
      // Check if formatting tools are likely configured
      return 0.7; // Assume some formatting exists

    case 'complexity':
      // Basic complexity check (could be enhanced with actual analysis)
      return 0.6; // Neutral score

    case 'dependencies':
      const hasPackageFile =
        fs.existsSync(path.join(projectDir, 'package.json')) ||
        fs.existsSync(path.join(projectDir, 'requirements.txt')) ||
        fs.existsSync(path.join(projectDir, 'pom.xml'));
      return hasPackageFile ? 1 : 0;

    case 'security':
      const hasSecurity =
        fs.existsSync(path.join(projectDir, '.github/workflows')) &&
        fs
          .readdirSync(path.join(projectDir, '.github/workflows'))
          .some((f) => f.includes('security') || f.includes('audit'));
      return hasSecurity ? 1 : 0;

    default:
      return 0.5;
  }
}

/**
 * Calculate project structure scores
 */
function calculateProjectStructureScore(projectDir, indicator) {
  switch (indicator) {
    case 'organization':
      const srcDir =
        fs.existsSync(path.join(projectDir, 'src')) || fs.existsSync(path.join(projectDir, 'lib'));
      return srcDir ? 1 : 0.5;

    case 'buildConfig':
      const buildFiles = ['package.json', 'Makefile', 'CMakeLists.txt', 'build.gradle'];
      const hasBuild = buildFiles.some((file) => fs.existsSync(path.join(projectDir, file)));
      return hasBuild ? 1 : 0;

    case 'packageManagement':
      const packageFiles = ['package.json', 'requirements.txt', 'pom.xml', 'go.mod', 'Cargo.toml'];
      const hasPackage = packageFiles.some((file) => fs.existsSync(path.join(projectDir, file)));
      return hasPackage ? 1 : 0;

    case 'ciCd':
      const hasCI =
        fs.existsSync(path.join(projectDir, '.github')) ||
        fs.existsSync(path.join(projectDir, '.gitlab-ci.yml'));
      return hasCI ? 1 : 0;

    case 'versionControl':
      // Check for .git directory (basic check)
      return fs.existsSync(path.join(projectDir, '.git')) ? 1 : 0;

    default:
      return 0.5;
  }
}

/**
 * Calculate process maturity scores
 */
function calculateProcessMaturityScore(projectDir, indicator) {
  switch (indicator) {
    case 'branchingStrategy':
      // Check for branch protection or common branching files
      const hasBranches =
        fs.existsSync(path.join(projectDir, '.github/workflows')) &&
        fs
          .readdirSync(path.join(projectDir, '.github/workflows'))
          .some((f) => f.includes('branch') || f.includes('merge'));
      return hasBranches ? 0.8 : 0.3;

    case 'codeReview':
      const hasPRTemplate = fs.existsSync(
        path.join(projectDir, '.github/PULL_REQUEST_TEMPLATE.md')
      );
      return hasPRTemplate ? 0.9 : 0.4;

    case 'releaseProcess':
      const hasReleaseWorkflow =
        fs.existsSync(path.join(projectDir, '.github/workflows')) &&
        fs
          .readdirSync(path.join(projectDir, '.github/workflows'))
          .some((f) => f.includes('release') || f.includes('publish'));
      return hasReleaseWorkflow ? 1 : 0;

    case 'issueTracking':
      const hasIssueTemplate = fs.existsSync(path.join(projectDir, '.github/ISSUE_TEMPLATE'));
      return hasIssueTemplate ? 0.8 : 0.2;

    case 'teamCollaboration':
      const hasContributing = fs.existsSync(path.join(projectDir, 'CONTRIBUTING.md'));
      return hasContributing ? 0.7 : 0.3;

    default:
      return 0.5;
  }
}

/**
 * Get source files for analysis
 */
function getSourceFiles(projectDir) {
  const sourceFiles = [];

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
        } else if (stat.isFile() && /\.(js|ts|py|java|go|rs)$/.test(file)) {
          sourceFiles.push(filePath);
        }
      });
    } catch (error) {
      // Skip directories we can't read
    }
  }

  scanDirectory(projectDir);
  return sourceFiles;
}

/**
 * Calculate overall readiness score
 */
function calculateOverallScore(categoryScores) {
  let totalScore = 0;

  Object.keys(categoryScores).forEach((category) => {
    totalScore += categoryScores[category] * ASSESSMENT_CATEGORIES[category].weight;
  });

  return Math.round(totalScore);
}

/**
 * Generate recommendations based on scores
 */
function generateRecommendations(scores) {
  const recommendations = [];

  Object.keys(scores).forEach((category) => {
    const score = scores[category];
    const categoryInfo = ASSESSMENT_CATEGORIES[category];

    if (score < 40) {
      recommendations.push({
        category: categoryInfo.name,
        priority: 'high',
        message: `${categoryInfo.name} needs significant improvement (Score: ${score}/100)`,
        suggestions: getCategorySuggestions(category, 'high'),
      });
    } else if (score < 70) {
      recommendations.push({
        category: categoryInfo.name,
        priority: 'medium',
        message: `${categoryInfo.name} has room for improvement (Score: ${score}/100)`,
        suggestions: getCategorySuggestions(category, 'medium'),
      });
    }
  });

  return recommendations;
}

/**
 * Get category-specific suggestions
 */
function getCategorySuggestions(category, priority) {
  const suggestions = {
    TESTING: {
      high: [
        'Add comprehensive unit test suite',
        'Implement integration tests for critical paths',
        'Set up test automation in CI/CD',
        'Add test coverage reporting',
      ],
      medium: [
        'Improve test coverage for existing code',
        'Add more edge case testing',
        'Implement automated test execution',
      ],
    },
    DOCUMENTATION: {
      high: [
        'Create comprehensive README with setup instructions',
        'Add inline code documentation',
        'Document API endpoints and usage',
        'Create architecture documentation',
      ],
      medium: ['Enhance existing documentation', 'Add code examples', 'Document recent changes'],
    },
    CODE_QUALITY: {
      high: [
        'Set up linting and code formatting',
        'Implement code quality gates',
        'Add security scanning',
        'Manage technical debt',
      ],
      medium: [
        'Improve code formatting consistency',
        'Add static code analysis',
        'Update dependencies regularly',
      ],
    },
  };

  return suggestions[category]?.[priority] || ['Improve this area'];
}

/**
 * Generate phased adoption roadmap
 */
function generateAdoptionRoadmap(scores) {
  const phases = [
    {
      name: 'Foundation Setup',
      duration: '2-4 weeks',
      prerequisites: ['Basic project structure', 'Development environment'],
      tasks: [
        'Set up CAWS CLI and basic configuration',
        'Create initial working spec template',
        'Establish basic linting and formatting',
        'Set up version control and CI basics',
      ],
      success_criteria: 'CAWS CLI operational, basic quality gates in place',
    },
    {
      name: 'Testing Infrastructure',
      duration: '4-6 weeks',
      prerequisites: ['Foundation setup complete'],
      tasks: [
        'Implement comprehensive test suite',
        'Add test coverage reporting',
        'Set up mutation testing',
        'Integrate tests into CI/CD',
      ],
      success_criteria: 'Test coverage >70%, automated testing operational',
    },
    {
      name: 'Documentation & Quality',
      duration: '3-5 weeks',
      prerequisites: ['Testing infrastructure complete'],
      tasks: [
        'Complete project documentation',
        'Implement advanced quality gates',
        'Add contract testing',
        'Set up monitoring and observability',
      ],
      success_criteria: 'Full CAWS compliance, comprehensive documentation',
    },
  ];

  // Adjust phases based on current scores
  return phases.map((phase, index) => ({
    ...phase,
    priority: index + 1,
    estimated_effort: scores[Object.keys(scores)[index]] < 50 ? 'high' : 'medium',
  }));
}

/**
 * Assess risk profile of the project
 */
function assessRiskProfile(projectDir, scores) {
  const profile = {
    overall_risk: 'medium',
    risk_factors: [],
    recommended_tier: 2,
  };

  // Determine risk based on scores
  const avgScore = Object.values(scores).reduce((a, b) => a + b, 0) / Object.keys(scores).length;

  if (avgScore < 40) {
    profile.overall_risk = 'high';
    profile.risk_factors.push('Low test coverage and documentation');
    profile.risk_factors.push('Missing quality gates');
    profile.recommended_tier = 1;
  } else if (avgScore < 70) {
    profile.overall_risk = 'medium';
    profile.risk_factors.push('Inconsistent testing practices');
    profile.risk_factors.push('Documentation gaps');
    profile.recommended_tier = 2;
  } else {
    profile.overall_risk = 'low';
    profile.risk_factors.push('Good foundation for quality practices');
    profile.recommended_tier = 3;
  }

  // Add specific risk factors
  if (scores.TESTING < 30) {
    profile.risk_factors.push('Critical: Minimal testing infrastructure');
  }
  if (scores.DOCUMENTATION < 30) {
    profile.risk_factors.push('High: Poor documentation quality');
  }
  if (scores.CODE_QUALITY < 40) {
    profile.risk_factors.push('Medium: Code quality needs improvement');
  }

  return profile;
}

// CLI interface
if (require.main === module) {
  const command = process.argv[2];
  const projectDir = process.argv[3] || process.cwd();

  switch (command) {
    case 'assess':
      console.log(`🔍 Assessing CAWS readiness for project: ${projectDir}`);

      const assessment = assessProject(projectDir);

      console.log('\n📊 CAWS Readiness Assessment Results:');
      console.log(`🏆 Overall Score: ${assessment.overallScore}/100`);

      console.log('\n📈 Category Scores:');
      Object.keys(assessment.scores).forEach((category) => {
        const score = assessment.scores[category];
        const categoryInfo = ASSESSMENT_CATEGORIES[category];
        const status =
          score >= 80
            ? '✅ Excellent'
            : score >= 60
              ? '🟢 Good'
              : score >= 40
                ? '🟡 Fair'
                : '🔴 Poor';
        console.log(`${status} ${categoryInfo.name}: ${score}/100`);
      });

      console.log('\n📋 Project Information:');
      console.log(`   Languages: ${assessment.projectInfo.languages.join(', ')}`);
      console.log(`   Package Manager: ${assessment.projectInfo.packageManager || 'Not detected'}`);
      console.log(
        `   Frameworks: ${assessment.projectInfo.frameworks.join(', ') || 'None detected'}`
      );
      console.log(
        `   Project Size: ${assessment.projectInfo.size.files} files, ${assessment.projectInfo.size.directories} directories`
      );

      if (assessment.recommendations.length > 0) {
        console.log('\n💡 Priority Recommendations:');
        assessment.recommendations.forEach((rec, index) => {
          console.log(`\n${index + 1}. [${rec.priority.toUpperCase()}] ${rec.category}`);
          console.log(`   ${rec.message}`);
          rec.suggestions.forEach((suggestion) => {
            console.log(`   • ${suggestion}`);
          });
        });
      }

      console.log('\n🗓️  Adoption Roadmap:');
      assessment.adoptionRoadmap.forEach((phase, index) => {
        console.log(`\n${index + 1}. ${phase.name} (${phase.duration})`);
        console.log(`   Priority: ${phase.priority} | Effort: ${phase.estimated_effort}`);
        console.log(`   Tasks: ${phase.tasks.join(', ')}`);
        console.log(`   Success: ${phase.success_criteria}`);
      });

      console.log('\n⚠️  Risk Profile:');
      console.log(`   Overall Risk: ${assessment.riskProfile.overall_risk}`);
      console.log(`   Recommended Tier: ${assessment.riskProfile.recommended_tier}`);
      assessment.riskProfile.risk_factors.forEach((factor) => {
        console.log(`   • ${factor}`);
      });

      console.log('\n🎯 Next Steps:');
      console.log('   1. Start with Foundation setup tasks');
      console.log('   2. Address high-priority recommendations first');
      console.log('   3. Set up CAWS CLI and create initial working spec');
      console.log('   4. Gradually implement testing and quality improvements');

      break;

    default:
      console.log('CAWS Legacy Codebase Assessment Tool');
      console.log('Usage:');
      console.log('  node legacy-assessor.js assess [project-directory]');
      console.log('');
      console.log('Assessment Categories:');
      Object.values(ASSESSMENT_CATEGORIES).forEach((category) => {
        console.log(`  - ${category.name} (${Math.round(category.weight * 100)}% weight)`);
      });
      console.log('');
      console.log('Examples:');
      console.log('  node legacy-assessor.js assess .');
      console.log('  node legacy-assessor.js assess /path/to/project');
      process.exit(1);
  }
}

module.exports = {
  assessProject,
  ASSESSMENT_CATEGORIES,
  generateRecommendations,
  generateAdoptionRoadmap,
};
