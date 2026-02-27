import threading

import azure.cognitiveservices.speech as speechsdk
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from ankify.settings import AzureProviderAccess

_CONTINUOUS_TIMEOUT_S = 10


class AzureSTTHelper:
    """Thin wrapper around Azure Speech SDK for speech-to-text in tests."""

    @staticmethod
    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(),
        retry=retry_if_exception_type(RuntimeError),
    )
    def transcribe(
        audio_bytes: bytes,
        language_code: str,
        azure_access: AzureProviderAccess,
    ) -> str:
        """Transcribe MP3 audio bytes via Azure continuous recognition.

        Uses continuous recognition instead of ``recognize_once`` so that
        pauses inside the audio (e.g. between slash-separated alternatives)
        do not cause premature truncation.
        """
        speech_config = speechsdk.SpeechConfig(
            subscription=azure_access.subscription_key.get_secret_value(),
            region=azure_access.region,
        )
        speech_config.speech_recognition_language = language_code

        compressed_format = speechsdk.audio.AudioStreamFormat(
            compressed_stream_format=speechsdk.audio.AudioStreamContainerFormat.MP3
        )
        stream = speechsdk.audio.PushAudioInputStream(compressed_format)
        stream.write(audio_bytes)
        stream.close()

        audio_config = speechsdk.audio.AudioConfig(stream=stream)
        recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config,
            audio_config=audio_config,
        )

        # -- continuous recognition: collect all segments ----------------
        done = threading.Event()
        segments: list[str] = []
        errors: list[str] = []

        def _on_recognized(evt: speechsdk.SpeechRecognitionEventArgs) -> None:
            if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
                segments.append(evt.result.text)

        def _on_canceled(evt: speechsdk.SpeechRecognitionCanceledEventArgs) -> None:
            cancellation = evt.result.cancellation_details
            if cancellation.reason == speechsdk.CancellationReason.Error:
                errors.append(
                    f"Azure STT failed: {cancellation.reason} — {cancellation.error_details}"
                )
            done.set()

        def _on_session_stopped(evt: speechsdk.SessionEventArgs) -> None:
            done.set()

        recognizer.recognized.connect(_on_recognized)
        recognizer.canceled.connect(_on_canceled)
        recognizer.session_stopped.connect(_on_session_stopped)

        recognizer.start_continuous_recognition()
        done.wait(timeout=_CONTINUOUS_TIMEOUT_S)
        recognizer.stop_continuous_recognition()

        if errors:
            raise RuntimeError(errors[0])

        return " ".join(segments)
