export interface ProjectionVisualSettings {
  readonly approachRingWidth: number;
  readonly approachRingOpacity: number;
  readonly lowPadScale: number;
  readonly midPadScale: number;
  readonly highPadScale: number;
  readonly centerPadScale: number;
}

export const DEFAULT_PROJECTION_VISUAL_SETTINGS: ProjectionVisualSettings = {
  approachRingWidth: 14,
  approachRingOpacity: 0.22,
  lowPadScale: 1,
  midPadScale: 1,
  highPadScale: 1,
  centerPadScale: 1
};
