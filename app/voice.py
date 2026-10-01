class VoiceController:
    """Optional local voice I/O. Core agent remains usable without it."""

    def __init__(self, activity):
        self.activity = activity

    def _speech_recognition(self):
        try:
            import speech_recognition as sr
            return sr
        except ImportError as exc:
            raise RuntimeError(
                "Voice input needs SpeechRecognition and PyAudio. "
                "Install the optional voice dependencies."
            ) from exc

    def listen(self, timeout=5, phrase_time_limit=20):
        sr = self._speech_recognition()
        recognizer = sr.Recognizer()
        with sr.Microphone() as source:
            self.activity.emit("VOICE -> listening")
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = recognizer.listen(
                source,
                timeout=max(1, int(timeout)),
                phrase_time_limit=max(1, int(phrase_time_limit)),
            )
        try:
            text = recognizer.recognize_google(audio)
        except sr.UnknownValueError:
            return ""
        self.activity.emit("VOICE -> recognized")
        return text

    def speak(self, text):
        try:
            import pyttsx3
        except ImportError as exc:
            raise RuntimeError("Voice output needs pyttsx3.") from exc
        engine = pyttsx3.init()
        engine.say(str(text))
        engine.runAndWait()
        self.activity.emit("VOICE -> spoken")
        return True
