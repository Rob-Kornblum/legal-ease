import React, { useState, useEffect } from "react";

const EXAMPLES = [
  "Notwithstanding anything to the contrary contained herein, the party of the second part shall indemnify, defend, and hold harmless the party of the first part from and against any and all claims, liabilities, losses, and expenses (including reasonable attorneys’ fees) arising out of or relating to the performance of this Agreement, except to the extent caused by the gross negligence or willful misconduct of the party of the first part.",
  "This Agreement shall be binding upon and inure to the benefit of the parties hereto and their respective heirs, executors, administrators, successors, and assigns.",
  "The failure of either party to enforce any provision of this Agreement shall not constitute a waiver of such provision or the right to enforce it at a later time.",
  "All notices required or permitted hereunder shall be in writing and shall be deemed given when delivered personally, sent by certified mail, return receipt requested, or by a nationally recognized overnight courier service.",
  "To the extent permitted by law, each party hereby irrevocably waives all rights to trial by jury in any action or proceeding arising out of or relating to this Agreement.",
  "Nothing in this Agreement shall be construed to create a joint venture, partnership, or agency relationship between the parties, and neither party shall have the authority to bind the other in any respect.",
  "Any and all disputes arising out of or in connection with this Agreement shall be resolved exclusively by binding arbitration in accordance with the rules of the American Arbitration Association, and judgment upon the award rendered by the arbitrator(s) may be entered in any court having jurisdiction thereof.",
  "The license granted herein is non-exclusive, non-transferable, and revocable at the sole discretion of the Licensor, subject to the terms and conditions set forth in this Agreement.",
  "The undersigned acknowledges that he or she has read and fully understands the foregoing terms and conditions, and voluntarily agrees to be bound thereby, without reliance upon any representations or warranties not expressly set forth herein.",
  "This Agreement constitutes the entire understanding between the parties with respect to the subject matter hereof, and supersedes all prior or contemporaneous negotiations, representations, or agreements, whether written or oral."
];

const API_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";
const isLocal = API_URL.includes("localhost");

function App() {
  const [backendStatus, setBackendStatus] = useState(isLocal ? "up" : "unknown");
  const [legalese, setLegalese] = useState("");
  const [plainEnglish, setPlainEnglish] = useState("");
  const [loading, setLoading] = useState(false);

  const checkBackend = async () => {
    setBackendStatus("unknown");
    try {
      const res = await fetch(`${API_URL}/health`);
      if (res.ok) {
        setBackendStatus("up");
      } else {
        setBackendStatus("down");
      }
    } catch {
      setBackendStatus("down");
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setPlainEnglish("");
    try {
      const response = await fetch(`${API_URL}/simplify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: legalese }),
      });
      const data = await response.json();
      setPlainEnglish(data.result || data.plain_english || "No response.");
    } catch (err) {
      setPlainEnglish(
        "Error: Could not connect to backend. The server may be waking up. If this is your first request, please wait a few moments and try again."
      );
      setBackendStatus("down");
    }
    setLoading(false);
  };

  const handleAutoGenerate = () => {
    const random = EXAMPLES[Math.floor(Math.random() * EXAMPLES.length)];
    setLegalese(random);
  };

  const statusColor =
    backendStatus === "up"
      ? "green"
      : backendStatus === "down"
      ? "red"
      : "gray";
  const statusText =
    backendStatus === "up"
      ? "Backend is UP"
      : backendStatus === "down"
      ? "Backend is DOWN"
      : "Backend status unknown";

  return (
    <div style={{ maxWidth: 600, margin: "2rem auto", fontFamily: "sans-serif" }}>
      <div style={{ display: "flex", alignItems: "center", marginBottom: "1rem" }}>
        <div
          style={{
            width: 16,
            height: 16,
            borderRadius: "50%",
            background: statusColor,
            marginRight: 8,
            border: "1px solid #333",
          }}
        />
        <span>{statusText}</span>
        <button
          style={{ marginLeft: 16 }}
          onClick={checkBackend}
          disabled={backendStatus === "up"}
        >
          Wake Up Server
        </button>
      </div>
      <h2>Legalese to Plain English</h2>
      <form onSubmit={handleSubmit}>
        <textarea
          rows={4}
          style={{ width: "100%" }}
          placeholder="Enter legalese phrase..."
          value={legalese}
          onChange={(e) => setLegalese(e.target.value)}
          required
          disabled={backendStatus !== "up"}
        />
        <div style={{ display: "flex", gap: "1rem", marginTop: "1rem" }}>
          <button type="submit" disabled={loading || backendStatus !== "up"}>
            {loading ? "Translating..." : "Translate"}
          </button>
          <button type="button" onClick={handleAutoGenerate} disabled={loading}>
            Auto-Generate Example
          </button>
        </div>
      </form>
      {plainEnglish && (
        <div style={{ marginTop: "2rem", background: "#f4f4f4", padding: "1rem", borderRadius: 4 }}>
          <strong>Plain English:</strong>
          <div>{plainEnglish}</div>
        </div>
      )}
    </div>
  );
}

export default App;