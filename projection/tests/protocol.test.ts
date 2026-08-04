import { readFileSync } from "node:fs";
import { fileURLToPath, URL } from "node:url";
import { describe, expect, it } from "vitest";
import { parseEnvelope, parsePlaybackSnapshot } from "../src/network/protocol";

const fixturePath = fileURLToPath(new URL("../../shared/fixtures/playback-snapshot.json", import.meta.url));
const fixture = JSON.parse(readFileSync(fixturePath, "utf8")) as unknown;

describe("protocol fixture", () => {
  it("parses the shared playback snapshot", () => {
    const envelope = parseEnvelope(fixture);
    expect(parsePlaybackSnapshot(envelope.payload)).toMatchObject({
      status: "playing",
      scoreId: "demo-score",
      positionMs: 2_500
    });
  });

  it("rejects an unsupported protocol", () => {
    expect(() => parseEnvelope({ ...(fixture as object), protocolVersion: 2 })).toThrow(
      "Unsupported protocolVersion"
    );
  });
});

