package expo.modules.gemmainference

import expo.modules.kotlin.modules.Module
import expo.modules.kotlin.modules.ModuleDefinition

class GemmaInferenceModule : Module() {
  override fun definition() = ModuleDefinition {
    Name("GemmaInferenceModule")

    Events("onToken")

    AsyncFunction("isAvailable") { model: String ->
      // TODO: Hook ML Kit GenAI Prompt API checkFeatureStatus
      model == "e2b"
    }

    AsyncFunction("checkFeatureStatus") { _: String ->
      // TODO: return available | downloading | unavailable from AICore
      "unavailable"
    }

    AsyncFunction("generate") { _: String, prompt: String, _: Map<String, Any> ->
      // TODO: Use PromptRequest + addOnPartialResponseListener + Dispatchers.IO
      sendEvent("onToken", mapOf("token" to "[stub-token]"))
      "Stub Android response for: $prompt"
    }

    AsyncFunction("generateWithImage") { _: String, prompt: String, _: String ->
      // TODO: Decode base64 to Bitmap and pass as multimodal content
      "Stub Android image response for: $prompt"
    }

    AsyncFunction("generateWithAudio") { _: String, prompt: String, _: String ->
      // TODO: Decode PCM audio and pass as multimodal audio content
      "Stub Android audio response for: $prompt"
    }
  }
}
