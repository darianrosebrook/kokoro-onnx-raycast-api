#!/usr/bin/env node

/**
 * @fileoverview CAWS Cross-Functional Integration Workflows
 * Facilitates collaboration between development, accessibility, UX, and product teams
 * @author @darianrosebrook
 */

const fs = require('fs');
const path = require('path');

/**
 * Cross-functional stakeholder roles and responsibilities
 */
const STAKEHOLDER_ROLES = {
  ACCESSIBILITY: {
    name: 'Accessibility Advocate',
    description: 'Ensures compliance with accessibility standards and guidelines',
    responsibilities: [
      'Review accessibility requirements in working spec',
      'Validate a11y test results and recommendations',
      'Approve changes affecting user interface accessibility',
      'Ensure WCAG compliance for Tier 1 features',
    ],
    sign_off_required: true,
    tier_requirement: [1, 2], // Required for Tier 1 and 2
  },

  UX_DESIGN: {
    name: 'UX Designer',
    description: 'Ensures user experience quality and design consistency',
    responsibilities: [
      'Review UX requirements and user journey impact',
      'Validate design system compliance',
      'Approve UI/UX changes for Tier 1 features',
      'Ensure responsive design across devices',
    ],
    sign_off_required: true,
    tier_requirement: [1], // Required for Tier 1 only
  },

  PRODUCT_MANAGER: {
    name: 'Product Manager',
    description: 'Ensures changes align with product strategy and user needs',
    responsibilities: [
      'Review business requirements and user stories',
      'Validate acceptance criteria alignment',
      'Approve changes affecting core user workflows',
      'Ensure feature completeness before release',
    ],
    sign_off_required: true,
    tier_requirement: [1, 2], // Required for Tier 1 and 2
  },

  SECURITY: {
    name: 'Security Engineer',
    description: 'Ensures security compliance and vulnerability mitigation',
    responsibilities: [
      'Review security requirements and threat model',
      'Validate security test results',
      'Approve changes affecting authentication or data',
      'Ensure compliance with security standards',
    ],
    sign_off_required: true,
    tier_requirement: [1], // Required for Tier 1 only
  },

  QA_LEAD: {
    name: 'QA Lead',
    description: 'Ensures comprehensive testing and quality standards',
    responsibilities: [
      'Review test coverage and quality metrics',
      'Validate testing strategy and edge case coverage',
      'Approve release readiness for Tier 1 features',
      'Ensure regression testing completeness',
    ],
    sign_off_required: false,
    tier_requirement: [1], // Optional for Tier 1, recommended
  },

  TECH_LEAD: {
    name: 'Technical Lead',
    description: 'Ensures technical excellence and architecture consistency',
    responsibilities: [
      'Review technical implementation approach',
      'Validate architecture and code quality',
      'Approve complex refactoring or system changes',
      'Ensure performance and scalability requirements',
    ],
    sign_off_required: false,
    tier_requirement: [1, 2], // Recommended for Tier 1 and 2
  },
};

/**
 * Generate cross-functional review checklist
 * @param {string} workingSpecPath - Path to working spec file
 * @param {number} tier - Risk tier (1, 2, or 3)
 * @returns {Object} Review checklist
 */
function generateReviewChecklist(workingSpecPath, tier) {
  console.log(`📋 Generating cross-functional review checklist for Tier ${tier}...`);

  let spec = null;
  try {
    const yaml = require('js-yaml');
    spec = yaml.load(fs.readFileSync(workingSpecPath, 'utf8'));
  } catch (error) {
    console.warn('⚠️  Could not load working spec for review checklist');
  }

  const checklist = {
    metadata: {
      generated_at: new Date().toISOString(),
      tier,
      project_id: spec?.id || 'unknown',
      project_title: spec?.title || 'unknown',
    },

    required_stakeholders: [],
    optional_stakeholders: [],
    review_items: {},
    sign_offs: {},
    status: 'pending',
  };

  // Determine required stakeholders based on tier
  Object.keys(STAKEHOLDER_ROLES).forEach((role) => {
    const roleInfo = STAKEHOLDER_ROLES[role];

    if (roleInfo.tier_requirement.includes(tier)) {
      checklist.required_stakeholders.push({
        role: roleInfo.name,
        description: roleInfo.description,
        required: roleInfo.sign_off_required,
        status: 'pending',
        assignee: null,
        comments: [],
      });
    } else {
      checklist.optional_stakeholders.push({
        role: roleInfo.name,
        description: roleInfo.description,
        required: false,
        status: 'not_required',
        assignee: null,
        comments: [],
      });
    }
  });

  // Generate review items based on working spec
  checklist.review_items = generateReviewItems(spec, tier);

  return checklist;
}

