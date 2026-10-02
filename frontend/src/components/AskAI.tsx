import { useEffect, useState } from "react";
import { api } from "../api/client";

export default function AskAI() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [privacyMode, setPrivacyMode] = useState<boolean | null>(null);
  const [aiMode, setAiMode] = useState<string>("offline");

  useEffect(() => {
    api
      .aiStatus()
      .then((s) => {
        setPrivacyMode(Boolean(s.privacy_mode));
        setAiMode(String(s.ai_mode));
      })
      .catch(() => {});
  }, []);

  async function ask() {
    if (!question.trim()) return;
    setLoading(true);
    setAnswer(null);
    try {
      const result = await api.aiAsk(question.trim());
      setAnswer(result.answered ? result.response ?? "" : result.message ?? "No response.");
    } catch (e) {
      setAnswer(e instanceof Error ? e.message : "Request failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="border-t border-hairline px-3 py-2">
      <div className="mb-1.5 flex items-center justify-between">
        <span className="label">Ask AI ({aiMode})</span>
        {privacyMode && <span className="badge-simulated">🔒 Privacy Mode</span>}
      </div>
      <div className="flex gap-1">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && ask()}
          placeholder="What's happening in the room?"
          className="flex-1 border border-hairline bg-panel2 px-2 py-1 text-xs text-ink placeholder:text-muted2"
        />
        <button
          onClick={ask}
          disabled={loading}
          className="border border-hairline px-2 py-1 text-xs text-muted hover:text-signal disabled:opacity-50"
        >
          {loading ? "…" : "Ask"}
        </button>
      </div>
      {answer && <p className="mt-2 max-h-32 overflow-y-auto text-[11px] leading-relaxed text-muted">{answer}</p>}
    </div>
  );
}
