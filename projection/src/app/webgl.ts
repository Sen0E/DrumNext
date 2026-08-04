export type WebGlCapability =
  | { supported: true; renderer: string }
  | { supported: false; reason: string };

export function detectWebGl2(documentObject: Document = document): WebGlCapability {
  const canvas = documentObject.createElement("canvas");
  const context = canvas.getContext("webgl2", {
    failIfMajorPerformanceCaveat: true
  });

  if (context === null) {
    return { supported: false, reason: "浏览器未提供硬件加速 WebGL2" };
  }

  const debugInfo = context.getExtension("WEBGL_debug_renderer_info");
  const renderer = debugInfo
    ? String(context.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL))
    : "WebGL2 renderer";
  context.getExtension("WEBGL_lose_context")?.loseContext();
  return { supported: true, renderer };
}