/**
 * Generate specific review items based on working spec content
 */
function generateReviewItems(spec, tier) {
  const items = {};

  if (!spec) {
    return items;
  }

  // Accessibility review items
  items.accessibility = {
    title: 'Accessibility Compliance',
    category: 'ACCESSIBILITY',
    priority: 'high',
    items: [
      {
        id: 'a11y_requirements',
        question:
          'Do the accessibility requirements in the working spec align with WCAG guidelines?',
        required: tier <= 2,
        status: 'pending',
        assignee: null,
        comments: [],
      },
      {
        id: 'a11y_testing',
        question: 'Are accessibility tests included and passing?',
        required: tier <= 2,
        status: 'pending',
        assignee: null,
        comments: [],
      },
      {
        id: 'keyboard_navigation',
        question: 'Does the change maintain keyboard navigation support?',
        required: tier <= 2,
        status: 'pending',
        assignee: null,
        comments: [],
      },
    ],
  };

  // UX design review items
  items.ux_design = {
    title: 'User Experience Quality',
    category: 'UX_DESIGN',
    priority: 'high',
    items: [
      {
        id: 'design_consistency',
        question: 'Does the change maintain design system consistency?',
        required: tier === 1,
        status: 'pending',
        assignee: null,
        comments: [],
      },
      {
        id: 'user_journey',
        question: 'Does the change preserve expected user workflows?',
        required: tier <= 2,
        status: 'pending',
        assignee: null,
        comments: [],
      },
      {
        id: 'responsive_design',
        question: 'Is the change responsive across all device sizes?',
        required: tier <= 2,
        status: 'pending',
        assignee: null,
        comments: [],
      },
    ],
  };

  // Product management review items
  items.product_management = {
    title: 'Product Alignment',
    category: 'PRODUCT_MANAGER',
    priority: 'high',
    items: [
      {
        id: 'business_requirements',
        question: 'Does the change fulfill the stated business requirements?',
        required: tier <= 2,
        status: 'pending',
        assignee: null,
        comments: [],
      },
      {
        id: 'acceptance_criteria',
        question: 'Do the acceptance criteria match the product requirements?',
        required: tier <= 2,
        status: 'pending',
        assignee: null,
        comments: [],
      },
      {
        id: 'user_impact',
        question: 'Has the user impact been properly assessed?',
        required: tier <= 2,
        status: 'pending',
        assignee: null,
        comments: [],
      },
    ],
  };

  // Security review items
  items.security = {
    title: 'Security Compliance',
    category: 'SECURITY',
    priority: 'critical',
    items: [
      {
        id: 'threat_model',
        question: 'Has the threat model been updated for this change?',
        required: tier === 1,
        status: 'pending',
        assignee: null,
        comments: [],
      },
      {
        id: 'security_tests',
        question: 'Are security tests passing and comprehensive?',
        required: tier === 1,
        status: 'pending',
        assignee: null,
        comments: [],
      },
      {
        id: 'data_handling',
        question: 'Does the change handle sensitive data appropriately?',
        required: tier <= 2,
        status: 'pending',
        assignee: null,
        comments: [],
      },
    ],
  };

  // Technical review items
  items.technical = {
    title: 'Technical Excellence',
    category: 'TECH_LEAD',
    priority: 'medium',
    items: [
      {
        id: 'architecture_impact',
        question: 'Does the change maintain architectural integrity?',
        required: tier <= 2,
        status: 'pending',
        assignee: null,
        comments: [],
      },
      {
        id: 'performance_impact',
        question: 'Has performance impact been assessed and is within budget?',
        required: tier <= 2,
        status: 'pending',
        assignee: null,
        comments: [],
      },
      {
        id: 'code_quality',
        question: 'Does the code meet quality standards (tests, documentation, style)?',
        required: true,
        status: 'pending',
        assignee: null,
        comments: [],
      },
    ],
  };

  // QA review items
  items.qa = {
    title: 'Quality Assurance',
    category: 'QA_LEAD',
    priority: 'medium',
    items: [
      {
        id: 'test_coverage',
        question: 'Is test coverage adequate for the risk level?',
        required: tier === 1,
        status: 'pending',
        assignee: null,
        comments: [],
      },
      {
        id: 'edge_cases',
        question: 'Have edge cases and error conditions been tested?',
        required: tier <= 2,
        status: 'pending',
        assignee: null,
        comments: [],
      },
      {
        id: 'regression_testing',
        question: 'Has regression testing been planned and executed?',
        required: tier <= 2,
        status: 'pending',
        assignee: null,
        comments: [],
      },
    ],
  };

  return items;
}

