type Participant = {
  initials: string
  color: string
}

export function AvatarGroup({ participants }: { participants: Participant[] }) {
  const visible = participants.slice(0, 3)
  const remaining = participants.length - visible.length

  return (
    <div className="member-stack" role="group" aria-label={`${participants.length} participants`}>
      {visible.map((participant, index) => (
        <span key={`${participant.initials}-${index}`} className={`member-avatar ${participant.color}`}>
          {participant.initials}
        </span>
      ))}
      {remaining > 0 && <span className="member-more" aria-label={`${remaining} more participants`}>+{remaining}</span>}
    </div>
  )
}
