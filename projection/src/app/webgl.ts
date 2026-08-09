export type WebGlCapability =
  | { supported: true }
  | { supported: false; reason: string };

export function detectWebGl2(documentObject: Document = document): WebGlCapability {
  const canvas = documentObject.createElement("canvas");
  const context = canvas.getContext("webgl2", {
    failIfMajorPerformanceCaveat: true
  });

  if (context === null) {
    return { supported: false, reason: "浏览器未提供硬件加速 WebGL2" };
  }

  context.getExtension("WEBGL_lose_context")?.loseContext();
  return { supported: true };
}