/**
 * Generate stakeholder notification templates
 * @param {Object} checklist - Review checklist
 * @returns {Object} Notification templates
 */
function generateNotificationTemplates(checklist) {
  const templates = {};

  // Generate notification for each required stakeholder
  checklist.required_stakeholders.forEach((stakeholder) => {
    const role = stakeholder.role.toLowerCase().replace(/\s+/g, '_');

    templates[role] = {
      subject: `CAWS Review Request: ${checklist.metadata.project_title} (Tier ${checklist.metadata.tier})`,
      body: `Dear ${stakeholder.role},

A new change requires your review as part of the CAWS (Coding Agent Workflow System) process.

**Project Details:**
- Project ID: ${checklist.metadata.project_id}
- Title: ${checklist.metadata.project_title}
- Risk Tier: ${checklist.metadata.tier}
- Generated: ${new Date(checklist.metadata.generated_at).toLocaleString()}

**Your Responsibilities:**
${STAKEHOLDER_ROLES[stakeholder.role.toUpperCase().replace(/\s+/g, '_')]?.responsibilities.map((resp) => `- ${resp}`).join('\n') || 'Review the proposed changes for compliance with your area of expertise.'}

**Review Items:**
${
  Object.values(checklist.review_items)
    .filter((item) => item.category === stakeholder.role.toUpperCase().replace(/\s+/g, '_'))
    .flatMap((item) => item.items)
    .map((reviewItem) => `- ${reviewItem.question}`)
    .join('\n') || 'Please review the change for general compliance.'
}

**Next Steps:**
1. Review the working spec and implementation
2. Provide feedback or approval in the PR comments
3. Update your review status in the checklist

**Timeline:**
Please complete your review within 2 business days for Tier ${checklist.metadata.tier} changes.

**Resources:**
- Working Spec: .caws/working-spec.yaml
- CAWS Documentation: [Link to CAWS docs]
- Dashboard: [Link to CAWS dashboard]

Thank you for your expertise in ensuring the quality and safety of our codebase.

Best regards,
CAWS Automation System`,
    };
  });

  return templates;
}

/**
 * Generate integration workflow configuration
 * @param {Object} checklist - Review checklist
 * @param {string} outputDir - Output directory for workflow files
 */
