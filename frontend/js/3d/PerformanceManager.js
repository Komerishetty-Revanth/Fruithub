export const TIERS = {
  high:   { pixelRatio: 2,   shadows: true,  env: true,  segments: 48, fruits: 7, particles: 90, antialias: true,  physical: true },
  medium: { pixelRatio: 1.5, shadows: false, env: true,  segments: 32, fruits: 6, particles: 40, antialias: true,  physical: false },
  low:    { pixelRatio: 1,   shadows: false, env: false, segments: 20, fruits: 4, particles: 0,  antialias: false, physical: false },
};

export function webglAvailable() {
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch {
    return false;
  }
}

// Returns "high" | "medium" | "low" | "static".
// For testing, open the page with ?tier=low (or high, medium, static).
export function detectTier() {
  const forced = new URLSearchParams(location.search).get("tier");
  if (forced && ["high", "medium", "low", "static"].includes(forced)) return forced;

  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return "static";
  if (!webglAvailable()) return "static";

  const cores = navigator.hardwareConcurrency || 4;
  const memory = navigator.deviceMemory || 4;
  const coarse = matchMedia("(pointer: coarse)").matches; // phones and tablets
  const saveData = !!(navigator.connection && navigator.connection.saveData);

  if (saveData || cores <= 2 || memory <= 2) return "low";
  if (coarse || cores <= 4 || memory <= 4) return "medium";
  return "high";
}

export function lowerTier(name) {
  return name === "high" ? "medium" : name === "medium" ? "low" : "static";
}

// Calls onSlow() when the average frame rate stays low (checked every 2 seconds).
export class FpsMonitor {
  constructor(onSlow) {
    this.onSlow = onSlow;
    this.frames = 0;
    this.time = 0;
    this.warm = 1.5; // ignore the first moments while shaders compile
    this.checks = 0;
  }
  tick(dt) {
    if (this.warm > 0) {
      this.warm -= dt;
      return;
    }
    this.frames++;
    this.time += dt;
    if (this.time >= 2) {
      const fps = this.frames / this.time;
      this.frames = 0;
      this.time = 0;
      if (fps < 28 && this.checks < 2) {
        this.checks++;
        this.warm = 1;
        this.onSlow(fps);
      }
    }
  }
}