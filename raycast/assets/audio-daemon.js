#!/usr/bin/env node

// This file is bundled with the Raycast extension as a static asset so that the
// daemon script is always available at runtime. The controller copies this file
// to Raycast's support directory before spawning it, avoiding reliance on
// environment variables or project-relative paths.

export { AudioDaemon, AudioProcessor, AudioFormat, AudioRingBuffer } from "../bin/audio-daemon.js";
