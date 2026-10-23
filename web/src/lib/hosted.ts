import { useEffect, useRef, useState } from "react";

// Hosted mode only: Cloudflare Turnstile proves a person is asking. Tokens are single
// use, so the widget is reset after each question. Local mode loads nothing.
type Turnstile = {
  render: (el: HTMLElement, options: Record<string, unknown>) => string;
  reset: (id: string) => void;
};
declare global {
  interface Window {
    turnstile?: Turnstile;
  }
}

const SCRIPT =
  "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";

export function useHumanCheck() {
  const [siteKey, setSiteKey] = useState("");
  const [token, setToken] = useState("");
  const widget = useRef<string | null>(null);
  const holder = useRef<HTMLDivElement>(null);
  useEffect(() => {
    fetch("/api/config")
      .then((r): Promise<{ hosted?: boolean; turnstile_site_key?: unknown }> =>
        r.ok ? r.json() : Promise.resolve({}),
      )
      .then(
        (c) =>
          c?.hosted &&
          typeof c.turnstile_site_key === "string" &&
          setSiteKey(c.turnstile_site_key),
      )
      .catch(() => undefined);
  }, []);
  useEffect(() => {
    if (!siteKey || !holder.current) return;
    const render = () => {
      if (!window.turnstile || !holder.current || widget.current) return;
      widget.current = window.turnstile.render(holder.current, {
        sitekey: siteKey,
        callback: (t: string) => setToken(t),
        "expired-callback": () => setToken(""),
      });
    };
    if (window.turnstile) return render();
    const script = document.createElement("script");
    script.src = SCRIPT;
    script.async = true;
    script.onload = render;
    document.head.appendChild(script);
  }, [siteKey]);
  return {
    hosted: Boolean(siteKey),
    ready: !siteKey || Boolean(token),
    holder,
    headers: (): Record<string, string> => ({
      "x-request-id": crypto.randomUUID(),
      ...(token ? { "x-turnstile-token": token } : {}),
    }),
    reset: () => {
      if (widget.current && window.turnstile)
        window.turnstile.reset(widget.current);
      setToken("");
    },
  };
}