function generateIntegrationWorkflow(checklist, outputDir = '.github/workflows') {
  const workflow = {
    name: 'CAWS Cross-Functional Review',
    on: {
      pull_request: {
        types: ['opened', 'synchronize', 'reopened'],
        paths: ['.caws/working-spec.yaml'],
      },
    },
    jobs: {
      cross_functional_review: {
        'runs-on': 'ubuntu-latest',
        steps: [
          {
            name: 'Checkout code',
            uses: 'actions/checkout@v4',
          },
          {
            name: 'Generate review checklist',
            run: 'node apps/tools/caws/cross-functional.js generate-checklist .caws/working-spec.yaml',
          },
          {
            name: 'Notify stakeholders',
            run: generateNotificationScript(checklist),
          },
          {
            name: 'Wait for approvals',
            run: generateApprovalWaitScript(checklist),
            timeout: '2d',
          },
        ],
      },
    },
  };

  // Ensure output directory exists
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  const workflowPath = path.join(outputDir, 'caws-cross-functional-review.yml');
  fs.writeFileSync(
    workflowPath,
    `# Generated by CAWS Cross-Functional Tool\n${JSON.stringify(workflow, null, 2)}`
  );

  console.log(`✅ Generated cross-functional review workflow: ${workflowPath}`);
}

/**
 * Generate notification script for workflow
 */
function generateNotificationScript(_checklist) {
  return `
# Generate and send notifications to required stakeholders
node apps/tools/caws/cross-functional.js notify-stakeholders review-checklist.json
`;
}

/**
 * Generate approval wait script for workflow
 */
function generateApprovalWaitScript(_checklist) {
  return `
# Wait for all required stakeholders to approve
node apps/tools/caws/cross-functional.js wait-for-approvals review-checklist.json
`;
}

/**
 * Create stakeholder onboarding guide
 * @param {string} outputPath - Output path for guide
 */
