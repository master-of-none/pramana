import { useRef } from "react";
import { createRoot } from "react-dom/client";
import { Chat } from "./chat/Chat.tsx";
import { Topbar } from "./components/Topbar.tsx";
import { useRoute } from "./lib/router.ts";
import { Study } from "./study/Study.tsx";
import "./style.css";

function App() {
  const route = useRoute();
  const section = route.path[0] === "study" ? "study" : "chat";
  const newChat = useRef<() => void>(() => undefined);
  return (
    <div className="app">
      <Topbar section={section} onNewChat={() => newChat.current()} />
      {/* Chat stays mounted while studying, so an answer in progress is not cancelled. */}
      <Chat
        active={section === "chat"}
        registerNewChat={(reset) => (newChat.current = reset)}
      />
      {section === "study" && <Study route={route} />}
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
