import ExpoModulesCore

public class GemmaInferenceModule: Module {
  public func definition() -> ModuleDefinition {
    Name("GemmaInferenceModule")

    Events("onToken")

    AsyncFunction("isAvailable") { (_: String) in
      // TODO: Check MediaPipe model readiness.
      false
    }

    AsyncFunction("checkFeatureStatus") { (_: String) in
      // TODO: Return available | downloading | unavailable
      "unavailable"
    }

    AsyncFunction("generate") { (_: String, prompt: String, _: [String: Any]) in
      // TODO: Wire MediaPipe LlmInference.generateResponseAsync streaming.
      self.sendEvent("onToken", ["token": "[stub-token]"])
      return "Stub iOS response for: \(prompt)"
    }

    AsyncFunction("generateWithImage") { (_: String, prompt: String, _: String) in
      // TODO: base64 -> UIImage -> multimodal inference call.
      return "Stub iOS image response for: \(prompt)"
    }

    AsyncFunction("generateWithAudio") { (_: String, prompt: String, _: String) in
      // TODO: base64 -> PCM audio content.
      return "Stub iOS audio response for: \(prompt)"
    }
  }
}
