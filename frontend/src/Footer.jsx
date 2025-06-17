import React from "react";

function Footer() {
  return (
    <footer style={{ marginTop: "3rem", textAlign: "center", fontSize: "0.95rem", color: "#555" }}>
      <hr style={{ margin: "2rem 0" }} />
      <div>
        Created by <strong>Rob Kornblum</strong>
        &nbsp;|&nbsp;
        <a href="https://www.linkedin.com/in/robert-kornblum-1b851b1a2/" target="_blank" rel="noopener noreferrer">
          LinkedIn
        </a>
        &nbsp;|&nbsp;
        <a href="https://github.com/Rob-Kornblum/legal-ease" target="_blank" rel="noopener noreferrer">
          GitHub Repo
        </a>
      </div>
    </footer>
  );
}

export default Footer;