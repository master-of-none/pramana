import { useEffect, useRef } from "react";
import { createRoot } from "react-dom/client";
import { Chat } from "./chat/Chat.tsx";
import { NEW_CHAT, Palette } from "./components/Palette.tsx";
import { Shortcuts } from "./components/Shortcuts.tsx";
import { Topbar } from "./components/Topbar.tsx";
import { leavePage, useRoute } from "./lib/router.ts";
import { Study } from "./study/Study.tsx";
import "./styles/fonts.css";
import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/chat.css";
import "./styles/study.css";
import "./styles/reader.css";

function App() {
  const route = useRoute();
  const section = route.path[0] === "study" ? "study" : "chat";
  const newChat = useRef<() => void>(() => undefined);
  useEffect(() => {
    if (section === "chat") leavePage();
  }, [section]);
  useEffect(() => {
    const reset = () => newChat.current();
    window.addEventListener(NEW_CHAT, reset);
    return () => window.removeEventListener(NEW_CHAT, reset);
  }, []);
  return (
    <div className="app">
      <Topbar section={section} onNewChat={() => newChat.current()} />
      {/* Chat stays mounted while studying, so an answer in progress is not cancelled. */}
      <Chat
        active={section === "chat"}
        registerNewChat={(reset) => (newChat.current = reset)}
      />
      {section === "study" && <Study route={route} />}
      <Palette section={section} />
      <Shortcuts />
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
