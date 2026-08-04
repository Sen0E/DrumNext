export interface PadConfig {
  readonly noteKey: string;
  readonly x: number;
  readonly y: number;
  readonly radius: number;
  readonly color: number;
  readonly label: string;
  readonly octaveLabel: string;
}

export interface DemoNote {
  readonly id: string;
  readonly timeMs: number;
  readonly noteKey: string;
  readonly velocity: number;
}

export const DEMO_DURATION_MS = 16_000;

export const DEMO_PADS: readonly PadConfig[] = [
  { noteKey: "low_1", x: 0.28, y: 0.70, radius: 0.057, color: 0x45a3ff, label: "1", octaveLabel: "L" },
  { noteKey: "low_2", x: 0.39, y: 0.76, radius: 0.057, color: 0x438cff, label: "2", octaveLabel: "L" },
  { noteKey: "low_3", x: 0.50, y: 0.79, radius: 0.057, color: 0x6678ff, label: "3", octaveLabel: "L" },
  { noteKey: "low_4", x: 0.61, y: 0.76, radius: 0.057, color: 0x8268f4, label: "4", octaveLabel: "L" },
  { noteKey: "low_5", x: 0.72, y: 0.70, radius: 0.057, color: 0xa75de1, label: "5", octaveLabel: "L" },
  { noteKey: "mid_1", x: 0.24, y: 0.50, radius: 0.052, color: 0x36c6d3, label: "1", octaveLabel: "M" },
  { noteKey: "mid_2", x: 0.37, y: 0.55, radius: 0.052, color: 0x3ec9a7, label: "2", octaveLabel: "M" },
  { noteKey: "mid_3", x: 0.50, y: 0.58, radius: 0.052, color: 0x63d785, label: "3", octaveLabel: "M" },
  { noteKey: "mid_4", x: 0.63, y: 0.55, radius: 0.052, color: 0xa1d66f, label: "4", octaveLabel: "M" },
  { noteKey: "mid_5", x: 0.76, y: 0.50, radius: 0.052, color: 0xe6ca67, label: "5", octaveLabel: "M" },
  { noteKey: "high_1", x: 0.31, y: 0.30, radius: 0.047, color: 0xffb64d, label: "1", octaveLabel: "H" },
  { noteKey: "high_2", x: 0.405, y: 0.25, radius: 0.047, color: 0xff9253, label: "2", octaveLabel: "H" },
  { noteKey: "high_3", x: 0.50, y: 0.23, radius: 0.047, color: 0xff6e69, label: "3", octaveLabel: "H" },
  { noteKey: "high_4", x: 0.595, y: 0.25, radius: 0.047, color: 0xef668e, label: "4", octaveLabel: "H" },
  { noteKey: "high_5", x: 0.69, y: 0.30, radius: 0.047, color: 0xd765b3, label: "5", octaveLabel: "H" }
];

export const DEMO_NOTES: readonly DemoNote[] = DEMO_PADS.map((pad, index) => ({
  id: `demo-${String(index + 1).padStart(2, "0")}`,
  timeMs: 1_000 + index * 900,
  noteKey: pad.noteKey,
  velocity: 0.72 + (index % 4) * 0.08
}));

