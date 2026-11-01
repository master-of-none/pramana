import type { ReactNode } from "react";

export function Status({ error, children }: { error?: string; children?: ReactNode }) {
  if (error)
    return (
      <p className="study-status" role="alert">
        {error}
      </p>
    );
  return (
    <p className="study-status" role="status">
      {children ?? "Opening the texts…"}
    </p>
  );
}
