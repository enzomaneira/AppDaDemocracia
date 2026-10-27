import { useNavigate } from "react-router-dom";

import { useFollowMutation } from "../api/hooks";
import { useAuth } from "../auth/AuthContext";

export function FollowButton({
  id,
  following,
  name,
  compact,
}: {
  id: string;
  following: boolean;
  name: string;
  compact?: boolean;
}) {
  const { loggedIn } = useAuth();
  const nav = useNavigate();
  const m = useFollowMutation();

  const onClick = () => {
    // Uso anônimo só para navegar; seguir exige conta (RF01).
    if (!loggedIn) return nav("/entrar", { state: { next: location.pathname } });
    m.mutate({ id, follow: !following });
  };

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={m.isPending}
      aria-pressed={following}
      aria-label={following ? `Deixar de seguir ${name}` : `Seguir ${name}`}
      className={`${following ? "btn-secondary" : "btn-primary"} ${compact ? "min-h-9 px-3" : ""}`}
    >
      <span aria-hidden="true">{following ? "★" : "☆"}</span>
      {following ? "Seguindo" : "Seguir"}
    </button>
  );
}
