#!/usr/bin/env node

/**
 * @fileoverview CAWS Waivers Management Tool
 * Manages time-boxed waivers for quality gates
 * @author @darianrosebrook
 */

const fs = require('fs');
const yaml = require('js-yaml');

/**
 * Waiver reasons enum
 */
const WAIVER_REASONS = {
  URGENT_FIX: 'urgent_fix',
  EXPERIMENTAL: 'experimental',
  LEGACY_CODE: 'legacy_code',
  RESOURCE_CONSTRAINTS: 'resource_constraints',
  OTHER: 'other',
};

/**
 * Waivable gates
 */
const WAIVABLE_GATES = ['coverage', 'mutation', 'contracts', 'manual_review', 'trust_score'];

/**
 * Load waivers configuration
 * @param {string} waiversPath - Path to waivers.yml file
 * @returns {Object} Parsed waivers configuration
 */
function loadWaiversConfig(waiversPath = '.caws/waivers.yml') {
  try {
    if (!fs.existsSync(waiversPath)) {
      return { waivers: [] };
    }

    const content = fs.readFileSync(waiversPath, 'utf8');
    return yaml.load(content);
  } catch (error) {
    console.error('❌ Error loading waivers config:', error.message);
    return { waivers: [] };
  }
}

/**
 * Save waivers configuration
 * @param {Object} config - Waivers configuration
 * @param {string} waiversPath - Path to save waivers.yml file
 */
function saveWaiversConfig(config, waiversPath = '.caws/waivers.yml') {
  try {
    const yamlContent = yaml.dump(config, { indent: 2 });
    fs.writeFileSync(waiversPath, yamlContent);
    console.log(`✅ Waivers configuration saved to ${waiversPath}`);
  } catch (error) {
    console.error('❌ Error saving waivers config:', error.message);
    process.exit(1);
  }
}

/**
 * Find active waivers for a project and gate
 * @param {string} projectId - Project identifier
 * @param {string} gate - Gate to check
 * @param {string} waiversPath - Path to waivers.yml file
 * @returns {Array} Active waivers
 */
function findActiveWaivers(projectId, gate, waiversPath = '.caws/waivers.yml') {
  const config = loadWaiversConfig(waiversPath);
  const now = new Date();

  return config.waivers.filter((waiver) => {
    const expiresAt = new Date(waiver.expires_at);

    // Filter out expired waivers
    if (now > expiresAt) {
      console.warn(`⚠️  Waiver ${waiver.id} has expired (${waiver.expires_at})`);
      return false;
    }

    // Check if project specific
    if (waiver.projects && waiver.projects.length > 0) {
      if (!waiver.projects.includes(projectId)) {
        return false;
      }
    }

    // Check if gate is waived
    return waiver.gates.includes(gate);
  });
}

/**
 * Create a new waiver
 * @param {Object} options - Waiver options
 */
function createWaiver(options) {
  const {
    id,
    description,
    gates,
    reason,
    approver,
    expiresInDays = 7,
    projects = [],
    maxTrustScore = 79,
  } = options;

  // Validate inputs
  if (!id || !description || !gates || !reason || !approver) {
    console.error('❌ Missing required waiver fields');
    process.exit(1);
  }

  // Validate gates
  const invalidGates = gates.filter((gate) => !WAIVABLE_GATES.includes(gate));
  if (invalidGates.length > 0) {
    console.error(`❌ Invalid gates: ${invalidGates.join(', ')}`);
    console.error(`💡 Valid gates: ${WAIVABLE_GATES.join(', ')}`);
    process.exit(1);
  }

  // Validate reason
  if (!Object.values(WAIVER_REASONS).includes(reason)) {
    console.error(`❌ Invalid reason: ${reason}`);
    console.error(`💡 Valid reasons: ${Object.values(WAIVER_REASONS).join(', ')}`);
    process.exit(1);
  }

  const expiresAt = new Date();
  expiresAt.setDate(expiresAt.getDate() + expiresInDays);

  const waiver = {
    id,
    description,
    gates,
    reason,
    approver,
    expires_at: expiresAt.toISOString(),
    projects,
    max_trust_score: maxTrustScore,
  };

  // Load existing waivers
  const config = loadWaiversConfig();

  // Check for duplicate ID
  const existingWaiver = config.waivers.find((w) => w.id === id);
  if (existingWaiver) {
    console.error(`❌ Waiver with ID ${id} already exists`);
    process.exit(1);
  }

  // Add new waiver
  config.waivers.push(waiver);

  // Save configuration
  saveWaiversConfig(config);

  console.log(`✅ Created waiver ${id}`);
  console.log(`   Description: ${description}`);
  console.log(`   Gates: ${gates.join(', ')}`);
  console.log(`   Reason: ${reason}`);
  console.log(`   Expires: ${expiresAt.toISOString()}`);
  if (projects.length > 0) {
    console.log(`   Projects: ${projects.join(', ')}`);
  }
  console.log(`   Max Trust Score: ${maxTrustScore}`);
}

/**
 * List all waivers
 * @param {string} waiversPath - Path to waivers.yml file
 */
