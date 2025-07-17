#!/usr/bin/env node

// Required core modules
const fs = require("fs");
const path = require("path");

// Configuration
const TARGET_FOLDERS = ["./raycast/src", "./api", "./scripts"]; // Added scripts folder

const EXCLUDED_EMOJIS = new Set(["⚠️", "✅", "🚫", "ℹ️", "🔧", "👍🏼"]);
const EXCLUDED_EXTENSIONS = [".sh", ".md", ".json", ".lock", ".log", ".env"];
const EMOJI_REGEX = /\p{Emoji_Presentation}/gu;

/**
 * Recursively get all files in a directory, ignoring excluded extensions
 */
function getAllFiles(dir, fileList = []) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });

  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      getAllFiles(fullPath, fileList);
    } else {
      const ext = path.extname(entry.name);
      if (!EXCLUDED_EXTENSIONS.includes(ext)) {
        fileList.push(fullPath);
      }
    }
  }

  return fileList;
}

/**
 * Removes all emojis except the excluded set from the given text
 */
function stripUnwantedEmojis(text) {
  return text.replace(EMOJI_REGEX, (match) => {
    return EXCLUDED_EMOJIS.has(match) ? match : "";
  });
}

/**
 * Creates a backup of the file before processing
 */
function createBackup(filePath) {
  const backupPath = `${filePath}.backup`;
  try {
    fs.copyFileSync(filePath, backupPath);
    return backupPath;
  } catch (err) {
    console.error(`Failed to create backup for ${filePath}: ${err.message}`);
    return null;
  }
}

/**
 * Processes each file: strips emojis and overwrites content
 */
function processFile(filePath) {
  try {
    const original = fs.readFileSync(filePath, "utf8");
    const cleaned = stripUnwantedEmojis(original);

    if (original !== cleaned) {
      // Create backup before modifying
      const backupPath = createBackup(filePath);

      fs.writeFileSync(filePath, cleaned, "utf8");
      console.log(
        `Cleaned: ${filePath}${backupPath ? ` (backup: ${backupPath})` : ""}`
      );
      return true;
    }
    return false;
  } catch (err) {
    console.error(`Failed to process ${filePath}: ${err.message}`);
    return false;
  }
}

/**
 * Main
 */
function main() {
  console.log("Starting emoji stripping...");

  let totalFiles = 0;
  let cleanedFiles = 0;

  for (const folder of TARGET_FOLDERS) {
    if (!fs.existsSync(folder)) {
      console.warn(`Skipped non-existent folder: ${folder}`);
      continue;
    }

    const files = getAllFiles(folder);
    totalFiles += files.length;

    for (const file of files) {
      if (processFile(file)) {
        cleanedFiles++;
      }
    }
  }

  console.log(
    `Done. Processed ${totalFiles} files, cleaned ${cleanedFiles} files.`
  );
}

main();
