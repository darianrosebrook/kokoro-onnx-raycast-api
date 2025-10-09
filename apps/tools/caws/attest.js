#!/usr/bin/env node

/**
 * @fileoverview CAWS Attestation Generator
 * Generates SBOM and SLSA attestations for supply chain security
 * @author @darianrosebrook
 */

const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

/**
 * Generate Software Bill of Materials (SBOM)
 * @param {string} projectPath - Path to project directory
 * @returns {Object} SBOM in SPDX format
 */
function generateSBOM(projectPath = ".") {
  const packageJsonPath = path.join(projectPath, "package.json");

  if (!fs.existsSync(packageJsonPath)) {
    console.error("❌ No package.json found");
    return null;
  }

  try {
    const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, "utf8"));

    const sbom = {
      spdxId: "SPDXRef-DOCUMENT",
      spdxVersion: "SPDX-2.3",
      creationInfo: {
        created: new Date().toISOString(),
        creators: ["Tool: caws-cli-1.0.0"],
      },
      name: packageJson.name || "unknown-project",
      dataLicense: "CC0-1.0",
      SPDXID: "SPDXRef-DOCUMENT",
      documentNamespace: `https://caws.dev/sbom/${
        packageJson.name || "unknown"
      }-${Date.now()}`,
      packages: [
        {
          SPDXID: "SPDXRef-Package-Root",
          name: packageJson.name || "unknown",
          version: packageJson.version || "0.0.0",
          downloadLocation: "NOASSERTION",
          filesAnalyzed: false,
          supplier: "Organization: Unknown",
          originator: "Organization: Unknown",
          copyrightText: "NOASSERTION",
          packageVerificationCode: {
            packageVerificationCodeValue: crypto
              .createHash("sha256")
              .update("no files analyzed")
              .digest("hex"),
          },
        },
      ],
      relationships: [],
    };

    // Add dependencies as packages
    if (packageJson.dependencies) {
      Object.entries(packageJson.dependencies).forEach(([name, version]) => {
        const packageId = `SPDXRef-Package-${name.replace(
          /[^a-zA-Z0-9]/g,
          "-"
        )}`;

        sbom.packages.push({
          SPDXID: packageId,
          name,
          version,
          downloadLocation: "NOASSERTION",
          filesAnalyzed: false,
          supplier: "Organization: Unknown",
          originator: "Organization: Unknown",
          copyrightText: "NOASSERTION",
          packageVerificationCode: {
            packageVerificationCodeValue: crypto
              .createHash("sha256")
              .update(name + version)
              .digest("hex"),
          },
        });

        // Add relationship
        sbom.relationships.push({
          spdxElementId: "SPDXRef-Package-Root",
          relationshipType: "DEPENDS_ON",
          relatedSpdxElement: packageId,
        });
      });
    }

    // Add dev dependencies
    if (packageJson.devDependencies) {
      Object.entries(packageJson.devDependencies).forEach(([name, version]) => {
        const packageId = `SPDXRef-Package-Dev-${name.replace(
          /[^a-zA-Z0-9]/g,
          "-"
        )}`;

        sbom.packages.push({
          SPDXID: packageId,
          name,
          version,
          downloadLocation: "NOASSERTION",
          filesAnalyzed: false,
          supplier: "Organization: Unknown",
          originator: "Organization: Unknown",
          copyrightText: "NOASSERTION",
          packageVerificationCode: {
            packageVerificationCodeValue: crypto
              .createHash("sha256")
              .update(name + version)
              .digest("hex"),
          },
        });

        // Add relationship
        sbom.relationships.push({
          spdxElementId: "SPDXRef-Package-Root",
          relationshipType: "DEV_DEPENDENCY_OF",
          relatedSpdxElement: packageId,
        });
      });
    }

    return sbom;
  } catch (error) {
    console.error("❌ Error generating SBOM:", error.message);
    return null;
  }
}

/**
 * Generate SLSA attestation
 * @param {Object} options - Attestation options
 * @returns {Object} SLSA attestation
 */