function generateStakeholderGuide(outputPath = 'CAWS_STAKEHOLDER_GUIDE.md') {
  const guide = `# CAWS Cross-Functional Stakeholder Guide

This guide explains how different roles participate in the CAWS (Coding Agent Workflow System) process.

## Overview

CAWS ensures that AI-assisted development meets senior-engineer-level quality standards through structured review processes involving multiple stakeholders.

## Stakeholder Roles and Responsibilities

### Accessibility Advocate
**When Involved:** Tier 1 and 2 changes affecting user interfaces

**Responsibilities:**
- Review accessibility requirements in working spec
- Validate a11y test results and axe-core reports
- Ensure WCAG 2.1 AA compliance
- Approve keyboard navigation and screen reader support

**Review Focus:**
- Color contrast ratios
- Keyboard navigation paths
- Screen reader compatibility
- Focus management
- Alternative text for images

### UX Designer
**When Involved:** Tier 1 changes with UI/UX impact

**Responsibilities:**
- Review design system compliance
- Validate user journey preservation
- Ensure responsive design across devices
- Approve visual consistency

**Review Focus:**
- Design system component usage
- User flow consistency
- Responsive breakpoints
- Visual hierarchy
- Brand consistency

### Product Manager
**When Involved:** Tier 1 and 2 changes with business impact

**Responsibilities:**
- Review business requirement alignment
- Validate acceptance criteria completeness
- Ensure feature meets user needs
- Approve release readiness

**Review Focus:**
- Business requirement fulfillment
- Acceptance criteria accuracy
- User story completeness
- Impact on user workflows

### Security Engineer
**When Involved:** Tier 1 changes affecting security

**Responsibilities:**
- Review threat model updates
- Validate security test results
- Ensure secure coding practices
- Approve authentication/authorization changes

**Review Focus:**
- Authentication mechanisms
- Data protection measures
- Input validation
- Security test coverage

### Technical Lead
**When Involved:** Tier 1 and 2 changes with architectural impact

**Responsibilities:**
- Review technical implementation approach
- Validate architecture consistency
- Ensure performance requirements
- Approve complex refactoring

**Review Focus:**
- Code architecture patterns
- Performance implications
- Scalability considerations
- Technical debt impact

### QA Lead
**When Involved:** Tier 1 changes requiring comprehensive testing

**Responsibilities:**
- Review test coverage adequacy
- Validate testing strategy
- Ensure edge case coverage
- Approve release testing

**Review Focus:**
- Test coverage metrics
- Edge case testing
- Regression test strategy
- Test automation quality

## Review Process

### 1. Notification
When a PR is created or updated with a working spec, stakeholders are automatically notified based on:
- Risk tier of the change
- Areas affected by the change
- Stakeholder expertise areas

### 2. Review
Stakeholders review the change against their area of expertise:
- Read the working spec requirements
- Examine the implementation
- Run relevant tests or checks
- Provide feedback or approval

### 3. Sign-off
Required stakeholders must provide explicit approval:
- Comment with approval status
- Include rationale for decisions
- Suggest improvements if needed

### 4. Escalation
If stakeholders cannot reach consensus:
- Tech lead arbitration for technical issues
- Product manager decision for business issues
- Security team override for security concerns

## Tools and Resources

### CAWS Dashboard
Access the CAWS dashboard to view:
- Current trust scores and metrics
- Historical trends and insights
- Actionable recommendations
- Risk distribution across tiers

### Review Checklist
Each review includes a structured checklist covering:
- Specific questions for your area of expertise
- Required vs optional review items
- Status tracking and comments

### Working Spec
The working spec contains:
- Detailed requirements and constraints
- Risk assessment and mitigation
- Test plans and acceptance criteria
- Rollback and migration strategies

## Best Practices

### For Reviewers
1. **Review early and often** - Catch issues before they become problems
2. **Be specific** - Provide concrete feedback and suggestions
3. **Test your assumptions** - Verify that requirements are testable
4. **Consider edge cases** - Think about error conditions and unusual scenarios
5. **Document decisions** - Explain why you approve or reject changes

### For Developers
1. **Involve stakeholders early** - Get input during planning phase
2. **Provide context** - Explain the "why" behind changes
3. **Respond to feedback** - Address concerns promptly and thoroughly
4. **Update documentation** - Keep working specs current
5. **Test thoroughly** - Ensure changes work as expected

## Emergency Procedures

### Hotfixes and Urgent Changes
For critical issues requiring immediate deployment:
1. Create minimal working spec with \`human_override\` section
2. Notify stakeholders after deployment if time-critical
3. Complete full review process post-deployment
4. Address any identified issues in follow-up PR

### Rollback Situations
If a deployment causes issues:
1. Follow the rollback plan in the working spec
2. Notify all stakeholders immediately
3. Conduct root cause analysis
4. Update working spec for future prevention

## Support and Training

### Getting Help
- CAWS Documentation: [Link to full CAWS docs]
- Stakeholder Slack Channel: #caws-stakeholders
- Office Hours: Weekly Q&A sessions with CAWS team

### Training Resources
- CAWS Overview Presentation
- Role-specific training modules
- Hands-on workshops and examples
- Best practices and anti-patterns guide

## Continuous Improvement

CAWS evolves based on stakeholder feedback:
- Regular retrospectives on review process
- Metric tracking for review effectiveness
- Process improvements based on lessons learned
- Tool enhancements for better collaboration

---

*This guide is automatically generated and maintained by the CAWS Cross-Functional Integration Tool.*
`;

  fs.writeFileSync(outputPath, guide);
  console.log(`✅ Generated stakeholder guide: ${outputPath}`);
}

/**
 * Validate stakeholder assignments and notify if needed
 * @param {Object} checklist - Review checklist
 */
function validateStakeholderAssignments(checklist) {
  console.log('🔍 Validating stakeholder assignments...');

  const issues = [];
  const missingAssignments = [];

  // Check required stakeholders
  checklist.required_stakeholders.forEach((stakeholder) => {
    if (!stakeholder.assignee) {
      missingAssignments.push(stakeholder.role);
      issues.push(`Missing assignee for ${stakeholder.role}`);
    }
  });

  // Check for overdue reviews
  const now = new Date();
  const twoDaysAgo = new Date(now.getTime() - 2 * 24 * 60 * 60 * 1000);

  checklist.required_stakeholders.forEach((stakeholder) => {
    if (stakeholder.status === 'pending' && stakeholder.assigned_at) {
      const assignedAt = new Date(stakeholder.assigned_at);
      if (assignedAt < twoDaysAgo) {
        issues.push(
          `${stakeholder.role} review is overdue (assigned ${assignedAt.toLocaleDateString()})`
        );
      }
    }
  });

  if (issues.length > 0) {
    console.warn('\n⚠️  Review Issues Found:');
    issues.forEach((issue) => console.warn(`   - ${issue}`));

    if (missingAssignments.length > 0) {
      console.log('\n📧 To assign reviewers:');
      missingAssignments.forEach((role) => {
        console.log(`   - Assign ${role} via PR comment or GitHub assignment`);
      });
    }

    return false;
  }

  console.log('✅ All stakeholder assignments are valid');
  return true;
}

