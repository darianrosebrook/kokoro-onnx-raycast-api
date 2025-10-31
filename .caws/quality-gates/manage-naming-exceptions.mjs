#!/usr/bin/env node

/**
 * CAWS Naming Exception Manager
 *
 * Manages controlled exceptions for banned naming patterns.
 * Provides commands to add, list, renew, and remove exceptions.
 */

import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const PROJECT_ROOT = path.join(__dirname, "..", "..");
const EXCEPTION_CONFIG_PATH = path.join(
  PROJECT_ROOT,
  ".caws",
  "naming-exceptions.json"
);

// Default configuration template
const DEFAULT_CONFIG = {
  version: "1.0.0",
  description: "Controlled exceptions for banned naming patterns",
  schema: {
    exceptions: [
      {
        file_pattern: "string (glob pattern)",
        modifier: "string (banned modifier)",
        reason: "string (architectural justification)",
        approved_by: "string (engineer email)",
        approved_at: "string (ISO 8601 date)",
        expires_at: "string (ISO 8601 date)",
        review_required: "boolean",
      },
    ],
  },
  exceptions: [],
  enforcement_levels: {
    commit: "warning",
    push: "block",
    ci: "fail",
  },
};

// Load current configuration
function loadConfig() {
  try {
    if (fs.existsSync(EXCEPTION_CONFIG_PATH)) {
      const content = fs.readFileSync(EXCEPTION_CONFIG_PATH, "utf8");
      return JSON.parse(content);
    }
  } catch (error) {
    console.error(`❌ Error loading config: ${error.message}`);
    process.exit(1);
  }

  return DEFAULT_CONFIG;
}

// Save configuration
function saveConfig(config) {
  try {
    // Ensure .caws directory exists
    const cawsDir = path.dirname(EXCEPTION_CONFIG_PATH);
    if (!fs.existsSync(cawsDir)) {
      fs.mkdirSync(cawsDir, { recursive: true });
    }

    fs.writeFileSync(EXCEPTION_CONFIG_PATH, JSON.stringify(config, null, 2));
    console.log("✅ Configuration saved");
  } catch (error) {
    console.error(`❌ Error saving config: ${error.message}`);
    process.exit(1);
  }
}

// Add a new exception
function addException(
  filePattern,
  modifier,
  reason,
  approvedBy,
  expiresInDays = 180
) {
  const config = loadConfig();
  const now = new Date();
  const expiresAt = new Date(
    now.getTime() + expiresInDays * 24 * 60 * 60 * 1000
  );

  const exception = {
    file_pattern: filePattern,
    modifier: modifier.toLowerCase(),
    reason: reason,
    approved_by: approvedBy,
    approved_at: now.toISOString(),
    expires_at: expiresAt.toISOString(),
    review_required: true,
  };

  // Check for duplicates
  const existing = config.exceptions.find(
    (ex) =>
      ex.file_pattern === filePattern && ex.modifier === modifier.toLowerCase()
  );

  if (existing) {
    console.log(
      "⚠️  Exception already exists for this file pattern and modifier"
    );
    console.log(`   Current: ${existing.reason}`);
    console.log(`   Expires: ${existing.expires_at}`);
    return;
  }

  config.exceptions.push(exception);
  saveConfig(config);

  console.log("✅ Exception added:");
  console.log(`   Pattern: ${filePattern}`);
  console.log(`   Modifier: ${modifier}`);
  console.log(`   Reason: ${reason}`);
  console.log(`   Approved by: ${approvedBy}`);
  console.log(`   Expires: ${expiresAt.toISOString()}`);
}

// List all exceptions
function listExceptions() {
  const config = loadConfig();
  const now = new Date();

  if (config.exceptions.length === 0) {
    console.log("No exceptions configured");
    return;
  }

  console.log(`${config.exceptions.length} exceptions configured:`);
  console.log("");

  config.exceptions.forEach((exception, index) => {
    const expiresAt = new Date(exception.expires_at);
    const isExpired = expiresAt <= now;
    const daysUntilExpiry = Math.ceil(
      (expiresAt - now) / (1000 * 60 * 60 * 24)
    );

    const statusIcon = isExpired ? "🔴" : daysUntilExpiry < 30 ? "🟡" : "🟢";

    console.log(`${statusIcon} Exception ${index + 1}:`);
    console.log(`   Pattern: ${exception.file_pattern}`);
    console.log(`   Modifier: ${exception.modifier}`);
    console.log(`   Reason: ${exception.reason}`);
    console.log(`   Approved by: ${exception.approved_by}`);
    console.log(`   Approved at: ${exception.approved_at}`);
    console.log(`   Expires: ${exception.expires_at}`);
    console.log(
      `   Status: ${
        isExpired ? "EXPIRED" : `${daysUntilExpiry} days remaining`
      }`
    );
    console.log("");
  });
}