function generateSLSA(options = {}) {
  const {
    builder = "https://github.com/caws/cli",
    buildType = "https://github.com/caws/cli@v1.0.0",
    invocationId = crypto.randomUUID(),
    parameters = {},
    materials = [],
    byproducts = [],
  } = options;

  return {
    _type: "https://in-toto.io/Statement/v0.1",
    subject: [],
    predicateType: "https://slsa.dev/provenance/v0.2",
    predicate: {
      builder: {
        id: builder,
      },
      buildType,
      invocation: {
        configSource: {
          uri: "git+https://github.com/caws/cli",
          digest: {
            sha1: "unknown",
          },
        },
        parameters,
        environment: {
          platform: process.platform,
          arch: process.arch,
          nodeVersion: process.version,
        },
      },
      buildConfig: {},
      metadata: {
        invocationId,
        startedOn: new Date().toISOString(),
        finishedOn: new Date().toISOString(),
      },
      materials,
      byproducts,
    },
  };
}

/**
 * Generate in-toto attestation
 * @param {Object} options - Attestation options
 * @returns {Object} In-toto attestation
 */
function generateInToto(options = {}) {
  const {
    subject = [],
    predicateType = "https://caws.dev/attestation/v1",
    predicate = {},
  } = options;

  return {
    _type: "https://in-toto.io/Statement/v0.1",
    subject,
    predicateType,
    predicate: {
      ...predicate,
      timestamp: new Date().toISOString(),
      generator: {
        name: "caws-cli",
        version: "1.0.0",
      },
    },
  };
}

/**
 * Save attestation to file
 * @param {Object} attestation - Attestation object
 * @param {string} outputPath - Output file path
 */
function saveAttestation(attestation, outputPath) {
  try {
    // Ensure directory exists
    const dir = path.dirname(outputPath);
    fs.mkdirSync(dir, { recursive: true });

    fs.writeFileSync(outputPath, JSON.stringify(attestation, null, 2));
    console.log(`✅ Attestation saved to ${outputPath}`);
  } catch (error) {
    console.error("❌ Error saving attestation:", error.message);
    process.exit(1);
  }
}

/**
 * Generate complete attestation bundle
 * @param {string} projectPath - Path to project
 * @param {Object} options - Attestation options
 * @returns {Object} Complete attestation bundle
 */
function generateAttestationBundle(projectPath = ".", options = {}) {
  const sbom = generateSBOM(projectPath);

  if (!sbom) {
    console.error("❌ Failed to generate SBOM");
    return null;
  }

  const slsa = generateSLSA({
    parameters: {
      projectPath,
      cawsVersion: "1.0.0",
      ...options.parameters,
    },
    materials: [
      {
        uri: `git+${projectPath}`,
        digest: {
          sha1: "unknown",
        },
      },
    ],
    byproducts: [
      {
        name: "sbom.json",
        digest: {
          sha256: crypto
            .createHash("sha256")
            .update(JSON.stringify(sbom))
            .digest("hex"),
        },
      },
    ],
  });

  const intoto = generateInToto({
    subject: [
      {
        name: "sbom.json",
        digest: {
          sha256: crypto
            .createHash("sha256")
            .update(JSON.stringify(sbom))
            .digest("hex"),
        },
      },
    ],
    predicate: {
      caws_version: "1.0.0",
      attestation_type: "sbom",
      project_info: {
        name: sbom.name,
        version: sbom.packages[0].version,
      },
    },
  });

  return {
    sbom,
    slsa,
    intoto,
  };
}

// CLI interface
if (require.main === module) {
  const command = process.argv[2];
  const projectPath = process.argv[3] || ".";

  switch (command) {
    case "sbom":
      const sbom = generateSBOM(projectPath);
      if (sbom) {
        console.log(JSON.stringify(sbom, null, 2));
      }
      break;

    case "slsa":
      const slsa = generateSLSA();
      console.log(JSON.stringify(slsa, null, 2));
      break;

    case "intoto":
      const intoto = generateInToto();
      console.log(JSON.stringify(intoto, null, 2));
      break;

    case "bundle":
      const bundle = generateAttestationBundle(projectPath);
      if (bundle) {
        // Save individual files
        saveAttestation(bundle.sbom, ".agent/sbom.json");
        saveAttestation(bundle.slsa, ".agent/slsa.json");
        saveAttestation(bundle.intoto, ".agent/intoto.json");

        // Print bundle
        console.log(JSON.stringify(bundle, null, 2));
      }
      break;

    default:
      console.log("CAWS Attestation Tool");
      console.log("Usage:");
      console.log("  node attest.js sbom [projectPath]");
      console.log("  node attest.js slsa");
      console.log("  node attest.js intoto");
      console.log("  node attest.js bundle [projectPath]");
      process.exit(1);
  }
}

module.exports = {
  generateSBOM,
  generateSLSA,
  generateInToto,
  generateAttestationBundle,
  saveAttestation,
};
