/**
 * CAWS Waivers Manager
 * TypeScript wrapper for waivers management functionality
 *
 * @author @darianrosebrook
 */

import * as fs from 'fs';
import * as path from 'path';
import yaml from 'js-yaml';
import { WaiverConfig } from './types.js';
import { CawsBaseTool } from './base-tool.js';

export class WaiversManager extends CawsBaseTool {
  private readonly waiversPath: string;

  constructor(waiversPath?: string) {
    super();
    this.waiversPath = waiversPath || path.join(this.getCawsDirectory(), 'waivers.yml');
  }

  /**
   * Load waivers configuration
   */
  private loadWaiversConfig(): { waivers: WaiverConfig[] } {
    try {
      if (!fs.existsSync(this.waiversPath)) {
        return { waivers: [] };
      }

      const content = fs.readFileSync(this.waiversPath, 'utf8');
      return yaml.load(content) as { waivers: WaiverConfig[] };
    } catch (error) {
      this.logError(`Error loading waivers config: ${error}`);
      return { waivers: [] };
    }
  }

  /**
   * Save waivers configuration
   */
  private saveWaiversConfig(config: { waivers: WaiverConfig[] }): void {
    try {
      const yamlContent = yaml.dump(config, { indent: 2 });
      fs.writeFileSync(this.waiversPath, yamlContent);
      this.logSuccess(`Waivers configuration saved to ${this.waiversPath}`);
    } catch (error) {
      this.logError(`Error saving waivers config: ${error}`);
      throw error;
    }
  }

  /**
   * Get all waivers for a specific gate
   */
  async getWaiversByGate(gate: string): Promise<WaiverConfig[]> {
    const config = this.loadWaiversConfig();
    const now = new Date();

    return config.waivers.filter((waiver) => {
      // Check if waiver covers this gate
      if (waiver.gate !== gate) {
        return false;
      }

      // Check if waiver is still active
      const expiresAt = new Date(waiver.expiry);
      if (now > expiresAt) {
        return false;
      }

      return waiver.status === 'active';
    });
  }

  /**
   * Check waiver status
   */
  async checkWaiverStatus(waiverId: string): Promise<{
    active: boolean;
    waiver?: WaiverConfig;
    reason?: string;
  }> {
    const config = this.loadWaiversConfig();
    const now = new Date();

    const waiver = config.waivers.find((w) => w.created_at === waiverId);

    if (!waiver) {
      return { active: false, reason: 'Waiver not found' };
    }

    const expiresAt = new Date(waiver.expiry);
    if (now > expiresAt) {
      return { active: false, waiver, reason: 'Waiver expired' };
    }

    if (waiver.status !== 'active') {
      return { active: false, waiver, reason: `Waiver status: ${waiver.status}` };
    }

    return { active: true, waiver };
  }

  /**
   * Create a new waiver
   */
  async createWaiver(waiver: Omit<WaiverConfig, 'created_at'>): Promise<void> {
    const config = this.loadWaiversConfig();

    const newWaiver: WaiverConfig = {
      ...waiver,
      created_at: new Date().toISOString(),
    };

    config.waivers.push(newWaiver);
    this.saveWaiversConfig(config);
  }

  /**
   * Revoke a waiver
   */
  async revokeWaiver(gate: string, owner: string): Promise<void> {
    const config = this.loadWaiversConfig();

    const waiver = config.waivers.find(
      (w) => w.gate === gate && w.owner === owner && w.status === 'active'
    );

    if (waiver) {
      waiver.status = 'revoked';
      this.saveWaiversConfig(config);
      this.logSuccess(`Revoked waiver for gate: ${gate}`);
    } else {
      this.logWarning(`No active waiver found for gate: ${gate}`);
    }
  }

  /**
   * Cleanup expired waivers
   */
  async cleanupExpiredWaivers(): Promise<number> {
    const config = this.loadWaiversConfig();
    const now = new Date();

    const activeWaivers = config.waivers.filter((waiver) => {
      const expiresAt = new Date(waiver.expiry);
      return now <= expiresAt;
    });

    const removedCount = config.waivers.length - activeWaivers.length;

    if (removedCount > 0) {
      config.waivers = activeWaivers;
      this.saveWaiversConfig(config);
      this.logSuccess(`Cleaned up ${removedCount} expired waiver(s)`);
    }

    return removedCount;
  }

  /**
   * List all active waivers
   */
  async listActiveWaivers(): Promise<WaiverConfig[]> {
    const config = this.loadWaiversConfig();
    const now = new Date();

    return config.waivers.filter((waiver) => {
      const expiresAt = new Date(waiver.expiry);
      return now <= expiresAt && waiver.status === 'active';
    });
  }
}