// Remove an exception
function removeException(filePattern, modifier) {
  const config = loadConfig();
  const initialLength = config.exceptions.length;

  config.exceptions = config.exceptions.filter(
    (ex) =>
      !(
        ex.file_pattern === filePattern &&
        ex.modifier === modifier.toLowerCase()
      )
  );

  if (config.exceptions.length === initialLength) {
    console.log("⚠️  No matching exception found");
    return;
  }

  saveConfig(config);
  console.log(`✅ Removed exception for ${filePattern} (${modifier})`);
}

// Renew an exception
function renewException(filePattern, modifier, expiresInDays = 180) {
  const config = loadConfig();
  const exception = config.exceptions.find(
    (ex) =>
      ex.file_pattern === filePattern && ex.modifier === modifier.toLowerCase()
  );

  if (!exception) {
    console.log("⚠️  No matching exception found");
    return;
  }

  const now = new Date();
  const expiresAt = new Date(
    now.getTime() + expiresInDays * 24 * 60 * 60 * 1000
  );

  exception.expires_at = expiresAt.toISOString();
  exception.approved_at = now.toISOString();

  saveConfig(config);
  console.log(`✅ Renewed exception for ${filePattern} (${modifier})`);
  console.log(`   New expiry: ${expiresAt.toISOString()}`);
}

// Set enforcement levels
function setEnforcementLevels(commitLevel, pushLevel, ciLevel) {
  const config = loadConfig();

  if (commitLevel) config.enforcement_levels.commit = commitLevel;
  if (pushLevel) config.enforcement_levels.push = pushLevel;
  if (ciLevel) config.enforcement_levels.ci = ciLevel;

  saveConfig(config);
  console.log("✅ Enforcement levels updated:");
  console.log(`   Commit: ${config.enforcement_levels.commit}`);
  console.log(`   Push: ${config.enforcement_levels.push}`);
  console.log(`   CI: ${config.enforcement_levels.ci}`);
}

// Show help
function showHelp() {
  console.log(`
CAWS Naming Exception Manager

Usage:
  node scripts/quality-gates/manage-naming-exceptions.js <command> [options]

Commands:
  add <pattern> <modifier> <reason> <approver> [days]  Add new exception
  list                                                  List all exceptions
  remove <pattern> <modifier>                          Remove exception
  renew <pattern> <modifier> [days]                    Renew exception
  levels <commit> <push> <ci>                         Set enforcement levels
  help                                                 Show this help

Examples:
  node scripts/quality-gates/manage-naming-exceptions.js add "**/unified-client.ts" unified "Official API standard" "engineer@company.com"
  node scripts/quality-gates/manage-naming-exceptions.js list
  node scripts/quality-gates/manage-naming-exceptions.js remove "**/unified-client.ts" unified
  node scripts/quality-gates/manage-naming-exceptions.js levels warning block fail

Enforcement Levels:
  warning  - Show warnings but allow commits
  block    - Block pushes but allow commits
  fail     - Fail CI/CD pipeline
`);
}

// Main execution
function main() {
  const args = process.argv.slice(2);

  if (args.length === 0) {
    showHelp();
    return;
  }

  const command = args[0];

  switch (command) {
    case "add":
      if (args.length < 5) {
        console.log(
          "❌ Usage: add <pattern> <modifier> <reason> <approver> [days]"
        );
        process.exit(1);
      }
      addException(
        args[1],
        args[2],
        args[3],
        args[4],
        parseInt(args[5]) || 180
      );
      break;

    case "list":
      listExceptions();
      break;

    case "remove":
      if (args.length < 3) {
        console.log("❌ Usage: remove <pattern> <modifier>");
        process.exit(1);
      }
      removeException(args[1], args[2]);
      break;

    case "renew":
      if (args.length < 3) {
        console.log("❌ Usage: renew <pattern> <modifier> [days]");
        process.exit(1);
      }
      renewException(args[1], args[2], parseInt(args[3]) || 180);
      break;

    case "levels":
      if (args.length < 4) {
        console.log("❌ Usage: levels <commit> <push> <ci>");
        process.exit(1);
      }
      setEnforcementLevels(args[1], args[2], args[3]);
      break;

    case "help":
      showHelp();
      break;

    default:
      console.log(`❌ Unknown command: ${command}`);
      showHelp();
      process.exit(1);
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main();
}