// CLI interface
if (require.main === module) {
  const command = process.argv[2];

  switch (command) {
    case 'generate-checklist':
      const specPath = process.argv[3] || '.caws/working-spec.yaml';
      const tier = parseInt(process.argv[4]) || 2;

      if (!fs.existsSync(specPath)) {
        console.error(`❌ Working spec not found: ${specPath}`);
        process.exit(1);
      }

      try {
        const checklist = generateReviewChecklist(specPath, tier);

        console.log('\n📋 Generated Cross-Functional Review Checklist:');
        console.log(`   Project: ${checklist.metadata.project_title}`);
        console.log(`   Tier: ${tier}`);
        console.log(`   Required Stakeholders: ${checklist.required_stakeholders.length}`);
        console.log(`   Optional Stakeholders: ${checklist.optional_stakeholders.length}`);

        // Save checklist
        const checklistPath = 'review-checklist.json';
        fs.writeFileSync(checklistPath, JSON.stringify(checklist, null, 2));
        console.log(`✅ Checklist saved: ${checklistPath}`);

        // Generate workflow
        generateIntegrationWorkflow(checklist);
      } catch (error) {
        console.error(`❌ Error generating checklist: ${error.message}`);
        process.exit(1);
      }
      break;

    case 'generate-guide':
      const guidePath = process.argv[3] || 'CAWS_STAKEHOLDER_GUIDE.md';

      try {
        generateStakeholderGuide(guidePath);
        console.log('\n📖 Generated comprehensive stakeholder guide');
        console.log('   Guide includes:');
        console.log('   - Role definitions and responsibilities');
        console.log('   - Review process and best practices');
        console.log('   - Tools and resources');
        console.log('   - Emergency procedures');
      } catch (error) {
        console.error(`❌ Error generating guide: ${error.message}`);
        process.exit(1);
      }
      break;

    case 'validate-assignments':
      const checklistPath = process.argv[3] || 'review-checklist.json';

      if (!fs.existsSync(checklistPath)) {
        console.error(`❌ Checklist not found: ${checklistPath}`);
        process.exit(1);
      }

      try {
        const checklist = JSON.parse(fs.readFileSync(checklistPath, 'utf8'));
        const isValid = validateStakeholderAssignments(checklist);

        if (isValid) {
          console.log('✅ All stakeholder assignments are complete and current');
        } else {
          console.error('❌ Stakeholder assignment issues found');
          process.exit(1);
        }
      } catch (error) {
        console.error(`❌ Error validating assignments: ${error.message}`);
        process.exit(1);
      }
      break;

    default:
      console.log('CAWS Cross-Functional Integration Tool');
      console.log('Usage:');
      console.log('  node cross-functional.js generate-checklist [spec-path] [tier]');
      console.log('  node cross-functional.js generate-guide [output-path]');
      console.log('  node cross-functional.js validate-assignments [checklist-path]');
      console.log('');
      console.log('Stakeholder Roles:');
      Object.values(STAKEHOLDER_ROLES).forEach((role) => {
        console.log(`  - ${role.name}: ${role.description}`);
      });
      console.log('');
      console.log('Examples:');
      console.log('  node cross-functional.js generate-checklist .caws/working-spec.yaml 1');
      console.log('  node cross-functional.js generate-guide docs/CAWS_STAKEHOLDER_GUIDE.md');
      console.log('  node cross-functional.js validate-assignments review-checklist.json');
      process.exit(1);
  }
}

module.exports = {
  generateReviewChecklist,
  generateNotificationTemplates,
  generateIntegrationWorkflow,
  generateStakeholderGuide,
  validateStakeholderAssignments,
  STAKEHOLDER_ROLES,
};
