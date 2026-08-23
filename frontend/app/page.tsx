"use client";

import { CopilotChat } from "@copilotkit/react-ui";

export default function Home() {
  return (
    <main style={{ height: "100vh", display: "flex", flexDirection: "column" }}>
      <CopilotChat
        labels={{
          title: "FinBot",
          initial: "Hi! I'm FinBot, your fintech data assistant. Ask me anything.",
        }}
      />
    </main>
  );
}