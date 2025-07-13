import React, { useState } from "react";
import Footer from "./Footer";

const EXAMPLES = [
  // Contract
  "Notwithstanding anything to the contrary contained herein, the party of the second part shall indemnify, defend, and hold harmless the party of the first part from and against any and all claims, liabilities, losses, and expenses (including reasonable attorneys’ fees) arising out of or relating to the performance of this Agreement, except to the extent caused by the gross negligence or willful misconduct of the party of the first part.",
  // Wills, Trusts, and Estates
  "I hereby bequeath all my personal property to my children, to be divided equally among them, and appoint my spouse as the executor of my estate.",
  "Upon my death, the trustee shall distribute the remaining assets of the trust to my grandchildren in equal shares.",
  // Criminal Procedure
  "The defendant is entitled to a speedy and public trial by an impartial jury of the State and district wherein the crime shall have been committed.",
  "Any evidence obtained in violation of the Fourth Amendment shall be inadmissible in a criminal prosecution.",
  // Family Law
  "The custodial parent shall have the right to make decisions regarding the child's education, health care, and religious upbringing.",
  // Real Estate
  "The buyer shall obtain title insurance at their own expense and the seller shall deliver a warranty deed at closing.",
  // Employment Law
  "The employee may not be terminated without cause during the initial probationary period.",
  // Personal Injury
  "The plaintiff seeks damages for injuries sustained in a car accident caused by the defendant's negligence."
];

const API_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";

function App() {
  const [legalese, setLegalese] = useState("");
  const [plainEnglish, setPlainEnglish] = useState("");
  const [category, setCategory] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setPlainEnglish("");
    setCategory("");
    try {
      const response = await fetch(`${API_URL}/simplify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: legalese }),
      });
      const data = await response.json();
      setPlainEnglish(data.response || data.result || data.plain_english || "No response.");
      setCategory(data.category || "");
    } catch (err) {
      setPlainEnglish(
        "Error: Could not connect to backend. Please try again later."
      );
      setCategory("");
    }
    setLoading(false);
  };

  const handleAutoGenerate = () => {
    const random = EXAMPLES[Math.floor(Math.random() * EXAMPLES.length)];
    setLegalese(random);
  };

  return (
    <div style={{ maxWidth: 600, margin: "2rem auto", fontFamily: "sans-serif" }}>
      <h2>Legalese to Plain English</h2>
      <form onSubmit={handleSubmit}>
        <textarea
          rows={4}
          style={{ width: "100%" }}
          placeholder="Enter legalese phrase..."
          value={legalese}
          onChange={(e) => setLegalese(e.target.value)}
          required
        />
        <div style={{ display: "flex", gap: "1rem", marginTop: "1rem" }}>
          <button type="submit" disabled={loading}>
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
      {category && (
        <div style={{ marginTop: "1rem", background: "#e9ecef", padding: "1rem", borderRadius: 4 }}>
          <strong>Legal Area:</strong> {category}
        </div>
      )}
      <Footer />
    </div>
  );
}

export default App;