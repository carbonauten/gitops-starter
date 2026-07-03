export function EmptyState({ message, icon = "📭" }: { message: string; icon?: string }) {
  return (
    <div className="empty-state empty-state-illustrated">
      <span className="empty-state-icon" aria-hidden="true">
        {icon}
      </span>
      <p>{message}</p>
    </div>
  );
}