function listWaivers(waiversPath = '.caws/waivers.yml') {
  const config = loadWaiversConfig(waiversPath);

  if (config.waivers.length === 0) {
    console.log('ℹ️  No waivers configured');
    return;
  }

  console.log('📋 Active Waivers:');
  const now = new Date();

  config.waivers.forEach((waiver) => {
    const expiresAt = new Date(waiver.expires_at);
    const isExpired = now > expiresAt;
    const status = isExpired ? '🔴 EXPIRED' : '🟢 ACTIVE';
    const daysLeft = Math.ceil((expiresAt - now) / (1000 * 60 * 60 * 24));

    console.log(`\n${status} Waiver: ${waiver.id}`);
    console.log(`   Description: ${waiver.description}`);
    console.log(`   Gates: ${waiver.gates.join(', ')}`);
    console.log(`   Reason: ${waiver.reason}`);
    console.log(`   Approver: ${waiver.approver}`);
    console.log(`   Expires: ${waiver.expires_at} (${daysLeft} days)`);
    if (waiver.projects && waiver.projects.length > 0) {
      console.log(`   Projects: ${waiver.projects.join(', ')}`);
    }
    if (waiver.max_trust_score) {
      console.log(`   Max Trust Score: ${waiver.max_trust_score}`);
    }
  });
}

/**
 * Remove expired waivers
 * @param {string} waiversPath - Path to waivers.yml file
 */
function cleanupExpiredWaivers(waiversPath = '.caws/waivers.yml') {
  const config = loadWaiversConfig(waiversPath);
  const now = new Date();

  const activeWaivers = config.waivers.filter((waiver) => {
    const expiresAt = new Date(waiver.expires_at);
    return now <= expiresAt;
  });

  const removedCount = config.waivers.length - activeWaivers.length;

  if (removedCount > 0) {
    config.waivers = activeWaivers;
    saveWaiversConfig(config);
    console.log(`✅ Cleaned up ${removedCount} expired waiver(s)`);
  } else {
    console.log('ℹ️  No expired waivers to clean up');
  }
}

/**
 * Check if a specific gate is waived for a project
 * @param {string} projectId - Project identifier
 * @param {string} gate - Gate to check
 * @param {string} waiversPath - Path to waivers.yml file
 * @returns {Object} Waiver status information
 */
function checkWaiverStatus(projectId, gate, waiversPath = '.caws/waivers.yml') {
  const activeWaivers = findActiveWaivers(projectId, gate, waiversPath);

  if (activeWaivers.length === 0) {
    return {
      waived: false,
      reason: null,
      maxTrustScore: 100,
    };
  }

  // Find the most restrictive waiver (lowest max trust score)
  const applicableWaiver = activeWaivers.reduce((mostRestrictive, waiver) => {
    if (
      !mostRestrictive ||
      (waiver.max_trust_score && waiver.max_trust_score < mostRestrictive.max_trust_score)
    ) {
      return waiver;
    }
    return mostRestrictive;
  }, null);

  return {
    waived: true,
    reason: applicableWaiver.reason,
    maxTrustScore: applicableWaiver.max_trust_score || 79,
    waiverId: applicableWaiver.id,
    expiresAt: applicableWaiver.expires_at,
  };
}

// CLI interface
if (require.main === module) {
  const command = process.argv[2];

  switch (command) {
    case 'create':
      createWaiver({
        id: process.argv[3],
        description: process.argv[4],
        gates: process.argv[5]?.split(',') || [],
        reason: process.argv[6],
        approver: process.argv[7],
        expiresInDays: parseInt(process.argv[8]) || 7,
        projects: process.argv[9]?.split(',') || [],
        maxTrustScore: parseInt(process.argv[10]) || 79,
      });
      break;

    case 'list':
      listWaivers();
      break;

    case 'cleanup':
      cleanupExpiredWaivers();
      break;

    case 'check':
      const projectId = process.argv[3];
      const gate = process.argv[4];
      if (!projectId || !gate) {
        console.error('❌ Usage: node waivers.js check <project-id> <gate>');
        process.exit(1);
      }
      const status = checkWaiverStatus(projectId, gate);
      console.log(`Waiver status for ${gate} on project ${projectId}:`);
      console.log(`   Waived: ${status.waived}`);
      if (status.waived) {
        console.log(`   Reason: ${status.reason}`);
        console.log(`   Max Trust Score: ${status.maxTrustScore}`);
        console.log(`   Waiver ID: ${status.waiverId}`);
        console.log(`   Expires: ${status.expiresAt}`);
      }
      break;

    default:
      console.log('CAWS Waivers Management Tool');
      console.log('Usage:');
      console.log(
        '  node waivers.js create <id> <description> <gates> <reason> <approver> [expires-days] [projects] [max-trust-score]'
      );
      console.log('  node waivers.js list');
      console.log('  node waivers.js cleanup');
      console.log('  node waivers.js check <project-id> <gate>');
      console.log('');
      console.log('Examples:');
      console.log(
        '  node waivers.js create HOTFIX-001 "Urgent security fix" "mutation,coverage" urgent_fix "senior-dev" 3'
      );
      console.log('  node waivers.js check FEAT-1234 mutation');
      process.exit(1);
  }
}

module.exports = {
  loadWaiversConfig,
  saveWaiversConfig,
  findActiveWaivers,
  checkWaiverStatus,
  createWaiver,
  listWaivers,
  cleanupExpiredWaivers,
  WAIVER_REASONS,
  WAIVABLE_GATES,
};
